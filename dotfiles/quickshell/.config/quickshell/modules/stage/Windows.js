.pragma library

// Pure helpers for the stage rail (Stage.qml), first written for the workspace overview (removed 2026-10-31). They take
// Hyprland IPC objects (the `lastIpcObject` of a HyprlandToplevel or monitor) and return plain data.
// Geometry: Hyprland reports monitor width/height in physical pixels but client at/size in logical ones, hence the
// scale division in monitorFrame(). `at` is in the global layout, so the monitor's x/y is subtracted.

var ADDRESS = /^0x[0-9a-f]{1,16}$/

function normalizeAddress(value) {
    var text = String(value === undefined || value === null ? "" : value).toLowerCase()
    if (text === "") return ""
    if (text.indexOf("0x") !== 0) text = "0x" + text
    return ADDRESS.test(text) ? text : ""
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
