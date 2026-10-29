#!/usr/bin/env bash
# bbkos-dots installer. Detects the hardware, installs the matching packages, links the dotfiles with GNU Stow.
# Nothing is overwritten: every file in the way is moved to ~/.local/share/bbkos/backup/<time>/ and uninstall.sh puts it back.
# Run as your user (it calls sudo itself, and shows what for). See ./install.sh --help.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

usage() { cat <<'U'
usage: ./install.sh [options]
  --detect            print what was detected and the packages that would be installed, then exit
  --dry-run           run every step but change nothing (shows the sudo commands it would run)
  -y, --yes           take the default answer to every question
  --with LIST         comma list of optional parts: dictation, android, remote, snapshots, lpmd,
                      touchpad, all        (default: none; answered interactively otherwise)
  --no-extras         skip packages/extras.txt (fastfetch, yazi, zathura, vim, fwupd, zram, ...)
  --no-packages       link the dotfiles only; install no packages
  --no-omasnap        do not build the screenshot tool from source
  --no-services       do not enable the user services (quickshell, cliphist, hypridle)
  --no-system         touch nothing outside $HOME except the pacman step (no system services, no root helpers)
  -h, --help
U
}

DRY=0; DETECT_ONLY=0; EXTRAS=1; PACKAGES=1; OMASNAP=1; SERVICES=1; SYSTEM=1; WITH=","
while [ $# -gt 0 ]; do
    case $1 in
        --detect) DETECT_ONLY=1 ;;
        --dry-run) DRY=1 ;;
        -y|--yes) ASSUME_YES=1 ;;
        --with) WITH=",${2:?--with needs a list},"; shift ;;
        --no-extras) EXTRAS=0 ;;
        --no-packages) PACKAGES=0 ;;
        --no-omasnap) OMASNAP=0 ;;
        --no-services) SERVICES=0 ;;
        --no-system) SYSTEM=0 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac; shift
done
want() { [[ $WITH == *,all,* || $WITH == *,$1,* ]]; }
OPT_dictation=0; OPT_android=0; OPT_remote=0; OPT_snapshots=0; OPT_lpmd=0; OPT_touchpad=0
run() { if [ $DRY = 1 ]; then printf '    %s[dry-run]%s %s\n' "$D" "$N" "$*"; else "$@"; fi; }

# ---- 1. preflight ----
step "Checking the system"
[ "$(id -u)" != 0 ] || die "run as your normal user, not root (the script uses sudo where needed)"
[ -f /etc/arch-release ] || die "this is for Arch Linux (and derivatives that ship the same repos)"
for c in pacman sudo git; do command -v "$c" >/dev/null || die "$c is required"; done
[ -d "$REPO/dotfiles" ] || die "run it from the repository"
if pacman -Si hyprland >/dev/null 2>&1; then
    hv=$(pacman -Si hyprland | awk '/^Version/{print $3; exit}')
    [ "$(vercmp "$hv" 0.55)" -ge 0 ] || die "the config is Lua and needs Hyprland 0.55 or newer; your repos offer $hv (sudo pacman -Syu first?)"
    info "Hyprland $hv in the repos (Lua config needs >= 0.55)"
else
    warn "hyprland not found in the sync database; run: sudo pacman -Syu"
fi
[ -n "${XDG_SESSION_TYPE:-}" ] && info "running from a $XDG_SESSION_TYPE session"

# ---- 2. detect ----
step "Detecting hardware"
detect_hardware
print_hardware

# ---- 3. choose packages ----
PKG=(); AUR=()
PKG+=($(list_pkgs packages/core.txt))
[ $EXTRAS = 1 ] && PKG+=($(list_pkgs packages/extras.txt))
case $HW_CPU in intel) PKG+=($(list_pkgs packages/hw-intel-cpu.txt)) ;; amd) PKG+=($(list_pkgs packages/hw-amd-cpu.txt)) ;; esac
for g in "${HW_GPUS[@]}"; do PKG+=($(list_pkgs "packages/hw-$g-gpu.txt")); done
[ "$HW_LAPTOP" = 1 ] && PKG+=($(list_pkgs packages/hw-laptop.txt))
[ "$HW_SOF" = 1 ] && PKG+=($(list_pkgs packages/hw-intel-audio-sof.txt))
[ "$HW_BTRFS" = 1 ] && PKG+=($(list_pkgs packages/hw-btrfs.txt))
# Drop what the machine cannot use.
drop() { local x p keep=(); for p in "${PKG[@]}"; do for x in "$@"; do [ "$p" = "$x" ] && continue 2; done; keep+=("$p"); done; PKG=("${keep[@]}"); }
[ "$HW_BLUETOOTH" = 0 ] && drop bluez bluez-utils bluetui
[ "$HW_WIFI" = 0 ] && drop iw
[ "$HW_LAPTOP" = 0 ] && drop powertop
if [[ " ${HW_GPUS[*]} " == *" nvidia "* ]]; then
    warn "NVIDIA GPU found: nvidia-open-dkms needs a Turing (RTX 20xx) or newer card and your kernel's headers."
    warn "Older card or a non-Arch kernel? Edit packages/hw-nvidia-gpu.txt first. Hyprland on NVIDIA: wiki.archlinux.org/title/Hyprland#Fixing_unreadable_cursor"
fi

step "Optional parts"
opt() { # opt KEY "question" default  -> sets OPT_KEY=1/0
    local k=$1 q=$2 d=$3
    if want "$k"; then eval "OPT_$k=1"; elif [ "$WITH" != "," ] || [ "$DETECT_ONLY" = 1 ]; then eval "OPT_$k=0"
    elif ask "$q" "$d"; then eval "OPT_$k=1"; else eval "OPT_$k=0"; fi
}
opt dictation "Dictation (Voxtype, AUR, builds from source, runs on this machine)?" n
opt android "Android apps window and scrcpy?" n
opt remote "Screen sharing over VNC and Tailscale?" n
[ "$HW_BTRFS" = 1 ] && opt snapshots "btrfs snapshots before pacman upgrades (snapper)? Needs a working snapper config" n || OPT_snapshots=0
[ "$HW_LPMD" = 1 ] && opt lpmd "Intel Low Power Mode daemon (your CPU supports it)?" n || OPT_lpmd=0
[ "$HW_TOUCHPAD_I2C" = 1 ] && opt touchpad "Touchpad stall fix (root helper; reloads the I2C driver)?" n || OPT_touchpad=0
[ "${OPT_dictation:-0}" = 1 ] && AUR+=($(list_pkgs packages/optional-dictation.txt))
[ "${OPT_android:-0}" = 1 ] && PKG+=($(list_pkgs packages/optional-android.txt))
[ "${OPT_remote:-0}" = 1 ] && PKG+=($(list_pkgs packages/optional-remote.txt))
[ "${OPT_snapshots:-0}" = 1 ] && PKG+=($(list_pkgs packages/optional-snapshots.txt))
[ "${OPT_lpmd:-0}" = 1 ] && PKG+=($(list_pkgs packages/hw-intel-lpmd.txt))
mapfile -t PKG < <(printf '%s\n' "${PKG[@]}" | awk 'NF' | sort -u)

if [ $DETECT_ONLY = 1 ]; then
    step "Packages that would be installed (${#PKG[@]} from the repos, ${#AUR[@]} from the AUR)"
    printf '    %s\n' "${PKG[*]}"; [ ${#AUR[@]} -gt 0 ] && printf '    AUR: %s\n' "${AUR[*]}"
    exit 0
fi

# ---- 4. packages ----
NEW=()
if [ $PACKAGES = 1 ]; then
    step "Packages"
    mapfile -t known < <(pacman -Slq)
    missing=(); todo=()
    for p in "${PKG[@]}"; do
        if ! printf '%s\n' "${known[@]}" | grep -qx -- "$p"; then missing+=("$p"); continue; fi
        pacman -Qq "$p" >/dev/null 2>&1 || { todo+=("$p"); NEW+=("$p"); }
    done
    [ ${#missing[@]} -gt 0 ] && warn "not in your enabled repos, skipped: ${missing[*]}"
    if [ ${#todo[@]} -gt 0 ]; then
        info "installing ${#todo[@]} packages (${#PKG[@]} wanted, the rest are already installed)"
        run sudo pacman -S --needed "${todo[@]}"
    else info "everything is already installed"; fi
    if [ ${#AUR[@]} -gt 0 ]; then
        helper=$(command -v yay || command -v paru || true)
        if [ -z "$helper" ]; then warn "no AUR helper (yay or paru): install one, then run: yay -S ${AUR[*]}"
        else
            warn "AUR packages are built from user-submitted PKGBUILDs: read them when asked."
            for p in "${AUR[@]}"; do pacman -Qq "$p" >/dev/null 2>&1 || NEW+=("$p"); done
            run "$helper" -S --needed "${AUR[@]}"
        fi
    fi
    [ $DRY = 0 ] && [ ${#NEW[@]} -gt 0 ] && state_add packages "${NEW[*]}"
fi

# ---- 5. link ----
step "Linking dotfiles"
TS=$(date +%Y%m%d-%H%M%S); BK="$BACKUP_ROOT/$TS"; backed=0
backup() { # backup PATH: move a file that is in the way
    local t=$1 rel=${1#"$HOME"/}
    [ $DRY = 1 ] && { info "would back up ~/$rel"; backed=1; return; }
    mkdir -p "$BK/$(dirname "$rel")"; mv "$t" "$BK/$rel"; echo "$rel" >> "$BK/manifest"; backed=1
}
in_repo() { [ -L "$1" ] && [[ $(readlink -f "$1") == "$REPO"/* ]]; }
if [ $DRY = 0 ]; then
    mkdir -p "$SHARE"; ln -sfn "$REPO" "$SHARE/repo"
fi
info "repository linked at ~/.local/share/bbkos/repo (the dotfiles are symlinks into it: do not move the checkout)"
for p in "${STOW_PKGS[@]}"; do
    if [ "$p" = quickshell ]; then
        t="$HOME/.config/quickshell"; { [ -e "$t" ] || [ -L "$t" ]; } && ! in_repo "$t" && ! [ "$(readlink -f "$t")" = "$REPO/dotfiles/quickshell/.config/quickshell" ] && backup "$t"
    else
        while IFS= read -r f; do
            t="$HOME/${f#./}"
            { [ -e "$t" ] || [ -L "$t" ]; } && ! in_repo "$t" && backup "$t"
        done < <(cd "$REPO/dotfiles/$p" && find . \( -type f -o -type l \) ! -name .stow-local-ignore)
    fi
done
[ $backed = 1 ] && info "moved existing files to ~/.local/share/bbkos/backup/$TS"
for p in "${STOW_PKGS[@]}"; do
    flag=--no-folding; [ "$p" = quickshell ] && flag=
    run stow $flag --restow -d "$REPO/dotfiles" -t "$HOME" "$p"
done
[ $DRY = 0 ] && state_add linked "${STOW_PKGS[*]}"
state_add backup "$TS" 2>/dev/null || true
# stow created ~/.config/bbkos/matugen.toml; the files with absolute paths are rendered, not linked
render() { # render TEMPLATE DEST
    local dest=$2
    { [ -e "$dest" ] || [ -L "$dest" ]; } && ! grep -q 'bbkOS' "$dest" 2>/dev/null && backup "$dest"
    [ $DRY = 1 ] && { info "would render ${2#"$HOME"/}"; return; }
    mkdir -p "$(dirname "$dest")"; sed "s#@HOME@#$HOME#g" "$1" > "$dest"; state_add rendered "$dest"
}
render "$REPO/templates/hyprlock.conf" "$HOME/.config/hypr/hyprlock.conf"
render "$REPO/templates/gtk-4.0.css" "$HOME/.config/gtk-4.0/gtk.css"
if [ ! -e "$HOME/.config/bbkos/settings.json" ] && [ $DRY = 0 ]; then
    install -Dm644 "$REPO/defaults/settings.json" "$HOME/.config/bbkos/settings.json"
    state_add created "$HOME/.config/bbkos/settings.json"; info "created ~/.config/bbkos/settings.json (the look; a copy, yours to change)"
fi

# ---- 6. services ----
step "User services"
if [ $DRY = 0 ] && [ $SERVICES = 1 ]; then
    systemctl --user daemon-reload
    units=(quickshell.service cliphist.service hypridle.service)
    [ "$HW_WEBCAM" = 1 ] && units+=(bbkos-camera.service)
    for u in "${units[@]}"; do
        systemctl --user enable "$u" >/dev/null 2>&1 && info "enabled $u" || warn "could not enable $u (hypridle needs its package installed)"
    done
    state_add units "${units[*]}"
fi

# ---- 7. system services and root helpers ----
if [ $SYSTEM = 1 ]; then
step "System services"
svc() { # svc UNIT HW_OK reason
    systemctl is-enabled "$1" >/dev/null 2>&1 && { info "$1 already enabled"; return; }
    [ "$2" = 1 ] || return 0
    if ask "Enable $1 ($3)?" y; then run sudo systemctl enable --now "$1"; state_add enabled "$1"; fi
}
if systemctl is-active NetworkManager >/dev/null 2>&1; then info "NetworkManager already running"
elif systemctl is-active iwd systemd-networkd >/dev/null 2>&1; then warn "iwd/systemd-networkd is running; the Wi-Fi panel needs NetworkManager. Not touching your network stack."
else svc NetworkManager.service 1 "the Wi-Fi panel and bbkos-network use it"; fi
svc bluetooth.service "$HW_BLUETOOTH" "the Bluetooth panel"
if systemctl is-enabled tlp auto-cpufreq >/dev/null 2>&1; then warn "tlp/auto-cpufreq is enabled: skipping power-profiles-daemon (they conflict)"
else svc power-profiles-daemon.service "$HW_LAPTOP" "power profiles in the bar and settings"; fi
if [ "$HW_LAPTOP" = 1 ] && ask "Install the power and lid helpers (root helpers, sudoers rule for exactly one file each)?" y; then
    run sudo bash "$REPO/scripts/install-power-helper.sh" --user "$USER"
    run sudo bash "$REPO/scripts/install-logind-helper.sh" --user "$USER"
    state_add helpers "power logind"
fi
if [ "${OPT_touchpad:-0}" = 1 ]; then
    run sudo bash "$REPO/scripts/install-touchpad-helper.sh" --user "$USER"; state_add helpers "touchpad"
fi
[ "${OPT_dictation:-0}" = 1 ] && command -v voxtype >/dev/null && run bash "$REPO/scripts/install-dictation.sh" || true
fi

if [ $OMASNAP = 1 ] && [ $PACKAGES = 1 ] && ! command -v omasnap >/dev/null; then
    step "Screenshot tool (omasnap, built from source at a pinned commit)"
    run bash "$REPO/scripts/install-omasnap.sh" || warn "omasnap build failed; screenshots stay unavailable. Rerun scripts/install-omasnap.sh"
fi

# ---- 7b. cursor theme: Afterglow (GPL-3.0, so fetched from its repository, not bundled) ----
step "Cursor theme"
AFTERGLOW_URL=https://github.com/yeyushengfan258/Afterglow-Cursors.git
AFTERGLOW_COMMIT=424a3326827f3bc56856fc5a3a1cce8da1ea3ecd      # 2021-11-17, the repository's last commit
CURSOR_OK=1
if [ -d "$HOME/.local/share/icons/Afterglow-cursors" ] || [ -d /usr/share/icons/Afterglow-cursors ]; then
    info "Afterglow-cursors already installed"
elif [ $DRY = 1 ]; then
    info "would clone $AFTERGLOW_URL (commit ${AFTERGLOW_COMMIT:0:7}) and copy dist/ to ~/.local/share/icons/Afterglow-cursors"
else
    tmp=$(mktemp -d)
    if git clone -q --depth 1 "$AFTERGLOW_URL" "$tmp/src" 2>/dev/null && [ "$(git -C "$tmp/src" rev-parse HEAD)" = "$AFTERGLOW_COMMIT" ] && [ -d "$tmp/src/dist/cursors" ]; then
        mkdir -p "$HOME/.local/share/icons" && cp -r "$tmp/src/dist" "$HOME/.local/share/icons/Afterglow-cursors"
        state_add cursor "$HOME/.local/share/icons/Afterglow-cursors"; info "installed Afterglow-cursors (GPL-3.0, github.com/yeyushengfan258/Afterglow-Cursors)"
    else
        CURSOR_OK=0; warn "could not fetch the Afterglow cursors (offline, or the repository changed); using Adwaita"
    fi
    rm -rf "$tmp"
fi

# ---- 8. first theme ----
step "Theme"
if [ $DRY = 0 ]; then
    export PATH="$HOME/.local/bin:$PATH"
    if ! compgen -G "$SHARE/wallpaper/current.*" >/dev/null; then
        bbkos-theme wallpaper set "$REPO/assets/wallpaper.jpg" >/dev/null && info "set the default wallpaper (colours follow it; change it in Settings > Appearance)"
    fi
    lay=$(localectl status 2>/dev/null | awk -F': *' '/X11 Layout/{print $2}'); lay=${lay%%,*}
    [ -n "$lay" ] && [ "$lay" != us ] && bbkos-theme set keyboard.layout "$lay" >/dev/null 2>&1 && info "keyboard layout: $lay"
    [ "$CURSOR_OK" = 0 ] && bbkos-theme set cursor.theme Adwaita >/dev/null 2>&1
    bbkos-theme apply >/dev/null 2>&1 && info "theme generated" || warn "bbkos-theme apply failed; run it by hand to see why"
fi

step "Done"
cat <<M
    Log out, then start the session:
      - from a TTY:       uwsm start hyprland-uwsm.desktop     (add it to your shell profile to start on login)
      - or pick "Hyprland (uwsm-managed)" in your display manager
    Then press Super+, for the settings, and run  bbkos-check  for a health check.
    Undo everything with ./uninstall.sh
M
