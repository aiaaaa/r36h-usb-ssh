# Troubleshooting

## No USB interface appears on the Mac

Use the OTG/data port, keep the handheld awake, and use a known data cable. Start with the documented Mac-side host-adapter path; a charging sound is not proof of USB data enumeration. Check System Information → USB, then run `bash host/macos-network.sh --show`.

On the device, from a local terminal if SSH is unavailable:

```sh
uname -r
sudo systemctl status r36h-usb-ssh.service --no-pager
cat /proc/device-tree/usb@ff300000/dr_mode
ls /sys/class/udc
ip -br address
```

Read `ports/r36h-usb-ssh/install.log` from the SD card after a normal shutdown if needed. `active (exited)` is normal for this oneshot service, but it does not prove the physical cable is attached. A different gadget module/configfs owner is deliberately rejected. Do not unload an unrelated gadget blindly.

## Interface exists, but ping/SSH times out

There is no DHCP server. Run `bash host/macos-network.sh --configure`; the host must be `.1`, not the device's `.2`, with mask `255.255.255.252`. Then:

```sh
ping -c 3 192.168.36.2
route -n get 192.168.36.2
ssh -vv -i ~/.ssh/r36h_usb -o IdentitiesOnly=yes ark@192.168.36.2
```

The route should use the identified USB interface. A VPN or another network using this subnet may conflict. Inspect the route; do not change Wi-Fi/default gateway settings to compensate. The helper refuses conflicting addresses rather than replacing them. Only one device with these default MAC/IP values should be attached.

## SSH connection refused

The network may be up but the existing SSH daemon is not listening. On the device:

```sh
sudo sshd -t
sudo systemctl status ssh.service --no-pager
sudo systemctl start ssh.service
```

The installer does not download OpenSSH, unmask blocked units, change daemon policies, or replace host keys. Missing components require OS-specific administration before installing this package.

## Authentication or host-key failure

Use the private key matching the `.pub` staged on the card, the correct account, and host address `192.168.36.1`. The newly added rule restricts that key to that source address. Check home/`.ssh`/`authorized_keys` ownership and permissions if the server rejects a valid key.

Compare the first server fingerprint with the installer output or SD log. After a deliberate reinstall, verify the new fingerprint before changing the specific known-hosts entry. Never disable host-key checking or import someone else's server/private keys.

## Link disappears after reconnect

Check physical enumeration again and rerun the host address helper if its runtime alias was lost. Wake the handheld. If a freshly booted device has the correct USB settings but still disconnects, capture `dmesg` and available service logs; do not repeatedly rewrite the SD card or modify unrelated boot settings. The recovered setup does not establish reliable suspend/resume or every cable/adapter combination.

## Ports installer missing or startup fails

Confirm the launcher is directly under `EASYROMS/ports`, beside the `r36h-usb-ssh` folder. Refresh/restart the frontend normally if it has not rescanned Ports. Run the launcher once; check its log. The device's runtime tree must reflect the patched active DTB, which requires a reboot after SD preparation.

Some images do not retain system journals across reboot. If available, `sudo journalctl -u r36h-usb-ssh.service -b --no-pager` helps; absence of a journal is not proof the service did not run. Capture errors before restarting.

## Installer refuses existing or changed files

This is intentional. A service installed by another tool is not adopted automatically. Review its setup rather than overwriting it. Repeating this package's unchanged install is safe. If its managed files have since changed, preserve those changes and reconcile them before uninstalling. Do not delete the rollback state to force an overwrite.

SD preparation stores the original DTB before staging files. On a preparation failure it attempts to restore that original, removes completed staged files, and retains the backup for review. If the card disconnected during rollback, inspect the files before booting. A successful `--restore` marks the backup restored; archive that backup directory before a new preparation.

## SCP/SFTP or rsync fails while SSH works

These depend on the existing server's subsystem/tools. Check SFTP configuration and whether `rsync` is installed on both ends. Do not assume a new firmware includes them. Shell-stream transfer remains available, for example:

```sh
ssh r36h 'cat /etc/os-release' > device-os-release.txt
```
