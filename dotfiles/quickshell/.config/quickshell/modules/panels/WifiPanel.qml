import QtQuick
import QtQuick.Layouts
import Quickshell
import qs
import qs.components
import qs.services

// Wi-Fi popup. Scanning runs only while this panel exists (it costs battery): switched on here, off again in
// onDestruction. (A Binding did not restore the value when its window was unloaded: tested, it leaked.)
ColumnLayout {
    id: root
    spacing: 8

    property string message: ""            // last connection error, shown until the next attempt or a successful connection
    property int prompts: 0                // open password prompts: the list is frozen while > 0
    property var rows: []


    // Re-sort only when networks appear or disappear, or the connection changes: never on signal-strength ticks, and
    // never while a password prompt is open (rebuilding the list would wipe what the user is typing).
    function resort() {
        if (prompts > 0 || !Net.wifi) return
        rows = Net.wifi.networks.values.slice().sort((a, b) =>
            (b.connected - a.connected) || (b.known - a.known) || (b.signalStrength - a.signalStrength))
    }
    Component.onCompleted: { resort(); if (Net.wifi) Net.wifi.scannerEnabled = true }
    Component.onDestruction: if (Net.wifi) Net.wifi.scannerEnabled = false
    onPromptsChanged: if (prompts === 0) resort()
    Connections { target: Net.wifi ? Net.wifi.networks : null; function onValuesChanged() { root.resort() } }
    Connections { target: Net; function onSsidChanged() { root.resort(); if (Net.ssid !== "") root.message = "" } function onWifiEnabledChanged() { root.resort() } }

    PopupHeader {
        title: "Wi-Fi"
        Toggle { checked: Net.wifiEnabled; enabled: !Net.hardwareBlocked; onToggled: on => Net.setWifiEnabled(on) }
    }

    Txt { visible: Net.hardwareBlocked; text: "Wi-Fi is switched off by the hardware switch"; color: Theme.warn; wrapMode: Text.Wrap; Layout.fillWidth: true }

    Rectangle {                                              // captive portal: sign in
        visible: Net.portal
        Layout.fillWidth: true
        implicitHeight: portalRow.implicitHeight + 16
        radius: Theme.controlRadius + 2
        color: Theme.inset
        border.width: Theme.hair
        border.color: Theme.warn
        RowLayout {
            id: portalRow
            anchors { fill: parent; margins: 8 }
            Txt { text: "Sign-in required by this network"; color: Theme.warn; Layout.fillWidth: true; wrapMode: Text.Wrap }
            Button { text: "Sign in"; tint: Theme.warn; onClicked: Quickshell.execDetached(["bbkos-captive-open"]) }
        }
    }
    Txt { visible: Net.limited && !Net.portal; text: "Connected, but no internet access"; color: Theme.warn }
    Txt { visible: root.message !== ""; text: root.message; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }

    ListView {
        id: list
        visible: Net.wifiEnabled && !Net.hardwareBlocked
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(contentHeight, 320)
        clip: true
        spacing: 2
        model: root.rows
        delegate: NetworkRow {
            onFailed: text => root.message = text
            onPrompt: open => root.prompts += open ? 1 : -1
        }
    }
    Txt { visible: Net.wifiEnabled && !Net.hardwareBlocked && list.count === 0; text: "Looking for networks…"; color: Theme.dim }
    Txt { visible: !Net.wifiEnabled && !Net.hardwareBlocked; text: "Wi-Fi is off"; color: Theme.dim }

    PopupSection {
        visible: Net.wifiConnected || Net.wiredConnected
        WifiTools { Layout.fillWidth: true }
    }

    SettingRow {
        label: "Hidden or enterprise network?"
        labelWidth: 196
        Layout.bottomMargin: -12                                // the card margin already gives the room below
        Item { Layout.fillWidth: true }
        Button { text: "Advanced…"; onClicked: { Quickshell.execDetached(["bbkos-tui", "nmtui"]); PanelState.close() } }
    }
}
