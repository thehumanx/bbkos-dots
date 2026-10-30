import QtQuick
import qs
import qs.services

// The pinned apps grid (docs/modules/dock.md; the state is services/Dock.qml): a grid of DockTile at the start of the rail (two
// columns down a side rail, one row along a top or bottom one, the same tile size on every edge), the pinned apps in the
// order they were pinned and a "+" tile after them, so there is always one empty tile to add an app with. Clicking an
// app focuses its window when it has one, and starts it otherwise.
Item {
    id: root

    required property var rail                 // the rail window (Stage.qml): sizes, and the focus action
    readonly property bool side: rail.sideRail
    readonly property int across: side ? 2 : 1       // tiles across the rail
    readonly property var apps: Dock.apps
    readonly property int count: apps.length + 1
    readonly property int lines: Math.ceil(count / across)     // tiles along the rail
    // Whole logical pixels, so the hairlines stay sharp; the second tile across takes what is left after the rail's gap.
    readonly property real firstW: rail.tile
    readonly property real secondW: side ? rail.crossSize - firstW - rail.gap : 0
    readonly property real tile: rail.tile             // the size along the rail
    readonly property real alongLen: lines * tile + (lines - 1) * rail.gap

    width: side ? rail.crossSize : alongLen
    height: side ? alongLen : rail.crossSize
    implicitWidth: width
    implicitHeight: height

    // The pinned apps whose tile found their desktop entry (a "?" tile did not); the tests read it.
    function resolved(): var {
        const out = []
        for (let i = 0; i < apps.length; i++) {
            const t = tiles.itemAt(i)
            if (t && t.entry) out.push(t.appId)
        }
        return out
    }

    // Outside grid mode with grouped bar pills: one pill behind all the tiles, like a grouped bar section.
    Rectangle {
        readonly property real pad: Math.min(4, root.rail.padding)
        visible: !Theme.gridMode && Theme.barPills === "grouped"
        x: -pad; y: -pad
        width: root.width + 2 * pad
        height: root.height + 2 * pad
        radius: Math.min(Theme.pillRadius, height / 2, width / 2)
        color: Theme.pillBg
    }

    Repeater {
        id: tiles
        model: root.count

        DockTile {
            required property int index
            readonly property bool isAdd: index === root.apps.length
            readonly property int cross: index % root.across            // which tile across the rail
            readonly property real crossPos: cross === 0 ? 0 : root.firstW + root.rail.gap
            readonly property real crossLen: cross === 0 ? root.firstW : root.secondW
            readonly property real alongPos: Math.floor(index / root.across) * (root.tile + root.rail.gap)

            rail: root.rail
            add: isAdd
            appId: isAdd ? "" : root.apps[index]
            running: !isAdd && root.apps[index] in Dock.running
            x: root.side ? crossPos : alongPos
            y: root.side ? alongPos : crossPos
            width: root.side ? crossLen : root.tile
            height: root.side ? root.tile : crossLen

            onActivated: {
                if (isAdd) { Dock.pickRequested(); return }
                root.rail.dockActivate(root.apps[index])
            }
            onRemoved: Dock.unpin(root.apps[index])
        }
    }
}
