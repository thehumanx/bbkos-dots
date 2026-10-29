import QtQuick
import Quickshell
import Quickshell.Io
import qs.services

// IPC target "record": `changed` is called by bbkos-record whenever a recording starts or ends; `status` is a test hook.
//   qs ipc call record status    JSON of what the shell believes
Scope {
    IpcHandler {
        target: "record"
        function changed(): void { Record.refresh() }
        function status(): string {
            return JSON.stringify({ recording: Record.recording, started: Record.started, elapsed: Record.elapsed,
                                    camera: Record.camera, clock: Record.clock })
        }
    }
}
