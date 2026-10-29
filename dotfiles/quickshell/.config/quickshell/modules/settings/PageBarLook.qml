import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Bar > Look: how see-through the bar is, its blur, the backgrounds behind the widgets and the widget icons. Blur is only
// meaningful behind a translucent bar and the pill radius only with pills, so those rows are disabled (dimmed) otherwise.
// The blur is the bar's own (modules/bar/BarBlur), so its strength is tuned here apart from the windows' blur.
SettingsPage {
    id: page
    note: "Text colour adapts to the wallpaper behind a translucent bar."

    readonly property var opacity_: SettingsStore.shown("shell.barOpacity")
    readonly property bool translucent: typeof page.opacity_ === "number" && page.opacity_ < 1.0
    readonly property bool blurOn: SettingsStore.shown("shell.barBlur") === true
    readonly property var pills: SettingsStore.shown("shell.barPills")

    SettingsSection {
        title: "Background"
        SettingSlider { label: "Opacity"; hint: "Below 100% the wallpaper shows through"; key: "shell.barOpacity"; from: 0.2; to: 1.0; step: 0.05; percent: true }
        SettingToggle { label: "Blur behind the bar"; hint: "Needs an opacity below 100%"; key: "shell.barBlur"; enabled: page.translucent }
        SettingSlider { label: "Blur strength"; hint: "Only the bar: windows keep their own blur (Windows › Look)"; key: "shell.barBlurAmount"; from: 0.05; to: 1.0; step: 0.05; enabled: page.translucent && page.blurOn; percent: true }
    }

    SettingsSection {
        title: "Widget background"
        SettingChoice { label: "Style"; key: "shell.barPills"; model: [
            { value: "off", label: "None" }, { value: "grouped", label: "One per group" },
            { value: "individual", label: "One per widget" }] }
        SettingSlider { label: "Widget padding"; hint: "Extra space inside each widget, left and right (top and bottom in a vertical bar)"; key: "shell.barItemPad"; from: 0; to: 24; step: 2; suffix: " px" }
        SettingSlider { label: "Corner radius"; key: "shell.pillRadius"; from: 0; to: 16; step: 2; enabled: page.pills !== "off"; suffix: " px" }
        SettingSlider { label: "Opacity"; key: "shell.pillOpacity"; from: 0.0; to: 1.0; step: 0.05; enabled: page.pills !== "off"; percent: true }
    }

    SettingsSection {
        title: "Widget icons"
        SettingSlider { label: "Icon to text gap"; hint: "Spaces between a widget's icon and its text (about 8 px each)"; key: "bar.iconGap"; from: 1; to: 6; step: 1; enabled: SettingsStore.shown("bar.iconsOnly") !== true }
        SettingToggle { label: "Icons only"; hint: "Hide the text of every widget: the icon alone, and a dot instead of a count on notifications and updates"; key: "bar.iconsOnly" }
        SettingChoice { label: "Wi-Fi"; key: "bar.iconWifi"; model: BarIcons.choices("wifi") }
        SettingChoice { label: "Bluetooth"; key: "bar.iconBluetooth"; model: BarIcons.choices("bluetooth") }
        SettingChoice { label: "Volume"; key: "bar.iconAudio"; model: BarIcons.choices("audio") }
        SettingChoice { label: "Battery"; key: "bar.iconBattery"; model: BarIcons.choices("battery") }
        SettingChoice { label: "Brightness"; key: "bar.iconDisplay"; model: BarIcons.choices("display") }
        SettingChoice { label: "Settings"; key: "bar.iconSettings"; model: BarIcons.choices("settings") }
    }
}
