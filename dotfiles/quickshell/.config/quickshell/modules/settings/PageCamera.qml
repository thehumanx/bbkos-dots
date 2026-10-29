import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components
import qs.services

// Camera page: the webcam's picture controls (docs/modules/camera.md). Keys and ranges mirror settings.py `camera.*`;
// bbkos-theme sets them on the camera with v4l2-ctl on every change, and bbkos-camera.service re-applies them each time
// an app opens the camera. Changes show at once in an open video call.
SettingsPage {
    id: page
    readonly property bool manualExposure: SettingsStore.shown("camera.exposure") === "manual"
    readonly property bool manualBalance: SettingsStore.shown("camera.whiteBalance") === "manual"

    note: "The laptop camera's picture controls. Turn on the live preview below, or open a video call, and change a value to see it live."

    // The preview is `bbkos-camera preview`: it runs for as long as the window is open, so stopping the process closes it.
    // It ends by itself when the page goes away.
    property string previewError: ""
    Process {
        id: previewProc
        command: ["bbkos-camera", "preview"]
        stderr: StdioCollector { id: previewErr }
        onExited: code => {
            page.previewError = code === 0 ? "" : previewErr.text.trim()
            if (page.tunePending) { page.tunePending = false; tuneProc.running = true }
        }
    }
    // "Tune for this light" is `bbkos-camera tune`: it needs the camera to itself, so a running preview is stopped first and
    // comes back afterwards. It prints one JSON line and has already saved the settings (they show in the sliders).
    property string tuneStatus: ""
    property bool tunePending: false
    property bool resumePreview: false
    function startTune() {
        tuneStatus = ""
        resumePreview = previewProc.running
        if (previewProc.running) { tunePending = true; previewProc.running = false }
        else tuneProc.running = true
    }
    Process {
        id: tuneProc
        command: ["bbkos-camera", "tune"]
        stdout: StdioCollector { id: tuneOut }
        stderr: StdioCollector { id: tuneErr }
        onExited: code => {
            if (code !== 0) page.tuneStatus = tuneErr.text.trim() !== "" ? tuneErr.text.trim() : "Tuning did not finish"
            else {
                let r = {}
                try { r = JSON.parse(tuneOut.text) } catch (e) { }
                page.tuneStatus = "Set exposure time " + (r.exposureTime / 10).toFixed(1) + " ms, gamma " + r.gamma
                    + (r.tooDark ? ". Still dark: this room needs more light on your face" : r.slowFrames ? ". Slow exposure: the frame rate may drop to about 12" : "")
            }
            if (page.resumePreview) { page.resumePreview = false; previewProc.running = true }
        }
    }
    onVisibleChanged: if (!visible) { previewProc.running = false; tuneProc.running = false }
    Component.onDestruction: { previewProc.running = false; tuneProc.running = false }

    SettingsSection {
        title: "Preview"
        description: "A small window beside this one shows what the camera sends, mirrored like a call's self-view. The settings window moves aside while it is open."
        SettingRow {
            label: "Live preview"
            hint: page.previewError !== "" ? page.previewError : "Closes when you leave this tab. Only one program can use the camera at a time"
            Item { Layout.fillWidth: true }
            Toggle {
                checked: previewProc.running
                onToggled: v => { page.previewError = ""; previewProc.running = v }
            }
        }
    }

    SettingsSection {
        title: "Light"
        description: "A bright window behind you makes automatic exposure expose for the window and your face goes dark. Manual exposure keeps your face lit whatever is behind."
        SettingRow {
            label: "Tune for this light"
            hint: tuneProc.running ? "Measuring the picture, about 15 seconds. Sit where you sit in a call"
                  : page.tuneStatus !== "" ? page.tuneStatus
                  : "Sets manual exposure (and gamma if the room is dark) so your face is lit. Run it again when the light changes"
            Item { Layout.fillWidth: true }
            Button {
                text: tuneProc.running || page.tunePending ? "Tuning..." : "Tune"
                enabled: !tuneProc.running && !page.tunePending
                onClicked: page.startTune()
            }
        }
        SettingChoice {
            label: "Exposure"
            hint: "Automatic follows the whole picture; manual stays fixed"
            key: "camera.exposure"
            model: [{ value: "auto", label: "Automatic" }, { value: "manual", label: "Manual" }]
        }
        SettingSlider {
            label: "Exposure time"
            hint: "Longer is brighter but blurs movement"
            key: "camera.exposureTime"; from: 3; to: 1250; step: 1; factor: 0.1; decimals: 1; suffix: " ms"
            enabled: page.manualExposure
        }
        SettingChoice {
            label: "Backlight compensation"; hint: "Automatic exposure favours the centre"; key: "camera.backlight"; enabled: !page.manualExposure
            model: [{ value: 0, label: "Off" }, { value: 1, label: "Some" }, { value: 2, label: "Strongest" }]
        }
        SettingSlider { label: "Brightness"; key: "camera.brightness"; from: 0; to: 255; step: 1 }
        SettingSlider { label: "Gamma"; hint: "Higher lifts the shadows"; key: "camera.gamma"; from: 90; to: 150; step: 1 }
        SettingSlider { label: "Contrast"; key: "camera.contrast"; from: 0; to: 100; step: 1 }
    }

    SettingsSection {
        title: "Colour and detail"
        SettingChoice {
            label: "White balance"
            key: "camera.whiteBalance"
            model: [{ value: "auto", label: "Automatic" }, { value: "manual", label: "Manual" }]
        }
        SettingSlider {
            label: "Colour temperature"
            hint: "Lower is warmer, higher is cooler"
            key: "camera.whiteBalanceTemp"; from: 2800; to: 6500; step: 100; suffix: " K"
            enabled: page.manualBalance
        }
        SettingSlider { label: "Saturation"; key: "camera.saturation"; from: 0; to: 100; step: 1 }
        SettingSlider { label: "Sharpness"; key: "camera.sharpness"; from: 0; to: 7; step: 1 }
    }

    SettingsSection {
        title: "Frame rate and flicker"
        SettingToggle {
            label: "Keep the frame rate steady"
            hint: "Off lets the camera drop to a few frames per second in dim light, which smears the picture"
            key: "camera.steadyFramerate"
        }
        SettingChoice {
            label: "Mains frequency"
            hint: "Stops lights flickering in the picture. 50 Hz in Europe, Asia and most of the world, 60 Hz in the Americas"
            key: "camera.powerLine"
            model: [{ value: "off", label: "Off" }, { value: "50hz", label: "50 Hz" }, { value: "60hz", label: "60 Hz" }]
        }
    }
}
