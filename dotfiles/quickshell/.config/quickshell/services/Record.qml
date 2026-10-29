pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Screen recording state (bbkos-record, docs/modules/capture.md). The tool owns the recording; this only mirrors it for the
// bar indicator and the options panel. Event driven: bbkos-record calls `qs ipc call record changed` whenever a recording
// starts or ends (modules/record/RecordIpc.qml), and this asks the tool for its status then. The only timer runs once a
// second while a recording is on, to count the elapsed time.
Singleton {
    id: root

    readonly property string tool: (Quickshell.env("HOME") ?? "") + "/.local/bin/bbkos-record"
    property bool recording: false
    property real started: 0                  // epoch seconds
    property bool camera: false
    property int elapsed: 0                   // seconds

    readonly property string clock: {
        const m = Math.floor(elapsed / 60), s = elapsed % 60
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
    }

    function refresh(): void { if (!statusProc.running) statusProc.running = true; else again = true }
    property bool again: false

    // Start a recording with these choices (the panel's); the picker for a region opens after the call.
    function start(area: string, audio: string, camera: bool): void {
        Quickshell.execDetached([tool, "start", area === "screen" ? "--screen" : "--region", "--audio", audio,
                                 camera ? "--camera" : "--no-camera"])
    }
    function stop(): void { Quickshell.execDetached([tool, "stop"]) }
    function cameraNext(): void { Quickshell.execDetached([tool, "camera", "next"]) }

    Process {
        id: statusProc
        command: [root.tool, "status"]
        stdout: StdioCollector {
            onStreamFinished: {
                let st = null
                try { st = JSON.parse(text) } catch (e) { st = null }
                root.recording = !!(st && st.recording === true)
                root.started = root.recording ? Number(st.started) || 0 : 0
                root.camera = root.recording && st.camera === true
                root.elapsed = root.recording ? Math.max(0, Math.floor(Date.now() / 1000 - root.started)) : 0
            }
        }
        onExited: if (root.again) { root.again = false; running = true }
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.recording
        onTriggered: root.elapsed = Math.max(0, Math.floor(Date.now() / 1000 - root.started))
    }

    Component.onCompleted: refresh()
}
