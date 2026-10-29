import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components
import qs.services
import "../../components/Duration.js" as Duration

// Battery popup: charge and time left, power draw / health / cycles, the power profile, and screen-on time since boot
// and since the charger was unplugged (services/ScreenTime). Everything is read-only except the profile.
ColumnLayout {
    id: root
    spacing: 10

    function duration(sec: real): string { return Duration.approx(sec) }
    readonly property string state: Power.charging ? "Charging" : Power.pluggedIn ? (Power.percent >= 99 ? "Fully charged" : "Plugged in")
                                  : "On battery"
    readonly property string timeText: !(Power.charging || Power.discharging) ? ""      // plugged in, not charging: UPower's estimate is stale
                                     : Power.secondsLeft > 0 ? duration(Power.secondsLeft) + (Power.charging ? " until full" : " left")
                                     : "Estimating..."

    FileView {                                    // read when the popup opens: nothing runs while it is closed
        id: cycles
        path: Power.battery ? "/sys/class/power_supply/" + Power.battery.nativePath + "/cycle_count" : ""
        blockLoading: true
    }
    readonly property string cycleText: { try { return cycles.text().trim() } catch (e) { return "" } }

    PopupHeader { title: "Battery"; status: root.state; statusColor: Power.pluggedIn ? Theme.accent : Theme.dim }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Txt { text: Power.percent + "%"; font.pixelSize: Theme.fontSize * 2; font.bold: true }
        Txt { text: root.timeText; color: Theme.dim; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 8
        radius: Theme.gridSquare ? 0 : 4
        color: Theme.inset
        Rectangle {
            width: parent.width * Math.min(Power.percent, 100) / 100
            height: parent.height
            radius: parent.radius
            color: Power.charging ? Theme.accent : (Power.discharging && Power.percent <= 10) ? Theme.crit
                 : (Power.discharging && Power.percent <= 20) ? Theme.warn : Theme.accent
        }
    }

    PopupSection { RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Repeater {
            model: [
                { label: "Power",  value: Power.watts > 0 ? Power.watts.toFixed(1) + " W" : "-" },
                { label: "Health", value: Power.healthPercent >= 0 ? Math.round(Power.healthPercent) + "%" : "-" },
                { label: "Cycles", value: root.cycleText !== "" ? root.cycleText : "-" }
            ]
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                spacing: 2
                Txt { text: modelData.value; font.bold: true }
                Txt { text: modelData.label; color: Theme.dim; font.pixelSize: Theme.fontSize - 1 }
            }
        }
    } }

    PopupSection {
        Txt { text: "Power mode" }
        Chips {
            model: [{ value: 0, label: "Battery" }, { value: 1, label: "Balanced" }]
                   .concat(Power.hasPerformance ? [{ value: 2, label: "Performance" }] : [])
            current: Power.profile
            onChosen: v => Power.setProfile(v)
        }
    }

    SettingRow {
        label: "Uptime"; labelWidth: 196
        Txt { text: root.duration(ScreenTime.uptimeSeconds); Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
    }
    SettingRow {
        label: Power.discharging ? "Since last charge" : "Plugged in for"; labelWidth: 196
        Layout.bottomMargin: -12                                // the card margin already gives the room below
        Txt { text: ScreenTime.chargerSeconds < 0 ? "-" : root.duration(ScreenTime.chargerSeconds); Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
    }
}
