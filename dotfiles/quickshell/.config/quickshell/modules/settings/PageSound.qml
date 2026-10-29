import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Pipewire
import qs
import qs.components
import qs.services

// Sound page: the default output and input device, their volume and mute, and the volume of each app that is playing.
// All of it is PipeWire's live state through services/Audio.qml (nothing is stored in settings.json: the devices and volumes
// are PipeWire's own, WirePlumber remembers them). The audio popup in the bar is the quick version of this page.
SettingsPage {
    id: page
    note: "Choose where sound comes from and goes to, and how loud each app is."

    // Playing apps (not devices): streams that send audio out. Each has its own volume.
    readonly property var streams: Pipewire.nodes.values.filter(n => n.isStream && n.audio && (n.properties["media.class"] ?? "") === "Stream/Output/Audio")
    function appName(n): string { return n.properties["application.name"] || n.properties["node.name"] || n.description || "App" }

    component VolumeRow: SettingRow {
        id: row
        property var node: null
        property bool showMute: true
        readonly property real vol: node && node.audio ? node.audio.volume : 0
        StepBar {
            Layout.fillWidth: true
            from: 0; to: 100; step: 5
            known: row.node !== null && row.node.audio !== undefined && row.node.audio !== null
            value: Math.min(100, Math.round(row.vol * 100))
            text: Math.round(row.vol * 100) + "%"
            onMoved: v => Audio.setVolume(row.node, v / 100)
        }
        Button {
            visible: row.showMute
            text: row.node && row.node.audio && row.node.audio.muted ? "Unmute" : "Mute"
            onClicked: Audio.setMuted(row.node, !(row.node && row.node.audio && row.node.audio.muted))
        }
    }

    SettingsSection {
        title: "Output"
        SettingRow {
            label: "Play sound through"; hint: Audio.sinks.length === 0 ? "No output device found" : ""
            Chips {
                Layout.fillWidth: true
                model: Audio.sinks.map(n => ({ value: String(n.id), label: Audio.label(n) }))
                current: Audio.sink ? String(Audio.sink.id) : undefined
                onChosen: v => Audio.setDefaultSink(Audio.sinks.find(n => String(n.id) === v))
            }
        }
        VolumeRow { label: "Volume"; node: Audio.sink }
    }
    SettingsSection {
        title: "Input"
        SettingRow {
            label: "Record sound from"; hint: Audio.sources.length === 0 ? "No input device found" : ""
            Chips {
                Layout.fillWidth: true
                model: Audio.sources.map(n => ({ value: String(n.id), label: Audio.label(n) }))
                current: Audio.source ? String(Audio.source.id) : undefined
                onChosen: v => Audio.setDefaultSource(Audio.sources.find(n => String(n.id) === v))
            }
        }
        VolumeRow { label: "Volume"; node: Audio.source }
    }
    SettingsSection {
        title: "Apps"
        Txt { visible: page.streams.length === 0; text: "No app is playing sound right now."; color: Theme.dim; Layout.margins: 14 }
        Repeater {
            model: page.streams
            delegate: VolumeRow {
                required property var modelData
                label: page.appName(modelData)
                node: modelData
            }
        }
    }
}
