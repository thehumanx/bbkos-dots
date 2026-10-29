import QtQuick
import QtQuick.Effects
import qs
import qs.services
import "../../components/FileUrl.js" as FileUrl

// The overview's backdrop: the wallpaper, blurred and tinted exactly like the bar's background, so bar and backdrop
// read as one blurred wall (requested 2026-10-20). It is drawn here and not compositor-blurred on purpose: a Hyprland
// layer rule blurs what is BEHIND a layer surface, and behind this overlay sit the real windows, never the wallpaper
// — so the compositor route would show blurred windows, which is precisely not wanted.
//
// The blur runs on a quarter-size copy of the wallpaper and is scaled back up: a blur has no fine detail, so it looks
// the same, and the shader touches 1/16 of the pixels. A live MultiEffect over the full-size image re-ran its passes
// on every frame, which is what made the open animation choppy on the Arc iGPU. (A first version baked the blur into
// a `ShaderEffectSource` with `live: false`; that texture was lost whenever the overlay window was unmapped and the
// backdrop came back flat dark on every open but the first, so the effect is drawn directly.) Parameters are the ones
// the tool writes into Hyprland's decoration.blur (windows.blurSize/blurPasses, 0 while windows.blurEnabled is off);
// the tint is the bar's own background colour (Theme.barBg). Text on top is plain Theme.fg/Theme.dim.
Item {
    id: root

    required property real screenWidth         // logical size of the screen: stable while the window is unmapped
    required property real screenHeight
    required property real screenScale

    readonly property var winSettings: ThemeStore.settings.windows
    readonly property bool blurOn: (winSettings ? winSettings.blurEnabled : true) !== false
    readonly property real blurSize: winSettings && typeof winSettings.blurSize === "number" ? winSettings.blurSize : 3
    readonly property real blurPasses: winSettings && typeof winSettings.blurPasses === "number" ? winSettings.blurPasses : 2

    readonly property int shrink: 4
    readonly property int bakeW: Math.max(1, Math.round(screenWidth * screenScale / shrink))
    readonly property int bakeH: Math.max(1, Math.round(screenHeight * screenScale / shrink))
    // The compositor's blur calibration (~10 px per unit of size*passes against blurMax 64), at the bake's scale.
    readonly property real blurAmount: blurOn ? Math.min(1.0, blurPasses * blurSize * 10 / 64) : 0

    Rectangle { anchors.fill: parent; color: Theme.bg }        // shown until the wallpaper loads or when there is none

    Image {
        id: pic
        width: root.bakeW
        height: root.bakeH
        visible: false
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        source: ThemeStore.wallpaperPath !== "" ? FileUrl.toUrl(ThemeStore.wallpaperPath) : ""
        sourceSize: Qt.size(root.bakeW, root.bakeH)
    }

    MultiEffect {
        id: fx
        width: root.bakeW
        height: root.bakeH
        transformOrigin: Item.TopLeft
        scale: root.shrink
        smooth: true
        source: pic
        blurEnabled: root.blurOn
        autoPaddingEnabled: false
        blurMax: 64 / root.shrink
        blur: root.blurAmount
        brightness: 0
    }

    // The very colour the bar paints over its blurred backdrop (bg at bar opacity), so the two surfaces blend.
    Rectangle { anchors.fill: parent; color: Theme.barBg }
}
