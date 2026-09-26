"""No hardware access: synthetic DTBs, scratch directories, mocked services."""
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
import dtb
import prepare_sd as sd
spec=importlib.util.spec_from_file_location('device_install',ROOT/'device'/'install.py')
device=importlib.util.module_from_spec(spec); spec.loader.exec_module(device)


def fixture_dtb():
    strings=bytearray(); body=bytearray()
    def node(name):
        raw=name.encode()+b'\0'
        body.extend(struct.pack('>I',1)+raw+b'\0'*(-len(raw)%4))
    def prop(name,value):
        offset=len(strings); strings.extend(name.encode()+b'\0')
        body.extend(struct.pack('>III',3,len(value),offset)+value+b'\0'*(-len(value)%4))
    def end(): body.extend(struct.pack('>I',2))
    node(''); prop('compatible',b'test,handheld\0rockchip,rk3326\0')
    node('display'); prop('panel',b'keep-this-panel\0'); end()
    node('usb@ff300000'); prop('dr_mode',b'otg\0'); prop('unrelated',b'\x01\x02'); end()
    node('syscon@ff2c0000'); node('usb2-phy@100'); node('otg-port')
    prop('status',b'disabled\0'); end(); end(); end(); end()
    body.extend(struct.pack('>I',9))
    prefix=struct.pack('>10I',0xd00dfeed,56+len(body)+len(strings),56,56+len(body),40,17,16,0,len(strings),len(body))
    return prefix+b'\0'*16+body+strings


def fixture_key():
    raw=b'\0\0\0\x0bssh-ed25519\0\0\0\x20'+bytes(range(32))
    return 'ssh-ed25519 '+base64.b64encode(raw).decode()+' disposable-test-fixture\n'


class MockSystem(device.System):
    def __init__(self,root):
        super().__init__(root)
        self.enabled={'ssh.service':'disabled',device.UNIT:'disabled'}
        self.active={'ssh.service':False,device.UNIT:False}
        self.fail_start=False
        self.calls=[]
    def preflight(self,user):
        return types.SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid(),pw_dir='/home/ark')
    def own(self,path,uid,gid): pass
    def run(self,*args,**kwargs):
        self.calls.append(args)
        if args[0]=='systemctl':
            action=args[1]; unit=args[-1]
            if action=='is-enabled': return (0 if self.enabled[unit]=='enabled' else 1,self.enabled[unit])
            if action=='is-active':
                result=(0 if self.active[unit] else 3,'')
                if kwargs.get('check',True) and result[0]: raise RuntimeError('Inactive unit')
                return result
            if action=='enable': self.enabled[unit]='enabled'
            elif action=='disable':
                self.enabled[unit]='disabled'
                if '--now' in args: self.active[unit]=False
            elif action in ('start','restart'):
                if self.fail_start and unit==device.UNIT:
                    self.fail_start=False
                    raise RuntimeError('Simulated USB start failure')
                self.active[unit]=True
                if unit==device.UNIT: self.active['ssh.service']=True
            elif action=='stop': self.active[unit]=False
        return 0,''


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.boot=self.root/'BOOT'; self.boot.mkdir()
        self.roms=self.root/'EASYROMS'; (self.roms/'ports').mkdir(parents=True)
        self.original=fixture_dtb()
        (self.boot/'active.dtb').write_bytes(self.original)
        (self.boot/'boot.ini').write_text('load mmc 1:1 ${dtb_loadaddr} active.dtb\n')
        self.key=self.root/'test.pub'; self.key.write_text(fixture_key())
        self.system=MockSystem(self.root/'linux')
        self.auth=self.system.path('/home/ark/.ssh/authorized_keys')
        self.auth.parent.mkdir(parents=True,mode=0o700)
        self.silence=contextlib.redirect_stdout(io.StringIO()); self.silence.__enter__()
    def tearDown(self):
        self.silence.__exit__(None,None,None); self.temp.cleanup()
    def install(self):
        device.install(self.system,ROOT/'device',self.key,'ark')

    def test_dtb_only_three_changes(self):
        patched,changes=dtb.patch(self.original)
        before=dtb.parse(self.original); after=dtb.parse(patched)
        expected=dict(before[3]); expected.update(dtb.CHANGES)
        self.assertEqual(after[3],expected)
        self.assertEqual(after[4],before[4])
        self.assertEqual(len(changes),3)
        self.assertEqual(patched[40:56],self.original[40:56])

    def test_dtb_idempotent(self):
        patched,_=dtb.patch(self.original)
        self.assertEqual(dtb.patch(patched),(patched,[]))

    def test_dtb_wrong_soc_refused(self):
        bad=self.original.replace(b'rockchip,rk3326',b'rockchip,rk9999')
        with self.assertRaises(ValueError): dtb.patch(bad)

    def test_dtb_truncation_refused(self):
        with self.assertRaises(ValueError): dtb.patch(self.original[:-1])

    def test_dry_run_changes_nothing(self):
        sd.prepare(self.boot,self.roms,self.key)
        self.assertFalse((self.boot/sd.BACKUP).exists())
        self.assertEqual((self.boot/'active.dtb').read_bytes(),self.original)
        self.assertEqual(list((self.roms/'ports').iterdir()),[])

    def test_prepare_repeat_restore_exact(self):
        sd.prepare(self.boot,self.roms,self.key,True)
        sd.prepare(self.boot,self.roms,self.key,True)
        self.assertEqual(sd.active_dtb(self.boot).name,'active.dtb')
        self.assertEqual((self.boot/'boot.ini').read_text(),'load mmc 1:1 ${dtb_loadaddr} active.dtb\n')
        sd.restore(self.boot,self.roms)
        sd.restore(self.boot,self.roms)
        self.assertEqual((self.boot/'active.dtb').read_bytes(),self.original)
        self.assertEqual(list((self.roms/'ports').iterdir()),[])

    def test_restore_refuses_changed_dtb(self):
        sd.prepare(self.boot,self.roms,self.key,True)
        current=(self.boot/'active.dtb').read_bytes().replace(b'keep-this-panel',b'keep-that-panel')
        (self.boot/'active.dtb').write_bytes(current)
        with self.assertRaises(ValueError): sd.restore(self.boot,self.roms)
        self.assertEqual((self.boot/'active.dtb').read_bytes(),current)

    def test_manifest_path_escape_refused(self):
        sd.prepare(self.boot,self.roms,self.key,True)
        p=self.boot/sd.BACKUP/'manifest.json'; m=json.loads(p.read_text())
        m['dtb']='../victim'; p.write_text(json.dumps(m))
        with self.assertRaises(ValueError): sd.restore(self.boot,self.roms)

    def test_prepare_refuses_existing_launcher(self):
        p=self.roms/'ports'/sd.LAUNCHER; p.write_text('unrelated')
        with self.assertRaises(ValueError): sd.prepare(self.boot,self.roms,self.key,True)
        self.assertEqual(p.read_text(),'unrelated')
        self.assertFalse((self.boot/sd.BACKUP).exists())

    def test_private_key_rejected(self):
        self.key.write_text('This is not a public key')
        with self.assertRaises(ValueError): sd.prepare(self.boot,self.roms,self.key,True)
        self.assertFalse((self.boot/sd.BACKUP).exists())

    def test_install_repeat_uninstall_exact(self):
        old=b'# existing authorization without final newline'
        self.auth.write_bytes(old); self.auth.chmod(0o640)
        self.install(); first=self.auth.read_bytes(); self.install()
        self.assertEqual(self.auth.read_bytes(),first)
        self.assertEqual(first.count(b'r36h-usb-ssh-managed'),1)
        device.uninstall(self.system)
        self.assertEqual(self.auth.read_bytes(),old)
        self.assertEqual(self.auth.stat().st_mode&0o777,0o640)
        self.assertEqual(self.system.enabled['ssh.service'],'disabled')
        self.assertFalse(self.system.active['ssh.service'])
        for p in device.FILES.values(): self.assertFalse(self.system.path(p).exists())

    def test_uninstall_preserves_later_keys(self):
        self.auth.write_text('# existing\n'); self.install()
        with self.auth.open('a') as f: f.write('# another key installed later\n')
        device.uninstall(self.system)
        self.assertEqual(self.auth.read_text(),'# existing\n# another key installed later\n')

    def test_existing_same_key_not_duplicated_or_removed(self):
        old=fixture_key().encode(); self.auth.write_bytes(old)
        self.install(); self.assertEqual(self.auth.read_bytes(),old)
        device.uninstall(self.system); self.assertEqual(self.auth.read_bytes(),old)

    def test_existing_ssh_state_preserved(self):
        self.system.enabled['ssh.service']='enabled'; self.system.active['ssh.service']=True
        self.install(); device.uninstall(self.system)
        self.assertEqual(self.system.enabled['ssh.service'],'enabled')
        self.assertTrue(self.system.active['ssh.service'])

    def test_start_failure_rolls_back(self):
        self.auth.write_text('# keep\n'); self.system.fail_start=True
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError): self.install()
        self.assertEqual(self.auth.read_text(),'# keep\n')
        self.assertFalse(self.system.path(device.STATE).exists())
        for p in device.FILES.values(): self.assertFalse(self.system.path(p).exists())
        self.assertEqual(self.system.enabled['ssh.service'],'disabled')

    def test_unmanaged_system_file_refused(self):
        p=self.system.path(device.FILES['start.sh']); p.parent.mkdir(parents=True); p.write_text('unmanaged')
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(p.read_text(),'unmanaged')
        self.assertFalse(self.system.path(device.STATE).exists())

    def test_changed_managed_file_not_deleted(self):
        self.install()
        p=self.system.path(device.FILES['start.sh']); p.write_text('local changes')
        with self.assertRaises(ValueError): device.uninstall(self.system)
        self.assertEqual(p.read_text(),'local changes')
        self.assertTrue(self.system.path(device.STATE).exists())

    def test_uninstall_without_install_no_changes(self):
        device.uninstall(self.system)
        self.assertEqual(self.system.calls,[])


if __name__=='__main__':
    unittest.main()
