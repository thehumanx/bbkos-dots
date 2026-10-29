import QtQuick
import QtQuick.Layouts
import Quickshell
import qs
import qs.components
import qs.services
import "../../components/CalendarMath.js" as Cal

// Calendar popup (PanelState "calendar"), opened by the bar clock: a month grid, the Nepali (Bikram Sambat) date under
// every day when calendar.nepali is on, the selected day in full, and how much of the year and month has gone.
// Keyboard: arrows move the day, PageUp/PageDown the month, T goes to today, N toggles the Nepali dates.
// Settings: calendar.* (docs/modules/calendar.md). All date maths is in components/CalendarMath.js.
ColumnLayout {
    id: root
    spacing: 8

    SystemClock { id: clock; precision: SystemClock.Minutes }
    readonly property date now: clock.date
    readonly property int todayY: now.getFullYear()
    readonly property int todayM: now.getMonth()
    readonly property int todayD: now.getDate()

    readonly property bool nepali: SettingsStore.shown("calendar.nepali") === true
    readonly property bool weekNumbers: SettingsStore.shown("calendar.weekNumbers") === true
    readonly property bool moonOn: SettingsStore.shown("calendar.moon") !== false
    readonly property string weekStartName: String(SettingsStore.shown("calendar.weekStart") ?? "mon")
    readonly property int weekStart: weekStartName === "sun" ? 0 : weekStartName === "sat" ? 6 : 1

    // The month on show and the selected day (kept as plain numbers; month 0-based).
    property int viewY: now.getFullYear()
    property int viewM: now.getMonth()
    property int selY: now.getFullYear()
    property int selM: now.getMonth()
    property int selD: now.getDate()

    readonly property var cells: Cal.grid(viewY, viewM, weekStart)
    readonly property var selDate: new Date(selY, selM, selD)
    readonly property var selBS: Cal.toBS(selY, selM, selD)
    readonly property var progress: Cal.yearProgress(now)
    readonly property string bsTitle: nepali ? Cal.bsTitle(viewY, viewM, false) : ""
    readonly property real cellW: (width - (weekNumbers ? weekColW + 2 : 0)) / 7 - 2
    readonly property int weekColW: 24
    readonly property int cellH: 38

    function select(y: int, m: int, d: int) {
        selY = y; selM = m; selD = d
        viewY = y; viewM = m
    }
    function today() { select(todayY, todayM, todayD) }
    function moveDays(n: int) {
        const t = new Date(selY, selM, selD + n)
        select(t.getFullYear(), t.getMonth(), t.getDate())
    }
    function moveMonths(n: int) {                       // the same day in another month, clamped to its length
        const t = new Date(selY, selM + n, 1)
        const last = Cal.daysInMonth(t.getFullYear(), t.getMonth())
        select(t.getFullYear(), t.getMonth(), Math.min(selD, last))
    }
    function relative(): string {
        const diff = Cal.dayNum(selY, selM, selD) - Cal.dayNum(todayY, todayM, todayD)
        if (diff === 0) return "Today"
        if (diff === 1) return "Tomorrow"
        if (diff === -1) return "Yesterday"
        return diff > 0 ? "In " + diff + " days" : (-diff) + " days ago"
    }
    function pct(f: real): string { return (f * 100).toFixed(1) + "%" }

    Shortcut { enabled: !timer.typing; sequence: "Left"; onActivated: root.moveDays(-1) }
    Shortcut { enabled: !timer.typing; sequence: "Right"; onActivated: root.moveDays(1) }
    Shortcut { enabled: !timer.typing; sequence: "Up"; onActivated: root.moveDays(-7) }
    Shortcut { enabled: !timer.typing; sequence: "Down"; onActivated: root.moveDays(7) }
    Shortcut { enabled: !timer.typing; sequence: "PgUp"; onActivated: root.moveMonths(-1) }
    Shortcut { enabled: !timer.typing; sequence: "PgDown"; onActivated: root.moveMonths(1) }
    Shortcut { enabled: !timer.typing; sequence: "T"; onActivated: root.today() }
    Shortcut { enabled: !timer.typing; sequence: "N"; onActivated: SettingsStore.set("calendar.nepali", !root.nepali) }

    // Header: month and year, the Nepali months it spans, and the controls.
    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Txt { text: Qt.formatDate(new Date(root.viewY, root.viewM, 1), "MMMM yyyy"); font.bold: true; font.pixelSize: Theme.fontSize + 1 }
            Txt {
                visible: root.nepali
                text: root.bsTitle !== "" ? root.bsTitle + " BS" : "Nepali dates cover 2007 to April 2028"
                color: Theme.dim; font.pixelSize: Theme.fontSize - 2
            }
        }
        Button { text: "BS"; tint: root.nepali ? Theme.accent : Theme.dim; onClicked: SettingsStore.set("calendar.nepali", !root.nepali) }
        Button { text: "‹"; implicitWidth: 30; onClicked: root.moveMonths(-1) }
        Button { text: "Today"; onClicked: root.today() }
        Button { text: "›"; implicitWidth: 30; onClicked: root.moveMonths(1) }
    }

    // Weekday names
    Row {
        Layout.fillWidth: true
        spacing: 2
        Item { visible: root.weekNumbers; width: root.weekColW; height: 1 }
        Repeater {
            model: 7
            delegate: Txt {
                required property int index
                width: root.cellW
                horizontalAlignment: Text.AlignHCenter
                text: Qt.locale().dayName((root.weekStart + index) % 7, Locale.ShortFormat)
                color: (root.weekStart + index) % 7 === 6 && root.nepali ? Theme.crit : Theme.dim
                font.pixelSize: Theme.fontSize - 2
            }
        }
    }

    // The month: six rows of seven days, always, so the popup keeps one height.
    Column {
        id: monthGrid
        Layout.fillWidth: true
        spacing: 2
        Repeater {
            model: 6
            delegate: Row {
                id: weekRow
                required property int index
                spacing: 2
                Txt {
                    visible: root.weekNumbers
                    width: root.weekColW; height: root.cellH
                    horizontalAlignment: Text.AlignHCenter
                    text: { const c = root.cells[weekRow.index * 7]; return Cal.isoWeek(c.y, c.m, c.d) }
                    color: Theme.dim; font.pixelSize: Theme.fontSize - 3
                }
                Repeater {
                    model: 7
                    delegate: Rectangle {
                        id: cell
                        required property int index
                        readonly property var c: root.cells[weekRow.index * 7 + index]
                        readonly property bool isToday: c.y === root.todayY && c.m === root.todayM && c.d === root.todayD
                        readonly property bool isSel: c.y === root.selY && c.m === root.selM && c.d === root.selD
                        readonly property bool saturday: new Date(c.y, c.m, c.d).getDay() === 6
                        width: root.cellW; height: root.cellH
                        radius: Theme.controlRadius
                        color: isToday ? Theme.accentSoft : isSel || hit.containsMouse ? Theme.control : "transparent"
                        border.width: isSel ? Theme.hair * 2 : 0
                        border.color: Theme.accent
                        Column {
                            anchors.centerIn: parent
                            spacing: -1
                            Txt {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: cell.c.d
                                font.bold: cell.isToday
                                color: cell.isToday ? Theme.accent : !cell.c.inMonth ? Theme.dim
                                     : cell.saturday && root.nepali ? Theme.crit : Theme.fg
                                opacity: cell.c.inMonth ? 1 : 0.7
                            }
                            Txt {
                                anchors.horizontalCenter: parent.horizontalCenter
                                visible: root.nepali && cell.c.bs !== null
                                text: !cell.c.bs ? "" : cell.c.bs.day === 1 ? Cal.BS_MONTHS_NE[cell.c.bs.month] : Cal.nepaliDigits(cell.c.bs.day)
                                color: Theme.dim
                                font.pixelSize: Theme.fontSize - 3
                            }
                        }
                        MouseArea {
                            id: hit
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.select(cell.c.y, cell.c.m, cell.c.d)
                        }
                    }
                }
            }
        }
        WheelHandler {                                   // scroll the month
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: ev => root.moveMonths(ev.angleDelta.y > 0 ? -1 : 1)
        }
    }

    // The selected day
    PopupSection { ColumnLayout {
        Layout.fillWidth: true
        spacing: 2
        RowLayout {
            Layout.fillWidth: true
            Txt { text: Qt.formatDate(root.selDate, "dddd, d MMMM yyyy"); font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
            Txt { text: root.relative(); color: Theme.accent }
        }
        Txt {
            visible: root.nepali
            text: root.selBS
                ? Cal.BS_MONTHS[root.selBS.month] + " " + root.selBS.day + ", " + root.selBS.year + " BS   "
                  + Cal.BS_MONTHS_NE[root.selBS.month] + " " + Cal.nepaliDigits(root.selBS.day) + ", " + Cal.nepaliDigits(root.selBS.year)
                : "Outside the Nepali table (2007 to April 2028)"
            color: Theme.dim
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
        Txt {
            text: "Week " + Cal.isoWeek(root.selY, root.selM, root.selD) + "  ·  day "
                  + (Cal.dayNum(root.selY, root.selM, root.selD) - Cal.dayNum(root.selY, 0, 1) + 1) + " of "
                  + (Cal.dayNum(root.selY + 1, 0, 1) - Cal.dayNum(root.selY, 0, 1))
            color: Theme.dim
        }
        Txt {
            visible: root.moonOn
            readonly property var m: Cal.moon(root.selY, root.selM, root.selD)
            text: m.icon + " " + m.name + "  ·  " + Math.round(m.lit * 100) + "% lit"
            color: Theme.dim
        }
    } }

    // How much of the year and the month is gone, as tiles: Gregorian on top, Bikram Sambat under it while BS is on.
    readonly property var bsNow: Cal.toBS(todayY, todayM, now.getDate())
    readonly property var tiles: {
        const out = [
            { label: String(todayY), p: progress },
            { label: Qt.formatDate(now, "MMMM"), p: { fraction: Cal.monthProgress(now), left: Cal.daysInMonth(todayY, todayM) - now.getDate() } }
        ]
        if (nepali && bsNow)
            out.push({ label: bsNow.year + " BS", p: Cal.bsYearProgress(now) }, { label: Cal.BS_MONTHS[bsNow.month], p: Cal.bsMonthProgress(now) })
        return out
    }
    PopupSection {
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 8
            rowSpacing: 8
            Repeater {
                model: root.tiles
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    implicitHeight: Math.ceil((tile.implicitHeight + 20) / 2) * 2
                    radius: Theme.controlRadius
                    color: Theme.inset
                    ColumnLayout {
                        id: tile
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 10 }
                        spacing: 6
                        RowLayout {
                            Layout.fillWidth: true
                            Txt { text: modelData.label; color: Theme.dim; font.pixelSize: Theme.fontSize - 1; elide: Text.ElideRight; Layout.fillWidth: true }
                            Txt { text: root.pct(modelData.p.fraction); font.bold: true }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 6
                            radius: Theme.gridSquare ? 0 : 3
                            color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.12)
                            Rectangle {
                                width: parent.width * Math.min(Math.max(modelData.p.fraction, 0), 1)
                                height: parent.height
                                radius: parent.radius
                                color: Theme.accent
                            }
                        }
                        Txt { text: modelData.p.left + (modelData.p.left === 1 ? " day left" : " days left"); color: Theme.dim; font.pixelSize: Theme.fontSize - 1 }
                    }
                }
            }
        }
    }

    PopupSection {
        title: "Timer"
        TimerControls { id: timer; Layout.fillWidth: true; embedded: true }
    }
}
