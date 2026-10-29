import QtQuick
import QtQuick.Layouts
import Quickshell.Bluetooth
import qs
import qs.components

// One Bluetooth device. Click: connect (paired), pair then trust then connect (new), or expand (connected).
// Trusting and connecting after a pairing is done by BluetoothPanel, not here: the list is rebuilt whenever a device
// property changes, which destroys the row that started the pairing before the pairing finishes.
Rectangle {
    id: row
    required property var modelData              // BluetoothDevice
    signal failed(string text)

    property bool expanded: false
    property bool pairAttempted: false
    readonly property bool busy: modelData.pairing || modelData.state === BluetoothDeviceState.Connecting

    function glyph() {
        const i = modelData.icon
        if (i.indexOf("headset") >= 0 || i.indexOf("headphone") >= 0) return ""
        if (i.indexOf("keyboard") >= 0) return ""
        if (i.indexOf("mouse") >= 0) return ""
        if (i.indexOf("phone") >= 0) return ""
        return ""
    }
    function activate() {
        if (modelData.connected) { expanded = !expanded; return }
        if (modelData.paired) { modelData.connect(); return }
        pairAttempted = true
        modelData.pair()
    }

    Connections {
        target: row.modelData
        function onPairedChanged() { if (row.modelData.paired) row.pairAttempted = false }
        function onPairingChanged() {
            if (!row.modelData.pairing && !row.modelData.paired && row.pairAttempted) settle.restart()
        }
    }
    // BlueZ can clear "Pairing" a moment before it sets "Paired": judge a failure only once the attempt has settled.
    Timer {
        id: settle
        interval: 1500
        onTriggered: {
            if (!row.pairAttempted) return
            if (row.modelData.pairing) return                         // a new attempt started
            row.pairAttempted = false
            if (!row.modelData.paired)
                row.failed("Pairing failed. If the device asks for a PIN, use Advanced (bluetui).")
        }
    }

    width: ListView.view.width
    implicitHeight: col.implicitHeight + 12
    height: implicitHeight
    radius: Theme.controlRadius
    color: modelData.connected ? Theme.inset : "transparent"

    ColumnLayout {
        id: col
        anchors { fill: parent; leftMargin: 12; rightMargin: 12; topMargin: 6; bottomMargin: 6 }   // first line 36 high
        spacing: 6

        Item {
            Layout.fillWidth: true
            implicitHeight: 24
            RowLayout {
                anchors.fill: parent
                spacing: 8
                Txt { text: row.glyph(); color: row.modelData.connected ? Theme.accent : Theme.fg }
                Txt { text: row.modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                Txt {
                    visible: row.modelData.batteryAvailable
                    text: Math.round(row.modelData.battery <= 1 ? row.modelData.battery * 100 : row.modelData.battery) + "%"
                    color: Theme.dim; font.pixelSize: Theme.fontSize - 2
                }
                Txt {
                    text: row.modelData.pairing ? "Pairing…" : row.busy ? "Connecting…" : row.modelData.connected ? "Connected" : row.modelData.paired ? "Paired" : ""
                    color: row.modelData.connected ? Theme.accent : Theme.dim
                    font.pixelSize: Theme.fontSize - 2
                }
                Txt {
                    visible: row.modelData.paired && !row.modelData.connected
                    text: ""; color: Theme.dim
                    MouseArea { anchors.fill: parent; anchors.margins: -4; onClicked: row.modelData.forget() }
                }
            }
            MouseArea { anchors.fill: parent; z: -1; onClicked: row.activate() }
        }

        RowLayout {
            visible: row.expanded && row.modelData.connected
            spacing: 8
            Button { text: "Disconnect"; onClicked: { row.modelData.disconnect(); row.expanded = false } }
            Button { text: "Forget"; tint: Theme.crit; onClicked: { row.modelData.forget(); row.expanded = false } }
        }
    }
}
