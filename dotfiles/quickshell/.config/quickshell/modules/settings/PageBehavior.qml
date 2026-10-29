import QtQuick
import qs
import qs.components
import qs.services

// Windows > Behaviour: how focus, workspaces and floating windows act (the cursor rows are on Mouse and touchpad since
// 2026-10-28). Keys mirror settings.py (behavior.*);
// bbkos-theme renders them into hypr-theme.lua as Hyprland options (docs/modules/behavior.md).
SettingsPage {
    note: "Changes apply at once."

    SettingsSection {
        title: "Focus"
        SettingChoice {
            label: "Focus"; hint: "Which window gets the keyboard when you move the mouse or click"; key: "behavior.followMouse"
            model: [{ value: "hover", label: "Follows the mouse" }, { value: "click", label: "Click to focus" },
                    { value: "detached", label: "Separate until you click" }]
        }
        SettingToggle {
            label: "Let apps take focus"; hint: "An app that asks to be focused is brought forward, as a browser sign-in does. A background app could take your typing too"
            key: "behavior.focusOnActivate"
        }
    }
    SettingsSection {
        title: "Workspaces"
        SettingToggle { label: "Switch back"; hint: "Choosing the workspace you are on goes to the previous one"; key: "behavior.workspaceBackAndForth" }
    }
    SettingsSection {
        title: "Floating windows"
        SettingToggle { label: "Snap to edges"; hint: "A floating window you drag sticks to nearby windows and screen edges"; key: "behavior.snap" }
        SettingSlider { label: "Snap distance"; key: "behavior.snapGap"; from: 0; to: 100; step: 5; enabled: SettingsStore.shown("behavior.snap") === true; suffix: " px" }
    }
}
