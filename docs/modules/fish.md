# Module: fish shell

Applied: 2026-10-18 (Task 3). Dotfiles: `dotfiles/fish`, `dotfiles/kitty` (managed with GNU Stow).

## What is configured

- `fish` (interactive) and `starship` (prompt). The **login shell stays bash** (`getent passwd bbk` → `/usr/bin/bash`), so `uwsm`, greetd and scripts keep a POSIX environment. Fish is started only by kitty (`shell fish` in `kitty.conf`).
- `dotfiles/fish/.config/fish/config.fish`: adds `~/.local/bin` to PATH, empties the greeting, color aliases, `starship init fish`.
- `dotfiles/fish/.config/fish/functions/bbk.fish` (2026-10-26): `bbk` does `cd ~/.local/share/bbkos/repo` and runs `claude`, passing arguments on (`bbk -c` continues the last session). Stowed with `--no-folding`, so `~/.config/fish/functions` is a real directory holding the link.
- Starship's glyphs need a Nerd Font; installed in Task 7. Until then some symbols may show as boxes.

## Stow notes (important)

Link with `--no-folding` for anything that writes state into its own directory:

```
stow -d ~/.local/share/bbkos/repo/dotfiles -t ~ kitty
stow -d ~/.local/share/bbkos/repo/dotfiles --no-folding -t ~ fish
```

Without `--no-folding`, Stow links the whole `~/.config/fish` directory into the repo and fish writes `fish_variables` (local state) into git. `dotfiles/.gitignore` also excludes it. `fish_variables` is a real local file, not tracked.

## Why fish

See `docs/decisions/0001-foundation-and-safety.md`. Alternatives: zsh (more plugins, needs config), bash (no features). Scripts keep a bash shebang.

## Undo

`stow -D -d ~/.local/share/bbkos/repo/dotfiles -t ~ fish kitty`; kitty falls back to the login shell (bash).
