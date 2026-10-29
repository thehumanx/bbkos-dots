# Module: stage mode

A macOS Stage Manager-style mode (added 2026-10-21), **per workspace since 2026-10-23**. A stage workspace opens windows
one at a time, full size, instead of tiling them, and the other windows of the workspace wait in a rail of small
thumbnail cards along one edge. A click on a card brings that window to the front. `stage.enabled` (Settings, "Stage
mode by default") is the mode every workspace starts in; the overview switch ("Stage mode for workspace N"),
`Super+Alt+S` or `qs ipc call stagews set NAME true|false` switch one workspace until the next boot. Every size and look
of the rail is on the Stage mode settings page. Source:
`dotfiles/quickshell/.config/quickshell/modules/stage/{Stage,StageCard,StillImage}.qml`, `services/StageState.qml`,
`modules/settings/PageStage.qml`, `bbkos_theme/{settings,render,keybinds}.py`.

## Per workspace (2026-10-23)

- **Default:** `stage.enabled` becomes Hyprland's `general.layout` (`monocle` or `dwindle`, `render.py`), as before.
- **One workspace different:** `StageState.qml` adds a runtime workspace rule, `hl.workspace_rule({ workspace = "3",
  layout = "monocle" })` (or `"dwindle"`), through `hyprctl eval`. Measured on Hyprland 0.56.2 on a spare workspace
  holding two probe windows: the rule switches a workspace that already exists and re-tiles it at once; a later rule
  for the same workspace wins; the handle's `set_enabled(false)` puts it back to the default at once; `hyprctl reload`
  drops every runtime rule. So the handles live in a Lua global `BBKOS_STAGE` (one per workspace, the old one disabled
  before a new one is added), and on Hyprland's `configreloaded` event every rule is added again.
- **Until reboot:** the choices are in `$XDG_RUNTIME_DIR/bbkos-stage.json` (`{"9": false}`, only workspaces that differ
  from the default), a tmpfs emptied at shutdown. They survive a shell restart and a Hyprland reload (both checked).
  Changing the default clears them (every workspace follows the new default).
- **Rail and keys:** the rail shows on a monitor only while its active workspace is a stage workspace
  (`StageState.isStage(name)`); `Super`+arrows read the active workspace's own layout
  (`hl.get_active_workspace().tiled_layout`, `keybinds.py`) when pressed.
- **Test hooks:** `qs ipc call stagews status | set NAME BOOL | toggle NAME` (`""` = the focused workspace);
  `qs ipc call stage status` shows `workspace` and `stage` per screen.
- **Verified:** on a spare workspace 9 with two probe windows: off gave `dwindle` while workspace 1 stayed `monocle`;
  the file held `{"9":false}`; after `systemctl --user restart quickshell` and after `hyprctl reload` workspace 9 was still
  `dwindle`; back to the default removed the rule and emptied the file; the overview header reads "Stage mode for
  workspace 1" (screenshot); `tiled_layout` read from Lua; keybinding tests. **Not verified:** a real reboot (the file is
  on a tmpfs, so it cannot survive one), a real `Super+Alt+S` press and the arrows on a mixed setup, the overview switch
  clicked on a workspace other than the focused one, a second monitor.

## How it works

- **Layout: Hyprland's built-in `monocle`.** `stage.enabled` makes `render.py` emit `general.layout = "monocle"` instead of
  `"dwindle"` in `hypr-theme.lua`. Every workspace then stacks its tiled windows at full size with the newest focus on
  top, which is exactly "each new window opens as if it were the only one". Switching the layout live re-tiles windows
  that are already open, in both directions (checked with two terminals). Floating windows are not part of the stage.
- **Rail: one Quickshell `PanelWindow` per screen** (`Stage.qml`, layer `Top`, namespace `bbkos-stage`). It lists the
  tiled windows of the monitor's active workspace except the front one (the front one is the tiled window with the
  lowest `focusHistoryID`), and exists only while the workspace has two or more windows (or one, with
  `stage.showWithOneWindow`). With `stage.reserveSpace` it takes an exclusive zone like the bar, so the front window is
  resized when the rail appears or goes away; a reserving rail sits in the compositor's usable area, so it needs no margin
  for the bar (an extra margin put it 36 px too low); without reserving it spans the screen edge and takes the bar's inset.
- **Cards** (`StageCard.qml`): the contents (screenshot and caption) are drawn into a layer and masked with the rounded
  card shape (`MultiEffect` mask), and the border is drawn on top; `clip: true` only clips to a rectangle, so the
  screenshot and the caption bar used to poke out of the rounded corners (fixed 2026-10-21, checked at radius 24 and 10
  with `grim`). A still screenshot of the window (`hyprland-toplevel-export-v1`, which captures windows
  that are covered by the front one), its title and app icon. The cards come from a `ListModel` diffed against the window
  list, so a Hyprland refresh never recreates a screenshot (same lesson as the overview). `StillImage.qml` refreshes a
  still without a blink: the new capture is built under the shown one and swapped in when its frame has arrived, and it
  is drawn through a layer because `ScreencopyView` does not blend (see the overview doc, translucent windows).
- **Refresh**: a still is taken when a card is created, when the front window changes, and every
  `stage.refreshSeconds` while a rail is visible (0 = only on a switch). Hyprland events (open, close, move, focus,
  workspace, fullscreen, float) refresh Quickshell's window models on a 140 ms debounce, only while the mode is on.
- **Keys**: in monocle `Super+Left/Right/Up/Down` (focus) would do nothing, so `keybinds.py` renders those four binds as
  Lua functions that check the active workspace's layout (`hl.get_active_workspace().tiled_layout == "monocle"`; until
  2026-10-23 the global `general.layout`) at press time: left/up cycle to the previous
  window (`hl.dsp.layout("cycleprev")`), right/down to the next (`cyclenext`); in any other layout they are the normal
  directional focus. No regeneration is needed when the mode is switched.

## Settings (`stage.*`, `settings.py`)

| Key | Range / values | Default |
|---|---|---|
| `enabled` | on/off: the default for every workspace | off |
| `railPosition` | left, right | left |
| `railWidth` | 100-320 step 10 | 150 |
| `railPadding` | 0-32 step 2 | 12 |
| `railOpacity` | 0.0-1.0 (rail background) | 0.0 |
| `cardHeight` | 60-240 step 10 | 100 |
| `cardGap` | 0-32 step 2 | 12 (0 while grid mode is on: the previews touch) |
| `cardRadius` | 0-24 step 2 | 10 |
| `showTitle`, `showIcon` | on/off | on |
| `order` | recent, opened | recent |
| `refreshSeconds` | 0-30 | 3 |
| `showWithOneWindow` | on/off | off |
| `reserveSpace` | on/off | on |
| `animations` | on/off (card hover grow) | on |

`bbkos-theme set stage.railWidth 180`, `bbkos-theme reset stage`; each card of Windows › Stage mode has "Reset these" (the Reset page's "Stage mode" row until 2026-10-28). The CLI and the
settings page use the same keys.

## Prior art

- [omarchy-stage-manager](https://github.com/debba/omarchy-stage-manager): a Quickshell Stage Manager sidebar with
  preview cards (sidebar only, no layout change) — the reference for the rail.
- Hyprland's [monocle layout](https://wiki.hypr.land/Configuring/Layouts/Monocle-Layout/), built in since 0.56 (the
  `hyprland-monocle` plugin and tab groups were not needed).

## Measured and verified (2026-10-21)

- Live layout switch with open windows, `hyprctl clients`: dwindle halves became full width in monocle and back.
- Windows in monocle are not `hidden`, so the covered ones can be captured (a real Zen window showed as a card).
- Rail geometry and the front window for bar top, left, bottom, right, rail on the right, and `reserveSpace` off, from
  `hyprctl layers` and `hyprctl clients` (for example bar top, rail left: rail `0 36 150 1164`, window `157 43 1756 1150`).
- Focus: `hl.dsp.focus({ window = ... })` brought a covered window to the front and the rail followed;
  `hl.dsp.layout("cyclenext")` and `("cycleprev")` cycle; `focus left` alone does nothing in monocle.
- Switching through `SettingsStore` (as the overview switch does): off gives `dwindle`, on gives `monocle`.
- CPU of Quickshell over 15 s with a rail of 2 cards: 90 ms with 3 s refresh, 0 with refresh off, 10 ms with stage off.

**Not verified:** a real mouse click on a card or on the overview switch (no pointer injection here; the dispatch and
the settings path were exercised instead), the physical `Super`+arrow keys (the generated Lua loads without errors and
its calls were run through `hyprctl eval`), a second monitor, windows that are fullscreen, and battery impact over time.

## Known limits

- Monitor x/y in Quickshell can go stale after a hotplug or layout change, which drops every window of that monitor (empty rail). `refreshNow` calls `Hyprland.refreshMonitors()`, and `hyprland.lua` runs `qs ipc call display monitorsChanged` on the Lua events `monitor.layout_changed`, `monitor.added` and `monitor.removed` (a monitor move sends no socket event) (2026-10-25); `qs ipc call stage status` shows each screen's `frame` and toplevel count to check.
- The stills are not live; a window that changes while it is in the rail is as old as the last refresh.
- The front window is resized when the rail appears (one window to two) or goes away, as on macOS.
- The overview's workspace card of a stage workspace shows stacked windows, so its miniature looks like one window.
- A card removed from the rail disappears at once (no exit animation).

## Cursor on rail clicks (2026-10-21)

A rail click focuses the window with `hl.dsp.focus`, which warps the cursor to that window's centre. `Stage.focusWindow` wraps the call in `hyprctl eval` that turns `cursor.no_warps` on for this one focus and restores the value read before (`hl.get_config('cursor.no_warps')`, a boolean). Test hook: `qs ipc call stage focus ADDRESS`. The Super+arrow cycling (`cyclenext` / `cycleprev` in monocle) is a plain dispatcher and still warps.
