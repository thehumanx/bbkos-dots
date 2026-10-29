import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Recording indicator: a red dot and the elapsed time while bbkos-record is recording (the BarItem hides it otherwise).
// Click stops and saves the recording. Start one with the keys or the Recording options panel (docs/modules/capture.md).
Txt {
    horizontalAlignment: Text.AlignHCenter
    // A recording dot is red whatever the palette: Theme.crit can be near-white (high contrast), which would not read as one.
    textFormat: Text.StyledText
    text: Theme.barIconsOnly ? "<font color=\"#ff4d4d\">●</font>" : Theme.barVertical ? "<font color=\"#ff4d4d\">●</font><br>" + Record.clock : "<font color=\"#ff4d4d\">●</font>" + BarIcons.gapText(Theme.barIconGap) + Record.clock
    font.bold: true

    BarHit { onClicked: Record.stop() }
}
