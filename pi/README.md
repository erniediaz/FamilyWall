# Build a Family Wall with Raspberry Pi and iCloud

A repeatable setup guide for a weekly calendar, rotating family photos, local weather, and a scheduled display.

Prepared September 16, 2026. Account names, network addresses, album links, credentials, and family photos have been removed. Commands use placeholders where you must supply your own information.

## 1. What you are building

A Raspberry Pi drives a monitor over HDMI. Chromium displays a local dashboard in full-screen kiosk mode. A Python service retrieves calendar events, photos, and weather, and controls when the monitor sleeps.

The design includes:

- A Monday–Sunday weekly calendar with timed and all-day events.
- One shared iCloud calendar, read using CalDAV, Apple's calendar access protocol.
- A dedicated iCloud Shared Album, with a photo changing every 60 seconds by default.
- Current weather and a five-day forecast in Fahrenheit from Open-Meteo.
- A black starfield with pink, blue, purple, and subtle green nebulas. The background image slowly drifts; it is not a live space simulation.
- Two daily screen-on windows, with the same hours every day.
- A private local link for changing the schedule and photo interval from a phone.
- Cached content for temporary internet outages.

The Pi stays powered on. Only the monitor goes to sleep. This lets the Pi continue refreshing data and wake the display later.

## 2. Before you begin: save the software

This is a custom application, not a feature included with Raspberry Pi OS. To reinstall it, retain a copy of the application installer ZIP. To change its title, location labels, time zone, or design, also retain the complete source project and its dependency lockfile.

This documentation bundle does not include the application. The original installer was personalized for a household. Keep that installer private: it can contain a household name, location, and a public album URL even though it excludes passwords and downloaded photos. Follow Section 12 before preparing a version for another household or publishing source code.

For the installation commands below, name your private installer copy `family-wall.zip`. Its internal top-level folder should be `family-wall`, containing `install.sh`, `server.py`, `photos.py`, `kiosk.sh`, and `web/`.

Keep these items together in a private backup:

- The installer ZIP for the version you use.
- The source project, including `app/`, `public/`, `pi/`, `scripts/`, `package.json`, and the dependency lockfile.
- This guide and a short note of your chosen time zone and display settings.
- An encrypted backup of your Pi configuration if you want to preserve credentials and settings. Do not put that configuration in a public repository or documentation bundle.

## 3. Hardware and account checklist

The reference hardware was a Raspberry Pi 3 Model B connected by HDMI to an LG 27UN850. Other monitors need their own sleep/wake test.

You need:

- A Raspberry Pi, its appropriate power supply, a microSD card, and an HDMI cable compatible with the Pi.
- A monitor with HDMI input.
- A Mac or another computer on the same home network.
- A microSD reader if preparing or repairing the operating system.
- Raspberry Pi OS with the desktop. The tested software environment used Debian 13 “Trixie,” 64-bit ARM, Chromium, and the labwc Wayland desktop.
- An Apple Account with access to the shared calendar and permission to prepare the photo album.
- Internet access for Apple services, weather, and initial package installation.

For a fresh desktop installation, Raspberry Pi recommends a card of at least 32 GB. Follow its current board-specific power and installation guidance: [Raspberry Pi getting started](https://www.raspberrypi.com/documentation/computers/getting-started.html).

A 1080p dashboard is a sensible starting point for a Pi 3, even when the monitor supports 4K. The kiosk script requests 1920 × 1080 when the monitor advertises that mode. Actual smoothness must be checked on the Pi.

## 4. Prepare headless access

“Headless” means configuring the Pi without a keyboard or mouse attached to it. The monitor can still be connected.

### Fresh operating system

1. Use Raspberry Pi Imager on your computer and choose Raspberry Pi OS with desktop for your board.
2. Set a hostname, a username, and a strong Pi login password in the customization options.
3. Configure your Wi-Fi, or connect the Pi to the router with Ethernet.
4. Enable SSH, the remote terminal service, in the Imager settings.
5. Write the card, insert it in the Pi, connect HDMI and power, and allow the first boot to finish.

Writing an operating system image erases the selected card. Do this only for a fresh installation or an intentional rebuild with your files backed up.

### Existing operating system

Do not re-image a working Pi just to install the dashboard. First try connecting to its existing SSH service. If SSH was never enabled, Raspberry Pi OS supports enabling it with an empty file named `ssh` in the boot partition. That method does not create a username or configure Wi-Fi; those must already exist. Consult the official instructions for your setup before changing the card: [Raspberry Pi remote access](https://www.raspberrypi.com/documentation/computers/remote-access.html).

### Find and connect to the Pi

Open your router's connected-device list and find the Pi's current address. A hostname ending in `.local` may also work, but the router's address is useful when name discovery fails.

On the Mac, replace both uppercase placeholders, then run:

```sh
ssh PI_USER@PI_ADDRESS
```

On the first connection, verify the device you are connecting to and accept its host key. Enter the Pi login password when prompted; passwords do not appear as you type.

After login, the terminal is running commands on the Pi. A prompt containing your Pi username and hostname helps distinguish it from a local Mac terminal.

A successful ping only shows that a device answers on the network. It does not prove that SSH is enabled or that the device is your Pi. SSH “connection refused” usually points to a disabled service; a timeout suggests the address, network, or firewall needs checking. A router DHCP reservation helps keep the Pi's address stable.

## 5. Verify the desktop and monitor control

Run these commands in the Pi SSH terminal:

```sh
cat /etc/os-release
uname -m
command -v chromium
systemctl get-default
pgrep -a labwc
command -v wlopm
```

For the reference setup, the useful results were a 64-bit ARM system (`aarch64`), Chromium installed, `graphical.target`, and a running labwc process. The installer adds `wlopm` if it is missing.

Check the desktop socket:

```sh
ls /run/user/$(id -u)/wayland-*
```

The script currently expects `wayland-0`. A file ending in `.lock` is not the socket. If your desktop uses another socket name, adjust the scripts described in Section 12 before installation.

With the desktop visible on the HDMI monitor, test sleep and automatic wake. If necessary, first install the small control tool:

```sh
sudo apt-get update
sudo apt-get install -y wlopm
```

Then run:

```sh
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export WAYLAND_DISPLAY=wayland-0
wlopm --off '*'
sleep 15
wlopm --on '*'
```

Keep the SSH connection open until the wake command finishes. If the screen stays dark, run the last command again and check the monitor's selected HDMI input.

The compositor remains active while the output sleeps. labwc recommends `wlopm` for this purpose: [labwc integration guidance](https://labwc.github.io/integration.html).

Do not continue to unattended scheduling until sleep and wake both work on your monitor.

## 6. Prepare Apple calendar and photos

### Shared calendar

1. Create or select one shared calendar in Apple Calendar.
2. Ensure the Apple Account used by the dashboard can see it and has accepted any sharing invitation.
3. Give the calendar a unique name among that account's calendars. The application matches its name exactly and rejects ambiguous matches.
4. Add a temporary timed event, an all-day event, and a repeating event for later verification.

The calendar remains private. This project does not require publishing a public calendar feed.

### App-specific password

The Python service signs in to Apple's CalDAV service using your Apple Account email and an app-specific password. Generate a dedicated password in Apple Account settings under Sign-In and Security → App-Specific Passwords. Two-factor authentication is required. Enter the generated password only into the setup prompt on the Pi; do not paste it into chat or place it in a shell command.

Apple allows individual revocation; changing your main Apple Account password also revokes existing app-specific passwords. See [Apple's app-specific password instructions](https://support.apple.com/en-us/102654).

The application only reads calendars, but the app-specific password itself is not restricted by this application to one calendar or to read-only access. Protect it accordingly.

### Dedicated photo album

1. Create a dedicated iCloud Shared Album and add the still images you want displayed.
2. Enable its Public Website option and copy the public link.
3. Open that link without signing in to confirm it displays the intended album.
4. Keep the link private and use only photos that everyone contributing is comfortable sharing through that link.

Anyone with a Public Website link can view that album. It is separate from the private calendar sign-in: [Apple Shared Album guidance](https://support.apple.com/guide/icloud/create-and-manage-shared-albums-mme985ae44d8/icloud).

The included photo connector supports links shaped like `https://photos.icloud.com/shared/album/ALBUM_TOKEN`. Older shared-album URL formats may require a different connector. It uses an unofficial public Apple interface, which could change; it is not an Apple-supported integration contract.

## 7. Configure the household without embedding credentials

For a reinstall using your own unchanged private installer, existing configuration can be retained. For another household, prepare a neutral build using Section 12 first. A configuration override changes the data sources, but does not remove personal text or an embedded album URL from an old installer.

The service stores settings in `~/.config/family-wall/config.json` on the Pi. The public installer asks for the calendar name, album link, and weather coordinates during setup. The following helper is optional: it lets you prepare or change those values before running the installer, without handling the Apple password.

On an existing installation, stop the service before editing configuration so a settings update cannot overwrite your changes:

```sh
systemctl --user stop family-wall.service
```

A “unit not found” message is expected on a fresh installation; proceed to the next step.

Run this block on the Pi to create a temporary helper:

```sh
cat > /tmp/configure-family-wall.py <<'PYCONFIG'
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse

os.umask(0o077)
folder = Path.home() / '.config' / 'family-wall'
folder.mkdir(parents=True, exist_ok=True, mode=0o700)
path = folder / 'config.json'
config = json.loads(path.read_text()) if path.exists() else {}
name = input('Exact shared calendar name: ').strip()
album = input('Public shared album URL: ').strip()
url = urlparse(album)
if not name:
    raise SystemExit('A calendar name is required.')
if (url.scheme != 'https' or url.netloc != 'photos.icloud.com'
        or not url.path.startswith('/shared/album/')
        or not url.path.removeprefix('/shared/album/')):
    raise SystemExit('Use a supported photos.icloud.com shared album link.')
latitude = float(input('Weather latitude, decimal degrees: '))
longitude = float(input('Weather longitude, decimal degrees: '))
if not (math.isfinite(latitude) and -90 <= latitude <= 90
        and math.isfinite(longitude) and -180 <= longitude <= 180):
    raise SystemExit('Coordinates are outside valid ranges.')
config.update(calendar_name=name, album_url=album,
              latitude=latitude, longitude=longitude)
config.setdefault('windows', [['06:00', '08:30'], ['16:30', '19:00']])
config.setdefault('photo_seconds', 60)
if path.exists():
    backup = folder / 'config.before-edit.json'
    backup.write_bytes(path.read_bytes())
    backup.chmod(0o600)
temporary = folder / 'config.manual.tmp'
temporary.write_text(json.dumps(config, indent=2) + '\n')
temporary.chmod(0o600)
temporary.replace(path)
print('Saved settings. Continue with the installer.')
PYCONFIG
python3 /tmp/configure-family-wall.py
```

Enter your own decimal coordinates; west longitudes are negative. The original application uses Fahrenheit. Coordinates update weather retrieval, but the displayed city label and time zone require the source changes in Section 12.

The sample on windows are 6:00–8:30 a.m. and 4:30–7:00 p.m. every day. The reference application uses `America/Denver`, including daylight saving time. Do not assume changing the Pi's system time zone alone changes the application's time zone.

## 8. Transfer and install the application

### On the Mac

Open a new local terminal window. Replace the two uppercase placeholders:

```sh
scp ~/Downloads/family-wall.zip PI_USER@PI_ADDRESS:~/
```

This copies your private installer to the Pi. If it is saved elsewhere, substitute its local path.

### On the Pi

Extract it to a new directory. For a later upgrade, use a different extraction directory so stale files cannot be left over from an older ZIP.

```sh
python3 -m zipfile -e ~/family-wall.zip ~/family-wall-install
bash ~/family-wall-install/family-wall/install.sh
```

Run the installer as your normal Pi user, not as root and not with `sudo bash`. It requests sudo only for operating system packages.

When prompted:

1. Enter the Pi login password if sudo requests it.
2. Enter the exact shared-calendar name.
3. Enter the Public Website URL for the dedicated Shared Album.
4. Enter the weather latitude and longitude in decimal degrees.
5. Enter the Apple Account email in the application setup prompt.
6. Enter the Apple app-specific password in its hidden password prompt.
7. Wait for calendar validation and installation to complete.
8. Save the private phone access link printed by the installer.

On an upgrade, pressing Enter at the credential prompts retains existing credentials. A fresh install requires both values.

### What the installer does

It installs Chromium, the necessary Debian Python libraries, and Wayland display tools. It validates calendar access, saves owner-only configuration, creates a timestamped application release, and sets up two user services:

- `family-wall.service` serves the dashboard and refreshes calendar, photo, and weather data.
- `family-wall-kiosk.service` starts Chromium full-screen against the local dashboard.

Releases live under `~/.local/share/family-wall/releases/`; `~/.local/share/family-wall/current` points to the active release. The Pi runs prebuilt browser files, so Node.js and a frontend build are not needed on the Pi.

The installer wakes the display for one hour to allow setup. That temporary override takes precedence over the schedule until it expires or you select Resume schedule.

If credential validation fails during an upgrade, correct the problem and rerun installation. To return to the previously installed services in the meantime:

```sh
systemctl --user start family-wall.service family-wall-kiosk.service
```

## 9. Enable startup and verify the result

The graphical desktop must log in automatically as the user who installed the dashboard. The installer enables the application services, but it does not configure desktop auto-login.

If necessary, run this on the Pi and choose the desktop auto-login option for your display user:

```sh
sudo raspi-config
```

Use the following acceptance checklist before calling the setup complete:

1. Confirm the full-screen page is displaying on the HDMI monitor with the expected title and location.
2. Check a real timed event, an all-day event, and a repeating event against Apple Calendar. A development preview may use sample events.
3. Edit a calendar event and allow at least one five-minute refresh interval for the change to appear.
4. Watch two or more photo changes. At the default setting, each image remains for 60 seconds; an album with six images takes about six minutes to loop, plus any transition time.
5. Confirm weather location, Fahrenheit units, forecast dates, and update status.
6. Open the private access link on a phone connected to the same home network. Confirm settings load and the calendar is visible.
7. Note your preferred schedule, temporarily set short test windows, and select Resume schedule to remove the setup override. Confirm both sleep and wake, then restore your desired hours.
8. Reboot and confirm recovery during an on window. Outside an on window, a sleeping monitor is expected; use the phone's one-hour wake override if needed.
9. Briefly disconnect internet access after content has loaded. Confirm cached content remains visible and the status indicates the refresh issue. Restore the connection and confirm recovery.

To reboot:

```sh
sudo reboot
```

Do not unplug the Pi each night to turn off the display. The schedule is designed to control the monitor while the Pi remains available.

## 10. Daily operation and expected timing

Edit calendar events using Apple Calendar and add or remove pictures in the dedicated Shared Album. The dashboard does not edit your calendar.

The current refresh intervals are:

- Calendar: every 5 minutes.
- Photos from iCloud: every 15 minutes.
- Weather: every 15 minutes.
- Browser data refresh: every 15 seconds.
- Monitor schedule evaluation: approximately every 15 seconds.
- Photo rotation: 60 seconds by default, adjustable in Display settings.

The photo connector keeps up to the newest 500 still images, makes oriented JPEG copies with a maximum dimension of 1920 pixels, and skips videos. Album removals take effect after a successful complete photo sync. A failed sync preserves the previous complete cache.

Display settings supports two daily windows, photo duration, a one-hour wake override, and Resume schedule. These are the same windows every day; this version has no separate weekday/weekend schedule. The override clears when the service restarts.

The star-and-nebula image drifts over 75 seconds in each direction. Reduced-motion preferences disable the animation. If performance is poor on the Pi, simplify or disable the background animation in the stylesheet and rebuild.

Weather is model-based current conditions and forecast data, not a weather station attached to the house. See [Open-Meteo's weather documentation](https://open-meteo.com/en/docs).

Keep the phone access link private: possession grants access to the calendar and settings. It is intended for a trusted home network over local HTTP. Do not expose port 8080 to the internet or configure router port forwarding for it.

## 11. Maintenance and troubleshooting

### Inspect services

On the Pi:

```sh
systemctl --user status family-wall.service family-wall-kiosk.service
journalctl --user -u family-wall.service -n 40 --no-pager
journalctl --user -u family-wall-kiosk.service -n 40 --no-pager
```

Check logs before reinstalling. Remove personal event details, access links, and identifiers before sharing diagnostic output. Do not publish `config.json` or its backup.

### Calendar is missing or credentials stopped working

Verify the exact calendar name, accepted sharing invitation, and account access. Revoke and replace the dedicated app-specific password if needed. On the Pi:

```sh
systemctl --user stop family-wall.service
python3 ~/.local/share/family-wall/current/server.py --setup
systemctl --user start family-wall.service
```

The setup command also prints the private phone link again after successful validation. If the Pi's address changed, use its current router address in the link while keeping the key private.

### Photos do not update

Check that Public Website is enabled and that the album link opens without signing in. Confirm the supported URL format. Allow a 15-minute refresh interval. Review photo errors in the service log. If Apple changes its public interface, the connector may need a source update; repeatedly reinstalling the same version will not fix an incompatible endpoint.

### Screen remains asleep

Confirm the current time is inside an on window or use the one-hour wake override. Verify desktop auto-login, the Wayland socket, HDMI input, and `wlopm` control. Run the wake command from Section 5. Schedule changes can take about 15 seconds to apply.

### Screen remains on

Select Resume schedule to cancel an active override. Check both configured windows, the application's time zone, and service errors. A monitor that shows a “no signal” panel instead of sleeping needs a monitor-specific power test.

### Dashboard does not return after reboot

Check desktop auto-login first, then both user services. The kiosk waits for a graphical Wayland session and the local server. A terminal-only boot or desktop login screen will prevent normal kiosk startup.

### Weather location or clock is wrong

Check coordinates in configuration. Check the frontend's location text separately. Time zone is currently set in several source locations; follow Section 12 and rebuild. System clock synchronization must also be correct.

### Stop the display application

```sh
systemctl --user disable --now family-wall-kiosk.service family-wall.service
XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 wlopm --on '*'
```

This retains configuration, downloaded photos, and releases. If retiring or transferring the Pi, revoke the app-specific password and securely remove private configuration and cached content before handing over the device. A reboot restores the desktop's normal session processes after the kiosk has disabled an idle-blanking process for that session.

## 12. Adapt, rebuild, and package for another household

The current application has some household defaults embedded in source and compiled files. Copy the source into a separate working directory before preparing a reusable edition; keep the existing installed dashboard intact.

Review these files:

- `app/page.tsx`: visible household title, weather location label, time-zone constant, and any location-specific copy.
- `app/layout.tsx`: browser-page title and metadata.
- `app/globals.css`: layout, motion, and background styling.
- `public/nebula-background.png`: local background artwork.
- `pi/server.py`: default calendar name, album URL, coordinates, the `TZ` time zone, and the weather request's `timezone` parameter.
- `pi/kiosk.sh` and `pi/server.py`: Wayland display selection if the socket is not `wayland-0`.
- `pi/README.md`, `pi/VALIDATION.md`, and design notes: remove household names, addresses, links, and personal installation examples before redistribution.

Use a generic title such as “Family Wall.” Remove the embedded personal album URL from defaults and require each household to configure its own link before installation. Make weather coordinates and visible location labels agree. Use the same IANA time zone, such as `America/Denver`, in both frontend and backend, including the weather request and any visible time-zone labels.

Changing `config.json` alone does not change a compiled page title, city label, or hardcoded time zone. Rebuild the frontend after editing those values.

### Build on the development computer

Use the saved source project's dependency lockfile, Node.js 22.13 or newer, and pnpm. From the source project directory:

```sh
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm build
python3 scripts/package-pi.py
```

The package script collects `dist/client/` and the Pi runtime files. In this project it writes `Family-Wall-Space-Pi.zip` to the sibling `deliverables/` directory. Rename a copy to `family-wall.zip` if following Section 8 literally. Do not rename the folder inside the archive.

For backend tests, use a separate Python environment with `caldav`, `requests`, `Pillow`, and `icalendar` installed, then run:

```sh
python3 -m unittest discover -s tests
bash -n pi/install.sh pi/kiosk.sh
```

The dashboard's recorded validation included successful type checks, a production build, 13 backend tests, shell syntax checks, and archive checks. Broad lint was not fully clean. Those results do not replace real calendar, monitor, scheduling, and reboot checks on the Pi after any change.

### Review a shareable package

Before redistribution, search source files, generated web files, documentation, and the ZIP's extracted contents for personal names, emails, network addresses, public album tokens, and access keys. Rebuilding is essential because old values can survive in compiled JavaScript.

Exclude configuration, credential backups, caches, downloaded family photos, browser profiles, and development logs. Retain the required third-party notices. Only share the neutral package after inspecting its actual contents.

## 13. How the components fit together

The browser talks to a local Python service on port 8080. The service authenticates directly with Apple's CalDAV endpoint for calendar events, reads the album's public photo interface, and requests weather using coordinates. It caches results on the Pi and uses `wlopm` to control the monitor through the existing desktop session.

Important paths on the Pi:

- `~/.config/family-wall/config.json`: private credentials, access key, and settings.
- `~/.config/family-wall/cache.json`: cached display data.
- `~/.config/family-wall/photos/`: downloaded and resized photos.
- `~/.config/family-wall/chromium/`: dedicated browser profile.
- `~/.local/share/family-wall/releases/`: installed application versions.
- `~/.local/share/family-wall/current`: link to the active version.
- `~/.config/systemd/user/`: application service definitions.

Apple credentials remain in the Pi's backend configuration and are not sent to the dashboard browser. File permissions limit ordinary access to the Pi account; they are not encryption and do not protect against someone who controls that account or the device.

## 14. Reusable AI build prompt

If recreating the project without the saved source, this prompt communicates the intended behavior. It is a specification, not a substitute for the application code or device testing.

```text
Help me build a local family wall dashboard for a Raspberry Pi 3 Model B
running Raspberry Pi OS desktop with labwc/Wayland and an HDMI monitor.

Show one private shared iCloud calendar in a Monday-to-Sunday weekly view,
current weather and a five-day Fahrenheit forecast, and a dedicated public
iCloud Shared Album with still photos rotating every 60 seconds.

Use a black starfield with a slowly drifting pink, blue, purple, and subtle
green nebula background. Keep animation lightweight and respect reduced motion.

Support two screen-on windows every day, editable from a private local phone
page. Include a one-hour wake override and a resume-schedule control. Keep the
Pi powered on and use monitor sleep/wake rather than nightly shutdown.

Ask for the household's title, weather coordinates, time zone, and exact
calendar name. Do not ask me to paste passwords into chat. Use a local hidden
prompt for an Apple app-specific password and protect its configuration file.

Cache content, show stale-data status, handle all-day and recurring events,
and preserve working photos when a refresh fails. Keep access on the home LAN.
Do not promise that an unofficial Apple photo endpoint is stable.

Provide source code, a prebuilt Pi installer, repeatable setup instructions,
tests, third-party notices, and an acceptance checklist. Separate preview data
from verified real account data. Verify monitor wake, reboot startup, scheduling,
and performance on the physical Pi before claiming those tests are complete.
```

## 15. References and credits

- [Raspberry Pi getting started](https://www.raspberrypi.com/documentation/computers/getting-started.html): operating system and hardware preparation.
- [Raspberry Pi remote access](https://www.raspberrypi.com/documentation/computers/remote-access.html): SSH setup and discovery.
- [Apple app-specific passwords](https://support.apple.com/en-us/102654): credential creation and revocation.
- [Apple Shared Albums](https://support.apple.com/guide/icloud/create-and-manage-shared-albums-mme985ae44d8/icloud): public album sharing.
- [Open-Meteo](https://open-meteo.com/en/docs): weather API; retain applicable attribution, including CC BY 4.0 attribution for the weather data used here.
- [labwc integration](https://labwc.github.io/integration.html): monitor power control.
- [iCloud shared album connector reference](https://github.com/BZPJoe/icloud-shared-album-sync-repo): MIT-licensed public CloudKit mapping adapted for this project; retain the application's third-party notice.

External interfaces and operating system menus can change. The local application details in this guide describe the version reviewed on the preparation date.
