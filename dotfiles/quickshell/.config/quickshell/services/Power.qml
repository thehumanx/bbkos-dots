pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower

// Battery and power-profile state. All values are bindings fed by UPower / power-profiles-daemon over D-Bus.
Singleton {
    id: root
    readonly property var device: UPower.displayDevice
    readonly property bool present: device.isLaptopBattery
    readonly property int percent: Math.round(device.percentage * 100)   // UPower reports a 0-1 fraction
    // Named "discharging", not "onBattery": QML reads a property called on<Capital> as a signal handler and the binding never ran.
    readonly property bool discharging: device.state === UPowerDeviceState.Discharging || device.state === UPowerDeviceState.PendingDischarge
    readonly property bool charging: device.state === UPowerDeviceState.Charging
    readonly property int profile: PowerProfiles.profile                 // 0 power-saver, 1 balanced, 2 performance
    readonly property bool hasPerformance: PowerProfiles.hasPerformanceProfile
    function setProfile(p: int) { PowerProfiles.profile = p }

    // The real battery (the display device is a composite with no path of its own).
    readonly property var battery: UPower.devices.values.find(d => d.isLaptopBattery) ?? null
    readonly property real watts: Math.abs(device.changeRate)
    readonly property real healthPercent: battery && battery.healthSupported ? battery.healthPercentage : -1
    readonly property int secondsLeft: charging ? device.timeToFull : device.timeToEmpty   // 0 = UPower has no estimate yet

    // Is any charger or USB-C source connected? Windows and macOS show the plug the moment power arrives; UPower only
    // says "charging" 2-3 s later (the embedded controller flips the battery state late, measured 2026-10-19: cable
    // event, adapter online 0.3 s later, UPower 1 s after that, battery "Charging" 2 s after that). So the bar and the
    // popup follow this instead: a long-running `udevadm monitor` (idle until the kernel reports a power-supply
    // change) re-reads the supplies' `online` files straight from sysfs.
    property bool pluggedIn: false
    Process {
        id: probe
        command: ["sh", "-c", "for d in /sys/class/power_supply/*; do [ \"$(cat $d/type)\" = Battery ] && continue; [ \"$(cat $d/online 2>/dev/null)\" = 1 ] && exit 0; done; exit 1"]
        onExited: code => root.pluggedIn = code === 0
    }
    Process {
        running: true
        command: ["udevadm", "monitor", "--kernel", "--subsystem-match=power_supply"]
        stdout: SplitParser { onRead: line => { if (line.includes("power_supply")) debounce.restart() } }
    }
    Timer { id: debounce; interval: 100; onTriggered: if (!probe.running) probe.running = true }
    Component.onCompleted: probe.running = true
}
