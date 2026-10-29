import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Displays page: the scale of each enabled monitor (MonitorScaleRow; bbkos-display owns it and every change gets the
// Keep / Revert prompt, docs/modules/displays.md) and night light (nightlight.*; bbkos-theme writes hyprsunset.conf and runs
// hyprsunset.service only while the mode is on, docs/modules/nightlight.md). Brightness, resolution and arrangement are in
// the display popup of the bar. Made 2026-10-28 from the Shell page's Displays card and the Night light page.
SettingsPage {
    note: "Brightness, resolution and where each screen sits are in the display popup of the bar."

    readonly property var evening: ["18:00", "19:00", "20:00", "21:00", "22:00", "23:00"]
    readonly property var morning: ["05:00", "06:00", "07:00", "08:00", "09:00"]

    // Display scale, one row per enabled monitor (see MonitorScaleRow). Changes share one Keep / Revert prompt.
    Component.onCompleted: Displays.refresh()
    SettingsSection {
        title: "Scale"
        description: "Makes text and everything else bigger. A change asks you to keep or revert it."
        Repeater {
            model: Displays.monitors.filter(m => !m.disabled)
            delegate: MonitorScaleRow { required property var modelData; mon: modelData }
        }

        Rectangle {
            visible: Displays.pending
            Layout.fillWidth: true
            implicitHeight: 44
            Layout.topMargin: 12
            Layout.bottomMargin: 12
            radius: Theme.controlRadius
            color: Theme.bg
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
            Layout.margins: 12
        }
    }

    SettingsSection {
        title: "Night light"
        description: "Needs hyprsunset. Nothing runs while it is off. Screenshots and recordings keep the normal colours."
        SettingChoice {
            label: "Mode"; hint: "A schedule warms the screen from the evening time until the morning time"; key: "nightlight.mode"
            model: [{ value: "off", label: "Off" }, { value: "on", label: "Always on" }, { value: "schedule", label: "Schedule" }]
        }
        SettingSlider { label: "Warmth"; hint: "Lower is warmer; 6000 K is no change"; key: "nightlight.temperature"; from: 2500; to: 6000; step: 100; suffix: " K" }
        SettingChoice { label: "Warm from"; hint: "Schedule only"; key: "nightlight.start"; model: evening }
        SettingChoice { label: "Back to normal at"; hint: "Schedule only"; key: "nightlight.end"; model: morning }
    }
}
