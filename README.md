# Family Wall

## Optional version 2: Daily Highlights

This branch adds shuffled History, Fun Observances, Quotes, and Sports team cards to the header every 15 seconds. Daily non-sports categories are capped at 10 items each. The sports slot cycles only Florida Gators football, men’s basketball, and baseball, plus the Rockies, Broncos, Nuggets, and Avalanche while in season. Each card shows the record, ranking/standing, last final result, and next scheduled game.

**[Preview, installation, sources, and one-command rollback](pi/HIGHLIGHTS.md)**. This version uses a separate **Family-Wall-Highlights-Pi.zip**; the original dashboard remains on `main`. Existing installations should use `release.py install`, not replace only their web files.

A full-screen family dashboard for Raspberry Pi that combines a weekly iCloud calendar, an iCloud Shared Album, local weather, and automatic monitor scheduling.

The project is designed to run locally on a Raspberry Pi connected to an HDMI monitor. Chromium provides the display, while a small Python service retrieves and caches the household data.

> [!IMPORTANT]
> Before publishing a fork, replace or remove every household-specific default in the source and generated files. Review the publishing checklist below. Never commit Apple credentials, access keys, calendar data, cached photos, browser profiles, or `~/.config/family-wall/`.

## Features

- Monday-to-Sunday weekly calendar with timed, all-day, and recurring events
- Compact event cards show start–end times and title only; all-day labels stay unchanged and locations remain in Apple Calendar
- Private iCloud calendar access through CalDAV
- Rotating still photos from a dedicated iCloud Shared Album
- Photos shuffle when the dashboard opens; routine updates preserve the order
- Desktop layout fits the screen height, with scrolling inside busy calendar days
- Current conditions and a five-day Fahrenheit forecast from Open-Meteo
- Two configurable daily monitor-on windows
- One-hour wake override and resume-schedule control
- Private settings page for devices on the home network
- Local caching for temporary internet or service interruptions
- Full-screen Chromium kiosk launched automatically after desktop login
- Lightweight animated star-and-nebula background with reduced-motion support
- Installation and upgrades through versioned local releases

## Screenshots

Add account-neutral screenshots here after replacing calendar events, photos, household names, and location details with sample content.

```text
docs/images/dashboard.png
docs/images/settings.png
```

## How it works

```text
Apple Calendar ── CalDAV ────────┐
                                 │
iCloud Shared Album ─ public ────┼── Python service ── local API ── Chromium kiosk
                                 │         │
Open-Meteo ─────── HTTPS ────────┘         ├── local cache
                                           └── wlopm monitor control
```

The backend runs on the Pi and serves both the browser application and its local API. Apple calendar credentials stay in an owner-readable configuration file on the Pi; they are not sent to the browser. Photos, events, and weather are cached locally so the last successful data remains available during a temporary outage.

## Hardware and software

The original build targeted:

- Raspberry Pi 3 Model B
- Raspberry Pi OS with desktop, 64-bit ARM
- Debian 13 “Trixie”
- labwc/Wayland desktop session
- Chromium
- HDMI monitor running the dashboard at 1920 × 1080

Other Raspberry Pi models and monitors may work, but monitor sleep/wake, kiosk startup, and performance should be tested on the physical device.

The development computer needs:

- Node.js 22.13 or newer
- pnpm
- Python 3

The Pi installer uses Debian packages for the runtime dependencies. Node.js is not required on the Pi because the browser application is built before packaging.

## Repository layout

```text
app/                    React dashboard
public/                 Local visual assets
pi/
  install.sh            Raspberry Pi installer
  kiosk.sh              Chromium and display-session launcher
  server.py             Local API, calendar, weather, cache, and schedule
  photos.py             iCloud Shared Album synchronization
  THIRD-PARTY-NOTICES   Dependency and adaptation notices
  VALIDATION.md         Recorded checks and remaining device checks
scripts/
  package-pi.py         Creates the Pi installation archive
tests/
  test_server.py        Backend validation tests
design/                 Design notes and asset provenance
```

## Data sources

### Calendar

The application reads one iCloud calendar through Apple's CalDAV service. Setup requires the exact calendar name, the Apple Account email that can access it, and an Apple app-specific password.

Create the app-specific password in Apple Account settings under **Sign-In and Security → App-Specific Passwords**. Enter it only at the hidden setup prompt on the Pi.

### Photos

Photos come from a dedicated iCloud Shared Album with **Public Website** enabled. Anyone possessing that public link can view the album, so use a dedicated collection and treat its URL as private household information.

The current connector supports URLs in this form:

```text
https://photos.icloud.com/shared/album/ALBUM_TOKEN
```

It uses an unofficial public Apple interface that may change. Still images are downloaded, oriented, resized to a maximum dimension of 1920 pixels, and cached as JPEG files. Videos are skipped.

### Weather

Open-Meteo supplies model-based current conditions and a five-day forecast. Latitude and longitude determine the forecast. The current implementation requests Fahrenheit units.

## Before building a public version

The working household edition may contain names, a location, time zone, coordinates, calendar defaults, and a Shared Album URL in source or compiled JavaScript. Clean a separate copy before pushing it to GitHub.

At minimum, review:

- `app/page.tsx`: household title, location labels, and time zone
- `app/layout.tsx`: page title and metadata
- `pi/server.py`: calendar name, album URL, coordinates, and time zone
- `pi/install.sh`: user-facing default schedule and time-zone text
- `pi/README.md`, `pi/VALIDATION.md`, and files under `design/`
- `dist/` and every packaged ZIP, because compiled files can preserve old values

Use neutral defaults or require configuration during setup. Search the complete repository and an extracted copy of the final ZIP for:

- Household names and email addresses
- Local IP addresses and hostnames
- Shared Album tokens
- Access keys
- Real calendar event names and locations
- Downloaded family photos
- Absolute paths containing a personal computer username

Do not commit these runtime paths from the Pi:

```text
~/.config/family-wall/config.json
~/.config/family-wall/config.before-edit.json
~/.config/family-wall/cache.json
~/.config/family-wall/photos/
~/.config/family-wall/chromium/
```

## Build

Install the locked dependencies, run the type check, and create the production browser files:

```sh
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm build
```

Run the backend tests and shell syntax checks:

```sh
python3 -m unittest discover -s tests
node --experimental-strip-types --test tests/photo-order.test.mjs
bash -n pi/install.sh pi/kiosk.sh
```

The Python tests require `caldav`, `requests`, `Pillow`, and `icalendar`. A virtual environment is recommended on the development computer.

Create the Pi installer archive:

```sh
python3 scripts/package-pi.py
```

The packaging script collects the prebuilt browser files and Pi runtime into a ZIP under the sibling `deliverables/` directory. Inspect the archive's actual contents before distributing it.

## Install on Raspberry Pi

Prepare Raspberry Pi OS with desktop, enable SSH, and ensure the graphical desktop logs in automatically as the user who will run the dashboard. Confirm that monitor sleep and wake work through `wlopm` before relying on the schedule.

Copy the packaged ZIP from the development computer, replacing the placeholders:

```sh
scp ~/Downloads/family-wall.zip PI_USER@PI_ADDRESS:~/
```

Connect to the Pi and install as the normal desktop user:

```sh
ssh PI_USER@PI_ADDRESS
python3 -m zipfile -e ~/family-wall.zip ~/family-wall-install
bash ~/family-wall-install/family-wall/install.sh
```

Do not run the installer with `sudo bash`. It requests sudo only when installing operating-system packages.

During setup, enter the exact calendar name, Shared Album URL, weather coordinates, Apple Account email, and dedicated app-specific password. The installer validates calendar access, creates user services, starts the local backend, and launches Chromium in kiosk mode.

For complete headless setup, configuration, monitor testing, upgrades, and recovery instructions, see [`docs/setup-guide.md`](docs/setup-guide.md).

## Configuration

Runtime configuration is stored at:

```text
~/.config/family-wall/config.json
```

Supported values include:

| Setting | Purpose |
| --- | --- |
| `calendar_name` | Exact iCloud calendar name |
| `album_url` | Public iCloud Shared Album URL |
| `latitude` / `longitude` | Weather coordinates |
| `windows` | Two daily monitor-on intervals in 24-hour time |
| `photo_seconds` | Time per photo, from 15 to 3600 seconds |
| `email` / `password` | Apple calendar credentials stored on the Pi |
| `access_key` | Generated key for the private local settings page |

The current UI allows changes to the two daily windows and photo interval. Household title, visible location labels, Fahrenheit units, and application time zone are source-level settings in this version and require rebuilding.

Example schedule value:

```json
{
  "windows": [
    ["06:00", "08:30"],
    ["16:30", "19:00"]
  ],
  "photo_seconds": 60
}
```

Do not commit a real configuration file, even if the password has been removed. The album URL and access key are also private.

## Services and useful commands

The installer creates two systemd user services:

- `family-wall.service` runs the local backend and scheduled monitor control.
- `family-wall-kiosk.service` launches the full-screen browser.

Check their state:

```sh
systemctl --user status family-wall.service family-wall-kiosk.service
```

Review recent backend messages:

```sh
journalctl --user -u family-wall.service -n 50 --no-pager
```

Monitor diagnostics survive service restarts and reboots in
`~/.config/family-wall/display.log`. Read recent records with:

```sh
tail -n 60 ~/.config/family-wall/display.log
```

Records include a local timestamp with UTC offset, the requested on/off state,
schedule versus override, the state reported by the desktop before any command,
and the command outcome or error type. State changes are logged immediately;
unchanged state is recorded every five minutes. A command being accepted does
not prove the physical monitor woke; the next record reports what the desktop sees.
Files rotate at 256 KiB with three backups (`display.log.1` through `.3`).
They are owner-readable and contain no calendar contents, album links, credentials,
or raw command output. These logs diagnose future failures; they cannot recover
records from earlier boots before this update was installed.

Re-enter or replace Apple credentials:

```sh
systemctl --user stop family-wall.service
python3 ~/.local/share/family-wall/current/server.py --setup
systemctl --user start family-wall.service
```

Stop the application while leaving its data installed:

```sh
systemctl --user disable --now family-wall-kiosk.service family-wall.service
XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 wlopm --on '*'
```

## Refresh behavior

The reference implementation uses these intervals:

| Content | Interval |
| --- | ---: |
| Calendar | 5 minutes |
| Shared Album | 15 minutes |
| Weather | 15 minutes |
| Browser state | 15 seconds |
| Monitor schedule | About 15 seconds |
| Photo rotation | 60 seconds by default |

On the first photo sync, the current implementation downloads and processes the complete album before publishing the photo list to the dashboard. Large albums can therefore leave the photo panel empty for several minutes on a Pi 3. If any individual download fails, the completed files remain cached and the sync retries later, but the new list is not published until a full pass succeeds.

## Security and privacy

- Keep the dashboard and settings interface on a trusted home network.
- Do not forward port 8080 or expose the service directly to the internet.
- Keep the generated phone access link private; it grants access to calendar display data and settings.
- Use a dedicated Apple app-specific password and revoke it when retiring the installation.
- The backend reads calendar information, but Apple's app-specific credential is not technically scoped by this application to a single calendar or read-only access.
- Owner-only file permissions reduce ordinary local exposure but do not protect against someone who controls the Pi account or physical device.
- A Shared Album Public Website is viewable by anyone with its link.
- Remove cached content and browser data before transferring or disposing of the Pi.

## Known limitations

- The photo connector depends on an unofficial Apple public interface.
- All days use the same two display windows; weekday and weekend schedules are not separate.
- The application time zone and visible location labels are hardcoded in multiple source locations.
- Only still images are displayed; videos are ignored.
- A large initial album can take several minutes to appear because the first list is published after a complete sync.
- The one-hour wake override is held in memory and clears after a service restart.
- There is no automatic application-update mechanism.
- Monitor power behavior varies by model and must be tested on the physical display.

## Validation checklist

Before declaring an installation complete, verify:

- A real timed event appears correctly.
- An all-day event spans the correct date.
- A recurring event and a changed appointment refresh correctly.
- At least two photos display and rotate.
- Weather location, units, and forecast dates are correct.
- Both schedule windows sleep and wake the monitor.
- The phone settings link works only as intended on the home network.
- Cached content remains visible during a short network interruption.
- The dashboard returns after a reboot during an on window.
- Desktop auto-login works without a keyboard or mouse.

Development tests do not replace these device checks.

## Troubleshooting

If photos remain blank, compare the number of cached files with the list exposed by the local API:

```sh
find ~/.config/family-wall/photos -type f -name '*.jpg' 2>/dev/null | wc -l
python3 -c 'import json,urllib.request; d=json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/state")); print("Photos offered:",len(d["photos"])); print("Status:",d["status"]["photos"])'
```

- A growing cache count usually means the first sync is still running.
- Cached files with zero offered photos usually indicate that one or more downloads prevented a complete sync.
- Zero cached files usually points to the album link, album visibility, network access, or Apple's endpoint.
- Offered photos greater than zero points to the browser or image-serving path.

Use the service commands above for additional diagnostics. Remove private event details and access links before posting logs publicly.

## Contributing

Issues and pull requests are welcome when they do not contain household data or credentials. Useful areas for contribution include:

- Progressive photo availability during the first sync
- Per-photo retry and clearer photo error reporting
- Configurable title, location label, units, and time zone
- Separate weekday and weekend schedules
- Automated migration between application releases
- Additional device and monitor compatibility testing

Please run the type check, production build, backend tests, and shell syntax checks before opening a pull request. Describe any checks that still require physical Raspberry Pi hardware.

## Third-party services and attribution

- Weather data: [Open-Meteo](https://open-meteo.com/), CC BY 4.0
- Calendar service: Apple iCloud CalDAV
- Shared Album interface: public iCloud/CloudKit behavior; mapping adapted from [BZPJoe/icloud-shared-album-sync-repo](https://github.com/BZPJoe/icloud-shared-album-sync-repo), MIT License
- Monitor control: [`wlopm`](https://git.sr.ht/~leon_plickat/wlopm) under a Wayland desktop session

Retain `pi/THIRD-PARTY-NOTICES` in source and installation packages.

Apple, iCloud, and Raspberry Pi are trademarks of their respective owners. This is an independent project and is not affiliated with or endorsed by Apple or Raspberry Pi.

## License

No project license has been selected yet. Add a `LICENSE` file before inviting reuse or outside contributions. Without an explicit license, copyright law generally reserves reuse rights to the copyright holder.
