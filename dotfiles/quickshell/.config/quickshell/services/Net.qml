pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Networking

// Connectivity from the native NetworkManager backend (no subprocess, no polling).
Singleton {
    readonly property var devices: Networking.devices.values
    readonly property var wifi: devices.find(d => d.type === DeviceType.Wifi) ?? null
    readonly property var wired: devices.find(d => d.type === DeviceType.Wired) ?? null
    readonly property bool wifiEnabled: Networking.wifiEnabled
    readonly property bool hardwareBlocked: !Networking.wifiHardwareEnabled     // hardware radio switch
    readonly property bool wifiConnected: wifi !== null && wifi.connected
    readonly property bool connecting: wifiEnabled && !wifiConnected && wifi !== null && wifi.networks.values.some(n => n.state === ConnectionState.Connecting)
    readonly property bool wiredConnected: wired !== null && wired.connected
    // NetworkManager's connectivity is global and lags behind the link, so it is only trusted
    // while a link is up and has been for a few seconds (not while Wi-Fi is off or still joining).
    property bool settled: false
    readonly property bool linkUp: wifiConnected || wiredConnected
    onLinkUpChanged: { settled = false; if (linkUp) settleTimer.restart(); else settleTimer.stop() }
    Timer { id: settleTimer; interval: 6000; onTriggered: Net.settled = true }
    Component.onCompleted: if (linkUp) settled = true
    readonly property bool portal: linkUp && settled && Networking.connectivity === NetworkConnectivity.Portal     // captive portal: sign in
    readonly property bool limited: linkUp && settled && Networking.connectivity === NetworkConnectivity.Limited   // connected, no internet
    readonly property var connectedNetwork: wifiConnected ? (wifi.networks.values.find(n => n.connected) ?? null) : null
    readonly property string ssid: connectedNetwork ? connectedNetwork.name : ""
    readonly property real signal: connectedNetwork ? connectedNetwork.signalStrength : -1     // 0-1 of the joined network; -1 when not on Wi-Fi

    // The last speed test from the Wi-Fi popup (modules/panels/WifiTools.qml): kept here so reopening the popup still
    // shows it. Mbps and ms; -1 = not measured; `at` = when it finished (ms since the epoch), 0 = running or stopped.
    property var lastSpeed: ({ ping: -1, down: -1, up: -1, at: 0 })

    function setWifiEnabled(on: bool) { Networking.wifiEnabled = on }
}
