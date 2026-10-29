pragma Singleton
import Quickshell

// Whether the bar is hidden (Super+Shift+Space, `qs ipc call bar toggle`). Runtime only: a restart brings the bar
// back. While hidden the bar's layer surface is unmapped, so its reserved edge is freed, and Theme.barInset is 0 so
// panels, notifications, the OSD, the overview and the stage rail use that space.
Singleton {
    property bool hidden: false
}
