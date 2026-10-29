import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Widgets
import qs
import qs.components

// One window in the overview. The card lives in the host's screen layer, which is the real monitor at 1:1 that the
// host scales down into the stage (a single GPU transform, so the open and close animations never relayout cards or
// resample captures per frame). The card therefore sits at the window's real position and size; decoration that must
// stay readable after the scale-down (border, caption) is sized in screen pixels divided by the layer scale
// (`host.stageScale`) and fades in with the open progress (`host.progress`), so at progress 0 the card is just the
// window's own screenshot and the swap with the real window is invisible.
//
// The preview is a single screenshot of the client surface (Hyprland's toplevel export, so windows on workspaces that
// are not visible work too). Drag it onto a workspace card to move it (the preview shrinks so it does not cover the
// strip); click it to focus it.
Item {
    id: card

    required property var host                 // the Overview window: drag state, scale and actions
    required property string address
    required property string appId
    required property string title
    required property real rx                  // the window as fractions of the monitor frame
    required property real ry
    required property real rw
    required property real rh
    required property int order                // draw order (tiled first, most recently focused last)

    readonly property real s: host.layerScale
    readonly property real decor: host.progress                       // 0 = real window, 1 = stage
    readonly property var toplevel: host.toplevelFor(address)
    readonly property var captureSource: toplevel ? toplevel.wayland : null
    readonly property bool hasContent: shotLoader.item ? shotLoader.item.hasContent : false
    readonly property bool dragging: host.dragAddress === address
    readonly property bool hovered: area.containsMouse
    // On-screen (scaled) size, used to pick caption and drag sizes.
    readonly property real shownWidth: width * s
    readonly property real shownHeight: height * s
    readonly property real captionPx: Math.min(24, Math.max(16, Math.round(shownHeight * 0.2)))
    // While dragged, shrink the preview well below a workspace card (160x104) so the card under the pointer stays
    // readable; the grab point is scaled with it, so the window still follows the pointer naturally.
    readonly property real dragScale: dragging
        ? Math.max(0.01, Math.min(1, 112 / Math.max(1, shownWidth), 72 / Math.max(1, shownHeight))) : 1
    readonly property var desktopEntry: appId !== "" ? DesktopEntries.heuristicLookup(appId) : null
    readonly property string iconSource: {
        const name = desktopEntry && desktopEntry.icon ? desktopEntry.icon : appId
        return name !== "" ? Quickshell.iconPath(name, "application-x-executable") : ""
    }

    readonly property point pointer: host.dragX !== undefined
        ? card.parent.mapFromItem(null, host.dragX, host.dragY) : Qt.point(0, 0)

    property real baseX: rx * host.frameWidth
    property real baseY: ry * host.frameHeight

    width: rw * host.frameWidth
    height: rh * host.frameHeight
    transformOrigin: Item.TopLeft
    scale: dragScale
    x: dragging ? pointer.x - host.dragOffsetX * dragScale : baseX
    y: dragging ? pointer.y - host.dragOffsetY * dragScale : baseY
    z: dragging ? 1000 : order
    opacity: dragging ? 0.96 : 1

    // Only settled cards glide to a new layout (a retile after a drop); while the overview opens or closes they snap.
    Behavior on x { enabled: card.host.settled && !card.dragging; NumberAnimation { duration: 140; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    Behavior on y { enabled: card.host.settled && !card.dragging; NumberAnimation { duration: 140; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    Behavior on width { enabled: card.host.settled && !card.dragging; NumberAnimation { duration: 140; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    Behavior on height { enabled: card.host.settled && !card.dragging; NumberAnimation { duration: 140; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

    Component.onCompleted: host.registerWindowCard(card)
    Component.onDestruction: host.unregisterWindowCard(card)

    Rectangle {
        id: frame
        anchors.fill: parent
        radius: card.decor * Theme.controlRadius / card.s
        opacity: card.decor
        color: Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.94)
        border.width: (card.dragging || card.hovered ? 2 : Theme.hair) / card.s
        border.color: card.dragging || card.hovered ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.22)
    }

    Item {
        id: body
        anchors.fill: frame
        anchors.margins: frame.border.width * card.decor
        clip: true

        // Backing for the icon placeholder only; once the screenshot is there a translucent window shows the stage's
        // wallpaper through itself, as the real one shows the desktop.
        Rectangle {
            anchors.fill: parent
            opacity: card.hasContent ? 0 : card.decor
            color: Qt.rgba(Theme.bg.r, Theme.bg.g, Theme.bg.b, 0.9)
        }

        Loader {
            id: shotLoader
            anchors.fill: parent
            active: card.captureSource !== null
            sourceComponent: Component {
                ScreencopyView {
                    anchors.fill: parent
                    captureSource: card.captureSource
                    live: false
                    paintCursor: false
                    // ScreencopyView paints without blending, so a translucent window's alpha would be written into
                    // the overlay surface itself and the real window underneath would show through the card. Drawn
                    // through a layer it blends normally (the reference overview does the same).
                    layer.enabled: true
                    layer.smooth: true
                }
            }
        }

        // Shown until the first frame arrives, or when the toplevel handle is not available.
        IconImage {
            anchors.centerIn: parent
            visible: !card.hasContent
            opacity: card.decor
            implicitSize: Math.max(16, Math.min(44, Math.round(Math.min(card.shownWidth, card.shownHeight) * 0.28))) / card.s
            source: card.iconSource
        }
    }

    // A window that changed size gets a fresh still (the old texture would be stretched). Debounced, and only when
    // the size really differs from the one captured, so a refresh that changes nothing never touches the capture.
    property real capturedWidth: 0
    property real capturedHeight: 0
    onHasContentChanged: {
        if (hasContent && capturedWidth === 0) { capturedWidth = width; capturedHeight = height }
        host.windowContentChanged()
    }

    Timer {
        id: recapture
        interval: 220
        onTriggered: {
            card.capturedWidth = card.width
            card.capturedHeight = card.height
            shotLoader.active = false
            shotLoader.active = card.captureSource !== null
        }
    }
    onWidthChanged: if (capturedWidth > 0 && Math.abs(width - capturedWidth) > 4 && card.host.settled) recapture.restart()
    onHeightChanged: if (capturedHeight > 0 && Math.abs(height - capturedHeight) > 4 && card.host.settled) recapture.restart()

    // Caption above the capture: a ScreencopyView paints a compositor-provided texture, so keep this a sibling with a
    // higher z rather than a child of the capture's container.
    Rectangle {
        id: caption
        anchors { left: frame.left; right: frame.right; bottom: frame.bottom }
        anchors.margins: frame.border.width * card.decor
        height: card.captionPx / card.s
        opacity: card.decor
        z: 1000
        clip: true
        color: Qt.rgba(Theme.bg.r, Theme.bg.g, Theme.bg.b, 0.92)

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: Theme.hair / card.s
            color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.18)
        }

        Txt {
            anchors.centerIn: parent
            text: card.title !== "" ? card.title : card.appId
            color: Theme.fg
            font.pixelSize: Math.max(8, Math.min(Theme.fontSize - 2, card.captionPx - 7)) / card.s
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        enabled: card.host.interactive
        hoverEnabled: true
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton

        property point press: Qt.point(0, 0)
        property bool moved: false

        onPressed: mouse => {
            press = Qt.point(mouse.x, mouse.y)
            moved = false
        }
        onPositionChanged: mouse => {
            if (!pressed || !(mouse.buttons & Qt.LeftButton)) return
            if (!moved) {
                // The threshold is in screen pixels, whatever the layer scale is.
                if (Math.abs(mouse.x - press.x) * card.s < 6 && Math.abs(mouse.y - press.y) * card.s < 6) return
                moved = true
                card.host.beginDrag(card.address, card.mapToItem(null, mouse.x, mouse.y), mouse.x, mouse.y)
                return
            }
            card.host.updateDrag(card.mapToItem(null, mouse.x, mouse.y))
        }
        onReleased: {
            if (moved) card.host.endDrag()
            else if (card.host) card.host.activateWindow(card.address)
            moved = false
        }
        onCanceled: {
            if (moved) card.host.cancelDrag()
            moved = false
        }
    }
}
