#!/usr/bin/env bash
# install-touchpad-watch.sh [--uninstall] [--prefix DIR]
# Installs the touchpad diagnostic logger (docs/modules/touchpad.md, "Diagnostic watch"):
#   /usr/local/sbin/bbkos-touchpad-watch                  root:root 0755, a copy of touchpad/bbkos-touchpad-watch
#   /etc/systemd/system/bbkos-touchpad-watch.service      root:root 0644, a copy of touchpad/bbkos-touchpad-watch.service
# then enables and starts the service. It writes /var/log/bbkos-touchpad-watch.log (0644).
# Run with sudo. --uninstall stops and removes both (the log is kept). --prefix DIR installs under DIR without systemctl:
# for the tests.
set -euo pipefail

prefix=""; uninstall=0
while [ $# -gt 0 ]; do
    case $1 in
        --prefix) prefix=${2:?--prefix needs a directory}; shift 2 ;;
        --uninstall) uninstall=1; shift ;;
        *) echo "usage: install-touchpad-watch.sh [--uninstall] [--prefix DIR]" >&2; exit 2 ;;
    esac
done

repo="$(cd "$(dirname "$0")/.." && pwd)"
bin="$prefix/usr/local/sbin/bbkos-touchpad-watch"
unit="$prefix/etc/systemd/system/bbkos-touchpad-watch.service"
real=0; [ -z "$prefix" ] && real=1

if [ "$real" = 1 ] && [ "$(id -u)" != 0 ]; then echo "needs root: run it with sudo" >&2; exit 1; fi

if [ "$uninstall" = 1 ]; then
    [ "$real" = 1 ] && systemctl disable --now bbkos-touchpad-watch.service 2>/dev/null || true
    rm -f "$bin" "$unit"
    [ "$real" = 1 ] && systemctl daemon-reload
    echo "removed $bin and $unit (the log /var/log/bbkos-touchpad-watch.log is kept)"
    exit 0
fi

for f in touchpad/bbkos-touchpad-watch touchpad/bbkos-touchpad-watch.service; do
    [ -f "$repo/$f" ] || { echo "missing $repo/$f" >&2; exit 1; }
done

own=(); [ "$real" = 1 ] && own=(-o root -g root)
mkdir -p "$(dirname "$bin")" "$(dirname "$unit")"
install "${own[@]}" -m 0755 "$repo/touchpad/bbkos-touchpad-watch" "$bin"
install "${own[@]}" -m 0644 "$repo/touchpad/bbkos-touchpad-watch.service" "$unit"
if [ "$real" = 1 ]; then
    systemctl daemon-reload
    systemctl enable --now bbkos-touchpad-watch.service
    systemctl restart bbkos-touchpad-watch.service      # a reinstall picks up the new copy
fi
echo "installed $bin and $unit"
