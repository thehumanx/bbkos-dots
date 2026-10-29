import QtQuick
import QtQuick.Layouts
import qs
import qs.services

// A numeric setting: label (and hint) and a StepBar ("−", the filled bar with the value in it, "+"). The value has 2 decimals
// for a fractional step and none otherwise (or `decimals`, after `factor`), then `suffix` (" px", " ms", "%"); with `percent` a 0-1 value is shown as 0-100%.
// Reads SettingsStore.shown(key) (the file's value, or the value last asked for while its run is pending) and only ever calls
// SettingsStore.set: it keeps no copy of the value. Dragging and the ends snap to `step` within from-to. A disabled row
// (enabled: false) dims every part to 0.4.
SettingRow {
    id: root
    property real from: 0
    property real to: 1
    property real step: 1
    property string suffix: ""
    property bool percent: false
    property real factor: 1                  // shown value = stored value × factor (camera exposure: tenths of a ms → ms)
    property int decimals: -1                // -1: 2 for a fractional step, else 0

    readonly property bool fractional: Math.round(step) !== step
    readonly property var raw: SettingsStore.shown(key)
    readonly property bool known: typeof raw === "number" && isFinite(raw)
    readonly property real current: known ? raw : from

    function describe(v): string {
        if (typeof v !== "number") return String(v)
        if (percent) return Math.round(v * 100) + "%"
        return (v * factor).toFixed(decimals >= 0 ? decimals : fractional ? 2 : 0) + suffix
    }

    StepBar {
        Layout.fillWidth: true
        from: root.from
        to: root.to
        step: root.step
        value: root.current
        known: root.known
        text: root.describe(root.current)
        onMoved: v => SettingsStore.set(root.key, v)
    }
}
