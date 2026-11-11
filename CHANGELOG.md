# Changelog

What changed for people using bbkOS dots, newest first. Update with `git pull && ./install.sh --no-packages` (see "Update" in the README).

## 2026-11-11

### New

- **Your own logo: an animated screensaver, an About window, and fastfetch.** One ASCII logo (the default is BBKOS in block letters) shows in three places. After 2.5 minutes idle it plays as a full-screen animation on every monitor, before the lock at 5 minutes; any key or touch ends it. `bbkos-about-window` opens a floating window with fastfetch and a glint that sweeps over the logo. Plain `fastfetch` in a terminal shows the same logo with the bbkOS layout. Change the logo with `bbkos-branding` (`words about "your text"`, `set-text about FILE`, `reset about`; the files are `~/.config/bbkos/branding/about.txt` and `screensaver.txt`; run `bbkos-branding reset about` once to create them). Settings > Power and sleep > When idle > Screensaver has the switch, the effect (decrypt, beams, matrix, slide, rain, burn, waves), the start time, and buttons to preview the screensaver and open the About window. The animation needs `tte`, from the AUR package `python-terminaltexteffects` (read its PKGBUILD before installing: `yay -S python-terminaltexteffects`). Without it nothing breaks: that idle step dims the screen as before, and `bbkos-check` says `tte` is missing. Inspired by Omarchy's branding.
- **Switch to an open app from the menu.** Settings > Launcher > "Switch to an open app": Enter on an app that is already open goes to its window; Shift+Enter always starts a new one.

### Changed

- **The idle step at 2.5 minutes is the screensaver while it is on** (it replaces the dimming; the keyboard light still goes off with it). Settings > Power and sleep > When idle shows "Screensaver" instead of "Dim the screen" while it is on. Turn the screensaver off to get the dimming back.

## 2026-11-01

### Fixed

- **Brightness keys on an external monitor no longer lag.** Holding the brightness key with the pointer on a DDC/CI monitor used to queue every key repeat, and the monitor kept changing for seconds after you let go. The keys now work like the slider in the Display popup: one press takes about 0.2 s, and the monitor stops within about 0.3 s of letting go. The laptop screen is unchanged.
- **Grid mode's screen border shows on all four edges of a monitor at scale 1.** On a screen with no scaling only the top edge (the bar's line) had a border; the left, right and bottom were missing.

## 2026-10-31

### New

- **Stage switch on the rail.** The far end of the rail (the bottom of a side rail, the right end of a top or bottom one) holds a two-icon switch: tiled or stage, the current one lit. Click the other to switch the workspace you are on. `Super+Alt+S` and "Stage mode for this workspace" in the menu still work.
- **App icons on the window cards.** Each card in the rail shows its app's icon in the middle, so you can tell windows apart on a top or bottom rail too, where the cards have no title strip.
- **Pinned apps in the rail.** The stage rail can hold your apps as tiles: click one to bring its window forward or start it, click `+` to pin an app from the menu, hover a tile and click `×` to unpin. A dot under a tile shows the app is running. Pinned apps are always on in grid mode, and a switch of their own (Settings > bbkOS > Rail and pinned apps) otherwise. While pinned apps are on, the rail shows on every workspace, not only stage ones.
- **Put the rail anywhere.** Any screen edge (left, right, top, bottom). On the top or bottom the tiles and window cards are one row and the rail is as thick as that row. The rail can run the full edge or **hug** its contents, and **Alignment** places the tiles and cards (or a hugging rail) at the start, centre or end. When the rail and the bar share an edge, the rail sits between the bar and your windows.
- **The rail follows the bar's look.** Outside grid mode it takes the bar's background and blur, rounded corners, floating gap and pill style (individual pills, one grouped pill, or none).
- **Window title widget.** A bar widget with the focused window's icon and title, in a fixed-width cell after the workspaces (horizontal bars).
- **Switch any bar widget off.** Settings > Bar > Layout has a switch at the start of each widget's row. A hidden widget leaves no gap and keeps its place for when you switch it back on. From a terminal: `bbkos-theme set bar.hidden tray,updates` (an empty value shows them all).
- **A bbkOS page in Settings.** The first page in the sidebar gathers what is particular to this desktop: Grid mode, Rail and pinned apps, Stage mode. These settings moved there from Appearance > Style and Windows > Stage mode.

### Changed

- **Popups and notifications line up with your windows.** Bar popups, the notification panel and notification popups keep the same margin from the screen edge as your windows (Settings > Windows, "Gaps outside"), instead of the shell's Gap setting (0 in grid mode, so they touched the edge). The Gap setting now only spaces the bar's widget groups.
- **Grid mode looks finished.** One-pixel lines everywhere, all on whole screen pixels (also at fractional scales such as 1.0667): no doubled joints between bar cells, a single line along all four screen edges, and the bar's line no longer flickers while you hover the pinned tiles. Windows keep your own margin and corner radius, so each window is a rounded card inside the grid, and the gap between two tiled windows equals the margin around them. In grid mode the bar's thickness is rounded up to the next whole-pixel size (for example 26 to 30 at a 1.0667 scale); your saved value comes back when grid mode is off.
- **Settings changes no longer flash your windows.** Changing a bar, rail, popup or other shell setting used to reload Hyprland, which re-applied every window. Now Hyprland reloads only when a setting it uses changes (window gaps, borders, rounding, animations, keybindings, colours). `bbkos-theme apply` still reloads everything.
- **Settings window.** "Background opacity" of the rail shows "Set by the bar style" (the rail now takes the bar's background). The rail's Width is now **Thickness**, and Card height is **Card length** (along the rail).

### Fixed

- The window title in the bar no longer shows a window from another workspace when you switch to an empty one.
- The rail no longer takes the full height and pushes the bar aside after the bar was hidden and shown again.
- Pinned app tiles no longer show "?" after a shell restart.
- A pinned tile's border stays visible while you hover it.
- Bar groups outside grid mode no longer end with an extra gap (the end group sat 12 px too far in with the default widget gap).

### Removed

- **The workspace overview** (the grid icon at the start of the bar, the three-finger swipe up). It overlapped with the workspaces widget and the stage rail. A saved bar layout or swipe that still names it is cleaned up quietly; the swipes become "none". If you used the swipe for something, pick a new action in Settings > Mouse and touchpad > Gestures.

### Notes

- Tested on one laptop (Intel, 1920x1200 at 1.0667). A second monitor with another scale, light mode and AMD or NVIDIA machines were not tested with these changes.
