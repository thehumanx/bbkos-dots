# Calendar popup and timer (clock click)

Added 2026-10-21. Left click on the bar clock opens a calendar popup in the same host as the other panels
(`PanelState` "calendar", `modules/panels/CalendarPanel.qml`, date maths in `components/CalendarMath.js`). Settings keys
`calendar.*` (`settings.py` `CALENDAR_DEFAULTS` and `RANGES`), shown on Bar › Widgets under "Calendar" (2026-10-28; was the Bar page's "Clock calendar" card).

## What it shows

- A six-row month grid (always six, so the popup keeps one height), today ringed in the accent, the selected day outlined.
  Click a day, scroll to change month, `‹ Today ›` buttons.
- The selected day in full: weekday, date, "Today / Tomorrow / In N days / N days ago", ISO week and day of year, and the
  moon phase.
- Two tiles: how much of the **year** and of the **month** has gone (the year's share includes the time of day, so it moves
  all day: 2026-10-21 12:00 is 80.5 %), with days left.
- Keyboard: arrows move the day (up and down by a week), PageUp and PageDown the month, `T` today,
  Esc closes (the panel host).

## World clocks

Added 2026-11-02. The popup has two panels side by side (each 320 px, the card 696 px; `Panels.qml` widens the card for "calendar", `CalendarPanel.colW`):
left the month, right the selected day, the year and month tiles and the timer. The **world clocks** are a strip of cards across both panels
under them, four to a row, so the popup is about one row taller however many zones there are (the first cut put them under the month and
the left panel grew 50 px per zone; the design audit of the same day moved them). Each card: the place, the time there (12 or 24 hour as
`clock.hour24`, AM/PM dim), and `Today / Tomorrow / Yesterday · 5:15 h ahead / behind` against this computer's own time. Hover a card for
its x; `+ Add time zone` opens a search over the tz database (type `tok`; matches the place, region or full name) and Enter or a click adds it.
The same list is edited on Bar › Widgets › Calendar › World clocks (chips to remove, the same search to add). Up to 8 zones. Setting `calendar.zones` (list of IANA names such as `Asia/Tokyo`,
default none; `bbkos-theme set calendar.zones Asia/Tokyo,Europe/London`; unknown or repeated names are dropped with a warning).
The offsets come from `bbkos-zones now ZONE...` (`bbkos_theme/zones.py`, python `zoneinfo`, so daylight saving is right; read when the
popup opens and when the list changes, not on a timer); `bbkos-zones list` feeds the search (the places in the tz database's `zone.tab` plus UTC; legacy aliases like `Australia/ACT` are not offered but a saved one still works). The search box needs the keyboard, so
the calendar's key shortcuts (arrows, T, N) stand aside while it or the timer's box has focus.

## Timer

Added 2026-10-21. The bottom of the calendar popup is a timer: presets (1, 5, 10, 30 min, 1 h; 15 and 25 min were dropped 2026-11-02) start at once, or type a
time and press Enter or Start: `5` is minutes, `5:30` minutes:seconds, `1:05:00` hours:minutes:seconds, `90s`, `5m`, `1h30m`
(zero, nonsense and over 99 hours are refused with a hint). While a timer exists the **timer widget** appears in the bar next to
the clock (`modules/bar/TimerWidget.qml`; layout key `timer`, section centre, hidden by its BarItem when idle). Click it for the
timer popup (same controls, `PanelState` "timer"): the live time with a progress bar, **Pause / Resume**, **+1 min**, **+5 min**,
**Reset**. Paused reads dim. On completion the widget turns red and its plate **flashes three times** (the text flips tone on
the plate), stays a soft red, and a notification "Timer finished" is sent; **Dismiss** clears it, and +1 min on a finished
timer starts a new one of that length. The red is a real red (`#ff5a5a` on a dark bar, `#b00020` on a light one), not
`Theme.crit`: with the high-contrast colour setting crit is near-white (`#ffece9` on this machine), which would not read as red.

State is `services/Countdown.qml` (one timer, idle / running / paused / done). It stores the end as a wall-clock stamp, so a
suspend or a late tick cannot drift it, and its tick is one single-shot timer aimed at the next whole second that runs only
while the timer runs: nothing wakes while idle, paused or done. It is **not kept across a shell restart**. Scripting and test
hooks: `qs ipc call timer start SECONDS | pause | resume | reset | add SECONDS | status`. Parsing and formatting are in
`components/Duration.js` (tested with node, `tests/calendar/test_duration.py`). No sound: the flash and the notification are
the signal.

## Settings

| Key | Default | Values |
|---|---|---|
| `calendar.weekStart` | mon | mon, sun, sat |
| `calendar.weekNumbers` | off | bool (ISO 8601 weeks, a column at the left) |
| `calendar.moon` | on | bool |

### The bar clock and the Date and time page (2026-10-24)

Bar › Widgets (`PageBarWidgets`; until 2026-10-28 the settings page **Date and time**, sidebar index 23, and a copy on the Bar page) holds the three `calendar.*` keys above and the
bar clock's `clock.hour24` (24 h, default on), `clock.date` (the date before the time, default on) and `clock.seconds` (default off). `clock.hoverDate` (default on) shows a card with the full date while the pointer is on the clock (`media.md`).
The format is `ddd d MMM   HH:mm` by default, `h:mm AP` for 12 hours, `:ss` added for seconds, and `HH` over `mm` (or `h` over `mm`) on a
vertical bar. With seconds on, `Clock.qml` asks `SystemClock` for second precision, so the shell wakes once a second instead of once a
minute: a small battery cost, off by default. The time zone is the system's (`timedatectl set-timezone`), not set here. Verified:
screenshots of the bar for 12 hour with seconds and date, 12 hour without the date, and the default; the seconds ticking (:47 then :48,
after a first version bound the precision to the wrong object and stayed at :00). The vertical-bar formats were not looked at.

## Moon phase

Mean lunation from a known new moon (6 Jan 2000 18:14 UTC), synodic month 29.5306 days; right to about a day. Good for
"is it full moon", not an almanac.

## Design and references

Searched 2026-10-21 for how others do it. Quickshell shells with a calendar: `At1ass/shell` (a Calendar tab in its dashboard),
`mavencore-shell` (month grid in a dashboard overlay), `mi-shell` on Codeberg (agenda from khal), `waycal` (agenda plus a
month overlay). Waybar's clock has a tooltip calendar with `mode = year`. None of them shows a year share, and
I could not find how Omarchy draws its year-progress figure (search returned nothing on it), so the percentage is our own:
day of the year plus the time of day, over the year's length. **Progress tiles (2026-10-29):** two tiles instead of
long bar rows: the year and the month. Each tile: the name, the percent, a 6 px bar and the days left. The popup itself follows the bbkOS panel host
(`panels.md`): one card centred on the widget that opened it (all popups do, `bar.md`), closes on click outside or Esc, nothing runs while it is closed.

## Cost

Nothing runs while closed. Open: a `SystemClock` at minute precision (the panel's own, gone when it closes) and a few
hundred JavaScript operations per redraw for the grid. No file, no network, no service.

## Verified and not

Timer verified 2026-10-21: start, pause, resume, +1 min and the popup on the live screen (a pause at 01:27 held, +60 s raised the total to 150 s), a burst of 40 screenshots across completion (red plate flashing, then the soft red resting state), the widget on a left bar (`1h`/`02`, `02`/`05`), the calendar popup's timer section, 14 tests. Not verified for the timer: typing a time and pressing Enter (no pointer to focus the input; parsing is tested), the Dismiss and Reset buttons by real click, that the plate flashes exactly three times (loops: 3 in the animation; the burst frames show repeated flashes but I did not count them one by one), a light theme, the notification on screen.

Calendar verified 2026-10-21: PageDown, Right and Down pressed with wtype moved the selection (Nov 2026, 29 Nov); node-backed tests (`tests/calendar`: grid shape for three week starts, leap February, ISO week edge cases, year progress, moon phases), settings tests, popup
screenshots on the live screen at bar top, bottom, left and right, week numbers on, Sunday
first. Not verified: a real mouse click on the clock (the popup was opened with `qs ipc call panel toggle calendar`; the
widget uses the same `BarHit` as the battery), the T key, a second monitor.
