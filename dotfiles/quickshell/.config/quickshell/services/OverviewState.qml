pragma Singleton
import Quickshell
import Quickshell.Hyprland

// State of the workspace overview (modules/overview). The bar icon and IPC toggle it; the overlay itself only exists
// while open. `selected` is the workspace whose windows are shown; it resets to the focused workspace each time the
// overview opens, and clicking a card only changes it, never the real focus. The strip shows the workspaces Hyprland
// currently has plus any empty ones added with the "+" card (`extra`); an added slot becomes a real workspace when it
// is focused or receives a window. `screen` is only set by openOn with a screen name: opened through IPC or a
// gesture it stays "" (`target` still latches the focused screen), and a bar icon click on that state closes the overview rather than re-selecting a screen.
Singleton {
    property bool open: false
    property string screen: ""            // the screen the bar icon was on; "" when opened by IPC or a gesture
    property string target: ""            // the screen that shows the overview, fixed at open so the cursor cannot move it
    property int selected: 1
    property var extra: []                // ids added with "+" while open; reset on close

    function focusedWorkspaceId(): int {
        const ws = Hyprland.focusedWorkspace
        const id = ws ? Number(ws.id) : 0
        return id >= 1 ? id : 1
    }

    function openOn(screenName: var): void {
        const name = typeof screenName === "string" ? screenName : ""
        screen = name
        target = name !== "" ? name : (Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        extra = []
        selected = focusedWorkspaceId()
        open = true
    }

    function toggle(screenName: var): void {
        const name = typeof screenName === "string" ? screenName : ""
        // Close when the click is on the screen the overview was opened from, and also when it was opened with no
        // screen (IPC or gesture, screen == ""): a bar click must always be able to close it then.
        if (open && (name === "" || name === screen || screen === "")) { close(); return }
        openOn(name)
    }

    // Add an empty workspace slot to the strip and select it. The lowest free positive id is used (1-10 first, so it
    // gets a Super+N bind, then beyond); Hyprland only creates the workspace when it is focused or gets a window.
    function addWorkspace(): int {
        const used = ({})
        const workspaces = Hyprland.workspaces.values
        for (let i = 0; i < workspaces.length; i++) {
            const id = Number(workspaces[i].id)
            if (id >= 1) used[id] = true
        }
        for (let i = 0; i < extra.length; i++) used[Number(extra[i])] = true
        let id = 1
        while (used[id]) id++
        extra = extra.concat([id])
        selected = id
        return id
    }

    function close(): void { open = false; extra = [] }
}
