import QtQuick
import QtQuick.Layouts
import qs
import qs.services

// Several values out of a list, as chips that toggle on a click (the screensaver's effects). `model` holds plain values or
// { value, label } objects. Reads SettingsStore.shown(key), an array; calls SettingsStore.set(key, array); keeps no copy.
// At least one stays chosen: a click on the last chosen chip does nothing. The tool keeps the list in its own order.
SettingRow {
    id: root
    property var model: []

    readonly property var raw: SettingsStore.shown(key)
    readonly property var picked: Array.isArray(raw) ? raw : []

    ColumnLayout {
        Layout.fillWidth: true
        Chips {
            Layout.fillWidth: true
            enabled: root.enabled
            multi: true
            model: root.model
            currents: root.picked
            onChosen: v => {
                const on = root.picked.indexOf(v) >= 0
                if (on && root.picked.length <= 1) return
                SettingsStore.set(root.key, on ? root.picked.filter(x => x !== v) : root.picked.concat([v]))
            }
        }
    }
}
