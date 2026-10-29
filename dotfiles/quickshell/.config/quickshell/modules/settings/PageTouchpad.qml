import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Touchpad tab (Mouse and touchpad): pointer, scrolling, tapping and clicking. The swipes are on the Gestures tab
// (PageGestures). Keys and ranges mirror settings.py RANGES. Changes apply live through bbkos-theme (hypr-theme.lua).
SettingsPage {
    id: page
    note: "Changes apply straight away. The pointer speed is on the Mouse and cursor tab."

    SettingsSection {
        title: "Pointer and scrolling"
        SettingToggle { label: "Natural scroll"; key: "touchpad.naturalScroll" }
        SettingSlider { label: "Scroll speed"; key: "touchpad.scrollFactor"; from: 0.1; to: 2.0; step: 0.1; suffix: "×" }
        SettingChoice { label: "Scroll method"; key: "touchpad.scrollMethod"; model: [
            { value: "auto", label: "Auto" }, { value: "2fg", label: "Two fingers" }, { value: "edge", label: "Edge" },
            { value: "on_button_down", label: "Button held" }, { value: "no_scroll", label: "Off" }] }
        SettingToggle { label: "Flip horizontal"; key: "touchpad.flipX" }
        SettingToggle { label: "Flip vertical"; key: "touchpad.flipY" }
    }

    SettingsSection {
        title: "Tapping and clicking"
        SettingToggle { label: "Tap to click"; key: "touchpad.tapToClick" }
        SettingToggle { label: "Tap and drag"; key: "touchpad.tapAndDrag" }
        SettingChoice {
            label: "Drag lock"; hint: "Lifting the finger during a tap-and-drag does not drop what you drag"; key: "touchpad.dragLock"
            model: [{ value: 0, label: "Off" }, { value: 1, label: "Until a short pause" }, { value: 2, label: "Until the next tap" }]
        }
        SettingChoice {
            label: "Drag with fingers"; hint: "Drag by moving fingers on the pad, without a click or a tap first"; key: "touchpad.drag3fg"
            model: [{ value: 0, label: "Off" }, { value: 1, label: "Three fingers" }, { value: 2, label: "Four fingers" }]
        }
        SettingChoice { label: "Tap button map"; key: "touchpad.tapButtonMap"; model: [
            { value: "auto", label: "Auto" }, { value: "lrm", label: "1, 2, 3 fingers = L, R, M" },
            { value: "lmr", label: "1, 2, 3 fingers = L, M, R" }] }
        SettingToggle { label: "Clickfinger buttons"; key: "touchpad.clickfingerBehavior" }
        SettingToggle { label: "Middle button emulation"; key: "touchpad.middleButtonEmulation" }
        SettingToggle { label: "Disable while typing"; key: "touchpad.disableWhileTyping" }
    }
}
