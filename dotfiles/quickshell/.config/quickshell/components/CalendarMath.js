.pragma library

// Date maths for the calendar popup (modules/panels/CalendarPanel.qml): the month grid, the Nepali (Bikram Sambat) date,
// the ISO week, the share of the year gone and the moon phase. Pure functions, no Date objects held, so they are the
// same under the shell and under node (tests/calendar). Months are 0-based like JavaScript's.
//
// Bikram Sambat has no formula: the government publishes the month lengths (29 to 32 days) year by year. The table is
// BS 2064-2084 (14 Apr 2007 to 12 Apr 2028), taken from the MIT-licensed pyBSDate data
// (https://github.com/SushilShrestha/pyBSDate) after checking that the year lengths chain without a gap. Its later
// years (2085-2100) failed that check, so they are left out: outside the table toBS() returns null and the panel hides
// the Nepali dates. Extend it from the official calendar when 2028 comes near (docs/modules/calendar.md).

var BS_FIRST_YEAR = 2064
var BS_ANCHOR = Math.floor(Date.UTC(2007, 3, 14) / 86400000)       // day number of 1 Baisakh 2064
var BS_LENGTHS = [
    [31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
    [31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31],
    [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
    [31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30],
    [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
    [31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31],
    [31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30],
    [31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31],
    [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
    [31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30]
]

var BS_MONTHS = ["Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin", "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"]
var BS_MONTHS_NE = ["बैशाख", "जेठ", "असार", "श्रावण", "भदौ", "आश्विन", "कार्तिक", "मंसिर", "पौष", "माघ", "फाल्गुन", "चैत्र"]
var DEVANAGARI = "०१२३४५६७८९"

function dayNum(y, m, d) { return Math.floor(Date.UTC(y, m, d) / 86400000) }

function daysInMonth(y, m) { return new Date(Date.UTC(y, m + 1, 0)).getUTCDate() }

function nepaliDigits(n) { return String(n).replace(/[0-9]/g, c => DEVANAGARI[c]) }

// The Bikram Sambat date of an AD date: { year, month, day } or null outside the table.
function toBS(y, m, d) {
    let n = dayNum(y, m, d) - BS_ANCHOR
    if (n < 0) return null
    for (let i = 0; i < BS_LENGTHS.length; i++) {
        for (let mo = 0; mo < 12; mo++) {
            const len = BS_LENGTHS[i][mo]
            if (n < len) return { year: BS_FIRST_YEAR + i, month: mo, day: n + 1 }
            n -= len
        }
    }
    return null
}

// Days since the week start `weekStart` (0 sunday, 1 monday, 6 saturday) of the date's weekday.
function weekdayIndex(y, m, d, weekStart) {
    const wd = new Date(Date.UTC(y, m, d)).getUTCDay()
    return (wd - weekStart + 7) % 7
}

// The 6x7 grid of a month: every cell { y, m, d, inMonth, bs }. Six rows always, so the popup keeps one height.
function grid(y, m, weekStart) {
    const first = weekdayIndex(y, m, 1, weekStart)
    const cells = []
    for (let i = 0; i < 42; i++) {
        const dt = new Date(Date.UTC(y, m, 1 - first + i))
        const cy = dt.getUTCFullYear(), cm = dt.getUTCMonth(), cd = dt.getUTCDate()
        cells.push({ y: cy, m: cm, d: cd, inMonth: cm === m, bs: toBS(cy, cm, cd) })
    }
    return cells
}

// "Kartik - Mangsir 2083": the Bikram Sambat months a grid month spans, or "" when it is outside the table.
function bsTitle(y, m, nepali) {
    const a = toBS(y, m, 1), b = toBS(y, m, daysInMonth(y, m))
    if (!a || !b) return ""
    const names = nepali ? BS_MONTHS_NE : BS_MONTHS
    const yr = v => nepali ? nepaliDigits(v) : String(v)
    if (a.year === b.year && a.month === b.month) return names[a.month] + " " + yr(a.year)
    return names[a.month] + (a.year !== b.year ? " " + yr(a.year) : "") + " - " + names[b.month] + " " + yr(b.year)
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

// The same for the month and the week, as a fraction 0..1 of the days gone, today counted.
function monthProgress(now) {
    return now.getDate() / daysInMonth(now.getFullYear(), now.getMonth())
}

// The same for the Bikram Sambat year and month of `now`: { fraction, left }, null outside the table. The year counts the
// time of day as yearProgress does; the month counts today as monthProgress does.
function bsYearProgress(now) {
    const bs = toBS(now.getFullYear(), now.getMonth(), now.getDate())
    if (!bs) return null
    const row = BS_LENGTHS[bs.year - BS_FIRST_YEAR]
    const total = row.reduce((a, b) => a + b, 0)
    const day = row.slice(0, bs.month).reduce((a, b) => a + b, 0) + bs.day
    const fraction = (day - 1 + (now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()) / 86400) / total
    return { fraction: fraction, left: total - day }
}

function bsMonthProgress(now) {
    const bs = toBS(now.getFullYear(), now.getMonth(), now.getDate())
    if (!bs) return null
    const len = BS_LENGTHS[bs.year - BS_FIRST_YEAR][bs.month]
    return { fraction: bs.day / len, left: len - bs.day }
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
