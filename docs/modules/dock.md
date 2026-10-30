# Module: pinned apps (dock) and the window title

Pinned apps are a grid of app tiles at the start of the stage rail, always shown, that start an app or bring its window to the front; a bar widget shows the focused window's title. Both were added 2026-10-30 for grid mode: they are cells like everything else there. The dock is on whenever `shell.gridMode` is on (`GRID_OVERRIDES`, `stage.dock`, shown "Set by grid mode") and is a separate toggle (`stage.dock`, "Pinned apps" on bbkOS › Rail and pinned apps, default off) without it. Since 2026-10-31 the rail goes on any edge, full length or hugging its contents at start, centre or end, and outside grid mode it looks like the bar ("Placement and style" below). The pins are `stage.dockApps`, a list of desktop-file ids, empty by default. Source: `modules/stage/{DockGrid,DockTile}.qml`, `services/Dock.qml`, `modules/bar/WindowTitle.qml`, pin mode in `modules/launcher/`. Design source: Zen Browser and Arc's pinned tiles, and Pond OS's pinned grid.

## Behaviour

- **Tiles.** Two columns down a side rail (one row along a top or bottom one), the pinned apps in the order they were pinned, then a "+" tile. There is always one "+" tile, so an empty dock shows one rectangle to add an app with. Tile sizes come from the rail width (`stage.railWidth`); in grid mode the padding around the grid and the gap between tiles are the window margin (`stage.railPadding`, `stage.cardGap`, both set by grid mode) and the tiles have the windows' corner radius.
- **Click.** The app has a window open: it is brought to the front (`Stage.qml` `dockActivate` → `focusWindow`, which switches workspace and keeps the pointer where it is). It has none: it is started with `uwsm app -- ID.desktop`, as the menu does, so a shell restart does not kill it.
- **Running dot.** A small accent dot under the icon while the app has a window. Windows are matched to apps by `DesktopEntries.heuristicLookup(class).id` (`services/Dock.qml`).
- **Separator.** A one-pixel `cardEdge` line, edge to edge across the rail, between the tiles and the open-window cards; shown only while there are cards (2026-10-30).
- **No double listing.** A pinned app's window is not also a card in the rail below the tiles (`Stage.qml` `others`).
- **Unpin.** A small × in the tile's corner on hover. On hover the tile also gets an accent highlight and an accent border; the border is its own rectangle above the highlight (as the tile's own border the highlight, its child, covered it and at its brightness the border looked gone, 2026-10-30).
- **"+".** Opens the menu (`Super+R` window) in pin mode: "Pick an app to pin", the all-apps grid opens at once, Enter pins instead of starting, Delete does not uninstall, commands and settings are not listed. Esc closes it.
- **Visibility.** With the dock on, the rail shows on every workspace and monitor (it reserves its space everywhere); the cards below still show only on stage workspaces with windows to list. With the dock on the cards start under the tiles instead of being centred.
- **Looks.** Grid mode: transparent cells with the `cardEdge` hairline over the rail's bar-style background (`grid-mode.md`). Otherwise the bar's pill style ("Placement and style"). In grid mode the tiles are rounded cells with the windows' corner radius (`windows.rounding`, through `stage.cardRadius`, which the open-window cards use too), 8 px from the rail's edges and from each other with the owner's 8 px margin (2026-10-30; before that they touched).

## Placement and style (2026-10-31)

Reference: end-4's dots-hyprland dock (`modules/ii/dock/Dock.qml`, read, not run): the layer window spans its whole edge and stays transparent, the visible dock hugs its content inside it, and the input mask is the visible part, so the reserved space never changes when an app is pinned. bbkOS's bar already does the same, and the rail now follows it.

- **Edge** (`stage.railPosition`: left, right, top, bottom). On top or bottom the tiles sit in one row along the edge (owner, 2026-10-31), then the separator (a vertical line across the rail), then the cards in a row; the rail is then one tile plus the padding thick (54 px with the owner's 100 and 8 px), so the reserved space and the windows follow. A tile is the same size on every edge, set by `stage.railWidth` (a side rail's thickness); `stage.cardHeight` is a card's length along the rail. Cards on a top or bottom rail are one tile tall, and a card under 60 px tall shows the picture without its title strip. With the bar on the same edge the rail sits between it and the windows. A live change of edge maps the rail again (a 120 ms blink): without it the layer kept its old place (left to right, right to bottom; found in the test shell).
- **Alignment** (`stage.railAlign`, default start; owner, 2026-10-31). On a full-length rail the tiles and cards move together to the start, centre or end of the rail (they used to start at the top with the dock on and be centred without it); on a hugging rail it places the rail itself.
- **Hug** (`stage.railHug`). Off: the body runs the full edge. On: it is as long as its contents and sits at start, centre or end; the window and its reserved thickness stay the same, and a body longer than the edge is full length and scrolls. In grid mode a hugging body is one cell and draws its two ends too (the screen edges stay `modules/frame`'s). The bar's corner cell lines up with the rail only for a full-length left rail (`Dock.alignBar`).
- **Style outside grid mode** (both modes share the background): `Theme.barBg` with the bar's own blur (`BarBlur`), `shell.barRadius` (capped at half the thickness), `shell.barFloat` off the screen edges and between bar and rail, and the tiles by `shell.barPills`: individual, each tile a pill (`pillBg`, `pillRadius`); grouped, one pill around the tile grid; off, plain icons. No hairline on the body (the bar's body has none); the hover accent border stays. `stage.railOpacity` is not read any more ("Set by the bar style").
- **Code.** `modules/stage/RailGeometry.js` (pure, node tests in `tests/stage`): `body`, `windowOrigin`, `windowMargins`; in grid mode every length is snapped to whole physical pixels. `Stage.qml` places the body item, masks input to it and lays the content out with a `Grid` (one column or one row; the other count is 0, computed: a Grid given 1000 rows reserved the spacing of each, 8122 px for five tiles, found in this pass).

Checked 2026-10-31, `eDP-1` at 1.0667: every rail edge with the bar on every edge (16), grid mode on and off (32 cases, a script reading `hyprctl layers` and a `grim` scan: no overlapping windows, the rail on its edge or stacked against the bar, in grid mode the four screen edges intact and every line 1 px); hugging at start, centre and end on a bottom rail and centred on a left rail (body rectangles from `qs ipc call stage status`); screenshots of the stacked layouts, the three pill styles and a floating rounded bar (6 px gap measured between bar and rail bodies); a screen recording of tile hover on a top rail under the bar (0 of 431 frames with the bar's line missing). Tests: `tests/stage` (7), `tests/shell/test_dock.py` (edges, hug, alignment, restack, style, the side-rail hug regression). Not verified: a second monitor, a real click, light mode, `reserveSpace` off on screen (the margins are unit-tested).

## The rail is mapped again when the bar comes back

Hyprland lays layer windows out in the order they were mapped, and the first one takes the screen edge. With the dock the rail stays mapped on every workspace, so after the bar was hidden (`Super+Shift+Space`) and shown again the rail was before it: it took the full height, pushed the bar aside (bar at x=100 instead of 0 in the log) and covered the bar's edge line (the owner's "the border sometimes does not show", 2026-10-30). `Stage.qml` now unmaps the rail 250 ms after `BarState.hidden` turns false and maps it again 120 ms later, so it is after the bar; the rail disappears for about a tenth of a second. Before the dock the rail was unmapped on most workspaces, which hid this.

## The rail meets the bar on a whole pixel (grid mode)

At a fractional scale a bar of 26 logical px is 27.73 physical px, so the last row of the bar and the first row of the rail were the same row. While the rail repainted, which it does for every frame of a tile's hover animation, the compositor redrew that shared row from the rail alone and the bar's bottom line (over the rail's width only) went black until the animation stopped: "the border disappears and reappears when I hover the pinned icon" (2026-10-30). It is invisible to `grim` (the compositor's own copy of the frame): it was found with screen recordings (`gpu-screen-recorder`, which reads what the display shows) and a per-frame scan of that row. The first fix was a 1 logical px gap between the two; since the evening of 2026-10-30 grid mode instead rounds the bar's thickness up to a whole number of physical pixels (`Theme.barHeight`, 26 → 30 at 16/15, `grid-mode.md`), so there is no shared row and the rail starts flush against the bar. The gap (`Stage.qml` `gridPad`) is kept only for a screen where no whole thickness is found (`Theme.exactOn`).

Measured (screen recordings at 60 fps, the pointer moved over the four tiles every 0.1 s with `hl.dsp.cursor.move`): with the whole-pixel bar and no gap the line was missing in 0 of 428 frames; the control, a 26 px bar with no gap, lost it in 16 of 480. Earlier, with the gap: 0 of 295 (and 295 of 295 without it).

## Window title (`bar.layout` entry `start:title`)

The focused window's icon and title in a fixed 260 px cell (a changing title never moves its neighbours), elided. By default it follows the workspaces in the start section; move it with the bar layout editor ("Window title"). Horizontal bars only (a vertical bar has no room for a title: the cell is hidden). Event-driven: it reads Hyprland's active toplevel; nothing polls. Until the first focus change after the shell starts Quickshell's `Hyprland.activeToplevel` is null and every window's `activated` is false, so the window with `focusHistoryID` 0 stands in (found while building it: the cell was empty after a restart).

## The corner cell lines up with the rail

In grid mode with the dock on, the rail at the left and a horizontal bar, the first two bar cells (overview, workspaces) add up to the rail's width (`Dock.alignBar`; `BarItem.minAlong` on the workspaces cell, `Bar.qml`), so the line between the workspaces and the title cell continues down the rail's inner edge, as in the wireframe. A cell that fits the target within one pixel takes exactly the target; more workspaces than fit keep their own size and the joint moves right. The rule assumes the default order (overview first, then workspaces). Measured with `grim` and a pixel scan at the top and bottom bar: bar joint at x=106, rail edge line at x=106 (it was 107 before, one physical pixel off).

## Settings (`stage.*`)

| Key | Values | Default |
|---|---|---|
| `dock` | on/off | off (on in grid mode) |
| `dockApps` | comma-separated desktop-file ids, 1-64 characters each, no repeats, at most 200 | empty |

There is no settings page for the pin list: pinning and unpinning happen on the rail, and `bbkos-theme set stage.dockApps kitty,thunar` sets the list. A pinned id whose app is uninstalled shows a "?" tile that can still be unpinned.

## Test hooks

`qs ipc call stage dock` (state: on, pins, running ids), `stage dockclick ID` (what a click on that tile does), `stage undock ID` (the ×; `stage dock` also lists `resolved`, the pins whose tile found its desktop entry), `launcher pin` (what "+" does: the menu in pin mode), then `launcher run app:ID ""` (Enter on that app).

## Verified (2026-10-30, `eDP-1`, grid mode on, `grim` and IPC)

- "+" opened the menu in pin mode; picking kitty, Thunar and Figma added three tiles and the "+" tile moved on; the list is in `settings.json`.
- Running dots: under kitty and Figma, none under Thunar while it was not running (checked against `hyprctl clients`), and one appeared once it was started.
- `dockclick figma-linux-next` switched to Figma's workspace and focused it; `dockclick kitty` went back; `dockclick thunar` with Thunar closed started it.
- A pinned app's window was not a card (0 cards); unpinned, it showed as a card under the tiles (1 card); pinned again, 0.
- The title cell showed "Figma" and the browser's title, with its icon, and still showed them after a Quickshell restart (with the fallback above).
- Bar at top, bottom, left and right: the dock sat beside the bar with no overlap (screenshots at bottom and left, layer geometry at right); the title cell is absent on the vertical bars.
- Tests: `tests/theme` (582): defaults, the grid override, the pin list's cleaning, the title widget in the default layout and added to an older saved layout.

Found after the first commit, from a restart: Quickshell loads desktop entries lazily, so the tiles' lookup at start found nothing for good (every tile a "?", no running dots) until the shell restarted again. `Dock.entryFor` and `Dock.idFor` now read `DesktopEntries.applications.values`, which re-runs the bindings when the list arrives. `tests/shell/test_dock.py` starts a fresh test shell and checks the pins resolve; it fails without the fix (`[]` instead of `['kitty']`, checked by removing the fix) and passes with it.

Not verified: a real mouse click (no pointer-injection tool is installed here; the click path was driven through the hooks above, which call the same function the tiles call), hover × by hand, a second monitor, light mode, a pin whose app is uninstalled, 1080p at scale 1, a stage-off workspace with the dock (the dock showed on workspaces 1-3 in stage mode only), dragging to reorder (not built).

## Not built

Frame mode (rounded window card on a chrome-coloured backdrop), drag to reorder, a settings page for the pins, a window-title cell that stretches to fill the bar, Pond OS's clock and media tiles.
