# Touchpad reset (safety net)

## The problem
The Synaptics touchpad (`SYNA2BA6:00 06CB:CEF5`, I2C HID, two evdev nodes: "Mouse" for the click button and "Touchpad" for touches) sometimes stops sending touches: no cursor movement, scrolling or gestures, while physical clicks still arrive. Seen on 2026-10-20 after the first HDMI monitor connect following a boot (twice), and the same on the owner's earlier Omarchy install. Reloading its driver brings it back.

**Cause: not known.** Ruled out: runtime power management (the device reports `unsupported`), a kernel error (none logged at the time), bbkOS code (the hotplug hook `bbkos-display apply` only rewrites monitor rules; the Hyprland log shows no reload or Lua error). Not shown: the charger. One boot on battery survived the connect, but one boot on the charger also survived it, so charger against battery does not separate the failures. Before the touchpad died the log showed ghost-touch signs ("tool-palm", palm "typing", "kernel bug: Touch jump detected"), which is also what the cursor jumping while typing looks like. Details of the evidence are in the changelog entry of 2026-10-20.

**Update 2026-10-29: the trigger is a monitor hotplug, the charger is not involved.** An HDMI unplug and replug **on battery** (`ADP1/online` 0, "Discharging") broke 2-, 3- and 4-finger gestures again while one-finger movement and clicks kept working. The touchpad's interrupt (`intel-gpio` 160, `SYNA2BA6:00` in `/proc/interrupts`) kept counting while it was used (164765 to 165754), but the Hyprland log had no `[1fg]`..`[4fg]` touch line on the "Touchpad" node after the HDMI connect line, only clicks on the "Mouse" node. So the device still reports, but not as a multi-touch touchpad: it behaves as if it had fallen back to the plain mouse mode a Precision Touchpad starts in, which the driver leaves only when it sets the touchpad input mode at probe; that is why reloading `i2c_hid_acpi` (`bbkos-touchpad-reset`) fixes it every time (it did again; owner confirmed). Why a plug resets the touchpad is not known (an electrical transient or a firmware quirk); not proven without root: the kernel log at the moment of a plug (`sudo dmesg`) and an event trace (`sudo libinput debug-events`) showing the pointer on the Mouse node.

**Open (owner, 2026-10-29: "note it down, revisit later"):** whether bbkOS should run `bbkos-touchpad-reset` by itself a few seconds after a monitor is added or removed (the `monitor.added`/`monitor.removed` hooks in `hyprland.lua` already run `bbkos-display apply`; the cost is a 1-2 s cursor pause after each plug), keep it manual, or first confirm the reset in the kernel log (`sudo dmesg`, `sudo libinput debug-events` around a plug). Nothing is automated yet.

How to see it in the Hyprland log (`/run/user/1000/hypr/*/hyprland.log`): count the touchpad's `gesture: [1fg]`/`[2fg]`/`[3fg]` lines after the last `Connector HDMI-A-1 connected` line. Zero after, many before, is this fault. The evdev node number changes between boots, so match the pattern, not `event11`.

## The safety net
- `bbkos-touchpad-reset` (user command, `dotfiles/bin/.local/bin/`): runs the root helper through `sudo -n` and shows a notification with the result. Exit 3 when the helper is not installed.
- `touchpad/bbkos-touchpad-reload` (root helper, installed as `/usr/local/sbin/bbkos-touchpad-reload`): takes no arguments and no environment; removes `i2c_hid_acpi`, loads it again, waits up to 5 s for a touchpad in `/proc/bus/input/devices`, retries the load once. The driver is always loaded again, even if removing it failed. A lock keeps two reloads from overlapping. Exit 0 back, 1 not back (a reboot restores it), 2 arguments given, 3 busy. The touchscreen shares the driver and is reset too.
- `scripts/install-touchpad-helper.sh` (run once with sudo; `--uninstall` removes both): copies the helper and writes `/etc/sudoers.d/bbkos-touchpad`, which lets your account run exactly that file with no arguments and no password (checked with `visudo -cf`).

Use: `bbkos-touchpad-reset` from a terminal, or bind it on Settings › Keyboard › Shortcuts as a custom command. Without a working cursor, type it in a terminal with the keyboard (or a bound key).

## Manual reload without the helper
Two separate steps, checking between them: `sudo modprobe -r i2c_hid_acpi`, then `sudo modprobe i2c_hid_acpi`. Chaining them with `&&` once left the driver unloaded and no cursor; unbinding only the touchpad device (`/sys/bus/i2c/drivers/i2c_hid_acpi/unbind`) also left it dead. Last resort: reboot.

## Tests and what was not verified
`tests/touchpad/test_touchpad.py` (installer layout, uninstall, bad user names, the user command with a fake `sudo`, the helper refusing arguments). The root helper itself was not run by the tests or by the agent: it reloads a kernel driver and needs root.
