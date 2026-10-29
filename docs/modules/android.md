# Android apps (disable and remove phone apps)

Added 2026-10-28. The command `bbkos-android` (`bbkos_theme/android.py`) and the window **Android apps**
(`modules/android/`, opened from the bbkOS menu or `qs ipc call android toggle`) disable, remove and restore apps on an Android
phone over adb, for user 0, guided by UAD-ng's safety rating for each package. No root. Spec:
`docs/specs/2026-10-28-android-debloat-design.md`; plan: `docs/plans/2026-10-28-android-debloat.md`.

## Reference

Follows **UAD-ng** (Universal Android Debloater, next generation, GPL-3,
github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation), read 2026-10-28. Borrowed:
- **the package list** `uad_lists.json` (5382 packages on 2026-10-28): package -> `list` (Oem, Carrier, Google, Aosp, Misc),
  `description`, `neededBy`, `removal` (Recommended, Advanced, Expert, Unsafe). Downloaded from the URL UAD-ng itself uses
  (`raw.githubusercontent.com/Universal-Debloater-Alliance/universal-android-debloater/main/resources/assets/uad_lists.json`)
  and cached; it is data, read and never run.
- **the commands** (`crates/uad-core/src/sync.rs`, Android 6+): remove `pm uninstall --user 0 P`, restore
  `cmd package install-existing --user 0 P`, disable `pm disable-user --user 0 P`, enable `pm enable --user 0 P`.
- **the package-name check** before a name reaches a device shell (`request_builder`).

App names come from `scrcpy --list-apps` (scrcpy 5.0.1): its on-device server asks Android for each launchable app's label.
Lines are ` * NAME  PACKAGE` (system) or ` - NAME  PACKAGE`; on the owner's phone it names 118 of 465 packages (only apps with
a launcher icon), so most system packages show the package as the title. Icons are letter tiles: real icons would need each
APK pulled and read with `aapt2`, left for later.

## Command

`bbkos-android status | list [--serial S] | update-list | disable|enable|remove|restore PKG... [--serial S] [--force] |
pair HOST:PORT CODE | connect HOST:PORT | disconnect [HOST:PORT]`. Output is one JSON object. Exit 0 when the command ran
(per-package failures are in `results`), 1 with `{"error": ...}` for no usable phone or `{"ok": false, "message": ...}` for a
bad address or code, 2 for wrong arguments.

- `status`: `adb devices -l` plus `getprop` per authorised phone (brand, model, Android version, SDK, USB or Wi-Fi).
- `list`: `pm list packages --user 0` with `-u` (every package, removed ones too), none (present), `-d` (disabled) and
  `-u -s` (system); state is `removed` (in `-u` only), `disabled` or `installed`; joined with the UAD entry (`Unlisted` when
  missing or an unknown rating). `listAge` is the cache's age in seconds.
- `--serial` is required when more than one phone is ready. **The owner's phone shows twice over Wi-Fi debugging** (as
  `IP:port` and as its mDNS name `adb-...._adb-tls-connect._tcp`), so the window shows a picker.

### Safety (in the code, not only in the window)

1. Package names must match `[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+` and be on the phone (`pm list packages -u`); the
   package is its own argv element, never part of a shell string.
2. `disable` and `remove` refuse Unsafe packages, and refuse everything when there is no safety list, unless `--force`. The
   window never passes `--force`; Unsafe rows are locked on its Installed tab. Actions never download the list.
3. `remove` refuses a package with **no factory copy** on the phone unless `--force`: `dumpsys package P` must show a
   `codePath` outside `/data` (the installed one, or the hidden factory copy of a Play-updated system app such as Gmail in
   `/product/app/Gmail2`). Only such a copy survives `pm uninstall --user 0`. The SYSTEM flag is not enough: on the owner's
   vivo, `/system/custom` preloads are installed into `/data` with that flag. Found live on 2026-10-28: removing
   `com.vivo.feedback` deleted it and `install-existing` answered "doesn't exist"; it was put back with
   `pm install --user 0 /system/custom/app/Feedback/Feedback.apk` (the same path may help for other vivo `custom` apps).
   Apps the owner installed are refused the same way. Disable stays available for all of them and is fully reversible.
4. Every action is appended to `~/.local/state/bbkos/android/history.jsonl` (`time, serial, model, package, action, ok,
   error`), so what was removed is known even after the phone changes.
5. Success is read from `pm`'s answer, per action: `Success` (uninstall), `Package P new state: disabled-user` / `enabled`,
   `Package P installed for user: 0` (install-existing). Anything else is shown as the error.
6. Every subprocess call has a timeout (5 s; 60 s for `pm list` and scrcpy; 30 s pair and connect; 20 s the download); a
   timeout is the error `timed out`. A test fails if a call without one is added.

Files: cache `~/.cache/bbkos/android/uad_lists.json` (written to a temp file and renamed, only when it parses as the
expected map: a captive-portal page never replaces it); history as above.

## Window

`AndroidWindow.qml` (Scope + `LazyLoader` + `FloatingWindow`, title `bbkOS Android`; rule `bbkos-android` in `hyprland.lua`:
floating 960x680 centred), `AppRow.qml`, `ConfirmSheet.qml`, `WifiForm.qml`, `Field.qml`. Device line (picker when several),
search, rating filters (Recommended and Advanced on at first), Show user apps, tabs Installed / Disabled and Removed, the list
(tick, letter tile, name, package, rating, description that expands on click, Needed by), action bar Disable / Remove (with
a confirm sheet; Expert packages marked) or Restore (enable for disabled rows, install-existing for removed rows). With no
phone ready it shows the steps and checks every 2 s while open. The first `list` downloads the 1.6 MB list (15.6 s on the
owner's network on 2026-10-28; cached runs take 1.4 s): the window says so after 3 s. Refresh downloads it again when the
cache is older than 7 days.

Test hooks: `qs ipc call android status | select PKG | tab installed|off | useSerial S | confirm disable|remove | wifi | close`.

## Verified

2026-10-28 on the owner's vivo V2503 (Android 16, SDK 36) over Wi-Fi debugging: `status` (0.3 s) and `list` (465 packages:
439 installed, 26 disabled; 127 Recommended, 70 Advanced, 83 Expert, 49 Unsafe, 136 Unlisted; 118 named); `list` without
`--serial` refused (two serials); `connect` to an already connected address. Window screenshots: picker, list, the Disabled
and Removed tab with a tick, the confirm sheet, the Wi-Fi form; the menu finds "Android apps" first for "android".
56 tests in `tests/android` (fake `adb` and `scrcpy`, fixtures recorded from that phone).

Live actions on `com.vivo.feedback` (the owner's pick), each checked with `pm list packages`: disable from the command line,
enable through the window's Restore, remove through the window (which exposed the factory-copy problem above; the app was
reinstalled), then remove refused by the new rule with the package untouched. The window's final-review fixes were checked
with the hooks: switching phones while a list loads ends with the list of the phone shown; a ticked row hidden by a filter is
not counted.

Remove -> restore of `com.vivo.compass` (factory copy `/system/app/Compass`, the owner's second pick): removed (gone from
`pm list packages`, `list` shows it `removed`), then restored (present again, same path).

Not verified: a real `adb pair`; USB; clicks with the mouse (the hooks were used).
