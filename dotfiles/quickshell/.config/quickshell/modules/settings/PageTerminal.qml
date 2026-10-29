import QtQuick
import qs
import qs.components

// Terminal page: kitty font size, padding and opacity. Keys and ranges mirror settings.py RANGES.
SettingsPage {
    note: "Changes reach running kitty windows through a config reload."

    SettingsSection {
        title: "kitty"
        SettingSlider { label: "Font size"; key: "terminal.fontSize"; from: 8; to: 20; step: 1; suffix: " pt" }
        SettingSlider { label: "Padding"; hint: "Space between the text and the window edge"; key: "terminal.padding"; from: 0; to: 24; step: 1; suffix: " px" }
        SettingSlider { label: "Opacity"; hint: "Below 100% the wallpaper shows through the terminal"; key: "terminal.opacity"; from: 0.6; to: 1.0; step: 0.05; percent: true }
    }
}
