#!/usr/bin/env python3
"""Prepare mounted BOOT/EASYROMS volumes; never flash or access a raw disk."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
from dtb import patch

PACKAGE = Path(__file__).resolve().parent.parent
BACKUP = '.r36h-usb-ssh-backup'
LAUNCHER = 'R36H USB SSH.sh'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data, mode=0o644):
    temp = path.with_name(path.name+'.r36h-tmp')
    with temp.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.chmod(str(temp), mode)
    os.replace(str(temp), str(path))
    if path.read_bytes() != data:
        raise IOError('Readback mismatch: '+str(path))


def public_key(path):
    fields = path.read_text().strip().split()
    if len(fields) < 2 or fields[0] != 'ssh-ed25519':
        raise ValueError('Supply your own Ed25519 PUBLIC .pub file, not a private key')
    raw = base64.b64decode(fields[1], validate=True)
    if len(raw) != 51 or raw[:19] != b'\0\0\0\x0bssh-ed25519\0\0\0\x20':
        raise ValueError('Invalid Ed25519 public key')
    return (fields[0]+' '+fields[1]+' r36h-usb-ssh\n').encode()


def media_check(boot, roms):
    if sys.platform != 'darwin':
        raise ValueError('The SD preparation CLI currently supports macOS only')
    def info(p):
        return plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(p)]))
    b, r = info(boot), info(roms)
    if b.get('ParentWholeDisk') != r.get('ParentWholeDisk') or b.get('DeviceIdentifier') == r.get('DeviceIdentifier'):
        raise ValueError('BOOT and EASYROMS must be different partitions of the same card')
    d = info('/dev/'+b['ParentWholeDisk'])
    if d.get('Internal') or d.get('VirtualOrPhysical') != 'Physical':
        raise ValueError('Expected an external physical SD card')
    if b.get('FilesystemType') != 'msdos' or r.get('FilesystemType') != 'exfat':
        raise ValueError('Expected FAT BOOT and exFAT EASYROMS; complete ArkOS first boot first')
    if Path(b.get('MountPoint','')).resolve() != boot or Path(r.get('MountPoint','')).resolve() != roms:
        raise ValueError('Use volume roots, not subfolders')
    return '/dev/'+b['ParentWholeDisk']


def active_dtb(boot):
    matches = re.findall(r'^\s*load\s+mmc\s+\S+\s+\$\{dtb_loadaddr\}\s+([\w.-]+\.dtb)\s*$',
                         (boot/'boot.ini').read_text(), re.M)
    if len(matches) != 1:
        raise ValueError('Cannot identify one active DTB in boot.ini; no files changed')
    target = boot/matches[0]
    if target.is_symlink() or not target.is_file():
        raise ValueError('Active DTB is missing or a symlink')
    return target


def payload(key):
    result = {LAUNCHER: (PACKAGE/'device'/LAUNCHER).read_bytes()}
    for name in ['install.py','start.sh','r36h-usb-ssh.service']:
        result['r36h-usb-ssh/'+name] = (PACKAGE/'device'/name).read_bytes()
    result['r36h-usb-ssh/user.pub'] = key
    return result


def prepare(boot, roms, keyfile, apply=False):
    ports = roms/'ports'
    if not ports.is_dir() or ports.is_symlink():
        raise ValueError('EASYROMS/ports is absent or a symlink')
    target = active_dtb(boot)
    original = target.read_bytes()
    patched, changes = patch(original)
    files = payload(public_key(keyfile))
    backup = boot/BACKUP
    manifest_path = backup/'manifest.json'
    if backup.is_symlink():
        raise ValueError('Backup directory must not be a symlink')
    if backup.exists():
        m = json.loads(manifest_path.read_text())
        if (m.get('restored') or m['dtb'] != target.name or sha(original) != m['patched_sha256'] or
                m['files'] != {k:sha(v) for k,v in files.items()} or
                sha((backup/'original.dtb').read_bytes()) != m['original_sha256']):
            raise ValueError('Existing preparation differs; restore/review its backup before proceeding')
        for name, data in files.items():
            if (ports/name).is_symlink() or (ports/name).read_bytes() != data:
                raise ValueError('Previously staged file changed: '+name)
        print('Already prepared; files and patched DTB match. No changes made.')
        return
    for name in files:
        if (ports/name).exists() or (ports/name).is_symlink():
            raise ValueError('Refusing to overwrite existing file: '+name)
    if (ports/'r36h-usb-ssh').exists():
        raise ValueError('Staging directory already exists; inspect before proceeding')
    print('Active DTB:', target.name)
    print('USB property changes:', ', '.join(changes) or 'already configured')
    print('Will stage the Ports installer and your public key; no firmware/driver replacement.')
    if not apply:
        print('Inspection only. Add --apply to write these changes.')
        return
    backup.mkdir()
    atomic(backup/'original.dtb', original)
    m = {'dtb':target.name,'original_sha256':sha(original),'patched_sha256':sha(patched),
         'changes':changes,'files':{k:sha(v) for k,v in files.items()},'restored':False}
    atomic(manifest_path, (json.dumps(m,indent=2)+'\n').encode())
    created = []
    try:
        (ports/'r36h-usb-ssh').mkdir()
        for name, data in files.items():
            path = ports/name
            atomic(path,data,0o755 if path.suffix in ('.py','.sh') else 0o644)
            created.append(path)
        if patched != original:
            atomic(target,patched)
    except Exception:
        if target.read_bytes() != original:
            atomic(target,original)
        for path in reversed(created):
            path.unlink()
        try: (ports/'r36h-usb-ssh').rmdir()
        except OSError: pass
        m['restored'] = True
        atomic(manifest_path,(json.dumps(m,indent=2)+'\n').encode())
        print('Preparation failed; original DTB restored. Backup retained for inspection.',file=sys.stderr)
        raise
    print('Prepared and read back successfully. Safely eject the whole card before removing it.')


def restore(boot, roms):
    backup = boot/BACKUP
    if backup.is_symlink():
        raise ValueError('Backup directory must not be a symlink')
    m = json.loads((backup/'manifest.json').read_text())
    target = active_dtb(boot)
    names = {LAUNCHER,'r36h-usb-ssh/install.py','r36h-usb-ssh/start.sh',
             'r36h-usb-ssh/r36h-usb-ssh.service','r36h-usb-ssh/user.pub'}
    if m['dtb'] != target.name or set(m['files']) != names:
        raise ValueError('Unexpected backup manifest paths; no changes made')
    if (roms/'ports'/'r36h-usb-ssh').is_symlink():
        raise ValueError('Staging directory became a symlink')
    original = (backup/'original.dtb').read_bytes()
    if sha(original) != m['original_sha256']:
        raise ValueError('Original DTB backup checksum mismatch')
    if m.get('restored'):
        if sha(target.read_bytes()) != m['original_sha256']:
            raise ValueError('DTB changed after restore; inspect manually')
        print('Already restored.'); return
    if sha(target.read_bytes()) != m['patched_sha256']:
        raise ValueError('Active DTB changed after preparation; refusing to overwrite it')
    for name, digest in m['files'].items():
        p = roms/'ports'/name
        if p.is_symlink() or not p.is_file() or sha(p.read_bytes()) != digest:
            raise ValueError('Staged file changed; preserve/review it before restoring: '+name)
    atomic(target,original)
    for name in m['files']:
        (roms/'ports'/name).unlink()
    try:
        (roms/'ports'/'r36h-usb-ssh').rmdir()
    except OSError:
        print('Runtime logs retained in EASYROMS/ports/r36h-usb-ssh.')
    m['restored'] = True
    atomic(backup/'manifest.json',(json.dumps(m,indent=2)+'\n').encode())
    print('Original DTB restored exactly; staged package files removed. Backup retained.')
    print('This does not uninstall the Linux service; run device uninstall before SD restore.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot',type=Path,required=True)
    p.add_argument('--roms',type=Path,required=True)
    p.add_argument('--public-key',type=Path)
    action=p.add_mutually_exclusive_group()
    action.add_argument('--apply',action='store_true')
    action.add_argument('--restore',action='store_true')
    a=p.parse_args(); boot=a.boot.resolve(); roms=a.roms.resolve()
    disk=media_check(boot,roms)
    print('Confirmed card:',disk)
    if a.restore:
        restore(boot,roms)
    else:
        if a.public_key is None:
            p.error('--public-key is required for inspection/preparation')
        prepare(boot,roms,a.public_key.expanduser(),a.apply)
    if a.apply or a.restore:
        subprocess.run(['sync'],check=True)
        print('Safe eject command: diskutil eject '+disk)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        sys.exit('Stopped: '+str(e))
