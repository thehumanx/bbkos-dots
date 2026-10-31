import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Widgets
import qs
import qs.components

// One window in the stage rail: a still of the window, its app icon in the middle (also on a top or bottom rail, where the card
// has no caption) and its title below. Click it to bring it to the front.
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
    // No caption on a card under 60 px tall (a top or bottom rail is one tile thick): the picture and the icon alone.
    readonly property real captionHeight: rail.showTitle && height >= 60 ? 22 : 0

    // Across the rail its thickness less the padding, along it stage.cardHeight, on every edge.
    width: rail.sideRail ? rail.crossSize : rail.cardHeight
    height: rail.sideRail ? rail.cardHeight : rail.crossSize
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

        // The app icon in the middle of the card, on a plate so it reads over any screenshot. Shown alone while there is no still.
        Rectangle {
            readonly property real size: Math.round(Math.min(32, Math.min(card.width, card.height) * 0.5))
            anchors.centerIn: parent
            visible: card.iconSource !== "" && (card.rail.showIcon || !still.hasContent)
            width: size + 8
            height: size + 8
            radius: Math.min(card.rail.cardRadius, width / 2)
            color: still.hasContent ? Qt.rgba(Theme.bg.r, Theme.bg.g, Theme.bg.b, 0.80) : "transparent"
            IconImage {
                anchors.centerIn: parent
                implicitSize: parent.size
                source: card.iconSource
            }
        }

        Rectangle {
            id: caption
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: card.captionHeight
            visible: height > 0
            color: Qt.rgba(Theme.bg.r, Theme.bg.g, Theme.bg.b, 0.92)

            Txt {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 6; rightMargin: 6 }
                text: card.title !== "" ? card.title : card.appId
                elide: Text.ElideRight
                font.pixelSize: Theme.fontSize - 3
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
        border.color: card.hovered ? Theme.accent : Theme.gridMode ? Theme.cardEdge : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.22)
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
