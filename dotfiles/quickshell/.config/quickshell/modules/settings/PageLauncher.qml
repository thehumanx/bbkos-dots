import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components

// Launcher page: what the bbkOS menu (Super+R) searches and how. Keys mirror settings.py (launcher.*); modules/launcher/Launcher.qml
// reads them live (docs/modules/menu.md). "Forget" clears what the menu learned from what you opened.
SettingsPage {
    id: page
    note: "The menu opens with Super+R."

    property bool confirming: false
    property string result: ""

    Process {
        id: forget
        command: ["qs", "ipc", "call", "launcher", "forget"]
        onExited: code => page.result = code === 0 ? "Forgotten." : "Could not reach the menu."
    }
    Timer { id: confirmTimer; interval: 4000; onTriggered: page.confirming = false }

    SettingsSection {
        title: "Search"
        SettingChoice {
            label: "Web search"; hint: "The last result of every search opens it in your default browser"; key: "launcher.webSearch"
            model: [{ value: "duckduckgo", label: "DuckDuckGo" }, { value: "google", label: "Google" }, { value: "brave", label: "Brave" },
                    { value: "startpage", label: "Startpage" }, { value: "ecosia", label: "Ecosia" }, { value: "off", label: "Off" }]
        }
        SettingToggle { label: "Calculator"; hint: "Type a sum and Enter copies the answer"; key: "launcher.calculator" }
        SettingToggle { label: "bbkOS commands and settings pages"; hint: "Lock, power modes, update, the settings pages and the other commands"; key: "launcher.commands" }
        SettingSlider { label: "Results shown"; key: "launcher.maxResults"; from: 10; to: 40; step: 5 }
    }
    SettingsSection {
        title: "Learning"
        SettingToggle { label: "Remember what I open"; hint: "What you open often, and the words you used to find it, come first next time"; key: "launcher.learn" }
        SettingRow {
            label: "Forget what the menu learned"; hint: page.result
            Item { Layout.fillWidth: true }
            Button {
                text: page.confirming ? "Really forget?" : "Forget"
                tint: page.confirming ? Theme.crit : Theme.fg
                onClicked: {
                    if (page.confirming) { page.confirming = false; forget.running = true }
                    else { page.confirming = true; page.result = ""; confirmTimer.restart() }
                }
            }
        }
    }
}
