"""Run Chromium only during display hours and recover missing page heartbeats."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

TIMEOUT = 180
WAKE_DELAY = 5


def display_ready():
    """False = scheduled sleep; None = unavailable/not yet awake; True = awake."""
    try:
        with urlopen('http://127.0.0.1:8080/api/state', timeout=5) as response:
            display = json.load(response)['display']
        if display.get('on') is False:
            return False
        if display.get('on') is not True or display.get('error'):
            return None
        result = subprocess.run(['wlopm'], capture_output=True, text=True,
                                timeout=5, check=True)
        lines = [line.strip().lower() for line in result.stdout.splitlines() if line.strip()]
        return True if lines and all(line.endswith(' on') for line in lines) else None
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None


def terminate(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    except ProcessLookupError:
        pass


class Supervisor:
    def __init__(self, command, heartbeat):
        self.command, self.heartbeat = command, heartbeat
        self.process = None
        self.ready_since = None
        self.last = 0
        self.stamp = None

    def stop(self):
        if self.process is not None:
            terminate(self.process)
            self.process = None
        self.ready_since = None

    def tick(self, ready, now):
        if ready is False:
            if self.process is not None:
                print('Display sleeping; closing kiosk browser.', flush=True)
            self.stop()
            return
        if ready is None:
            # Preserve a running browser during an API/display-control outage.
            self.ready_since = None
            return
        if self.process is not None and self.process.poll() is not None:
            self.stop()
        stamp = self.heartbeat.stat().st_mtime_ns if self.heartbeat.exists() else None
        if self.process is None:
            if self.ready_since is None:
                self.ready_since = now
            if now - self.ready_since < WAKE_DELAY:
                return
            print('Display awake; starting fresh kiosk browser.', flush=True)
            self.process = subprocess.Popen(self.command, start_new_session=True)
            self.last, self.stamp = now, stamp
            return
        if stamp is not None and stamp != self.stamp:
            self.stamp, self.last = stamp, now
        if now - self.last > TIMEOUT:
            print('Kiosk page heartbeat missing for 180 seconds; restarting browser.', flush=True)
            self.stop()


def main():
    supervisor = Supervisor(sys.argv[1:], Path.home() / '.config/family-wall/kiosk-heartbeat')
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while True:
            supervisor.tick(display_ready(), time.monotonic())
            time.sleep(5)
    finally:
        supervisor.stop()


if __name__ == '__main__':
    main()
