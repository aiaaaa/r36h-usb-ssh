#!/bin/bash
set -euo pipefail
base="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/r36h-usb-ssh"
if sudo -n python3 "$base/install.py" --key "$base/user.pub" 2>&1 | tee "$base/install.log"; then
    printf '\nUSB SSH is ready. Host address: 192.168.36.1/30\n'
else
    printf '\nSetup stopped. Details are in ports/r36h-usb-ssh/install.log\n'
fi
sleep 8
