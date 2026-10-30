import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// bbkOS > Grid mode (docs/modules/grid-mode.md): the switch for the flat cell look and its one option. Moved here from
// Appearance > Style on 2026-10-31, so what is particular to bbkOS is on one page.
SettingsPage {
    id: page
    note: "Flat cells with hairline borders on the bar, the rail and the screen edges. Windows keep your margin and corner radius. The gap, radius and shadow settings it replaces show \"Set by grid mode\"; your values return when it is off."

    SettingsSection {
        SettingToggle { label: "Grid mode"; hint: "Flat cells with no gaps, no rounded corners and hairline borders, on the bar, windows and stage previews. Overrides the gap, radius and shadow settings while on; your values return when it is off"; key: "shell.gridMode" }
        SettingToggle { label: "Round popups and controls in grid mode"; hint: "Grid mode keeps the corners of popups, buttons and controls rounded; the bar, windows and stage previews stay square"; key: "shell.gridRoundControls" }
    }
}
