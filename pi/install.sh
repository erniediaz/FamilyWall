#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" = 0 ]; then
    echo 'Run this as family, not with sudo. It will ask for sudo only to install packages.'
    exit 1
fi
cd -- "$(dirname -- "$0")"
if [ ! -f web/index.html ]; then echo 'Missing dashboard files. Extract the complete ZIP first.'; exit 1; fi
sudo apt-get update
sudo apt-get install -y python3-caldav python3-requests python3-pil python3-icalendar chromium wlopm wlr-randr curl
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
# Stop an older installation while credentials are updated to avoid concurrent writes.
systemctl --user stop family-wall.service family-wall-kiosk.service 2>/dev/null || true
python3 server.py --setup
release="$HOME/.local/share/family-wall/releases/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$release" "$HOME/.config/systemd/user"
cp server.py photos.py highlights.py team_sports.py quotes.json release.py kiosk.sh THIRD-PARTY-NOTICES "$release/"
cp -R web "$release/web"
chmod 700 "$release/kiosk.sh"
python3 - "$release" <<'PY'
import os,sys
from pathlib import Path
base=Path.home()/'.local/share/family-wall'
link=base/'current.new'
if link.is_symlink():link.unlink()
link.symlink_to(sys.argv[1],target_is_directory=True)
os.replace(link,base/'current')
PY
cat > "$HOME/.config/systemd/user/family-wall.service" <<'UNIT'
[Unit]
Description=Family Wall calendar, photos, weather and display schedule
After=network.target
[Service]
Type=simple
ExecStart=/usr/bin/python3 %h/.local/share/family-wall/current/server.py
Restart=always
RestartSec=10
UMask=0077
[Install]
WantedBy=default.target
UNIT
cat > "$HOME/.config/systemd/user/family-wall-kiosk.service" <<'UNIT'
[Unit]
Description=Family Wall full-screen browser
After=family-wall.service
Wants=family-wall.service
[Service]
Type=simple
ExecStart=/bin/bash %h/.local/share/family-wall/current/kiosk.sh
Restart=always
RestartSec=10
UMask=0077
[Install]
WantedBy=default.target
UNIT
# Give the first install an hour on screen to inspect it, even outside the schedule.
# Override is memory-only: subsequent reboots immediately use the daily schedule.
systemctl --user daemon-reload
systemctl --user enable --now family-wall.service
for attempt in $(seq 1 30); do
    if curl --silent --fail http://127.0.0.1:8080/api/state >/dev/null; then break; fi
    sleep 1
done
curl --silent --show-error --fail -H 'Content-Type: application/json' -H 'X-Family-Wall: 1' \
    -d '{"minutes":60}' http://127.0.0.1:8080/api/override >/dev/null
systemctl --user enable --now family-wall-kiosk.service
printf '\nFamily Wall installed. The monitor will stay on for one hour for setup.\n'
printf 'Then: daily 6:00–8:30 a.m. and 4:30–7:00 p.m., Mountain time.\n'
printf 'Photos and weather may take a minute to load.\n'
printf 'After checking the screen, reboot once to verify desktop auto-login and startup.\n'
