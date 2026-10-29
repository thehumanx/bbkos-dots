# Night light (hyprsunset)

Added 2026-10-24. Settings: the Night light card of **Displays** (`PageDisplays`; its own page `PageNightLight`, sidebar index 17, until 2026-10-28), keys `nightlight.*`
(`settings.py`), package `hyprsunset` (official repo, 261 KiB, installed by the owner). Reference: the Night light pages of COSMIC
and DankMaterialShell (GammaControl); the method is the one documented on the Hyprland wiki (hyprsunset profiles).

## What it does

`hyprsunset` warms the screen colour through the compositor's colour matrix (`hyprland-ctm-control-v1`), so screenshots and
recordings keep the normal colours, and nothing is drawn by a shader. Nothing runs while the mode is off.

| Key | Default | Range |
|---|---|---|
| `nightlight.mode` | `off` | `off`, `on` (warm all the time), `schedule` (warm from `start` until `end`) |
| `nightlight.temperature` | 4000 | 2500-6000 K step 100; lower is warmer, 6000 is no change |
| `nightlight.start` / `end` | `21:00` / `07:00` | 24 h `H:MM` (anything else is refused); the page offers evening and morning presets |

`bbkos-theme set nightlight.mode schedule`.

## How it works

- `bbkos-theme` writes `~/.config/hypr/hyprsunset.conf` on every apply (like omasnap's config; only for the real settings file,
  `BBKOS_HYPRSUNSET_CONF` overrides the path): `on` is one profile at 00:00 with the temperature; `schedule` is a neutral
  profile (`identity = true`) at `end` and a warm one at `start`; `off` is a neutral profile. hyprsunset applies the profile for the
  current time at start and switches by timer (no polling). Read in its source: before the first profile of the day it uses the
  last one, so a schedule that crosses midnight is warm at 03:00.
- `reload.reload_nightlight` runs the packaged `hyprsunset.service`: mode on or schedule, `enable` (so it starts at the next login)
  and `start`, or `restart` when the generated file differs from `nightlight-active.conf` in the state directory (hyprsunset reads
  its config only at start); mode off, `disable --now`. Skipped without hyprsunset, and when HOME is not the real home (the
  test suite must never touch the live unit; see `idle.md`).
- The unit lives in `session.slice` and is enabled through a link in `~/.config/systemd/user/graphical-session.target.wants/`
  (state, not tracked).

## Verified (2026-10-24)

10 tests in `tests/theme/test_nightlight.py` (the three renders, bad times and ranges, start, restart and stop decisions, the
guards), the whole theme suite (459, the live unit stayed inactive and disabled during it). Live: mode on gave the unit active and
enabled, the right file, `hyprctl hyprsunset profile` = 4000 K and the CTM in the journal; a new temperature restarted it (3500 K);
`schedule` at 10:3x chose the neutral profile (6000 K, identity), and with `start` moved to 10:00 the warm one; off stopped and
disabled it and removed the marker. The page on screen. Settings were put back to off, 4000 K, 21:00 and 07:00.

**Not verified:** how the screen looks at night (the colour matrix is not in a screenshot, and no one was looking), a real wait
for a profile switch at the set time, the unit starting at the next login, a second monitor (hyprsunset applies to all outputs).

## Not done

A sunrise and sunset schedule from the location, a keyboard shortcut or bar toggle, the gamma (extra dimming) control hyprsunset
also has.
