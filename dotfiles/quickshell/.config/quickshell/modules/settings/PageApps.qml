import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components

// Default apps page (docs/modules/settings-app.md, "Default apps"): which app opens web links, folders, images, video,
// music, PDFs, text and mail. Read and written by `bbkos-defaults` (~/.config/mimeapps.list); the choices offered are
// the installed apps that declare the category's type. The model owns the state: the chips show what the file says
// after each write (the tool is re-read), never a local copy.
SettingsPage {
    id: page
    note: "Which app opens a link or a file. Only apps that say they can open that kind of file are offered."

    property var categories: []
    property string error: ""

    function refresh() { if (!statusProc.running) statusProc.running = true }
    Component.onCompleted: refresh()

    Process {
        id: statusProc
        command: ["bbkos-defaults", "status"]
        stdout: StdioCollector {
            onStreamFinished: { try { page.categories = JSON.parse(text) } catch (e) { page.error = "Could not read the default apps" } }
        }
    }
    Process {
        id: setProc
        stderr: StdioCollector { id: setErr }
        onExited: code => { page.error = code === 0 ? "" : (setErr.text.trim() || "Could not set the default app"); page.refresh() }
    }

    SettingsSection {
        Repeater {
            model: page.categories
            delegate: SettingRow {
                required property var modelData
                label: modelData.label
                hint: modelData.candidates.length === 0 ? "No installed app can open these"
                      : modelData.current === "" ? "Not set: apps pick one themselves" : ""
                Chips {
                    Layout.fillWidth: true
                    model: modelData.candidates.map(c => ({ value: c.id, label: c.name }))
                    current: modelData.current
                    onChosen: v => { setProc.command = ["bbkos-defaults", "set", modelData.key, v]; setProc.running = true }
                }
            }
        }
    }
    Txt { visible: page.error !== ""; text: page.error; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }
}
