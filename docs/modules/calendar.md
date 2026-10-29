# Calendar popup and timer (clock click)

Added 2026-10-21. Left click on the bar clock opens a calendar popup in the same host as the other panels
(`PanelState` "calendar", `modules/panels/CalendarPanel.qml`, date maths in `components/CalendarMath.js`). Settings keys
`calendar.*` (`settings.py` `CALENDAR_DEFAULTS` and `RANGES`), shown on Bar › Widgets under "Calendar" (2026-10-28; was the Bar page's "Clock calendar" card).

## What it shows

- A six-row month grid (always six, so the popup keeps one height), today ringed in the accent, the selected day outlined.
  Click a day, scroll to change month, `‹ Today ›` buttons.
- The selected day in full: weekday, date, "Today / Tomorrow / In N days / N days ago", ISO week and day of year, and the
  moon phase.
- Two bars: how much of the **year** and of the **month** has gone (the year's share includes the time of day, so it moves
  all day: 2026-10-21 12:00 is 80.5 %), with days left.
- **Nepali dates** (`calendar.nepali`, also the `BS` button in the popup or `N`): the Bikram Sambat day under each AD day (the
  Nepali month name on day 1), the BS months the grid month spans in the header, and the full BS date in Latin and Devanagari
  for the selected day. Saturdays turn crit-coloured while it is on (Nepal's weekly holiday).
- Keyboard: arrows move the day (up and down by a week), PageUp and PageDown the month, `T` today, `N` the Nepali dates,
  Esc closes (the panel host).

## Timer

Added 2026-10-21. The bottom of the calendar popup is a timer: presets (1, 5, 10, 15, 25, 30 min, 1 h) start at once, or type a
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
| `calendar.nepali` | off | bool |
| `calendar.weekStart` | mon | mon, sun, sat |
| `calendar.weekNumbers` | off | bool (ISO 8601 weeks, a column at the left) |
| `calendar.moon` | on | bool |

### The bar clock and the Date and time page (2026-10-24)

Bar › Widgets (`PageBarWidgets`; until 2026-10-28 the settings page **Date and time**, sidebar index 23, and a copy on the Bar page) holds the four `calendar.*` keys above and the
bar clock's `clock.hour24` (24 h, default on), `clock.date` (the date before the time, default on) and `clock.seconds` (default off). `clock.hoverDate` (default on) shows a card with the full and Nepali date while the pointer is on the clock (`media.md`).
The format is `ddd d MMM   HH:mm` by default, `h:mm AP` for 12 hours, `:ss` added for seconds, and `HH` over `mm` (or `h` over `mm`) on a
vertical bar. With seconds on, `Clock.qml` asks `SystemClock` for second precision, so the shell wakes once a second instead of once a
minute: a small battery cost, off by default. The time zone is the system's (`timedatectl set-timezone`), not set here. Verified:
screenshots of the bar for 12 hour with seconds and date, 12 hour without the date, and the default; the seconds ticking (:47 then :48,
after a first version bound the precision to the wrong object and stayed at :00). The vertical-bar formats were not looked at.

## The Bikram Sambat table

Bikram Sambat has no formula: month lengths (29 to 32 days) are published year by year. `CalendarMath.js` holds BS 2064 to
2084 (14 Apr 2007 to 12 Apr 2028), from the MIT-licensed pyBSDate data (`SushilShrestha/pyBSDate`, itself from
`bahadurbaniya/Date-Converter-Bikram-Sambat-to-English-Date`). That data was **checked, not trusted**: its per-year start
dates must equal the previous start plus the month lengths, and they do for 2064 to 2084 but not for 2062 to 2063 and 2085
to 2098 (17 broken years; one is a plain typo, 2005 for 2006), so those years are left out. Outside the table `toBS` returns
`null` and the popup says "Nepali dates cover 2007 to April 2028". **To extend it** take the month lengths from the
government's published calendar, append the years to `BS_LENGTHS`, and `tests/calendar` re-checks that every day chains.
Anchors confirmed by hand: 1 Baisakh 2082 is 14 Apr 2025, 1 Baisakh 2083 is 14 Apr 2026. Public holidays and festival dates
(tithi based) are not included: no open, trustworthy data was found, so the popup does not guess them.

## Moon phase

Mean lunation from a known new moon (6 Jan 2000 18:14 UTC), synodic month 29.5306 days; right to about a day. Good for
"is it full moon", not an almanac.

## Design and references

Searched 2026-10-21 for how others do it. Quickshell shells with a calendar: `At1ass/shell` (a Calendar tab in its dashboard),
`mavencore-shell` (month grid in a dashboard overlay), `mi-shell` on Codeberg (agenda from khal), `waycal` (agenda plus a
month overlay). Waybar's clock has a tooltip calendar with `mode = year`. None of them shows a year share or a Nepali date, and
I could not find how Omarchy draws its year-progress figure (search returned nothing on it), so the percentage is our own:
day of the year plus the time of day, over the year's length. **Progress tiles (2026-10-29):** a 2 × 2 grid instead of
long bar rows: the year and the month (Gregorian) on top and, while Nepali dates are on, the Bikram Sambat year and month
(`Cal.bsYearProgress`, `Cal.bsMonthProgress`: the same year rule, the month counting today as the Gregorian month does,
null outside the table, which hides the row). Each tile: the name, the percent, a 6 px bar and the days left. The popup itself follows the bbkOS panel host
(`panels.md`): one card centred on the widget that opened it (all popups do, `bar.md`), closes on click outside or Esc, nothing runs while it is closed.

## Cost

Nothing runs while closed. Open: a `SystemClock` at minute precision (the panel's own, gone when it closes) and a few
hundred JavaScript operations per redraw for the grid. No file, no network, no service.

## Verified and not

Timer verified 2026-10-21: start, pause, resume, +1 min and the popup on the live screen (a pause at 01:27 held, +60 s raised the total to 150 s), a burst of 40 screenshots across completion (red plate flashing, then the soft red resting state), the widget on a left bar (`1h`/`02`, `02`/`05`), the calendar popup's timer section, 14 tests. Not verified for the timer: typing a time and pressing Enter (no pointer to focus the input; parsing is tested), the Dismiss and Reset buttons by real click, that the plate flashes exactly three times (loops: 3 in the animation; the burst frames show repeated flashes but I did not count them one by one), a light theme, the notification on screen.

Calendar verified 2026-10-21: PageDown, Right and Down pressed with wtype moved the selection (Nov 2026, 29 Nov); 11 node-backed tests (`tests/calendar`: table anchors, every day of 2007 to 2028 chains without a gap,
grid shape for three week starts, leap February, ISO week edge cases, year progress, moon phases), settings tests, popup
screenshots on the live screen at bar top, bottom, left and right, with Nepali dates on and off, week numbers on, Sunday
first. Not verified: a real mouse click on the clock (the popup was opened with `qs ipc call panel toggle calendar`; the
widget uses the same `BarHit` as the battery), the T and N keys, a second monitor, BS dates against an
official printed calendar beyond the two new-year anchors and today (21 Oct 2026 = 4 Kartik 2083).
