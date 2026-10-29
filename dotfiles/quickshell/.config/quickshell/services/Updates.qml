pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Pending repo updates, from `checkupdates` (pacman-contrib: reads a temporary copy of the sync database, needs no root
// and never touches the real one). Checked at shell start and then every 30 minutes; after a failed check (no network
// yet, mirror down) it retries in 5 minutes and keeps the last count. AUR packages are not counted. The bar widget
// shows when count > 0; clicking it runs `bbkos-update`, which calls `qs ipc call updates refresh` when it finishes.
Singleton {
    id: root

    property int count: 0
    property bool failed: false

    function refresh() { if (!probe.running) probe.running = true }

    Process {
        id: probe
        command: ["checkupdates"]
        stdout: StdioCollector { id: out }
        onExited: code => {
            // 0 = updates listed, 2 = none pending, anything else = the check itself failed
            root.failed = code !== 0 && code !== 2
            if (code === 0) root.count = out.text.split("\n").filter(l => l.trim() !== "").length
            else if (code === 2) root.count = 0
        }
    }

    Timer {
        interval: root.failed ? 300000 : 1800000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    IpcHandler {
        target: "updates"
        function refresh(): void { root.refresh() }
        function status(): string { return JSON.stringify({ count: root.count, failed: root.failed }) }
    }
}
