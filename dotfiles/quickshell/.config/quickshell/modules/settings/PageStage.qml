import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Stage mode page: the switch, and every size and look of the rail (modules/stage). Keys and ranges mirror settings.py
// RANGES. Turning the mode on switches every workspace to Hyprland's monocle layout; the rail shows the other windows
// of the workspace as thumbnail cards. Sub-controls of the off mode stay in place, dimmed and not interactive, so the
// layout never jumps (like the Windows page).
SettingsPage {
    id: page
    note: "A stage workspace opens windows one at a time, full size, instead of tiling them. The other windows of the workspace wait in a rail of small cards: click one to bring it to the front. Switch one workspace from the overview (until the next reboot); the switch here is the default for every workspace."


    SettingsSection {
        SettingToggle { label: "Stage mode by default"; hint: "Every workspace starts in stage mode. Changing it clears the per-workspace switches from the overview."; key: "stage.enabled" }
    }

    SettingsSection {
        title: "Rail"
        SettingChoice { label: "Side"; key: "stage.railPosition"; model: [{ value: "left", label: "Left" }, { value: "right", label: "Right" }] }
        SettingSlider { label: "Width"; key: "stage.railWidth"; from: 100; to: 320; step: 10; suffix: " px" }
        SettingSlider { label: "Padding"; key: "stage.railPadding"; from: 0; to: 32; step: 2; suffix: " px" }
        SettingSlider { label: "Background opacity"; key: "stage.railOpacity"; from: 0.0; to: 1.0; step: 0.05; percent: true }
        SettingToggle { label: "Reserve space for the rail"; hint: "Windows stop at the rail instead of sliding under it"; key: "stage.reserveSpace" }
        SettingToggle { label: "Show with a single window"; key: "stage.showWithOneWindow" }
    }

    SettingsSection {
        title: "Cards"
        SettingSlider { label: "Card height"; key: "stage.cardHeight"; from: 60; to: 240; step: 10; suffix: " px" }
        SettingSlider { label: "Gap between cards"; key: "stage.cardGap"; from: 0; to: 32; step: 2; suffix: " px" }
        SettingSlider { label: "Corner radius"; key: "stage.cardRadius"; from: 0; to: 24; step: 2; suffix: " px" }
        SettingToggle { label: "Show window title"; key: "stage.showTitle" }
        SettingToggle { label: "Show app icon"; key: "stage.showIcon" }
        SettingChoice { label: "Order"; key: "stage.order"; model: [{ value: "recent", label: "Most recent first" }, { value: "opened", label: "In opening order" }] }
        SettingToggle { label: "Animations"; key: "stage.animations" }
    }

    SettingsSection {
        title: "Previews"
        description: "Previews are still pictures, retaken when you switch windows and on this interval. Shorter intervals cost a little GPU and battery."
        SettingSlider { label: "Refresh every"; hint: "0 = only when you switch windows"; key: "stage.refreshSeconds"; from: 0; to: 30; step: 1; suffix: " s" }
    }
}
