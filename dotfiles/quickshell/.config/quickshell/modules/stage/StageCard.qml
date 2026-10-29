import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Widgets
import qs
import qs.components

// One window in the stage rail: a still of the window with its title and icon. Click it to bring it to the front.
// Sizes and looks come from the stage settings (the rail passes them in), so every one is tunable in the settings app.
Item {
    id: card

    required property var rail                 // the rail window: settings, toplevel lookup and the focus action
    required property string address
    required property string appId
    required property string title

    readonly property bool hovered: area.containsMouse
    readonly property var toplevel: rail.toplevelFor(address)
    readonly property var desktopEntry: appId !== "" ? DesktopEntries.heuristicLookup(appId) : null
    readonly property string iconSource: {
        const name = desktopEntry && desktopEntry.icon ? desktopEntry.icon : appId
        return name !== "" ? Quickshell.iconPath(name, "application-x-executable") : ""
    }
    readonly property real captionHeight: rail.showTitle || rail.showIcon ? 22 : 0

    width: rail.cardWidth
    height: rail.cardHeight
    // Enter: grows in with a short fade (off with the animations setting).
    opacity: 1
    scale: hovered && rail.animations ? 1.03 : 1
    Behavior on scale { enabled: card.rail.animations; NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

    // `clip` only clips to a rectangle, so the screenshot and the caption would poke out of the rounded corners. The
    // contents are drawn into a layer and masked with the rounded shape; the border is drawn on top, outside the mask.
    Item {
        id: frame
        anchors.fill: parent
        layer.enabled: true
        layer.smooth: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: roundMask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.94)
        }

        StillImage {
            id: still
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: caption.top }
            captureSource: card.toplevel ? card.toplevel.wayland : null
            refreshToken: card.rail.captureVersion
        }

        IconImage {
            anchors.centerIn: still
            visible: !still.hasContent
            implicitSize: 32
            source: card.iconSource
        }

        Rectangle {
            id: caption
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: card.captionHeight
            visible: height > 0
            color: Qt.rgba(Theme.bg.r, Theme.bg.g, Theme.bg.b, 0.92)

            Row {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 6; rightMargin: 6 }
                spacing: 6
                IconImage {
                    visible: card.rail.showIcon && card.iconSource !== ""
                    implicitSize: 14
                    source: card.iconSource
                    anchors.verticalCenter: parent.verticalCenter
                }
                Txt {
                    visible: card.rail.showTitle
                    width: parent.width - (card.rail.showIcon && card.iconSource !== "" ? 20 : 0)
                    text: card.title !== "" ? card.title : card.appId
                    elide: Text.ElideRight
                    font.pixelSize: Theme.fontSize - 3
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }

    Item {
        id: roundMask
        anchors.fill: parent
        visible: false
        layer.enabled: true
        layer.smooth: true
        Rectangle { anchors.fill: parent; radius: card.rail.cardRadius; color: "black" }
    }

    Rectangle {
        anchors.fill: parent
        radius: card.rail.cardRadius
        color: "transparent"
        border.width: card.hovered ? 2 : Theme.hair
        border.color: card.hovered ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.22)
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton
        onClicked: card.rail.focusWindow(card.address)
    }
}
