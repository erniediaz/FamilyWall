"""Restart the kiosk if its page heartbeat stops, even if Chromium stays alive."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

TIMEOUT = 180


def expired(now, last):
    return now - last > TIMEOUT


def main():
    heartbeat = Path.home() / '.config/family-wall/kiosk-heartbeat'
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        process = subprocess.Popen(sys.argv[1:], start_new_session=True)
        last = time.monotonic()
        stamp = heartbeat.stat().st_mtime_ns if heartbeat.exists() else None
        try:
            while process.poll() is None:
                time.sleep(10)
                current = heartbeat.stat().st_mtime_ns if heartbeat.exists() else None
                if current is not None and current != stamp:
                    stamp, last = current, time.monotonic()
                if expired(time.monotonic(), last):
                    # A server outage is not proof of a browser failure.
                    try:
                        with urlopen('http://127.0.0.1:8080/api/state', timeout=5) as response:
                            if response.status != 200:
                                continue
                    except OSError:
                        continue
                    print('Kiosk page heartbeat missing for 180 seconds; restarting browser.', flush=True)
                    break
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                # Also clean up any surviving child processes in this group.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            except ProcessLookupError:
                pass
        time.sleep(10)


if __name__ == '__main__':
    main()
