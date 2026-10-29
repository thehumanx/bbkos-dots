import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Bluetooth
import qs
import qs.components
import qs.services

// Bluetooth popup. Discovery runs only while this panel exists (it costs battery): on here, off in onDestruction.
ColumnLayout {
    id: root
    spacing: 8
    property string message: ""            // last pairing error, shown until a device pairs or connects

    // Quickshell can start a pairing but cannot answer BlueZ's questions (confirm, authorise): without a pairing agent
    // every pairing hangs on "Connecting...". bluetoothctl registers one ("just works": no PIN or code, which covers
    // earbuds, speakers and phones; keyboards that need a typed PIN go through Advanced). It runs only while this panel
    // is open, so nothing can be paired silently in the background and nothing runs while it is closed. It ends when its
    // stdin closes, so a Quickshell crash cannot leave it behind.
    Process {
        running: Bt.enabled
        stdinEnabled: true
        command: ["bluetoothctl", "--agent", "NoInputNoOutput"]
    }

    // A device paired from here is marked trusted (BlueZ only lets trusted devices reconnect on their own: earbuds
    // after the case lid, everything after a resume) and connected. Lives in the panel, not in a row: rows are rebuilt
    // whenever any device property changes, which happens during pairing.
    Instantiator {
        model: Bluetooth.devices
        delegate: QtObject {
            required property var modelData
            property var conn: Connections {
                target: modelData
                function onConnectedChanged() { if (modelData.connected) root.message = "" }
                function onPairedChanged() {
                    if (!modelData.paired) return
                    root.message = ""
                    if (!modelData.trusted) modelData.trusted = true
                    if (!modelData.connected) modelData.connect()
                }
            }
        }
    }

    // Only when fully Enabled: right after the switch is flipped the adapter is still Enabling and BlueZ refuses
    // StartDiscovery ("Resource Not Ready"), which would leave the list without scanning.
    // Powering off needs no stop request: BlueZ ends discovery itself, and asking during "on-disabling" only logs a
    // second "Resource Not Ready".
    readonly property bool adapterReady: Bt.adapter !== null && Bt.adapter.state === BluetoothAdapterState.Enabled
    function syncDiscovery() { if (adapterReady) Bt.adapter.discovering = true }
    Component.onCompleted: syncDiscovery()
    Component.onDestruction: if (adapterReady) Bt.adapter.discovering = false
    Connections { target: Bt.adapter; function onStateChanged() { root.syncDiscovery() } }

    PopupHeader {
        title: "Bluetooth"
        Toggle { checked: Bt.enabled; enabled: Bt.available && !Bt.blocked; onToggled: on => Bt.setEnabled(on) }
    }

    Txt { visible: !Bt.available; text: "No Bluetooth adapter found"; color: Theme.warn }
    Txt { visible: Bt.blocked; text: "Bluetooth is blocked. Unblock it with: rfkill unblock bluetooth"; color: Theme.warn; wrapMode: Text.Wrap; Layout.fillWidth: true }
    Txt { visible: root.message !== ""; text: root.message; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }

    ListView {
        id: list
        visible: Bt.enabled
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(contentHeight, 320)
        clip: true
        spacing: 2
        model: Bt.devices
        delegate: BluetoothRow { onFailed: text => root.message = text }
    }
    Txt { visible: Bt.enabled && list.count === 0; text: "Searching for devices…"; color: Theme.dim }
    Txt { visible: Bt.available && !Bt.enabled && !Bt.blocked; text: "Bluetooth is off"; color: Theme.dim }

    SettingRow {
        label: "Device wants a PIN or code?"
        labelWidth: 196
        Layout.bottomMargin: -12                                // the card margin already gives the room below
        Item { Layout.fillWidth: true }
        Button { text: "Advanced…"; onClicked: { Quickshell.execDetached(["bbkos-tui", "bluetui"]); PanelState.close() } }
    }
}
