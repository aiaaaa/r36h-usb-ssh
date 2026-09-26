# Architecture and persistent changes

```text
Mac 192.168.36.1/30
        |
        | USB CDC Ethernet (ECM)
        |
R36H 192.168.36.2/30 -> existing OpenSSH -> shell / commands / files
```

## Recovered working values

| Item | Value | Evidence status |
|---|---|---|
| Device | R36H, RK3326, aarch64 | VERIFIED on physical device |
| OS | ArkOS R35S–R36S v2.0_11072025 MultiPanel, Panel 4 | VERIFIED |
| Kernel / UDC | `4.4.189` / `ff300000.usb` | VERIFIED |
| Gadget | Kernel `g_ether`, `use_eem=0`, ECM selected by macOS | VERIFIED |
| Device MAC | `02:36:48:00:00:02` | VERIFIED |
| Host MAC | `02:36:48:00:00:01` | VERIFIED |
| Device IP | `192.168.36.2/30` | VERIFIED |
| Host IP | `192.168.36.1/30`, mask `255.255.255.252` | VERIFIED |
| Device interface | Located by MAC; usually `usb0` | MAC-based selection VERIFIED; name is not assumed |
| SSH | Existing OpenSSH, account `ark`, supplied Ed25519 public key | VERIFIED |
| Boot integration | systemd oneshot, enabled for multi-user target | VERIFIED |
| New public USB identity | product `R36H USB SSH`, serial `R36H-USB-SSH` | PACKAGED; new serial still needs physical acceptance |
| Public installer / rollback | guarded scripts in this repository | LOCALLY TESTED; physical cycle pending |

The exact USB ID observed in the working setup was `0525:a4a2`; macOS selected CDC Ethernet configuration 1. The Linux `g_ether` build may also advertise RNDIS. That does **not** establish Windows support. No configfs networking gadget, CDC-NCM switch, DHCP daemon, or foreign `.ko` file is introduced.

## Three boot changes

The SD helper reads `boot.ini` to find its one active `.dtb` and edits these properties:

| DT path | Property | Required value |
|---|---|---|
| `/usb@ff300000` | `dr_mode` | string `peripheral` |
| `/syscon@ff2c0000/usb2-phy@100/otg-port` | `status` | string `okay` |
| same OTG PHY node | `rockchip,vbus-always-on` | present, empty boolean |

The first forces device mode, the second enables the OTG PHY, and the third is a board/kernel-specific PHY setting present in the successful connection. These are not claimed as universal settings for other boards. Peripheral mode dedicates that port to being a USB device; normal USB host accessory behavior on that port is not retained while using this configuration.

The editor requires an RK3326 FDT v17 layout and the expected nodes/properties. It verifies that every unrelated node, property, and memory-reservation byte is preserved. It does not alter `boot.ini`, screen selection, kernel, initrd, or the other DTBs. Its backup contains the exact original bytes and before/after SHA-256 values. A panel switch or OS update can select/replace the DTB; re-inspect rather than blindly applying an old file.

## Files created

On the SD card during preparation:

- `BOOT/.r36h-usb-ssh-backup/original.dtb` and `manifest.json`: rollback data generated from that user's card.
- `EASYROMS/ports/R36H USB SSH.sh`: one-time menu entry.
- `EASYROMS/ports/r36h-usb-ssh/`: installer, runtime script, unit, and **that user's public key**. The launcher subsequently writes `install.log`.
- The active BOOT DTB is the only existing boot file modified.

On the running Linux device during installation:

- `/usr/local/sbin/r36h-usb-ssh-start.sh` (root executable).
- `/etc/systemd/system/r36h-usb-ssh.service` and its systemd enable link.
- `/var/lib/r36h-usb-ssh/state.json` (root-only rollback record).
- One marked public-key line in the chosen user's `~/.ssh/authorized_keys`, unless the same key already exists. Existing contents are backed up in the root-only rollback record; uninstall preserves keys added later.
- The existing `ssh.service` is started and enabled if needed. Its original state is recorded. No `sshd_config` edits or server-key replacement occur.

Runtime-only state: loaded `g_ether`, an IPv4 address, an up network link, and a lock in `/run`. The service does not unload another USB gadget or steal its controller. Uninstall leaves this runtime state until reboot to avoid a forced USB disconnect during removal.

On the Mac: the optional preparation shortcut creates a user-owned key under `~/.ssh`, outside the repository. The network helper adds a runtime IPv4 address only. Persistent network profiles and SSH aliases are explicit manual choices.

## Sources

- [Linux 4.4 Ethernet gadget source](https://github.com/torvalds/linux/blob/v4.4/drivers/usb/gadget/legacy/ether.c): `g_ether`, ECM/EEM selection, and optional RNDIS configurations.
- [Rockchip 4.4 USB2 PHY source](https://github.com/rockchip-linux/kernel/blob/develop-4.4/drivers/phy/rockchip/phy-rockchip-inno-usb2.c): `rockchip,vbus-always-on` property handling. This moving branch is explanatory, not a compatibility guarantee for every firmware.
- [Devicetree specifications](https://www.devicetree.org/specifications/): flattened device-tree format.

No code or compiled driver from those projects is redistributed in this package.
