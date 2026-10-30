---
name: bbkos
description: REQUIRED for any work on this bbkOS desktop (Hyprland + Quickshell). Use when editing ~/.config/hypr/, ~/.config/quickshell/, ~/.config/bbkos/, the dotfiles in ~/.local/share/bbkos/repo, or the kitty and fish configs, or when running bbkos-* commands. Triggers include Hyprland, window rules, keybindings, monitors, gaps, blur, theme, wallpaper, the bar, the settings app, lock screen, idle, power, battery, touchpad, Wi-Fi and Bluetooth panels, updates, Stow and dotfiles. Carries the rules that were broken before and points to the docs in ~/.local/share/bbkos/repo, which are the source of truth.
---

# bbkOS

## What bbkOS is
Arch Linux + Hyprland + Quickshell desktop (the bbkos-dots repo). `~/.local/share/bbkos/repo` is a symlink to the checkout that holds the dotfiles, scripts, tests and the docs; the installed config files are symlinks into it. The docs say what is built, why, and what was rejected; they describe only what is really applied. Read before you change, and trust the docs over memory.

## Rules
These each come from a real mistake while building this desktop.
1. **Read first.** Read `docs/principles.md`, then the module doc for the thing you touch (find it in `modules-index.md` next to this file). Read a file or service state before changing it.
2. **Stow:** link only with `stow --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ <package>`, after a `-n -v` dry run. Without `-t ~` Stow links into the repo's parent and litters the repo with a `.local` link. `quickshell` is the one folded package (`dotfiles/README.md`).
3. **Never run `sudo`.** Show the exact command and the user runs it (`! <command>` in the Claude Code prompt), then check the result yourself. A `sudo -v` there does not give your shell a ticket (it is per terminal), so for a long root run give one line, `sudo -v && <command>`, for the user's kitty, and say to type it **without** `!`: in fish a leading `!` means `not`, and the command is silently skipped. Root helpers live in `power/` and `touchpad/` with `scripts/install-*-helper.sh`.
4. **Driver reloads are two commands, never `cmd1 && cmd2`.** A chained remove-and-load once left the driver unloaded and the user without a cursor. Give the remove, check, then give the load. A reboot is the last resort.
5. **Find the cause before the fix.** No guessed fixes: read the code and the live state (logs, `journalctl`, `hyprctl`). If the cause is not found, say what was ruled out.
6. **Never write "verified" for something you did not observe.** Prove it with a command, a log line or a `grim` screenshot of the live screen, and write down what was NOT verified (a real boot, a real click, a second monitor). Bar and shell layout changes are checked for every bar position and mode; restore the user's settings afterwards.
7. **Settings go through the tool, and resets need a yes.** Change look settings with `bbkos-theme set KEY VALUE`; never hand-edit the generated files in `~/.local/state/bbkos/theme/`. `~/.config/bbkos/settings.json` is the user's live file (a copy made by install.sh, not a link into the repo; `defaults/settings.json` is the shipped look): do not revert it. Ask the user before `bbkos-theme reset` or any restore-defaults.
8. **Do not write Hyprland or Quickshell code from memory.** The Hyprland config is Lua (0.55+), not `hyprland.conf`: the API reference is `/usr/share/hypr/stubs/hl.meta.lua`; Quickshell facts are in `docs/modules/quickshell.md`. After ANY Hyprland config change run `hyprctl reload`, then `hyprctl configerrors`, and fix until it is empty.
9. **Root helpers are installed copies.** `/usr/local/sbin/` and `/etc/sudoers.d/` hold copies made by `scripts/install-*-helper.sh`; Edit the repo copy (`power/`, `touchpad/`) and ask the user to rerun the installer; never edit the installed file.
10. **Changelog:** this repo has no changelog file: describe the change and what was verified in the commit message.
11. **Do not start long measurement runs unasked** (power tuning: `docs/modules/power-tuning.md`). Do not delete files or branches you did not create unless asked.
12. **Git:** commit to a branch after the tests pass; never push unless the user asks.
13. **Look at other people's work before building.** For any non-trivial feature (an overview, a gesture, a panel, an animation), first find how existing projects solve it (GitHub, Codeberg, the Hyprland and Quickshell communities; clone to the scratchpad and read, do not run it) and borrow the proven approach. Do not build from scratch or over-engineer when a reference exists; say in the module doc which reference the design follows.
14. **Check the screen is unlocked before touching the live session.** Before a Quickshell restart, `hyprctl reload`, `bbkos-keybinds apply`, `bbkos-theme apply` or any on-screen test, run `pgrep -x hyprlock`: if it prints a pid the user is away and the session is locked, so stop the live steps and work on files and tests only. A locked session died once while such steps ran; the safe recovery is `hyprctl eval 'hl.exec_cmd("bbkos-lock")'` (a new hyprlock takes the lock over), never `hl.clear_crashed_lockscreen()`, which unlocks without a password.

## Where things live
- `dotfiles/<package>/` mirrors `~` (Stow packages); `dotfiles/bin/.local/bin/` holds the `bbkos-*` commands and `dotfiles/bin/.local/lib/bbkos_theme/` their Python code.
- `dotfiles/quickshell/.config/quickshell/` is the shell: `services/` (state), `modules/` (bar, panels, settings pages).
- `install.sh` / `uninstall.sh` (hardware detection, packages in `packages/*.txt`, Stow, backups), `scripts/` the root-helper installers (run by the user with sudo); `tests/<area>/` unit tests; `docs/` as in `README.md`.
- Generated at runtime: `~/.local/state/bbkos/` (theme files, flags such as `awake` and `bluetooth-off`).

## Tools
Every command with a one-line description is under `## Commands` in `.claude/skills/bbkos/modules-index.md`. The ones you will use most:
- `bbkos-theme` status, `set KEY VALUE`, `apply`, `reset [SECTION|KEY...]`, `defaults`, wallpaper: the settings and theme engine (`docs/modules/theme.md`).
- `bbkos-display` per-monitor scale, mode and layout; `bbkos-keybinds` keybindings (`docs/modules/keybindings.md`).
- `bbkos-check` health check after any change; `bbkos-update` the update routine (`docs/modules/update-safety.md`).
- `bbkos-qml-audit` finds missing QML imports and QML that does not parse: run it after QML edits, then `systemctl --user restart quickshell` (a syntax error stops the whole bar).
- `bbkos-touchpad-reset` reloads a stalled touchpad (`docs/modules/touchpad.md`); `bbkos-awake` and `bbkos-lid` idle and lid behaviour.
- `bbkos-lock-test` locks the screen for real: it can trip a failed-login lockout, so run it only when the user asks.

## Example requests
- "Make the window gaps smaller" -> `bbkos-theme set windows.gapsIn 2`, then `bbkos-theme status`.
- "Make the bar taller" -> `bbkos-theme set shell.barHeight 40`.
- "Change the wallpaper" -> `bbkos-theme wallpaper set FILE` (colours follow the wallpaper).
- "Add or change a shortcut" -> `bbkos-keybinds` (never edit the generated binds file); read `docs/modules/keybindings.md`.
- "Scale the external monitor" -> `bbkos-display set-scale NAME 1.25`.
- "The touchpad stopped responding" -> `bbkos-touchpad-reset`; if it says the helper is missing, read `docs/modules/touchpad.md`.
- "Is everything fine after the update?" -> `bbkos-check`.
- "Add a setting to the settings app" -> read `docs/modules/theme.md` and `docs/modules/settings-app.md` first (the page list is `modules/settings/Pages.js`), put the row on the page and tab where someone would look for it, run `python3 scripts/build-settings-index.py`, then follow Finishing a change.

## Where to read
- `docs/principles.md` always first; `docs/design.md` before adding any visible feature, setting, widget, panel or command; `git log` for what changed recently.
- `.claude/skills/bbkos/modules-index.md` to find the module doc for a topic.
- `docs/modules/failure-modes.md` for known edge cases, `docs/modules/` for the design behind a feature.

## Finishing a change
1. Run the tests for the area: `python3 -m unittest discover -s tests/theme` (also `tests/power`, `tests/keybinds`, `tests/touchpad`, `tests/launcher`, `tests/dictation`, `tests/stage`, `tests/skill`), then `bbkos-check`. After a shell (QML) change also `python3 -m unittest discover -s tests/shell -t .`: a separate test shell in a nested Hyprland, about 4 minutes, never the live one (`docs/modules/shell-tests.md`). After editing a `.js` file in the shell, restart Quickshell (live reload keeps the old script).
2. Update the module doc, and say in the commit message what was verified and what was not.
   Then sweep for stale text before committing: `grep -rn` the docs and this skill for the old value, file, setting or state you just changed, and fix every hit; add a dated update note to a decision instead of rewriting it. Check that each touched doc's first paragraph (the skill index summary) and this file's rules still hold.
3. If you added or renamed a doc, run `python3 scripts/build-skill-index.py` (the `tests/skill` suite fails until you do). If you added, moved or renamed a settings row, run `python3 scripts/build-settings-index.py` (`tests/theme` fails until you do).
4. Commit; push only when asked.
