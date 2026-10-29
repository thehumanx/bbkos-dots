import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Notifications page: how the popups behave and how much history the bell keeps. Keys mirror settings.py
// (notifications.*); services/Notifs.qml and modules/notifications read them live (docs/modules/notifications.md).
SettingsPage {
    note: "Do not disturb keeps every notification in the history and shows no popup."

    SettingsSection {
        title: "Do not disturb"
        SettingRow {
            label: "Do not disturb"; hint: "No popups, critical ones included. Also the DND switch in the bell's panel."
            Item { Layout.fillWidth: true }
            Toggle { checked: Notifs.dnd; onToggled: on => Notifs.setDnd(on) }
        }
    }
    SettingsSection {
        title: "Popups"
        SettingChoice {
            label: "Corner"; hint: "Auto is the corner on the bar's end side"; key: "notifications.position"
            model: [{ value: "auto", label: "Auto" }, { value: "top-right", label: "Top right" }, { value: "top-left", label: "Top left" },
                    { value: "bottom-right", label: "Bottom right" }, { value: "bottom-left", label: "Bottom left" }]
        }
        SettingSlider { label: "Time on screen"; hint: "Seconds, when the app sent no time of its own"; key: "notifications.timeout"; from: 2; to: 30; step: 1; suffix: " s" }
        SettingToggle { label: "Use the app's own time"; hint: "Off: every popup uses the time above"; key: "notifications.senderTimeout" }
        SettingToggle { label: "Critical ones stay"; hint: "Off: critical popups disappear after the time above too"; key: "notifications.criticalSticky" }
        SettingSlider { label: "Popups at once"; hint: "Newer ones push older ones out of sight (they stay in the history)"; key: "notifications.maxPopups"; from: 1; to: 10; step: 1 }
        SettingToggle { label: "Show pictures"; hint: "Screenshots, avatars and app logos sent with a notification"; key: "notifications.showPictures" }
    }
    SettingsSection {
        title: "Short notices"
        description: "A small card above the volume bar for one second or two. Not kept in the history."
        SettingToggle { label: "Charger"; hint: "Plugged in or unplugged"; key: "notifications.toastCharger" }
        SettingToggle { label: "Sound output"; hint: "The speakers, headphones or Bluetooth device in use changed"; key: "notifications.toastAudio" }
        SettingToggle { label: "VPN"; hint: "Tailscale connected or disconnected"; key: "notifications.toastVpn" }
    }
    SettingsSection {
        id: apps
        title: "Apps"
        description: names.length === 0 ? "Apps appear here after their first notification."
                     : "Turn an app off to drop its notifications: no popup and no history entry."
        // The names are what apps send (the history's app names); an app is listed after its first notification, and a
        // muted one stays listed so it can be turned back on.
        readonly property var muted: SettingsStore.shown("notifications.mutedApps") ?? []
        readonly property var names: {
            const out = muted.slice()
            for (const h of Notifs.history) if (h.appName !== "" && !out.includes(h.appName)) out.push(h.appName)
            return out.sort((a, b) => a.localeCompare(b))
        }
        Item {                       // lets the card's "Reset these" unmute every app (SettingsSection reads key and modified)
            readonly property string key: "notifications.mutedApps"
            readonly property bool modified: SettingsStore.modified(key)
        }
        Repeater {
            model: apps.names
            delegate: SettingRow {
                required property string modelData
                label: modelData
                hint: apps.muted.includes(modelData) ? "Muted" : ""
                Item { Layout.fillWidth: true }
                Toggle {
                    checked: !apps.muted.includes(modelData)
                    onToggled: on => {
                        const rest = apps.muted.filter(n => n !== modelData)
                        SettingsStore.set("notifications.mutedApps", on ? rest : rest.concat([modelData]))
                    }
                }
            }
        }
    }
    SettingsSection {
        title: "History"
        SettingSlider { label: "Notifications kept"; hint: "In the bell's list; the oldest are dropped"; key: "notifications.historySize"; from: 20; to: 500; step: 20 }
    }
}
