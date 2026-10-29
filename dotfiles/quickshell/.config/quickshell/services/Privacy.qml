pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire

// What is using the microphone, the camera or the screen right now, for the bar's privacy indicator (modules/bar/PrivacyWidget.qml).
// Read from PipeWire's streams, the same way the audio popup reads devices: an app with an open input stream is listening, a
// stream with the Camera role is a camera, and a video stream that the compositor produces is a screen share. An app that keeps an
// idle microphone stream open counts as using it (PipeWire's node state is not exposed to Quickshell). Which of the three are shown
// is the Privacy page (privacy.mic, camera, screen).
// Most apps (Vivaldi and the web apps made from it, Electron, video-call clients) open /dev/video* themselves and never make a
// PipeWire camera stream, so the camera is also read from the device: inotifywait reports each open and close (no polling), and
// bbkos-camera-users then lists the programs that hold a camera node open.
Singleton {
    id: root

    readonly property var cfg: ThemeStore.settings.privacy ?? ({})
    readonly property var streams: Pipewire.nodes.values.filter(n => n.isStream)

    function cls(n): string { return (n.properties && n.properties["media.class"]) || "" }
    function app(n): string { return (n.properties && (n.properties["application.name"] || n.properties["node.name"])) || "an app" }

    // The apps behind each kind, for the indicator's tooltip text.
    readonly property var mics: streams.filter(n => cls(n) === "Stream/Input/Audio").map(app)
    property var deviceCameras: []
    readonly property var cameras: streams.filter(n => cls(n) === "Stream/Input/Video" && n.properties["media.role"] === "Camera").map(app).concat(deviceCameras)
    readonly property var screens: streams.filter(n => cls(n) === "Stream/Output/Video").map(app)

    readonly property bool mic: cfg.mic !== false && mics.length > 0
    readonly property bool camera: cfg.camera !== false && cameras.length > 0
    readonly property bool screen: cfg.screen !== false && screens.length > 0
    readonly property bool any: mic || camera || screen

    Process {
        running: true
        command: ["sh", "-c", "exec inotifywait -m -q -e open,close /dev/video* 2>/dev/null"]
        stdout: SplitParser { onRead: line => scanDebounce.restart() }
    }
    Timer { id: scanDebounce; interval: 150; onTriggered: if (!scan.running) scan.running = true }
    Process {
        id: scan
        command: ["bbkos-camera-users"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.deviceCameras = JSON.parse(text) } catch (e) { root.deviceCameras = [] }
            }
        }
    }
    Component.onCompleted: scan.running = true

    // Properties of a node are only readable while it is tracked (see Audio.qml).
    PwObjectTracker { objects: Pipewire.nodes.values }

    IpcHandler {                          // test hook: qs ipc call privacy status
        target: "privacy"
        function status(): string {
            return JSON.stringify({ mic: root.mic, camera: root.camera, screen: root.screen, mics: root.mics, cameras: root.cameras, screens: root.screens,
                                    streams: root.streams.map(n => ({ cls: root.cls(n), app: root.app(n) })), nodes: Pipewire.nodes.values.length })
        }
    }
}
