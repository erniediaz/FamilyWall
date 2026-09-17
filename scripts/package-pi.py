from pathlib import Path
import hashlib,json,re,zipfile
from urllib.parse import urlsplit
root=Path(__file__).resolve().parents[1]
web=root/'dist/client'
assert (web/'index.html').is_file()
html=(web/'index.html').read_text()
refs=re.findall(r'(?:src|href)="([^"]+)"',html)
local=[urlsplit(x).path for x in refs if x.startswith('/') and not x.startswith('//')]
missing=[x for x in local if not (web/x.lstrip('/')).is_file()]
assert not missing,missing
out=root.parent/'deliverables'
out.mkdir(exist_ok=True)
archive=out/'Family-Wall-Space-Pi.zip'
files={}
for name in ['server.py','photos.py','kiosk.sh','install.sh','README.md','VALIDATION.md','THIRD-PARTY-NOTICES']:
    files['family-wall/'+name]=root/'pi'/name
for path in web.rglob('*'):
    if path.is_file():files['family-wall/web/'+str(path.relative_to(web))]=path
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name,path in sorted(files.items()):z.write(path,name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert 'family-wall/web/index.html' in z.namelist()
    assert not any('config.json' in n or '/photos/' in n or 'node_modules' in n for n in z.namelist())
    assert all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist())
(out/'Installation-Guide.md').write_text((root/'pi/README.md').read_text())
(out/'Validation.md').write_text((root/'pi/VALIDATION.md').read_text())
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
(out/'Space-SHA256.txt').write_text(f'{sha}  Family-Wall-Space-Pi.zip\n')
print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'files':len(files),'local_asset_references_verified':len(local),'sha256':sha},indent=2))
