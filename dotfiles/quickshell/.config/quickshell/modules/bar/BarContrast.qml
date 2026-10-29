import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import "../../components/FileUrl.js" as FileUrl
import "../../components/Luma.js" as Luma

// Text colours for one screen's bar that stay readable on the wallpaper behind it. Only matters while the bar is
// translucent and has no pills (an opaque bar or an opaque pill sits on the palette's own background, which already has
// contrast): then `fg` / `dim` are the palette's `fg` / `dim` when they read against the backdrop, else the palette's
// background colour (the opposite tone) / `fg` itself when `dim` would not reach 4.5:1. Opaque or pilled: exactly `Theme.fg` / `Theme.dim`.
// The backdrop is the wallpaper strip under the bar, sampled through a small offscreen Canvas (cover-fitted like
// modules/wallpaper), blended with the bar tint at the bar opacity. Re-sampled when the wallpaper (path or bytes),
// the bar position or thickness, or the screen size changes; a failed sample keeps the last result.
Item {
    id: root
    required property var screen

    property real luma: -1               // mean luminance of the strip behind the bar; -1 = not sampled
    property int serial: 0               // bumped when the wallpaper file changes on disk

    readonly property bool adaptive: Theme.barPills === "off" && Theme.barOpacity < 1.0
    readonly property string wallpaperUrl: FileUrl.toUrl(ThemeStore.wallpaperPath)
    readonly property real backdrop: Luma.blend(Theme.bg, luma >= 0 ? luma : Luma.luminance(Theme.bg), Theme.barOpacity)
    readonly property color fg: adaptive ? Luma.pick(Theme.fg, Theme.bg, backdrop, 4.5) : Theme.fg
    readonly property color dim: !adaptive ? Theme.dim
        : Luma.contrastLuma(Theme.dim, backdrop) >= 4.5 ? Theme.dim : fg      // 4.5:1 like the text (WCAG 1.4.3); below it, the full text colour

    // No sampling (opaque bar, pills, no wallpaper): forget the last result, so it is never used stale when sampling resumes.
    onAdaptiveChanged: if (!adaptive) luma = -1
    onWallpaperUrlChanged: if (wallpaperUrl === "") luma = -1

    // The strip under the bar, in the screen's logical pixels. Bar.qml sets it to the bar's own rectangle (a floating or
    // hugging bar covers only part of the edge); this is the full-edge default.
    property rect strip: {
        const w = screen.width, h = screen.height, t = Theme.barHeight
        switch (Theme.barPosition) {
        case "bottom": return Qt.rect(0, h - t, w, t)
        case "left": return Qt.rect(0, 0, t, h)
        case "right": return Qt.rect(w - t, 0, t, h)
        default: return Qt.rect(0, 0, w, t)
        }
    }

    FileView {                           // watch only: the file is never read here, Canvas decodes it
        path: root.adaptive && root.wallpaperUrl !== "" ? ThemeStore.wallpaperPath : ""
        preload: false
        watchChanges: true
        printErrors: false
        onFileChanged: settle.restart()
    }

    Timer { id: settle; interval: 300; onTriggered: root.serial++ }

    Loader {
        active: root.adaptive && root.wallpaperUrl !== ""

        sourceComponent: Canvas {
            id: cv
            width: 32
            height: 8
            opacity: 0                   // painted all the same, never seen
            // Everything that changes the strip; any change re-samples after a short debounce.
            readonly property string key: [root.wallpaperUrl, root.serial, root.strip, root.screen.width, root.screen.height].join("|")
            property string loading: ""

            onKeyChanged: again.restart()
            Component.onCompleted: again.restart()
            Timer { id: again; interval: 200; onTriggered: cv.start() }

            function start() {
                const u = root.wallpaperUrl
                if (loading !== "") unloadImage(loading)
                loading = u
                unloadImage(u)           // same path, new bytes: drop the cached decode
                loadImage(u)
                if (isImageLoaded(u)) requestPaint()     // already decoded (cached by url): imageLoaded never fires
            }
            onImageLoaded: requestPaint()
            onPaint: {
                const u = loading
                if (u === "" || !isImageLoaded(u)) return
                const ctx = getContext("2d")
                const size = ctx.createImageData(u)
                const iw = size.width, ih = size.height
                const sw = root.screen.width, sh = root.screen.height
                if (iw > 0 && ih > 0 && sw > 0 && sh > 0) {
                    const s = Math.max(sw / iw, sh / ih)            // cover fit, centred
                    const ox = (sw - iw * s) / 2, oy = (sh - ih * s) / 2
                    const r = root.strip
                    ctx.clearRect(0, 0, width, height)
                    ctx.drawImage(u, (r.x - ox) / s, (r.y - oy) / s, r.width / s, r.height / s, 0, 0, width, height)
                    const d = ctx.getImageData(0, 0, width, height).data
                    let sum = 0
                    for (let i = 0; i < d.length; i += 4)
                        sum += Luma.luminance(Qt.rgba(d[i] / 255, d[i + 1] / 255, d[i + 2] / 255, 1))
                    root.luma = sum / (d.length / 4)
                }
                unloadImage(u)           // a wallpaper can be tens of MB decoded: keep none of it
                loading = ""
            }
        }
    }
}
