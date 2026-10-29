import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Scale of one monitor: one chip per valid scale (mon.scaleOptions, four on this laptop: 1, 1.1, 1.2, 1.25; uneven steps, so
// chips and not a slider). bbkos-display owns the scale (displays.json), so a choice goes through Displays and its
// Keep / Revert prompt.
SettingRow {
    id: root
    required property var mon                // one entry of Displays.monitors

    readonly property var scales: mon.scaleOptions ?? []

    label: mon.name.startsWith("eDP") ? "Built-in screen" : mon.name
    hint: (mon.name.startsWith("eDP") ? mon.name + "  ·  " : "") + (mon.description ?? "")
    enabled: scales.length > 1 && !Displays.pending

    Chips {
        Layout.fillWidth: true
        enabled: root.enabled
        model: root.scales.map(s => ({ value: s, label: Math.round(s * 100) + "%" }))
        current: root.mon.scale
        onChosen: v => { if (v !== root.mon.scale) Displays.setScale(root.mon.name, v) }
    }
}
