# Module: workspace overview

A Mission Control-style workspace manager for Hyprland, opened from the grid icon at the start of the bar, a
three-finger swipe up (2026-10-20, see Behaviour · Gestures) or `qs ipc call overview open`. The workspaces Hyprland
currently has sit along the top, followed by a "+" card; the selected workspace's windows are drawn below at their real
positions and sizes. Click a workspace card to preview it, click it again (or double-click, or `Return`) to switch to
it, click a window to focus it, drag a window onto a card to move it there, `Esc` or a click on the empty backdrop
closes. The bar stays visible at its edge, so the grid icon is not covered and can close the overview again. Source:
`dotfiles/quickshell/.config/quickshell/modules/overview/`, `services/OverviewState.qml`,
`modules/bar/OverviewWidget.qml`.

The backdrop is not a flat panel: it is the wallpaper, blurred and tinted exactly like the bar, so the bar and the
overview read as one blurred wall (`Backdrop.qml`, why below). The focused workspace's windows shrink from their real
screen rectangles into the stage on open, staggered a little per window.

## Research first

The native overviews clone windows inside the compositor: GNOME Shell's `Clutter.Clone` and KDE's `KWin::Effect`
thumbnail both read the compositor's own buffers. A Wayland client cannot do that. The options on Hyprland were:

| Approach | Result |
|---|---|
| `hyprexpo` plugin | Closest native feel, but its grid has no transparency, no window captions and no drag-to-workspace; it also adds a C++ plugin to the compositor |
| Hyprland's `screencopy` protocol via `grim` | Works for the visible workspace only; one process per frame and no way to capture hidden workspaces |
| `hyprland-toplevel-export-v1` + Quickshell `ScreencopyView` | **Chosen.** Captures an individual toplevel by its `xdg-foreign` handle, including windows on workspaces that are not visible, with no subprocess |

Existing Quickshell configurations (caelestia, end-4, Omarchy-adjacent plugins) either use live `ScreencopyView`s for
every window (expensive) or show only the current workspace. The design here captures **only the selected workspace**
and keeps the top cards as layout miniatures, so the cost is two or three still images, not a live stream per window.

## Behaviour

- **Open**: the bar icon calls `OverviewState.toggle(screenName)`, which opens on that screen and resets `selected` to
  the focused workspace. The bar stays visible and is no longer covered: the overlay is anchored to the screen minus
  the bar edge (`Theme.barPosition`, `Theme.barInset`), so the grid icon is not obscured and can close it again. `Esc`
  and a click on the empty backdrop also close it. `toggle` closes whenever it is open and the click is on the screen
  it was opened from — **and also when it was opened with no screen at all** (`screen == ""`, which is the state after
  a gesture or a bare IPC `open`): an earlier version compared only `name === screen` and a bar click after a gesture
  open re-opened instead of closing (fixed 2026-10-20).
- **Open and close animation** (rewritten 2026-10-21): the windows live in one *screen layer*, the real monitor at 1:1
  (`Overview.qml`). A single progress value `p` (0 = desktop, 1 = overview) scales and moves that layer from the real
  screen into the stage slot (`x`, `y`, `scale` only, so it is one GPU transform and nothing is relaid out per frame),
  fades the blurred wallpaper in, and drops the workspace cards in from above, each a little after the previous one.
  Closing runs `p` backwards (260 ms), so the screen scales back up onto the real one; open is 300 ms; both use the
  drawer curve `Theme.easeDrawer` (until 2026-10-23: open 340 ms `OutCubic`, close 280 ms `InOutCubic`; `motion.md`). Card decoration (border, caption, fonts) is divided by the layer's current scale so it keeps its pixel size
  and fades in with `p`; at `p = 0` a card is just the window's own screenshot, so the swap with the real window is not
  visible. The open waits (40 ms minimum, 220 ms maximum) until every screenshot has arrived before it starts. Closing
  onto a workspace that is not on screen (Esc after previewing another one) fades the sheet instead of zooming, because
  the stage would zoom onto the wrong windows. The animation starts when the gesture ends: Hyprland runs a custom
  gesture's action once, so the overview does not follow the fingers (only the compositor's own workspace swipe does).
- **Why it was choppy before**: measured with `/proc/<pid>/stat` while opening over IPC: about 250 ms of CPU in the first
  half second (10 ms ticks, 50 ms samples). The causes were a window and a full-size live `MultiEffect` blur created on every open, a JS-array model that
  rebuilt every window card (and its screenshot) whenever Hyprland data changed, a mass capture reset 180 ms into the
  animation, per-card width/height animation, and no closing animation. After the rewrite the same first 50 ms cost
  roughly 130-200 ms over the same stretch (several runs; it varies). That is a smaller drop than first written (an earlier version of this line said 60 ms, which was an addition error): the window map and image decode still cost; what is gone is the per-frame full-size blur, the capture rebuilds and the per-card size animation. GPU load could not be measured (`intel_gpu_top` needs CAP_PERFMON), so smoothness itself is judged by eye.
- **Stable delegates**: the window cards and the workspace cards come from `ListModel`s that are diffed against the
  Hyprland data (`syncWindows`, `syncWorkspaces`), so a refresh moves cards in place and never recreates a screenshot. A
  screenshot is retaken only when a card's size really changed (debounced, only once settled). The overlay windows are
  created once and only mapped while shown; the cards (and so the captures) exist only while it is shown.
- **Reference**: the persistent-window-with-`visible` pattern and the drop-to-workspace flow follow the Quickshell
  overview extracted from end-4's illogical-impulse (`codeberg.org/fsilly/quickshell-overview`). The compositor plugins
  (Hyprspace, hymission) can follow the fingers, but they are tied to the exact Hyprland build, run inside the
  compositor and need `hyprpm`, so they were not adopted; hymission is the one to try if finger-following is wanted.
- **Backdrop**: `modules/overview/Backdrop.qml` shows the wallpaper blurred and tinted like the bar. The blur runs on a
  quarter-size copy of the wallpaper (decoded at a quarter of the physical size, `MultiEffect` radius scaled to match)
  that is scaled back up, so the shader touches 1/16 of the pixels; a live blur over the full-size image re-ran its
  passes every frame. A first version baked the blur once into a `ShaderEffectSource` (`live: false`); that texture was
  lost whenever the overlay window was unmapped, so the backdrop came back flat dark on every open but the first
  (fixed 2026-10-21, reproduced by three opens in a row, now blurred on all three). The compositor's own blur cannot
  be used: a layer rule blurs what is **behind** the overlay, which is the real windows, not the wallpaper. The mapping
  `min(1, passes × size × 10 / 64)` is the lock-screen preview's calibration, so it is close to, not identical with, the
  bar's blur. `autoPaddingEnabled: false` keeps the blur from fading toward transparent at the screen edges (the
  default padding made a dark vignette; edge brightness 122 vs 150 in the middle before, 149 vs 151 after, measured
  from a `grim` capture). On top sits `Theme.barBg`. The screen layer also carries the sharp wallpaper (decoded at half size), so
  the shrinking layer reads as the screen itself.
- **Gestures**: `bbkos-theme` maps touchpad swipe actions (Settings → Touchpad) into Hyprland gestures in
  `hypr-theme.lua`. `swipe3Up: overview` emits a Lua-function action running
  `hl.exec_cmd("qs ipc call overview open")` (open, not toggle: a second swipe up does nothing, swipe down closes).
  Inside a function `hl.dsp.exec_cmd(...)` only builds a dispatcher object and runs nothing — the earlier version used
  it and a real swipe did nothing (found 2026-10-21 with `hyprctl eval`: the dsp form created no file, `hl.exec_cmd` did). `swipe3Down: overview-close` closes
  (`overview close`), a no-op when it is not open. The three-finger left/right swipes remain Hyprland's built-in
  workspace swipe in **every** state: while the overview is open the real workspace changes behind the opaque backdrop,
  and the overview follows the change (next bullet), so the swipe moves the overview's view; closing leaves the user on
  the swiped-to workspace. Taking the gesture over in Lua would apply when the overview is closed too and would
  replace the native animated swipe with discrete switches, so it was rejected (owner chose "overview follows").
- **Screen** (2026-10-24): the screen showing the overview is latched at open in `OverviewState.target` (the bar icon's
  screen, else the focused monitor then) and never follows the cursor to another monitor; the Follow below ignores
  focus changes on the other monitor.
- **Stage switch** (2026-10-24): `StageState.overrides` changing while open triggers a refresh (and a second one 450 ms
  later), because the layout change emits no geometry event; the cards then move in place.
- **Follow**: while open, `Hyprland.focusedWorkspace` moving to another workspace sets `OverviewState.selected` to it
  and the stage slides 44 px in the change's direction (240 ms, `OutQuad`) as the transition; preview clicks slide the
  stage the same way, deliberately. The follow must **not** be read out of the `workspace` raw event: inside
  `onRawEvent` Quickshell's `focusedWorkspace` property is still stale and the handler would write the previous value
  back (observed live: selected stayed on the old workspace). It is a `Connections` `onFocusedWorkspaceChanged`
  handler, which fires after the service state has moved, and is verified live (dispatch `hl.dsp.focus({ workspace
  = N })` while open → `selected` follows, even 0.3 s after open, inside the intro window too).
- **Workspaces**: the strip lists the workspaces that currently exist in Hyprland, sorted by id, plus a "+" card. The
  fixed 1-10 range is gone; `Super+1..0` still switches between ids 1-10 because those are the keybinds.
- **Add**: clicking "+" adds the lowest free positive id to the strip and selects it without switching (1-10 first, so
  it gets a keybind, then beyond). It becomes a real workspace when it is switched to or receives a window; an unused
  added slot disappears when the overview closes. Dropping a window on "+" creates the workspace and moves the window
  there in one step.
- **Preview**: clicking a card changes only `OverviewState.selected`; the real workspace is untouched. Clicking the
  selected card, double-clicking any card, or `Return` calls `hl.dsp.focus({ workspace = N })` and closes.
- **Windows**: drawn from `Hyprland.workspaces` → `workspace.toplevels`, using `lastIpcObject`. Tiled windows first,
  then floating, each group with the most recently focused last, so the stacking matches the compositor.
- **Live updates**: opening, any relevant Hyprland event while open, and a drop refresh `Hyprland.workspaces` and
  `Hyprland.toplevels` (debounced, no polling), then the still captures are recreated. This is needed because a window
  that is retiled after another window moves gets no event carrying its new geometry, so `lastIpcObject` would stay at
  the old rectangle.
- **Focus a window**: click it. The overlay first focuses the selected workspace if needed, then the window, then
  closes. The card is a screenshot, so the click target is the card, not the client surface.
- **Drag**: press a window card and it follows the pointer; the workspace card under the pointer gets the accent
  border and "Move here". The preview shrinks to at most 112x72 (well under the 160x104 workspace card) so it does not
  hide the strip. Release moves the window; dropping anywhere else cancels. Pressing on a workspace card never starts a
  window drag, and navigation shortkeys are ignored while a window is in flight.
- **Empty workspaces**: a workspace with no windows shows "empty" in its card; selecting it shows "No windows on this
  workspace" in the stage. A workspace always exists while it is focused, so the focused empty one is always a card.

Keyboard: `Left`/`Right` move through the visible cards (including an added one), `Return` switches, `Esc` closes.
There is deliberately no global bind in V1 (the bar icon and IPC are enough); adding one is a one-line `hl.bind` when
wanted.

## Files

| File | Role |
|---|---|
| `modules/overview/Overview.qml` | Layer-shell `PanelWindow` per screen (`Variants`, persistent, mapped while shown) plus a transparent bar-strip click catcher, backdrop, workspace strip, stage, open-animation and follow plumbing, stage slide, drag state and hit-testing, refresh hooks, IPC target `overview` |
| `modules/overview/Backdrop.qml` | The blurred, bar-tinted wallpaper backdrop (see Behaviour · Backdrop) |
| `modules/overview/WindowCard.qml` | One window in the screen layer, at its real place and size: `ScreencopyView` of the toplevel drawn through a layer, decoration sized in screen pixels (divided by the layer scale) and faded in by the open progress, title caption, hover outline, scaled drag preview, recapture when its size changes |
| `modules/overview/WorkspaceCard.qml` | One top card: number badge, window count, miniature layout, selected/current/drop states |
| `modules/overview/AddWorkspaceCard.qml` | The "+" card at the end of the strip; adds a slot, and is a drop target that creates a workspace |
| `modules/overview/OverviewModel.js` | Pure geometry and window-list helpers (`mix`, `surfaceRect` for the open animation) |
| `services/OverviewState.qml` | Singletons: `open`, `screen`, `selected`, `extra`; `openOn` resets to the focused workspace, `toggle` closes from any open state, `addWorkspace` picks the next free id |
| `modules/bar/OverviewWidget.qml` | The grid glyph (`\uf009`, Font Awesome th-large); accent while open |

`Overview.qml` is instantiated once in `shell.qml`. Each `PanelWindow` is a `WlrLayer.Overlay` with
`ExclusionMode.Ignore` and `WlrKeyboardFocus.Exclusive` on every screen (while one exclusive layer exists Hyprland
only sends pointer events to exclusive layers, so a non-exclusive second screen would see nothing). The window is inset
by `Theme.barInset` on the bar edge, which is what keeps the bar visible; the other edges are flush. Only the target
screen sets `sheet.visible`, and the Repeaters use `win.target ? ... : []` so the other screens start no captures.
While shown, the cards (and so the captures) exist; closed, the windows are unmapped and hold no captures.

**Bar icon closes it (2026-10-21).** The bar is visible next to the overview, but with an exclusive layer mapped Hyprland
delivers pointer events to exclusive layers only, so the bar widget never saw a click (measured by hovering over it:
0 enter events while open, 1 closed). A second transparent `PanelWindow` per screen (`bbkos-overview-bar`, exclusive,
exactly the bar strip: `Theme.barInset` thick on `Theme.barPosition`) now sits over the bar and closes the overview on a
click, and on Esc. So a click anywhere on the bar closes it, the grid icon included; other bar items do not run their own
action while the overview is open (same as a click outside a panel). Checked: the strip's geometry for top, bottom, left
and right with `hyprctl layers`, and a hover on it reaching the catcher; the real click was not injected (no `uinput`).

## Previews

`WindowCard.captureSource` is `entry.toplevel.wayland`, the `xdg-foreign` handle that Hyprland's
`hyprland-toplevel-export-v1` accepts. `ScreencopyView` is created with `live: false`, so each open is a one-shot
still; it is scaled into the stage. It sits in a `Loader` drawn through a layer (blending, see the translucent-window
note). A card takes a new still only when its size really changed (debounced, only once the overview has settled), instead
of stretching the old texture; a data refresh that changes nothing never touches the capture.
The compositor's border and shadow are **not** part of the capture, so the card draws a 1 px frame and a 24 px caption
itself. The caption is a sibling declared after the capture with `z: 1000`, `clip: true` and a 92 % theme-background
strip. (A `MultiEffect` mask directly around the `ScreencopyView` once hid the caption and broke the preview; the
capture itself is only layered, never masked, and the overview cards are not rounded.)

The stage aspect comes from the selected workspace's monitor (`width / height / scale`), and the card is letterboxed
inside the available area; window rectangles are fractions of that frame and are clamped, so a window partly
off-screen is shown cut at the stage edge rather than outside it. Windows with no geometry or `mapped: false` /
`hidden: true` are skipped. `OverviewModel.monitorFrame` divides Hyprland's physical monitor width/height by the
monitor scale because client `at`/`size` are logical.

## Moving windows (Hyprland 0.56 Lua dispatch)

This is the part that does not work the obvious way. **Hyprland 0.56 runs Lua configs and no longer accepts the
legacy dispatchers over IPC**: `Hyprland.dispatch("workspace 3")` and `hyprctl dispatch workspace 3` both fail
(`')' expected near '3'`) and the legacy `movetoworkspacesilent` is not available either. The replacement is the Lua
API, and Quickshell's `Hyprland.dispatch()` passes the string through as Lua:

```qml
Hyprland.dispatch("hl.dsp.focus({ workspace = 3 })")
Hyprland.dispatch("hl.dsp.focus({ window = \"address:0x...\" })")
Hyprland.dispatch("hl.dsp.window.move({ workspace = 4, window = \"address:0x...\" })")
```

All three were verified live (`hyprctl` for the API strings, then the real QML through IPC). The API reference is
installed at `/usr/share/hypr/stubs/hl.meta.lua`; the generated keybinds use the same form
(`hl.bind("SUPER + 1", hl.dsp.focus({ workspace = 1 }))`).

`hl.dsp.window.move()` brings the moved window's workspace to the front when that window had focus (unlike the old
silent dispatcher). `moveWindow` therefore records `Hyprland.focusedWorkspace` before the move and re-dispatches focus
to it afterwards when it differs, so a drop never yanks the user away from where they were. Verified: window moved
1 → 4 → 5, active workspace stayed put each time.

## IPC (test hooks and scripting)

`qs ipc call overview ...`:

| Call | Effect |
|---|---|
| `status` | JSON: `open`, target `screen`, `selected`, visible `workspaces`, focused workspace, window addresses on the selected workspace |
| `open` / `close` / `toggle` | Same as the bar icon; `open` resets the selection to the focused workspace and clears added slots |
| `select N` | Preview workspace N, without switching |
| `switchTo N` | Switch the real workspace to N and close |
| `move ADDRESS N` | Move a window (with or without `0x`) to workspace N, the same path as a drop |
| `add` | Add the next free workspace slot and select it (the same as clicking "+"); returns the id |

`address` is normalised (lower-case, `0x` added, 16 hex digits max) before it reaches the dispatcher. Workspace ids
are positive integers; named and special (negative) workspaces are not shown.

## Resources and limits

Measured on the owner's 1920x1200 single-monitor session (PSS from `/proc/<pid>/smaps_rollup`, Quickshell 0.3.2):

| State | PSS |
|---|---|
| Closed | 188.1 MB |
| Open, workspace 1 (two terminals) | 196.7 MB |

So the overview costs roughly 9 MB while open, and the captures are released when it closes. There is no timer,
no polling and no live capture. The strip builds cards only for the workspaces that exist (plus "+"), so its cost
follows the session instead of always reserving ten slots.

Limits: one screen in V1 (windows are laid out against the selected workspace's monitor; a workspace spanning
multiple monitors is clamped to the first). `ScreencopyView` is a still, so a playing video or a progress bar in the
overview does not move while it is open; the still is refreshed after Hyprland events, not continuously. Added slots
that stay empty disappear when the overview closes, and Hyprland may remove an empty workspace once it is no longer
focused. Workspace ids above 10 are shown and can be moved to, but only 1-10 have `Super+N` binds. Special workspaces,
named workspaces and workspace rules are not shown as cards. The overview is not reachable with the keyboard alone
(open it from the bar); pointer drag was not observed on real hardware (see below).

## Verification (2026-10-20)

- Visual, via `grim`: the bar stays visible with the overlay starting at its edge for top, bottom, left and right
  positions; the strip shows only the existing workspaces plus "+"; window previews, counts, empty and "no windows"
  states render. Screenshots in `/tmp/opencode/overview-*.png` (not committed).
- Add: `qs ipc call overview add` returned 3 with workspaces 1 and 2 present, added the card, selected it and showed
  the empty stage; the "+" card rendered at the end of the strip.
- Live move: two temporary kitty windows (`bbkos-overview-test`, created and closed for the test) on workspace 8;
  moving one to 9 updated the open overview without closing it: card 8's miniature and count went from two windows to
  one full-width window, card 9 appeared, and the stage grew the remaining window to full width (the still was
  recaptured, not stretched). `status` showed `windows` on 8 with only the remaining address.
- IPC: `status` (with the visible `workspaces`), `open`, `close`, `toggle`, `select`, `switchTo`, `move`, `add`;
  `open` resets the selection; invalid addresses are rejected; any positive workspace id is accepted.
- Move/focus: the Lua path still moves a window and restores the previous focus; the earlier 1 → 4 → 5 → 1 test and
  window focus were rechecked during the first build. The owner's windows were not touched.
- `bbkos-qml-audit`: 0 missing imports. `python3 -m unittest discover -s tests/theme`: 322 tests pass.
- Memory (PSS): 188.1 MB closed, 196.7 MB open on workspace 1 with two terminals (about 9 MB).

## Verification, second pass (2026-10-20, the five requested changes)

- **Backdrop (blurred wallpaper, bar-seamless)**: `grim` capture (`/tmp/opencode/overview-backdrop.png`) with the
  owner's settings (`barOpacity 0.2`, `barBlur`, 3 × 2 blur): the backdrop reads as one continuous blurred wall with
  the bar strip at its edge; no window visible behind the overview.
- **Open animation**: mid-flight `grim` captures at ~0.25 s show the card between its real place and the stage,
  clipped at the stage border (`clip: root.introOpen`); the settled frame matches the old layout (`/tmp/opencode/
  overview-intro-*.png`, `t1..t3.png`). Early frames stay clipped too (checked at ~0.06 s and ~0.28 s after open).
- **Toggle fix (item 4)**: `overview open` (no screen), then `overview toggleOn eDP-1` — the exact values the bar icon
  passes — closes (`open: false`); previously that re-opened.
- **Follow (item 5)**: opened, then `hyprctl dispatch 'hl.dsp.focus({ workspace = 1 })'` → 0.8 s later `status` shows
  `selected: 1` matching `focused: 1`; three switches (1→3→1 and inside the 760 ms intro window) all followed; the
  stage slide ran for each. Verified that reading the follow out of the raw `workspace` event is broken (stale state)
  before moving it to `onFocusedWorkspaceChanged`.
- **Gestures (item 1)**: `bbkos-theme set touchpad.swipe3Up overview` + `swipe3Down overview-close` (then `apply`);
  `~/.local/state/bbkos/theme/hypr-theme.lua` emits `hl.gesture({ fingers = 3, direction = "up|down", action =
  function() hl.dsp.exec_cmd("qs ipc call overview toggle|close") end })`; `hyprctl configerrors` empty; 323 theme
  tests pass (the render test asserts the exact Lua). `tests`, `python3 -m unittest discover tests` (91) and
  `bbkos-check` pass overall.
- The IPC-exec path of the gesture Lua was exercised end-to-end via
  `hyprctl dispatch 'hl.dsp.exec_cmd("qs ipc call overview toggle")'` → the overview opened.

**Not verified:** the real touchpad swipe itself (Hyprland runs the Lua action only on a physical gesture and this
environment cannot inject one — the owner must swipe up/down once to confirm item 1 end-to-end); the visual
continuity of the MultiEffect blur against the compositor's bar blur on other wallpapers (checked on the current
one only); real pointer clicks and drags (so the shrunk drag preview, drop hit-testing and click-to-focus were
exercised through the same functions via IPC only), dropping on "+", double-click to switch, a second monitor, a
light theme. The closing side has no animation by design (see Behaviour · Open animation).

## Stage mode switch

The right end of the overview header has a "Stage mode for workspace N" switch (2026-10-21; it replaced the
"Workspace N · count" text). Since 2026-10-23 it switches only the workspace shown below (`OverviewState.selected`)
until the next boot, through `StageState`; the default for every workspace is on bbkOS › Stage mode. See
`stage.md`.

## Nice to have (not done)

- **Live, scaled-down real screen with finger-following gestures.** Not possible from Quickshell: Wayland does not let a
  client transform other clients' windows, and Hyprland sends a custom gesture's action only when it ends. It would
  need a compositor plugin; hymission (Hyprland plugin: live previews, workspace strip, gestures with continuous
  progress, drag between workspaces) is the candidate, possibly as our own fork (backdrop blur is off by default there).
  Trade-offs: tied to the exact Hyprland build, rebuilt per update, runs inside the compositor. See the 2026-10-21 notes.
- **Seamless left/right workspace swipe inside Quickshell**: capture every workspace's windows and slide a wide strip.
  Costs GPU/memory (a screenshot per window on every workspace) and sync code.
- **Upstream**: `ScreencopyView` paints without blending (a translucent window's alpha lands in the overlay surface);
  worth confirming it is not intended, then reporting or fixing in Quickshell.

## Stale monitor frame (2026-10-25)

The window fractions are computed from the monitor's x/y/size, and Quickshell's copy of x/y can stay stale after a hotplug or layout change (seen: `1600,0` against Hyprland's `0,-1080`), which puts every window off-screen and leaves the workspace empty. `refreshNow` now calls `Hyprland.refreshMonitors()` first. This was the cause of the empty workspace 2 noted on 2026-10-24.

A monitor move sends no socket event, so `hyprland.lua` hooks `monitor.layout_changed` (and added/removed) to `qs ipc call display monitorsChanged`, which refreshes monitors, workspaces and toplevels (`Panels.qml`); an open overview follows on its next refresh. The per-screen windows read `modelData` null-safely: while an unplugged monitor's delegate is torn down Quickshell hands it a null screen ("attempted to use dangling screen object"), and each binding logged a TypeError (2026-10-28).
