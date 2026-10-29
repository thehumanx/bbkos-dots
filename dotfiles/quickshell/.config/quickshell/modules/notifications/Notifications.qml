import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs
import qs.services

// Popup stack in the corner at the bar's end side (top right for a top bar). The window exists only while a notification is on screen.
// Also the test hook for the history behind the bar's notification widget and the notification panel.
Scope {
    IpcHandler {
        target: "notifications"
        function status(): string {
            return JSON.stringify({
                tracked: Notifs.count, dnd: Notifs.dnd, unread: Notifs.unread, history: Notifs.history.length, cap: Notifs.cap,
                entries: Notifs.history.map(e => ({ key: e.key, notifId: e.notifId, app: e.appName,
                                                    summary: e.summary, read: e.read, urgency: e.urgency, time: e.time }))
            })
        }
        function markAllRead(): void { Notifs.markAllRead() }
        function clear(): void { Notifs.clearAll() }
        function dismiss(key: int): void { Notifs.remove(key) }
        function dnd(on: bool): void { Notifs.setDnd(on) }                                   // test hook: the panel's Do not disturb switch
        function invoke(notifId: int): bool { return Notifs.invokeDefault(notifId) }       // test hook: only the default action
        function click(notifId: int, left: bool): void { Notifs.activate(notifId, left) }  // test hook: a click on the popup
    }

    LazyLoader {
        active: Notifs.count > 0 && !Notifs.dnd    // do not disturb: history only, no popup

        PanelWindow {
            id: win
            // Same corner rule as the panels: the bar's end side, clear of the bar.
            // notifications.position: "auto" is the corner on the bar's end side, else one of the four corners.
            readonly property string corner: Notifs.cfg.position ?? "auto"
            readonly property bool atBottom: corner === "auto" ? Theme.barEdge === "bottom" : corner.startsWith("bottom")
            readonly property bool atLeft: corner === "auto" ? Theme.barEdge === "left" : corner.endsWith("left")
            anchors {
                top: !win.atBottom
                bottom: win.atBottom
                right: !win.atLeft
                left: win.atLeft
            }
            // Where the cards sit (as before), and the room kept around them for their shadows: up to Theme.shadowPad,
            // taken out of the margin on an anchored side (never below 0) and added freely on the open sides.
            readonly property int mTop: Theme.barEdge === "top" ? Theme.barInset + 8 : Theme.gap
            readonly property int mBottom: Theme.barEdge === "bottom" ? Theme.barInset + 8 : Theme.gap
            readonly property int mRight: Theme.barEdge === "right" ? Theme.barInset + 8 : Theme.gap
            readonly property int mLeft: Theme.barEdge === "left" ? Theme.barInset + 8 : Theme.gap
            readonly property int padTop: !win.atBottom ? Math.min(Theme.shadowPad, mTop) : Theme.shadowPad
            readonly property int padBottom: win.atBottom ? Math.min(Theme.shadowPad, mBottom) : Theme.shadowPad
            readonly property int padLeft: win.atLeft ? Math.min(Theme.shadowPad, mLeft) : Theme.shadowPad
            readonly property int padRight: !win.atLeft ? Math.min(Theme.shadowPad, mRight) : Theme.shadowPad
            margins {
                top: win.mTop - win.padTop
                bottom: win.mBottom - win.padBottom
                right: win.mRight - win.padRight
                left: win.mLeft - win.padLeft
            }
            implicitWidth: 360 + padLeft + padRight
            implicitHeight: stack.implicitHeight + padTop + padBottom
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "bbkos-notifications"
            color: "transparent"

            ColumnLayout {
                id: stack
                x: win.padLeft
                y: win.padTop
                width: 360
                spacing: 8

                Repeater {
                    model: Notifs.server.trackedNotifications
                    // Show only the newest few (notifications.maxPopups, 5): an app spamming notifications must not cover the screen.
                    delegate: NotificationCard { visible: index >= Notifs.count - (Notifs.cfg.maxPopups ?? 5); popupAtLeft: win.atLeft }
                }
            }
        }
    }
}
