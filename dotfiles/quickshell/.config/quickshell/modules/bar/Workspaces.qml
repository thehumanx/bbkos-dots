import QtQuick
import QtQuick.Layouts
import Quickshell.Hyprland
import qs
import qs.components

// Existing (non-special) workspaces; the focused one is highlighted. Click to switch.
GridLayout {
    columns: Theme.barVertical ? 1 : 1000
    rowSpacing: 2
    columnSpacing: 2

    Repeater {
        model: Hyprland.workspaces.values.filter(w => w.id > 0).sort((a, b) => a.id - b.id)

        delegate: Txt {
            required property var modelData
            text: modelData.id
            padding: 5
            horizontalAlignment: Text.AlignHCenter
            font.bold: modelData.focused
            color: modelData.focused ? Theme.accent : (modelData.active ? tone(Theme.accent3) : dimColor)

            BarHit {
                crossOnly: true
                onClicked: modelData.activate()
            }
        }
    }
}
