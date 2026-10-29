import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Gestures tab (Mouse and touchpad): the workspace swipe and what each multi-finger swipe does. Keys mirror settings.py
// (touchpad.wsSwipe*, touchpad.swipe*). The three-finger left and right swipes are the built-in workspace swipe and cannot
// be remapped, so the list offers up and down for three fingers and all four for four. Swipe up/down can open or close the
// workspace overview (modules/overview); left/right remains Hyprland's own workspace swipe whether the overview is open or
// not (the overview follows the change instead, with a slide). Each swipe is a compact choice: the current action, and the
// eight actions only while it is open.
SettingsPage {
    id: page
    note: "Three fingers left and right always switch workspaces (the overview follows the change)."

    readonly property var swipeActions: [
        { value: "none", label: "None" }, { value: "workspace", label: "Switch workspace" },
        { value: "close", label: "Close window" }, { value: "fullscreen", label: "Fullscreen" },
        { value: "float", label: "Float toggle" }, { value: "special", label: "Scratchpad" },
        { value: "overview", label: "Overview" }, { value: "overview-close", label: "Close overview" }]

    SettingsSection {
        title: "Swipes"
        SettingChoice { label: "3 fingers swipe up"; key: "touchpad.swipe3Up"; model: page.swipeActions; compact: true }
        SettingChoice { label: "3 fingers swipe down"; key: "touchpad.swipe3Down"; model: page.swipeActions; compact: true }
        SettingChoice { label: "4 fingers swipe up"; key: "touchpad.swipe4Up"; model: page.swipeActions; compact: true }
        SettingChoice { label: "4 fingers swipe down"; key: "touchpad.swipe4Down"; model: page.swipeActions; compact: true }
        SettingChoice { label: "4 fingers swipe left"; key: "touchpad.swipe4Left"; model: page.swipeActions; compact: true }
        SettingChoice { label: "4 fingers swipe right"; key: "touchpad.swipe4Right"; model: page.swipeActions; compact: true }
    }

    SettingsSection {
        title: "Workspace swipe"
        description: "Three fingers left and right."
        SettingSlider { label: "Swipe distance"; key: "touchpad.wsSwipeDistance"; from: 50; to: 2000; step: 10; suffix: " px" }
        SettingSlider { label: "Cancel point"; key: "touchpad.wsSwipeCancelRatio"; from: 0.0; to: 1.0; step: 0.05; percent: true }
        SettingToggle { label: "Invert swipe"; key: "touchpad.wsSwipeInvert" }
        SettingToggle { label: "Lock swipe direction"; key: "touchpad.wsSwipeDirectionLock" }
        SettingToggle { label: "New workspace at the end"; key: "touchpad.wsSwipeCreateNew" }
        SettingToggle { label: "Swipe past the first and last"; key: "touchpad.wsSwipeForever" }
    }
}
