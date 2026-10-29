import QtQuick
import QtQuick.Layouts
import qs.components

// The timer popup (PanelState "timer"): opened by the timer widget in the bar, which shows while a timer exists.
ColumnLayout {
    TimerControls { Layout.fillWidth: true; autoFocus: true }
}
