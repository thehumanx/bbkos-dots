import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.SystemTray
import qs
import qs.components
import qs.services

// One bar per screen (Variants follows monitor hotplug). Reserves space at the edge Theme.barPosition names.
// Layout: three BarSections (start, centre, end). To add a widget, put it in a BarItem inside a section; the item
// follows the position, opacity, pills and radius settings by itself (docs/modules/bar.md, "Adding a widget").
Scope {
    IpcHandler {
        target: "bar"
        function toggle(): void { BarState.hidden = !BarState.hidden }
        function hide(): void { BarState.hidden = true }
        function unhide(): void { BarState.hidden = false }
        function status(): string {         // test hook: per bar, the colours in use and what they were derived from
            return JSON.stringify(bars.instances.map(w => ({ screen: w.modelData.name, position: Theme.barPosition, hidden: BarState.hidden,
                luma: w.contrast.luma, backdrop: w.contrast.backdrop, adaptive: w.contrast.adaptive,
                fg: String(w.barFg), dim: String(w.barDim) })))
        }
    }

    Variants {
        id: bars
        model: Quickshell.screens

        PanelWindow {
            id: win
            required property var modelData
            readonly property bool vertical: Theme.barVertical
            property alias contrast: barContrast
            // Text colours for this bar (Txt.fgColor / dimColor read them through QsWindow.window).
            readonly property color barFg: barContrast.fg
            readonly property color barDim: barContrast.dim
            screen: modelData
            visible: !BarState.hidden
            anchors {
                top: Theme.barPosition !== "bottom"
                bottom: Theme.barPosition !== "top"
                left: Theme.barPosition !== "right"
                right: Theme.barPosition !== "left"
            }
            // The window is the bar plus the space it floats off its edge (Theme.barFloat); the bar itself is `body`,
            // drawn inside it. The window is transparent and takes input only over the body, so the space around a floating
            // or hugging bar lets clicks through. The compositor reserves the whole window, so windows start below the float.
            implicitWidth: vertical ? Theme.barHeight + Theme.barFloat : 0
            implicitHeight: vertical ? 0 : Theme.barHeight + Theme.barFloat
            color: "transparent"
            mask: Region { item: body }
            WlrLayershell.namespace: "bbkos-bar"

            // Where the body sits in the screen's logical pixels: what the text-contrast sampling and the blur look at.
            readonly property rect bodyStrip: {
                const w = modelData.width, h = modelData.height, t = Theme.barHeight + Theme.barFloat
                const ox = vertical && Theme.barPosition === "right" ? w - t : 0
                const oy = !vertical && Theme.barPosition === "bottom" ? h - t : 0
                return Qt.rect(ox + body.x, oy + body.y, body.width, body.height)
            }
            BarContrast { id: barContrast; screen: win.modelData; strip: win.bodyStrip }

            // Which widgets sit in each section, in order: from settings bar.layout ("section:widget" entries, the
            // list order sets the order within a section). settings.py always writes a complete, valid list.
            readonly property var layout: {
                const v = SettingsStore.shown("bar.layout")
                return Array.isArray(v) ? v : []
            }
            function widgetsIn(section: string): var {
                return layout.filter(e => e.startsWith(section + ":")).map(e => e.slice(section.length + 1))
            }

            // One component per widget. A widget's own show/hide rule (battery, bluetooth) stays with it.
            Component { id: overviewWidget; BarItem { highlighted: OverviewState.open && (OverviewState.screen === "" || OverviewState.screen === win.modelData.name); OverviewWidget { screenName: win.modelData.name } } }
            Component { id: workspacesWidget; BarItem { Workspaces {} } }
            Component { id: clockWidget; BarItem { highlighted: PanelState.isOn("calendar", win.modelData.name); Clock { screenName: win.modelData.name } } }
            Component { id: mediaWidget; BarItem { active: Media.present && !Theme.barVertical; MediaWidget { screenName: win.modelData.name } } }
            Component { id: timerWidget; BarItem { active: Countdown.active; highlighted: PanelState.isOn("timer", win.modelData.name); TimerWidget { screenName: win.modelData.name } } }
            Component { id: updatesWidget; BarItem { active: Updates.count > 0; UpdatesWidget {} } }
            Component { id: trayWidget; BarItem { active: SystemTray.items.values.length > 0; Tray { window: win } } }
            Component { id: displayWidget; BarItem { highlighted: PanelState.isOn("display", win.modelData.name); DisplayWidget { screenName: win.modelData.name } } }
            Component { id: audioWidget; BarItem { highlighted: PanelState.isOn("audio", win.modelData.name); AudioWidget { screenName: win.modelData.name } } }
            Component { id: bluetoothWidget; BarItem { active: Bt.available; highlighted: PanelState.isOn("bluetooth", win.modelData.name); BluetoothWidget { screenName: win.modelData.name } } }
            Component { id: networkWidget; BarItem { highlighted: PanelState.isOn("wifi", win.modelData.name); NetworkWidget { screenName: win.modelData.name } } }
            Component { id: batteryWidget; BarItem { active: Power.present; highlighted: PanelState.isOn("battery", win.modelData.name); BatteryWidget { screenName: win.modelData.name } } }
            Component { id: notificationsWidget; BarItem { highlighted: PanelState.isOn("notifications", win.modelData.name); NotificationsWidget { screenName: win.modelData.name } } }
            Component { id: recordWidget; BarItem { active: Record.recording; highlighted: PanelState.isOn("record", win.modelData.name); RecordWidget {} } }
            Component { id: privacyWidget; BarItem { active: Privacy.any; PrivacyWidget {} } }
            Component { id: settingsWidget; BarItem { highlighted: SettingsStore.windowOpen; SettingsWidget {} } }
            readonly property var widgetComponents: ({
                overview: overviewWidget, workspaces: workspacesWidget, clock: clockWidget, media: mediaWidget, timer: timerWidget, updates: updatesWidget, tray: trayWidget, display: displayWidget,
                audio: audioWidget, bluetooth: bluetoothWidget, network: networkWidget, battery: batteryWidget,
                notifications: notificationsWidget, settings: settingsWidget, record: recordWidget, privacy: privacyWidget
            })

            // The bar itself. Attached (barFloat 0, no hug) it fills the window and looks as before; floating it is inset by
            // barFloat from the screen edges; hugging it is only as long as its widgets and
            // centred on the edge (the three groups follow each other, a gap apart).
            Rectangle {
                id: body
                readonly property real along: win.vertical ? win.contentItem.height : win.contentItem.width
                readonly property real f: Theme.barFloat
                readonly property bool hug: Theme.barHug
                readonly property real gapS: Theme.gap                         // between groups, and at both ends when hugging
                readonly property real sizeS: secStart.extent
                readonly property real sizeC: secCentre.extent
                readonly property real sizeE: secEnd.extent
                readonly property int groups: (sizeS > 0 ? 1 : 0) + (sizeC > 0 ? 1 : 0) + (sizeE > 0 ? 1 : 0)
                readonly property real hugLen: Math.ceil(2 * gapS + sizeS + sizeC + sizeE + Math.max(0, groups - 1) * gapS)
                readonly property real len: Math.round(hug ? Math.min(hugLen, along) : Math.max(0, along - 2 * f))
                x: win.vertical ? (Theme.barPosition === "left" ? f : 0) : Math.round((along - len) / 2)
                y: win.vertical ? Math.round((along - len) / 2) : (Theme.barPosition === "bottom" ? 0 : f)
                width: win.vertical ? Theme.barHeight : len
                height: win.vertical ? len : Theme.barHeight
                radius: Math.min(Theme.barRadius, Theme.barHeight / 2)
                color: barBlur.active ? "transparent" : Theme.barBg

                // Behind everything else on the bar: the bar's own blurred wallpaper (Theme.barBlur, Theme.barBlurAmount).
                BarBlur {
                    id: barBlur
                    anchors.fill: parent
                    screenWidth: win.modelData.width
                    screenHeight: win.modelData.height
                    strip: win.bodyStrip
                    radius: body.radius
                }

                Rectangle {                    // grid mode: the line along the bar's inner edge, under the cells and the gaps between them
                    visible: Theme.gridMode
                    color: Theme.cardEdge
                    readonly property string e: Theme.barPosition
                    x: e === "right" ? 0 : e === "left" ? parent.width - Theme.hair : 0
                    y: e === "bottom" ? 0 : e === "top" ? parent.height - Theme.hair : 0
                    width: win.vertical ? Theme.hair : parent.width
                    height: win.vertical ? parent.height : Theme.hair
                }

                // Grid mode: the empty stretches between (and around) the groups are empty cells in the same style, so the bar reads
                // as one seamless row. Each cell overlaps its neighbours by one hairline, like the cells themselves.
                readonly property var gridFills: {
                    if (!Theme.gridMode) return []
                    const spans = []
                    for (const sec of [secStart, secCentre, secEnd]) if (sec.extent > 0) spans.push([sec.spanFrom, sec.spanTo])
                    spans.sort((a, b) => a[0] - b[0])
                    const total = win.vertical ? height : width
                    const out = []
                    let pos = 0
                    for (const sp of spans) {
                        if (sp[0] - pos > 1) out.push([pos, sp[0]])
                        pos = Math.max(pos, sp[1])
                    }
                    if (total - pos > 1) out.push([pos, total])
                    return out.map(g => [g[0] > 0 ? g[0] - Theme.hair : g[0], g[1] < total ? g[1] + Theme.hair : g[1]])
                }
                Repeater {
                    model: body.gridFills
                    delegate: Rectangle {
                        required property var modelData
                        x: win.vertical ? 0 : modelData[0]
                        y: win.vertical ? modelData[0] : 0
                        width: win.vertical ? Theme.barHeight : modelData[1] - modelData[0]
                        height: win.vertical ? modelData[1] - modelData[0] : Theme.barHeight
                        color: Theme.pillBg
                        border.width: Theme.hair
                        border.color: Theme.cardEdge
                    }
                }

                BarSection {
                    id: secStart
                    anchors.fill: parent
                    align: "start"
                    hug: body.hug
                    hugPos: body.gapS + (0) + pad
                    Repeater {
                        model: win.widgetsIn("start")
                        delegate: Loader {
                            required property string modelData
                            sourceComponent: win.widgetComponents[modelData] ?? null
                            visible: !item || item.active !== false     // a hidden BarItem still gives its Loader a size: leave no gap
                        }
                    }
                }

                BarSection {
                    id: secCentre
                    anchors.fill: parent
                    align: "centre"
                    hug: body.hug
                    hugPos: body.gapS + (body.sizeS + (body.sizeS > 0 ? body.gapS : 0)) + pad
                    Repeater {
                        model: win.widgetsIn("center")
                        delegate: Loader {
                            required property string modelData
                            sourceComponent: win.widgetComponents[modelData] ?? null
                            visible: !item || item.active !== false     // a hidden BarItem still gives its Loader a size: leave no gap
                        }
                    }
                }

                BarSection {
                    id: secEnd
                    anchors.fill: parent
                    align: "end"
                    hug: body.hug
                    hugPos: body.gapS + (body.sizeS + (body.sizeS > 0 ? body.gapS : 0) + body.sizeC + (body.sizeC > 0 ? body.gapS : 0)) + pad
                    Repeater {
                        model: win.widgetsIn("end")
                        delegate: Loader {
                            required property string modelData
                            sourceComponent: win.widgetComponents[modelData] ?? null
                            visible: !item || item.active !== false     // a hidden BarItem still gives its Loader a size: leave no gap
                        }
                    }
                }
            }
        }
    }
}
