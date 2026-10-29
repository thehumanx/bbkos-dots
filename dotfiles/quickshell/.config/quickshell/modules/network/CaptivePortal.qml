import QtQuick
import Quickshell
import Quickshell.Io
import qs.services

// Captive portals (cafe, hotel, airport Wi-Fi): when NetworkManager reports "Portal" the internet is blocked until a
// sign-in page is visited. It opens ONCE per portal episode, in a private browser window (bbkos-captive-open); the
// Wi-Fi panel shows a banner with a Sign in button to open it again. Re-arms when the state leaves "Portal".
Scope {
    id: root
    property bool handled: false

    function open() {
        Quickshell.execDetached(["notify-send", "-a", "Wi-Fi", "Sign in to the network", "Opening the sign-in page in a private window."])
        Quickshell.execDetached(["bbkos-captive-open"])
    }
    function evaluate() {
        if (Net.portal) { if (!handled) { handled = true; open() } }
        else handled = false
    }

    Timer { interval: 4000; running: true; onTriggered: root.evaluate() }          // services start lazily
    Connections { target: Net; function onPortalChanged() { root.evaluate() } }

    IpcHandler {                                    // test hook: qs ipc call captive open
        target: "captive"
        function open(): void { root.open() }
    }
}
