#!/usr/bin/env python3
# Copyright 2026 Daniel Ramos (Capitain Jack), GPL-3.0-or-later
"""Generate real menu text from controlled copies; no boot binaries are executed."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE=Path(os.environ.get('SUBJECT',Path(__file__).resolve().parents[1]))
NINE=('en','pl','pt_BR','fr','de','ja','ko','zh_CN','zh_TW')


class MenuFailures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.profile=self.root/'profile'
        shutil.copytree(SOURCE/'lib/stereo',self.profile)
        self.base=self.root/'base.cfg';shutil.copyfile(SOURCE/'lib/boot/grub/grub.cfg',self.base)
        self.tree=self.root/'iso'
        for path in ('live/vmlinuz','live/initrd.img','EFI/boot/mmx64.efi','EFI/boot/edition.der'):
            f=self.tree/path;f.parent.mkdir(parents=True,exist_ok=True);f.touch()
        self.grub=self.tree/'boot/grub/grub.cfg';self.grub.parent.mkdir(parents=True);self.grub.write_text('previous GRUB\n')
        self.bios=self.tree/'isolinux/isolinux.cfg';self.bios.parent.mkdir(parents=True);self.bios.write_text('previous BIOS\n')

    def generate(self,languages='de_DE'):
        return subprocess.run([sys.executable,str(self.profile/'gen-menus.py'),str(self.tree),
                               '--label','Label','--live-label','Name','--languages',languages],
                              env=dict(os.environ,SPARKYBACKUP_BASE_MENU=str(self.base)),
                              text=True,capture_output=True)

    def fails_before_output(self,result,detail):
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn(detail,result.stderr)
        self.assertIn('Repair the named file/package and regenerate the image',result.stderr)
        self.assertEqual(self.grub.read_text(),'previous GRUB\n')
        self.assertEqual(self.bios.read_text(),'previous BIOS\n')

    def test_U49_missing_language_files(self):
        for code in NINE:
            with self.subTest(code=code):
                f=self.profile/'lang'/code;data=f.read_bytes();f.unlink()
                self.fails_before_output(self.generate(),f'lang/{code}')
                f.write_bytes(data)

    def test_U49_missing_keys(self):
        for code in NINE:
            f=self.profile/'lang'/code;original=f.read_text()
            for key in ('NAME','NO_KEY','STEPS'):
                with self.subTest(code=code,key=key):
                    f.write_text('\n'.join(line for line in original.splitlines() if not line.startswith(key+'=')))
                    self.fails_before_output(self.generate(),key)
            f.write_text(original)

    def test_U49_missing_enrolment_title(self):
        f=self.profile/'lang/en';f.write_text('\n'.join(x for x in f.read_text().splitlines() if not x.startswith('ENROLL_TITLE=')))
        self.fails_before_output(self.generate(),'ENROLL_TITLE')

    def test_U49_empty_text(self):
        f=self.profile/'lang/ja';f.write_text(re.sub(r'NO_KEY=.*','NO_KEY=""',f.read_text()))
        self.fails_before_output(self.generate(),'NO_KEY')

    def test_U49_missing_base_menu(self):
        self.base.unlink();self.fails_before_output(self.generate(),'base.cfg')

    def test_U49_empty_base_menu(self):
        self.base.write_text('');self.fails_before_output(self.generate(),'missing required locales')

    def test_U49_missing_required_locale(self):
        self.base.write_text(self.base.read_text().replace('locales=ja_JP.UTF-8','not-a-locale=ja_JP.UTF-8'))
        self.fails_before_output(self.generate(),'ja_JP')

    def test_U49_missing_layout_map(self):
        (self.profile/'keyboard-layouts').unlink();self.fails_before_output(self.generate(),'keyboard-layouts')

    def test_U49_empty_layout_map(self):
        (self.profile/'keyboard-layouts').write_text('');self.fails_before_output(self.generate(),'empty keyboard layout table')

    def test_U49_missing_layout_row(self):
        f=self.profile/'keyboard-layouts';f.write_text('\n'.join(x for x in f.read_text().splitlines() if not x.startswith('de_DE')))
        self.fails_before_output(self.generate(),'missing policy for de_DE')

    def test_U49_malformed_layout_row(self):
        f=self.profile/'keyboard-layouts';f.write_text(f.read_text()+'malformed\n')
        self.fails_before_output(self.generate(),'malformed or duplicate')

    def test_U49_requested_language_unknown(self):
        self.fails_before_output(self.generate('zz_ZZ'),'zz_ZZ')

    def test_U49_missing_bios_header(self):
        (self.profile/'isolinux-head.cfg').unlink();self.fails_before_output(self.generate(),'isolinux-head.cfg')

    def test_U49_unsafe_text(self):
        f=self.profile/'lang/pl';f.write_text(f.read_text().replace('NO_KEY="','NO_KEY="$bad '))
        self.fails_before_output(self.generate(),'unsafe text')

    def test_U49_missing_certificate_placeholder(self):
        f=self.profile/'lang/fr';f.write_text(f.read_text().replace('{cert}','key.der'))
        self.fails_before_output(self.generate(),'STEPS must name')

    def test_U49_success_all_languages(self):
        result=self.generate('de_DE zh_TW');self.assertEqual(result.returncode,0,result.stderr)
        for code in ('pl_PL','pt_BR','fr_FR','de_DE','ja_JP','ko_KR','zh_CN','zh_TW','en_GB'):
            self.assertIn(f'locales={code}.UTF-8',self.grub.read_text())
            self.assertIn(f'locales={code}.UTF-8',self.bios.read_text())
        for name in ('English','Polski','Português','Français','Deutsch','日本語','한국어','简体中文','繁體中文'):
            self.assertEqual(self.grub.read_text().count(f'echo "{name}: '),2,name)
        self.assertIn('edition.der',self.grub.read_text())
        self.assertNotIn('vmlinuz2',self.grub.read_text())


if __name__=='__main__':unittest.main(verbosity=2)
