import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components

// Keyboard > Dictation (docs/modules/dictation.md): what Voxtype is doing and which key starts it. Read-only: Voxtype owns
// ~/.config/voxtype/config.toml, so a second writer would be a second source of truth. Reads on open and keeps no copy.
SettingsPage {
    id: page
    note: "Press the toggle key, speak, press it again: the words are typed where the cursor is. Everything runs on this computer."

    property bool installed: false
    property string service: ""
    property string backend: ""
    property string model: ""
    property string language: ""
    property string toggleKey: ""

    readonly property string configPath: Quickshell.env("HOME") + "/.config/voxtype/config.toml"

    function refresh() {
        if (!infoProc.running) infoProc.running = true
        if (!keyProc.running) keyProc.running = true
    }
    Component.onCompleted: refresh()

    // One shell run, "name=value" lines: the package, the service, the active backend and the config's model and language.
    Process {
        id: infoProc
        command: ["sh", "-c", "command -v voxtype >/dev/null && echo installed=yes || echo installed=no; " +
                  "echo service=$(systemctl --user is-active voxtype 2>/dev/null); " +
                  "echo backend=$(voxtype setup gpu --status 2>/dev/null | sed -n 's/^Active backend: //p' | sed 's/ (daemon pid.*//'); " +
                  "grep -E '^(model|language) *=' \"$HOME/.config/voxtype/config.toml\" 2>/dev/null | tr -d ' \"'"]
        stdout: StdioCollector {
            onStreamFinished: {
                const v = {}
                for (const line of text.split("\n")) {
                    const i = line.indexOf("=")
                    if (i > 0) v[line.slice(0, i)] = line.slice(i + 1).trim()
                }
                page.installed = v.installed === "yes"
                page.service = v.service ?? ""
                page.backend = v.backend ?? ""
                page.model = v.model ?? ""
                page.language = v.language ?? ""
            }
        }
    }
    Process {
        id: keyProc
        command: ["bbkos-keybinds", "status"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const b = JSON.parse(text).binds.find(x => x.id === "dictation-toggle" && x.enabled !== false)
                    const names = { SUPER: "Super", CTRL: "Ctrl", ALT: "Alt", SHIFT: "Shift" }
                    page.toggleKey = b ? b.keys.mods.map(m => names[m] ?? m).concat([b.keys.key]).join("+") : ""
                } catch (e) { page.toggleKey = "" }
            }
        }
    }

    SettingsSection {
        title: "Dictation"
        SettingRow {
            label: "Voxtype"
            hint: page.installed ? "The program that turns speech into text" : "Not installed: yay -S voxtype, then scripts/install-dictation.sh (docs/modules/dictation.md)"
            Item { Layout.fillWidth: true }
            Txt { text: page.installed ? "Installed" : "Not installed"; color: page.installed ? Theme.fg : Theme.warn }
        }
        SettingRow {
            label: "Service"
            hint: "Runs in the background while you are logged in"
            Item { Layout.fillWidth: true }
            Txt { text: page.service === "active" ? "Running" : page.service === "" ? "Unknown" : "Stopped"; color: page.service === "active" ? Theme.fg : Theme.warn }
        }
        SettingRow {
            label: "Backend"
            hint: "GPU (Vulkan) transcribes about 30 times faster than the CPU here. After a Voxtype upgrade run: sudo voxtype setup gpu --enable"
            Item { Layout.fillWidth: true }
            // The package owns the /usr/bin/voxtype symlink and an upgrade puts the CPU build back: amber until the GPU is on again.
            Txt { text: page.backend === "" ? "Unknown" : page.backend; color: page.backend.indexOf("Vulkan") >= 0 ? Theme.dim : Theme.warn }
        }
        SettingRow {
            label: "Toggle key"
            hint: "Starts and stops dictation"
            link: "keyboard/shortcuts"
            Item { Layout.fillWidth: true }
            Txt { text: page.toggleKey === "" ? "Not set" : page.toggleKey; color: page.toggleKey === "" ? Theme.warn : Theme.fg }
        }
        SettingRow {
            label: "Model"
            hint: "The speech model; the .en ones are English only"
            Item { Layout.fillWidth: true }
            Txt { text: page.model === "" ? "Unknown" : page.model; color: Theme.dim }
        }
        SettingRow {
            label: "Language"
            Item { Layout.fillWidth: true }
            Txt { text: page.language === "" ? "Unknown" : page.language; color: Theme.dim }
        }
        SettingRow {
            label: "Config file"
            hint: "Voxtype's own settings, kept with the bbkOS dotfiles"
            Item { Layout.fillWidth: true }
            Button { text: "Open"; onClicked: Quickshell.execDetached(["xdg-open", page.configPath]) }
        }
    }
}
