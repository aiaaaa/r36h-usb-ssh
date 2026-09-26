# Validation and compatibility

## VERIFIED on the recovered physical setup

- R36H running ArkOS R35S–R36S v2.0_11072025 MultiPanel, selected Panel 4, aarch64, kernel `4.4.189`.
- The three USB device-tree settings listed in architecture.md, `g_ether use_eem=0`, stable MAC addresses and static `/30` peer addresses.
- macOS host enumeration using CDC Ethernet; ordinary SSH with Ed25519 user-key authentication and checked host identity.
- Repeated remote commands and file transfers through SSH streams, including multi-gigabyte transfers verified by hashes.
- A systemd boot service with the same network initialization sequence. A frontend launcher was used to install/start it.

This verifies the recovered mechanism, not every new packaging wrapper. No claim is made that the link survives all suspend/reconnect conditions; an observed loss of USB enumeration required recovery, and its cause was not established.

## Locally validated for this package

The accompanying test suite checks FDT semantic preservation and idempotence, full SD prepare/restore in temporary directories, checksum refusal after an unrelated DTB change, installer idempotence, exact authorization rollback, preservation of subsequently added keys, refusal of unmanaged files, and rollback after a simulated service-start failure. Services, kernel checks and root ownership are mocked in these tests.

During packaging, the DTB editor was also run against local copies of the known-working device DTB and an earlier reference already containing the controller/PHY-enable changes. The working tree required no changes; the earlier reference gained the missing VBUS property and matched the working tree semantically, checked with an independent property reader. All three changes are exercised by the synthetic tests. A separate stock DTB kept its own unrelated properties and was not treated as interchangeable with the selected panel. No device DTB files are distributed.

Shell syntax and Python syntax are checked. Public package contents are scanned for private keys, bundled public identities, personal paths/names, credentials, firmware/ROM/BIOS assets, binaries, logs, caches, and unrelated artifacts. There is no inherited Git history or remote configuration.

## Final physical acceptance still required

Use a backed-up working installation; do not claim these steps passed until someone performs them:

1. Prepare with a newly generated user key; reboot and launch Ports → R36H USB SSH.
2. Verify the new generic USB serial/product is recognized and the MAC-based host helper selects the right interface.
3. Match the server fingerprint, connect, run `uname -r`, transfer a small file both ways, and compare its hash. Test SCP/SFTP and rsync only if their existing components are present.
4. Reboot the handheld and reconnect once; verify service startup and reapply the host address if necessary.
5. Repeat installation and verify no duplicate key or overwritten settings.
6. Uninstall, shut down, restore the SD backup, and verify normal boot and original USB role.

## Deliberately unclaimed

- Windows support or a Windows driver package.
- Linux host installation/testing, other macOS releases, and every adapter/cable topology.
- Other handheld models, R36H clones, other kernels/distributions, or untested panel variants. Expected-node checks reduce accidental edits; they do not prove hardware compatibility.
- New driver functionality, reliable sleep/wake recovery, DHCP, automatic Internet sharing, remote desktop, or USB mass storage.

Other hosts may support CDC Ethernet and OpenSSH, but that is **INFERRED compatibility**, not tested support. The installer rejects a different kernel/architecture instead of presenting it as supported.
