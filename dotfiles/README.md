# Dotfiles

One GNU Stow package per directory, each mirroring `$HOME`. `install.sh` links them; you rarely need to run Stow yourself.

| Package | Links to |
|---|---|
| `hypr` | `~/.config/hypr/` (`hyprland.lua`, `hypridle.conf`, `lock-avatar.png`) |
| `quickshell` | `~/.config/quickshell` (the whole directory, **folded**) |
| `bin` | `~/.local/bin/bbkos-*` commands and `~/.local/lib/bbkos_theme/` (their Python code) |
| `uwsm` | `~/.config/uwsm/env` (session environment, `PATH`) |
| `systemd-user` | `~/.config/systemd/user/` (`quickshell.service`, `cliphist.service`, `bbkos-camera.service`, drop-ins) |
| `kitty`, `fish` | terminal and shell |
| `gtk` | `~/.config/gtk-3.0/gtk.css` (a comment; GTK 3 takes colours from the generated theme) |
| `thunar` | the "Set as wallpaper" action |
| `xdg-apps` | launcher entries hidden |
| `bbkos-settings` | `~/.config/bbkos/matugen.toml` |

**Not linked, rendered or copied by `install.sh`:**

| File | Why |
|---|---|
| `~/.config/hypr/hyprlock.conf`, `~/.config/gtk-4.0/gtk.css` | rendered from `templates/` (they hold absolute paths) |
| `~/.config/bbkos/settings.json` | copied from `defaults/settings.json`: it is *your* file, the settings app writes to it |

The cursor theme is not a package here: `install.sh` fetches Afterglow (GPL-3.0) from its own repository at a pinned commit.

## By hand

```sh
stow -n -v --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ hypr   # dry run first
stow --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ hypr          # link
stow -D -d ~/.local/share/bbkos/repo/dotfiles -t ~ hypr                    # unlink
```

## Rules

- Use `--no-folding` for every package except `quickshell` (apps that write state into their config directory would write it into the repo).
- Always `-t ~`: without it Stow links into the repo's parent.
- The checkout must stay where it is: the links point into it (`~/.local/share/bbkos/repo` is a link to it).
- Never commit secrets or state (keyrings, tokens, `fish_variables`, caches).
