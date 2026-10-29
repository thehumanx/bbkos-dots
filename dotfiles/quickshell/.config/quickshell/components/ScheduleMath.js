.pragma library

// The automatic light and dark schedule (colors.auto, modules/theme/ThemeSchedule.qml): which palette a time of day gets.

// "7:30" or "07:30" -> minutes since midnight, or -1 when it is not a 24-hour clock time.
function parseClock(text) {
    const m = /^([01]?[0-9]|2[0-3]):([0-5][0-9])$/.exec(String(text))
    return m ? Number(m[1]) * 60 + Number(m[2]) : -1
}

// True when `minutes` (since midnight) falls in the light part of the day: from lightFrom until darkFrom, which may wrap past
// midnight (light from 19:00 to 07:00 is a valid choice). Bad times fall back to 07:00 and 19:00; equal times mean light.
function isLight(minutes, lightFrom, darkFrom) {
    let lf = parseClock(lightFrom)
    let df = parseClock(darkFrom)
    if (lf < 0) lf = 7 * 60
    if (df < 0) df = 19 * 60
    if (lf === df) return true
    return lf < df ? (minutes >= lf && minutes < df) : (minutes >= lf || minutes < df)
}
