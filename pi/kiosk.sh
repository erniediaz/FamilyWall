#!/usr/bin/env bash
set -eu
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WAYLAND_DISPLAY=wayland-0
while [ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; do sleep 3; done
# Inhibit desktop idle blanking while the dashboard controls display hours.
# swayidle is the Raspberry Pi OS screen blanking process; no session is ended.
pkill -u "$(id -u)" -x swayidle || true
# Use a supported 1080p mode where available. Leave other outputs alone.
output=$(wlr-randr --json 2>/dev/null | python3 -c '
import json,sys
try:
    for output in json.load(sys.stdin):
        if output.get("enabled") and any(m.get("width")==1920 and m.get("height")==1080 for m in output.get("modes",[])):
            print(output["name"]);break
except Exception:pass
') || true
if [ -n "$output" ]; then
    wlr-randr --output "$output" --mode 1920x1080 || true
fi
until curl --silent --fail http://127.0.0.1:8080/api/state >/dev/null; do sleep 2; done
exec chromium --kiosk --no-first-run --noerrdialogs --disable-session-crashed-bubble \
  --user-data-dir="$HOME/.config/family-wall/chromium" \
  --ozone-platform=wayland --password-store=basic \
  http://127.0.0.1:8080/
