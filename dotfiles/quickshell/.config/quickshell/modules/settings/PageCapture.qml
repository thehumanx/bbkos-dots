import QtQuick
import qs
import qs.components
import qs.services

// Capture page: screenshots (omasnap, docs/modules/capture.md). Keys and values mirror settings.py `capture.*`;
// bbkos-theme writes them into ~/.config/omasnap/omasnap.conf on every apply, omasnap reads the file when it starts.
SettingsPage {
    id: page
    readonly property bool cameraOn: SettingsStore.shown("capture.recordCamera") === true

    note: "Screenshots, OCR and screen recording. Super+Shift+S opens the selector: drag a region, click a window, or click empty space for the whole screen."

    SettingsSection {
        title: "Screenshots"
        SettingToggle {
            label: "Save screenshots by default"
            hint: "On: every capture is copied and saved. Off: copied only; save one from its preview or the editor."
            key: "capture.autosave"
        }
        SettingText {
            label: "Save folder"
            hint: "A path under your home (~/...) or absolute"
            key: "capture.directory"
            placeholder: "~/Pictures/Screenshots"
        }
        SettingChoice {
            label: "Editor"
            hint: "Fullscreen overlay, or a normal window you can put beside others"
            key: "capture.editorMode"
            model: [{ value: "overlay", label: "Fullscreen overlay" }, { value: "window", label: "Window" }]
        }
    }

    SettingsSection {
        title: "Screen recording"
        description: "Super+Shift+R stops a running recording, or opens the options panel when none is running. A red timer in the bar also stops it."
        SettingChoice {
            label: "What to record"
            key: "capture.recordArea"
            model: [{ value: "region", label: "Select a region" }, { value: "screen", label: "Whole screen" }]
        }
        SettingChoice {
            label: "Sound"
            hint: "Computer and microphone are mixed into one track"
            key: "capture.recordAudio"
            model: [{ value: "none", label: "None" }, { value: "desktop", label: "Computer" },
                    { value: "mic", label: "Microphone" }, { value: "both", label: "Both" }]
        }
        SettingToggle { label: "Camera in the corner"; hint: "A small window you can drag while recording"; key: "capture.recordCamera" }
        SettingChoice {
            label: "Camera size"
            key: "capture.recordCameraSize"
            model: [{ value: "small", label: "Small" }, { value: "medium", label: "Medium" }, { value: "large", label: "Large" }]
            enabled: page.cameraOn
        }
        SettingToggle { label: "Mirror the camera"; hint: "Like a video call: your right is on the right"; key: "capture.recordCameraMirror"; enabled: page.cameraOn }
        SettingChoice {
            label: "Quality"
            hint: "Higher uses more disk space"
            key: "capture.recordQuality"
            model: [{ value: "medium", label: "Medium" }, { value: "high", label: "High" },
                    { value: "very_high", label: "Very high" }, { value: "ultra", label: "Ultra" }]
        }
        SettingChoice { label: "Frames per second"; key: "capture.recordFps"; model: [{ value: 30, label: "30 fps" }, { value: 60, label: "60 fps" }] }
        SettingText { label: "Save folder"; hint: "A path under your home (~/...) or absolute"; key: "capture.recordDirectory"; placeholder: "~/Videos" }
    }

    SettingsSection {
        title: "Keys"
        description: "Super+Shift+S: select a region or window (press again to cancel). Super+Shift+R: recording. Super+;: emoji picker. Change keys in Keyboard › Shortcuts. In the screenshot editor, O copies all the text in the image (OCR), D redacts, Enter copies and saves."
    }
}
