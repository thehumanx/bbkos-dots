pragma Singleton
import Quickshell
import Quickshell.Hyprland

// Which popup panel is open ("", "wifi", "bluetooth", "audio", "power", "display", "battery", "notifications", "record", "calendar" or "timer")
// and on which screen. The bar widgets toggle it (each passes the name of its own screen), modules/panels shows it.
// screen "" means the screen with the focus (the power key and IPC have no screen of their own).
Singleton {
    property string open: ""
    property string screen: ""
    // Where the opening widget sits along the bar, in screen pixels; the card centres on it. -1 (power key, IPC): no
    // widget, the card sits in the corner at the bar's end.
    property real anchor: -1
    // The same panel from the same screen closes it; from another screen it moves there.
    function toggle(which: string, screenName: var, along: var) {
        const sc = typeof screenName === "string" ? screenName : ""
        if (open === which && (sc === "" || sc === screen)) { open = ""; return }
        screen = sc
        anchor = typeof along === "number" && isFinite(along) ? along : -1
        open = which
    }
    function close() { open = "" }
    // Whether panel `which` is open on the screen named `screenName`: the bar widget that opened it lights up. A panel
    // opened with no screen (power key, IPC) shows on the focused monitor, so it matches that one.
    function isOn(which: string, screenName: string): bool {
        if (open !== which) return false
        if (screen !== "") return screen === screenName
        const f = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
        return f === "" || f === screenName
    }
}
