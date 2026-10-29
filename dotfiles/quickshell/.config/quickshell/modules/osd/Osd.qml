import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
import qs
import qs.components
import qs.services

// Volume / brightness indicator. Volume reacts to PipeWire changes; brightness is pushed by
// `bbkos-brightness` over IPC (the backlight has no change events). The window exists only
// while shown, about 1.5 s after the last change.
Scope {
    id: root
    property string kind: "volume"     // "volume" | "brightness"
    property real level: 0             // 0-1
    property bool muted: false
    property bool shown: false
    property bool ready: false         // skip the initial values that arrive right after startup
    property string screenName: ""     // where it is shown: "" = the focused monitor

    function show(k, l, m, sc) { kind = k; level = l; muted = m; screenName = typeof sc === "string" ? sc : ""; shown = true; hide.restart() }

    // The named screen, else the focused one, else the first.
    function screenFor(name) {
        const list = Quickshell.screens
        const n = name !== "" ? name : (Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        return list.find(s => s.name === n) ?? list[0]
    }

    Timer { interval: 2000; running: true; onTriggered: root.ready = true }
    Timer { id: hide; interval: 1500; onTriggered: root.shown = false }

    Connections {
        target: Displays
        function onBrightnessSet(name, percent) { if (root.ready) root.show("brightness", percent / 100, false, name) }
    }

    Connections {
        target: Audio
        function onVolumeChanged() { if (root.ready) root.show("volume", Audio.volume, Audio.muted) }
        function onMutedChanged() { if (root.ready) root.show("volume", Audio.volume, Audio.muted) }
    }

    IpcHandler {
        target: "osd"
        function brightness(percent: int): void { root.show("brightness", percent / 100, false, "") }
        // bbkos-brightness: the bar appears on the monitor whose brightness changed (the one under the pointer)
        function brightnessOn(percent: int, screen: string): void { root.show("brightness", percent / 100, false, screen) }
    }

    LazyLoader {
        active: root.shown

        PanelWindow {
            screen: root.screenFor(root.screenName)
            anchors { bottom: true }
            // The window is larger than the card by Theme.shadowPad on each side, room for the card's shadow.
            margins { bottom: 80 - Theme.shadowPad + (Theme.barEdge === "bottom" ? Theme.barInset : 0) }
            implicitWidth: 260 + 2 * Theme.shadowPad
            implicitHeight: 52 + 2 * Theme.shadowPad
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "bbkos-osd"
            color: "transparent"
            mask: Region {}            // empty input region: clicks pass through

            Rectangle {
                anchors { fill: parent; margins: Theme.shadowPad }
                radius: Theme.radius
                color: Theme.popupBg
                border.width: Theme.hair
                border.color: Theme.cardEdge

                CardShadow {}

                RowLayout {
                    anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                    spacing: 12

                    Txt {
                        text: root.kind === "brightness" ? "" : (root.muted ? "" : root.level < 0.33 ? "" : "")
                        color: root.muted ? Theme.dim : Theme.fg
                        font.pixelSize: Theme.fontSize + 4
                        Layout.preferredWidth: 22
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 8
                        radius: Theme.gridSquare ? 0 : 4
                        color: Theme.inset
                        Rectangle {
                            width: parent.width * Math.max(0, Math.min(1, root.muted ? 0 : root.level))
                            height: parent.height
                            radius: parent.radius
                            color: Theme.accent
                        }
                    }
                    Txt { text: Math.round((root.muted ? 0 : root.level) * 100) + "%"; Layout.preferredWidth: 40; horizontalAlignment: Text.AlignRight }
                }
            }
        }
    }
}
