import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components

// Startup apps page (docs/modules/startup.md): the apps started at login, from the freedesktop autostart folder. Read and
// written by `bbkos-autostart` (~/.config/autostart); the page shows what the tool says after each change and keeps no copy.
// System entries (the keyring, accessibility) can be switched off but not removed.
SettingsPage {
    id: page
    note: "Changes take effect at the next login."

    property var entries: []
    property var apps: []
    property string error: ""
    property string query: ""
    readonly property var matches: apps.filter(a => query.trim() === "" || a.name.toLowerCase().indexOf(query.trim().toLowerCase()) >= 0).slice(0, 8)

    function refresh() { if (!statusProc.running) statusProc.running = true }
    function run(args) { if (!actProc.running) { actProc.command = ["bbkos-autostart"].concat(args); actProc.running = true } }
    Component.onCompleted: refresh()

    Process {
        id: statusProc
        command: ["bbkos-autostart", "status"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { const d = JSON.parse(text); page.entries = d.entries; page.apps = d.apps; page.error = "" }
                catch (e) { page.error = "Could not read the startup apps" }
            }
        }
    }
    Process {
        id: actProc
        stderr: StdioCollector { id: actErr }
        onExited: code => { page.error = code === 0 ? "" : (actErr.text.trim() || "Could not change the startup apps"); page.refresh() }
    }

    SettingsSection {
        title: "Started at login"
        Txt { visible: page.entries.length === 0; text: "Nothing is started by this list yet."; color: Theme.dim; Layout.margins: 14 }
        Repeater {
            model: page.entries
            delegate: SettingRow {
                required property var modelData
                label: modelData.name
                hint: modelData.source === "system" || modelData.source === "override" ? "Part of the desktop: leave on unless you know why" : modelData.exec
                Item { Layout.fillWidth: true }
                Button {
                    visible: modelData.source === "user"
                    text: "Remove"
                    onClicked: page.run(["remove", modelData.id])
                }
                Toggle { checked: modelData.enabled; onToggled: on => page.run([on ? "enable" : "disable", modelData.id]) }
            }
        }
    }

    SettingsSection {
        title: "Add an app"
        SettingRow {
            label: "Search"; hint: "Installed apps; the first eight matches are shown"
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 32
                radius: Theme.controlRadius
                color: Theme.inset
                border.width: search.activeFocus ? 2 : Theme.hair
                border.color: search.activeFocus ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.3)
                TextInput {
                    id: search
                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                    verticalAlignment: TextInput.AlignVCenter
                    clip: true
                    color: Theme.fg
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSize
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.bg
                    onTextChanged: page.query = text
                }
            }
        }
        Repeater {
            model: page.matches
            delegate: SettingRow {
                required property var modelData
                label: modelData.name
                Item { Layout.fillWidth: true }
                Button { text: "Start at login"; onClicked: page.run(["add", modelData.id]) }
            }
        }
    }
    Txt { visible: page.error !== ""; text: page.error; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }
}
