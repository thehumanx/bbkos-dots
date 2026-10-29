# Lid and power button

Added 2026-10-24. Settings: **Power and sleep › Lid and power button** (`PageLidPower`, place `power/lid`; sidebar index 26 until 2026-10-28), keys `session.*`
(`settings.py`), the root helper `power/bbkos-logind-apply` with `scripts/install-logind-helper.sh`, the service
`services/LogindApply.qml`, and a change to `bbkos-lid check`. Reference: the Power pages of GNOME and COSMIC (lid and power button
actions) and the existing root-helper design of the Power page (`power-tuning.md`).

## What it sets

| Key | Default | logind key | Words offered |
|---|---|---|---|
| `session.lidBattery` | `suspend-then-hibernate` | `HandleLidSwitch` | `suspend-then-hibernate`, `suspend`, `hibernate`, `lock`, `ignore` |
| `session.lidPower` | `suspend-then-hibernate` | `HandleLidSwitchExternalPower` | the same |
| `session.powerKeyLong` | `poweroff` | `HandlePowerKeyLongPress` | `poweroff`, `suspend-then-hibernate`, `suspend`, `hibernate`, `ignore` |

Not settings: a docked lid (an external screen) stays `ignore` (`bbkos-lid` locks the session and switches the laptop panel off), and
a short power press stays `ignore` (Hyprland binds it to the power menu, `panels.md`). Powering off is not offered for the lid, so
a bag cannot shut the laptop down by accident. `lid action: ignore` on the charger keeps the laptop running with the lid shut, which is
what the phone mirror (`remote-screen.md`) needs; on battery it leaves a hot, draining laptop in a bag, and the page says so.

## How it works

- `/etc/systemd/logind.conf.d/bbkos.conf` is now owned by the helper (task09 first wrote it with the same defaults). **`bbkos-logind-apply`**
  is one self-contained root file, like `bbkos-power-apply`: it takes no arguments, finds the user from `SUDO_USER`, reads
  `~/.config/bbkos/settings.json` with the user's own rights (a symlink into the repo works; the file must belong to the user,
  be a regular file and be under 64 KiB), re-checks every value against its fixed word list, writes the drop-in atomically only when the text
  would change, and then runs `systemctl reload systemd-logind` (logind is `Type=notify-reload`: no session ends). It prints one
  JSON line `{applied, changed, errors}`. A settings file it cannot read is an error and nothing is written. Test overrides of the paths
  work only when not root.
- **Install (once, by the owner):** `sudo ~/.local/share/bbkos/repo/scripts/install-logind-helper.sh` copies the helper to `/usr/local/sbin/` (root, 0755) and
  writes `/etc/sudoers.d/bbkos-logind` (0440, `visudo`-checked) that lets the owner run exactly that file with no arguments and no password.
  `--uninstall` removes both. After a change in `power/bbkos-logind-apply` the installer has to be run again (rule 9).
- `LogindApply.qml` runs `sudo -n` on the helper when `session.*` changes (also when changed from the command line, because the
  settings window's root `Scope` initialises the service at shell start), shows "applying" or the helper's first error line, and tells the
  page when the helper is missing (`not-installed`), which then shows the install command.
- **`bbkos-lid check`** (a monitor went away): with the lid closed and no screen left it now does what logind would have done for the
  current power source (read from the drop-in; `ignore` does nothing, `lock` locks, the sleep words run `systemctl`), instead of always
  suspending then hibernating. Without the file it behaves as before.

## Verified (2026-10-24)

13 tests in `tests/power/test_logind.py` (the word lists equal the settings schema, the defaults render the file task09 wrote, a hostile
value cannot reach the file, written once and reloaded only on change, a failed reload reported with the file kept, the symlink and foreign owner
cases, bad files writing nothing, a root run not redirectable, the installer's layout, uninstall and refusals), 4 in
`tests/theme/test_bbkos_lid.py` (the check by power source), and the whole suites.

After the owner ran the installer (the installed copy is byte-identical to `power/bbkos-logind-apply`), a live round trip with the
normal tool: `bbkos-theme set session.lidPower ignore` made the shell run the helper, which rewrote `/etc/systemd/logind.conf.d/bbkos.conf`
(the other keys unchanged), logind logged "Config file reloaded", and `busctl` showed `HandleLidSwitchExternalPower` = `ignore` while
the other three kept their values; the session list was untouched. `bbkos-lid check` (dry run, the lid closed, no screen left) then read
`ignore` on the charger and `suspend-then-hibernate` on battery from the real file. The choice was set back to
`suspend-then-hibernate` the same way, and the file and the live value followed.

**Not verified:** a real lid close on battery and on the charger, a real long power press, a closed lid with the phone mirror running
(and so whether the Wi-Fi stays up for it), the page on screen, the page's "not installed" message after an uninstall, and the helper
after a reboot (the drop-in is a plain file logind reads at start).

## Not done

A choice for the docked lid, the short power press and the "idle action while on the charger" of logind (hypridle's timers are on the Idle page).
