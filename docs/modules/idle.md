# Idle and lock (the idle timers)

Added 2026-10-24. Settings: **Power and sleep › When idle** (`PageIdle`, place `power/idle`, with a time line of the steps; the Idle and lock page, sidebar index 14, until 2026-10-28), keys `idle.*` (`settings.py`
`IDLE_DEFAULTS` and `RANGES`), the command `bbkos-idle`, the generated `hypridle.conf`, and the awake-mode switch on the same page.
Reference: COSMIC and GNOME Power pages and DankMaterialShell's PowerSleep tab, which all expose these timers.

## What it does

Until now the timers were fixed in `dotfiles/hypr/.config/hypr/hypridle.conf`. They are now settings, seconds of inactivity
before each step, `0` = never (steps of 30 s, 0 to 3600; the page offers presets as chips, the CLI takes any value):

| Key | Default | Step |
|---|---|---|
| `idle.dim` | 150 | dim the screen and switch the keyboard light off (two listeners, one setting) |
| `idle.lock` | 300 | lock (`bbkos-awake idle-lock`, then `loginctl lock-session`) |
| `idle.screenOff` | 330 | switch the screen off |
| `idle.suspend` | 900 | `suspend-then-hibernate` |

`bbkos-theme set idle.lock 600`. Every step still asks `bbkos-awake`, so awake mode skips all of them. A manual lock (key, menu,
bar), the lock before sleep (lid, `before_sleep_cmd`) and the lock after resume do not depend on these timers.

## How it works

- `render.render_hypridle` writes `~/.local/state/bbkos/theme/hypridle.conf` (one of the generated files; a step set to 0 has no
  listener, the `general` block with the lock-before-sleep commands is always there).
- **`bbkos-idle`** is the unit's `ExecStart` (user drop-in `hypridle.service.d/10-bbkos-idle.conf`, Stow package
  `systemd-user`). It runs `hypridle -c` on the generated file when that exists and has a `general` block, otherwise plain
  `hypridle` on the static `~/.config/hypr/hypridle.conf` (kept as the fallback, same idea as `bbkos-lock`). It copies the file it
  used to `hypridle-active.conf`.
- `reload.reload_hypridle` restarts `hypridle.service` after an apply only when the generated file differs from
  `hypridle-active.conf` and the unit is running, so changing an unrelated setting never resets the idle timers. It is skipped
  when HOME is not the real home (see the incident).
- The static `hypridle.conf` keeps the old defaults (lock and the rest through `bbkos-awake`).

## Verified (2026-10-24)

11 tests in `tests/theme/test_idle.py` (render with defaults equal to the old timers, 0 = no listener, snapping, restart only when
changed, never from a temporary HOME, `bbkos-idle` choosing the file) and the whole theme suite (438). Live: `bbkos-theme set
idle.dim 120` rewrote the file and restarted hypridle (running with `-c` on the generated file), back to 150 the same way;
the page on screen (screenshot) with the defaults highlighted.

**Not verified:** a real idle wait for each step with awake mode off, a reboot (the drop-in starts `bbkos-idle` at login), the
page's chips clicked with a real pointer.

## Incident (2026-10-24)

The first version of `reload_hypridle` had no guard, so the test suite called the real `systemctl --user restart hypridle` six
times in five seconds; systemd refused to start it again (`start-limit-hit`) and the idle lock was off until
`systemctl --user reset-failed hypridle && systemctl --user start hypridle`. Now the restart only runs when HOME is the user's
real home, like the GTK reload, and a test covers it (the journal showed no further stops during the full suite).

## Not done

Lid-close and power-button actions are on their own page, **Lid and power button** (`lid-power.md`): they are logind settings and need a root helper.
