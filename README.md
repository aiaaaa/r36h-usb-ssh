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


