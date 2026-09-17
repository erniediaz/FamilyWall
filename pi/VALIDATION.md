# Validation — 2026-09-16

## Passed locally on the Mac

- Fresh production static export of the approved space theme succeeded (2 routes, including the fallback).
- Final TypeScript check succeeded. Shell installer and kiosk scripts passed syntax checks.
- 13 Python unit tests: schedule boundaries, overnight windows, Mountain daylight-saving
  offsets, week rollover, invalid settings, parsed all-day/cancelled/moved-instance fixtures,
  duplicate calendars, cache retention on failure, credential exclusion and file permissions,
  photo-host checks, private LAN authentication, DNS-rebinding host rejection, cross-origin POST rejection.
- Live iCloud public-album retrieval downloaded all 6 still images and converted them to
  maximum-1920px JPEGs. No photos or Apple credentials are included in this installer.
- Live Open-Meteo request returned Fahrenheit weather and America/Denver forecast data.
- User previously verified private Family-calendar discovery and 15-second monitor sleep/wake.

## Limits and outstanding checks

- No direct SSH access from this task: No route to host. Installation on the Pi is pending.
- No actual family-event data was used in development. Calendar rendering was tested using
  fixtures, and recurrence expansion was requested but not yet verified against the user's
  real repeating events. Setup performs an event-fetch test using the Pi's installed library.
- The preview uses labeled sample calendar events plus live weather and shared-album photos.
- Space-theme preview was visually inspected and approved by the user. The display settings
  showed 60 seconds per photo. Local preview HTTP returned 200. Full browser interaction QA
  and device performance benchmarking have not been performed.
- The generated starter's broad lint check fails on unused supplied components and on
  style/compiler recommendations in the dashboard. Type checking and production export pass;
  do not interpret this package as having a clean repository-wide lint result.
- This package includes the newly generated production export and local nebula asset.
- User-service startup, physical Pi 3 performance, installed daily scheduling, recurring
  event behavior, and reboot/autologin recovery require checks on the actual Pi.

Photos use unofficial Apple public-album endpoints and may need maintenance after Apple changes.
