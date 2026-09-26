#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
command -v python3 >/dev/null || { echo 'Install Python 3 first; see README.md.'; exit 1; }
printf 'R36H USB SSH — prepare a cleanly shut-down ArkOS SD card\n'
printf 'Requires a working R36H / supported ArkOS installation. Read README first.\n'
read -r -p 'BOOT volume path [/Volumes/BOOT]: ' boot
read -r -p 'EASYROMS volume path [/Volumes/EASYROMS]: ' roms
boot=${boot:-/Volumes/BOOT}
roms=${roms:-/Volumes/EASYROMS}
key="$HOME/.ssh/r36h_usb"
if [ ! -f "$key.pub" ]; then
    if [ -e "$key" ]; then
        echo 'Private key exists but its .pub file is missing. See README; nothing overwritten.'; exit 1
    fi
    mkdir -p "$HOME/.ssh"
    echo 'Create your own SSH key. ssh-keygen will ask for a passphrase.'
    ssh-keygen -t ed25519 -f "$key" -C r36h-usb-ssh
fi
python3 host/prepare_sd.py --boot "$boot" --roms "$roms" --public-key "$key.pub"
read -r -p 'Apply these changes to this card? Type YES: ' answer
[ "$answer" = YES ] || { echo 'Cancelled; no card files changed.'; exit 0; }
python3 host/prepare_sd.py --boot "$boot" --roms "$roms" --public-key "$key.pub" --apply
printf '\nSafely eject the whole SD card, boot the handheld, then open Ports > R36H USB SSH.\n'
read -r -p 'Press Return to close.' answer
