import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
import qs
import qs.components
import qs.services
import "../notifications"

// Popup host for the Wi-Fi, Bluetooth, audio, power, display, battery, calendar, timer, record and notification-history panels. The windows
// (and everything in them, including the scanner) exist only while a panel is open. Click anywhere, on any screen, or Esc closes it.
Scope {
    id: root

    IpcHandler {
        target: "panel"
        function toggle(which: string): void { PanelState.toggle(which, "") }
        function toggleOn(which: string, screenName: string): void { PanelState.toggle(which, screenName) }   // test hook: open on a named screen
        function toggleAt(which: string, screenName: string, along: real): void { PanelState.toggle(which, screenName, along) }   // test hook: as if the widget at `along` px was clicked
        function close(): void { PanelState.close() }
        function status(): string {                      // test hook: what is open, and whether scanning is on
            return JSON.stringify({
                open: PanelState.open, shown: root.shown, leaving: root.leaving, screen: root.targetName, anchor: PanelState.anchor,
                wifiScanning: Net.wifi ? Net.wifi.scannerEnabled : null,
                btDiscovering: Bt.adapter ? Bt.adapter.discovering : null
            })
        }
    }

    IpcHandler {                                         // test hooks for the display service (docs/modules/displays.md)
        target: "display"
        function status(): string {
            return JSON.stringify({ monitors: Displays.monitors, layout: Displays.layout, pending: Displays.pending,
                                    brightness: Displays.brightness, brightnessError: Displays.brightnessError,
                                    status: Displays.status,
                                    keepSeconds: Displays.keepSeconds, runs: Displays.runs })
        }
        function refresh(): void { Displays.refresh() }
        // Called by the Hyprland hooks (hyprland.lua) when a monitor is added, removed or moved: Quickshell keeps its own copy
        // of every monitor's x/y and of every window's global position, and none of Hyprland's socket events announces a move.
        function monitorsChanged(): void {
            Hyprland.refreshMonitors()
            Hyprland.refreshWorkspaces()
            Hyprland.refreshToplevels()
            Displays.refresh()                 // the monitor list behind the display panel and the brightness widget
        }
        function refreshBrightness(name: string): void { Displays.refreshBrightness(name) }
        function setBrightness(name: string, percent: int): void { Displays.setBrightness(name, percent) }
        function setScale(name: string, scale: string): void { Displays.setScale(name, parseFloat(scale)) }
        function setMode(name: string, mode: string): void { Displays.setMode(name, mode) }
        function setLayout(mode: string, primary: string, position: string): void { Displays.setLayout(mode, primary, position) }
        function keep(): void { Displays.keep() }
        function revert(): void { Displays.revert() }
    }

    // The screen that shows the card: the one the widget was clicked on, else the focused one, else the first.
    readonly property string targetName: {
        const names = Quickshell.screens.map(sc => sc.name)
        if (PanelState.screen !== "" && names.includes(PanelState.screen)) return PanelState.screen
        const f = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
        return names.includes(f) ? f : (names.length > 0 ? names[0] : "")
    }

    // The panel on screen. It follows PanelState.open, but on close it keeps the last name for Theme.durExit, so the
    // card can shrink and fade out before the windows go (docs/modules/motion.md). While `leaving`, the overlay lets
    // clicks and keys through, so a click on another widget is not swallowed by a popup that is already going.
    property string shown: ""
    property bool leaving: false
    Connections {
        target: PanelState
        function onOpenChanged() {
            if (PanelState.open !== "") { leave.stop(); root.leaving = false; root.shown = PanelState.open }
            else if (root.shown !== "") { root.leaving = true; leave.restart() }
        }
    }
    Timer { id: leave; interval: Theme.durExit + 20; onTriggered: { root.leaving = false; root.shown = "" } }

    // One full-screen overlay per screen while a panel is open, so a click on ANY screen closes it. Only the target
    // screen shows the card, takes the keyboard and builds the panel (a second copy would start a second scanner).
    Variants {
        model: Quickshell.screens

        LazyLoader {
            id: loader
            required property var modelData
            active: root.shown !== ""

            PanelWindow {
                id: win
                readonly property bool target: loader.modelData.name === root.targetName
                readonly property bool sheet: root.shown === "notifications"    // full-height right-hand panel
                readonly property int sheetTop: Theme.barEdge === "top" ? Theme.barInset + 6 : Theme.gap
                readonly property int sheetBottom: Theme.barEdge === "bottom" ? Theme.barInset + 6 : Theme.gap
                screen: loader.modelData
                anchors { top: true; bottom: true; left: true; right: true }
                exclusionMode: ExclusionMode.Ignore
                WlrLayershell.layer: WlrLayer.Overlay
                // Exclusive on EVERY screen's overlay, not just the target: while one exclusive layer exists Hyprland sends
                // pointer events to exclusive layers only, so a non-exclusive overlay on another screen never saw a click
                // (measured: no enter/press at all on the second monitor). Keyboard focus follows the pointer between them.
                WlrLayershell.keyboardFocus: root.leaving ? WlrKeyboardFocus.None : WlrKeyboardFocus.Exclusive
                WlrLayershell.namespace: "bbkos-panel"
                color: "transparent"
                mask: root.leaving ? passThrough : null
                Region { id: passThrough }                // empty input region: clicks go to what is below

                Shortcut { sequence: "Escape"; onActivated: PanelState.close() }
                MouseArea { anchors.fill: parent; onClicked: PanelState.close() }

                Rectangle {
                    id: card
                    visible: win.target
                    width: win.sheet ? 380 : 360
                    height: win.sheet ? parent.height - win.sheetTop - win.sheetBottom
                                      : Math.min(body.item ? body.item.implicitHeight + 40 : 100, parent.height - (Theme.barVertical ? 0 : Theme.barInset) - 24)
                    // The notification history is a side sheet on the right, whatever edge the bar is on. Every other
                    // panel opens at the widget that was clicked: centred on it along the bar and just clear of the bar
                    // (Theme.barEdge / barInset), kept inside the screen by a gap. Opened without a widget (power key,
                    // IPC: PanelState.anchor < 0) it sits in the corner at the bar's end: top bar -> top right,
                    // bottom bar -> bottom right, left bar -> top left, right bar -> top right.
                    readonly property real edge: Theme.barInset + 6
                    readonly property bool anchored: PanelState.anchor >= 0
                    function along(size: real, limit: real): real {      // the card's start along the bar, clamped on screen
                        return Math.max(Theme.gap, Math.min(PanelState.anchor - size / 2, limit - size - Theme.gap))
                    }
                    x: win.sheet || Theme.barEdge === "right" ? (win.sheet ? parent.width - width - Theme.gap : parent.width - width - edge)
                       : Theme.barEdge === "left" ? edge
                       : anchored ? along(width, parent.width) : parent.width - width - Theme.gap
                    y: win.sheet ? win.sheetTop
                       : Theme.barEdge === "top" ? edge
                       : Theme.barEdge === "bottom" ? parent.height - height - edge
                       : anchored ? along(height, parent.height) : Theme.gap
                    radius: Theme.radius
                    color: Theme.popupBg
                    border.width: Theme.hair
                    border.color: Theme.cardEdge

                    // Enter and exit (docs/modules/motion.md): fade with a slight grow from 96% (never from nothing), out
                    // of the point nearest the widget that opened it, with the strong ease-out; leaving is quicker.
                    // Reduce motion keeps the fade only. The Behavior makes it interruptible: a fast reopen reverses it.
                    property bool ready: false
                    Component.onCompleted: ready = true
                    property real p: ready && !root.leaving ? 1 : 0
                    Behavior on p {
                        NumberAnimation {
                            duration: root.leaving ? Theme.durExit : Theme.durEnter
                            easing.type: Easing.BezierSpline
                            easing.bezierCurve: Theme.easeOut
                        }
                    }
                    opacity: p
                    transform: Scale {
                        readonly property real s: Theme.reduceMotion ? 1 : 0.96 + 0.04 * card.p
                        xScale: s
                        yScale: s
                        // The edge that faces the bar, at the widget's position along it (the corner at the bar's end
                        // when there is no widget; the top right for the notification sheet).
                        origin.x: win.sheet || Theme.barEdge === "right" ? card.width
                                  : Theme.barEdge === "left" ? 0
                                  : card.anchored ? Math.max(0, Math.min(card.width, PanelState.anchor - card.x)) : card.width
                        origin.y: win.sheet ? 0
                                  : Theme.barEdge === "top" ? 0
                                  : Theme.barEdge === "bottom" ? card.height
                                  : card.anchored ? Math.max(0, Math.min(card.height, PanelState.anchor - card.y)) : 0
                    }

                    CardShadow {}
                    MouseArea { anchors.fill: parent }          // swallow clicks inside the card

                    Loader {
                        id: body
                        active: win.target
                        anchors { fill: parent; margins: 20 }        // the settings card's inner margin
                        sourceComponent: root.shown === "wifi" ? wifi : root.shown === "bluetooth" ? bluetooth : root.shown === "audio" ? audio : root.shown === "power" ? power : root.shown === "display" ? display : root.shown === "battery" ? battery : root.shown === "notifications" ? notifications : root.shown === "record" ? record : root.shown === "calendar" ? calendar : root.shown === "timer" ? timer : null   // never a default: closing would briefly build (and start scanning in) another panel
                    }
                    Component { id: wifi; WifiPanel {} }
                    Component { id: bluetooth; BluetoothPanel {} }
                    Component { id: audio; AudioPanel {} }
                    Component { id: power; PowerPanel {} }
                    Component { id: display; DisplayPanel {} }
                    Component { id: battery; BatteryPanel {} }
                    Component { id: notifications; NotificationHistoryPanel {} }
                    Component { id: record; RecordPanel {} }
                    Component { id: calendar; CalendarPanel {} }
                    Component { id: timer; TimerPanel {} }
                }
            }
        }
    }
}
