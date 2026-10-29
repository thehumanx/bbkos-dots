import QtQuick
import QtQuick.Layouts
import qs
import qs.services

// A text setting: label and a one-line field. Reads SettingsStore.shown(key); the typed text is sent on Enter or when
// the field loses focus (editingFinished), not on every key, because each send re-renders files. Keeps no copy of the
// value while it is not being edited.
SettingRow {
    id: root
    property string placeholder: ""

    readonly property var raw: SettingsStore.shown(key)
    function describe(v): string { return v === "" ? "empty" : String(v) }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 32
        radius: Theme.controlRadius
        color: Theme.inset
        border.width: input.activeFocus ? 2 : Theme.hair
        border.color: input.activeFocus ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.3)
        opacity: root.enabled ? 1 : 0.4

        TextInput {
            id: input
            anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            color: Theme.fg
            font.family: Theme.font
            font.pixelSize: Theme.fontSize
            selectionColor: Theme.accent
            selectedTextColor: Theme.bg
            // Follows the setting until the user edits it (a pending value shows at once).
            text: typeof root.raw === "string" ? root.raw : ""
            onEditingFinished: if (text !== root.raw) SettingsStore.set(root.key, text)
        }
        Txt {
            visible: input.text === "" && !input.activeFocus
            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
            text: root.placeholder
            color: Theme.dim
        }
    }
}
