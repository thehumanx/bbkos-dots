import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.SystemTray
import Quickshell.Widgets
import qs
import qs.components

// StatusNotifier tray. Left click activates, right click opens the item's menu. A monochrome icon (grey, black or white
// shapes: apps often ship black ones, which vanish on a dark bar) is drawn in the bar's text colour. A coloured icon
// keeps its colours: painting it in one colour would flatten it to a blob (Spotify's green disc with black waves).
GridLayout {
    id: root
    required property var window
    columns: Theme.barVertical ? 1 : 1000
    rowSpacing: 8
    columnSpacing: 8

    Repeater {
        model: SystemTray.items

        delegate: IconImage {
            id: icon
            required property var modelData
            implicitSize: 12
            source: modelData.icon
            // Set by the probe below once it has read the icon's pixels; until then (or if it cannot) the icon is untouched.
            property bool mono: false
            layer.enabled: mono
            layer.effect: MultiEffect {
                brightness: 1.0
                colorization: 1.0
                colorizationColor: root.window.barFg
            }

            // Reads the icon's pixels: mono when every clearly visible pixel is nearly grey (R, G and B within 30 of each other).
            Canvas {
                id: probe
                width: 16
                height: 16
                opacity: 0                   // painted all the same, never seen
                property string url: ""
                Connections { target: icon.modelData; function onIconChanged() { probe.start() } }
                Component.onCompleted: start()
                function start() {
                    if (url !== "") unloadImage(url)
                    url = icon.modelData.icon
                    if (url === "") { icon.mono = false; return }
                    loadImage(url)
                    if (isImageLoaded(url)) requestPaint()
                }
                onImageLoaded: requestPaint()
                onPaint: {
                    if (url === "" || !isImageLoaded(url)) return
                    const ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.drawImage(url, 0, 0, width, height)
                    const d = ctx.getImageData(0, 0, width, height).data
                    let visible = 0, coloured = 0
                    for (let i = 0; i < d.length; i += 4) {
                        if (d[i + 3] < 128) continue
                        visible++
                        if (Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]) > 30) coloured++
                    }
                    icon.mono = visible > 0 && coloured === 0
                }
            }

            BarHit {
                crossOnly: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                onClicked: mouse => {
                    if (mouse.button === Qt.LeftButton) icon.modelData.activate()
                    else if (mouse.button === Qt.MiddleButton) icon.modelData.secondaryActivate()
                    else if (icon.modelData.hasMenu) {
                        // Menu anchor: the bar's inner edge (the window edge facing the screen), at the icon along the bar.
                        const p = icon.mapToItem(null, 0, 0)
                        const e = Theme.barEdge
                        icon.modelData.display(root.window, e === "left" ? root.window.width : e === "right" ? 0 : p.x, e === "top" ? root.window.height : e === "bottom" ? 0 : p.y)
                    }
                }
            }
        }
    }
}
