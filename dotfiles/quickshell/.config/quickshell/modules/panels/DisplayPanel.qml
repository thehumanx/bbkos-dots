import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services
import "../../components/DisplayText.js" as DisplayText

// Display popup: per monitor its brightness, scale and mode, then (with two monitors) the layout. Every change
// goes through Displays -> bbkos-display; a changed scale, mode or layout asks "Keep these settings?" and reverts
// after Displays.keepWindow seconds without an answer. Awake mode (Awake -> bbkos-awake) is the last row.
ColumnLayout {
    id: root
    spacing: 8

    readonly property var modeLabels: [{ value: "extend", label: "Extend" }, { value: "mirror", label: "Mirror" }]
    readonly property var positions: [{ value: "left", label: "Left" }, { value: "right", label: "Right" },
                                     { value: "above", label: "Above" }, { value: "below", label: "Below" }]

    Component.onCompleted: { Displays.refresh(); Displays.refreshAllBrightness(); Awake.refresh() }

    PopupHeader { title: "Display" }

    Rectangle {
        visible: Displays.pending
        Layout.fillWidth: true
        implicitHeight: 44
        radius: Theme.controlRadius
        color: Theme.inset
        RowLayout {
            anchors { fill: parent; leftMargin: 10; rightMargin: 8 }
            spacing: 8
            Txt {
                text: Displays.keepSeconds > 0 ? "Keep these settings?  " + Displays.keepSeconds + " s" : "Keep these settings?"
                Layout.fillWidth: true
            }
            Button { text: "Revert"; onClicked: Displays.revert() }
            Button { text: "Keep"; tint: Theme.accent; onClicked: Displays.keep() }
        }
    }

    Txt {
        visible: Displays.status.startsWith("error:")
        text: Displays.status.substring(7)
        color: Theme.crit
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }

    Repeater {
        model: Displays.monitors
        delegate: PopupSection {
            id: card
            required property var modelData
            required property int index
            first: index === 0                                   // right under the header: no hairline
            title: modelData.name + (modelData.disabled ? "  (off)" : "")

            Txt { text: DisplayText.modeLine(card.modelData.mode, card.modelData.scale); color: Theme.dim; font.pixelSize: Theme.fontSize - 1 }
            Txt { text: card.modelData.description; color: Theme.dim; font.pixelSize: Theme.fontSize - 1; elide: Text.ElideRight; Layout.fillWidth: true }

            RowLayout {
                visible: card.modelData.brightness !== null
                Layout.fillWidth: true
                spacing: 8
                Txt { text: ""; Layout.preferredWidth: 20 }
                StepBar {
                    Layout.fillWidth: true
                    from: 0; to: 100; step: 5
                    known: Displays.brightnessOf(card.modelData.name) >= 0
                    value: Math.max(0, Displays.brightnessOf(card.modelData.name))
                    text: value + " %"
                    unknownText: "…"                     // a DDC read can take seconds
                    opacity: known ? 1 : 0.4
                    onMoved: v => Displays.setBrightness(card.modelData.name, v)
                }
            }
            Txt {
                visible: card.modelData.brightness === null
                text: "Brightness: needs ddcutil and DDC/CI on this monitor"
                color: Theme.dim; font.pixelSize: Theme.fontSize - 1; elide: Text.ElideRight; Layout.fillWidth: true
            }
            Txt {
                visible: (Displays.brightnessError[card.modelData.name] ?? "") !== ""
                text: Displays.brightnessError[card.modelData.name] ?? ""
                color: Theme.crit; font.pixelSize: Theme.fontSize - 1; wrapMode: Text.Wrap; Layout.fillWidth: true
            }

            Txt { text: "Scale"; Layout.topMargin: 4 }
            Chips {
                model: card.modelData.scaleOptions.map(s => ({ value: s, label: DisplayText.scaleLabel(s) }))
                current: card.modelData.scale
                onChosen: v => Displays.setScale(card.modelData.name, v)
            }

            Txt { visible: card.modelData.modes.length > 1; text: "Resolution and refresh rate"; Layout.topMargin: 4 }
            Chips {
                visible: card.modelData.modes.length > 1
                model: card.modelData.modes
                current: card.modelData.mode
                onChosen: m => Displays.setMode(card.modelData.name, m)
            }
        }
    }

    Txt { visible: Displays.monitors.length === 0; text: "No monitor information"; color: Theme.dim }

    PopupSection {
        visible: Displays.monitors.length === 2 && Displays.layout !== null
        title: "Layout"
        Chips {
            model: root.modeLabels.concat([{ value: "only", label: "Only " + (Displays.layout ? Displays.layout.primary : "") }])
            current: Displays.layout ? Displays.layout.mode : ""
            onChosen: m => Displays.setLayout(m, Displays.layout.primary, Displays.layout.position)
        }
        Txt { text: "Main display"; Layout.topMargin: 4 }
        Chips {
            model: Displays.monitors.map(m => m.name)
            current: Displays.layout ? Displays.layout.primary : ""
            onChosen: n => Displays.setLayout(Displays.layout.mode, n, Displays.layout.position)
        }
        Txt { visible: Displays.layout !== null && Displays.layout.mode === "extend"; text: "The other display sits"; Layout.topMargin: 4 }
        Chips {
            visible: Displays.layout !== null && Displays.layout.mode === "extend"
            model: root.positions
            current: Displays.layout ? Displays.layout.position : ""
            onChosen: p => Displays.setLayout(Displays.layout.mode, Displays.layout.primary, p)
        }
    }

    SettingRow {
        label: "Awake mode"
        hint: "Never suspends when idle. The screen still dims and locks; closing the lid still suspends."
        labelWidth: 236
        Layout.bottomMargin: -12                                // the card margin already gives the room below
        Item { Layout.fillWidth: true }
        Toggle { checked: Awake.on; onToggled: on => Awake.set(on) }
    }
}
