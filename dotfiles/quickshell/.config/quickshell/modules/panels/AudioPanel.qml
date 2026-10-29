import QtQuick
import QtQuick.Layouts
import Quickshell
import qs
import qs.components
import qs.services

// Audio popup: output and input devices, default device, volume and mute.
ColumnLayout {
    id: root
    spacing: 8

    // One section (output or input). `nodes` is the device list, `current` the default device. The speaker / mic glyph at
    // the right of its title is the mute button.
    component Section: PopupSection {
        id: sec
        property string heading                         // not `title`: PopupSection has one (qmllint property-override)
        property bool input: false
        property var nodes: []
        property var current: null
        property bool muted: false
        property real level: 0
        signal setMuted(bool muted)
        signal setLevel(real level)
        signal choose(var node)

        PopupHeader {
            title: sec.heading
            Rectangle {                                  // mute button
                implicitWidth: 30; implicitHeight: 30
                radius: Theme.controlRadius
                color: muteArea.containsMouse ? Theme.control : "transparent"
                Txt {
                    anchors.centerIn: parent
                    text: sec.muted ? (sec.input ? "" : "") : (sec.input ? "" : "")
                    color: sec.muted ? Theme.crit : Theme.fg
                }
                MouseArea { id: muteArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: sec.setMuted(!sec.muted) }
            }
        }
        StepBar {
            Layout.fillWidth: true
            from: 0; to: Math.max(100, value); step: 5           // above 100 % only when another tool set it
            known: sec.current !== null
            value: Math.round(sec.level * 100)
            text: Math.round(sec.level * 100) + " %"
            opacity: known ? 1 : 0.4
            onMoved: v => sec.setLevel(v / 100)
        }
        Repeater {
            model: sec.nodes
            delegate: AudioRow {
                required property var modelData
                node: modelData
                input: sec.input
                isDefault: sec.current !== null && modelData.id === sec.current.id
                onChosen: sec.choose(modelData)
            }
        }
        Txt { visible: sec.nodes.length === 0; text: sec.input ? "No microphone found" : "No output device found"; color: Theme.dim }
    }

    Section {
        heading: "Output"
        first: true
        nodes: Audio.sinks
        current: Audio.sink
        muted: Audio.muted
        level: Audio.volume
        onSetMuted: m => Audio.setMuted(Audio.sink, m)
        onSetLevel: v => Audio.setVolume(Audio.sink, v)
        onChoose: n => Audio.setDefaultSink(n)
    }

    Section {
        heading: "Input"
        input: true
        nodes: Audio.sources
        current: Audio.source
        muted: Audio.micMuted
        level: Audio.micVolume
        onSetMuted: m => Audio.setMuted(Audio.source, m)
        onSetLevel: v => Audio.setVolume(Audio.source, v)
        onChoose: n => Audio.setDefaultSource(n)
    }
}
