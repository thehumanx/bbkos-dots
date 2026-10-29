import QtQuick
import qs
import qs.components

// Keyboard > Typing: layout, Caps Lock, key repeat and Num Lock. Keys mirror settings.py (keyboard.*); bbkos-theme renders
// them into the input block of hypr-theme.lua (docs/modules/input.md). Shortcuts are the other tab (PageKeybindings).
SettingsPage {
    note: "Changes apply at once. Use xkb names for the layout, for example us or us,np (the first is active)."

    SettingsSection {
        title: "Layout and keys"
        SettingText { label: "Layout"; hint: "xkb layout names, comma separated"; key: "keyboard.layout" }
        SettingText { label: "Variant"; hint: "Optional, for example dvorak. One per layout, comma separated"; key: "keyboard.variant" }
        SettingChoice {
            label: "Caps Lock"; hint: "A common remap for the Caps Lock key"; key: "keyboard.options"
            model: [{ value: "none", label: "Normal" }, { value: "caps:escape", label: "Escape" },
                    { value: "ctrl:nocaps", label: "Ctrl" }, { value: "ctrl:swapcaps", label: "Swap with Ctrl" }]
        }
        SettingSlider { label: "Repeat rate"; hint: "Keys per second while a key is held"; key: "keyboard.repeatRate"; from: 10; to: 60; step: 1; suffix: "/s" }
        SettingSlider { label: "Repeat delay"; hint: "Milliseconds before a held key starts repeating"; key: "keyboard.repeatDelay"; from: 150; to: 1000; step: 50; suffix: " ms" }
        SettingToggle { label: "Num Lock on at login"; key: "keyboard.numlock" }
    }
}
