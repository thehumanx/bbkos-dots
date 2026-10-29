pragma Singleton
import Quickshell
import Quickshell.Services.Pipewire

// Audio outputs and inputs, default devices, volume and mute, via PipeWire.
Singleton {
    id: root
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource
    readonly property real volume: sink && sink.audio ? sink.audio.volume : 0   // 0-1
    readonly property bool muted: sink && sink.audio ? sink.audio.muted : false
    readonly property real micVolume: source && source.audio ? source.audio.volume : 0
    readonly property bool micMuted: source && source.audio ? source.audio.muted : false

    // Real devices only: not application streams, not cameras (video nodes).
    readonly property var sinks: Pipewire.nodes.values.filter(n => !n.isStream && n.properties["media.class"] === "Audio/Sink")
    readonly property var sources: Pipewire.nodes.values.filter(n => !n.isStream && n.properties["media.class"] === "Audio/Source")

    // A node exposes its properties (media.class) and .audio only while tracked, so track every node first and filter
    // afterwards: filtering first leaves everything but the default device invisible.
    PwObjectTracker { objects: Pipewire.nodes.values }

    // Short readable name: "Speaker", "HDMI 3", "Digital Microphone", or the Bluetooth device's own name.
    function label(n): string {
        if (!n) return "No device"
        const d = (n.description || n.nickname || n.name || "").replace(/^.*HD Audio Controller\s*/, "")
        const hdmi = d.match(/HDMI.*?(\d)/)
        return hdmi ? "HDMI " + hdmi[1] : d
    }
    function isBluetooth(n): bool { return !!n && (n.name || "").startsWith("bluez_") }

    function step(delta: real) { setVolume(sink, volume + delta) }
    // Never above 100 % from the shell; a volume another tool set above 100 % can still be stepped down from where it is
    // (120 -> 115), instead of jumping to 100.
    function setVolume(node, v: real) {
        if (node && node.audio) node.audio.volume = Math.max(0, Math.min(Math.max(1, node.audio.volume), v))
    }
    function setMuted(node, m: bool) { if (node && node.audio) node.audio.muted = m }
    function toggleMute() { if (sink && sink.audio) sink.audio.muted = !sink.audio.muted }
    function toggleMicMute() { if (source && source.audio) source.audio.muted = !source.audio.muted }
    function setDefaultSink(n) { Pipewire.preferredDefaultAudioSink = n }
    function setDefaultSource(n) { Pipewire.preferredDefaultAudioSource = n }
}
