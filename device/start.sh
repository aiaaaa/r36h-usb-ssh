#!/bin/bash
set -euo pipefail
exec 9>/run/r36h-usb-ssh.lock
flock -w 10 9
fail() { printf '%s\n' "$*" >&2; exit 1; }
[ "$(uname -r)" = 4.4.189 ] || fail 'This release requires kernel 4.4.189.'
tree=/proc/device-tree
phy="$tree/syscon@ff2c0000/usb2-phy@100/otg-port"
[ "$(tr -d '\000' < "$tree/usb@ff300000/dr_mode")" = peripheral ] || fail 'USB controller is not in peripheral mode.'
[ "$(tr -d '\000' < "$phy/status")" = okay ] || fail 'OTG PHY is not enabled.'
[ -f "$phy/rockchip,vbus-always-on" ] || fail 'Required OTG VBUS property is absent.'
for path in /sys/module/g_*; do
    [ -d "$path" ] || continue
    [ "${path##*/}" = g_ether ] || fail "Another gadget module is loaded: ${path##*/}"
done
for path in /sys/kernel/config/usb_gadget/*/UDC; do
    [ -f "$path" ] || continue
    [ -z "$(cat "$path")" ] || fail 'A configfs USB gadget is already bound.'
done
if [ -d /sys/module/g_ether ]; then
    [ "$(cat /sys/module/g_ether/parameters/dev_addr)" = 02:36:48:00:00:02 ] || fail 'Existing g_ether has another device MAC.'
    [ "$(cat /sys/module/g_ether/parameters/host_addr)" = 02:36:48:00:00:01 ] || fail 'Existing g_ether has another host MAC.'
    [ "$(cat /sys/module/g_ether/parameters/iSerialNumber)" = R36H-USB-SSH ] || fail 'Existing g_ether belongs to another setup; it was left untouched.'
fi
modprobe g_ether use_eem=0 dev_addr=02:36:48:00:00:02 host_addr=02:36:48:00:00:01 iSerialNumber=R36H-USB-SSH iProduct='R36H USB SSH'
iface=''
for attempt in {1..30}; do
    for path in /sys/class/net/*; do
        if [ "$(cat "$path/address")" = 02:36:48:00:00:02 ]; then iface=${path##*/}; break; fi
    done
    [ -z "$iface" ] || break
    sleep .2
done
[ -n "$iface" ] || fail 'USB Ethernet interface did not appear.'
ip address replace 192.168.36.2/30 dev "$iface"
ip link set "$iface" up
printf 'USB network configured on %s: 192.168.36.2/30\n' "$iface"
