import QtQuick
import qs
import qs.components

// Accessibility page: the settings that make the desktop easier to see and to use, gathered from the other pages (the same keys,
// so a change here shows there). Nothing new is stored: shell.*, windows.*, colors.contrast, keyboard.*, cursor.* and terminal.*.
SettingsPage {
    note: "The same settings as on their own pages, gathered here. Each row links to its page."

    SettingsSection {
        title: "Motion"
        SettingToggle { label: "Reduce motion"; hint: "Panels and windows fade instead of sliding and popping"; key: "shell.reduceMotion"; link: "appearance/style" }
        SettingToggle { label: "Window animations"; hint: "Off: windows and workspaces change at once"; key: "windows.animations"; link: "windows/look#Animations" }
    }
    SettingsSection {
        title: "Seeing"
        SettingSlider { label: "Contrast"; hint: "Raises the contrast of the colours made from the wallpaper"; key: "colors.contrast"; link: "appearance/wallpaper"; from: -1; to: 1; step: 0.1 }
        SettingSlider { label: "Interface text size"; key: "shell.fontSize"; link: "appearance/style#Font size"; from: 10; to: 20; step: 1; suffix: " px" }
        SettingSlider { label: "Terminal text size"; key: "terminal.fontSize"; link: "appearance/terminal#Font size"; from: 8; to: 20; step: 1; suffix: " pt" }
        SettingSlider { label: "Cursor size"; key: "cursor.size"; link: "mouse/mouse#Size"; from: 16; to: 48; step: 2; suffix: " px" }
    }
    SettingsSection {
        title: "Typing"
        SettingSlider { label: "Key repeat delay"; hint: "Milliseconds before a held key repeats; longer is easier with slow fingers"; key: "keyboard.repeatDelay"; link: "keyboard/typing#Repeat delay"; from: 150; to: 1000; step: 50; suffix: " ms" }
        SettingSlider { label: "Key repeat rate"; key: "keyboard.repeatRate"; link: "keyboard/typing#Repeat rate"; from: 10; to: 60; step: 1; suffix: "/s" }
    }
}
