pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Io

// Bluetooth adapter state, device list and number of connected devices (BlueZ over D-Bus).
// BlueZ powers the adapter on at every boot and does not remember "off", so the choice is kept in a flag file in the
// state directory (exists = the user switched Bluetooth off) and applied to each adapter object once, when it shows up:
// at shell start, and again when bluetoothd restarts (or the adapter resets), which re-creates the adapter powered on
// (AutoEnable). A re-created adapter can still be powering on (state Enabling, enabled false) when the check ends: then
// the flag waits for that first power-on and undoes it; a later "on" (the user) is left alone.
// Checked 2026-10-29: `systemctl restart bluetooth` left Bluetooth on with the first-start-only version; the log showed the
// check ending in Enabling and the adapter coming on 300 ms later.
Singleton {
    id: root
    readonly property var adapter: Bluetooth.defaultAdapter
    readonly property bool available: adapter !== null
    readonly property bool enabled: available && adapter.enabled
    readonly property bool blocked: available && adapter.state === BluetoothAdapterState.Blocked   // rfkill
    readonly property var connected: Bluetooth.devices.values.filter(d => d.connected)
    readonly property int connectedCount: connected.length

    // Paired or connected devices, plus nearby ones that advertise a real name. Nameless advertisers show up as their
    // MAC address by the dozen; they are hidden unless already paired. Connected first, then paired, then by name.
    readonly property var devices: {
        const macLike = /^([0-9A-F]{2}[-:]){5}[0-9A-F]{2}$/i
        return Bluetooth.devices.values
            .filter(d => d.paired || d.connected || !macLike.test(d.name))
            .slice()
            .sort((a, b) => (b.connected - a.connected) || (b.paired - a.paired) || a.name.localeCompare(b.name))
    }

    readonly property string offFlag: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") ?? "") + "/.local/state") + "/bbkos/bluetooth-off"
    property var restoredFor: null              // the adapter object the flag was last applied to
    property var offWhenUp: null                // an adapter still powering on that the flag must switch off once it is on

    function setEnabled(on: bool) {
        if (!adapter) return
        adapter.enabled = on
        Quickshell.execDetached(["sh", "-c", on ? 'rm -f "$1"' : 'mkdir -p "$(dirname "$1")" && : > "$1"', "sh", offFlag])
    }

    onAdapterChanged: restore()
    Component.onCompleted: restore()

    function restore(): void {
        if (!adapter || restoredFor === adapter || restoreProc.running) return
        restoreProc.target = adapter
        restoreProc.running = true
    }

    Connections {
        target: root.adapter
        function onEnabledChanged() {
            if (root.offWhenUp === null || root.offWhenUp !== root.adapter) return
            root.offWhenUp = null
            if (root.adapter.enabled) root.adapter.enabled = false
        }
    }

    Process {
        id: restoreProc
        property var target: null
        command: ["sh", "-c", 'test -e "$1" && echo off', "sh", root.offFlag]
        stdout: StdioCollector { id: restoreOut }
        onExited: {
            root.restoredFor = target
            const off = restoreOut.text.trim() === "off" && target && target === root.adapter
            if (off && target.enabled) target.enabled = false
            else if (off && target.state === BluetoothAdapterState.Enabling) root.offWhenUp = target
            if (root.adapter !== target) root.restore()          // the adapter changed again while the check ran
        }
    }
}
