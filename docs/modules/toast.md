# Short notices (toasts). Added 2026-10-29
A small card for a state change: the charger plugged or unplugged, the sound output switched, Tailscale (the VPN) connected or disconnected. It sits above the volume and brightness OSD on the focused monitor, shows for 2.5 s, and a new one replaces the one on screen. Not kept in the notification history: these say what just happened, they are not messages. Files: `dotfiles/quickshell/.config/quickshell/modules/toast/Toast.qml` (the watchers and the card, one file like the OSD), registered in `shell.qml`; settings page: Notifications › "Short notices".

Design follows Caelestia's `Toaster` (one toast singleton called from the service that notices the change; one on/off switch per kind), cloned and read on 2026-10-29, not run. bbkOS differs in keeping the watchers next to the card and in not stacking.

## What triggers it (no polling)
- **Charger:** `Power.pluggedIn` changes (the sysfs read triggered by `udevadm monitor`, so it shows the plug at once, before UPower says "charging").
- **Sound output:** `Audio.sink` changes to a device with another name (`Audio.label`): headphones, Bluetooth, HDMI, picked in the audio popup.
- **VPN:** `tailscale debug watch-ipn -initial` streams one JSON block per Tailscale state change; the top-level `"State": 6` is Running. Idle between changes.
- Values that arrive in the first 3 s after the shell starts are skipped (the first reading is not a change).

## Settings
`notifications.toastCharger`, `toastAudio`, `toastVpn` (bool, default on), one switch each on the Notifications page. Edited with `bbkos-theme set`.

## Test hook
`qs ipc call toast notify TITLE TEXT` shows a card (`show` is not usable as an IPC function name, see `bar.md`).

## Left out, on purpose
- **Caps Lock** (Caelestia has it): the owner does not want it. which Hyprland event fires for it was never found (the recording window caught none), and the other way is polling; do not add a timer for it.
- Game mode, now playing, keyboard layout, Num Lock (Caelestia extras): not asked for.

## Verified and not verified (2026-10-29)
Verified: the card renders above the OSD position on the focused monitor (HDMI, scale 1, dark theme, top bar), no shell errors on two restarts; the **sound output** toast appeared on a real output change (owner saw it); settings keys, defaults and the search index (tests). Not verified: the **charger** and **VPN** toasts on a real plug or `tailscale down`/`up` (a recording window caught neither), the card at the other three bar positions, in light mode and on the laptop panel (scale 1.07), grid mode.
