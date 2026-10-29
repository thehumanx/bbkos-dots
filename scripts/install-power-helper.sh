#!/usr/bin/env bash
# install-power-helper.sh [--user NAME] [--uninstall] [--prefix DIR]
# Installs the root helper for the Power settings page (docs/specs/2026-10-19-power-tuning-design.md):
#   /usr/local/sbin/bbkos-power-apply      root:root 0755, a copy of power/bbkos-power-apply
#   /etc/sudoers.d/bbkos-power             root:root 0440, lets NAME run exactly that file, with no arguments, without a password
# Run with sudo. NAME defaults to $SUDO_USER. The sudoers file is checked with `visudo -cf` before it is put in place.
# --uninstall removes both. --prefix DIR installs under DIR instead of / (no chown, no visudo): for the tests.
set -euo pipefail

prefix=""; user="${SUDO_USER:-}"; uninstall=0
while [ $# -gt 0 ]; do
    case $1 in
        --prefix) prefix=${2:?--prefix needs a directory}; shift 2 ;;
        --user) user=${2:?--user needs a name}; shift 2 ;;
        --uninstall) uninstall=1; shift ;;
        *) echo "usage: install-power-helper.sh [--user NAME] [--uninstall] [--prefix DIR]" >&2; exit 2 ;;
    esac
done

src="$(cd "$(dirname "$0")/.." && pwd)/power/bbkos-power-apply"
helper="$prefix/usr/local/sbin/bbkos-power-apply"
rule="$prefix/etc/sudoers.d/bbkos-power"
real=0; [ -z "$prefix" ] && real=1

if [ "$real" = 1 ] && [ "$(id -u)" != 0 ]; then echo "needs root: run it with sudo" >&2; exit 1; fi

if [ "$uninstall" = 1 ]; then
    rm -f "$helper" "$rule"
    echo "removed $helper and $rule"
    exit 0
fi

[ -n "$user" ] || { echo "no user: pass --user NAME (or run through sudo)" >&2; exit 2; }
[[ $user =~ ^[a-z_][a-z0-9_-]*$ && $user != root ]] || { echo "refusing user name '$user'" >&2; exit 2; }
[ -f "$src" ] || { echo "missing $src" >&2; exit 1; }

own=(); [ "$real" = 1 ] && own=(-o root -g root)
mkdir -p "$(dirname "$helper")" "$(dirname "$rule")"          # never chmod an existing /etc/sudoers.d
install "${own[@]}" -m 0755 "$src" "$helper"

tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/bbkos-power-apply ""\n' "$user" > "$tmp"
if [ "$real" = 1 ]; then
    visudo -cf "$tmp" >/dev/null || { echo "visudo rejected the rule; nothing installed for sudo" >&2; exit 1; }
fi
install "${own[@]}" -m 0440 "$tmp" "$rule"
echo "installed $helper and $rule (user $user)"
