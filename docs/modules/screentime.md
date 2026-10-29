# Screen time and the break reminder

Added 2026-10-24. Settings: the Break reminder and Screen on cards of **Privacy and wellbeing** (`PagePrivacy`; the Screen time page, sidebar index 29, until 2026-10-28), key `wellbeing.breakEvery`
(`settings.py`), the stretch counting in `components/ScreenBreak.js` and its use in `services/ScreenTime.qml`. Reference: GNOME's
Wellbeing page and DankMaterialShell's DigitalWellbeing tab.

- **The totals** are the service's existing ones (screen on since boot, and since the charger was last unplugged). The battery popup showed them until 2026-10-25; it now shows uptime and time since the last charge instead (`panels.md`), so they appear only on this page. "On" means not locked and the monitors not powered off, sampled every 30 s (see the header of the service).
- **The reminder:** `wellbeing.breakEvery` (0 = never, default; 5 to 120 minutes, the page offers 20, 30, 45, 60, 90). The service also keeps the
  length of the current stretch (`streakSeconds`, shown on the page). A stretch grows while the screen is on; the screen off or locked for five minutes
  ends it, and so does a gap of over a minute between samples (the laptop slept or the shell stalled). When it reaches the limit the shell sends a
  low-urgency notification, "Time for a break", through its own server (`notify-send -a bbkOS`), so it follows do not disturb and lands in the history
  like any other, and the stretch starts again (the next reminder comes after another full interval).
- Cost: no new timer or process; the check rides on the existing 30-second sample.

## Verified (2026-10-24)

7 tests in `tests/theme/test_screen_break.py` under node (growth, the reminder and restart, off, five minutes off against a shorter lock, the gap, the first
sample) and the key, plus the whole suites. Live: with the limit at 20 minutes and the stretch set to 1190 s through the test hook
(`qs ipc call screentime setStreak`), the next sample sent "Time for a break" (it was in the notification history within 25 s) and the stretch went back to
0; the test entry was removed and the setting put back to Never. The page on screen with the real totals (6 h 49 min since start).

**Not verified:** a reminder after a real stretch, the popup's look, a real five-minute lock resetting the stretch, behaviour across suspend.

## Not done

A daily total, a per-app breakdown, and a longer "rest" prompt (this is a nudge to look away, nothing blocks the screen).
