.pragma library

// Text for the Display popup, with units as in the settings window: "1920 × 1200 · 60 Hz · 1.07×".
// Tested under node by tests/calendar/test_display_text.py.

// A scale factor with at most two decimals and no trailing zeros: 1.0666667 -> "1.07×", 1 -> "1×"; "" when not known.
function scaleLabel(s) {
    if (s === null || s === undefined || !isFinite(Number(s))) return ""
    return Number(Number(s).toFixed(2)) + "×"
}

// Hyprland's mode text ("1920x1200@60.00") and the scale as one line; an unparsed mode is kept as it is.
function modeLine(mode, scale) {
    const m = /^(\d+)x(\d+)@([\d.]+)$/.exec(mode || "")
    const head = m ? m[1] + " × " + m[2] + " · " + Math.round(Number(m[3])) + " Hz" : (mode || "")
    const sc = scaleLabel(scale)
    return head !== "" && sc !== "" ? head + " · " + sc : head + sc
}
