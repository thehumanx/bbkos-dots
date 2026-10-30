import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Appearance > Style: popup geometry, motion and shadow, text (grid mode moved to bbkOS > Grid mode, PageGrid, 2026-10-31). Keys and ranges mirror bbkos_theme/settings.py RANGES
// (sizes step 2). The display scale moved to the Displays page on 2026-10-28.
// The font list is a short candidate list filtered to the families Qt reports as installed (Qt.fontFamilies()),
// plus the current value, so a font set elsewhere never vanishes from the chips.
SettingsPage {
    id: page
    note: ""

    readonly property var candidates: ["Adwaita Sans", "JetBrainsMono Nerd Font", "FiraCode Nerd Font", "Hack Nerd Font",
        "CaskaydiaCove Nerd Font", "Iosevka Nerd Font", "Noto Sans Mono", "DejaVu Sans Mono", "Liberation Mono"]
    readonly property var installed: Qt.fontFamilies()
    readonly property var fonts: {
        const list = candidates.filter(f => installed.indexOf(f) >= 0)
        const cur = SettingsStore.shown("shell.font")
        if (typeof cur === "string" && cur !== "" && list.indexOf(cur) < 0) list.push(cur)
        return list
    }

    SettingsSection {
        title: "Shape"
        SettingSlider { label: "Gap"; hint: "Between the bar, panels and the screen edge"; key: "shell.gap"; from: 0; to: 32; step: 2; suffix: " px" }
        SettingSlider { label: "Popup radius"; hint: "Corners of popups and cards"; key: "shell.radius"; from: 0; to: 24; step: 2; suffix: " px" }
        SettingSlider { label: "Control radius"; hint: "Corners of buttons and rows"; key: "shell.controlRadius"; from: 0; to: 16; step: 2; suffix: " px" }
    }

    SettingsSection {
        title: "Motion and depth"
        SettingToggle { label: "Reduce motion"; hint: "Fades only: popups, cards, windows and workspaces do not grow or slide"; key: "shell.reduceMotion" }
        SettingSlider { label: "Popup shadow"; hint: "Tinted shadow under popups, notifications and the OSD (0 = none)"; key: "shell.popupShadow"; from: 0; to: 1; step: 0.05; percent: true }
    }

    SettingsSection {
        title: "Text"
        SettingSlider { label: "Font size"; key: "shell.fontSize"; from: 10; to: 20; step: 1; suffix: " px" }
        SettingChoice { label: "Font"; hint: "Each name is shown in its own font"; key: "shell.font"; model: page.fonts.map(f => ({ value: f, label: f, font: f })) }
    }
}
