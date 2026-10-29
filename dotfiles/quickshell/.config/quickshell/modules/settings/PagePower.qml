import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components
import qs.services

// Power page: what each power profile does. Per profile the CPU energy preference (EPP), turbo and a package power cap;
// every knob starts at "System default" (power-profiles-daemon stays in charge). Keys and values mirror settings.py
// (power.<saver|balanced|performance>Epp / Turbo / Cap). The root helper bbkos-power-apply applies them for the active
// profile (services/PowerTuning.qml); this page only edits settings and shows what the kernel really holds right now.
// The battery's charge mode (power.chargeMode) is one setting for every profile, applied by the same helper.
// The numbers in the hints are measurements on this laptop (docs/modules/power-tuning.md).
SettingsPage {
    id: page
    note: "Nothing is overridden until you change a value. The profile values reset on reboot; the battery keeps its charge mode."

    readonly property var profiles: [
        { name: "Battery saver", p: "saver" }, { name: "Balanced", p: "balanced" }, { name: "Performance", p: "performance" }]
    readonly property var eppModel: [
        { value: "default", label: "System default" }, { value: "performance", label: "Performance" },
        { value: "balance_performance", label: "Balance performance" }, { value: "balance_power", label: "Balance power" },
        { value: "power", label: "Power" }]
    readonly property var turboModel: [
        { value: "default", label: "System default" }, { value: "on", label: "On" }, { value: "off", label: "Off" }]
    readonly property var capModel: [
        { value: 0, label: "Off" }, { value: 12, label: "12 W" }, { value: 16, label: "16 W" },
        { value: 20, label: "20 W" }, { value: 24, label: "24 W" }]
    readonly property var chargeModel: [
        { value: "default", label: "System default" }, { value: "Fast", label: "Fast" },
        { value: "Standard", label: "Standard" }, { value: "Long_Life", label: "Limit to ~80 %" }]

    // Opening the page re-runs the helper: the service only learns that it was installed (or broke) when it next runs, so a
    // banner left over from before an install would otherwise stay until the next profile, charger or settings change.
    Component.onCompleted: PowerTuning.apply("page")

    // What the kernel holds now (readable without root). sysfs does not notify, so a timer re-reads the files.
    property int tick: 0
    function read(view): string { try { return view.text().trim() } catch (e) { return "" } }
    readonly property string appliedText: {
        tick
        const epp = read(eppFile), turbo = read(turboFile), cap = parseInt(read(capFile))
        return "EPP " + (epp || "-") + "  ·  turbo " + (turbo === "1" ? "off" : turbo === "0" ? "on" : "-")
             + "  ·  cap " + (cap > 0 ? Math.round(cap / 1000000) + " W" : "-")
    }
    FileView { id: eppFile; path: "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"; blockLoading: true }
    FileView { id: turboFile; path: "/sys/devices/system/cpu/intel_pstate/no_turbo"; blockLoading: true }
    FileView { id: capFile; path: "/sys/class/powercap/intel-rapl-mmio:0/constraint_0_power_limit_uw"; blockLoading: true }
    // charge_types lists every mode with the active one in brackets: "[Fast] Standard Long_Life".
    FileView { id: chargeFile; path: "/sys/class/power_supply/BAT0/charge_types"; blockLoading: true }
    readonly property string chargeText: {
        tick
        const m = read(chargeFile).match(/\[([^\]]+)\]/)
        if (!m) return "-"
        const opt = page.chargeModel.find(o => o.value === m[1])
        return opt ? opt.label : m[1]
    }
    Timer {
        interval: 2000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: { eppFile.reload(); turboFile.reload(); capFile.reload(); chargeFile.reload(); page.tick++ }
    }

    SettingsSection {
        title: "Helper"
        description: "bbkos-power-apply applies these for the active profile."
        SettingRow {
            visible: PowerTuning.status === "not-installed" || PowerTuning.status.startsWith("error: ")
            label: PowerTuning.status === "not-installed" ? "Helper not installed" : "Helper error"
            hint: PowerTuning.status === "not-installed" ? "Nothing is applied yet. Run: sudo ~/.local/share/bbkos/repo/scripts/install-power-helper.sh" : PowerTuning.status.slice(7)
            Item { Layout.fillWidth: true }
        }
        SettingRow {
            label: "Applied now"
            hint: "What the kernel holds right now"
            Txt { text: page.appliedText; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
        }
    }

    SettingsSection {
        title: "Battery charging"
        description: "One mode for every profile. The battery keeps the last mode set, also in Windows."
        SettingChoice { label: "Charging"; hint: "Fast charging adds wear. The limit stops charging at about 80 % so the battery lasts more years. System default changes nothing."
            key: "power.chargeMode"; model: page.chargeModel }
        SettingRow {
            label: "Charging now"
            hint: "The mode the battery reports"
            Txt { text: page.chargeText; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
        }
    }

    Repeater {
        model: page.profiles
        delegate: SettingsSection {
            id: section
            required property var modelData
            readonly property bool active: ["saver", "balanced", "performance"][Power.profile] === modelData.p
            title: modelData.name + (active ? "  (active)" : "")

            SettingChoice { label: "CPU energy preference"; hint: "Power saves the most energy per job. Balance performance is about 25% faster for 30% more power."
                key: "power." + section.modelData.p + "Epp"; model: page.eppModel }
            SettingChoice { label: "Turbo"; hint: "Off is cooler but slower. The Power preference saves the same energy with less slowdown."
                key: "power." + section.modelData.p + "Turbo"; model: page.turboModel }
            SettingChoice { label: "Package power cap"; hint: "Moderate risk: a sustained limit. Short bursts are unaffected; all-core work such as a big compile may slow down."
                key: "power." + section.modelData.p + "Cap"; model: page.capModel }
        }
    }
}
