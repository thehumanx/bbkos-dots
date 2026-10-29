# shellcheck shell=bash
# Shared by install.sh and uninstall.sh: output helpers, hardware detection, paths.

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SHARE="$HOME/.local/share/bbkos"
BACKUP_ROOT="$SHARE/backup"
STATE_FILE="$SHARE/installer"           # one "key=value" per line: linked packages, rendered files, new packages
STOW_PKGS=(bin hypr quickshell uwsm systemd-user kitty fish gtk thunar xdg-apps bbkos-settings)

if [ -t 1 ]; then B=$'\e[1m'; D=$'\e[2m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; N=$'\e[0m'; else B=; D=; G=; Y=; R=; N=; fi
step() { printf '\n%s==>%s %s%s%s\n' "$G" "$N" "$B" "$*" "$N"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '%s  ! %s%s\n' "$Y" "$*" "$N" >&2; }
die()  { printf '%sError:%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

# ask "question" y|n  -> 0 for yes. --yes (ASSUME_YES) and a non-interactive stdin take the default.
ask() {
    local def=${2:-y} reply
    if [ "${ASSUME_YES:-0}" = 1 ] || [ ! -t 0 ]; then [ "$def" = y ]; return; fi
    read -r -p "    $1 [$([ "$def" = y ] && echo Y/n || echo y/N)] " reply
    reply=${reply:-$def}; [[ $reply =~ ^[Yy] ]]
}

# list_pkgs FILE... -> package names, comments stripped
list_pkgs() { grep -hvE '^\s*(#|$)' "$@" 2>/dev/null | awk '{print $1}'; }

state_add() { mkdir -p "$SHARE"; printf '%s=%s\n' "$1" "$2" >> "$STATE_FILE"; }
state_get() { [ -f "$STATE_FILE" ] && sed -n "s/^$1=//p" "$STATE_FILE" || true; }

# ---- hardware detection: each sets HW_* globals; nothing here changes the system ----
detect_hardware() {
    HW_CPU=unknown
    case $(awk -F': *' '/^vendor_id/{print $2; exit}' /proc/cpuinfo) in
        GenuineIntel) HW_CPU=intel ;; AuthenticAMD) HW_CPU=amd ;;
    esac
    HW_CPU_MODEL=$(awk -F': *' '/^model name/{print $2; exit}' /proc/cpuinfo)

    HW_GPUS=()
    local v
    for v in /sys/class/drm/card[0-9]*/device/vendor; do
        [ -r "$v" ] || continue
        case $(<"$v") in 0x8086) HW_GPUS+=(intel) ;; 0x1002) HW_GPUS+=(amd) ;; 0x10de) HW_GPUS+=(nvidia) ;; esac
    done
    mapfile -t HW_GPUS < <(printf '%s\n' "${HW_GPUS[@]}" | sort -u)

    HW_LAPTOP=0; compgen -G '/sys/class/power_supply/BAT*' >/dev/null && HW_LAPTOP=1
    HW_BLUETOOTH=0; compgen -G '/sys/class/bluetooth/hci*' >/dev/null && HW_BLUETOOTH=1
    HW_WIFI=0; compgen -G '/sys/class/net/*/wireless' >/dev/null && HW_WIFI=1
    HW_WEBCAM=0; compgen -G '/dev/video*' >/dev/null && HW_WEBCAM=1
    HW_BTRFS=0; [ "$(findmnt -no FSTYPE / 2>/dev/null)" = btrfs ] && HW_BTRFS=1

    # Intel HD audio controller (PCI class 0x0403, vendor 0x8086): newer ones need SOF firmware.
    HW_SOF=0
    local d
    for d in /sys/bus/pci/devices/*; do
        case "$(cat "$d/class" 2>/dev/null)" in 0x0401*|0x0403*) ;; *) continue ;; esac; [ "$(cat "$d/vendor" 2>/dev/null)" = 0x8086 ] && HW_SOF=1
    done

    # A touchpad on the I2C bus is the kind that can stall until its driver is reloaded (docs/modules/touchpad.md).
    HW_TOUCHPAD=0; HW_TOUCHPAD_I2C=0
    if grep -qi 'touchpad' /proc/bus/input/devices 2>/dev/null; then
        HW_TOUCHPAD=1
        awk 'BEGIN{RS="";IGNORECASE=1} /touchpad/ && /Sysfs=[^\n]*i2c/ {f=1} END{exit !f}' /proc/bus/input/devices && HW_TOUCHPAD_I2C=1
    fi
    HW_KERNEL=$(uname -r)
    # Intel hybrid CPUs from Meteor Lake (Core Ultra, family 6 model 170/172/189/197/198) can use intel-lpmd.
    HW_LPMD=0
    if [ "$HW_CPU" = intel ]; then
        case "$(awk -F': *' '/^model\s*:/{print $2; exit}' /proc/cpuinfo)" in 170|172|189|197|198|204) HW_LPMD=1 ;; esac
    fi
}

print_hardware() {
    local yn=(no yes)
    printf '    %-22s %s\n' "CPU" "$HW_CPU_MODEL ($HW_CPU)"
    printf '    %-22s %s\n' "GPU" "${HW_GPUS[*]:-none found}"
    printf '    %-22s %s\n' "Laptop (battery)" "${yn[$HW_LAPTOP]}"
    printf '    %-22s %s\n' "Wi-Fi / Bluetooth" "${yn[$HW_WIFI]} / ${yn[$HW_BLUETOOTH]}"
    printf '    %-22s %s\n' "Webcam" "${yn[$HW_WEBCAM]}"
    printf '    %-22s %s\n' "Touchpad" "${yn[$HW_TOUCHPAD]}$([ "$HW_TOUCHPAD_I2C" = 1 ] && echo " (I2C)")"
    printf '    %-22s %s\n' "btrfs root" "${yn[$HW_BTRFS]}"
    printf '    %-22s %s\n' "Intel audio (SOF)" "${yn[$HW_SOF]}"
}
