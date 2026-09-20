#!/usr/bin/env python3
"""Family Wall local service. Calendar credentials never enter the browser."""
import argparse
import copy
import hashlib
import hmac
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import mimetypes
import os
import secrets
import subprocess
import threading
import time
from datetime import date, datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import requests
from photos import sync_photos
from highlights import Highlights, quotes

TZ=ZoneInfo('America/Denver')
DEFAULTS={'calendar_name':'Family','album_url':'',
          'windows':[['06:00','08:30'],['16:30','19:00']],'photo_seconds':60,
          'latitude':None,'longitude':None}


def atomic_json(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name(path.name+'.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(data,f)
    temporary.replace(path)
    path.chmod(0o600)


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        fd=os.open(self.baseFilename,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        return os.fdopen(fd,'a',encoding='utf-8')


def configure_display_log(folder):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=folder/'display.log'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    os.close(fd)
    path.chmod(0o600)
    handler=PrivateRotatingFileHandler(path,maxBytes=256*1024,backupCount=3,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger=logging.getLogger('family_wall.display')
    logger.setLevel(logging.INFO)
    logger.propagate=False
    for old in list(logger.handlers):
        logger.removeHandler(old)
        old.close()
    logger.addHandler(handler)
    return logger


def week_days(now):
    start=now.date()-timedelta(days=now.weekday())
    return [(start+timedelta(days=i)).isoformat() for i in range(7)]


def in_schedule(now,windows):
    minute=now.hour*60+now.minute
    for start,end in windows:
        a,b=(int(v[:2])*60+int(v[3:]) for v in (start,end))
        if (a<b and a<=minute<b) or (a>b and (minute>=a or minute<b)):
            return True
    return False


def validate_settings(data):
    windows=data.get('windows')
    if not isinstance(windows,list) or len(windows)!=2:
        raise ValueError('Enter two daily display windows.')
    import re
    for pair in windows:
        if not isinstance(pair,list) or len(pair)!=2 or any(not isinstance(x,str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',x) for x in pair):
            raise ValueError('Use valid on and off times.')
        if pair[0]==pair[1]:
            raise ValueError('On and off times must differ.')
    seconds=data.get('photo_seconds')
    if isinstance(seconds,bool) or not isinstance(seconds,int) or not 15<=seconds<=3600:
        raise ValueError('Photo interval must be 15–3600 seconds.')
    return {'windows':windows,'photo_seconds':seconds}


def calendar_events(config,now):
    import caldav
    import icalendar
    week=week_days(now)
    start=datetime.combine(date.fromisoformat(week[0]),datetime.min.time(),TZ)
    end=start+timedelta(days=14)
    with caldav.DAVClient(url='https://caldav.icloud.com/',username=config['email'],
                         password=config['password'],timeout=35) as client:
        matches=[c for c in client.principal().calendars() if c.name==config['calendar_name']]
        if len(matches)!=1:
            raise ValueError('Expected exactly one calendar with the configured name')
        # Request expanded recurring instances from CalDAV, including moved exceptions.
        resources=matches[0].date_search(start=start,end=end,expand=True)
        rows={}
        for resource in resources:
            doc=icalendar.Calendar.from_ical(resource.data)
            for event in doc.walk('VEVENT'):
                if str(event.get('STATUS','')).upper()=='CANCELLED' or not event.get('DTSTART'):
                    continue
                begins=event.decoded('DTSTART')
                all_day=not isinstance(begins,datetime)
                finishes=event.decoded('DTEND') if event.get('DTEND') else begins+(event.decoded('DURATION') if event.get('DURATION') else timedelta(days=1) if all_day else timedelta())
                if not all_day:
                    begins=begins.replace(tzinfo=TZ) if begins.tzinfo is None else begins.astimezone(TZ)
                    finishes=finishes.replace(tzinfo=TZ) if finishes.tzinfo is None else finishes.astimezone(TZ)
                # Expansion failure must not silently hide future recurring occurrences.
                if event.get('RRULE'):
                    raise ValueError('Server did not expand repeating events')
                identity=str(event.get('UID',''))+'|'+begins.isoformat()
                key=hashlib.sha256(identity.encode()).hexdigest()[:20]
                rows[key]={'id':key,'title':str(event.get('SUMMARY','Untitled event')),
                           'location':str(event.get('LOCATION','')),'start':begins.isoformat(),
                           'end':finishes.isoformat(),'allDay':all_day}
        return sorted(rows.values(),key=lambda e:(e['start'],e['title']))


def get_weather(config):
    r=requests.get('https://api.open-meteo.com/v1/forecast',params={
        'latitude':config['latitude'],'longitude':config['longitude'],
        'current':'temperature_2m,apparent_temperature,weather_code',
        'daily':'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
        'temperature_unit':'fahrenheit','timezone':'America/Denver','forecast_days':5},timeout=30)
    r.raise_for_status()
    data=r.json()
    if not data.get('current') or not data.get('daily'):
        raise ValueError('Weather response missing data')
    return data


class Wall:
    def __init__(self,folder,web,demo=False):
        self.folder=Path(folder)
        self.folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.web=Path(web).resolve()
        self.demo=demo
        self.lock=threading.RLock()
        self.config={**DEFAULTS}
        if (self.folder/'config.json').exists():
            self.config.update(json.loads((self.folder/'config.json').read_text()))
        if not self.config.get('access_key'):
            self.config['access_key']=secrets.token_urlsafe(32)
        self.cache={'events':[],'weather':None,'photos':[],
                    'status':{k:{'updated':0,'error':None} for k in ('calendar','weather','photos')}}
        if (self.folder/'cache.json').exists():
            try:self.cache.update(json.loads((self.folder/'cache.json').read_text()))
            except (ValueError,OSError):pass
        self.override_until=time.time()+3600 if demo else 0
        self.display={'on':True,'override_until':self.override_until,'error':None}
        if demo:
            now=datetime.now(TZ)
            days=week_days(now)
            self.cache['events']=[{'id':'demo1','title':'Family dinner','location':'','start':days[3]+'T18:00:00-06:00','end':days[3]+'T19:00:00-06:00','allDay':False},
                                  {'id':'demo2','title':'Library day','location':'','start':days[5]+'T16:00:00-06:00','end':days[5]+'T17:00:00-06:00','allDay':False},
                                  {'id':'demo3','title':'Weekend together','location':'','start':days[6],'end':(date.fromisoformat(days[6])+timedelta(days=1)).isoformat(),'allDay':True}]
            self.cache['status']['calendar']={'updated':time.time(),'error':None}
        self.last_display=None
        self.last_power_record=None
        self.last_power_heartbeat=0
        self.highlights=Highlights(self.folder/'highlights.json',atomic_json)
        self.highlights_view=self.highlights.snapshot(datetime.now(TZ))
        if not any(row['category']=='quotes' for row in self.highlights_view['items']):
            self.highlights_view['items'].extend(quotes(datetime.now(TZ).date().isoformat()))
            self.highlights_view['unavailable']=[kind for kind in self.highlights_view['unavailable'] if kind!='quotes']

    def snapshot(self):
        with self.lock:
            now=datetime.now(TZ)
            value=copy.deepcopy(self.cache)
            value.update(today=now.date().isoformat(),week=week_days(now),
                         settings={k:self.config[k] for k in ('windows','photo_seconds')},
                         display=self.display.copy(),demo=self.demo)
            value['photos']=['/photos/'+name for name in value['photos']]
            if self.demo:
                value['status']['calendar']={'updated':time.time(),'error':None}
                if not self.config.get('album_url') and value['photos']:
                    value['status']['photos']={'updated':time.time(),'error':None}
            value['highlights']=copy.deepcopy(self.highlights_view)
            if value['highlights']['day']!=now.date().isoformat():
                value['highlights']={'day':now.date().isoformat(),'items':quotes(now.date().isoformat()),'unavailable':['history','observances','sports']}
            value['version']='2.0-highlights'
            value['display_title']=self.config.get('display_title','FAMILY WALL')
            return value

    def highlights_worker(self):
        def publish(value):
            with self.lock:self.highlights_view=value
        while True:
            try:
                self.highlights.refresh(datetime.now(TZ),publish)
            except Exception as exc:
                logging.warning('Highlights update failed (%s)',type(exc).__name__)
            time.sleep(60)

    def refresh(self,kind):
        try:
            with self.lock:config=self.config.copy()
            if kind=='calendar':
                if self.demo:return
                value=calendar_events(config,datetime.now(TZ));key='events'
            elif kind=='weather':value=get_weather(config);key='weather'
            else:
                if self.demo and not config.get('album_url'):return
                value=sync_photos(config['album_url'],self.folder/'photos');key='photos'
            with self.lock:
                self.cache[key]=value
                self.cache['status'][kind]={'updated':time.time(),'error':None}
                atomic_json(self.folder/'cache.json',self.cache)
        except Exception as exc:
            # Do not log service URLs, credentials, or event contents.
            logging.warning('%s update failed (%s)',kind,type(exc).__name__)
            with self.lock:self.cache['status'][kind]['error']='Update unavailable; retrying'

    def worker(self,kind,interval):
        while True:
            self.refresh(kind)
            time.sleep(interval)

    def check_power(self):
        now=datetime.now(TZ)
        with self.lock:
            override=time.time()<self.override_until
            desired=override or in_schedule(now,self.config['windows'])
        error=None
        observed='unknown'
        action='none'
        failure='none'
        if not self.demo:
            try:
                env=os.environ.copy()
                env['XDG_RUNTIME_DIR']=f'/run/user/{os.getuid()}'
                env['WAYLAND_DISPLAY']='wayland-0'
                state=subprocess.run(['wlopm'],env=env,capture_output=True,text=True,timeout=8,check=True).stdout
                lines=[line.strip().lower() for line in state.splitlines() if line.strip()]
                if lines:
                    observed='on' if all(line.endswith(' on') for line in lines) else 'off' if all(line.endswith(' off') for line in lines) else 'mixed-or-unknown'
                correct=bool(lines) and all(line.endswith(' on' if desired else ' off') for line in lines)
                if not correct:
                    action='request-on' if desired else 'request-off'
                    subprocess.run(['wlopm','--on' if desired else '--off','*'],env=env,capture_output=True,timeout=8,check=True)
                    action+='-accepted'
                self.last_display=desired
            except Exception as exc:
                error='Monitor control unavailable; retrying'
                # Never record command output or arbitrary exception messages.
                failure=type(exc).__name__
        record=(desired,override,observed,action,failure)
        tick=time.monotonic()
        if record!=self.last_power_record or tick-self.last_power_heartbeat>=300:
            logging.getLogger('family_wall.display').info(
                '%s desired=%s source=%s observed-before=%s action=%s error=%s',
                now.isoformat(timespec='seconds'),'on' if desired else 'off',
                'override' if override else 'schedule',observed,action,failure)
            self.last_power_record=record
            self.last_power_heartbeat=tick
        with self.lock:self.display={'on':desired,'override_until':self.override_until,'error':error}

    def power(self):
        while True:
            self.check_power()
            time.sleep(15)

    def start(self):
        for kind,interval in [('calendar',300),('weather',900),('photos',900)]:
            threading.Thread(target=self.worker,args=(kind,interval),daemon=True).start()
        threading.Thread(target=self.power,daemon=True).start()
        threading.Thread(target=self.highlights_worker,daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version='FamilyWall'
    def log_message(self,*args):pass

    @property
    def wall(self):return self.server.wall

    def host_valid(self):
        host=self.headers.get('Host','').split(':')[0].lower()
        if host in ('localhost','familywall','familywall.local'):return True
        try:return ipaddress.ip_address(host).is_private
        except ValueError:return False

    def authorized(self):
        if not self.host_valid():return False
        if ipaddress.ip_address(self.client_address[0]).is_loopback:return True
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return False
        value=cookie.get('family_wall')
        return bool(value and hmac.compare_digest(value.value,self.wall.config['access_key']))

    def send(self,status,body,content_type='application/json'):
        if not isinstance(body,bytes):body=json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed=urlparse(self.path)
        provided=parse_qs(parsed.query).get('key',[''])[0]
        if provided and self.host_valid() and hmac.compare_digest(provided,self.wall.config['access_key']):
            self.send_response(303)
            self.send_header('Location','/')
            self.send_header('Set-Cookie',f'family_wall={provided}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length','0')
            self.end_headers();return
        if not self.authorized():
            self.send(401,b'Open the private dashboard link printed during setup.','text/plain');return
        if parsed.path=='/api/kiosk-heartbeat':
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                self.send(403,{'error':'Local kiosk only'});return
            (self.wall.folder/'kiosk-heartbeat').touch(mode=0o600)
            self.send(200,{'ok':True});return
        if parsed.path=='/api/state':self.send(200,self.wall.snapshot());return
        if parsed.path.startswith('/api/'):
            self.send(404,{'error':'Not found'});return
        if parsed.path.startswith('/photos/'):
            name=parsed.path[len('/photos/'):]
            with self.wall.lock:allowed=name in self.wall.cache['photos']
            if not allowed:self.send(404,{'error':'Photo not found'});return
            path=self.wall.folder/'photos'/name
        else:
            relative=parsed.path.lstrip('/') or 'index.html'
            path=(self.wall.web/relative).resolve()
            if not path.is_relative_to(self.wall.web):self.send(403,{'error':'Forbidden'});return
            if path.is_dir():path=path/'index.html'
        if not path.is_file():self.send(404,{'error':'Not found'});return
        self.send(200,path.read_bytes(),mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

    def do_POST(self):
        if not self.authorized():self.send(401,{'error':'Open your private dashboard link.'});return
        origin=self.headers.get('Origin')
        if self.headers.get('X-Family-Wall')!='1' or self.headers.get('Content-Type')!='application/json' or (origin and urlparse(origin).netloc!=self.headers.get('Host')):
            self.send(403,{'error':'Request not allowed'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=4096:raise ValueError('Invalid request size')
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict):raise ValueError('Invalid settings')
            with self.wall.lock:
                if self.path=='/api/settings':
                    values=validate_settings(body)
                    self.wall.config.update(values)
                    if not self.wall.demo:atomic_json(self.wall.folder/'config.json',self.wall.config)
                elif self.path=='/api/override':
                    minutes=body.get('minutes')
                    if type(minutes)!=int or minutes not in (0,60):raise ValueError('Invalid override')
                    self.wall.override_until=time.time()+minutes*60 if minutes else 0
                else:self.send(404,{'error':'Not found'});return
            self.send(200,{'ok':True})
        except (ValueError,TypeError):self.send(400,{'error':'Check the times and photo interval.'})


def setup(folder):
    import getpass
    folder=Path(folder)
    config={**DEFAULTS}
    if (folder/'config.json').exists():config.update(json.loads((folder/'config.json').read_text()))
    print('\nFamily Wall — private calendar setup')
    print('Credentials are stored only on this Pi, in a file readable by your Pi account.')
    calendar_name=input(f'Calendar name [{config["calendar_name"]}]: ').strip()
    if calendar_name:config['calendar_name']=calendar_name
    album_url=input('Public iCloud Shared Album URL (Enter keeps current): ').strip()
    if album_url:config['album_url']=album_url
    parsed=urlparse(config.get('album_url',''))
    if (parsed.scheme!='https' or parsed.hostname!='photos.icloud.com' or
            not parsed.path.startswith('/shared/album/') or
            not parsed.path.removeprefix('/shared/album/')):
        raise SystemExit('A valid photos.icloud.com/shared/album URL is required.')
    for key,label,low,high in (('latitude','Weather latitude',-90,90),
                               ('longitude','Weather longitude',-180,180)):
        current=config.get(key)
        prompt=f'{label}' + (f' [{current}]' if current is not None else '') + ': '
        raw=input(prompt).strip()
        if raw:
            try:value=float(raw)
            except ValueError:raise SystemExit(f'{label} must be a number.')
            if not low<=value<=high:raise SystemExit(f'{label} is outside its valid range.')
            config[key]=value
        if config.get(key) is None:raise SystemExit(f'{label} is required.')
    email=input('Apple Account email (Enter keeps current): ').strip()
    if email:config['email']=email
    password=getpass.getpass('App-specific password (hidden; Enter keeps current): ').strip()
    if password:config['password']=password
    if not config.get('email') or not config.get('password'):raise SystemExit('Email and app-specific password are required.')
    config.setdefault('access_key',secrets.token_urlsafe(32))
    print(f'Testing {config["calendar_name"]} calendar and event retrieval…')
    try:
        events=calendar_events(config,datetime.now(TZ))
    except Exception as e:
        print('Calendar test failed:',type(e).__name__)
        raise SystemExit('Settings were not saved. Check credentials and try again.')
    atomic_json(folder/'config.json',config)
    print(f'Connected. Found {len(events)} events in the two-week window.')
    print('Saved securely. Keep this private access link for your phone (same home Wi-Fi):')
    try:
        addresses=subprocess.check_output(['hostname','-I'],text=True).split()
        address=next(a for a in addresses if ipaddress.ip_address(a).version==4)
    except Exception:address='familywall.local'
    print(f'http://{address}:8080/?key={config["access_key"]}')
    print('Do not share this link: it grants access to your calendar and display settings.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default=str(Path.home()/'.config/family-wall'))
    parser.add_argument('--web',default=str(Path(__file__).parent/'web'))
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--setup',action='store_true')
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    if args.setup:setup(args.data);return
    display_logger=configure_display_log(args.data)
    display_logger.info('%s service-start timezone=%s demo=%s',
                        datetime.now(TZ).isoformat(timespec='seconds'),TZ,args.demo)
    wall=Wall(args.data,args.web,args.demo)
    wall.start()
    server=ThreadingHTTPServer(('127.0.0.1' if args.demo else '0.0.0.0',args.port),Handler)
    server.wall=wall
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    logging.info('Family Wall listening on port %s',args.port)
    server.serve_forever()

if __name__=='__main__':main()
