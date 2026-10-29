import QtQuick
import QtQuick.Effects
import Quickshell
import qs
import qs.components
import qs.services
import "../../components/FileUrl.js" as FileUrl

// A scaled mock of the lock screen (hyprlock), drawn from the lock.* settings: the blurred wallpaper, then each visible
// element at its offset from the centre (y up, like hyprlock) and size, times `s`, the preview's pixels per screen
// pixel. It is an approximation: hyprlock's font metrics and blur differ a little; the page's "Test real lock" shows
// the real thing. `selected` is the element id the page edits ("avatar", "welcome", "date", "time", "battery",
// "field") or "".
Item {
    id: root
    property string selected: "avatar"          // opens on the avatar, so its Picture row is in view (2026-10-28)

    // Mirrors settings.py LOCK_DEFAULTS: used while a key is missing from an older settings.json.
    readonly property var defaults: ({
        avatarShow: true, avatarX: 0, avatarY: 260, avatarSize: 84,
        welcomeShow: true, welcomeX: 0, welcomeY: 190, welcomeSize: 18,
        dateShow: true, dateX: 0, dateY: 125, dateSize: 14,
        timeShow: true, timeX: 0, timeY: 50, timeSize: 96,
        batteryShow: true, batteryX: 0, batteryY: -150, batterySize: 13,
        avatarAlign: "center", welcomeAlign: "center", dateAlign: "center", timeAlign: "center", batteryAlign: "center",
        fieldAlign: "center", edgeMargin: 10,
        fieldX: 0, fieldY: -70, fieldWidth: 300, fieldHeight: 50, fieldRadius: -1, fieldOpacity: 0.14,
        blurPasses: 3, blurSize: 7, brightness: 0.75,
        font: "JetBrainsMono Nerd Font", textColor: "#f0f0f0", welcomeText: "Welcome $USER",
        timeFormat: "24h", dateFormat: "weekday-long"
    })
    // Values being dragged: shown at once, sent to the settings once on release (each send re-renders files).
    property var live: ({})
    property Item selItem: null
    function val(k: string): var {
        if (k in live) return live[k]
        const v = SettingsStore.shown("lock." + k)
        return v === undefined || v === null ? defaults[k] : v
    }
    // Ranges of the draggable keys, as in settings.py RANGES.
    function lim(k: string): var {
        if (k === "fieldX") return [-600, 600]
        if (k === "fieldY") return [-500, 500]
        if (k === "fieldWidth") return [120, 800]
        if (k === "fieldHeight") return [30, 120]
        if (k === "avatarSize") return [32, 300]
        if (k.endsWith("Size")) return [8, 200]
        return [-1200, 1200]
    }
    function setLive(k: string, v: real): void {
        const r = lim(k)
        const o = Object.assign({}, live)
        o[k] = Math.max(r[0], Math.min(r[1], Math.round(v)))
        live = o
    }
    function commit(): void {
        const o = live
        live = ({})
        for (const k in o) SettingsStore.set("lock." + k, o[k])
    }

    readonly property var screenObj: Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
    // hyprlock works in the panel's pixels (1920x1200 at scale 1.0667), not the logical size Quickshell reports
    readonly property real dpr: screenObj && screenObj.devicePixelRatio > 0 ? screenObj.devicePixelRatio : 1
    readonly property real monW: screenObj && screenObj.width > 0 ? screenObj.width * dpr : 1920
    readonly property real monH: screenObj && screenObj.height > 0 ? screenObj.height * dpr : 1200
    readonly property real s: width / monW
    readonly property color textColor: val("textColor")
    readonly property string font_: String(val("font"))
    readonly property string home: Quickshell.env("HOME") ?? ""

    implicitHeight: width * monH / monW
    clip: true

    Rectangle { anchors.fill: parent; color: Theme.bg }

    Image {
        id: wallpaper
        anchors.fill: parent
        source: ThemeStore.wallpaperPath !== "" ? FileUrl.toUrl(ThemeStore.wallpaperPath) : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: false
    }
    MultiEffect {
        anchors.fill: parent
        source: wallpaper
        visible: wallpaper.status === Image.Ready
        blurEnabled: true
        blurMax: 64
        // hyprlock blurs by passes x size screen pixels; the preview is smaller, so scale that down
        blur: Math.min(1.0, root.val("blurPasses") * root.val("blurSize") * root.s * 10 / 64)
        brightness: root.val("brightness") - 1.0
    }

    // Click on the empty preview clears the selection.
    MouseArea { anchors.fill: parent; onClicked: root.selected = "" }

    // One element: its centre sits at (x, y) from the screen centre. `eid` picks its settings; clicking selects it.
    component Placed: Item {
        id: it
        property string eid
        readonly property bool shownNow: eid === "field" || root.val(eid + "Show") === true
        default property alias content: holder.data
        visible: shownNow
        width: holder.childrenRect.width
        height: holder.childrenRect.height
        readonly property string align: root.val(eid + "Align")
        // left/right: the edge sits edgeMargin % of the width in from that edge (X unused); centre: middle at X
        x: align === "left" ? root.width * root.val("edgeMargin") / 100
         : align === "right" ? root.width * (1 - root.val("edgeMargin") / 100) - width
         : root.width / 2 + root.val(eid + "X") * root.s - width / 2
        y: root.height / 2 - root.val(eid + "Y") * root.s - height / 2

        // Drag: the element follows the pointer (y is up in the settings, down on the screen).
        property real startX: 0
        property real startY: 0
        Item { id: holder; width: parent.width; height: parent.height }
        DragHandler {
            target: null
            onActiveChanged: {
                if (active) { root.selected = it.eid; it.startX = root.val(it.eid + "X"); it.startY = root.val(it.eid + "Y") }
                else root.commit()
            }
            onTranslationChanged: if (active) {
                if (it.align === "center") root.setLive(it.eid + "X", it.startX + translation.x / root.s)
                root.setLive(it.eid + "Y", it.startY - translation.y / root.s)
            }
        }
        readonly property bool isSel: root.selected === eid
        onIsSelChanged: if (isSel) root.selItem = it
        Rectangle {
            anchors { fill: parent; margins: -3 }
            visible: root.selected === it.eid
            color: "transparent"
            border.width: 1
            border.color: Theme.accent
        }
        MouseArea { anchors.fill: parent; onClicked: root.selected = it.eid }
    }

    Placed {
        eid: "avatar"
        Item {
            width: root.val("avatarSize") * root.s
            height: width
            Image {
                anchors.fill: parent
                // the chosen copy (lock.avatar), else the shipped picture
                source: (SettingsStore.shown("lock.avatar") ?? "") !== "" ? FileUrl.toUrl(SettingsStore.shown("lock.avatar"))
                        : root.home !== "" ? FileUrl.toUrl(root.home + "/.config/hypr/lock-avatar.png") : ""
                fillMode: Image.PreserveAspectCrop
                layer.enabled: true
                layer.effect: MultiEffect { maskEnabled: true; maskSource: avatarMask }
            }
            Rectangle { id: avatarMask; anchors.fill: parent; radius: width / 2; visible: false; layer.enabled: true }
        }
    }

    Placed {
        eid: "welcome"
        Txt {
            text: String(root.val("welcomeText")).replace(/\$USER/g, Quickshell.env("USER") ?? "").replace(/\$/g, "")
            color: root.textColor
            font.family: root.font_
            font.pixelSize: Math.max(1, root.val("welcomeSize") * root.s)
        }
    }

    SystemClock { id: clock; precision: SystemClock.Minutes }

    Placed {
        eid: "date"
        Txt {
            readonly property var formats: ({ "weekday-long": "dddd, dd MMMM yyyy", "weekday-short": "ddd dd MMM", "numeric": "dd/MM/yyyy" })
            text: Qt.formatDateTime(clock.date, formats[root.val("dateFormat")] ?? formats["weekday-long"])
            color: Qt.alpha(root.textColor, 0.8)
            font.family: root.font_
            font.pixelSize: Math.max(1, root.val("dateSize") * root.s)
        }
    }

    Placed {
        eid: "time"
        Txt {
            text: Qt.formatDateTime(clock.date, root.val("timeFormat") === "12h" ? "hh:mm" : "HH:mm")
            color: root.textColor
            font.family: root.font_
            font.pixelSize: Math.max(1, root.val("timeSize") * root.s)
        }
    }

    Placed {
        eid: "field"
        Rectangle {
            width: root.val("fieldWidth") * root.s
            height: root.val("fieldHeight") * root.s
            radius: root.val("fieldRadius") < 0 ? height / 2 : root.val("fieldRadius") * root.s
            color: Qt.rgba(1, 1, 1, root.val("fieldOpacity"))
            Txt {
                anchors.centerIn: parent
                text: "Password"
                font.italic: true
                color: root.textColor
                font.family: root.font_
                font.pixelSize: Math.max(1, 14 * root.s)
            }
        }
    }

    Placed {
        eid: "battery"
        Txt {
            text: "󰁹  " + Math.round(Power.percent) + "%"
            color: Qt.alpha(root.textColor, 0.85)
            font.family: root.font_
            font.pixelSize: Math.max(1, root.val("batterySize") * root.s)
        }
    }

    // Resize handle of the selected element, a sibling of the elements (not a child) so their drag handlers never see
    // its presses. Avatar: diameter from the horizontal drag; text: font size from the vertical drag; field: width and
    // height. The element is centred, so its edge moves half as far as its size changes.
    Rectangle {
        id: handle
        readonly property bool on: root.selected !== "" && root.selItem !== null && root.selItem.eid === root.selected && root.selItem.shownNow
        visible: on
        width: 10
        height: 10
        color: Theme.accent
        x: on ? root.selItem.x + root.selItem.width + 4 - width / 2 : 0
        y: on ? root.selItem.y + root.selItem.height + 4 - height / 2 : 0

        MouseArea {
            anchors { fill: parent; margins: -4 }
            cursorShape: Qt.SizeFDiagCursor
            property real px: 0
            property real py: 0
            property real s0: 0
            property real s1: 0
            onPressed: mouse => {
                const p = mapToItem(root, mouse.x, mouse.y)
                px = p.x; py = p.y
                const e = root.selected
                s0 = root.val(e === "field" ? "fieldWidth" : e + "Size")
                s1 = e === "field" ? root.val("fieldHeight") : 0
            }
            onPositionChanged: mouse => {
                if (!pressed) return
                const p = mapToItem(root, mouse.x, mouse.y)
                const dx = (p.x - px) * 2 / root.s, dy = (p.y - py) * 2 / root.s
                const e = root.selected
                if (e === "field") { root.setLive("fieldWidth", s0 + dx); root.setLive("fieldHeight", s1 + dy) }
                else if (e === "avatar") root.setLive("avatarSize", s0 + dx)
                else root.setLive(e + "Size", s0 + dy / 1.2)
            }
            onReleased: root.commit()
        }
    }
}
