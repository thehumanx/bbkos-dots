.pragma library

// Break reminders (services/ScreenTime.qml, wellbeing.breakEvery). The screen is sampled every `intervalMs`; this keeps the length of the
// current stretch at the screen. Pure, tested under node (tests/theme/test_screen_break.py).

var RESET_OFF_SECONDS = 300      // the screen off or locked this long counts as a break

// state { streak, off } in seconds. on: the screen was on and unlocked at this sample. dtMs: time since the previous sample (0 for the
// first). Returns the new state and `remind`: the stretch just reached everyMinutes (0 = reminders off), after which it starts again.
function step(state, on, dtMs, intervalMs, everyMinutes) {
    let streak = state.streak, off = state.off
    if (dtMs > 2 * intervalMs) {                        // asleep or stalled for a while: that was a break
        streak = 0
        off = 0
    } else if (on) {
        streak += dtMs / 1000
        off = 0
    } else {
        off += (dtMs > 0 ? dtMs : intervalMs) / 1000
        if (off >= RESET_OFF_SECONDS) streak = 0
    }
    let remind = false
    if (everyMinutes > 0 && streak >= everyMinutes * 60) {
        remind = true
        streak = 0
    }
    return { streak: streak, off: off, remind: remind }
}
