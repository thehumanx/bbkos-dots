import QtQuick
import QtQuick.Layouts
import Quickshell.Networking
import qs
import qs.components

// One Wi-Fi network. Click: connect (saved or open), ask for the password (new secured), or expand (connected).
// A new secured network is NOT touched until a password is entered, so the current connection is not dropped
// by a click that is then abandoned.
Rectangle {
    id: row
    required property var modelData              // WifiNetwork
    signal failed(string text)
    signal prompt(bool open)                  // true while the password prompt is open (the list must not re-sort)

    property bool expanded: false
    property bool asking: false
    property bool wasKnown: false
    readonly property bool secured: modelData.security !== WifiSecurityType.Open
    readonly property bool busy: modelData.state === ConnectionState.Connecting

    onAskingChanged: prompt(asking)
    Component.onDestruction: if (asking) prompt(false)

    function reasonText(r) {
        switch (r) {
        case ConnectionFailReason.NoSecrets:        return "Wrong or missing password"
        case ConnectionFailReason.WifiAuthTimeout:  return "Authentication timed out"
        case ConnectionFailReason.WifiNetworkLost:  return "Network went out of range"
        default:                                    return "Could not connect"
        }
    }
    function activate() {
        if (modelData.connected) { expanded = !expanded; return }
        wasKnown = modelData.known
        if (modelData.known || !secured) modelData.connect()
        else asking = true
    }
    function submit() {
        wasKnown = false
        modelData.connectWithPsk(pw.text)
        pw.text = ""                              // never keep the password around
        asking = false
    }

    Connections {
        target: row.modelData
        function onRequestConnectWithPsk() { row.asking = true }
        function onConnectionFailed(reason) {
            if (reason !== ConnectionFailReason.NoSecrets) { row.failed(row.reasonText(reason)); return }
            // NetworkManager passes through need-auth ("secrets are required") even for a saved network whose secrets
            // exist, then connects (journal 2026-10-26). Judge it only once the attempt has settled.
            settle.restart()
        }
        function onConnectedChanged() { if (row.modelData.connected) { settle.stop(); row.asking = false } }
    }
    Timer {
        id: settle
        interval: 1500
        onTriggered: {
            if (row.busy) { restart(); return }                       // still trying: no verdict yet
            if (row.modelData.connected) return                       // it worked: nothing to report
            row.failed(row.reasonText(ConnectionFailReason.NoSecrets))
            if (!row.wasKnown) row.modelData.forget()                 // a profile saved with a wrong password would retry forever
            row.asking = true
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
                Txt { text: ""; color: Theme.fg; opacity: 0.35 + 0.65 * row.modelData.signalStrength }
                Txt { text: row.modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                Txt { text: ""; visible: row.secured; color: Theme.dim; font.pixelSize: Theme.fontSize - 2 }
                Txt {
                    text: row.busy ? "Connecting…" : row.modelData.connected ? "Connected" : row.modelData.known ? "Saved" : ""
                    color: row.modelData.connected ? Theme.accent : Theme.dim
                    font.pixelSize: Theme.fontSize - 2
                }
                Txt {                                    // forget a saved network that is not the current one
                    visible: row.modelData.known && !row.modelData.connected
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

        RowLayout {
            visible: row.asking
            spacing: 8
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 30
                radius: Theme.controlRadius
                color: Theme.inset
                TextInput {
                    id: pw
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    verticalAlignment: TextInput.AlignVCenter
                    echoMode: reveal.checked ? TextInput.Normal : TextInput.Password
                    color: Theme.fg
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSize
                    Keys.onReturnPressed: row.submit()
                    Keys.onEscapePressed: { text = ""; row.asking = false }
                    onVisibleChanged: if (visible) forceActiveFocus()
                }
                Txt { text: "Password"; color: Theme.dim; visible: pw.text === ""; anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter } }
            }
            Rectangle {                                  // show / hide the password
                id: reveal
                property bool checked: false
                implicitWidth: 28; implicitHeight: 28; radius: Theme.controlRadius; color: "transparent"
                Txt { anchors.centerIn: parent; text: reveal.checked ? "" : ""; color: Theme.dim }
                MouseArea { anchors.fill: parent; onClicked: reveal.checked = !reveal.checked }
            }
            Button { text: "Join"; tint: Theme.accent; enabled: pw.text.length >= 8 && pw.text.length <= 64; onClicked: row.submit() }
            Button { text: "Cancel"; onClicked: { pw.text = ""; row.asking = false } }
        }
    }
}
