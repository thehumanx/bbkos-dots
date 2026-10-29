import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// About and system > Reset: revert to the settings from when this window opened, and reset everything (second click within
// 4 s, like the power menu). Single settings and cards are reset where they are shown (SettingRow, SettingsSection); the list
// of per-section Reset buttons that was here went on 2026-10-28. All go through SettingsStore (one bbkos-theme run at a time).
SettingsPage {
    id: page
    note: "To reset one setting, rest the pointer on its row and click Default. Each card has Reset these while anything in it differs from the default."

    readonly property bool busy: SettingsStore.status === "applying"
    property bool armed: false          // "Reset everything" waits for a second click

    SettingsSection {
        title: "Revert and restore"
        SettingRow {
            label: "Revert to when this window opened"
            hint: "Including the wallpaper"
            Item { Layout.fillWidth: true }
            Button { text: "Revert"; enabled: !page.busy; onClicked: SettingsStore.revertToOpen() }
        }
        SettingRow {
            label: "Reset everything"
            hint: "Every setting and the wallpaper back to the defaults"
            Item { Layout.fillWidth: true }
            Button {
                text: page.armed ? "Click again to reset everything" : "Reset everything"
                tint: page.armed ? Theme.crit : Theme.fg
                border.color: page.armed ? Theme.crit : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.2)
                enabled: !page.busy
                onClicked: {
                    if (!page.armed) { page.armed = true; disarm.restart(); return }
                    page.armed = false
                    disarm.stop()
                    SettingsStore.reset("")
                }
            }
        }
    }

    Timer { id: disarm; interval: 4000; onTriggered: page.armed = false }
}
