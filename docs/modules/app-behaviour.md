# App behaviour (window rules for specific apps)

Window rules in `dotfiles/hypr/.config/hypr/hyprland.lua`, one per behaviour, each with the evidence behind it. Rules apply
when a window opens: a window already open keeps its old state until it is closed and reopened.

## Dialog sweep (2026-10-28)

Owner asked that every dialog float. Method: open each kind on purpose and read class, title and `floating` from `hyprctl clients -j` (a dialog is invisible to the list until it exists). Opened over D-Bus or from the command line: portal OpenFile, SaveFile, SaveFiles (floating through `bbkos-file-chooser`); zenity info, question, entry, file (already floating, transient); Thunar properties, rename, create, preferences over `org.xfce.FileManager`; zenity colour chooser; xfce4-about. **Found tiled:** Thunar's properties, rename and create (the earlier `bbkos-thunar-dialogs` rule matched class `Thunar` only, but through the D-Bus daemon the class is `thunar`, and the titles are `a.txt - Properties`, `Rename "a.txt"`, `Create New File`, not the bare words I had guessed), the zenity colour chooser (class `zenity`, title `zenity`) and xfce4-about. Fixed: class `[Tt]hunar` with the real title patterns, and a new rule `bbkos-misc-dialogs` for `zenity` and `xfce4-about`. After `hyprctl reload` (`configerrors` empty) all of them opened floating; the Thunar file manager (`tt - Thunar`) stays tiled. Seahorse ("Passwords and Keys") is an application, not a dialog, and stays tiled.

**Not opened, so not verified:** the AppChooser and Print portals (no working trigger found), pinentry-qt and gcr-prompter (no window appeared from a hand-fed request), Thunar's progress, confirm and Open With dialogs (matched by title guesses only), dialogs of Electron apps and browsers beyond the portal chooser. When the owner meets a tiled one, read its class and title from `hyprctl clients -j` and add it here.

## File chooser (2026-10-28)

Owner report: the "Select folder" dialog opened as a tile filling the workspace. Reproduced without the owner by calling the portal over D-Bus (`gdbus call ... org.freedesktop.portal.FileChooser.OpenFile "" "Select folder" "{'directory': <true>}"`): `hyprctl clients -j` showed class and initialClass `xdg-desktop-portal-gtk`, title `Select folder`, tiled, 1458x972. Rule `bbkos-file-chooser`: match on the class, floating, 1000x640, centred (open, save and folder choosers of every app share the class). Verified after `hyprctl reload` (`configerrors` empty): the same call gave floating 1000x640 at 370,193 and a `grim` screenshot shows a centred dialog over the terminal. Not verified: a real Browse click in the Android window, Save dialogs (same class, not opened).

**How to find these dialogs:** they exist only while open, so listing `hyprctl clients` never shows them. Trigger them (portal call, or the app's button) and read the class from the live client list.

## Screen-share picker (2026-10-26)

Owner report: the portal's "Select what to share" window opened as a tile that filled the workspace. Evidence from `hyprctl clients -j`: class `hyprland-share-picker`, title `Select what to share`, tiled, size of the whole workspace (it also covers the browser in stage mode). Rule `bbkos-share-picker`: match on the class, floating, 720x480, centred. Verified by starting the picker by hand (`XDPH_WINDOW_SHARING_LIST="" hyprland-share-picker`) and a `grim` screenshot: a dialog in the middle of the screen over the terminal. Not verified: a real share started from Meet. Vivaldi (Chromium) asks the portal twice per share (observed 2026-10-26, cause not proven), so two of these dialogs appear one after the other; a picker that never closes (seen once, pid left over from the second ask) blocks later shares until it is killed.

## Picture-in-picture (2026-10-21)

Owner report: Zen's YouTube Picture-in-Picture opened as another tile (it was a small floating window in Omarchy). Evidence from
`hyprctl clients -j`: class `zen`, title `Picture-in-Picture`, tiled 948x570. Omarchy's rule (`default/hypr/apps/pip.lua`, read
from `basecamp/omarchy`) was adopted as `bbkos-pip`: match on title `(Picture.?in.?[Pp]icture)`, floating, pinned (on every
workspace), 600x338, keep aspect ratio, no border, top right.

One change from Omarchy's rule: its `move` uses `window_w`, but here that was still the tiled width when the rule ran (x came out
932 instead of 1280), so the x position is `monitor_w-640` (600 width + 40 margin). If the size in the rule changes, change 640.

Verified 2026-10-21: a kitty window titled `Picture-in-Picture` opened floating, pinned, 600x338 at 1280,48 on the 1920x1200 screen;
`hyprctl configerrors` empty. Not verified: Zen's own PiP window after the change (the existing one cannot be re-ruled; close it
and open PiP again), and Meet's own PiP (Omarchy has a separate rule for its `Meet - ...` title; not added).

## Thunar dialogs (2026-10-28)

Owner report: the rename dialog opened as a tile filling the workspace. Thunar's dialogs have class `Thunar`, the same as the file manager, and are not floated by Hyprland on their own. Rule `bbkos-thunar-dialogs` matches the dialog titles (the file manager's `<folder> - Thunar` is not matched): floating and centred, size left to the dialog. A new Thunar dialog with a title not in the list will tile again; add its title to the rule. Not verified: delete-confirm, copy-conflict and progress dialogs.

## Android apps window (2026-10-28)

Rule `bbkos-android`: class `org.quickshell` + title `bbkOS Android` (the window of `docs/modules/android.md`), floating, 960x680, centred, next to `bbkos-settings`. Verified: `hyprctl reload` and `configerrors` clean, `hyprctl clients -j` shows the window floating at 960x680.
