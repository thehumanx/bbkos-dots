#!/usr/bin/env bash
# Build and install omasnap (screenshots, OCR, annotation: docs/modules/capture.md) into ~/.local, at a pinned commit.
# No root needed. The build dependencies are installed by you first (this script never runs sudo):
#   sudo pacman -S --needed cmake ninja layer-shell-qt tesseract-data-eng
# Why a commit and not the v1.21.0 tag: the tag has no `[output] autosave` option (save by default on/off); it arrived in
# commit e23ce79, 81 commits later. Update COMMIT after reading what changed.
set -euo pipefail

COMMIT=6771b19        # 2026-10-03, "fix(tests): keep smoke artifacts in the build directory"
SRC="${XDG_CACHE_HOME:-$HOME/.cache}/omasnap-src"
PREFIX="${OMASNAP_PREFIX:-$HOME/.local}"

missing=()
for pkg in cmake ninja layer-shell-qt tesseract tesseract-data-eng qt6-base wayland-protocols libdeflate wl-clipboard; do
    pacman -Qq "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "missing packages: ${missing[*]}" >&2
    echo "run: sudo pacman -S --needed ${missing[*]}" >&2
    exit 1
fi

[ -d "$SRC/.git" ] || git clone https://github.com/omacom/omasnap.git "$SRC"
git -C "$SRC" fetch --quiet origin
git -C "$SRC" checkout --quiet "$COMMIT"
make -C "$SRC" build PREFIX="$PREFIX"
cmake --install "$SRC/build" --prefix "$PREFIX"
"$PREFIX/bin/omasnap" --version
echo "installed at commit $COMMIT. Its notifications need ~/.local/bin/omarchy-notification-send (stow package bin)."
