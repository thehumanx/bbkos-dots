import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
import qs
import qs.components
import qs.services

// Short notices for a state change: charger plugged or unplugged, audio output switched, VPN (Tailscale) on or off
// (docs/modules/toast.md; the idea is Caelestia's Toaster). Each watcher is a signal or an event stream that already exists, so
// nothing polls. The window exists only while a toast is shown; a new toast replaces the one on screen. Not kept in the
// notification history: these say what just happened, they are not messages.
Scope {
    id: root
    property string icon: ""
    property string title: ""
    property string text: ""
    property bool shown: false
    property bool ready: false         // skip the values that arrive right after startup

    function on(key: string): bool { return SettingsStore.shown("notifications." + key) !== false }
    function show(i: string, t: string, x: string) { icon = i; title = t; text = x; shown = true; hide.restart() }

    function screenFor() {
        const list = Quickshell.screens
        const n = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
        return list.find(s => s.name === n) ?? list[0]
    }

    Timer { interval: 3000; running: true; onTriggered: root.ready = true }
    Timer { id: hide; interval: 2500; onTriggered: root.shown = false }

    Connections {
        target: Power
        function onPluggedInChanged() {
            if (root.ready && root.on("toastCharger"))
                root.show("", Power.pluggedIn ? "Charger connected" : "Charger unplugged", Power.pluggedIn ? "Charging" : "Running on the battery")
        }
    }

    // The default output changed (headphones plugged, Bluetooth connected, picked in the audio panel).
    property string lastSink: ""
    Connections {
        target: Audio
        function onSinkChanged() {
            const name = Audio.sink ? Audio.label(Audio.sink) : ""
            if (name === "") return
            if (root.ready && root.lastSink !== "" && name !== root.lastSink && root.on("toastAudio"))
                root.show("", "Sound output", "Now using " + name)
            root.lastSink = name
        }
    }

    // Tailscale pushes its state over a local socket: one line per change, nothing while it stays the same. State 6 is Running.
    property int vpnState: -1
    Process {
        running: true
        command: ["tailscale", "debug", "watch-ipn", "-initial"]
        stdout: SplitParser {
            onRead: line => {
                const m = line.match(/^\t"State": (\d+),?$/)
                if (!m) return
                const up = Number(m[1]) === 6
                const was = root.vpnState === 6
                if (root.ready && root.vpnState !== -1 && up !== was && root.on("toastVpn"))
                    root.show("", up ? "VPN connected" : "VPN disconnected", "Tailscale")
                root.vpnState = Number(m[1])
            }
        }
    }

    IpcHandler {
        target: "toast"
        function notify(title: string, text: string): void { root.show("", title, text) }
    }

    LazyLoader {
        active: root.shown

        PanelWindow {
            screen: root.screenFor()
            anchors { bottom: true }
            // Above the volume/brightness OSD (80 up, 52 high), with a gap. The window is larger than the card by
            // Theme.shadowPad on each side, room for the card's shadow.
            margins { bottom: 144 - Theme.shadowPad + (Theme.barEdge === "bottom" ? Theme.barInset : 0) }
            implicitWidth: 320 + 2 * Theme.shadowPad
            implicitHeight: 56 + 2 * Theme.shadowPad
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "bbkos-toast"
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

                    Txt { text: root.icon; color: Theme.accent; font.pixelSize: Theme.fontSize + 4; Layout.preferredWidth: 22; horizontalAlignment: Text.AlignHCenter }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Txt { text: root.title; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                        Txt { text: root.text; color: Theme.dim; font.pixelSize: Theme.fontSize - 1; elide: Text.ElideRight; Layout.fillWidth: true }
                    }
                }
            }
        }
    }
}
