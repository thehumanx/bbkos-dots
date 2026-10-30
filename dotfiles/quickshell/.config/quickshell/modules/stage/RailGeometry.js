.pragma library

// Where the stage rail sits (docs/modules/dock.md). The rail's window spans its whole edge and reserves a fixed thickness;
// the body inside it is full length or hugs its contents, placed at start, centre or end (as Bar.qml places a hugging bar,
// and as end-4's dock does). All lengths are logical pixels; `px` is the step every result is a multiple of (one physical
// pixel in grid mode, so the hairlines stay on whole pixels; 1 otherwise).

function vertical(edge) { return edge === "left" || edge === "right" }

function snap(v, px) { return Math.round(v / px) * px }

// The body's rectangle inside the window. o: {edge, hug, align, float, thickness, windowLength, contentLength, px}.
function body(o) {
    const px = o.px > 0 ? o.px : 1
    const room = Math.max(0, o.windowLength - 2 * o.float)
    const len = o.hug ? Math.min(Math.ceil(o.contentLength / px - 0.001) * px, room) : room
    const start = !o.hug || o.align === "start" ? o.float
                : o.align === "end" ? o.windowLength - o.float - len
                : (o.windowLength - len) / 2
    const across = o.edge === "left" || o.edge === "top" ? o.float : 0
    const a = snap(start, px), l = snap(len, px), c = snap(across, px), t = snap(o.thickness, px)
    return vertical(o.edge) ? { x: c, y: a, width: t, height: l } : { x: a, y: c, width: l, height: t }
}

// The window's top-left on its screen, for the blur strip. o: {edge, screenWidth, screenHeight, windowThickness, barPosition, barInset}.
function windowOrigin(o) {
    const inset = side => o.barPosition === side ? o.barInset : 0
    if (vertical(o.edge))
        return { x: o.edge === "left" ? inset("left") : o.screenWidth - o.windowThickness - inset("right"), y: inset("top") }
    return { x: inset("left"), y: o.edge === "top" ? inset("top") : o.screenHeight - o.windowThickness - inset("bottom") }
}

// The window's margins. o: {edge, reserve, barPosition, barInset, gridPad}. A reserving rail is placed by the compositor inside
// the area the bar leaves free and only keeps gridPad from the bar; one that does not reserve keeps the bar's inset itself.
// Only the side where the bar is, and only when the rail touches that side (its own edge, or the two edges it runs between).
function windowMargins(o) {
    const out = { top: 0, bottom: 0, left: 0, right: 0 }
    const s = o.barPosition
    const touches = s === o.edge || vertical(s) !== vertical(o.edge)
    if (s in out && touches) out[s] = o.reserve ? o.gridPad : o.barInset
    return out
}
