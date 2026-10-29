# Agent instructions

This repo is a Hyprland + Quickshell desktop for Arch (see README.md). Before changing anything, read
`.claude/skills/bbkos/SKILL.md`: the rules there (never run sudo for the user, no guessed fixes, settings only through
`bbkos-theme`, check the screen is unlocked before touching the live session, Stow with `-t ~`) each come from a real
mistake. `.claude/skills/bbkos/modules-index.md` maps every topic and every `bbkos-*` command to its doc in `docs/modules/`.

Claude Code loads the skill by itself. For other agents (Codex, opencode, Gemini CLI, Cursor, ...) copy or symlink the
`.claude/skills/bbkos/` folder to where they look for skills or rules, or point them at this file.

Run the tests for the area you touched: `python3 -m unittest discover -s tests/<area>` (theme, keybinds, power, touchpad,
launcher, dictation, android, skill), then `bbkos-check` on a running desktop.
