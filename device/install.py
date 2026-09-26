#!/usr/bin/env python3
"""Install/revert the small USB service and one caller-supplied public key."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import shutil
import subprocess
import sys

UNIT = 'r36h-usb-ssh.service'
STATE = '/var/lib/r36h-usb-ssh/state.json'
FILES = {'start.sh':'/usr/local/sbin/r36h-usb-ssh-start.sh',
         UNIT:'/etc/systemd/system/'+UNIT}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data, mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.r36h-tmp')
    with tmp.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.chmod(str(tmp),mode)
    os.replace(str(tmp),str(path))


class System:
    def __init__(self, root=Path('/')):
        self.root=root

    def path(self, p):
        return self.root/p.lstrip('/')

    def run(self, *args, **kwargs):
        check=kwargs.get('check',True)
        p=subprocess.run(list(args),stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        if check and p.returncode:
            raise RuntimeError('Command failed: '+' '.join(args)+'\n'+p.stderr.strip())
        return p.returncode,p.stdout.strip()

    def own(self, path, uid, gid):
        os.chown(str(path),uid,gid)

    def preflight(self, user):
        if os.geteuid()!=0 or platform.system()!='Linux' or platform.machine()!='aarch64' or platform.release()!='4.4.189':
            raise ValueError('Run as root on the supported ArkOS aarch64 / 4.4.189 device')
        for cmd in ['systemctl','modprobe','modinfo','ip','flock','ssh-keygen','sshd']:
            if shutil.which(cmd) is None:
                raise ValueError('Required existing OS tool is missing: '+cmd)
        account=pwd.getpwnam(user)
        if account.pw_uid==0 or not Path(account.pw_dir).is_dir():
            raise ValueError('Choose an existing non-root account with a home directory')
        tree=Path('/proc/device-tree')
        expected={'usb@ff300000/dr_mode':b'peripheral\0',
                  'syscon@ff2c0000/usb2-phy@100/otg-port/status':b'okay\0',
                  'syscon@ff2c0000/usb2-phy@100/otg-port/rockchip,vbus-always-on':b''}
        for name, value in expected.items():
            if not (tree/name).is_file() or (tree/name).read_bytes()!=value:
                raise ValueError('Required runtime DT property missing; prepare BOOT and reboot: '+name)
        self.run('modinfo','g_ether')
        self.run('sshd','-t')
        return account


def load_key(path):
    fields=path.read_text().strip().split()
    if len(fields)<2 or fields[0]!='ssh-ed25519':
        raise ValueError('Expected your own Ed25519 PUBLIC key file')
    raw=base64.b64decode(fields[1],validate=True)
    if len(raw)!=51 or raw[:19]!=b'\0\0\0\x0bssh-ed25519\0\0\0\x20':
        raise ValueError('Invalid public key')
    return fields[0]+' '+fields[1]


def save_state(system, state):
    write(system.path(STATE),(json.dumps(state,indent=2)+'\n').encode())


def fingerprints(system):
    print('Verify these server fingerprints at first connection:')
    for pub in sorted(system.path('/etc/ssh').glob('ssh_host_*_key.pub')):
        print(system.run('ssh-keygen','-lf',str(pub))[1])


def install(system, source, keyfile, user):
    account=system.preflight(user)
    key=load_key(keyfile)
    managed=('from="192.168.36.1",no-agent-forwarding,no-port-forwarding,no-X11-forwarding '+key+' r36h-usb-ssh-managed\n').encode()
    expected={dest:(source/name).read_bytes() for name,dest in FILES.items()}
    statefile=system.path(STATE)
    if statefile.exists():
        state=json.loads(statefile.read_text())
        if state['user']!=user or state['key']!=key or state['phase']!='installed':
            raise ValueError('Existing install differs or is incomplete; uninstall/review before retrying')
        for name, data in expected.items():
            if system.path(name).is_symlink() or system.path(name).read_bytes()!=data:
                raise ValueError('Installed file changed: '+name)
        auth=system.path(state['auth']).read_bytes()
        if not any(key in line for line in auth.decode().splitlines()):
            raise ValueError('Installed public key is absent; inspect authorized_keys')
        system.run('systemctl','start',UNIT)
        system.run('systemctl','start','ssh.service')
        print('Already installed; managed files verified and services started.')
        fingerprints(system)
        return
    for name in expected:
        if system.path(name).exists() or system.path(name).is_symlink():
            raise ValueError('Unmanaged file already exists; refusing to overwrite: '+name)
    _, enabled=system.run('systemctl','is-enabled','ssh.service',check=False)
    if enabled not in ('enabled','disabled','static','indirect','enabled-runtime'):
        raise ValueError('Unsupported SSH service state (not unmasking/changing it): '+enabled)
    active=system.run('systemctl','is-active','--quiet','ssh.service',check=False)[0]==0
    authpath=account.pw_dir+'/.ssh/authorized_keys'
    auth=system.path(authpath)
    if auth.is_symlink() or auth.parent.is_symlink():
        raise ValueError('Symlinked SSH paths require manual installation')
    if auth.parent.exists() and auth.parent.stat().st_mode & 0o022:
        raise ValueError('Existing .ssh directory is writable by another user/group; inspect its permissions')
    old=auth.read_bytes() if auth.exists() else b''
    existed=auth.exists()
    mode=(auth.stat().st_mode&0o777) if existed else 0o600
    key_exists=any(key in line for line in old.decode().splitlines() if not line.lstrip().startswith('#'))
    appended=old if key_exists else old+(b'\n' if old and not old.endswith(b'\n') else b'')+managed
    state={'phase':'installing','user':user,'uid':account.pw_uid,'gid':account.pw_gid,'key':key,
           'auth':authpath,'auth_existed':existed,'auth_mode':mode,
           'auth_uid':auth.stat().st_uid if existed else account.pw_uid,
           'auth_gid':auth.stat().st_gid if existed else account.pw_gid,
           'auth_before':base64.b64encode(old).decode(),'auth_after_sha256':sha(appended),
           'managed_line':managed.decode(),'key_added':not key_exists,
           'ssh_enabled':enabled,'ssh_active':active,
           'files':{name:sha(data) for name,data in expected.items()}}
    save_state(system,state)
    try:
        for name,data in expected.items():
            write(system.path(name),data,0o755 if name.endswith('.sh') else 0o644)
        if not auth.parent.exists():
            auth.parent.mkdir(mode=0o700)
            system.own(auth.parent,account.pw_uid,account.pw_gid)
        if not key_exists:
            write(auth,appended,0o600)
            system.own(auth,account.pw_uid,account.pw_gid)
        system.run('systemctl','daemon-reload')
        if enabled=='disabled':
            system.run('systemctl','enable','ssh.service')
        system.run('systemctl','enable',UNIT)
        system.run('systemctl','restart',UNIT)
        system.run('systemctl','start','ssh.service')
        system.run('systemctl','is-active','--quiet',UNIT)
        system.run('systemctl','is-active','--quiet','ssh.service')
        state['phase']='installed'; save_state(system,state)
    except Exception:
        print('Install failed; reverting managed persistent changes.',file=sys.stderr)
        uninstall(system,rollback=True)
        raise
    print('Installed: '+user+'@192.168.36.2; USB service starts on boot.')
    if key_exists:
        print('That key already existed; its existing authorization rules were preserved.')
    fingerprints(system)
    print('No server private keys, passwords, or SSH daemon policy were replaced.')


def uninstall(system, rollback=False):
    path=system.path(STATE)
    if not path.exists():
        print('No managed installation found. Nothing changed.'); return
    state=json.loads(path.read_text())
    for name,digest in state['files'].items():
        f=system.path(name)
        if f.is_symlink() or (f.exists() and sha(f.read_bytes())!=digest):
            raise ValueError('Managed file changed; refusing to delete: '+name)
    auth=system.path(state['auth'])
    if auth.is_symlink() or auth.parent.is_symlink():
        raise ValueError('SSH path became a symlink; inspect before uninstalling')
    system.run('systemctl','disable','--now',UNIT,check=not rollback)
    for name in state['files']:
        f=system.path(name)
        if f.exists(): f.unlink()
    if state['key_added'] and auth.exists():
        current=auth.read_bytes()
        if sha(current)==state['auth_after_sha256']:
            restored=base64.b64decode(state['auth_before'])
            if not state['auth_existed']:
                auth.unlink()
            else:
                write(auth,restored,state['auth_mode']); system.own(auth,state['auth_uid'],state['auth_gid'])
        else:
            restored=b''.join(line for line in current.splitlines(keepends=True) if line!=state['managed_line'].encode())
            write(auth,restored,auth.stat().st_mode&0o777); system.own(auth,state['uid'],state['gid'])
    system.run('systemctl','daemon-reload')
    if state['ssh_enabled']=='disabled':
        system.run('systemctl','disable','ssh.service')
    if not state['ssh_active']:
        system.run('systemctl','stop','ssh.service')
    path.unlink()
    try: path.parent.rmdir()
    except OSError: pass
    print('Managed service/key removed; previous SSH enable/running state restored.')
    print('Loaded USB module/IP stay until reboot. Restore the SD boot backup for full USB-role rollback.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key',type=Path)
    p.add_argument('--user',default='ark',help='existing ArkOS account (default: ark)')
    p.add_argument('--uninstall',action='store_true')
    a=p.parse_args()
    if os.geteuid()!=0:
        p.error('Run with sudo on the handheld')
    if a.uninstall:
        uninstall(System())
    else:
        if a.key is None: p.error('--key is required')
        install(System(),Path(__file__).resolve().parent,a.key,a.user)
    os.sync()


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,RuntimeError) as e:
        sys.exit('Stopped: '+str(e))
