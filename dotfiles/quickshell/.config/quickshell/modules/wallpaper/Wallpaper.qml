import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs
import qs.services
import "../../components/FileUrl.js" as FileUrl

// Wallpaper: one background-layer window per screen (Variants follows monitor hotplug).
// - The window's own colour is Theme.bg, so a missing, unreadable or corrupt file (or no wallpaper) shows the
//   plain colour, never a hole or an error. Image load failures are logged once per screen by Qt itself
//   ("QML Image ...: Cannot open / Error decoding"); nothing retries, so a failure never repeats in the log.
// - Decoded at the screen's physical size (sourceSize), not the file's, with PreserveAspectCrop.
// - Two Images crossfade (400 ms) on a change; the first image of a window appears without a fade.
// - Same path, new bytes: `bbkos-theme wallpaper set` always writes current.<ext>, so a second PNG has the same
//   path. A FileView with preload: false only watches the file (never reads it) and bumps `serial`; images
//   load with cache: false and the source is reset first, so the bytes are re-read from disk.
//
// IPC target "wallpaper" (test hook): `qs ipc call wallpaper status`.
Scope {
    id: root

    readonly property string path: ThemeStore.wallpaperPath
    readonly property string url: toUrl(path)
    property int serial: 0          // bumped (debounced) whenever the file at `path` changes on disk

    // Each path segment percent-encoded (components/FileUrl.js), so spaces, unicode, #, ? and % in a hand-edited
    // path stay a file name.
    function toUrl(p) { return FileUrl.toUrl(p) }

    onPathChanged: {
        if (path !== "" && !path.startsWith("/"))
            console.warn("Wallpaper: wallpaper.path is not absolute, showing the plain colour: " + path)
    }

    FileView {
        path: root.url !== "" ? root.path : ""
        preload: false               // watch only: a wallpaper can be tens of MB and is never read here
        watchChanges: true
        printErrors: false
        onFileChanged: settle.restart()
    }

    Timer {
        id: settle
        interval: 150                // an in-place rewrite fires several change events; coalesce them
        onTriggered: root.serial++
    }

    Variants {
        id: screens
        model: Quickshell.screens

        PanelWindow {
            id: win
            required property ShellScreen modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Background
            WlrLayershell.namespace: "bbkos-wallpaper"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            mask: Region {}              // no input
            color: Theme.bg

            readonly property int physW: Math.round(width * devicePixelRatio)
            readonly property int physH: Math.round(height * devicePixelRatio)
            readonly property bool sized: physW > 0 && physH > 0   // sourceSize 0 would decode at full size

            property Image front: null       // image on screen (or fading in); null = plain colour
            property Image pending: null     // image loading the wanted file
            property bool settled: false     // first load done: later changes crossfade
            property string lastStatus: "Null"

            readonly property string wantUrl: root.url
            readonly property int wantSerial: root.serial
            onWantUrlChanged: Qt.callLater(load)
            onWantSerialChanged: Qt.callLater(load)
            onSizedChanged: Qt.callLater(load)
            Component.onCompleted: Qt.callLater(load)

            function load() {
                if (!sized) return
                finishFades()
                const back = front === imgA ? imgB : imgA   // after finishFades the non-front image is free
                back.source = ""             // with cache: false, setting the same url again re-reads the file
                back.opacity = 0
                if (wantUrl === "") {
                    pending = null
                    lastStatus = "Null"
                    toPlain()
                    return
                }
                pending = back
                back.source = wantUrl        // onStatusChanged -> finished(); also when it fails at once
            }

            // A change during a running fade: jump that fade to its end, so at most one image is visible.
            function finishFades() {
                if (fadeIn.running) {
                    fadeIn.stop()            // stop() does not emit finished(): finish by hand
                    fadeIn.target.opacity = 1
                    drop(fadeIn.target === imgA ? imgB : imgA)
                }
                if (fadeOut.running) {
                    fadeOut.stop()
                    fadeOut.target.opacity = 0
                    drop(fadeOut.target)
                }
            }

            function finished(img) {
                if (img !== pending) return
                if (img.status === Image.Ready) {
                    pending = null
                    lastStatus = "Ready"
                    const other = img === imgA ? imgB : imgA
                    img.z = 1
                    other.z = 0
                    front = img
                    if (settled) {
                        fadeIn.target = img
                        fadeIn.start()
                    } else {
                        img.opacity = 1
                        drop(other)
                    }
                    settled = true
                } else if (img.status === Image.Error) {
                    pending = null
                    lastStatus = "Error"
                    img.source = ""
                    toPlain()
                }
            }

            function toPlain() {
                const old = front
                front = null
                if (old && settled) {
                    fadeOut.target = old
                    fadeOut.start()
                } else if (old) {
                    drop(old)
                }
                settled = true
            }

            function drop(img) {
                if (img === front || img === pending) return
                img.source = ""
                img.opacity = 0
            }

            NumberAnimation {
                id: fadeIn
                property: "opacity"
                to: 1
                duration: 400
                easing.type: Easing.InOutQuad
                onFinished: win.drop(win.front === imgA ? imgB : imgA)
            }

            NumberAnimation {
                id: fadeOut
                property: "opacity"
                to: 0
                duration: 400
                easing.type: Easing.InOutQuad
                onFinished: win.drop(fadeOut.target)
            }

            Image {
                id: imgA
                anchors.fill: parent
                opacity: 0
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: false
                sourceSize: Qt.size(win.physW, win.physH)
                onStatusChanged: win.finished(imgA)
            }

            Image {
                id: imgB
                anchors.fill: parent
                opacity: 0
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: false
                sourceSize: Qt.size(win.physW, win.physH)
                onStatusChanged: win.finished(imgB)
            }
        }
    }

    IpcHandler {
        target: "wallpaper"
        function status(): string {
            const names = ["Null", "Ready", "Loading", "Error"]
            const list = []
            for (let i = 0; i < screens.instances.length; i++) {
                const w = screens.instances[i]
                const img = w.pending ?? w.front
                list.push({
                    name: w.modelData.name, width: w.physW, height: w.physH,    // physical = decode size
                    logical: w.width + "x" + w.height, scale: w.devicePixelRatio,
                    shown: (w.front && w.front.status === Image.Ready) ? "image" : "plain",   // fading in counts
                    opacity: w.front ? w.front.opacity : 0,
                    decoded: w.front ? w.front.implicitWidth + "x" + w.front.implicitHeight : "",   // decoded pixels
                    status: img ? (names[img.status] ?? String(img.status)) : w.lastStatus
                })
            }
            return JSON.stringify({ path: ThemeStore.wallpaperPath, screens: list })
        }
    }
}
