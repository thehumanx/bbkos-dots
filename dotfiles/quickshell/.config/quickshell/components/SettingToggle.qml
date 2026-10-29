import QtQuick
import QtQuick.Layouts
import qs
import qs.services

// An on/off setting: label (and hint) and Toggle at the right. Reads SettingsStore.shown(key), calls SettingsStore.set;
// keeps no copy. Disabled while the value is not a boolean (missing key).
SettingRow {
    id: root

    readonly property var raw: SettingsStore.shown(key)
    function describe(v): string { return v === true ? "on" : v === false ? "off" : String(v) }

    Item { Layout.fillWidth: true }
    Toggle {
        checked: root.raw === true
        enabled: typeof root.raw === "boolean" && root.enabled
        onToggled: v => SettingsStore.set(root.key, v)
    }
}
