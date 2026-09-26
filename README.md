# r36h-usb-ssh
USB networking and SSH access for the r36h linux handheld

rev0.01

The stock r36h device is only provided with inbound usb likages (host)... to connect a game controller or wifi dongle

I did not have a wifi dongle, and simply wanted to plug the r636h into a computer as a client and control the device via SSH

This repo will set up the r36h to establish a wired ssh connection just with a few modifications to a r36h SD card. (currently mac only but the process here could be easily adapted)

# Purpose

The stock r36h device is only provided with inbound usb likages (host)... to connect a game controller or wifi dongle

I did not have a wifi dongle, and simply wanted to plug the r636h into a computer as a client and control the device via SSH

This repo will set up the r36h to establish a wired ssh connection just with a few modifications to a r36h SD card. (currently mac only but the process here could be easily adapted)


# R36H USB SSH Technicals 

USB networking and SSH access for the R36H handheld, enabling direct shell access, file transfer, scripting, and device control without Wi-Fi.

The R36H can be inconvenient to administer without a network. This utility gives it a direct USB Ethernet connection to a computer and uses its existing OpenSSH server. There is no remote desktop, new USB stack, or replacement operating system.

**Status:** the underlying connection worked on a physical R36H with ArkOS, kernel `4.4.189`, and macOS. This standalone installer has local automated validation; a fresh install/reboot/uninstall cycle on another card is still required. See [validation and compatibility](docs/validation.md).
