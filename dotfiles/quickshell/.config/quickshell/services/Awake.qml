pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Awake mode (bbkos-awake): on = hypridle does not suspend the laptop, dim the screen, lock it or switch it off
// when idle (a manual lock still works). The flag file in the state directory is the state. refresh() reads it with `bbkos-awake status`; set() changes it at once and runs `bbkos-awake on|off`.
Singleton {
    id: root

    property bool on: false
    readonly property string tool: (Quickshell.env("HOME") ?? "") + "/.local/bin/bbkos-awake"

    Component.onCompleted: refresh()

    function refresh(): void { if (!statusProc.running) statusProc.running = true }

    function set(value: bool): void {
        root.on = value
        Quickshell.execDetached([tool, value ? "on" : "off"])
    }

    Process {
        id: statusProc
        command: [root.tool, "status"]
        stdout: StdioCollector { id: statusOut }
        onExited: root.on = statusOut.text.trim() === "on"
    }
}
