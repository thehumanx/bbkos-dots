import QtQuick
import qs
import qs.components
import qs.services

// Bar > Layout: where the bar sits and how big it is, whether it floats or hugs its widgets, and the order of the widgets
// (BarLayoutEditor). Keys and ranges mirror bbkos_theme/settings.py RANGES (docs/modules/bar.md).
SettingsPage {
    id: page

    SettingsSection {
        title: "Position and size"
        SettingChoice { label: "Position"; key: "shell.barPosition"; model: [
            { value: "top", label: "Top" }, { value: "bottom", label: "Bottom" },
            { value: "left", label: "Left" }, { value: "right", label: "Right" }] }
        SettingSlider { label: "Thickness"; key: "shell.barHeight"; from: 24; to: 48; step: 2; suffix: " px" }
        SettingSlider { label: "Widget gap"; hint: "Space between widgets"; key: "shell.barItemGap"; from: 0; to: 32; step: 2; suffix: " px" }
    }

    SettingsSection {
        title: "Floating and hugging"
        SettingSlider { label: "Space around the bar"; hint: "Lifts the bar off the screen edge so it floats; 0 attaches it"; key: "shell.barFloat"; from: 0; to: 24; step: 2; suffix: " px" }
        SettingSlider { label: "Corner radius"; hint: "Rounds the bar's corners (never more than half its thickness)"; key: "shell.barRadius"; from: 0; to: 24; step: 2; suffix: " px" }
        SettingToggle { label: "Hug the widgets"; hint: "The bar is only as long as its widgets and sits in the middle of the edge"; key: "shell.barHug" }
    }

    SettingsSection {
        title: "Widget order and sections"
        description: "Drag a widget by its grip onto another widget, or use the Left, Centre and Right buttons."
        padded: true
        BarLayoutEditor { scroller: page }
    }
}
