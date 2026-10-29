import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components
import qs.services

// Privacy and wellbeing page: the bar's privacy indicator (privacy.*; services/Privacy.qml reads PipeWire's streams,
// docs/modules/privacy.md) and what is in use now; the clipboard history (clipboard.maxItems, applied to the next copy, and
// clearing it now; text only, password-manager copies skipped, wiped at logout, docs/modules/clipboard.md); screen time
// (wellbeing.breakEvery and the screen-on totals of services/ScreenTime.qml, docs/modules/screentime.md). Made 2026-10-28
// from the Privacy, Clipboard and Screen time pages.
SettingsPage {
    id: page

    property bool confirming: false
    property string result: ""

    Process {
        id: wipe
        command: ["cliphist", "wipe"]
        onExited: code => page.result = code === 0 ? "History cleared." : "Could not clear the history."
    }
    Timer { id: confirmTimer; interval: 4000; onTriggered: page.confirming = false }

    function fmt(seconds: real): string {
        const m = Math.floor(seconds / 60)
        return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + (m % 60) + " min"
    }

    SettingsSection {
        title: "Privacy indicator"
        description: "A bar widget that shows only while something is in use. Move or remove it on Bar › Layout."
        SettingToggle { label: "Microphone"; hint: "An app has an open input stream, even if it is quiet"; key: "privacy.mic" }
        SettingToggle { label: "Camera"; hint: "An app is using the camera through PipeWire (browsers do, through the portal)"; key: "privacy.camera" }
        SettingToggle { label: "Screen sharing"; hint: "The compositor is sending your screen to an app"; key: "privacy.screen" }
    }

    SettingsSection {
        title: "Right now"
        SettingRow {
            label: "In use"
            hint: Privacy.mics.length + Privacy.cameras.length + Privacy.screens.length === 0 ? "Nothing is using the microphone, camera or screen"
                  : (Privacy.mics.length ? "Microphone: " + Privacy.mics.join(", ") + ". " : "") + (Privacy.cameras.length ? "Camera: " + Privacy.cameras.join(", ") + ". " : "")
                    + (Privacy.screens.length ? "Screen: " + Privacy.screens.join(", ") + "." : "")
        }
    }

    SettingsSection {
        title: "Clipboard history"
        description: "Copies from password managers are never stored, and the history is wiped when you log out."
        SettingSlider { label: "Entries kept"; hint: "Older entries are dropped as you copy new ones"; key: "clipboard.maxItems"; from: 10; to: 500; step: 10 }
        SettingToggle { label: "Keep images"; hint: "Screenshots and copied pictures, up to 10 MB each, with a thumbnail in the history"; key: "clipboard.images" }
        SettingRow {
            label: "Clear the history"; hint: page.result
            Item { Layout.fillWidth: true }
            Button {
                text: page.confirming ? "Really clear?" : "Clear now"
                tint: page.confirming ? Theme.crit : Theme.fg
                onClicked: {
                    if (page.confirming) { page.confirming = false; wipe.running = true }
                    else { page.confirming = true; page.result = ""; confirmTimer.restart() }
                }
            }
        }
    }

    SettingsSection {
        title: "Break reminder"
        SettingChoice {
            label: "Remind me to look away"; hint: "A notification after this long at the screen without a break. Five minutes with the screen off or locked count as a break"
            key: "wellbeing.breakEvery"
            model: [{ value: 0, label: "Never" }, { value: 20, label: "20 min" }, { value: 30, label: "30 min" }, { value: 45, label: "45 min" },
                    { value: 60, label: "1 hour" }, { value: 90, label: "1.5 hours" }]
        }
    }

    SettingsSection {
        title: "Screen on"
        description: "Counts while the screen is on and not locked."
        SettingRow { label: "Since this stretch began"; hint: "Resets after a break or a reminder"; Item { Layout.fillWidth: true } Txt { text: fmt(ScreenTime.streakSeconds); color: Theme.dim } }
        SettingRow { label: "Since the computer started"; Item { Layout.fillWidth: true } Txt { text: fmt(ScreenTime.bootSeconds); color: Theme.dim } }
        SettingRow { label: "Since the charger was unplugged"; Item { Layout.fillWidth: true } Txt { text: fmt(ScreenTime.unplugSeconds); color: Theme.dim } }
    }
}
