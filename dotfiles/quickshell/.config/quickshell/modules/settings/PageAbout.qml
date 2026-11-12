import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components
import qs.services
import "../../components/FileUrl.js" as FileUrl

// About and updates page (docs/modules/about.md): facts about this computer from `bbkos-about`, and the update state. The
// pending count is the bar widget's (services/Updates.qml, `checkupdates`); Update opens the same floating terminal.
SettingsPage {
    id: page
    note: ""

    property var rows: []
    property string lastUpdate: ""
    property string error: ""
    property var identity: ({})
    property var accounts: []
    readonly property string home: Quickshell.env("HOME") ?? ""
    readonly property string avatarPath: SettingsStore.shown("lock.avatar") ?? ""
    readonly property string shownName: {
        const n = String(SettingsStore.shown("profile.name") ?? "").trim()
        return n !== "" ? n : (identity.fullName || identity.user || "")
    }
    Component.onCompleted: if (!aboutProc.running) aboutProc.running = true

    Process {
        id: aboutProc
        command: ["bbkos-about"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { const d = JSON.parse(text); page.rows = d.rows; page.lastUpdate = d.update.last || ""; page.identity = d.identity || {}; page.accounts = d.accounts || []; page.error = "" }
                catch (e) { page.error = "Could not read the system information" }
            }
        }
    }

    // The picture is the lock screen's (lock.avatar, `bbkos-theme avatar set`): one picture for both. zenity's dialog floats
    // (Hyprland rule bbkos-misc-dialogs); the tool validates and copies the file, so nothing here reads it.
    Process {
        id: chooser
        command: ["zenity", "--file-selection", "--title=Choose your picture", "--filename=" + page.home + "/Pictures/",
                  "--file-filter=Images | *.png *.jpg *.jpeg *.webp *.PNG *.JPG *.JPEG *.WEBP"]
        stdout: StdioCollector { id: chosen }
        onExited: code => { const f = chosen.text.trim(); if (code === 0 && f !== "") SettingsStore.setAvatar(f) }
    }
    SettingsSection {
        title: "Profile"
        padded: true
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            Item {
                Layout.preferredWidth: 72; Layout.preferredHeight: 72
                Image {
                    anchors.fill: parent
                    source: page.avatarPath !== "" ? FileUrl.toUrl(page.avatarPath)
                            : page.home !== "" ? FileUrl.toUrl(page.home + "/.config/hypr/lock-avatar.png") : ""
                    sourceSize: Qt.size(144, 144)
                    fillMode: Image.PreserveAspectCrop
                    layer.enabled: true
                    layer.effect: MultiEffect { maskEnabled: true; maskSource: avatarMask }
                }
                Rectangle { id: avatarMask; anchors.fill: parent; radius: width / 2; visible: false; layer.enabled: true }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Txt { text: page.shownName; font.pixelSize: Theme.fontSize + 6; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                Txt { text: (page.identity.user ?? "") + "@" + (page.identity.host ?? ""); color: Theme.dim; Layout.fillWidth: true }
                RowLayout {
                    Layout.topMargin: 8
                    spacing: 8
                    Button { text: "Choose picture"; onClicked: if (!chooser.running) chooser.running = true }
                    Button { visible: page.avatarPath !== ""; text: "Use the default"; onClicked: SettingsStore.clearAvatar() }
                }
            }
        }
    }
    SettingsSection {
        SettingText { label: "Name"; hint: "Shown here. Empty uses the account's full name, or the user name"; key: "profile.name"; placeholder: page.identity.fullName || page.identity.user || "" }
        Repeater {
            model: [["Login shell", page.identity.shell], ["Groups", page.identity.groups], ["Session", page.identity.session]]
            delegate: SettingRow {
                required property var modelData
                visible: !!modelData[1]
                label: modelData[0]
                Item { Layout.fillWidth: true }
                Txt { text: modelData[1] ?? ""; color: Theme.dim; elide: Text.ElideRight; Layout.maximumWidth: 420 }
            }
        }
    }
    SettingsSection {
        visible: page.accounts.length > 0
        title: "Signed in"
        description: "Read from local files on this computer; nothing is sent anywhere"
        Repeater {
            model: page.accounts
            delegate: SettingRow {
                required property var modelData
                label: modelData[0]
                Item { Layout.fillWidth: true }
                Txt { text: modelData[1]; color: Theme.dim; elide: Text.ElideRight; Layout.maximumWidth: 420 }
            }
        }
    }
    SettingsSection {
        title: "Updates"
        SettingRow {
            label: Updates.failed ? "Could not check for updates" : Updates.count === 0 ? "Everything is up to date" : Updates.count + " updates waiting"
            hint: page.lastUpdate === "" ? "Repository packages only; AUR packages are not counted." : "Last update " + page.lastUpdate + ". Repository packages only; AUR packages are not counted."
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
