#!/usr/bin/env python3
"""Install the optional highlights release, or return to the saved release."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

FILES = ('server.py', 'photos.py', 'highlights.py', 'team_sports.py', 'quotes.json', 'kiosk.sh','window_rule.py','browser_watchdog.py', 'THIRD-PARTY-NOTICES', 'release.py')


def switch(base, target):
    temporary = base / 'current.new'
    if temporary.is_symlink(): temporary.unlink()
    temporary.symlink_to(target, target_is_directory=True)
    os.replace(temporary, base / 'current')


def services(action):
    subprocess.run(['systemctl', '--user', action, 'family-wall.service', 'family-wall-kiosk.service'], check=True)


def healthy(expected=None):
    for _ in range(30):
        try:
            with urlopen('http://127.0.0.1:8080/api/state', timeout=2) as response:
                state = json.load(response)
            if expected is None or state.get('version') == expected: return True
        except (OSError, ValueError):
            pass
        time.sleep(1)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'rollback'))
    parser.add_argument('--title', help='Optional dashboard title; stored only in your local configuration')
    args = parser.parse_args()
    if os.getuid() == 0: raise SystemExit('Run as your normal Pi user, without sudo.')
    base = Path.home() / '.local/share/family-wall'
    current = base / 'current'
    previous = base / 'before-highlights'
    if not current.is_symlink() or not current.resolve().is_dir():
        raise SystemExit('An existing Family Wall installation is required. For a fresh install, use install.sh.')
    os.environ.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
    os.environ.setdefault('DBUS_SESSION_BUS_ADDRESS', 'unix:path=' + os.environ['XDG_RUNTIME_DIR'] + '/bus')
    old = current.resolve()
    if args.action == 'rollback':
        if not previous.is_symlink() or not previous.resolve().is_dir(): raise SystemExit('No saved pre-highlights release was found.')
        target = previous.resolve()
    else:
        source = Path(__file__).resolve().parent
        if not (source / 'web/index.html').is_file(): raise SystemExit('Extract the complete ZIP first.')
        for name in FILES:
            if not (source / name).is_file(): raise SystemExit('Missing release file: ' + name)
        # Check imports and data before stopping the working display.
        subprocess.run([sys.executable, '-c', 'import server, highlights; highlights.quotes("2026-01-01")'], cwd=source, check=True)
        if not previous.is_symlink():
            if previous.exists(): raise SystemExit('Backup path already exists; no changes were made.')
            previous.symlink_to(old, target_is_directory=True)
        target = base / 'releases' / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-highlights')
        target.mkdir(parents=True, exist_ok=False)
        for name in FILES: shutil.copy2(source / name, target / name)
        shutil.copytree(source / 'web', target / 'web')
    services('stop')
    try:
        if args.action == 'install' and args.title:
            from server import atomic_json
            config_path = Path.home() / '.config/family-wall/config.json'
            config = json.loads(config_path.read_text())
            config['display_title'] = args.title.strip()[:80]
            atomic_json(config_path, config)
        switch(base, target)
        services('start')
        if not healthy('2.0-highlights' if args.action == 'install' else None):
            raise RuntimeError('The selected release did not pass its startup check.')
    except Exception:
        services('stop')
        switch(base, old)
        services('start')
        raise SystemExit('Update failed. The previous release has been restored.')
    print('Highlights installed.' if args.action == 'install' else 'The pre-highlights dashboard has been restored.')
    print('Calendar, photos, settings, and monitor schedule are retained.')
    if args.action == 'install':
        print('Rollback at any time: python3 ~/.local/share/family-wall/current/release.py rollback')


if __name__ == '__main__': main()
