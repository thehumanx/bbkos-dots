# Module: Quickshell (research notes and API facts)

Task 8. Quickshell 0.3.2 on Qt 6, Hyprland 0.56.2 (Lua config). Code lives in `dotfiles/quickshell/.config/quickshell/`. This file records what was learned, so changes (and a future agent) do not have to rediscover it.

## Community configs studied (read-only, ideas only)

Cloned into an isolated scratch directory, never executed. Both are **GPL-3.0**, so no code is copied (copying would make our code a GPL-3 derivative). Only structural and behavioural ideas were taken.

| Config | Size | Ideas taken | Things deliberately avoided |
|---|---|---|---|
| `caelestia-dots/shell` (commit 71c2833) | 284 QML files, 40k lines, plus a C++ plugin | `services/` singletons (Audio, Brightness, Hypr, Notifs, Players, ...) separate from `modules/` (bar, launcher, osd, notifications, lock); each module split into a lazy `Wrapper` and a `Content`; `settings.watchFiles` for live reload while developing | 49 `Timer` instances (polling), 144 `Loader`s, large feature surface |
| `end-4/dots-hyprland` (commit 2f2a376) | 586 QML files, 56k lines | Panel "families", clean `modules/common` vs per-feature split | 60 `Timer` instances, 221 `Loader`s, AI/weather/etc. features |

Our target is about 20 files and roughly 1,500 lines.

## Quickshell 0.3.2 API facts (verified by running a windowless probe against the real system, 2026-10-18)

Available modules (`/usr/lib/qt6/qml/Quickshell/`): `Services.{Polkit,Notifications,UPower,Pipewire,SystemTray,Mpris,Greetd,Pam}`, `Bluetooth`, `Networking`, `Hyprland`, `Io`, `Widgets`, `Wayland`, `WindowManager`, `I3`, `DBusMenu`, `X11`.

- **Services start lazily on first reference.** Reading `Hyprland.workspaces` or `UPower.displayDevice` at the same instant a service is first touched returns empty values; the data arrives a moment later via bindings. Widgets must bind, never read once. (Good for resources: unused services cost nothing.)
- **UPower**: `UPower.onBattery` (bool), `UPower.displayDevice.percentage` is a **0-1 fraction** (multiply by 100), `.state` (0 unknown, 2 discharging, others per `UPowerDeviceState`), `.isLaptopBattery`, `.iconName`. `PowerProfiles.profile` (0 power-saver, 1 balanced, 2 performance) and `.hasPerformanceProfile` wrap `power-profiles-daemon` natively, so the bar can switch profiles with no extra tool.
- **Pipewire**: `Pipewire.defaultAudioSink.audio.volume` is a 0-1 float, `.muted` a bool. A `PwObjectTracker { objects: [Pipewire.defaultAudioSink] }` is required to make the node's audio properties valid.
- **Networking** (native NetworkManager backend): `Networking.wifiEnabled`, `Networking.devices` (`NetworkDevice`: `name`, `type`, `connected`, `networks`), `Networking.connectivity`. No `nmcli` needed. `connectivity` is NetworkManager's global check and lags the link: it still read Limited with Wi-Fi switched off and while a network was joining (2026-10-25), so `Net.limited` / `Net.portal` trust it only after a link has been up for 6 s. A network being joined has `state === ConnectionState.Connecting` (`Net.connecting`).
- **SystemClock** has `date` (a JS Date), `hours`, `minutes`, `seconds`, and **no `now`**: `clock.now` is undefined and arithmetic on it gives NaN silently, with no log line (the battery popup's "NaN h NaN min", fixed 2026-10-25). Use `clock.date.getTime()`.
- **Bluetooth**: `Bluetooth.defaultAdapter` (`enabled`, `devices`), `Bluetooth.devices` (`connected`, `battery`, ...).
- **Polkit**: `PolkitAgent { path, isRegistered, isActive, flow: AuthFlow }`; `AuthFlow` exposes `message`, `inputPrompt`, `isResponseRequired`, `supplementaryMessage`, `isCompleted`, `isSuccessful`, `isCancelled`, `identities`, `selectedIdentity`.
- **Notifications**: `NotificationServer` (`trackedNotifications`, supports body, markup, actions, images); `Notification` (`appName`, `summary`, `body`, `urgency`, `actions`, `image`, `tracked`, `expireTimeout`). A NotificationServer *is* the daemon: only one can own `org.freedesktop.Notifications` at a time. `trackedNotifications` is live-only; `services/Notifs.qml` copies the fields into its own persisted history (see `notifications.md`).
- `upower` (package) is already installed and D-Bus-activated; nothing to install for the battery widget.

## How to probe a module safely

A windowless `shell.qml` that touches the services in `Component.onCompleted`, logs values from a `Timer` a few seconds later, then calls `Qt.quit()`. Run with `quickshell -p <path>/shell.qml`. It changes nothing on the system.

---

# Built shell (Task 8, applied 2026-10-18)

Config: `dotfiles/quickshell/.config/quickshell/` (stowed with folding to `~/.config/quickshell`). Run by `quickshell.service` (user unit, `dotfiles/systemd-user/`): `Restart=on-failure`, `RestartSec=1`, `WantedBy=graphical-session.target`, `Environment=QSG_DISTANCEFIELD_ANTIALIASING=gray` (grayscale text), `Environment=QS_ICON_THEME=Adwaita`. **GPU renderer** since 2026-10-18 (see below); the earlier `QT_QUICK_BACKEND=software` line is gone.

## Layout

| Path | Role |
|---|---|
| `shell.qml` | Entry point: instantiates Wallpaper, Bar, Notifications, Osd, Launcher, Polkit, Clipboard, Panels, CaptivePortal, BatteryAlerts, Overview, ThemeIpc, SettingsWindow |
| `Theme.qml` | Singleton: colours, font, sizes, `radius`/`controlRadius`, `hair`; bound to `services/ThemeStore.qml`, which watches the generated `colors.json` (see `docs/modules/theme.md`) and falls back to the built-in look |
| `services/ThemeStore.qml` | Singleton: generated theme and `settings.json` via `FileView` + `watchChanges` |
| `modules/theme/ThemeIpc.qml` | IPC target `theme` (`status`, `reload`) |
| `services/SettingsStore.qml` | Singleton: settings app state and the `bbkos-theme` run queue (see `docs/modules/settings-app.md`) |
| `modules/settings/` | Settings window (`SettingsWindow`, `Sidebar`, `SettingsPage`, `PageShell`, `PageWindows`, `PageTerminal`, `PageWallpaper`, `PageReset`), IPC target `settings`; `Super+,` and the bar gear |
| `modules/wallpaper/Wallpaper.qml` | One `WlrLayer.Background` window per screen (`Variants`), `Theme.bg` plus the wallpaper image (crossfade, decoded at physical screen size); IPC target `wallpaper` (`status`). See `docs/modules/theme.md` |
| `services/{Power,Audio,Net,Bt,Notifs}.qml` | Singletons wrapping UPower/PowerProfiles, PipeWire, Networking, Bluetooth, NotificationServer, plus the notification history (saved in `$XDG_STATE_HOME/quickshell`). Pure bindings, no timers. |
| `services/Updates.qml` | Singleton: pending repo updates from `checkupdates`, one 30-minute timer (the one deliberate polling timer; 5 minutes after a failed check). Only started while the bar's Updates widget is in the layout. IPC: `qs ipc call updates status` / `refresh` |
| `components/{Txt,Picker}.qml` | Shared text style; the search-and-pick overlay of the clipboard picker (optional preview beside the list) |
| `components/{Button,Toggle,StepBar}.qml` | Primitives (the model owns the state); `Slider.qml` was removed 2026-10-29 |
| `components/{PopupHeader,PopupSection}.qml` | The title line and the parts of a bar popup, in the settings look (`design.md` section 5) |
| `components/FileUrl.js` | Pragma-library `toUrl(path)`: safe `file://` URL (each segment percent-encoded); used by `Wallpaper.qml` and `PageWallpaper.qml` |
| `components/Setting{Slider,Toggle,Choice}.qml` | One setting per row, bound to `SettingsStore` |
| `modules/bar/` | One file per widget: `OverviewWidget`, `Workspaces`, `Clock`, `Tray`, `DisplayWidget`, `AudioWidget`, `BluetoothWidget`, `NetworkWidget`, `BatteryWidget`, `NotificationsWidget` (bell), `SettingsWidget` (gear); `Bar.qml` places them (one bar per screen via `Variants`) |
| `modules/notifications/` | Popup stack + `NotificationCard`, and `NotificationHistoryPanel` / `NotificationHistoryCard` (the sheet; see `notifications.md`) |
| `modules/osd/Osd.qml` | Volume/brightness indicator |
| `modules/launcher/{Launcher,MenuWindow}.qml`, `Rank.js`, `Commands.js` | The bbkOS menu: apps, web apps, commands, settings pages, calculator, web search (`menu.md`; it replaced the app launcher on 2026-10-23) |
| `modules/polkit/Polkit.qml` | Polkit authentication agent dialog |
| `modules/clipboard/Clipboard.qml` | Clipboard history picker |
| `modules/overview/` | Workspace overview: `Overview` (overlay), `Backdrop` (blurred, bar-tinted wallpaper), `WorkspaceCard`, `AddWorkspaceCard`, `WindowCard` and `OverviewModel.js`; `services/OverviewState.qml` holds open/screen/selected/extra. IPC target `overview` and the bar's grid icon; see `docs/modules/overview.md` |

Every popup module uses `LazyLoader`: its window exists only while visible.

## Interfaces

| IPC target (`qs ipc call ...`) | Used by |
|---|---|
| `launcher toggle` / `close` | `Super+R` (`hyprland.lua`, `menu`) |
| `clipboard toggle` | `Super+Shift+V` |
| `osd brightnessOn <percent> <screen>` / `osd brightness <percent>` | `~/.local/bin/bbkos-brightness` (brightness keys; the backlight emits no change events; the bar appears on the named screen, the focused one for the old form) |
| `display status` / `refresh` / `refreshBrightness NAME` / `setBrightness NAME N` / `setScale` / `setMode` / `setLayout` / `keep` / `revert`; `panel toggleOn PANEL SCREEN` | Display widget (`docs/modules/displays.md`); `bbkos-brightness` calls `refreshBrightness` |
| `notifications status` / `markAllRead` / `clear` / `dismiss KEY` | Test hooks and the notification panel (`docs/modules/notifications.md`) |
| `wallpaper status` | Test hook: per screen, decode size, scale, `image`/`plain`, `Image.status` |
| `theme status` / `reload` | Tests and manual use: tokens as the shell resolves them; re-read the theme files (normally not needed, the files are watched) |
| `overview status` / `open` / `close` / `toggle` / `select N` / `switchTo N` / `move ADDRESS N` / `add` | Test hooks and scripting; the bar's grid icon uses `OverviewState`. See `docs/modules/overview.md` |
| `settings toggle` / `status` / `set KEY VALUE` / `reset SECTION` / `revert` / `wallpaper PATH` / `clearWallpaper` / `snapshotInfo` / `snapDirFor` / `page PLACE` / `shown KEY` (what a control for KEY shows, as JSON; test hook 2026-10-29) | `Super+,`, the bar gear (through `SettingsStore`), tests; see `docs/modules/settings-app.md` |

Volume OSD is reactive (PipeWire changes). Notifications are received on `org.freedesktop.Notifications` (Quickshell owns the name; only one daemon can).

## Behaviour notes

- **Bar widgets**: workspaces (click to activate), clock (minute precision; click opens the calendar popup, calendar.md), tray (left activate, middle secondary, right menu), audio (click mute, scroll 5%), Bluetooth (hidden without adapter), Wi-Fi name / wired / off, battery (hidden without battery; warn 20 %, critical 10 % on battery; accent while charging). Do-not-disturb deliberately omitted (owner choice).
- **Notifications** advertise body (plain text) and persistence; actions, images and markup are off. The server owns `org.freedesktop.Notifications`; live cards expire after the sender's timeout (6 s default) or stay when critical, while a capped history (100, persisted) is shown by the bell/right-hand sheet. Clicking a live card marks its history entry read; read state is manual (see `notifications.md`).
- **Launcher** (until 2026-10-23; now the bbkOS menu, `menu.md`, with Raycast-style ranking in `Rank.js`) ranked per query token: name prefix 4, name substring 3, fuzzy match on the name 2, keywords/generic name/comment 1.
- **Clipboard**: `cliphist.service` records text and (since 2026-10-28) images, 100 entries by default (`clipboard.maxItems`, the Clipboard history card of Privacy and wellbeing: `bbkos-theme` renders `clipboard.conf` and `bbkos-clip-store` reads it on each copy), wipes on service stop (logout). `bbkos-clip-store` skips anything carrying `x-kde-passwordManagerHint` (cliphist 0.7.0 does not check it itself). Verified: a `wl-copy --sensitive` copy is not stored, a normal copy is.
- **Clipboard images (2026-10-28)**: the service runs two watchers (`wl-paste --type text` and `--type image`, as cliphist's README does) in one unit, so a stop still wipes both; `bbkos-clip-store text|image` keeps one entry per copy (image mode skips a copy that also offers `text/plain`, copies over 10 MB and everything while `clipboard.images` is off; text mode skips an image copy that offers HTML but no plain text, a browser's "Copy image"). The picker (`modules/clipboard/Clipboard.qml`) shows an image as a 96x60 thumbnail with "Image · W × H" and type and size: the 20 newest images are decoded into `$XDG_RUNTIME_DIR/bbkos-clip` (RAM, emptied on each open, gone at logout) while it is open; picking one copies it back with `wl-copy --type image/<ext>`. The picker now draws every label as plain text: copied HTML (Figma) had rendered as rich text, with tall blank rows. Test hook `qs ipc call clipboard list`. Reference: cliphist's README (the two watchers); DankMaterialShell runs its own Go clipboard daemon, not borrowed.
- **Clipboard preview (2026-10-29)**: the picker is two columns, 880 px wide and of fixed height: the list (360 px, the whole history, scrolls; until 2026-10-29 it was cut to 8 rows) on the left, the current entry on the right. Images past the 20 newest show an empty thumbnail until selected. A text entry is decoded again (`cliphist decode`; the list line is cut at about 100 characters) and shown in full as plain text, wrapped and scrollable, with "N characters · N lines"; over 20 KB only the first 20 KB, with "First 20 KB of N KB shown". An image is shown whole, fitted, with type, size and file size; one older than the 20 decoded at open is decoded when selected. One decode runs at a time and the newest selection wins. The row you chose stays chosen when the list is rebuilt (thumbnails written, an image decoded); before, a rebuilt list jumped back to the top (`Picker.chosen`, found by `test_selection_survives_decode`). The decoded files go to `$BBKOS_CLIP_DIR` when set, else `$XDG_RUNTIME_DIR/bbkos-clip`: the test shell shares the live runtime directory and would otherwise empty the live picker's folder. Test hooks `clipboard preview`, `select N`, `search TEXT`. Reference: Noctalia's Clipper plugin and nwg-clipman show the entry beside the list.
- **Polkit**: Quickshell's `PolkitAgent`. `hyprpolkitagent` (115 MB PSS) was removed.
- **Workspace overview** (`modules/overview/`): a layer-shell overlay inset by the bar (so the bar stays visible) opened from the bar's grid icon or a 3-finger swipe up; its backdrop is the blurred, bar-tinted wallpaper (`Backdrop.qml`; the compositor's blur can't be used because the real windows sit behind the overlay), the focused workspace's windows shrink from their screen rectangles into the stage on open, and a 3-finger left/right swipe behind the backdrop is followed (`onFocusedWorkspaceChanged` — not from the raw event, where `focusedWorkspace` is still stale) with a stage slide. It lists the workspaces Hyprland currently has plus a "+" card, and screenshots each window of the selected workspace through `hyprland-toplevel-export-v1` (`ScreencopyView`, still images), so hidden workspaces are visible. `Hyprland.refreshWorkspaces()` / `refreshToplevels()` are called on open, on relevant events while open, and after a drop, because Quickshell's `lastIpcObject` does not update when a window is retiled. Hyprland 0.56 uses Lua configs, so actions are dispatched as Lua (`hl.dsp.focus(...)`, `hl.dsp.window.move(...)`); the legacy `workspace N` / `movetoworkspacesilent` forms silently do nothing. See `docs/modules/overview.md`.
- **Live reload skips JavaScript libraries (2026-10-23).** After a change to a `.pragma library` file (`modules/launcher/Rank.js`) the shell reloaded its QML but kept running the old JS; `systemctl --user restart quickshell` picked it up. Restart after editing a `.js` file.
- **Picker** (clipboard history; the emoji picker and the bbkOS menu have their own windows with the same look) is a full-screen transparent layer-shell window: a click outside the panel dismisses it, `Esc` also does. `HyprlandFocusGrab` was tried first (smaller window) but did **not** dismiss on an outside click, so it was dropped; the reason was not investigated. **Polkit** is a small centered window with no outside-click dismissal on purpose.

## Resource measurements (2026-10-18, software renderer, `measurement.md` method)

| State | PSS |
|---|---|
| Bar only, GPU renderer | 125 MB (RSS 245) |
| Bar only, **software renderer** | 74 MB (RSS 91) |
| All modules, fresh start | 102 MB |
| After first launcher open (loads `libQt6Svg` + icon cache for app icons) | about 130 MB |

Idle CPU about 3 ticks in 30 s (about 0.1 % of a core). Wakeups were about 6-9 per second **while the session was actively used** (the terminal's title changes generate Hyprland events); a true-idle figure is to be taken during the battery tests (Task 11). A full-screen overlay window costs roughly 10-14 MB more while open than a small one (measurements were noisy); it is created only while a picker is open.

Re-measured 2026-10-18 with today's full config, fresh start each, same method: software **110 MB** PSS, GPU renderer **153 MB** (+43 MB). A zoomed capture of the OSD bar shows the software renderer gives staircase rounded ends (an `antialiasing: true` flag changes nothing) and the GPU renderer gives smooth ones; the owner noticed the jagged look. Power cost of the GPU renderer is not measured.

**Decision (owner, 2026-10-18): GPU renderer, no compromise on visual quality.** Measured after the switch with the full config: PSS **164 MB**, idle CPU 0.0 % (software was 110 MB fresh). Idle power on battery is not measured yet: measure with `bbkos-power-sample` before a long café day. It also enables shader effects (blur, masks) for phase 3. To go back, add `Environment=QT_QUICK_BACKEND=software` to the unit.

## Pixel-perfect rules (panel is 1920x1200 at 1.5x)

Seen at 8-12x zoom: with the GPU renderer, shapes are smooth only if they land on whole physical pixels.
- Use **even logical sizes, margins and offsets** (even x 1.5 is a whole pixel; 3 px = 4.5 physical blurs the edge). Examples fixed: toggle 40x24 with a 16 px knob and 4 px margin; slider 16 px handle in a 20 px row; OSD bar 8 px tall.
- Radii: cards, popups and dialogs use `Theme.radius`; rows, buttons and inputs `Theme.controlRadius` (the two 8 px cards `Theme.controlRadius + 2`); pills (toggle, slider, OSD bar) keep half their own height. All theme sizes are even (the settings step by 2).
- Use **`Theme.hair`** (one physical pixel in logical units, 1/devicePixelRatio) for hairlines, separators and borders. A 1 logical px line is 1.5 physical px and renders soft.
- Text: Qt Quick defaults to RGB-stripe (LCD) smoothing, which shows coloured fringes on the Samsung OLED panel (EDID `ATNA40CT01`). `QSG_DISTANCEFIELD_ANTIALIASING=gray` in the unit fixes it. (`Text.QtRendering` and a fontconfig `rgba=none` file were tried and changed nothing; the fontconfig file was removed again.)
- Check new shapes with `grim -g "x,y WxH"` (logical coordinates) and `ffmpeg -vf scale=iw*8:ih*8:flags=neighbor` to see individual pixels.
- Limit: `Theme.hair` reads the first screen's scale; a monitor with a different scale gets 1 px lines that are slightly off, not broken.

## Verified by test (2026-10-18)

- Bar renders all live data (screenshot read back); notifications popups (normal and critical); launcher; OSD; `pkexec` shows the polkit dialog and it closes when the request ends.
- Notification history (2026-10-20): normal/critical/low stored, transient skipped, persisted across a shell restart, "mark all read" persisted, dismiss/clear via IPC, sheet rendered at all four bar positions and all three pill modes. See `notifications.md` for the details and the untested pointer clicks.
- Brightness helper: 20 % to 27 % to 20 %, OSD shown.
- Hotplug: a virtual monitor got its own bar and lost it on removal; Quickshell PID unchanged, 0 restarts.
- Supervision: `SIGKILL` to the shell restarted it in under 3 s.
- Tray verified end to end (2026-10-18) with a fake StatusNotifierItem registered from a Python script (`dbus-python` + `python-gobject`): the item appeared in the bar. First run showed the magenta missing-icon checkerboard because Qt only searched `hicolor`; `QS_ICON_THEME=Adwaita` in `quickshell.service` (Adwaita inherits AdwaitaLegacy and hicolor) fixed it. No installed app registers a tray icon today (**Vivaldi has none on Linux**); apps such as Discord, Steam or nm-applet will.
- Owner-run checks: `ky` in the launcher found nothing because `ky` is not a substring of `kitty` (fuzzy matching added); click-outside dismissal did not work with `HyprlandFocusGrab` (replaced with a full-screen backdrop, retest pending).

## Apps must not run inside `quickshell.service` (found 2026-10-18)

`Quickshell.execDetached` and `DesktopEntry.execute()` start processes as children of Quickshell, i.e. inside `quickshell.service`'s cgroup. The old service run showed a 3.8 GB memory peak for a shell of about 100 MB: it was carrying the apps launched from it. A Quickshell restart or crash would then kill every one of them (browser, Figma with unsaved work, Spotify).

Fix (`modules/launcher/Launcher.qml`): launch through `uwsm app -- <id>.desktop`, so each app gets its own `app-*.scope` under `app.slice`; terminal apps run as `uwsm app -- kitty -e <command>`. Verified: a launched kitty sat in `app-Hyprland-kitty-….scope` (not `quickshell.service`) and **survived `systemctl --user restart quickshell.service`**. Desktop entries load lazily, so the module touches `DesktopEntries.applications` at startup (without it the first `launch <id>` after a restart found nothing). Scripting/test hook: `qs ipc call launcher launch <id>`.

Note: `uwsm app` stays in the foreground until the app exits; never pipe it in a test without a timeout.

## Flatpak apps in the launcher

Quickshell finds app entries only through `XDG_DATA_DIRS`, and the user manager's copy was set before Flatpak was installed, so the launcher did not see Flatpak apps at all. `quickshell.service` now sets:

```
Environment=XDG_DATA_DIRS=%h/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/usr/local/share:/usr/share
```

Verified: the running shell's environment carries it (`tr '\0' '\n' < /proc/<quickshell pid>/environ | grep XDG_DATA_DIRS`). Stremio is the only installed Flatpak app and it has not exported a `.desktop` file yet (both `exports/share/applications` directories are empty), so no new launcher entry has appeared; a Flatpak app with an exported entry should now show up without a shell restart.

## Logout

`Super+M` runs `uwsm stop` (graceful: clients stop before the compositor). The previous default (`hyprctl dispatch exit`, since `hyprshutdown` is not installed) killed Hyprland while Quickshell, hypridle, Xwayland and the portals were running, so all of them aborted (4 coredumps on 2026-10-18 09:46). To be confirmed at the next logout: no new coredumps (`coredumpctl list`).

## Extending

Add a service singleton in `services/`, a module directory in `modules/`, instantiate it in `shell.qml`. Touch services early and bind (they start lazily). No polling timers; one-shot timers are fine. Check the log with `journalctl --user -u quickshell.service` or `qs log`.

## Undo

`systemctl --user disable --now quickshell.service cliphist.service`; `stow -D -d ~/.local/share/bbkos/repo/dotfiles -t ~ quickshell systemd-user`; reinstall `hyprpolkitagent` only if no Quickshell agent is wanted.
