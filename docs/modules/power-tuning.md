# Power profile tuning: measurements and findings

What each power knob costs and gains on this laptop, on kernel 6.18 LTS (2026-10-19) and 7.2 (2026-10-21), what was applied (runtime PM, NMI watchdog off), and the queue of tests still to run.

Measured 2026-10-19 on the Lenovo Slim 7 14IMH9 (Core Ultra 7 155H), **kernel 6.18.57-2-lts**, on battery, 40% brightness, Hyprland with two kitty windows. Tool: `scripts/power-matrix.sh` (workloads idle, 1080p video, "mix" = one fixed job every 2 s, "burst" = 4 threads; sampler `bbkos-power-sample`). Raw results: `power-matrix.csv` (round 1, three profiles), `power-matrix-r2.csv` (knob experiments; `state_end` records what the kernel really held). Noise: about 2-3%; the reference runs repeated within that.

## What power-profiles-daemon does here

It writes two things only: the CPU energy preference (EPP, the same value on all 22 CPUs) and the firmware `platform_profile` (Lenovo DYTC through `ideapad-laptop`). EPP: power-saver `power`, performance `performance`, **balanced `balance_power` on battery but `balance_performance` on AC**. Power limits, turbo, GPU clocks, ASPM and Wi-Fi power save do not change with the profile.

## Round 1: the three profiles (watts / hours on a full battery)

| Workload | power-saver | balanced | performance |
|---|---|---|---|
| Idle | 2.91 W / 19.1 h | 3.08 / 18.1 | 3.60 / 15.5 |
| Video | 5.65 / 9.9 | 5.65 / 9.9 | 9.76 / 5.7 |
| Mix (s per job) | 4.97 / 11.2 (1.09 s) | 5.99 / 9.3 (0.89 s) | 9.59 / 5.8 (0.57 s) |
| Burst (jobs/s) | 18.7 / 3.0 (14.2) | 27.6 / 2.0 (15.8) | 35.6 / 1.6 (19.5), 97 C |

Power-saver is the most energy-efficient per job (burst: 1.31 J vs 1.75 and 1.83). Performance on battery costs +73% for video with no benefit.

## Round 2: which knob does what (from balanced, battery)

| Variant | Mix | Burst |
|---|---|---|
| EPP `balance_performance` (rest as balanced) | 9.93 W, 0.575 s | 36.5 W, 19.8 jobs/s, 91 C |
| firmware `low-power` + EPP `balance_power` | 6.34 W, 0.887 s | 30.5 W, 16.0 (slightly worse than balanced) |
| turbo off | 4.96 W, 1.33 s | 15.6 W, 10.8 |
| PL1 20 W on the MSR interface (`intel-rapl:0`) | no effect | no effect (not the binding limit) |
| **PL1 18 W on the MMIO interface (`intel-rapl-mmio:0`)** | 5.82 W, 0.886 s | **24.3 W, 15.6 (-13% power, -1.5% speed)** |
| PL1 22 W (MMIO) | 6.16 W, 0.886 s | 27.4 W, 15.8 |
| intel-lpmd running | 5.99 W (no gain) | not tested; idle 3.25 vs 3.08 W, video identical |

Conclusions: **EPP is the lever that matters** (balance_performance reproduces the "performance" profile's cost). The firmware profile has almost no power effect (likely fan curve). The firmware's real power limits live on the **MMIO RAPL interface** (PL1 28 W, PL2 64 W, 27 s window) and do not change with the profile; the MSR interface is not binding. Turbo-off is dominated by EPP `power`. intel-lpmd showed no gain.

## Kernel 7.2 vs 6.18 LTS (2026-10-21)

Same reference set and runner on `linux` 7.2.11 (`power-matrix-k72.csv`), battery 87% to 80%, two kitty windows, opencode left running in one of them (about 1% CPU). Average watts from the samples (`avg_w`; the battery energy figure is coarse at idle), one run each, noise about 2-3%.

| Workload | power-saver 6.18 / 7.2 | balanced 6.18 / 7.2 | performance 6.18 / 7.2 |
|---|---|---|---|
| Idle | 2.90 / 3.02 W | 3.01 / 3.00 | 3.65 / 3.40 |
| Video | 5.59 / 5.09 | 5.59 / 4.83 | 9.79 / 8.80 |
| Mix (s per job) | 5.03 / 5.31 W (1.085 / 1.097 s) | 6.18 / 5.46 (0.888 / 0.937) | 9.32 / 9.19 (0.570 / 0.571) |
| Burst, balanced (jobs/s) | | 28.6 / 34.7 W (15.8 / 17.4) | |

Findings: idle is the same (the ~3 W floor is not the kernel). **Video is 9-14% cheaper on 7.2** in every profile. Mix: power-saver and performance unchanged; balanced 12% cheaper and 5% slower. Burst on balanced is 10% faster but 21% more power, so about 10% more energy per job, and 85 C. The profile ranking and the conclusions above still hold on 7.2: EPP is the lever, power-saver is the most efficient, performance on battery is not worth it. 7.2 stays the default kernel.

## Idle knobs on 7.2 (2026-10-21)

Package C-states with the screen on (turbostat, 30 s idle, power-saver): **PC2 87%, PC6/PC8/PC10 0%**, cores C10 99%, GPU RC6 97%, package 2.27 W. On Meteor Lake this is architectural: PC6 and deeper need the PCH, the SoC-IOE die link and the PCIe fabric to power-gate, which they do only in s2idle (reference: blog.fsck.com "Linux power tuning on Meteor Lake", 2026-03, which measured 3.5-4 W tuned idle on another MTL laptop). S0ix residency in suspend is non-zero (`low_power_idle_system_residency_us`), so suspend reaches it. powertop's tunables list: runtime PM `on` for 10 PCI devices (NVMe, Wi-Fi, ISH, GNA, DTT, PMT, host bridge, eSPI, SPI, shared SRAM), NMI watchdog on; its EPP and `min_perf_pct` suggestions cost power and were ignored.

Variants from balanced, battery, one run each (`power-matrix-k72-idle.csv`; `state_end` confirms each knob held: `pci_on`, `nmi`, `i915_cpus`):

| Variant | Idle W | Video W |
|---|---|---|
| base-balanced | 3.06 | 4.90 |
| balanced-rpm (runtime PM `auto` on all PCI) | 2.99 | 4.88 |
| balanced-nmi0 (NMI watchdog off) | 3.01 | 4.84 |
| balanced-irqlp (i915, iwlwifi, audio IRQs on CPU 20-21) | 2.95 | 4.79 |
| balanced-idleset (all three) | **2.92** | **4.82** |

Each knob alone is within the 2-3% noise; together -0.14 W idle (-4.6%, about +1 h on a full battery at idle) and -0.08 W video. The IRQ move was not tested under load (responsiveness, video at high load).

## Redraws and direct scanout (2026-10-25)

- **Redraws cost real CPU.** Hyprland uses variable refresh (`debug.vfr` on) and full damage tracking (`debug.damage_tracking` 2), so it only draws when a client changes; the cost is whatever keeps clients changing. The music widget's animated progress line kept the bar repainting at 60 Hz while a song played (Hyprland 10 % and Quickshell 7 % of a core; 3 % and 1 % without it), so the line was removed (`media.md`). A video in a tiled Zen window still costs Hyprland about 10 % of a core: each video frame is composited. Zen decodes on the GPU (`iHD_drv_video.so` from `intel-media-driver` is loaded in its decode process).
- **Blur costs nothing now:** `decoration.blur` is on (size 9, 3 passes) but every window is opaque (kitty `background_opacity 1.0`, window opacity 1.0) and no layer rule blurs the bar or popups; the bar's own blur is drawn once in Quickshell (`BarBlur.qml`).
- **`render.direct_scanout` stays 0** (tried and rejected 2026-10-25). It is meant to hand a single fullscreen window straight to the display without compositing; 2 ("auto") only does it for windows that say they are games, so 1 was tried. Fullscreen mpv test pattern (20 s each): Hyprland 6 % of a core off and on. Fullscreen Stremio playing a film on battery, 60 s each, alternated off/on/off/on: 7.80, 7.79, 7.91, 8.13 W (7.86 W off against 7.96 W on, within run-to-run noise) and Hyprland 4 % of a core every time; had scanout engaged, Hyprland's per-frame work would have dropped, so it most likely never engaged (why is not known: Hyprland's log has no scanout lines, likely trace-only). No gain, and a known risk of fullscreen flicker, so it is set back to 0 in `hyprland.lua`. Also measured: fullscreen video is already cheaper to composite than windowed (Hyprland 4 % for fullscreen Stremio against about 10 % for video in a tiled Zen window).

## Not available on this machine
No Lenovo firmware power attributes (`/sys/class/firmware-attributes` empty), the panel only offers 1920x1200 at 60 Hz, the firmware has no S3 `deep` sleep, no discrete GPU. The Intel SoC slider module parameters exist (`slider_balance`, `slider_offset`) but do not follow profiles and are undocumented for Meteor Lake: do not touch.

## Real-use drain log

`scripts/drain-log.sh start|stop|summary` logs the live session once a minute to `~/.local/state/bbkos/drain-log.csv` (no workload, no inhibitor, so a lid-closed suspend shows as a gap whose energy cost `summary` reports). Added 2026-10-29 because the lab idle floor (about 3 W) is far below what a normal session draws (about 10 W measured while working).

## Open items (not done yet)
- **Status 2026-10-21 (owner away about two days):** runtime PM `auto` + NMI watchdog off installed at 22:20 by `scripts/task17-power-idle.sh` (files in `power/`; `--undo` reverts) as a soak test. Check-in 2026-10-23: both settings back after reboots (`pci_on` 0, `nmi_watchdog` 0 on the 23 Oct boot); one 4 h session on 22 Oct with no Wi-Fi, NVMe, touchpad or PCIe errors in the log and nothing noticed by the owner; **no suspend or hibernate happened**, so resume is still untested (the owner will close the lid later; then read the resume in `journalctl -b`). The i915 "Port A asks to use VBT vswing/preemph tables" warning at boot predates the change (present on 20 Oct). Then, in this order: the IRQ move under load (`-W "mix" -P "base-balanced balanced-irqlp"`; adopt only if mix speed holds), the reboot tests (`i915.enable_psr` modes, the `xe` driver), the all-core cap test. Also queued (owner, 2026-10-21): **`scx_lavd`** (sched_ext, `sudo pacman -S scx-scheds`; the 7.2 kernel has `CONFIG_SCHED_CLASS_EXT=y`, state `disabled` now; test its default and power-saving modes against EEVDF on idle, video, mix; stopping it returns to EEVDF at once) and **`intel_pstate/hwp_dynamic_boost`** 1 (now 0; mix speed vs watts). Both need new matrix variants. Checked and not worth testing: the NVMe I/O scheduler (`none` is right for NVMe), custom kernels (zen, BORE: latency, not battery), swappiness (30 GB RAM, swap unused), preemption mode and HZ (dynamic, 1000). TLP was considered and not adopted: it would fight power-profiles-daemon (or, as `tlp-pd`, replace it and clash with the Power page helper); its two settings that mattered here are the ones applied.
- **Run the matrix from the owner's kitty, not with `!` in Claude Code:** the `sudo -v` ticket is per terminal, so `sudo -v && scripts/power-matrix.sh ...` in one line. In fish, a leading `!` means `not`.
- **All-core load with the MMIO cap** (`burstall` workload, variants base-balanced, balanced-mmio18w, balanced-mmio22w, power-saver). The 4-thread burst understates how hard a cap bites; a 10 s dry run of all cores drew about 54 W and reached 93 C before the sustained limit applied. Needed before adopting a cap.
- **Kernel comparison:** done 2026-10-21, see "Kernel 7.2 vs 6.18 LTS" below. The knob experiments (round 2) and the MMIO cap were not repeated on 7.2.
- **Idle floor** (about 2.9-3.1 W): not a profile effect; look at Wi-Fi power save, ASPM, runtime PM, C-state residency and the display.
- Settings page: per-profile EPP (and possibly the MMIO PL1 cap), applied by a small root helper with an allowlist and clamped values; the helper must check each file exists (kernel-dependent).

## Settings page and helper (built 2026-10-19; spec `docs/specs/2026-10-19-power-tuning-design.md`)

**What it is.** A Power page in the settings app (index 8; Power and sleep › Power profiles since 2026-10-28) where each profile (Battery saver, Balanced, Performance) gets three knobs: CPU energy preference (EPP), turbo and a package power cap. Every knob starts at "System default", so nothing changes until you choose. Keys: `power.<saver|balanced|performance>Epp` / `Turbo` / `Cap` (cap 0 = off, 1-9 W are stored as 10, maximum 28). Edited through `bbkos-theme set` like every setting.

**Battery charging (added 2026-10-29).** One more setting for every profile, `power.chargeMode`: `default` (bbkOS does not touch the battery), `Fast`, `Standard` or `Long_Life` (shown as "Limit to ~80 %"). These are the values of `/sys/class/power_supply/BAT0/charge_types` (`ideapad_acpi`); the file lists all of them with the active one in brackets (`[Fast] Standard Long_Life`), only one can be active, so a limit and fast charging cannot both be on. `Long_Life` is Lenovo's conservation mode: writing it set `conservation_mode` to 1 (checked 2026-10-29), and the firmware picks the stop point (about 80 % on IdeaPads; not yet seen on this battery). The firmware keeps the last mode across reboots and in Windows, so `default` leaves whatever was set last (also by Lenovo Vantage); any other choice is written again at each helper run (login, resume, charger, edit), which undoes a change made under Windows.

**Parts.**
- `power/bbkos-power-apply`: the root helper, ONE self-contained file (standard library only, installed root-owned; it must never import code from the home directory). No arguments. Reads `~/.config/bbkos/settings.json` with the user's own rights (the real file is a stow symlink), validates every value again, reads the active profile from power-profiles-daemon and writes only EPP (`cpu*/cpufreq/energy_performance_preference`), `intel_pstate/no_turbo` and the MMIO RAPL PL1 (`intel-rapl-mmio:0`), plus `power_supply/BAT*/charge_types` when `power.chargeMode` is not `default` (only a value the file offers, and only when it is not already active). The cap is never raised above the firmware's own value (saved on first use in `/run/bbkos-power/orig.json`). Missing files are reported under `skipped`, never an error. Prints one JSON line.
- `scripts/install-power-helper.sh`: run once with sudo. Copies the helper to `/usr/local/sbin/bbkos-power-apply` and installs `/etc/sudoers.d/bbkos-power` (checked with `visudo -cf`) allowing exactly that file with no arguments. `--uninstall` removes both.
- `services/PowerTuning.qml`: runs the helper at login, 400 ms after a profile change, when the charger is plugged or unplugged, after a `power.*` edit and after a resume; one run at a time (a request during a run runs once more afterwards), 10 s watchdog. Going back to "System default" for the current profile's EPP bounces the profile so the daemon rewrites its own value. `qs ipc call power status` / `apply` are the test hooks; status is `idle`, `applying`, `not-installed` or `error: ...`.
- `modules/settings/PagePower.qml`: the page; an "Applied now" line reads the real values from sysfs without root, and the Battery charging section's "Charging now" row reads the bracketed mode from `charge_types`.

**Install (once).** `sudo ~/.local/share/bbkos/repo/scripts/install-power-helper.sh`. The helper and its sudoers rule are permanent (they survive reboots and shell restarts); run the script again only after an uninstall, on a fresh system, or after the helper file `power/bbkos-power-apply` itself changed (the installed file is a copy). Uninstall: `sudo ~/.local/share/bbkos/repo/scripts/install-power-helper.sh --uninstall`.

**Banner and status.** The service learns whether the helper works only when it runs it (login, profile, charger or settings change, a resume, or opening the Power page). Opening the page re-runs the helper, so a "not installed" banner left over from before the install clears when the page is opened.

**Gotcha: switching git branches under a running shell.** `~/.config/quickshell` is a stow link into this checkout, so a `git checkout` that deletes and recreates `services/PowerTuning.qml` can leave the running shell registered without it (`ReferenceError: PowerTuning is not defined`, `qs ipc call power status` empty). A touch-reload does not clear it; `systemctl --user restart quickshell.service` does (briefly restarts the bar and notifications and closes the settings window).

**Recovery (everything also resets on reboot).**
```
sudo sh -c 'echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo; echo 28000000 > /sys/class/powercap/intel-rapl-mmio:0/constraint_0_power_limit_uw'
powerprofilesctl set performance; powerprofilesctl set power-saver
```

**Tests.** `python3 -m unittest discover -s tests/power` (helper against a fake sysfs tree, settings file checks, installer) and `tests/theme` (settings and CLI). The service was checked against a stand-in helper (success, failure, 3 rapid requests -> 2 runs, hung helper -> `error: helper timed out` after 11 s).

**Found while building.** The real `settings.json` is a symlink, so the helper had to follow symlinks (it reads as the user, then checks owner, type and size on the opened file); `bbkos-theme reset` and the store's revert-on-open each keep their own section list, so `power` had to be added to both.

**Verified on the laptop (2026-10-19, kernel 6.18.57-2-lts, helper installed).**
- sudo rule: an argument is refused by sudo ("a password is required"), no argument runs without a password, any other command is refused.
- Saver profile: EPP `balance_performance` read back on cpu0, cpu14 and cpu21 (P, E and low-power cores); turbo off gave `no_turbo` 1; cap 18 W gave MMIO PL1 `18000000`.
- Switching to balanced removed those overrides (EPP `balance_power`, turbo on, 28 W); switching back to power-saver brought all three back; setting each knob back to default restored the firmware values, EPP through the profile bounce (profile ended on power-saver).
- Charger: with balanced + EPP `power`, plugging in made the daemon write `balance_performance` at +1.0 s and the service restored `power` 1.5 s later; unplugging: daemon `balance_power`, restored after 0.5 s. The override is briefly overwritten on each change.
- Two bugs only the hardware run showed, both in the settings-edit trigger of `PowerTuning.qml`: the first edit after a shell start was skipped, and the change detector, written as a property initializer, was a binding that updated itself so every edit compared equal. It is now assigned once in `Component.onCompleted`.
- `qs ipc call power status` also reports `seen` (the power.* values the service last saw).
- Not verified: resume from sleep, and the page itself as a picture (the screen was locked).
- Deferred minors from the final review are in the branch ledger; see the list in the hand-over message.

**Verified for the charge mode (2026-10-29, kernel 7.2.11, helper reinstalled and byte-equal to the repo copy).** `bbkos-theme set power.chargeMode` with `Long_Life`, `Standard` and `Fast` in turn: within 3 s the shell's own helper run made `charge_types` read `Fast Standard [Long_Life]` (`conservation_mode` 1), `Fast [Standard] Long_Life` (0), `[Fast] Standard Long_Life` (0); the helper reported each under `applied.charge` with no errors. Back to `default` left `[Fast]`, as designed. The page was screenshotted: the four choices with "System default" selected and "Charging now: Fast". Not verified: where the limit really stops (needs a charge past 80 % with `Long_Life`), and whether Windows keeps or changes the mode.

