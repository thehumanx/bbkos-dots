.pragma library

// Pure helpers for the workspace overview (modules/overview). They take Hyprland IPC objects (the `lastIpcObject`
// of a HyprlandToplevel or monitor) and return plain data, so the layout can be reasoned about without a window.
// Geometry: Hyprland reports monitor width/height in physical pixels but client at/size in logical ones, hence the
// scale division in monitorFrame(). `at` is in the global layout, so the monitor's x/y is subtracted.

var ADDRESS = /^0x[0-9a-f]{1,16}$/

function normalizeAddress(value) {
    var text = String(value === undefined || value === null ? "" : value).toLowerCase()
    if (text === "") return ""
    if (text.indexOf("0x") !== 0) text = "0x" + text
    return ADDRESS.test(text) ? text : ""
}

function isWorkspaceId(value) {
    var id = Number(value)
    return isFinite(id) && Math.floor(id) === id && id >= 1
}

function monitorFrame(monitor) {
    if (!monitor) return null
    var scale = Number(monitor.scale)
    if (!(scale > 0)) scale = 1
    var width = Number(monitor.width) / scale
    var height = Number(monitor.height) / scale
    if (!(width > 0) || !(height > 0)) return null
    return { x: Number(monitor.x) || 0, y: Number(monitor.y) || 0, width: width, height: height }
}

function clamp01(value) {
    if (!isFinite(value)) return 0
    return value < 0 ? 0 : (value > 1 ? 1 : value)
}

// Linear interpolation, t clamped to [0, 1]. Used by the open animation that brings a window card in from its real
// screen rectangle.
function mix(a, b, t) {
    if (!isFinite(t)) return b
    return a + (b - a) * (t < 0 ? 0 : (t > 1 ? 1 : t))
}

// A window card's start rectangle for the open animation, in the overlay surface's logical coordinates: the client
// geometry (fractions of the monitor frame) mapped back into screen pixels and offset by where the surface begins
// (the bar edge it is inset by, given in logical px). Null when it cannot be placed.
function surfaceRect(entry, monitor, offX, offY) {
    if (!entry || !entry.rect || !monitor) return null
    var frame = monitorFrame(monitor)
    if (!frame) return null
    var x = frame.x + entry.rect.x * frame.width - (offX || 0)
    var y = frame.y + entry.rect.y * frame.height - (offY || 0)
    return { x: x, y: y, width: entry.rect.width * frame.width, height: entry.rect.height * frame.height }
}

// Window rectangle as fractions of the monitor frame, clamped to it. Null when it cannot be placed (unmapped,
// no geometry, or entirely off-screen).
function windowRect(ipc, frame) {
    if (!ipc || !frame) return null
    var at = ipc.at
    var size = ipc.size
    if (!at || !size || at.length < 2 || size.length < 2) return null
    var left = clamp01((Number(at[0]) - frame.x) / frame.width)
    var top = clamp01((Number(at[1]) - frame.y) / frame.height)
    var right = clamp01((Number(at[0]) + Number(size[0]) - frame.x) / frame.width)
    var bottom = clamp01((Number(at[1]) + Number(size[1]) - frame.y) / frame.height)
    if (!(right > left) || !(bottom > top)) return null
    return { x: left, y: top, width: right - left, height: bottom - top }
}

// Windows of one HyprlandWorkspace, in draw order: tiled first, then floating, and within each group the most
// recently focused last (so it draws on top). Each entry carries the fractions and the HyprlandToplevel for capture.
function windowsOf(workspace, frame) {
    var out = []
    if (!workspace || !workspace.toplevels || !frame) return out
    var values = workspace.toplevels.values || []
    for (var i = 0; i < values.length; i++) {
        var top = values[i]
        var ipc = top ? top.lastIpcObject : null
        if (!ipc || ipc.mapped === false || ipc.hidden === true) continue
        var rect = windowRect(ipc, frame)
        var address = normalizeAddress(ipc.address)
        if (!rect || address === "") continue
        var focus = Number(ipc.focusHistoryID)
        out.push({
            address: address,
            addressIpc: address,
            appId: String(ipc["class"] || ""),
            title: String(top.title || ipc.title || ""),
            floating: ipc.floating === true,
            focus: isFinite(focus) ? focus : 1e6,
            workspaceId: ipc.workspace ? Number(ipc.workspace.id) : Number(workspace.id),
            rect: rect,
            toplevel: top
        })
    }
    out.sort(function (left, right) {
        if (left.floating !== right.floating) return left.floating ? 1 : -1
        return right.focus - left.focus
    })
    return out
}
