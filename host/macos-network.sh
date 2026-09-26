#!/bin/bash
# Temporary host address only. No gateway, DNS, or persistent profile changes.
set -euo pipefail
[ "$(uname -s)" = Darwin ] || { echo 'This helper is for macOS.' >&2; exit 1; }
action=${1:---show}
case "$action" in --show|--configure|--clear) ;; *) echo 'Usage: bash host/macos-network.sh [--show|--configure|--clear]' >&2; exit 2;; esac
matches=()
for iface in $(/sbin/ifconfig -l); do
    mac=$(/sbin/ifconfig "$iface" | awk '/^[[:space:]]*ether / {print tolower($2)}')
    [ "$mac" != 02:36:48:00:00:01 ] || matches+=("$iface")
done
[ "${#matches[@]}" -eq 1 ] || { echo "Expected one R36H USB Ethernet interface; found ${#matches[@]}. Check power, data cable, OTG port and device service." >&2; exit 1; }
iface=${matches[0]}
printf 'R36H USB interface: %s (02:36:48:00:00:01)\n' "$iface"
case "$action" in
    --configure)
        for other in $(/sbin/ifconfig -l); do
            [ "$other" = "$iface" ] && continue
            if /sbin/ifconfig "$other" | awk '/^[[:space:]]*inet / {print $2}' | grep -qx 192.168.36.1; then
                echo "192.168.36.1 already exists on $other; no change made." >&2; exit 1
            fi
        done
        existing=$(/sbin/ifconfig "$iface" | awk '/^[[:space:]]*inet / {print $2}')
        for addr in $existing; do
            case "$addr" in 192.168.36.1|169.254.*) ;; *) echo "Interface has another IPv4 address ($addr); inspect it first." >&2; exit 1;; esac
        done
        # Add our address as an alias; retain any existing link-local address.
        sudo /sbin/ifconfig "$iface" inet 192.168.36.1 netmask 255.255.255.252 alias
        sudo /sbin/ifconfig "$iface" up
        ;;
    --clear)
        if /sbin/ifconfig "$iface" | awk '/^[[:space:]]*inet / {print $2}' | grep -qx 192.168.36.1; then
            sudo /sbin/ifconfig "$iface" inet 192.168.36.1 -alias
        fi
        ;;
esac
/sbin/ifconfig "$iface"
[ "$action" != --configure ] || printf '\nConnect: ssh -i ~/.ssh/r36h_usb ark@192.168.36.2\n'
