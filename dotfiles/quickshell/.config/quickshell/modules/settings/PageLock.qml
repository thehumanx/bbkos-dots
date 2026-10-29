import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components
import qs.services
import "../../components/FileUrl.js" as FileUrl

// Lock screen page: a scaled preview of the lock screen (hyprlock) and the settings behind it. Click an element on the
// preview to edit it. Keys and ranges mirror bbkos_theme/settings.py (the lock section); bbkos-theme renders them into
// the hyprlock.conf that bbkos-lock starts. The password field is always shown.
SettingsPage {
    id: page
    card: true
    note: "The preview is an approximation of hyprlock. Positions are pixels from the screen centre (up is positive)."

    readonly property var aligns: [{ value: "left", label: "Left" }, { value: "center", label: "Center" }, { value: "right", label: "Right" }]
    readonly property var elements: [
        { id: "avatar", label: "Avatar", sizeLabel: "Diameter", from: 32, to: 300 },
        { id: "welcome", label: "Welcome text", sizeLabel: "Font size", from: 8, to: 200 },
        { id: "date", label: "Date", sizeLabel: "Font size", from: 8, to: 200 },
        { id: "time", label: "Time", sizeLabel: "Font size", from: 8, to: 200 },
        { id: "battery", label: "Battery", sizeLabel: "Font size", from: 8, to: 200 }
    ]

    // The avatar picture: lock.avatar is the copy `bbkos-theme avatar set` made, "" the shipped one. zenity's file dialog picks
    // it (it floats: Hyprland rule bbkos-misc-dialogs); the tool validates and copies the file, so nothing here reads it.
    readonly property string avatarPath: SettingsStore.shown("lock.avatar") ?? ""
    Process {
        id: chooser
        command: ["zenity", "--file-selection", "--title=Choose the lock screen picture",
                  "--filename=" + (Quickshell.env("HOME") ?? "") + "/Pictures/",
                  "--file-filter=Images | *.png *.jpg *.jpeg *.webp *.PNG *.JPG *.JPEG *.WEBP"]
        stdout: StdioCollector { id: chosen }
        onExited: code => { const f = chosen.text.trim(); if (code === 0 && f !== "") SettingsStore.setAvatar(f) }
    }

    LockPreview { id: preview; Layout.fillWidth: true; Layout.preferredHeight: width * monH / monW }

    // The real thing: bbkos-lock-test locks for 5 s, photographs the lock screen and unlocks by itself.
    property string capturePath: ""
    property int captureSerial: 0
    property string testStatus: ""
    Process {
        id: realTest
        command: ["bbkos-lock-test", "5"]
        stdout: StdioCollector { id: testOut }
        stderr: StdioCollector { id: testErr }
        onExited: code => {
            if (code === 0) { page.capturePath = testOut.text.trim(); page.captureSerial++; page.testStatus = "" }
            else page.testStatus = testErr.text.trim() !== "" ? testErr.text.trim() : "The test did not finish (exit " + code + ")"
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        Button {
            text: realTest.running ? "Locking for 5 s..." : "Test real lock (5 s)"
            enabled: !realTest.running
            onClicked: { page.testStatus = ""; realTest.running = true }
        }
        Txt {
            Layout.fillWidth: true
            text: page.testStatus !== "" ? page.testStatus : "Locks for 5 s, then unlocks by itself. Counts as a failed login: refused while any is on record (3 in 10 minutes lock the account)."
            color: page.testStatus !== "" ? Theme.crit : Theme.dim
            elide: Text.ElideRight
        }
    }
    Image {
        visible: page.capturePath !== ""
        Layout.fillWidth: true
        Layout.preferredHeight: width * preview.monH / preview.monW
        source: page.capturePath !== "" ? "file://" + page.capturePath + "?" + page.captureSerial : ""
        fillMode: Image.PreserveAspectFit
        cache: false
    }

    Chips {
        id: picker
        Layout.fillWidth: true
        model: [{ value: "avatar", label: "Avatar" }, { value: "welcome", label: "Welcome" }, { value: "date", label: "Date" },
                { value: "time", label: "Time" }, { value: "battery", label: "Battery" }, { value: "field", label: "Password field" }]
        current: preview.selected
        onChosen: v => preview.selected = v
    }
    Txt { visible: preview.selected === ""; text: "Click an element on the preview, or pick one above."; color: Theme.dim }

    Repeater {
        model: page.elements
        delegate: ColumnLayout {
            id: el
            required property var modelData
            visible: preview.selected === modelData.id
            Layout.fillWidth: true
            spacing: 12
            SettingToggle { label: "Show " + el.modelData.label.toLowerCase(); key: "lock." + el.modelData.id + "Show" }
            SettingRow {
                visible: el.modelData.id === "avatar"
                label: "Picture"
                hint: page.avatarPath === "" ? "The picture that came with bbkOS" : "Your picture (a copy, so the original can move)"
                Image {
                    Layout.preferredWidth: 40
                    Layout.preferredHeight: 40
                    source: FileUrl.toUrl(page.avatarPath !== "" ? page.avatarPath : (Quickshell.env("HOME") ?? "") + "/.config/hypr/lock-avatar.png")
                    fillMode: Image.PreserveAspectCrop
                    sourceSize: Qt.size(80, 80)
                }
                Item { Layout.fillWidth: true }
                Button { text: chooser.running ? "Choosing..." : "Choose picture..."; enabled: !chooser.running; onClicked: chooser.running = true }
                Button { visible: page.avatarPath !== ""; text: "Use the default"; onClicked: SettingsStore.clearAvatar() }
            }
            SettingChoice { label: "Align"; key: "lock." + el.modelData.id + "Align"; model: page.aligns }
            SettingSlider { label: "X (right)"; key: "lock." + el.modelData.id + "X"; from: -1200; to: 1200; step: 1
                enabled: SettingsStore.shown("lock." + el.modelData.id + "Align") === "center" }
            SettingSlider { label: "Y (up)"; key: "lock." + el.modelData.id + "Y"; from: -1200; to: 1200; step: 1 }
            SettingSlider { label: el.modelData.sizeLabel; key: "lock." + el.modelData.id + "Size"; from: el.modelData.from; to: el.modelData.to; step: 1 }
        }
    }

    ColumnLayout {
        visible: preview.selected === "field"
        Layout.fillWidth: true
        spacing: 12
        SettingChoice { label: "Align"; key: "lock.fieldAlign"; model: page.aligns }
        SettingSlider { label: "X (right)"; key: "lock.fieldX"; from: -600; to: 600; step: 1
            enabled: SettingsStore.shown("lock.fieldAlign") === "center" }
        SettingSlider { label: "Y (up)"; key: "lock.fieldY"; from: -500; to: 500; step: 1; suffix: " px" }
        SettingSlider { label: "Width"; key: "lock.fieldWidth"; from: 120; to: 800; step: 1; suffix: " px" }
        SettingSlider { label: "Height"; key: "lock.fieldHeight"; from: 30; to: 120; step: 1; suffix: " px" }
        SettingSlider { label: "Corner radius (-1 = pill)"; key: "lock.fieldRadius"; from: -1; to: 60; step: 1 }
        SettingSlider { label: "Fill opacity"; key: "lock.fieldOpacity"; from: 0.0; to: 1.0; step: 0.02; percent: true }
    }

    Txt { text: "Layout"; color: Theme.dim; font.bold: true }
    SettingSlider { label: "Left / right margin"; key: "lock.edgeMargin"; from: 0; to: 40; step: 1; suffix: "%" }

    Txt { text: "Background"; color: Theme.dim; font.bold: true }
    SettingSlider { label: "Blur passes"; key: "lock.blurPasses"; from: 0; to: 5; step: 1 }
    SettingSlider { label: "Blur size"; key: "lock.blurSize"; from: 1; to: 15; step: 1 }
    SettingToggle { label: "Keep text readable"; hint: "Dims a bright wallpaper until the text reads at 4.5:1 (WCAG)"; key: "lock.autoDim" }
    SettingSlider { label: "Brightness"; hint: "The most the lock screen may show; lower when the wallpaper needs it"; key: "lock.brightness"; from: 0.2; to: 1.0; step: 0.05 }

    Txt { text: "Text"; color: Theme.dim; font.bold: true }
    SettingText { label: "Font"; key: "lock.font"; placeholder: "JetBrainsMono Nerd Font" }
    SettingText { label: "Text colour"; key: "lock.textColor"; placeholder: "#f0f0f0" }
    SettingText { label: "Welcome text"; key: "lock.welcomeText"; placeholder: "Welcome $USER" }
    SettingChoice { label: "Time format"; key: "lock.timeFormat"; model: [{ value: "24h", label: "24-hour" }, { value: "12h", label: "12-hour" }] }
    SettingChoice { label: "Date format"; key: "lock.dateFormat"; model: [
        { value: "weekday-long", label: "Monday, 19 October 2026" }, { value: "weekday-short", label: "Mon 19 Oct" },
        { value: "numeric", label: "19/10/2026" }] }
}
