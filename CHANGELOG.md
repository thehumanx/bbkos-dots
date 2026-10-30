# Changelog

What changed for people using bbkOS dots, newest first. Update with `git pull && ./install.sh --no-packages` (see "Update" in the README).

## 2026-10-31

### New

- **Pinned apps in the rail.** The stage rail can hold your apps as tiles: click one to bring its window forward or start it, click `+` to pin an app from the menu, hover a tile and click `×` to unpin. A dot under a tile shows the app is running. Pinned apps are always on in grid mode, and a switch of their own (Settings > bbkOS > Rail and pinned apps) otherwise. While pinned apps are on, the rail shows on every workspace, not only stage ones.
- **Put the rail anywhere.** Any screen edge (left, right, top, bottom). On the top or bottom the tiles and window cards are one row and the rail is as thick as that row. The rail can run the full edge or **hug** its contents, and **Alignment** places the tiles and cards (or a hugging rail) at the start, centre or end. When the rail and the bar share an edge, the rail sits between the bar and your windows.
- **The rail follows the bar's look.** Outside grid mode it takes the bar's background and blur, rounded corners, floating gap and pill style (individual pills, one grouped pill, or none).
- **Window title widget.** A bar widget with the focused window's icon and title, in a fixed-width cell after the workspaces (horizontal bars).
- **Switch any bar widget off.** Settings > Bar > Layout has a switch at the start of each widget's row. A hidden widget leaves no gap and keeps its place for when you switch it back on. From a terminal: `bbkos-theme set bar.hidden tray,updates` (an empty value shows them all).
- **A bbkOS page in Settings.** The first page in the sidebar gathers what is particular to this desktop: Grid mode, Rail and pinned apps, Stage mode. These settings moved there from Appearance > Style and Windows > Stage mode.

### Changed

- **Grid mode looks finished.** One-pixel lines everywhere, all on whole screen pixels (also at fractional scales such as 1.0667): no doubled joints between bar cells, a single line along all four screen edges, and the bar's line no longer flickers while you hover the pinned tiles. Windows keep your own margin and corner radius, so each window is a rounded card inside the grid, and the gap between two tiled windows equals the margin around them. In grid mode the bar's thickness is rounded up to the next whole-pixel size (for example 26 to 30 at a 1.0667 scale); your saved value comes back when grid mode is off.
- **Settings changes no longer flash your windows.** Changing a bar, rail, popup or other shell setting used to reload Hyprland, which re-applied every window. Now Hyprland reloads only when a setting it uses changes (window gaps, borders, rounding, animations, keybindings, colours). `bbkos-theme apply` still reloads everything.
- **Settings window.** "Background opacity" of the rail shows "Set by the bar style" (the rail now takes the bar's background). The rail's Width is now **Thickness**, and Card height is **Card length** (along the rail).

### Fixed

- The rail no longer takes the full height and pushes the bar aside after the bar was hidden and shown again.
- Pinned app tiles no longer show "?" after a shell restart.
- A pinned tile's border stays visible while you hover it.
- Bar groups outside grid mode no longer end with an extra gap (the end group sat 12 px too far in with the default widget gap).

### Notes

- Tested on one laptop (Intel, 1920x1200 at 1.0667). A second monitor with another scale, light mode and AMD or NVIDIA machines were not tested with these changes.
