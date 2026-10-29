import QtQuick
import Quickshell
import qs

// Base text style shared by every module. `fgColor` / `dimColor` are the text colours for where the text sits: inside a
// bar window they are that bar's colours (readable on the wallpaper behind a translucent bar, modules/bar/BarContrast),
// everywhere else Theme.fg / Theme.dim. Bar widgets use these instead of Theme.fg / Theme.dim.
Text {
    readonly property var hostWindow: QsWindow.window
    readonly property color fgColor: hostWindow && hostWindow.barFg !== undefined ? hostWindow.barFg : Theme.fg
    readonly property color dimColor: hostWindow && hostWindow.barDim !== undefined ? hostWindow.barDim : Theme.dim

    // Bar widgets lean toward a wallpaper tint (`tone(Theme.accent2)`); on a bar whose text colour was flipped to stay
    // readable on a bright wallpaper the tints (made for the dark palette background) would not read, so it stays plain.
    readonly property bool tintOk: !hostWindow || hostWindow.barFg === undefined || String(hostWindow.barFg) === String(Theme.fg)
    function tone(c: color): color { return tintOk ? Theme.tinted(c, fgColor) : fgColor }

    color: fgColor
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    verticalAlignment: Text.AlignVCenter
}
