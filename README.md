# r36h-usb-ssh
USB networking and SSH access for the r36h linux handheld

rev0.01

# Purpose

The stock r36h device is only provided with inbound usb likages (host)... to connect a game controller or wifi dongle

I did not have a wifi dongle, and simply wanted to plug the r636h into a computer as a client and control the device via SSH

This repo will set up the r36h to establish a wired ssh connection just with a few modifications to a r36h SD card. (currently mac only but the process here could be easily adapted)


# R36H USB SSH Technicals 

USB networking and SSH access for the R36H handheld, enabling direct shell access, file transfer, scripting, and device control without Wi-Fi.

The R36H can be inconvenient to administer without a network. This utility gives it a direct USB Ethernet connection to a computer and uses its existing OpenSSH server. There is no remote desktop, new USB stack, or replacement operating system.

**Status:** the underlying connection worked on a physical R36H with ArkOS, kernel `4.4.189`, and macOS. This standalone installer has local automated validation; a fresh install/reboot/uninstall cycle on another card is recommended. See [validation and compatibility](docs/validation.md).

## What you need

- An R36H that already boots correctly. The tested installation was **ArkOS R35S–R36S v2.0_11072025 MultiPanel**, aarch64, kernel **4.4.189**, using Panel 4. Finish first-boot setup before preparing the card.
- The original OS/system SD card, a reliable reader, and a recommend a backup. Preparation modifies three USB properties in its active DTB; it does not affect other settings.
- The handheld's **OTG/data port** and a data-capable cable. The proven connection path was a Mac USB-C port → USB-C-to-USB-A host adapter → USB-A-to-USB-C data cable → handheld OTG port. Direct C-to-C operation is not established.
- A Mac with Python 3 and the standard `ssh`/`ssh-keygen` tools. 
- On the device: Python 3, systemd, OpenSSH server and existing host keys, `g_ether`, `ip`, `flock`, `modprobe`, and an existing non-root account. The tested ArkOS account is `ark`; Ports installation assumes its normal passwordless `sudo` access.

Only connect **one handheld using these defaults at a time**. This release uses fixed locally administered MAC addresses and a fixed `/30` network. It does not install DHCP, routing, Internet sharing, or DNS.

## Easiest installation: prepare the SD card

1. Shut down through the handheld's menu and insert the system SD card into the Mac. Both **BOOT** and **EASYROMS** should mount; the Linux partition normally will not appear in Finder.
2. Open **`Prepare SD Card.command`** from this folder. If Finder does not execute it, run `bash "Prepare SD Card.command"` in Terminal from the repository folder.
3. Confirm the two volume paths. The helper creates your own Ed25519 key at `~/.ssh/r36h_usb` if it does not already exist. Choose a passphrase when prompted. **The private key stays on the Mac.**
4. Review the identified card, active DTB, and proposed USB changes, then type `YES` to apply. It backs up the original DTB and stages a small Ports installer plus your public key. It refuses unknown layouts and conflicting files.
5. Safely eject the **whole SD card** with Finder or the exact `diskutil eject` command printed by the tool. Put it back into the handheld and boot.
6. Open **Ports → R36H USB SSH** once. It installs the service, adds your public key, and shows server-key fingerprints. It returns to the menu after eight seconds; output is also in `EASYROMS/ports/r36h-usb-ssh/install.log`.

Exact changes and rollback behavior are documented in [architecture](docs/architecture.md). The installer uses the device's kernel module and patches **your existing active DTB**. 

### Terminal equivalent

Run from this repository's directory. Do not overwrite an existing key:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/r36h_usb -C r36h-usb-ssh
python3 host/prepare_sd.py --boot /Volumes/BOOT --roms /Volumes/EASYROMS \
  --public-key ~/.ssh/r36h_usb.pub
# After reviewing the inspection output:
python3 host/prepare_sd.py --boot /Volumes/BOOT --roms /Volumes/EASYROMS \
  --public-key ~/.ssh/r36h_usb.pub --apply
```

If a private key already exists but its `.pub` file is missing, recover it with `ssh-keygen -y -f ~/.ssh/r36h_usb > ~/.ssh/r36h_usb.pub` instead of generating a replacement. Quote volume paths containing spaces. Always use the printed card identifier for ejection; do not assume a disk number.

## Connect the Mac

Boot the handheld and connect its OTG/data port. The device service loads automatically after installation. From the repository folder:

```sh
bash host/macos-network.sh --show
bash host/macos-network.sh --configure
ssh -i ~/.ssh/r36h_usb -o IdentitiesOnly=yes ark@192.168.36.2
```

The helper identifies the interface by **MAC address**, not an assumed `en` number, and adds the temporary host address **192.168.36.1/30**. The handheld is **192.168.36.2/30**. Your normal gateway/DNS remain untouched. Run the helper again after a reconnect or Mac restart if the address is lost.

At the first SSH prompt, compare the server fingerprint with the installer output or its SD-card log. Do not bypass host-key checking. If you missed the fingerprint, shut down normally and read that log from the SD card. No known-hosts file or server identity is distributed here.

For a persistent Mac network profile, set the **USB Ethernet service only** to manual IPv4 `192.168.36.1`, mask `255.255.255.252`, with no router or DNS. Record its previous settings first. Follow [Apple's TCP/IP settings instructions](https://support.apple.com/guide/mac-help/mh14129/mac). The included helper changes only runtime interface addressing.

### Optional SSH alias

Add this block to your own `~/.ssh/config` (do not replace the file):

```sshconfig
Host r36h
    HostName 192.168.36.2
    User ark
    IdentityFile ~/.ssh/r36h_usb
    IdentitiesOnly yes
```

Then use ordinary tools:

```sh
ssh r36h
ssh r36h 'uptime; uname -r'
ssh r36h 'ps -ef'
ssh r36h 'dmesg | tail -n 50' > kernel-tail.txt
ssh r36h 'sh -s' < ./your-script.sh
```

Use the username you installed for if it differs from `ark`. Standard SSH command execution and shell-stream file transfer are part of the recovered working setup. These additional recipes require the usual server/client components and remain fresh-install acceptance checks:

```sh
scp ./file.txt r36h:/tmp/file.txt
scp r36h:/tmp/file.txt ./file-from-device.txt
sftp r36h
rsync -av ./directory/ r36h:/home/ark/directory/
```

Current `scp` clients normally use SFTP; its subsystem must be enabled in the existing SSH server. `rsync` must be installed at both ends. Neither component is downloaded or configured by this package. The installed key permits shell/file access but disables agent, TCP, and X11 forwarding and restricts that key to source `192.168.36.1`.

## Automatic startup and security

`r36h-usb-ssh.service` is enabled at boot. It runs one small script that checks the expected device tree, loads `g_ether`, finds the device-side interface by MAC, assigns the address, and raises the link. OpenSSH is enabled if previously disabled and started if needed. It does not require the Ports launcher on every boot.

Existing SSH passwords, daemon settings, host keys, and unrelated authorized keys are preserved. **The SSH server's existing listening and password policies still apply to other interfaces.** This package does not claim to confine the entire SSH server to USB. If the chosen public key already exists, its existing authorization rule is kept rather than silently narrowed. Keep your private key private and do not publish prepared SD-card logs or state as repository files.

## Uninstall / restore

1. On the running device (over SSH or a local terminal), remove the managed service and key:

   ```sh
   sudo python3 /roms/ports/r36h-usb-ssh/install.py --uninstall
   ```

   This restores the SSH service's pre-install enabled/running state. It can close access if SSH was previously stopped. It preserves other keys and refuses to delete changed managed files. An empty `.ssh` directory may remain. USB module/address state remains until reboot.

2. Shut down normally, put the card into the Mac, and restore the original DTB and remove the staged installer:

   ```sh
   python3 host/prepare_sd.py --boot /Volumes/BOOT --roms /Volumes/EASYROMS --restore
   ```

   This requires the current DTB and staged files to match the recorded versions; it will not overwrite a later OS/panel change. The original backup is retained in `BOOT/.r36h-usb-ssh-backup`. Runtime logs may remain in `EASYROMS/ports/r36h-usb-ssh`. After a completed restore, archive the backup directory before preparing that card again.

3. Safely eject the card and boot. The original USB role is restored. On the Mac, `bash host/macos-network.sh --clear` removes the helper's runtime address while the interface is attached. If you created a persistent network profile, restore its recorded settings manually. Remove only the SSH alias/key you no longer need; this package never deletes your host keys or private key.

No remote repository is created or contacted by these tools. For installation problems, use [troubleshooting](docs/troubleshooting.md). For exactly what was tested and what remains, see [validation](docs/validation.md).

## Developer Checks

These will print results in the terminal

```sh
python3 -m unittest discover -s tests -v
for script in "Prepare SD Card.command" device/start.sh "device/R36H USB SSH.sh" host/macos-network.sh; do
  bash -n "$script" || break
done
```
## License

The tests use temporary files and mocked system services. They do not touch a connected SD card, load a USB driver, or change the host network. Software is MIT licensed; the OS's existing kernel modules retain their own licenses and are not included.
