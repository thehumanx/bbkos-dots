# Module: desktop tools

Applied: 2026-10-18 (Task 7). Script: `scripts/task07-desktop-tools.sh`. Configs in `dotfiles/hypr` and `dotfiles/bin`. Decision: `docs/decisions/0002-desktop-essentials.md`.

## What is installed and configured

| Tool | Config / unit | Notes |
|---|---|---|
| `hypridle` | `~/.config/hypr/hypridle.conf`; user unit `hypridle.service` (enabled, `WantedBy=graphical-session.target`). `lock_cmd` is `bbkos-lock` (flock-guarded `hyprlock`, see the incident below); `after_sleep_cmd` also runs `loginctl lock-session`, so a lock that failed before sleep is retried at once on resume | Timers are settings now (`idle.*`, page Idle and lock, `idle.md`): `bbkos-idle` starts hypridle on the generated `hypridle.conf`; the static file is the fallback. Defaults: 150 s dim (brightness to 10) and keyboard backlight off (`platform::kbd_backlight`); 300 s lock (`bbkos-awake idle-lock` → `loginctl lock-session`, skipped while awake mode is on); 330 s screen off; 900 s `bbkos-awake idle-suspend` (runs `systemctl suspend-then-hibernate` unless awake mode is on; see `displays.md`); lock before any sleep. Event-driven. PSS 1.4 MB. |
| `hyprlock` | generated `~/.local/state/bbkos/theme/hyprlock.conf` (from the `lock` settings, edited on the settings app's Lock screen page; `bbkos-lock` uses it when it exists and has a `background` block); `~/.config/hypr/hyprlock.conf` is the static fallback | The saved wallpaper blurred (not a screenshot), round avatar (`lock-avatar.png`), "Welcome $USER", small date, large time, frosted borderless password field (translucent fill, no outline; the background is already blurred), battery line from `bbkos-lock-battery` (level icon and percent, a bolt while charging). Animations off. No fingerprint (no reader). Triggered by `Super+CTRL+L` (moved from `Super+L` on 2026-10-21, when `Super+L` became the Power menu) via logind so hypridle's `lock_cmd` keeps a single instance. |
| `omasnap` (screenshots, editor, OCR), `grim`, `slurp`, `wl-clipboard` | `~/.local/bin/omasnap` (built by `scripts/install-omasnap.sh`); the older `~/.local/bin/bbkos-screenshot {region\|full}` still works but nothing binds it | **`Super+Shift+S`** = smart selector (region, window or screen). Since 2026-10-21; see `capture.md`. |
| `gpu-screen-recorder` | `~/.local/bin/bbkos-record` (`capture.md`) | `Super+Shift+R` stops a recording, or opens the options panel. Hardware H.264 on Arc verified (see below) and a 60 fps recording verified 2026-10-21. |
| `thunar`, `gvfs`, `tumbler`, `ffmpegthumbnailer`, `yazi` | `xdg-mime inode/directory` = thunar | `fileManager = "thunar"` in `hyprland.lua` (`Super+E`). |
| `mpv`, `imv`, `zathura`, `zathura-pdf-mupdf` | defaults | Video, images, PDFs. |
| `playerctl` | binds already in `hyprland.lua` | Media keys. |
| `ttf-jetbrains-mono-nerd` | system font | Glyphs for starship, hyprlock, Quickshell. |

Hyprland changes (`hyprland.lua`): `Super+L`, `Print`, `Shift+Print`; `misc.force_default_wallpaper = 0`, `disable_hyprland_logo = true`, `background_color = 0xff101014` (no wallpaper daemon until phase 3); `misc.allow_session_lock_restore = true`.

## Decisions changed during this task (with evidence)

- **`hyprpolkitagent` removed from the design and uninstalled (2026-10-18, Task 8).** Measured PSS **115 MB** (RSS 159 MB), about as much as the compositor, for a dialog used rarely. Quickshell ships a native `Quickshell.Services.Polkit` module, so the agent moves into the Quickshell shell (Task 8), saving about 115 MB and a process. Until then the unit is disabled: GUI privilege prompts do not appear; `sudo` in a terminal is unaffected. The package is uninstalled once Quickshell polkit is verified.
- **`hyprpaper` skipped, `cliphist` deferred** (see ledger): no resident process for a missing wallpaper; clipboard history arrives with its picker.
- **`ffmpegthumbnailer` added** for video thumbnails (movies are a stated use).

## Verification (2026-10-18)

- All 17 packages installed.
- `hyprctl reload` ok, `hyprctl configerrors` empty; `Super+L`, `Print`, `Shift+Print` registered (`hyprctl binds`).
- `hypridle`: log `found 5 rules`, matching the config; sleep inhibition registered; service active.
- `bbkos-screenshot full` wrote a PNG to `~/Pictures/Screenshots/` and the PNG was in the clipboard (`wl-paste` magic `89 50 4E 47`).
- `gpu-screen-recorder -w eDP-1 -k h264 -encoder gpu -fallback-cpu-encoding no` for 6 s: "capturing and encoding on that gpu"; output H.264 1920x1200 at 30 fps; process 8-13 % of one core, about 207 MB RSS while recording. Test file deleted.
- `xdg-mime query default inode/directory` = `thunar.desktop`.
- Owner-run checks (2026-10-18): lock screen, `Super+E` and media keys passed; the Print key did not behave as expected, which led to the two findings above.

## Hardware quirk: the Print key sends `Super+Shift+S`

On the Slim 7 14IMH9 the physical Print key emits the Windows snipping shortcut `Super+Shift+S`, not the `Print` keysym. Found 2026-10-18 by recording Hyprland's event stream (socket2) while the key was pressed: it showed `movewindow>>...,special:magic`, which is what the default `SUPER+SHIFT+S` scratchpad bind does. The scratchpad "move" bind therefore moved to `SUPER+CTRL+S` (toggle stays on `SUPER+S`).

## Session PATH (bug found and fixed)

Hyprland's environment did not contain `~/.local/bin`: `~/.bashrc` returns early for non-interactive shells before it sets `PATH`, so binds, systemd user units and Quickshell never saw user scripts. Fix: `dotfiles/uwsm/.config/uwsm/env` (`export PATH="$HOME/.local/bin:$PATH"`), the standard uwsm place for session-wide variables. It takes effect at the **next login**. Check with:
`tr '\0' '\n' < /proc/$(pgrep -x Hyprland)/environ | grep '^PATH='` (must include `.local/bin`).

## Post-login verification (owner, 2026-10-18)

After re-login: `/proc/<Hyprland>/environ` `PATH` starts with `/home/user/.local/bin`; the Print key (Super+Shift+S) takes a region screenshot into `~/Pictures/Screenshots/`.

## Incident 2026-10-18: laptop slept and hibernated unlocked

Symptom: after a suspend-then-hibernate test the session came back without a password prompt.

Cause (from the journal): lid close triggered **two** lock requests at once (`bbkos-lid closed` and hypridle's `before_sleep_cmd`). Both passed the stock guard `pidof hyprlock || hyprlock` before either had started, so two hyprlocks started. The loser was refused the session lock but kept running. From then on `pidof hyprlock` was always true, so hypridle never started a real lock; at the next lid close systemd waited the 5 s sleep-inhibitor limit (`Delay lock is active ... but inhibitor timeout is reached`) and slept unlocked, then hibernated and resumed unlocked.

Fixes: (1) `bbkos-lid` no longer locks when there is no external display (hypridle's sleep hook already does, verified in the journal); (2) `lock_cmd` is now `bbkos-lock`, which runs `hyprlock` under `flock` held for its whole lifetime, so a concurrent or repeated request fails at once instead of starting a second instance; (3) `after_sleep_cmd` locks again on resume as a backstop. Verified: two simultaneous `loginctl lock-session` calls produced exactly one hyprlock, and zero remained after unlock. Observed facts: `LockedHint` stays `no` while locked, hyprlock exits on unlock, `hyprctl status` has no lock flag.

Re-test of the full lid, suspend, hibernate, resume path is pending.

## Lock screen recovery

`allow_session_lock_restore = true` lets a new locker take over. If the screen ever shows the red "lockdead" image: `Ctrl+Alt+F3`, log in, then
`WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/user/1000 hyprlock`, or as a last resort `systemctl --user restart wayland-wm@hyprland.desktop.service` (ends the graphical session; apps close).

## Progress bar (`bbkos-progress`)

`bbkos-progress [-w WIDTH] [-n] DONE TOTAL [UNIT]` draws a one-line bar, `[██████░░░░░░░░░░░░░░░░░░░░░░░░] 2/9 steps`: full blocks in the terminal's cyan for the done part, light-shade blocks (`░`) dimmed for the rest. Called again it redraws in place and ends the line at DONE = TOTAL. UNIT `%` shows a percentage (`bbkos-progress 45 100 %`). `-n` prints a new line per call (logs); piped output is plain text. Width defaults to 30 and shrinks to fit the terminal. Used by `bbkos-update`; it only draws bars for our own scripts, other tools (pacman, git, curl) draw their own. Checked in kitty: colours, in-place redraw and the 0, partial and full states.

## Lock screen editor (`bbkos-lock-test`)

`bbkos-lock-test [SECONDS]` (1-30, default 5) locks for real through `bbkos-lock`, waits, captures `$XDG_RUNTIME_DIR/bbkos-lock-test.png` with `grim`, unlocks with `loginctl unlock-session` and, if the lock is still up, `pkill -USR1 -x hyprlock` (hyprlock's unlock signal; `unlock-session` once did not end a lock started from a backgrounded shell). It prints the capture path. **Account lockout hazard (found 2026-10-19):** ending a lock from outside counts as one failed login for `pam_faillock` (three in ten minutes lock the account: the lock screen, `sudo` and the login all refuse even the right password; three tests in a row did exactly that). So it refuses with exit 3 while `faillock --user $USER` lists any valid failure, and with exit 1 if a lock is already up (it never unlocks a lock it did not start). Check with `faillock --user $USER`; entries expire after about 10 minutes. If the lock never starts it does nothing else (exit 1); if the screen is still locked after both unlocks it says so and exits 1 (type the password). Tests: `tests/theme/test_bbkos_lock_test.py` (fake lock, grim, loginctl) and `test_bbkos_lock.py` (generated config and fallback).

## Undo

`systemctl --user disable --now hypridle.service`; `stow -D -d ~/.local/share/bbkos/repo/dotfiles -t ~ bin`; remove the three binds and the `misc` lines from `hyprland.lua`; `pacman -Rns` the packages listed in `scripts/task07-desktop-tools.sh`.
