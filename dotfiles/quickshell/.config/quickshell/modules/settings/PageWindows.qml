import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Windows page: Hyprland gaps, border, rounding, opacity and effects. Keys and ranges mirror settings.py RANGES.
// Sub-controls of an off toggle stay in place, dimmed and not interactive (enabled: false disables the whole row,
// slider, value and stepper; SettingSlider dims each part once to 0.4, so no row opacity here), so the layout never jumps.
SettingsPage {
    id: page
    note: "Blur, shadow and animations use the GPU and battery. Not measured yet: compare with them off on battery."

    readonly property bool shadowOn: SettingsStore.shown("windows.shadowEnabled") === true
    readonly property bool blurOn: SettingsStore.shown("windows.blurEnabled") === true
    readonly property bool borderOn: (SettingsStore.shown("windows.borderSize") ?? 0) > 0
    readonly property bool resizeOn: SettingsStore.shown("windows.resizeOnBorder") === true

    SettingsSection {
        title: "Layout"
        SettingSlider { label: "Gaps inside"; hint: "Between windows"; key: "windows.gapsIn"; from: 0; to: 20; step: 1; suffix: " px" }
        SettingSlider { label: "Gaps outside"; hint: "Between windows and the screen edge"; key: "windows.gapsOut"; from: 0; to: 40; step: 1; suffix: " px" }
        SettingSlider { label: "Border size"; key: "windows.borderSize"; from: 0; to: 8; step: 1; suffix: " px" }
        SettingToggle { label: "Highlight active window"; hint: "Off: the focused window's border looks like the others"; key: "windows.activeBorder"; enabled: page.borderOn }
        SettingSlider { label: "Rounding"; hint: "Window corner radius"; key: "windows.rounding"; from: 0; to: 24; step: 1; suffix: " px" }
    }

    SettingsSection {
        title: "Opacity"
        SettingSlider { label: "Active window"; key: "windows.activeOpacity"; from: 0.6; to: 1.0; step: 0.05; percent: true }
        SettingSlider { label: "Inactive windows"; key: "windows.inactiveOpacity"; from: 0.6; to: 1.0; step: 0.05; percent: true }
    }

    SettingsSection {
        title: "Effects"
        SettingToggle { label: "Shadow"; key: "windows.shadowEnabled" }
        SettingSlider { label: "Shadow range"; key: "windows.shadowRange"; from: 0; to: 20; step: 1; enabled: page.shadowOn; suffix: " px" }
        SettingToggle { label: "Blur"; hint: "Blurs what is behind translucent windows"; key: "windows.blurEnabled" }
        SettingSlider { label: "Blur size"; key: "windows.blurSize"; from: 1; to: 12; step: 1; enabled: page.blurOn }
        SettingSlider { label: "Blur passes"; key: "windows.blurPasses"; from: 1; to: 4; step: 1; enabled: page.blurOn }
        SettingToggle { label: "Animations"; key: "windows.animations" }
        SettingSlider { label: "Animation speed"; hint: "Windows and workspaces: 1 is the default, higher is quicker"; key: "windows.animationSpeed"; from: 0.5; to: 2.0; step: 0.1; suffix: "×" }
    }

    SettingsSection {
        title: "Resizing"
        SettingToggle { label: "Resize by dragging borders"; key: "windows.resizeOnBorder" }
        SettingSlider { label: "Border grab area"; hint: "How far outside the border still grabs it"; key: "windows.borderGrabArea"; from: 0; to: 30; step: 1; enabled: page.resizeOn; suffix: " px" }
    }
}
