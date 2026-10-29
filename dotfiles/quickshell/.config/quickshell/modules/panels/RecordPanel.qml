import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Recording options popup (PanelState "record"): what the next recording captures and records, then Start. While a
// recording runs it shows the time with Stop (and Move camera when the camera is on). The choices are the
// capture.record* settings (the Capture page edits the same keys); Start passes them explicitly, so it never races the
// settings write. A region is picked after the panel closes, with slurp.
ColumnLayout {
    id: root
    spacing: 8

    readonly property string area: String(SettingsStore.shown("capture.recordArea") ?? "region")
    readonly property string audio: String(SettingsStore.shown("capture.recordAudio") ?? "desktop")
    readonly property bool camera: SettingsStore.shown("capture.recordCamera") === true

    PopupHeader { title: "Record screen" }

    // Recording now
    ColumnLayout {
        visible: Record.recording
        Layout.fillWidth: true
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Txt { text: "●"; color: Theme.crit }
            Txt { text: "Recording  " + Record.clock; font.bold: true; Layout.fillWidth: true }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button { text: "Stop and save"; tint: Theme.crit; Layout.fillWidth: true; onClicked: { Record.stop(); PanelState.close() } }
            Button { visible: Record.camera; text: "Move camera"; onClicked: Record.cameraNext() }
        }
        Txt { visible: Record.camera; text: "Drag the camera to move it, or press Move camera to jump to the next corner."; color: Theme.dim; font.pixelSize: Theme.fontSize - 1; wrapMode: Text.Wrap; Layout.fillWidth: true }
    }

    // Options for the next one
    ColumnLayout {
        visible: !Record.recording
        Layout.fillWidth: true
        spacing: 8

        Txt { text: "What" }
        Chips {
            model: [{ value: "region", label: "Select a region" }, { value: "screen", label: "Whole screen" }]
            current: root.area
            onChosen: v => SettingsStore.set("capture.recordArea", v)
        }
        Txt { text: "Sound"; Layout.topMargin: 4 }
        Chips {
            model: [{ value: "none", label: "None" }, { value: "desktop", label: "Computer" },
                    { value: "mic", label: "Microphone" }, { value: "both", label: "Both" }]
            current: root.audio
            onChosen: v => SettingsStore.set("capture.recordAudio", v)
        }
        SettingRow {
            label: "Camera in the corner"; labelWidth: 196
            Item { Layout.fillWidth: true }
            Toggle { checked: root.camera; onToggled: v => SettingsStore.set("capture.recordCamera", v) }
        }
        PopupSection {
            Button {
                text: "Start recording"
                tint: Theme.accent
                Layout.fillWidth: true
                onClicked: { Record.start(root.area, root.audio, root.camera); PanelState.close() }
            }
            Txt { text: "Super+Shift+R stops a running recording, or opens this panel when idle."; color: Theme.dim; font.pixelSize: Theme.fontSize - 1; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
    }
}
