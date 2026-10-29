#!/usr/bin/env bash
# Set up dictation (docs/modules/dictation.md): link the Voxtype config, download the model, start the user service.
# Run it as yourself, never with sudo. The package itself is installed by you first (this script never runs sudo or yay):
#   yay -S voxtype      (builds from source; the prebuilt voxtype-bin fetches ~700 MB of GPU variants from GitHub releases)
# Safe to run again. `--dry-run` prints the steps and runs none of them.
set -euo pipefail

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

# BBKOS_FAKE_EUID exists for the test only, and only with --dry-run.
euid=$EUID
[ "$DRY" = 1 ] && euid=${BBKOS_FAKE_EUID:-$EUID}
if [ "$euid" -eq 0 ]; then
    echo "do not run this as root: it sets up your own user service and config" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

step() {
    if [ "$DRY" = 1 ]; then
        echo "would run: $*"
    else
        echo "+ $*"
        "$@"
    fi
}

if [ "$DRY" = 1 ]; then
    echo "would run: yay -S voxtype   (you run this first; the script does not)"
elif ! command -v voxtype >/dev/null 2>&1; then
    echo "voxtype is not installed. Install it first, then run this again:" >&2
    echo "  yay -S voxtype" >&2
    exit 1
fi

step stow -n -v --no-folding -d "$REPO/dotfiles" -t "$HOME" voxtype
step stow --no-folding -d "$REPO/dotfiles" -t "$HOME" voxtype
step voxtype setup --download
step voxtype setup systemd
step systemctl --user enable --now voxtype
[ "$DRY" = 1 ] || echo "done. Dictation: Super+Ctrl+X to start, again to stop (once the key preset is applied)."
