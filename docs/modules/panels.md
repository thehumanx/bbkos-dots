# Wi-Fi, Bluetooth, audio and power panels

(The display panel, brightness and monitor layout, is documented in `displays.md`; it uses the same `PanelState` and `Panels.qml` host. The notification history is a full-height sheet in the same host; see `notifications.md`.)

Click the Wi-Fi or Bluetooth icon in the bar (audio: the volume widget): a popup opens at it (centred on the widget, `bar.md`; the calendar and timer popups are in `calendar.md`) (separate popup per icon). Click outside or press Esc to close. Source: `dotfiles/quickshell/.config/quickshell/modules/{panels,network}`, services `Net`, `Bt`, `PanelState`.

## Placement against the windows (2026-10-31)

Owner: "the popup should have the padding such that it aligns with the window padding". Every popup in `Panels.qml`, the
notification sheet and the notification cards keep `Theme.windowMargin` (the windows' `windows.gapsOut`, Hyprland's
`gaps_out`) from the screen edges, so their outer edge lines up with the windows' border; before, they kept `shell.gap`,
which grid mode sets to 0, so they touched the screen edge. The side that faces the bar is unchanged (the bar's inset plus
6 px for popups, 8 px for notifications). A popup centred on its widget is clamped to that margin at both ends. Measured
with `grim` at scale 16/15, gaps 8: with a top or bottom bar the battery popup's background ends at physical column 1909
and its edge line is at 1910, the same column as the tiled window's border; the notification card, top bar, the same.
Seen in screenshots: a notification at the bottom right (bottom bar) and at the top left (left bar). Not handled: a stage
rail on the popup's side (the windows then start after the rail; the popups do not), light mode.

## Design

- **Look (2026-10-29, spec `docs/specs/2026-10-29-popup-redesign-design.md`).** The popups share the settings window's language: a `PopupHeader` (section-title style, a toggle or status at the right), `PopupSection` parts separated by the settings hairline (10 % `fg`), `SettingRow` without `key` for a label with a toggle, button or value, chip rows labelled above them in the row-label style, `StepBar` for volume, microphone and brightness ("22 %", − and + step by 5), list rows 36 high with 12 px padding, card content margin 20. The Display popup writes its mode with units (`components/DisplayText.js`: `1920 × 1200 · 60 Hz · 1.07×`). The audio section's speaker / mic glyph at the right of its title is the mute button.
- **Open and close animation, shadow.** The card grows from the widget (96 % to 100 %, fade, 200 ms) and leaves in 140 ms; the overlay stays mapped for that long with no input, then goes. It has a hairline edge and the tinted `CardShadow`. Details and settings (`shell.reduceMotion`, `shell.popupShadow`): `motion.md`.
- **Native Quickshell, no extra daemon.** Wi-Fi goes through the NetworkManager bindings, Bluetooth through BlueZ. Nothing runs while the popup is closed.
- **Scanning only while a popup is open.** Wi-Fi scans and Bluetooth discovery cost battery. They are switched on when the panel is built and off in `Component.onDestruction`. `qs ipc call panel status` prints what is on.
- **Wi-Fi list.** Connected, then known, then by signal. It re-sorts only when networks appear or disappear, never on signal ticks, and never while a password prompt is open (a re-sort would destroy the row you are typing in).
- **Bluetooth pairing errors** follow the same rule: the row reports "Pairing failed" only 1.5 s after BlueZ stops pairing without a Paired state, and the message clears when any device pairs or connects.
- **Joining.** Known or open network: one click. New secured network: password row (8-64 characters, show/hide). NetworkManager passes through a need-auth state even for a saved network whose secrets exist (journal: "secrets are required", then "secrets exist. No new secrets needed", then activated), and Quickshell reports that as `NoSecrets`. The row therefore waits 1.5 s and again while still connecting, and reports "Wrong or missing password" only if the network is neither connected nor connecting; the message is also cleared when a connection succeeds. A real wrong password makes NetworkManager ask again, and the half-created profile is forgotten so a failed attempt leaves nothing saved.
- **Bluetooth.** Click pairs. A pairing agent (`bluetoothctl --agent NoInputNoOutput`, just works) runs only while the popup is open: Quickshell can start a pairing but cannot answer BlueZ's confirm/authorise questions, so without an agent every pairing hangs on "Connecting...". Any device that becomes paired while the popup is open is marked trusted (so earbuds reconnect by themselves) and connected. Devices that need a typed PIN (some keyboards) go through Advanced (`bluetui`). Devices that only advertise a MAC address are hidden unless paired.
- **Bluetooth on/off survives a reboot.** BlueZ powers the adapter on at every boot (`AutoEnable` defaults to true) and does not remember "off". `Bt.qml` keeps the choice in a flag file, `~/.local/state/bbkos/bluetooth-off` (exists = the user switched Bluetooth off), written by the popup's toggle and applied to each adapter object once, when it appears: at shell start, and again when `bluetoothd` restarts or the adapter resets (BlueZ then re-creates it powered on). A re-created adapter can still be powering on when the check ends, so the flag waits for that first power-on and undoes it; switching Bluetooth on later is left alone. Verified 2026-10-29 with `sudo systemctl restart bluetooth`: before the fix it came back on, after it stayed off; `bluetoothctl power on` afterwards stayed on. The adapter is still on from boot until login. To undo by hand: delete the file.
- **Captive portals.** When NetworkManager reports "Portal" the sign-in page opens once, in a private Zen window (`bbkos-captive-open`), with a notification. It re-arms when the network leaves the portal state. The Wi-Fi popup shows a "Sign in" banner to open it again. `Net.portal` and `Net.limited` (the "Connected, but no internet access" line) count only while a Wi-Fi or wired link is up and has been for 6 s: NetworkManager's connectivity is global and lags, so with Wi-Fi off or while joining it used to show a stale "no internet" line.
- **Fallback for what the popups do not cover** (hidden SSIDs, enterprise Wi-Fi, PIN pairing): the **Advanced...** button runs `bbkos-tui nmtui` / `bbkos-tui bluetui`, a floating kitty window that is focused instead of duplicated when it already exists.

## Speed test and Share (Wi-Fi popup, added 2026-10-23)

Below the network list while connected (Share only on Wi-Fi): `modules/panels/WifiTools.qml`, commands `bbkos-speedtest`
and `bbkos-wifi-qr`. Both run only on a click and only while the popup is open. Reference: Omarchy's
`omarchy-network-speedtest` and `omarchy-network-qr` (MIT, read 2026-10-23); the methods are theirs, the endpoints differ.

- **Speed test:** ping (median of five TCP connects to `speed.cloudflare.com`), then download, then upload, 8 s each:
  six parallel `curl` workers keep the link busy and the rate is read once a second from the interface's own byte
  counters (`/sys/class/net/IF/statistics`), so TLS and per-transfer overhead do not skew it. The figure is the median
  of the samples after the first two (TCP ramp-up); the running figure updates live in the accent colour. Endpoints:
  Cloudflare's public speed test (`/__down?bytes=`, `/__up`), no token (Omarchy scrapes fast.com's). **Data:** about
  the rate times 8 s per direction (100 Mbps: about 100 MB each way); the popup says it uses data. The last result is
  kept in `Net.lastSpeed` until the shell restarts. **Stop / close:** Quickshell kills the script with SIGKILL when the
  popup closes, so no trap runs; each worker watches the script and kills its `curl` within 0.3 s (before this, six
  downloads ran on for up to 10 s; checked: 6 `curl` during, 0 one second after closing).
- **Share:** `bbkos-wifi-qr` reads the joined network's name, key type and password from NetworkManager
  (`nmcli --show-secrets`, no prompt for the owner's own profiles), builds the standard `WIFI:T:WPA;S:...;P:...;;`
  payload (escaping `\ ; , : "`; WEP and open networks too; enterprise networks are refused) and pipes it to
  `qrencode --type ASCII`; each two characters become one module, printed as rows of 0 and 1. The popup draws them
  on a `Canvas`, dark modules on the lighter of the two text colours (never an inverted code). No image file, nothing
  on disk; the password is never a command-line argument (it would show in `/proc`). **Show password** runs
  `bbkos-wifi-qr --password` only when pressed; hiding the card drops it.
- **Package:** `qrencode` (extra, 110 KiB, depends on libpng which is already installed, no service). Without it Share
  says "qrencode is not installed: sudo pacman -S qrencode" (exit 3). Alternatives: vendoring a QR encoder in JavaScript
  (about 400 lines of someone else's code in the shell) or a Python library from the AUR; the small official package is
  less to maintain.
- **Test hooks:** `qs ipc call wifitools status | speedtest | share true` (only while the popup is open).
- **Verified:** live runs on this Wi-Fi (ping 90-96 ms, download 50 Mbps, upload 21 Mbps), the live figure and result
  row on screen (screenshot), the missing-qrencode message on screen, closing mid-test, `tests/theme/test_wifi_tools.py`
  (payload escaping, password never in argv, open and enterprise networks, worker cleanup); after the owner installed
  `qrencode`, the code on screen (33 x 33 modules, dark on light, "Scan to join <network>", screenshot). **Not verified:**
  a phone scanning it, Show password on screen, a wired-only connection, a metered connection.

## Audio popup

- **Bar widget:** icon and volume (a headphone icon when the output is Bluetooth). The connected Bluetooth device's name is shown on the Bluetooth widget instead, like the Wi-Fi widget shows its network ("name +N" for several devices). Left click opens the popup (like Wi-Fi and Bluetooth), middle click mutes, scroll changes volume in 5 % steps; the popup also has mute buttons.
- **Popup:** an Output and an Input section. Each has a mute button, a volume slider and the device list; clicking a device makes it the default (`preferredDefaultAudioSink` / `Source`), and running streams follow it. Device names are shortened ("Speaker", "HDMI 3", "Digital Microphone"); a Bluetooth device shows its own name. Cameras and application streams are not listed.
- **Bluetooth audio routing:** nothing needed to be built. PipeWire (`pipewire-audio`) creates a card and a sink when a device connects with an A2DP profile, makes it the default and moves running streams (seen with the BBK speaker). Earbuds reconnecting, and what happens to the default when a device goes out of range, are untested; the popup is the manual override.

## Power menu

The power key (short press) opens it; `qs ipc call panel toggle power` does the same. Lock (`bbkos-lock`), Suspend (`systemctl suspend-then-hibernate`, same as closing the lid) and Hibernate act at once. Log out (`uwsm stop`, the graceful path), Reboot and Power off need a second click within 4 seconds. A failed command raises a critical notification. logind still ignores the short press itself and powers off on a long press (5 s), so a stuck menu cannot trap you. The bind is not `locked = true`: the menu is not reachable from the lock screen.

## Battery popup

Left click on the battery widget (`qs ipc call panel toggle battery` does the same). Shows the charge with a bar, the state and UPower's time left (or until full; blank when plugged in and not charging, "Estimating..." until UPower has a figure), power draw, health (`energy-full` / design) and cycle count (read from sysfs when the popup opens), the power mode (Battery / Balanced / Performance = power-profiles-daemon's power-saver / balanced / performance; Performance is hidden when the machine has none), and two wall-clock rows: uptime and time since the last charge ("Plugged in for" on AC).

- **Uptime and charger time** (`services/ScreenTime.qml`): the popup rows are wall clock, not screen use. "Uptime" is `/proc/uptime`, re-read every 30 s. "Since last charge" (on battery) / "Plugged in for" (on AC) counts from `changedAt`, saved in `screentime.json` each time the charger state changes (shows "-" until the first change after the field was added; an unplug while the shell was down is stamped when the shell notices). The screen-on totals below are no longer in the popup; they stay on the Screen time settings page and in the break reminder.
- **Screen-on time** (`services/ScreenTime.qml`): sampled every 30 s while the screen is on, meaning no `hyprlock` and DPMS on (`pgrep` + `hyprctl monitors -j`). Gaps over 60 s (suspend) are not counted. The boot total resets with the boot id; the unplug total resets on each unplug and stops growing on AC (the Screen on card of Privacy and wellbeing shows both). An unplug is detected by comparing with the last charger state **saved in the file** (`onBattery`), once UPower is `ready`; so an unplug while the shell was not running counts too, and after a reboot a battery percentage more than 2 points above the saved one counts as charged while off. Totals are saved in `$XDG_STATE_HOME/quickshell/by-shell/*/screentime.json` so a shell restart keeps them. `BatteryAlerts` touches the service at login so counting does not wait for the first click.
- **Plug indicator speed** (`Power.pluggedIn`): the bar's charging icon and the popup's state follow the charger itself, not the battery's "Charging" state. The battery state arrives 2-3 s after the cable (the embedded controller is slow; UPower only relays it), so a `udevadm monitor` on the `power_supply` subsystem (idle until a change) triggers a re-read of every non-battery supply's `online` file. Measured 2026-10-19: the bar follows the kernel event in 0.25-0.3 s, against about 3 s before. The popup says "Plugged in" for those seconds, then "Charging".
- **Naming trap:** a QML property called `onBattery` is read as a signal handler and its binding never runs, so the service calls it `discharging`.
- **Test hook:** `qs ipc call battery status` prints percent, watts, health, time left, profile, both screen-on totals, uptime and the seconds since the last charger change (-1 = not known).
- **Not built:** history graph. The charge mode (fast charging or a limit at about 80 %) is a setting on the Power profiles page since 2026-10-29 (`power-tuning.md`), not in this popup.
- **Tested** (2026-10-19): popup opens and renders on the bar's screen; the counter reached 30 s after the first tick and was saved. **Not tested:** clicking the profile chips, an unplug resetting the unplug total, lock/DPMS pausing the count, a shell restart keeping the totals.

## Wi-Fi list refresh speed (measured, decided: leave)

Owner report: new networks appear late. Measured 2026-10-18 from NetworkManager's `LastScan`: popup closed = no scans; opening triggers an immediate scan and the first fresh result arrives after 3.1 s (the same as an explicit `nmcli device wifi rescan`: one scan takes 3.1 s on this chip); while open, a scan completes about every 13 s (3 s scan plus Quickshell's roughly 10 s wait, not configurable). Quickshell CPU is about 0 % open or closed, so the list code is not the cause. Options considered: leave it (chosen: no extra radio time or battery), a "Scan now" button (small, not built), scanning faster automatically (rejected: each scan moves the radio off the connected channel and can stutter calls and music). Revisit if the 13 s wait becomes a real annoyance.

## Log lines that look alarming but are harmless (investigated)

- `Pipewire error on object N with code -14` (Quickshell) with `running -> error` / "connection terminated unexpectedly" (WirePlumber): a Bluetooth audio device disconnected (Disconnect button, the Bluetooth switch, or the device going away) and its audio node ended. Reproduced twice on purpose.
- `Failed to stop discovery ... Resource Not Ready`: Quickshell itself asks BlueZ to stop discovery when the adapter powers off; the adapter has already ended it. Not from this config and not removable from it.
- bluetoothd `btd_adv_monitor_power_down() Unexpected NULL ... object upon power down` and `Unknown disconnection value: 21`: noise logged on every adapter power-down or disconnect.

## Failure modes found and fixed while building

| Problem | Cause | Fix |
|---|---|---|
| Scanning stayed on after closing the popup | A `Binding` does not restore its value when its window is unloaded | Set on open, cleared in `onDestruction` (tested) |
| Bluetooth discovery started again when closing from the Wi-Fi popup | The `Loader` expression defaulted to the Bluetooth panel when nothing was open, so closing briefly built it | No default: `null` when nothing is open (tested: open, switch, close, 12 rapid switches) |
| Bluetooth devices hung on "Connecting..." and never paired | No pairing agent on the bus (found by reading the binary and `busctl`, then confirmed: with an agent running the phone paired and connected in under 15 s) | Agent runs while the popup is open (see above) |
| Paired devices were left `trusted=no` | The list model is rebuilt on every device property change, destroying the row that remembered the pairing | Trust and connect live in the panel (`Instantiator`), not in a row |
| `BluetoothRow` threw a ReferenceError on every render | Missing `import Quickshell.Bluetooth`; only tested with an empty device list | Import added; rows rendered with devices present |
| Audio popup listed one output and no microphone | A PipeWire node exposes its properties (`media.class`) only while tracked; the list was filtered before anything was tracked, so only the default device passed | Track every node first, filter afterwards. Unbound-node errors on a mute click (seen 3 times) came from the same cause |
| Power menu clicks did nothing | `PowerPanel` used `PanelState` without `import qs.services`; the ReferenceError fired before the command ran. Found only because the owner clicked: the menu had been rendered, never clicked | Import added; every QML file audited for missing `qs.services` / `qs.components` / `qs` imports (none left) |
| After switching Bluetooth off and on in the popup, the list never started scanning ("Failed to start discovery: Resource Not Ready") | Discovery was requested as soon as `enabled` flipped, while the adapter was still `Enabling` and BlueZ refused. Found with a 0.2 s recorder of the adapter state: `on` -> `on-disabling` -> `off` -> `off-enabling` -> `on` over about 5 s | Start discovery only when `adapter.state` is `Enabled`, and again on every state change. Verified: discovery starts right after the adapter reaches `on` |
| The `bbkos-tui` window stayed tiled | Hyprland matches the whole class: `^bbkos-tui-` never matches | Pattern `bbkos-tui-.*` |

## Not tested (state plainly)

- Joining a real network from the popup, a wrong password, and a real captive portal: testing would drop the connection this session runs on, so only the portal hand-off (`qs ipc call captive open`: private Zen window opened and closed) and the panel states were exercised.
- Pairing by clicking a row with the permanent agent (the agent and the pairing worked with a temporary agent; the panel-held agent was only verified to start and stop with the popup), the trust-on-pair step on a fresh pairing, and earbuds reconnecting after sleep.
- Clicking rows with a mouse: the panels were opened and read through IPC and screenshots, not clicked.
- Hidden or enterprise networks (`nmtui` path).
- Power menu: the real power-key press, every action, the second-click confirm and the failure notification card (the wrapper command was tested with `true` and `false`; no real power action was run).
- Audio popup: picking another output or input, dragging the sliders and the popup mute buttons (only opened and read; I did not switch your sound while it was playing). Earbuds and the Nothing Ear (a) route (out of range during the tests).
