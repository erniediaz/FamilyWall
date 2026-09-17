import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pi'))
from server import TZ,DEFAULTS,in_schedule,week_days,validate_settings,calendar_events,Wall,atomic_json,Handler
from photos import apple_host

class Scheduling(unittest.TestCase):
    def test_boundaries(self):
        for hour,minute,wanted in [(5,59,False),(6,0,True),(8,29,True),(8,30,False),(16,29,False),(16,30,True),(18,59,True),(19,0,False)]:
            with self.subTest(hour=hour,minute=minute):
                self.assertEqual(in_schedule(datetime(2026,9,16,hour,minute,tzinfo=TZ),DEFAULTS['windows']),wanted)
    def test_dst_uses_local_hours(self):
        summer=datetime(2026,7,1,12,tzinfo=timezone.utc).astimezone(TZ)
        winter=datetime(2026,12,1,13,tzinfo=timezone.utc).astimezone(TZ)
        self.assertEqual(summer.hour,6);self.assertEqual(winter.hour,6)
        for x in (summer,winter):self.assertTrue(in_schedule(x,DEFAULTS['windows']))
    def test_overnight(self):
        for h,want in [(23,True),(1,True),(3,False)]:
            self.assertEqual(in_schedule(datetime(2026,9,16,h,tzinfo=TZ),[['22:00','02:00']]),want)
    def test_week_rollover(self):
        self.assertEqual(week_days(datetime(2026,9,19,tzinfo=TZ))[0],'2026-09-13')
        self.assertEqual(week_days(datetime(2026,9,20,tzinfo=TZ))[0],'2026-09-20')
    def test_reject_invalid_settings(self):
        for w in [[['25:00','08:00'],['16:00','19:00']],[['06:00','06:00'],['16:00','19:00']]]:
            with self.assertRaises(ValueError):validate_settings({'windows':w,'photo_seconds':60})
        for s in [0,True,60.5,3601]:
            with self.assertRaises(ValueError):validate_settings({'windows':DEFAULTS['windows'],'photo_seconds':s})

ICS='''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:all-day
DTSTART;VALUE=DATE:20260916
DTEND;VALUE=DATE:20260918
SUMMARY:Two days
END:VEVENT
BEGIN:VEVENT
UID:repeating
RECURRENCE-ID:20260916T000000Z
DTSTART:20260916T003000Z
DTEND:20260916T013000Z
SUMMARY:Moved instance
END:VEVENT
BEGIN:VEVENT
UID:cancelled
DTSTART:20260916T180000Z
STATUS:CANCELLED
SUMMARY:Do not show
END:VEVENT
END:VCALENDAR'''
class Calendar(unittest.TestCase):
    def test_all_day_exception_and_timezone(self):
        calendar=MagicMock();calendar.name='Family'
        resource=MagicMock();resource.data=ICS
        calendar.date_search.return_value=[resource]
        with patch('caldav.DAVClient') as constructor:
            constructor.return_value.__enter__.return_value.principal.return_value.calendars.return_value=[calendar]
            events=calendar_events({**DEFAULTS,'email':'test','password':'test'},datetime(2026,9,16,tzinfo=TZ))
        self.assertEqual(len(events),2)
        timed=next(e for e in events if not e['allDay'])
        self.assertEqual(timed['start'],'2026-09-15T18:30:00-06:00')
        day=next(e for e in events if e['allDay'])
        self.assertEqual(day['end'],'2026-09-18')
        self.assertTrue(calendar.date_search.call_args.kwargs['expand'])
    def test_duplicate_calendar_fails(self):
        c=MagicMock();c.name='Family'
        with patch('caldav.DAVClient') as constructor:
            constructor.return_value.__enter__.return_value.principal.return_value.calendars.return_value=[c,c]
            with self.assertRaises(ValueError):calendar_events({**DEFAULTS,'email':'test','password':'test'},datetime.now(TZ))

class PrivacyAndCache(unittest.TestCase):
    def test_secret_not_in_snapshot(self):
        with tempfile.TemporaryDirectory() as p:
            atomic_json(Path(p)/'config.json',{'email':'secret-email','password':'secret-password','access_key':'secret-key'})
            wall=Wall(p,p)
            state=json.dumps(wall.snapshot())
            self.assertNotIn('secret-',state)
            self.assertEqual((Path(p)/'config.json').stat().st_mode & 0o777,0o600)
    def test_network_failure_preserves_cache(self):
        with tempfile.TemporaryDirectory() as p:
            wall=Wall(p,p);wall.cache['weather']={'saved':'weather'}
            wall.cache['status']['weather']['updated']=100
            with patch('server.get_weather',side_effect=RuntimeError()):wall.refresh('weather')
            self.assertEqual(wall.cache['weather'],{'saved':'weather'})
            self.assertEqual(wall.cache['status']['weather']['updated'],100)
            self.assertTrue(wall.cache['status']['weather']['error'])
    def test_photo_host_boundary(self):
        self.assertTrue(apple_host('https://p1.icloud-content.com/photo',['icloud-content.com']))
        self.assertFalse(apple_host('https://evilicould.com/photo',['icloud-content.com']))
        self.assertFalse(apple_host('https://evilicloud-content.com/photo',['icloud-content.com']))
        self.assertFalse(apple_host('http://p1.icloud-content.com/photo',['icloud-content.com']))
        self.assertFalse(apple_host('https://user@p1.icloud-content.com/photo',['icloud-content.com']))

if __name__=='__main__':unittest.main()

class HttpAccess(unittest.TestCase):
    def handler(self,wall,host='192.168.1.50:8080',address='192.168.1.51',cookie=''):
        from types import SimpleNamespace
        handler=object.__new__(Handler)
        handler.server=SimpleNamespace(wall=wall)
        handler.client_address=(address,1234)
        handler.headers={'Host':host,'Cookie':cookie}
        return handler
    def test_lan_requires_private_key(self):
        with tempfile.TemporaryDirectory() as p:
            wall=Wall(p,p)
            self.assertFalse(self.handler(wall).authorized())
            self.assertTrue(self.handler(wall,cookie='family_wall='+wall.config['access_key']).authorized())
            self.assertFalse(self.handler(wall,cookie='family_wall=incorrect').authorized())
    def test_rebinding_host_is_rejected_even_on_loopback(self):
        with tempfile.TemporaryDirectory() as p:
            wall=Wall(p,p)
            self.assertFalse(self.handler(wall,host='malicious.example',address='127.0.0.1').authorized())
            self.assertTrue(self.handler(wall,host='127.0.0.1:8080',address='127.0.0.1').authorized())
    def test_reject_cross_origin_post(self):
        with tempfile.TemporaryDirectory() as p:
            wall=Wall(p,p)
            h=self.handler(wall,address='127.0.0.1')
            h.headers.update({'Origin':'https://malicious.example','Content-Type':'application/json','X-Family-Wall':'1'})
            h.send=MagicMock();h.do_POST()
            self.assertEqual(h.send.call_args.args[0],403)
