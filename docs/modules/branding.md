# Branding: ASCII logo, animated screensaver, About window

Added 2026-11-11. One editable ASCII logo, shown in an About window (fastfetch plus a glint) and in an animated terminal screensaver that starts on idle, before the lock. Settings `branding.screensaver`, `branding.effects` (a list) and `idle.screensaver` (Power and sleep › When idle, card "Screensaver"); commands `bbkos-branding`, `bbkos-about-window`, `bbkos-screensaver`. Spec `docs/specs/2026-11-11-branding-design.md`, plan `docs/plans/2026-11-11-branding.md`.

## Reference

Omarchy (`basecamp/omarchy`, cloned into the scratchpad and read, not run): `manual/41-branding.md`, `bin/omarchy-launch-about`, `bin/omarchy-branding-about-animation`. Borrowed: the two branding files (about and screensaver), the glint sweep over the About logo (only when every logo character is one column wide), the screensaver as a fullscreen terminal per monitor before the lock. Not borrowed: the About window sizing by measurement (a fixed float rule is enough here), image conversion (not built, see "Not built"). The animation library, terminaltexteffects, is what Omarchy's older screensaver used.

## Files

- `~/.config/bbkos/branding/about.txt` and `screensaver.txt`: the logo text, plain files, untracked. A **missing** file falls back to the tracked default in `dotfiles/bin/.local/share/bbkos/branding/` (the word BBKOS in block letters); a file that exists but is **blank** shows nothing.
- `bbkos-branding show|reset KIND`, `set-text KIND FILE`, `words KIND TEXT...` (KIND is `about` or `screensaver`; `words` draws letters and spaces in a small built-in 5-row font and names anything else it dropped on stderr). Code `bbkos_theme/branding.py`.

## About window

`bbkos-about-window` (the name `bbkos-about` was taken: it is the JSON the settings About page reads) opens a floating kitty, class `org.bbkos.about`, fixed 900x480 and centred by a window rule in `hyprland.lua`. Inside, `bbkos_theme/glint.py` runs fastfetch with the logo from `branding.read("about")` and the config `dotfiles/fastfetch/.config/fastfetch/config.jsonc` (Stow package `fastfetch`), finds where the logo was drawn, and every 4 s repaints a diagonal band of bright cyan (palette colour 14) over the logo cells, handing each cell back in its base colour. It stays still for a logo with double-width characters, a blank logo and `NO_COLOR`. A key closes it; a resize redraws.

Plain `fastfetch` in any terminal uses the same config and shows the same logo: the config's `logo.source` is `~/.config/bbkos/branding/about.txt` (added 2026-11-11 at the owner's request; before that it showed the Arch logo). That file is created by `bbkos-branding reset about` (done once on this machine); if it is missing fastfetch falls back to its own logo. The About window passes the text itself with `--logo`, which overrides the config (checked), so it also works without the file.

## Screensaver

`bbkos-screensaver` opens one fullscreen kitty per monitor (class `org.bbkos.screensaver`; placed with the `monitor` and `fullscreen` rules of `hl.dsp.exec_cmd`) that loops `tte EFFECT` over the logo. `bbkos-screensaver stop` closes them. It does nothing when `tte` is missing, when it is already running (exit 0), and when the logo is blank or `hyprlock` is running (exit 3). A key in one window closes the windows on every monitor. The effects (`branding.effects`, a list from decrypt, beams, matrix, slide, rain, burn, waves) are read from `settings.json`. One effect plays once and the window waits for a key; several play one after another in that fixed list order (not the order they were ticked), a 3 s pause between, and start over after the last. Unknown names are dropped, an empty list plays decrypt. The old single key `branding.effect` is read as a one-item list (settings validation and the script both). In the settings window the Effects row is a row of multi-select chips with a checkbox in front, so it differs from the single-choice chips (one filled chip, no box). Checked 2026-11-11: matrix then rain then matrix then rain in a pty (`BBKOS_SAVER_MAX`, timestamps from a `tte` shim); in a real fullscreen kitty a stray Esc byte ended a run twice (any key ends it by design; cause not proven, probably a real keypress).

- **Idle step.** `render_hypridle` puts a listener at `idle.screensaver` (default 150 s) running `bbkos-awake idle-screensaver`, in place of the dim listener while `branding.screensaver` is on and the timer is above 0. The keyboard-light listener moves with it (it uses the screensaver's timer while the screensaver is active, `idle.dim` otherwise). Lock 300 s, screen off 330 s and suspend 900 s are unchanged. Awake mode skips it like every idle step.
- **Without tte, or when it declines** (blank logo, or the lock is already up: `bbkos-screensaver` exits 3) `bbkos-awake idle-screensaver` dims instead (the old step), so a machine without the package loses nothing; `bbkos-check` prints a note. The on-resume command (`idle-screensaver-resume`) closes the screensaver on any key or pointer movement and restores the brightness if it dimmed.
- **Lock.** `bbkos-lock` runs `bbkos-screensaver stop` before it starts hyprlock, so a manual lock never draws over the animation.

## Dependency

`python-terminaltexteffects` (AUR). Why: it is the effect library Omarchy and the community use. Alternatives: write the effects ourselves (code to maintain), a Quickshell overlay (not a terminal, and testing it means locking the real screen). Pure Python, no native dependencies; the PKGBUILD was read on 2026-11-11 (pinned source checksum, no install script) (`docs/decisions/0005-terminaltexteffects.md`). The owner runs the install.

## Cost (estimate, not measured)

The screensaver redraws continuously on the iGPU, but only between its timer and the lock (150 s with the defaults), then it is closed. One kitty and one Python process per monitor, gone afterwards. Nothing runs at login, nothing polls. Not measured: the battery cost of a full run (method in `docs/measurement.md`).

## Verified (2026-11-11)

Tests `test_branding`, `test_bbkos_screensaver`, `test_glint`, `test_bbkos_awake`, `test_idle`, `test_bbkos_check` (fakes for kitty, hyprctl, pgrep, tte). Live, with the screen unlocked: the About window (grim: floating, 900x480, logo and modules; burst crops show the glint band moving over the logo); a screensaver window opened fullscreen on eDP-1 through the real `hyprctl dispatch` line and `bbkos-screensaver stop` closed it; `hyprctl configerrors` empty.

The Idle page on screen (grim): the timeline shows "Saver" in place of "Dim", the Screensaver card (toggle, effect chips, Preview and About window buttons), search jumps to the row; `bbkos-theme apply` rendered the hypridle listeners with the owner's live settings and hypridle stayed active.

After the owner installed `python-terminaltexteffects` 0.15.0 (same day): every flag the script uses and all seven effects exist in `tte -h`; `bbkos-screensaver` run for real played decrypt on the internal screen (grim: the scrambled characters resolving into the logo, centred) and `stop` closed it. Two fixes from that run: `--canvas-width 0 --canvas-height 0` (tte sizes its canvas to the text by default, so the logo sat small at the top) and kitty `font_size=36` for the screensaver windows. A third fix (owner: "the text moves slightly up at the end"): with the canvas as tall as the terminal, `tte` ends with a newline that scrolls the screen up one row (measured: the logo's top edge went from y 355 to y 285 at font 36, one 70 px row); `--no-eol` removes it (measured again: the top edge stays at 355 in every settled frame over 16 s).

`tests/shell` (nested test shell, on a clean checkout of the committed state, 563 s): 44 of 45 pass; the one failure was the qmllint baseline, whose `PageIdle.qml` and `IdleTimeline.qml` counts went up because the Screensaver card adds rows (the findings are the usual unresolved `qs.components` types and unqualified ids, nothing new in kind); the baseline was updated for those two files only. `test_bbkos_check` has 6 failures that also fail on the commit before this work (checked in a scratch checkout).

**Not verified:** the other six effects on screen, a real idle wait through screensaver, lock and screen off, HDMI as the second monitor, the battery cost, a reboot, a real click on the settings rows.

## Not built

Image-to-ASCII conversion (`from-image`): no ImageMagick, chafa or Pillow is installed, so it waits for the owner to pick a converter (chafa is the smallest). An animated hyprlock and a boot splash were left out on purpose.
