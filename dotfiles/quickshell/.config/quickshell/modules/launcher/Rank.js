.pragma library
// Ranking for the bbkOS menu (docs/modules/menu.md). Our own code, after the behaviour oma-cast documents for Raycast's
// root search (github.com/typecraft-dev/oma-cast, SPEC.md and reference/02-backend.md section 4, read 2026-10-23;
// no code copied, the repo states no license):
// - fuzzy(): every query character must appear in order; a character at the very start scores 4, at the start of a word
//   3, elsewhere 2; a jump over skipped characters costs 1. Accepted at "medium" sensitivity:
//   score >= 1.5 * (length - 2) + 4.
// - A whole-word hit in the title is lifted to at least the score of a prefix of that length.
// - Frecency: every launch is remembered (the newest 10 per item); each counts exp(-age / 14 days). Learned search
//   terms: a query used to open an item before (within 17 days) puts it first when typed again, or as a prefix of it.
// Tests: tests/launcher/test_rank.py (runs this file under node).

var SEPARATORS = " \t\n-./()[]_:"

function isSep(c) { return SEPARATORS.indexOf(c) >= 0 }

// Best score of `query` as a subsequence of `target` (both lower case), or -1.
function fuzzy(target, query) {
    if (query.length === 0) return 0
    if (target === query) return 1000
    if (query.length > target.length) return -1
    // dynamic programming over (query index, target index): best[i][j] = best score with query[i] matched at target[j]
    var prev = null
    for (var i = 0; i < query.length; i++) {
        var cur = new Array(target.length).fill(-1)
        var q = query[i]
        for (var j = i; j < target.length; j++) {
            if (target[j] !== q) continue
            var s = j === 0 ? 4 : (isSep(target[j - 1]) ? 3 : 2)
            if (i === 0) { cur[j] = s; continue }
            var best = -1
            for (var k = i - 1; k < j; k++) {
                if (prev[k] < 0) continue
                var v = prev[k] + s - (k === j - 1 ? 0 : 1)
                if (v > best) best = v
            }
            cur[j] = best
        }
        prev = cur
        var any = false
        for (var m = 0; m < cur.length; m++) if (cur[m] >= 0) { any = true; break }
        if (!any) return -1
    }
    return Math.max.apply(null, prev)
}

function accepted(score, length) {
    return score >= 0 && (length <= 2 || score >= 1.5 * (length - 2) + 4)
}

function wholeWord(target, query) {
    var at = target.indexOf(query)
    while (at >= 0) {
        var before = at === 0 || isSep(target[at - 1])
        var after = at + query.length === target.length || isSep(target[at + query.length])
        if (before && after) return true
        at = target.indexOf(query, at + 1)
    }
    return false
}

// Text score of one item: the best of its title, subtitle (fuzzy) and keywords (word prefix); the last two count a
// little less than the title.
function textScore(item, query) {
    var q = query.toLowerCase()
    var title = item.title.toLowerCase()
    var best = fuzzy(title, q)
    if (best !== 1000 && q.length >= 3 && q.indexOf(" ") < 0 && wholeWord(title, q))
        best = Math.max(best, 4 + (q.length - 1) * 2 + 0.5)
    // A query of several words also matches a title in which every word starts one of its words ("card gap" finds
    // "Gap between cards"), scored like a keyword hit.
    if (q.indexOf(" ") > 0) {
        var words = q.split(/\s+/).filter(function (w) { return w !== "" })
        if (words.length > 1 && words.every(function (w) { return (" " + title).indexOf(" " + w) >= 0 }))
            best = Math.max(best, 4 + (q.length - 1) * 2 - 1)
    }
    var sub = item.subtitleOnly ? -1 : fuzzy(String(item.subtitle || "").toLowerCase(), q)
    if (sub >= 0 && accepted(sub, q.length)) best = Math.max(best, sub - 1)
    // Keywords match only at the start of one of their words: app keyword lists are long (Thunar's has 17), and a
    // fuzzy match over them finds unrelated apps.
    var kws = item.keywords || []
    for (var i = 0; i < kws.length; i++) {
        var k = " " + String(kws[i]).toLowerCase()
        if (k.indexOf(" " + q) >= 0) best = Math.max(best, 4 + (q.length - 1) * 2 - 1)
    }
    return accepted(best, q.length) ? best : -1
}

var DAY = 86400000

function frecency(visits, now) {
    var f = 0
    for (var i = 0; i < (visits || []).length; i++) f += Math.exp(-(now - visits[i]) / (14 * DAY))
    return f
}

// 2 = the query was used for this item before, 1 = a learned term starts with the query, 0 = neither.
function learned(terms, query, lastVisit, now) {
    if (!terms || !lastVisit || now - lastVisit > 17 * DAY) return 0
    var q = query.toLowerCase(), best = 0
    for (var i = 0; i < terms.length; i++) {
        if (terms[i] === q) return 2
        if (terms[i].indexOf(q) === 0) best = 1
    }
    return best
}

// items: [{ id, title, subtitle, keywords, kind }]; usage: { id: { visits: [ms], terms: [query] } }.
// Kinds rank apps first on a tie (Raycast's order: application, command, other).
var KIND_ORDER = { app: 5, webapp: 5, command: 4, settings: 3 }

function rank(items, query, usage, now) {
    usage = usage || {}
    var q = query.trim()
    var out = []
    for (var i = 0; i < items.length; i++) {
        var it = items[i]
        var u = usage[it.id] || {}
        var visits = u.visits || []
        var f = frecency(visits, now)
        if (q === "") { out.push({ item: it, text: 0, learned: 0, f: f }); continue }
        var t = textScore(it, q)
        var l = learned(u.terms, q, visits.length ? visits[visits.length - 1] : 0, now)
        if (t < 0 && l === 0) continue
        out.push({ item: it, text: t, learned: l, f: f })
    }
    out.sort(function (a, b) {
        return (b.learned - a.learned) || (b.text - a.text) || (b.f - a.f)
            || ((KIND_ORDER[b.item.kind] || 0) - (KIND_ORDER[a.item.kind] || 0))
            || a.item.title.localeCompare(b.item.title)
    })
    return out.map(function (r) { return r.item })
}

// Record a launch: the newest 10 visits and 5 distinct queries per item, at most 300 items (oldest dropped).
function record(usage, id, query, now) {
    var next = JSON.parse(JSON.stringify(usage || {}))
    var u = next[id] || { visits: [], terms: [] }
    u.visits = (u.visits || []).concat([now]).slice(-10)
    var q = query.trim().toLowerCase()
    if (q !== "") u.terms = [q].concat((u.terms || []).filter(function (t) { return t !== q })).slice(0, 5)
    next[id] = u
    var ids = Object.keys(next)
    if (ids.length > 300) {
        ids.sort(function (a, b) { return last(next[a]) - last(next[b]) })
        for (var i = 0; i < ids.length - 300; i++) delete next[ids[i]]
    }
    return next
}

function last(u) { return u && u.visits && u.visits.length ? u.visits[u.visits.length - 1] : 0 }

// ---- Calculator: + - * / % ^ and parentheses on decimal numbers. A tiny recursive-descent parser, never eval().
// Returns a number, or null when the text is not a calculation (no operator, or anything else in it).
function calculate(text) {
    var s = text.replace(/\s+/g, "").replace(/×/g, "*").replace(/÷/g, "/").replace(/,/g, "")
    if (!/^[0-9.+\-*/%^()]+$/.test(s) || !/[+\-*/%^]/.test(s.replace(/^-/, ""))) return null
    var pos = 0
    function peek() { return s[pos] }
    function number() {
        var m = /^\d*\.?\d+(?:e[+-]?\d+)?|^\d+\.?/.exec(s.slice(pos))
        if (!m) throw "number"
        pos += m[0].length
        return parseFloat(m[0])
    }
    function atom() {
        if (peek() === "(") { pos++; var v = expr(); if (peek() !== ")") throw ")"; pos++; return v }
        if (peek() === "-") { pos++; return -atom() }
        if (peek() === "+") { pos++; return atom() }
        return number()
    }
    function power() {
        var b = atom()
        if (peek() === "^") { pos++; return Math.pow(b, power()) }
        return b
    }
    function term() {
        var v = power()
        while (peek() === "*" || peek() === "/" || peek() === "%") {
            var op = s[pos++], r = power()
            v = op === "*" ? v * r : op === "/" ? v / r : v % r
        }
        return v
    }
    function expr() {
        var v = term()
        while (peek() === "+" || peek() === "-") { var op = s[pos++]; var r = term(); v = op === "+" ? v + r : v - r }
        return v
    }
    try {
        var v = expr()
        if (pos !== s.length || !isFinite(v)) return null
        return Math.round(v * 1e10) / 1e10
    } catch (e) {
        return null
    }
}
