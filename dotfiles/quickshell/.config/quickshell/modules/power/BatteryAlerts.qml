import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import "../../components/Duration.js" as Duration

// Battery warnings. The bar only changes colour, so without this nothing would say "plug in" away from the desk.
// UPower hibernates at 5 % (/etc/UPower/UPower.conf.d/10-bbkos.conf); these come first: 15 % normal, 8 % critical.
// Each level fires once per discharge and re-arms when the charge rises above 18 % or the charger is plugged in.
Scope {
    id: root
    property int stage: 0          // 0 none, 1 low sent, 2 critical sent

    function evaluate(percent: int, onBattery: bool) {
        if (!onBattery) { stage = 0; return }
        if (percent <= 8 && stage < 2) {
            stage = 2
            Quickshell.execDetached(["notify-send", "-u", "critical", "-a", "Battery", "Battery " + percent + "%",
                "Plug in now. The laptop hibernates at 5%. Save your work."])
        } else if (percent <= 15 && stage < 1) {
            stage = 1
            Quickshell.execDetached(["notify-send", "-a", "Battery", "Battery " + percent + "%",
                (Power.discharging && Power.secondsLeft > 0 ? "About " + Duration.approx(Power.secondsLeft) + " left. " : "") + "Plug in soon."])
        } else if (percent > 18) {
            stage = 0
        }
    }

    function check() { if (Power.present) evaluate(Power.percent, Power.discharging) }

    // Singletons start lazily and the battery popup may never be opened: touching ScreenTime here starts its counting at login.
    // Same for PowerTuning (runs the power helper at login, then on profile / charger / settings changes).
    Component.onCompleted: { ScreenTime.interval; PowerTuning.status }

    // Services start lazily: wait a moment for UPower before the first reading.
    Timer { interval: 3000; running: true; onTriggered: root.check() }
    Connections {
        target: Power
        function onPercentChanged() { root.check() }
        function onDischargingChanged() { root.check() }
    }

    IpcHandler {                   // test hook: qs ipc call power status | apply (docs/modules/power-tuning.md)
        target: "power"
        function status(): string { return JSON.stringify({ status: PowerTuning.status, helper: PowerTuning.helperPath, seen: PowerTuning._powerJson, last: PowerTuning.last }) }
        function apply(): void { PowerTuning.apply("ipc") }
    }

    IpcHandler {                   // test hook: qs ipc call battery simulate 8
        target: "battery"
        function simulate(percent: int): void { root.evaluate(percent, true) }
        function status(): string {
            return JSON.stringify({ percent: Power.percent, discharging: Power.discharging, watts: Power.watts, health: Power.healthPercent,
                                    secondsLeft: Power.secondsLeft, charging: Power.charging, pluggedIn: Power.pluggedIn, profile: Power.profile,
                                    screenBoot: ScreenTime.bootSeconds, screenUnplug: ScreenTime.unplugSeconds,
                                    uptime: ScreenTime.uptimeSeconds, sinceCharger: ScreenTime.chargerSeconds })
        }
    }
}
