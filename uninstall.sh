#!/usr/bin/env bash
# Undo ./install.sh. By default: unlink the dotfiles, remove the files it rendered, disable the user services and put
# back the files it moved aside. Packages, system services and your settings are only touched when you ask.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

usage() { cat <<'U'
usage: ./uninstall.sh [options]
  --dry-run     show what would happen
  -y, --yes     take the default answer to every question
  --system      also remove the root helpers and disable the system services install.sh enabled
  --packages    also remove (pacman -Rns) the packages install.sh installed; packages that were already there stay
  --purge       also delete your settings and state: ~/.config/bbkos, ~/.local/state/bbkos, the wallpaper copy, the backups
  -h, --help
U
}
DRY=0; SYSTEM=0; PKGS=0; PURGE=0
while [ $# -gt 0 ]; do
    case $1 in
        --dry-run) DRY=1 ;; -y|--yes) ASSUME_YES=1 ;; --system) SYSTEM=1 ;; --packages) PKGS=1 ;; --purge) PURGE=1 ;;
        -h|--help) usage; exit 0 ;; *) usage >&2; exit 2 ;;
    esac; shift
done
run() { if [ $DRY = 1 ]; then printf '    %s[dry-run]%s %s\n' "$D" "$N" "$*"; else "$@"; fi; }
[ "$(id -u)" != 0 ] || die "run as your normal user"
[ -f "$STATE_FILE" ] || warn "no install record at $STATE_FILE: unlinking anyway, restoring nothing"

if pgrep -x quickshell >/dev/null && [ -n "${WAYLAND_DISPLAY:-}" ]; then
    warn "Quickshell is running in this session: the bar disappears when its service stops."
    ask "Continue?" y || exit 1
fi

step "User services"
for u in $(state_get units | tr ' ' '\n' | sort -u); do
    run systemctl --user disable --now "$u" >/dev/null 2>&1 && info "disabled $u" || true
done

step "Unlinking dotfiles"
for p in "${STOW_PKGS[@]}"; do
    [ -d "$REPO/dotfiles/$p" ] && { run stow -D -d "$REPO/dotfiles" -t "$HOME" "$p" 2>&1 | grep -v '^$' || true; }
done
for f in $(state_get rendered | sort -u); do [ -e "$f" ] && { run rm -f "$f"; info "removed ${f#"$HOME"/}"; }; done
[ -L "$SHARE/repo" ] && run rm -f "$SHARE/repo"
run systemctl --user daemon-reload

step "Restoring files that were moved aside"
restored=0
for d in $(ls -d "$BACKUP_ROOT"/*/ 2>/dev/null | sort); do
    [ -f "$d/manifest" ] || continue
    while IFS= read -r rel; do
        t="$HOME/$rel"
        if [ -e "$d/$rel" ] || [ -L "$d/$rel" ]; then
            if [ -e "$t" ] || [ -L "$t" ]; then warn "~/$rel exists, left the backup in $d"; continue; fi
            run mkdir -p "$(dirname "$t")"; run mv "$d/$rel" "$t"; info "restored ~/$rel"; restored=1
        fi
    done < "$d/manifest"
done
[ $restored = 0 ] && info "nothing to restore"

if [ $SYSTEM = 1 ]; then
    step "System parts"
    helpers=$(state_get helpers)
    [[ $helpers == *power* ]] && run sudo bash "$REPO/scripts/install-power-helper.sh" --user "$USER" --uninstall
    [[ $helpers == *logind* ]] && run sudo bash "$REPO/scripts/install-logind-helper.sh" --user "$USER" --uninstall
    [[ $helpers == *touchpad* ]] && run sudo bash "$REPO/scripts/install-touchpad-helper.sh" --user "$USER" --uninstall
    for u in $(state_get enabled | sort -u); do ask "Disable $u (install.sh enabled it)?" n && run sudo systemctl disable --now "$u"; done
fi

if [ $PKGS = 1 ]; then
    step "Packages"
    mapfile -t list < <(state_get packages | tr ' ' '\n' | awk 'NF' | sort -u | while read -r p; do pacman -Qq "$p" >/dev/null 2>&1 && echo "$p"; done)
    if [ ${#list[@]} -eq 0 ]; then info "nothing recorded"; else
        info "installed by install.sh: ${list[*]}"
        warn "this removes the desktop itself (hyprland, quickshell, ...). pacman shows what else goes and asks."
        ask "Remove them with pacman -Rns?" n && run sudo pacman -Rns "${list[@]}"
    fi
fi

if [ $PURGE = 1 ]; then
    step "Purging settings and state"
    ask "Delete ~/.config/bbkos, ~/.local/state/bbkos and ~/.local/share/bbkos (wallpaper copy, backups)?" n && \
        run rm -rf "$HOME/.config/bbkos" "$HOME/.local/state/bbkos" "$SHARE"
else
    [ $DRY = 0 ] && rm -f "$STATE_FILE"
    info "kept ~/.config/bbkos (your settings) and ~/.local/state/bbkos; --purge deletes them"
fi
step "Done"
