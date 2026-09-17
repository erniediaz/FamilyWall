# From an Idea to a Family Wall: Building with AI and a Raspberry Pi

*How a spare computer, an HDMI monitor, and a conversation became a practical home dashboard.*

I wanted a place where the family could glance at the week ahead without opening another app. The idea was simple: show our shared calendar, the weather, and a rotating collection of photos on a screen at home.

I already had a Raspberry Pi 3 Model B and a monitor. What I did not have was a finished plan—or a keyboard and mouse to plug into the Pi.

That turned out to be a useful starting point for working with AI. I could describe the result I wanted in ordinary language, then work through the details one manageable step at a time.

## Start with the household routine

The first decisions were about how the screen should fit into daily life.

We wanted a weekly calendar, one shared source of events, and a dedicated photo album. Weather needed a clear temperature and forecast. The screen also needed to sleep when it was not useful, with one on window in the morning and another later in the day.

Those details became the specification. They helped avoid building a dashboard that looked attractive but needed constant attention.

The resulting design uses a private iCloud calendar, an iCloud Shared Album, and Open-Meteo weather. A local Python service gathers the information, while Chromium displays the dashboard full-screen on the Pi.

## Getting connected without extra equipment

The first practical challenge was accessing the Pi from another computer. We used SSH, which provides a remote terminal over the home network.

Finding the correct device address took a little troubleshooting. A failed network test did not mean the project was impossible; it meant we needed to check the router and confirm which address belonged to the Pi.

Once connected, we checked the operating system, browser, and desktop environment. Those checks mattered because monitor-control instructions vary between older Raspberry Pi setups and the newer Wayland desktop.

AI helped interpret the results and choose the next step. I still supplied the local information and performed the hardware checks. That division of work kept the process moving without pretending the assistant could see or control everything.

## Test the uncertain parts early

Before investing in the finished dashboard, we tested whether the monitor could sleep and wake under software control.

The test turned the display off for 15 seconds and brought it back. It was a small success, but it answered an important question: could the morning and afternoon schedule work without shutting down the entire Pi?

The design keeps the Pi running and controls only the monitor. That lets it refresh information while the screen is dark and bring the display back at the next scheduled time.

We also confirmed that the intended shared calendar could be found through Apple's calendar service. Access to a calendar is one milestone; accurately displaying real events, recurring appointments, and all-day entries remains a separate acceptance check.

## Connect existing habits to the screen

The aim was to keep using familiar tools.

Calendar changes happen in Apple Calendar. Photos are added to a dedicated Shared Album. The dashboard refreshes those sources in the background rather than requiring a second round of data entry.

The calendar connection uses an Apple app-specific password entered privately on the Pi. The photo connection uses a public album link. These are different privacy arrangements: the calendar is authenticated, while anyone with the album's public link can view its photos. A dedicated album makes it easier to choose exactly what belongs on the wall.

The photo integration also exposed one of the less glamorous parts of building software. Apple's public album formats do not all behave the same way, and this connector relies on an unofficial interface. AI helped investigate that compatibility issue and adapt the connector, but it cannot make an unofficial service permanent.

That is why the dashboard keeps a local photo cache and preserves the last complete collection when a refresh fails.

## Make it feel like part of the home

Once the structure was in place, we could make the display more personal.

The background became a black starfield with pink, blue, purple, and hints of green nebula color. It moves slowly enough to add atmosphere without competing with calendar entries. The implementation gently shifts a background image, which is a more modest task for an older Pi than rendering a complex live scene.

Photos stay on screen for a minute by default. That gives each one time to be enjoyed while keeping the display fresh. The interval is adjustable.

This was one of the most enjoyable parts of working with AI: I could describe the feeling I wanted, inspect a preview, and refine it with a short follow-up. The assistant translated those choices into layout, styling, and animation changes.

## The useful work behind the preview

A good-looking preview is only part of a usable household project.

The application also needed a repeatable installer, startup services, saved settings, error messages, and a way to recover when the network was unavailable. The installer packages the built dashboard so the Pi does not need to compile the frontend itself.

A private local settings page allows schedule and photo-interval changes from a phone on the same network. A one-hour wake override helps when setting up the screen outside its normal hours.

The development work included a production build, type checks, 13 backend tests, and packaging checks. Physical-device behavior still needs its own checklist: real events, repeated photo changes, both schedule windows, and recovery after reboot. Software tests and a browser preview cannot prove all of those things.

That distinction is part of what made the process useful. We could see what was demonstrated and what still needed a household test.

## What AI made easier

AI reduced the effort of moving between different kinds of work: network troubleshooting, Apple integration, interface design, scripting, testing, and documentation.

Instead of researching each piece in isolation, I could keep the overall goal in one conversation. A question about photo timing could lead directly to a settings change. A concern about monitor scheduling could become a small test before it became a larger installation problem.

There were still decisions for me to make. I chose the information, approved the appearance, entered credentials locally, and checked the actual monitor. The assistant contributed implementation work and explanations that made those decisions easier to act on.

The value was a shorter path from “Could this work?” to something concrete that could be inspected, adjusted, and installed again.

## What I would tell someone starting a similar project

Start with one calendar, one album, and a clear daily schedule. Test remote access and monitor wake before polishing the design. Keep credentials out of chat and public files. Save the source code and installer as carefully as the finished screen layout.

Most of all, ask for a repeatable process. A dashboard that can be rebuilt after a failed card or moved to another Pi is much more useful than a one-time demonstration.

A family wall is a modest project, but it captures a practical way to use AI: bring a clear household need, work through the uncertain parts together, and leave with both the software and instructions for maintaining it.

## Build your own

The companion [step-by-step setup guide](setup-guide.html) explains the hardware, headless access, Apple connections, installation, schedule, and verification checklist. It documents this custom application; recreating it requires either the retained source and installer or a new implementation using the included build prompt.

For the underlying services, consult [Raspberry Pi's documentation](https://www.raspberrypi.com/documentation/computers/getting-started.html), [Apple's app-specific password guide](https://support.apple.com/en-us/102654), [Apple's Shared Album guidance](https://support.apple.com/guide/icloud/create-and-manage-shared-albums-mme985ae44d8/icloud), and [Open-Meteo](https://open-meteo.com/).
