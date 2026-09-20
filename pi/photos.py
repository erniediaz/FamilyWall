"""Public iCloud photo retrieval. No Apple account credentials are used here.
CloudKit field mapping adapted from BZPJoe/icloud-shared-album-sync-repo
(MIT, commit bcbd02272ed3e001ddb3368adbf01c005272de5b). See THIRD-PARTY-NOTICES.
Apple's public website endpoints are unofficial and may change.
"""
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image, ImageOps

BASE = '/database/1/com.apple.photos.cloud/production/'

def apple_host(url, roots):
    p = urlparse(url)
    return (p.scheme == 'https' and not p.username and not p.password and p.port in (None,443)
            and any(p.hostname == root or (p.hostname or '').endswith('.'+root) for root in roots))

def field(record, name, default=None):
    return record.get('fields', {}).get(name, {}).get('value', default)

def post(session, url, payload, params):
    r = session.post(url, data=json.dumps(payload), params=params,
                     headers={'Content-Type':'text/plain'}, timeout=35)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or data.get('serverErrorCode'):
        raise ValueError('Album service rejected the request')
    return data

def list_photos(shared_url):
    parsed=urlparse(shared_url)
    match=re.fullmatch(r'/shared/album/([A-Za-z0-9_-]+)/?', parsed.path)
    if parsed.scheme!='https' or parsed.hostname!='photos.icloud.com' or not match:
        raise ValueError('Use a photos.icloud.com/shared/album link')
    album=match[1]
    with requests.Session() as s:
        s.headers['User-Agent']='FamilyWall/1.0'
        params={'remapEnums':'true','getCurrentSyncToken':'true','sharing_url_key':album}
        resolved=post(s,'https://ckdatabasews.icloud.com'+BASE+'public/records/resolve',
                      {'shortGUIDs':[{'value':album}]},params)
        result=resolved['results'][0]
        access=result['anonymousPublicAccess']
        partition=access['databasePartition']
        host=urlparse(partition).hostname or ''
        if not (apple_host(partition, ['ckdatabasews.icloud.com']) or
                (re.fullmatch(r'p[0-9]+-ckdatabasews\.icloud\.com',host) and
                 apple_host(partition,['icloud.com']))):
            raise ValueError('Unexpected album service host')
        params['publicAccessAuthToken']=access['token']
        payload={'query':{'recordType':'CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted',
                         'filterBy':[{'fieldName':'direction','comparator':'EQUALS',
                                      'fieldValue':{'value':'DESCENDING','type':'STRING'}}]},
                 'zoneID':result['zoneID'],'resultsLimit':100}
        items=[]
        seen=set()
        for _ in range(200):
            page=post(s,partition.rstrip('/')+BASE+'shared/records/query',payload,params)
            if not isinstance(page.get('records'),list):
                raise ValueError('Album media list unavailable')
            for record in page['records']:
                if record.get('recordType')!='CPLMaster' or record.get('deleted'):
                    continue
                kind=str(field(record,'itemType','')).lower()
                if any(x in kind for x in ('video','movie','mpeg','quicktime')):
                    continue
                for prefix in ('resJPEGMed','resOriginal','resJPEGThumb'):
                    asset=field(record,prefix+'Res',{})
                    if not isinstance(asset,dict) or not asset.get('downloadURL'):
                        continue
                    url=asset['downloadURL'].replace('${f}','photo.jpg')
                    if not apple_host(url,['icloud-content.com','icloud.com','apple.com']):
                        raise ValueError('Unexpected photo host')
                    identity=record['recordName']+str(asset.get('fileChecksum') or asset.get('size') or '')
                    items.append({'id':hashlib.sha256(identity.encode()).hexdigest()[:32], 'url':url})
                    break
            marker=page.get('continuationMarker')
            if not marker:
                return list({x['id']:x for x in items}.values())
            if marker in seen:
                raise ValueError('Album pagination repeated')
            seen.add(marker)
            payload['continuationMarker']=marker
        raise ValueError('Album exceeds pagination limit')

def resize_photo(source, path):
    """Shrink before orientation/color copies; JPEG draft avoids full-size decode."""
    with Image.open(source) as original:
        if original.width * original.height > 40_000_000:
            raise ValueError('Photo dimensions exceed the Pi decode limit')
        original.draft('RGB', (1280, 1280))
        original.thumbnail((1280, 1280))
        with ImageOps.exif_transpose(original) as oriented:
            with oriented.convert('RGB') as image:
                temp = path.with_suffix('.tmp')
                image.save(temp, format='JPEG', quality=85)
                temp.replace(path)


def sync_photos(shared_url, destination, limit=500):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    items=list_photos(shared_url)[:limit]
    filenames=[]
    failures=0
    for item in items:
        name=item['id']+'.jpg'
        path=destination/name
        if not path.exists():
            try:
                with requests.get(item['url'],timeout=40,stream=True,allow_redirects=False) as r:
                    r.raise_for_status()
                    if r.is_redirect:
                        raise ValueError('Unexpected photo redirect')
                    content=bytearray()
                    for part in r.iter_content(65536):
                        content.extend(part)
                        if len(content)>30*1024*1024:
                            raise ValueError('Photo too large')
                resize_photo(io.BytesIO(content), path)
            except Exception:
                failures+=1
                continue
        try:
            with Image.open(path) as cached:
                oversized = max(cached.size) > 1280
            if oversized:
                resize_photo(path, path)
        except Exception:
            failures += 1
            continue
        filenames.append(name)
    if failures:
        # Retain the previous complete cache if a sync is incomplete.
        raise ValueError(f'{failures} photos could not be downloaded')
    # Only remove stale files after a complete, successful listing/download.
    keep=set(filenames)
    for old in destination.glob('*.jpg'):
        if old.name not in keep:
            old.unlink()
    return filenames

if __name__=='__main__':
    import sys
    files=sync_photos(sys.argv[1],sys.argv[2])
    print(f'Photo sync succeeded: {len(files)} images cached.')
