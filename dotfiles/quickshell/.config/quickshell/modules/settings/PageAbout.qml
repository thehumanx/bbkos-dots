import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components
import qs.services

// About and updates page (docs/modules/about.md): facts about this computer from `bbkos-about`, and the update state. The
// pending count is the bar widget's (services/Updates.qml, `checkupdates`); Update opens the same floating terminal.
SettingsPage {
    id: page
    note: ""

    property var rows: []
    property string lastUpdate: ""
    property string error: ""
    Component.onCompleted: if (!aboutProc.running) aboutProc.running = true

    Process {
        id: aboutProc
        command: ["bbkos-about"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { const d = JSON.parse(text); page.rows = d.rows; page.lastUpdate = d.update.last || ""; page.error = "" }
                catch (e) { page.error = "Could not read the system information" }
            }
        }
    }

    SettingsSection {
        title: "Updates"
        SettingRow {
            label: Updates.failed ? "Could not check for updates" : Updates.count === 0 ? "Everything is up to date" : Updates.count + " updates waiting"
            hint: page.lastUpdate === "" ? "Repository packages only; AUR packages are not counted" : "Last update " + page.lastUpdate + ". Repository packages only; AUR packages are not counted"
            Item { Layout.fillWidth: true }
            Button { text: "Check now"; onClicked: Updates.refresh() }
            Button { text: "Update"; onClicked: Quickshell.execDetached(["bbkos-tui", "bbkos-update"]) }
        }
    }
    SettingsSection {
        title: "This computer"
        Repeater {
            model: page.rows
            delegate: SettingRow {
                required property var modelData
                label: modelData[0]
                Item { Layout.fillWidth: true }
                Txt { text: modelData[1]; color: Theme.dim; elide: Text.ElideRight; Layout.maximumWidth: 420 }
            }
        }
    }
    Txt { visible: page.error !== ""; text: page.error; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }
}
