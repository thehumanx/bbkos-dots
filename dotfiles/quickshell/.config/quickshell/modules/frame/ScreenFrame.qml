import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs

// Grid mode (docs/modules/grid-mode.md): a hairline along all four edges of every screen, so the desktop has one uniform
// border. This is the one owner of those lines: it sits on the Overlay layer, above the bar and the rail (which no longer draw
// their own outer lines; the bar's cells end on the same pixel in the same opaque colour and are covered), and hides while the
// screen shows a fullscreen window, as the bar does. Four thin windows per screen (cheaper than one transparent window over
// the whole screen), made only while grid mode is on, taking no input and reserving no space.
Scope {
    Variants {
        model: Theme.gridMode ? Quickshell.screens : []

        Scope {
            id: per
            required property var modelData
            readonly property var workspace: Hyprland.monitorFor(per.modelData)?.activeWorkspace ?? null
            // A real fullscreen window; a maximised one (also counted by hasFullscreen) keeps the bar and so the frame.
            readonly property bool fullscreen: (per.workspace?.hasFullscreen ?? false)
                && per.workspace.toplevels.values.some(t => t.wayland?.fullscreen === true)
            // Each strip is a whole number of physical pixels thick (15 logical at 16/15): a surface of a fractional physical size
            // is scaled by the compositor, and a one-pixel line at its edge was then not drawn at all (2026-10-30).
            readonly property int thickness: {
                for (let l = 1; l <= 15; l++) if (Theme.exactOn(per.modelData, l)) return l
                return 2
            }

            Variants {
                model: per.fullscreen ? [] : ["top", "bottom", "left", "right"]

                PanelWindow {
                    id: strip
                    required property string modelData
                    readonly property bool horizontal: modelData === "top" || modelData === "bottom"
                    readonly property real line: 1 / Theme.scaleOf(per.modelData)   // one physical pixel on this screen

                    screen: per.modelData
                    anchors {
                        top: strip.modelData !== "bottom"
                        bottom: strip.modelData !== "top"
                        left: strip.modelData !== "right"
                        right: strip.modelData !== "left"
                    }
                    implicitWidth: horizontal ? 0 : per.thickness
                    implicitHeight: horizontal ? per.thickness : 0
                    color: "transparent"
                    exclusionMode: ExclusionMode.Ignore
                    mask: Region {}
                    WlrLayershell.layer: WlrLayer.Overlay
                    WlrLayershell.namespace: "bbkos-frame"

                    Rectangle {
                        color: Theme.cardEdge
                        width: strip.horizontal ? parent.width : strip.line
                        height: strip.horizontal ? strip.line : parent.height
                        x: strip.modelData === "right" ? parent.width - width : 0
                        y: strip.modelData === "bottom" ? parent.height - height : 0
                    }
                }
            }
        }
    }
}
