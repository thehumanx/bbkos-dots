import QtQuick
import QtQuick.Effects
import qs
import qs.services
import "../../components/FileUrl.js" as FileUrl

// The blur behind a translucent bar: the wallpaper strip under the bar, blurred by shell.barBlurAmount. Drawn here and not
// by a Hyprland layer rule because the rule has no strength of its own (it reuses the windows' decoration.blur size and
// passes), so the bar could not be tuned apart from the windows. A bar reserves its edge, so what sits behind it is the
// wallpaper (the same cover-fit picture modules/wallpaper draws); a floating window dragged under it is not blurred.
// The blur runs on a quarter-size copy and is scaled back up, as in modules/overview/Backdrop: a blur has no fine
// detail, so it looks the same and touches 1/16 of the pixels. Static: nothing redraws until the wallpaper, the amount or
// the bar's place changes. Needs the bar window's screen size and the strip's place in it (logical pixels).
Item {
    id: root

    required property real screenWidth
    required property real screenHeight
    required property rect strip
    property real radius: 0              // the body's corner radius (a floating or hugging bar)

    readonly property int shrink: 4
    readonly property int bakeW: Math.max(1, Math.round(screenWidth / shrink))
    readonly property int bakeH: Math.max(1, Math.round(screenHeight / shrink))

    // True while the bar shows its blur: the bar window then has no colour of its own, the tint below paints it.
    readonly property bool active: Theme.barBlur && ThemeStore.wallpaperPath !== ""

    clip: true
    visible: active

    // Rounded corners: the whole blur and tint are masked by a rounded rectangle.
    layer.enabled: radius > 0
    layer.effect: MultiEffect { maskEnabled: true; maskSource: mask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 }
    Rectangle { id: mask; anchors.fill: parent; radius: root.radius; visible: false; layer.enabled: true; layer.smooth: true }

    Image {
        id: pic
        x: -root.strip.x / root.shrink
        y: -root.strip.y / root.shrink
        width: root.bakeW
        height: root.bakeH
        visible: false
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        source: root.visible ? FileUrl.toUrl(ThemeStore.wallpaperPath) : ""
        sourceSize: Qt.size(root.bakeW, root.bakeH)
    }

    MultiEffect {
        x: pic.x * root.shrink
        y: pic.y * root.shrink
        width: root.bakeW
        height: root.bakeH
        transformOrigin: Item.TopLeft
        scale: root.shrink
        smooth: true
        source: pic
        blurEnabled: true
        autoPaddingEnabled: false
        blurMax: 64 / root.shrink
        blur: Theme.barBlurAmount
    }

    // The bar's own colour at the bar opacity, over the blur (what the window colour is when there is no blur).
    Rectangle { anchors.fill: parent; color: Theme.barBg }
}
