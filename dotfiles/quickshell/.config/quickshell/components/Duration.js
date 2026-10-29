.pragma library

// Timer durations (services/Countdown.qml, modules/panels/TimerControls.qml) and battery time left
// (modules/panels/BatteryPanel.qml, modules/power/BatteryAlerts.qml). Pure functions, tested under node
// (tests/calendar/test_duration.py).

var MAX_MS = 99 * 3600 * 1000

// What the user typed -> milliseconds, or null when it is not a duration or is zero or over 99 hours.
// Accepted: "5" (minutes), "5:30" (minutes:seconds), "1:05:00" (hours:minutes:seconds), "90s", "5m", "1h30m", "1h 30m 10s".
function parse(text) {
    const t = String(text).trim().toLowerCase()
    let ms = null, m
    if ((m = /^(\d{1,5})$/.exec(t))) ms = +m[1] * 60000
    else if ((m = /^(\d{1,4}):([0-5]?\d)$/.exec(t))) ms = (+m[1] * 60 + +m[2]) * 1000
    else if ((m = /^(\d{1,3}):([0-5]?\d):([0-5]?\d)$/.exec(t))) ms = ((+m[1] * 60 + +m[2]) * 60 + +m[3]) * 1000
    else if (t !== "" && (m = /^(?:(\d{1,3})\s*h)?\s*(?:(\d{1,5})\s*m(?:in)?)?\s*(?:(\d{1,6})\s*s(?:ec)?)?$/.exec(t)))
        ms = ((+(m[1] || 0)) * 3600 + (+(m[2] || 0)) * 60 + (+(m[3] || 0))) * 1000
    return ms !== null && ms > 0 && ms <= MAX_MS ? ms : null
}

// Milliseconds -> "MM:SS", or "H:MM:SS" from an hour up. Whole seconds, rounded up: a timer reads 00:01 until it ends.
function format(ms) {
    const s = Math.max(0, Math.ceil(ms / 1000))
    const h = Math.floor(s / 3600), mi = Math.floor(s / 60) % 60, se = s % 60
    const p = n => (n < 10 ? "0" : "") + n
    return h > 0 ? h + ":" + p(mi) + ":" + p(se) : p(mi) + ":" + p(se)
}

// Seconds -> "35 min" or "1 h 5 min", to the nearest minute: an estimate such as the battery's time left.
function approx(sec) {
    const m = Math.round(sec / 60)
    return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + (m % 60) + " min"
}
