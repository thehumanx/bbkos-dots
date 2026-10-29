import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components

// Network page (docs/modules/network.md): Wi-Fi on or off, the saved connections (switch auto-connect, forget), Tailscale on
// or off and the phone mirror. Read and written by `bbkos-network` (nmcli); the page shows what the tool says after each change and keeps
// no copy. The Wi-Fi and Bluetooth popups in the bar are the quick version of this.
SettingsPage {
    id: page
    note: ""

    property var info: ({ wifi: true, connections: [], tailscale: null, mirror: null })
    property string error: ""
    property string confirming: ""                       // the connection whose Forget was clicked once (second click within 4 s)

    function refresh() { if (!statusProc.running) statusProc.running = true }
    function run(args) { if (!actProc.running) { actProc.command = ["bbkos-network"].concat(args); actProc.running = true } }
    Component.onCompleted: refresh()

    Process {
        id: statusProc
        command: ["bbkos-network", "status"]
        stdout: StdioCollector {
            onStreamFinished: { try { page.info = JSON.parse(text); page.error = "" } catch (e) { page.error = "Could not read the network state" } }
        }
    }
    Process {
        id: actProc
        stderr: StdioCollector { id: actErr }
        onExited: code => { page.error = code === 0 ? "" : (actErr.text.trim() || "Could not change the network"); page.refresh() }
    }
    Process {
        id: mirrorProc
        onExited: page.refresh()
    }
    Timer { id: confirmTimer; interval: 4000; onTriggered: page.confirming = "" }

    SettingsSection {
        title: "Wi-Fi"
        SettingRow {
            label: "Wi-Fi"
            Item { Layout.fillWidth: true }
            Toggle { checked: page.info.wifi; onToggled: on => page.run(["wifi", on ? "on" : "off"]) }
        }
    }
    SettingsSection {
        title: "Saved connections"
        Txt { visible: page.info.connections.length === 0; text: "No saved connections."; color: Theme.dim; Layout.margins: 14 }
        Repeater {
            model: page.info.connections
            delegate: SettingRow {
                required property var modelData
                label: modelData.name
                hint: modelData.kind + (modelData.active ? ", connected" : "")
                Item { Layout.fillWidth: true }
                Txt { text: "Connect automatically"; color: Theme.dim; font.pixelSize: Theme.fontSize - 1 }
                Toggle { checked: modelData.autoconnect; onToggled: on => page.run(["autoconnect", modelData.name, on ? "yes" : "no"]) }
                Button {
                    text: page.confirming === modelData.name ? "Really forget?" : "Forget"
                    tint: page.confirming === modelData.name ? Theme.crit : Theme.fg
                    onClicked: {
                        if (page.confirming === modelData.name) { page.confirming = ""; page.run(["forget", modelData.name]) }
                        else { page.confirming = modelData.name; confirmTimer.restart() }
                    }
                }
            }
        }
    }
    SettingsSection {
        title: "Tailscale"
        SettingRow {
            id: tsRow
            readonly property var ts: page.info.tailscale
            readonly property bool running: ts !== null && ts.state === "Running"
            label: ts === null ? "Not installed" : running ? "Connected" : ts.state === "Stopped" ? "Off" : ts.state
            // Off is kept across reboots by tailscaled. Without operator rights the switch is greyed and says how to get them.
            hint: ts === null ? "" : !ts.operator ? "To switch it here, run once in a terminal: sudo tailscale set --operator=$USER"
                  : running ? ts.address + ", " + ts.peers + " other device" + (ts.peers === 1 ? "" : "s") + ". Stays as you leave it after a restart"
                  : "Stays off after a restart until you switch it on"
            Item { Layout.fillWidth: true }
            Toggle {
                visible: tsRow.ts !== null
                enabled: tsRow.ts !== null && tsRow.ts.operator && !actProc.running
                checked: tsRow.running
                onToggled: on => page.run(["tailscale", on ? "on" : "off"])
            }
        }
    }
    SettingsSection {
        title: "Phone mirror"
        SettingRow {
            label: "Show this screen on the phone"
            hint: page.info.mirror === null ? "bbkos-mirror is not installed"
                  : "Over Tailscale only, with a password. " + page.info.mirror.address + (page.info.mirror.state.startsWith("on") ? ", " + page.info.mirror.state : "")
            Item { Layout.fillWidth: true }
            Button {
                visible: page.info.mirror !== null && page.info.mirror.state.startsWith("on")
                text: "Copy password"
                onClicked: Quickshell.execDetached(["sh", "-c", "bbkos-mirror password | wl-copy"])
            }
            Toggle {
                enabled: page.info.mirror !== null && page.info.tailscale !== null && page.info.tailscale.state === "Running"
                checked: page.info.mirror !== null && page.info.mirror.state.startsWith("on")
                onToggled: on => { mirrorProc.command = ["bbkos-mirror", on ? "on" : "off"]; mirrorProc.running = true }
            }
        }
    }
    Txt { visible: page.error !== ""; text: page.error; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }
}
