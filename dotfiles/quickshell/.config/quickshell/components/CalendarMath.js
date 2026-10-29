.pragma library

// Date maths for the calendar popup (modules/panels/CalendarPanel.qml): the month grid, the ISO week, the share of the
// year gone and the moon phase. Pure functions, no Date objects held, so they are the same under the shell and under
// node (tests/calendar). Months are 0-based like JavaScript's.

function dayNum(y, m, d) { return Math.floor(Date.UTC(y, m, d) / 86400000) }

function daysInMonth(y, m) { return new Date(Date.UTC(y, m + 1, 0)).getUTCDate() }

// Days since the week start `weekStart` (0 sunday, 1 monday, 6 saturday) of the date's weekday.
function weekdayIndex(y, m, d, weekStart) {
    const wd = new Date(Date.UTC(y, m, d)).getUTCDay()
    return (wd - weekStart + 7) % 7
}

// The 6x7 grid of a month: every cell { y, m, d, inMonth }. Six rows always, so the popup keeps one height.
function grid(y, m, weekStart) {
    const first = weekdayIndex(y, m, 1, weekStart)
    const cells = []
    for (let i = 0; i < 42; i++) {
        const dt = new Date(Date.UTC(y, m, 1 - first + i))
        const cy = dt.getUTCFullYear(), cm = dt.getUTCMonth(), cd = dt.getUTCDate()
        cells.push({ y: cy, m: cm, d: cd, inMonth: cm === m })
    }
    return cells
}

// ISO 8601 week number (weeks start on Monday; week 1 holds the year's first Thursday).
function isoWeek(y, m, d) {
    const n = dayNum(y, m, d)
    const thu = n + 3 - ((new Date(n * 86400000).getUTCDay() + 6) % 7)
    const yearStart = dayNum(new Date(thu * 86400000).getUTCFullYear(), 0, 1)
    return Math.floor((thu - yearStart) / 7) + 1
}

// How far through the calendar year `now` (a Date, local time) is: { day, total, fraction, left }.
function yearProgress(now) {
    const y = now.getFullYear()
    const total = (dayNum(y + 1, 0, 1) - dayNum(y, 0, 1))
    const day = dayNum(y, now.getMonth(), now.getDate()) - dayNum(y, 0, 1) + 1
    const fraction = (day - 1 + (now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()) / 86400) / total
    return { day: day, total: total, fraction: fraction, left: total - day }
}

// The same for the month, as a fraction 0..1 of the days gone, today counted.
function monthProgress(now) {
    return now.getDate() / daysInMonth(now.getFullYear(), now.getMonth())
}

var SYNODIC = 29.530588853
var NEW_MOON = Date.UTC(2000, 0, 6, 18, 14) / 86400000            // a known new moon, in days since 1970

// Moon phase at noon UTC of the date: { age (days), lit (0..1), name, icon }. Mean-lunation accuracy: within about a
// day, which is enough for a calendar cell; it is not an almanac.
function moon(y, m, d) {
    let age = (Date.UTC(y, m, d, 12) / 86400000 - NEW_MOON) % SYNODIC
    if (age < 0) age += SYNODIC
    const lit = (1 - Math.cos(2 * Math.PI * age / SYNODIC)) / 2
    const i = Math.floor((age / SYNODIC) * 8 + 0.5) % 8
    return { age: age, lit: lit, name: MOON_NAMES[i], icon: MOON_ICONS[i] }
}
var MOON_NAMES = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous", "Full moon", "Waning gibbous", "Last quarter", "Waning crescent"]
var MOON_ICONS = ["\u{1F311}", "\u{1F312}", "\u{1F313}", "\u{1F314}", "\u{1F315}", "\u{1F316}", "\u{1F317}", "\u{1F318}"]
