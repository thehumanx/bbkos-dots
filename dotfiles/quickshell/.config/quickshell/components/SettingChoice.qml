import QtQuick
import QtQuick.Layouts
import qs
import qs.services

// One value out of a list, as chips that wrap to more lines when they do not fit (the nine colour schemes). `model` holds
// plain values or { value, label } objects. Reads SettingsStore.shown(key), calls SettingsStore.set; keeps no copy.
// Values compare as text, so 0 and "0" match.
// `compact: true` (a long list on a row that is one of many, such as the six swipes): the row shows only the current
// choice as a button with a ▾; a click opens the chips under it, and a choice (or a second click) closes them again.
SettingRow {
    id: root
    property var model: []
    property bool compact: false
    property bool open: false

    readonly property var raw: SettingsStore.shown(key)
    function describe(v): string {
        for (const o of model) {
            if (o !== null && typeof o === "object" ? String(o.value) === String(v) : String(o) === String(v))
                return o !== null && typeof o === "object" ? String(o.label ?? o.value) : String(o)
        }
        return String(v)
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        Button {
            Layout.alignment: Qt.AlignLeft
            visible: root.compact
            enabled: root.enabled
            text: (root.raw === undefined || root.raw === null ? "-" : root.describe(root.raw)) + (root.open ? "  " : "  ")
            onClicked: root.open = !root.open
        }
        Chips {
            visible: !root.compact || root.open
            Layout.fillWidth: true
            enabled: root.enabled
            model: root.model
            current: root.raw === undefined || root.raw === null ? undefined : String(root.raw)
            onChosen: v => { SettingsStore.set(root.key, v); root.open = false }
        }
    }
}
