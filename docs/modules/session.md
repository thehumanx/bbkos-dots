# Module: session (greetd + tuigreet + uwsm)

Applied: 2026-10-18 (Task 5). Script: `scripts/task05-session.sh`. Snapshot before: `pre-task5-session`.

## What is configured

| Item | Where | Notes |
|---|---|---|
| Login manager | `greetd.service` (enabled), `/etc/greetd/config.toml` | tuigreet on VT1, runs as user `greeter`. Replaces the `getty@tty1` login (greetd conflicts with it). |
| Default session | `uwsm start -e -D Hyprland hyprland.desktop` | Deterministic: no `--remember-session`, so a broken remembered session cannot persist. |
| Session picker | tuigreet `--sessions /usr/share/wayland-sessions` | **F3** lists all sessions, including plain `Hyprland` (fallback, no uwsm). |
| Session manager | `uwsm` | Runs Hyprland as the systemd user unit `wayland-wm@hyprland.desktop.service`; `graphical-session.target` is active, so user units (Quickshell, hypridle, ...) can bind to it. |
| Keyring unlock | `/etc/pam.d/greetd` | `pam_gnome_keyring` (auth and session `auto_start`) unlocks the login keyring with the login password. `gnome-keyring-daemon.socket` was already enabled. |

## Why

| Option | Pros | Cons |
|---|---|---|
| **greetd + tuigreet** (chosen) | Tiny, no toolkit dependency; any Wayland greeter (a Quickshell one later) can replace it | Text-only greeter for now |
| SDDM | Graphical, themeable | Heavy, Qt, separate from the Quickshell look |
| TTY autologin / manual `start-hyprland` | Nothing to install | Hyprland and its children run outside systemd; no lock between boot and desktop |

## Verification (2026-10-18)

- `greetd.service` enabled and active.
- `systemctl --user list-units 'wayland-wm@*'` → `wayland-wm@hyprland.desktop.service` active; `graphical-session.target` active.
- `XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=Hyprland`; `loginctl session-status`: `Service: greetd`, `Type: wayland`.
- Keyring: `org.freedesktop.secrets` login collection `Locked = false` after login.
- `systemctl --failed` and `systemctl --user --failed`: none. Boot 13.8 s.

## If login fails (fallbacks)

1. tuigreet: press **F3**, choose plain `Hyprland`.
2. `Ctrl+Alt+F3`, log in, `sudo systemctl disable greetd`, reboot (back to TTY login).
3. GRUB, "Arch Linux snapshots", `pre-task5-session`.

Backups: `/etc/greetd/config.toml.bak-bbkos`, `/etc/pam.d/greetd.bak-bbkos`.

## Notes

The `gnome-keyring-daemon` line in `hyprland.lua` autostart is now redundant (PAM `auto_start` and the socket cover it); removed in Task 6.

## Later

A Quickshell greeter (phase 2) replaces only the `command` in `config.toml`; the session layer stays.

## Autologin and lock (the lock screen is the login screen)

`tuigreet` is a text screen and cannot show a wallpaper, avatar or frosted field, so the login look lives in `hyprlock` instead (decided 2026-10-19; the alternative, a Quickshell greeter on `cage`, was rejected as far more to build and maintain).

| Piece | What it does |
|---|---|
| `scripts/install-autologin.sh` (run with `sudo`) | Adds `[initial_session]` to `/etc/greetd/config.toml`: greetd logs your user in once at boot with the same `uwsm start -e -D Hyprland hyprland.desktop`. `default_session` (tuigreet) is untouched, so after a logout or a crash tuigreet still appears. Adds `auth optional pam_gnome_keyring.so` to `/etc/pam.d/hyprlock`, so the password typed at the lock screen unlocks the GNOME keyring (greetd's PAM did that at login). Backups `*.bak-autologin`; `--uninstall` restores them. Checked against a scratch copy of `/etc` (idempotent, restore is byte-identical). |
| `hyprland.lua`: `hl.on("hyprland.start", ...)` | Runs `bbkos-lock` at the start of every session. It does not depend on how the session was started, so a missing flag cannot leave an open desktop. A tuigreet login also asks for the password once more. |

Trade-offs, accepted: the disk is not encrypted (no LUKS), so the lock screen is the only barrier after boot; for about a second after login the desktop exists before `hyprlock` is up; if `hyprlock` failed to start the desktop would stay open (`allow_session_lock_restore` lets a new one take over).

**Undo / recovery:** `sudo scripts/install-autologin.sh --uninstall`, or from a TTY (`Ctrl+Alt+F3`) restore `/etc/greetd/config.toml.bak-autologin` over `/etc/greetd/config.toml`.

**Not yet verified (needs a reboot):** that the lock appears at boot, and that the password typed there unlocks the keyring.

The lock screen's layout is editable: settings app, Lock screen page (`docs/modules/settings-app.md`). `bbkos-lock`, used by the session-start lock above, runs `hyprlock` on the generated `~/.local/state/bbkos/theme/hyprlock.conf` and falls back to the static `hyprlock.conf` when it is missing or has no `background` block, so a failed render never leaves the session without a lock.
