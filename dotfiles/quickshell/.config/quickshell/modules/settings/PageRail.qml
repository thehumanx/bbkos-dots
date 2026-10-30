import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// bbkOS > Rail and pinned apps (docs/modules/dock.md): where the rail sits and how it looks; it carries the pinned apps and,
// on a stage workspace, the window cards (their settings are on bbkOS > Stage mode). Moved from Windows > Stage mode on 2026-10-31.
SettingsPage {
    id: page
    note: "The rail is a strip along one screen edge with your pinned apps and, on a stage workspace, the other windows. Pin an app with the + tile; hover a tile and click × to unpin it."

    SettingsSection {
        SettingToggle { label: "Pinned apps"; hint: "App tiles at the start of the rail, on every workspace"; key: "stage.dock" }
        SettingChoice { label: "Side"; key: "stage.railPosition"; model: [{ value: "left", label: "Left" }, { value: "right", label: "Right" }, { value: "top", label: "Top" }, { value: "bottom", label: "Bottom" }] }
        SettingSlider { label: "Thickness"; hint: "Of a side rail; on the top or bottom the rail is one row of tiles"; key: "stage.railWidth"; from: 100; to: 320; step: 10; suffix: " px" }
        SettingToggle { label: "Hug its contents"; hint: "Only as long as its tiles and cards, like a hugging bar"; key: "stage.railHug" }
        SettingChoice { label: "Alignment"; hint: "Where the tiles and cards sit along the rail; when hugging, where the rail sits"; key: "stage.railAlign"; model: [{ value: "start", label: "Start" }, { value: "centre", label: "Centre" }, { value: "end", label: "End" }] }
        SettingSlider { label: "Padding"; key: "stage.railPadding"; from: 0; to: 32; step: 2; suffix: " px" }
        SettingSlider { label: "Background opacity"; key: "stage.railOpacity"; from: 0.0; to: 1.0; step: 0.05; percent: true; lockedBy: "the bar style" }
        SettingToggle { label: "Reserve space for the rail"; hint: "Windows stop at the rail instead of sliding under it"; key: "stage.reserveSpace" }
    }
}
