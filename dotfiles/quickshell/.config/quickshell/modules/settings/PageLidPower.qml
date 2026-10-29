import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Lid and power page: what closing the lid and holding the power button do. Keys mirror settings.py (session.*). logind reads
// root-owned files, so a small root helper writes them (power/bbkos-logind-apply, installed once with
// scripts/install-logind-helper.sh); services/LogindApply.qml runs it after each change (docs/modules/lid-power.md).
SettingsPage {
    id: page
    note: LogindApply.installed ? "" : "The root helper is not installed, so changes are saved but not applied yet. Run once in a terminal: sudo ~/.local/share/bbkos/repo/scripts/install-logind-helper.sh"
    Component.onCompleted: LogindApply.refresh()

    readonly property var lidActions: [
        { value: "suspend-then-hibernate", label: "Suspend, then hibernate" }, { value: "suspend", label: "Suspend" },
        { value: "hibernate", label: "Hibernate" }, { value: "lock", label: "Only lock" }, { value: "ignore", label: "Do nothing" }]
    readonly property var keyActions: [
        { value: "poweroff", label: "Power off" }, { value: "suspend-then-hibernate", label: "Suspend, then hibernate" },
        { value: "suspend", label: "Suspend" }, { value: "hibernate", label: "Hibernate" }, { value: "ignore", label: "Do nothing" }]

    SettingsSection {
        title: "Closing the lid"
        SettingChoice { label: "On battery"; hint: "Doing nothing leaves the laptop running in a bag: it gets hot and drains the battery"; key: "session.lidBattery"; model: lidActions }
        SettingChoice { label: "On the charger"; hint: "Do nothing keeps the laptop reachable from your phone with the lid shut"; key: "session.lidPower"; model: lidActions }
        SettingRow { label: "With an external screen"; hint: "Nothing happens to the session; the laptop panel switches off and the screen locks (not a setting)" }
    }
    SettingsSection {
        title: "Power button"
        SettingChoice { label: "Hold it"; hint: "A short press opens the power menu (not a setting)"; key: "session.powerKeyLong"; model: keyActions }
    }
    Txt {
        visible: LogindApply.status !== "idle" && LogindApply.installed
        text: LogindApply.status === "applying" ? "Applying…" : LogindApply.status
        color: LogindApply.status === "applying" ? Theme.dim : Theme.crit
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }
}
