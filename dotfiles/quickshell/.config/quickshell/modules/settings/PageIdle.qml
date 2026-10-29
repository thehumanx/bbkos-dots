import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Idle and lock page: how long the laptop sits idle before each step (hypridle), and awake mode. Keys mirror settings.py
// (idle.dim, lock, screenOff, suspend; seconds, 0 = never). bbkos-theme renders hypridle.conf and restarts hypridle when it
// changes (docs/modules/idle.md). A manual lock (Super+L, the menu) is never affected by these. IdleTimeline draws the four
// steps on one time line above their chips (2026-10-28).
SettingsPage {
    note: "Awake mode skips every step below. Locking by hand still works."

    readonly property var early: [
        { value: 0, label: "Never" }, { value: 60, label: "1 min" }, { value: 120, label: "2 min" },
        { value: 150, label: "2.5 min" }, { value: 300, label: "5 min" }, { value: 600, label: "10 min" }]
    readonly property var late: [
        { value: 0, label: "Never" }, { value: 120, label: "2 min" }, { value: 300, label: "5 min" },
        { value: 600, label: "10 min" }, { value: 900, label: "15 min" }, { value: 1800, label: "30 min" }]
    readonly property var suspendModel: [
        { value: 0, label: "Never" }, { value: 300, label: "5 min" }, { value: 600, label: "10 min" },
        { value: 900, label: "15 min" }, { value: 1800, label: "30 min" }, { value: 3600, label: "1 hour" }]

    SettingsSection {
        title: "Awake mode"
        SettingRow {
            label: "Keep awake"; hint: "No dimming, locking, screen off or suspend while idle. The lid still suspends."
            Item { Layout.fillWidth: true }
            Toggle { checked: Awake.on; onToggled: on => Awake.set(on) }
        }
    }
    SettingsSection {
        title: "When idle"
        description: Awake.on ? "Keep awake is on, so none of these happen now. They are kept for when it is off." : ""
        IdleTimeline {}
        SettingChoice { label: "Dim the screen"; hint: "Also switches the keyboard light off"; key: "idle.dim"; model: early }
        SettingChoice { label: "Lock the screen"; key: "idle.lock"; model: late }
        SettingChoice { label: "Switch the screen off"; key: "idle.screenOff"; model: late }
        SettingChoice { label: "Suspend"; hint: "Suspend, then hibernate later"; key: "idle.suspend"; model: suspendModel }
    }
}
