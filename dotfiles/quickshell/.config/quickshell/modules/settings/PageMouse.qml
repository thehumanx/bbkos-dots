import QtQuick
import qs
import qs.components
import qs.services

// Mouse and touchpad > Mouse and cursor: pointer speed and buttons (mouse.*), the cursor's size and theme (cursor.*) and when
// it hides or moves by itself (behavior.*). bbkos-theme renders them into hypr-theme.lua and changes the running cursor
// (docs/modules/input.md, behavior.md). Made 2026-10-28 from the Keyboard and mouse page and the Window behaviour page.
SettingsPage {
    note: "Changes apply at once."

    SettingsSection {
        title: "Mouse"
        SettingSlider { label: "Pointer speed"; hint: "0 is the device's own speed. Also applies to the touchpad"; key: "mouse.sensitivity"; from: -1; to: 1; step: 0.1 }
        SettingChoice {
            label: "Acceleration"; hint: "Flat moves the pointer the same distance at any speed"; key: "mouse.accelProfile"
            model: [{ value: "default", label: "Default" }, { value: "adaptive", label: "Adaptive" }, { value: "flat", label: "Flat" }]
        }
        SettingToggle { label: "Natural scrolling"; hint: "Content follows the wheel, like a touchscreen. The touchpad has its own switch"; key: "mouse.naturalScroll" }
        SettingToggle { label: "Left-handed"; hint: "Swaps the left and right buttons"; key: "mouse.leftHanded" }
    }

    SettingsSection {
        title: "Cursor"
        SettingSlider { label: "Size"; hint: "Applies to running apps at once, and to new ones"; key: "cursor.size"; from: 16; to: 48; step: 2; suffix: " px" }
        SettingText { label: "Theme"; hint: "Name of an installed cursor theme"; key: "cursor.theme" }
        SettingToggle { label: "Hide while typing"; hint: "Until the mouse moves"; key: "behavior.hideCursorWhenTyping" }
        SettingSlider { label: "Hide when still"; hint: "Seconds without movement; 0 never hides it"; key: "behavior.cursorHideAfter"; from: 0; to: 20; step: 1; suffix: " s" }
        SettingToggle { label: "Cursor follows focus"; hint: "Off: keys and clicks that change focus never move the cursor"; key: "behavior.cursorWarps" }
    }
}
