# Family Wall 2 — Daily Highlights

This optional version adds a rotating header card. The original dashboard remains on the repository’s `main` branch; this version lives on `feature/daily-highlights`. Its installer ZIP is **Family-Wall-Highlights-Pi.zip**, separate from the original space-theme ZIP.

## What changes

- Desktop weather/footer spacing is tighter, giving the calendar and photos 42 additional vertical pixels at 1920×1080. Weather font sizes are unchanged; the bottom margin remains 8 pixels.

- A card between the date and weather changes every **15 seconds**, with a gentle fade and a pause/resume button.
- History, Fun Observances, Quotes, and Final Scores take turns in a shuffled order. Items within each category also shuffle; a long sports list does not crowd out the other categories.
- **One-minute policy:** when all four categories are available, every four-card cycle contains exactly one history item, one observance, one quote, and one final score, each displayed for 15 seconds. More sports results extend the number of cycles, never the share of screen time. Unavailable categories are skipped rather than filled with stale or invented information.
- History, observances, and quotes each have **at most 10 distinct items per Mountain-time calendar day**. They repeat during that day. There may be fewer if the source has fewer suitable entries or is unavailable.
- A daily sample of 10 quotes comes from 20 checked public-domain excerpts. Each includes its author and source book. It does not require an AI subscription or a quote-service account.
- NFL and MLB: all completed games, including Broncos and Rockies results without duplicates.
- NHL: Colorado Avalanche. NBA: Denver Nuggets.
- College football, men’s basketball, women’s basketball, and baseball: games involving an ESPN-designated Top 25 team, plus Florida Gators games regardless of ranking. Rank labels come from ESPN’s game data; polls may differ between sports.
- Sports results cover today and the previous seven calendar days. Dates and final status are displayed. Scheduled, live, postponed, and canceled games are excluded. No games during the off-season means no cards for that sport.
- Current and previous-day scoreboards refresh approximately every 30 minutes. Older scoreboards refresh daily for corrections. This is a results display, not a live ticker.
- The Monday–Sunday calendar, photo shuffle, 60-second default photo interval, nebula animation, and monitor schedule remain in place.

## Preview first

The prepared local preview uses **http://127.0.0.1:5174/**. The original preview uses port 5173. Preview calendar events are labeled samples. Public highlights are real fetched content; the preview does not connect to the private calendar.

The first fetch can take a few minutes on a slow connection. Quotes appear immediately; other categories appear as their feeds load. Subsequent startup uses the saved highlights cache.

## Upgrade an existing Pi

Use the Pi’s normal login account. Do not use `sudo` for the commands below. Copy the new ZIP to that account’s home folder, then:

```bash
mkdir -p ~/family-wall-highlights-installer
unzip -o ~/Family-Wall-Highlights-Pi.zip -d ~/family-wall-highlights-installer
cd ~/family-wall-highlights-installer/family-wall
python3 release.py install --title "Your Family Wall"
```

Replace the quoted title with the title you want on the screen. To retain an existing configured `display_title`, omit `--title`. If none is configured, the default is “FAMILY WALL.” The title is stored locally on the Pi, not in this repository.

The updater checks the new files, creates a separate release folder, saves the current release as `~/.local/share/family-wall/before-highlights`, and restarts both the dashboard service and Chromium. It verifies the new service’s version; a failed startup automatically restores the previous release. Installation does not temporarily override the monitor schedule, so a correctly sleeping monitor stays asleep.

Do not copy only `web/` for this upgrade: the backend and new data files must be installed together. The updater includes them all. Existing calendar credentials, album link, photo files, weather coordinates, and schedule remain in `~/.config/family-wall/`.

### Return to the previous dashboard

```bash
python3 ~/.local/share/family-wall/current/release.py rollback
```

Or run the retained installer’s copy:

```bash
python3 ~/family-wall-highlights-installer/family-wall/release.py rollback
```

Rollback switches the saved release back into use and restarts Chromium. It does not delete either release or the photo/calendar cache. Keep the saved release folder and `before-highlights` symlink. Reinstalling highlights retains the original backup.

### Fresh installation

Follow `README.md` for Raspberry Pi OS, desktop auto-login, HDMI, and iCloud setup. Use this ZIP and run `bash install.sh` in its extracted folder. A fresh install has no previous release to restore; the rollback command applies only to upgrades.

## Sources and resilience

- History: [Wikipedia On This Day](https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/09/18), using the actual month/day, limited to complete short entries. Attribution: Wikipedia contributors, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Displayed wording is retained, with whitespace normalized and the year displayed separately. Facts link to the date’s Events section.
- Fun Observances: [Checkiday](https://www.checkiday.com/), using its currently accessible legacy daily feed. Names link to the source’s detail pages. These include unofficial celebrations and awareness days, not just official holidays. The legacy feed has no uptime guarantee; [Checkiday’s supported API plans](https://www.checkiday.com/developers.php) are a possible future replacement.
- Quotes: excerpts checked against public-domain books hosted by [Project Gutenberg](https://www.gutenberg.org/). The source collection is `pi/quotes.json`; fictional dialogue also names the speaker in the source label.
- Scores: ESPN’s public scoreboard feeds. These are undocumented endpoints and can change. No API key is currently needed. Each result links to ESPN; this is not an ESPN-sponsored product.

The Pi fetches and caches public data; the browser only contacts the Pi. No calendar events, Apple credentials, or family photos are sent to these sources. Requests contain dates and league identifiers.

If a daily source fails, it retries after 30 minutes and its category is skipped. Yesterday’s history/observances are never labeled as today’s. Quotes still work offline. Recent saved sports results can remain visible with “saved result” until they age out of the seven-day window. Sources do not block the calendar, photos, or monitor-control worker.

## Files and development

- `pi/highlights.py`: data sources, daily limits, final-score filtering, separate cache.
- `pi/quotes.json`: verified source-attributed quotation collection.
- `components/daily-highlights.tsx`: card and 15-second timer.
- `lib/highlight-order.ts`: shuffle and balanced category rotation.
- `pi/release.py`: upgrade and rollback.
- `~/.config/family-wall/highlights.json`: runtime cache, never committed.

Build with the repository’s existing Node dependencies (`tsc --noEmit`, `vinext build`), then run `python3 scripts/package-pi.py`. Output is a new Highlights ZIP; it does not overwrite the original Space ZIP.

Tests: `python3 -m unittest discover -s tests -p 'test_*.py'` with the Pi dependencies installed, plus `node --test tests/*.test.mjs` using the supported Node runtime.

## Deployment boundary

Mac tests and a local browser preview do not establish Pi hardware performance or physical monitor wake behavior. After installation, verify the header, photos, and the next scheduled sleep/wake on the actual Pi. The monitor-control code itself is unchanged in this version.
