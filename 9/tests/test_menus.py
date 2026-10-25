#!/usr/bin/python3
# Created by Paweł "pavroo" Pijanowski and Daniel Ramos (Capitain Jack) 2026/10/25
# Copyright 2026 under the GNU GPL3 License
"""The Stereo profile's menus come from what the ISO tree holds (lib/stereo/gen-menus.py)."""
import os
import subprocess
import sys
import tempfile
import unittest

NINE = ('English', 'Polski', 'Português', 'Français', 'Deutsch', '日本語', '한국어', '简体中文', '繁體中文')
HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, '..', 'lib', 'stereo', 'gen-menus.py')
BASE = os.path.join(HERE, '..', 'lib', 'boot', 'grub', 'grub.cfg')


def tree(kernels=(), enrol=True):
    t = tempfile.mkdtemp(prefix='menus-')
    os.makedirs(os.path.join(t, 'live'))
    os.makedirs(os.path.join(t, 'EFI', 'boot'))
    for name in ('vmlinuz', 'initrd.img'):
        open(os.path.join(t, 'live', name), 'w').close()
    for release in kernels:
        for name in ('vmlinuz-', 'initrd.img-'):
            open(os.path.join(t, 'live', name + release), 'w').close()
    if enrol:
        for name in ('mmx64.efi', 'edition-key.der'):
            open(os.path.join(t, 'EFI', 'boot', name), 'w').close()
    return t


def run(t, languages='de_DE'):
    subprocess.run([sys.executable, GEN, t, '--label', 'Label', '--live-label', 'Name', '--languages', languages],
                   check=True, env=dict(os.environ, SPARKYBACKUP_BASE_MENU=BASE))
    return (open(os.path.join(t, 'boot', 'grub', 'grub.cfg'), encoding='utf-8').read(),
            open(os.path.join(t, 'isolinux', 'isolinux.cfg'), encoding='utf-8').read())


class Menus(unittest.TestCase):
    def test_kernels_from_the_tree(self):
        g, i = run(tree(kernels=('7.3.0-rc6-stereo3d12-v3', '7.3.0-rc6-rt-stereo3d12')))
        for release in ('7.3.0-rc6-stereo3d12-v3', '7.3.0-rc6-rt-stereo3d12'):
            self.assertIn('if linux /live/vmlinuz-%s ' % release, g)
            self.assertIn('initrd /live/initrd.img-%s' % release, g)
            self.assertIn('kernel /live/vmlinuz-%s' % release, i)
        self.assertNotIn('vmlinuz2', g + i)
        self.assertNotIn('nokaslr', g + i)

    def test_enrolment_when_mokmanager_and_certificate_are_there(self):
        g, _ = run(tree())
        self.assertIn('--id sparky-enroll', g)
        self.assertIn('chainloader /EFI/boot/mmx64.efi', g)
        self.assertIn('edition-key.der', g)   # the certificate's own name in the steps
        self.assertEqual(g.count('sparky_no_key\n'), g.count('    if linux /live/vmlinuz'))
        for name in NINE:
            self.assertEqual(g.count('echo "%s: ' % name), 2, name)

    def test_no_enrolment_without_mokmanager(self):
        g, _ = run(tree(enrol=False))
        self.assertNotIn('sparky-enroll', g)
        self.assertNotIn('sparky_no_key', g)

    def test_languages_from_the_base_menus(self):
        g, i = run(tree(), languages='de_DE pl_PL')
        base = open(BASE, encoding='utf-8').read()
        self.assertEqual(g.count('locales='), base.count('locales=') + 2)   # the submenu's, and two on the first page
        self.assertIn('menuentry "Name (live, Deutsch)"', g)
        self.assertIn('menuentry "Name (live, Polski)"', g)
        self.assertIn('locales=de_DE.UTF-8 keyboard-layouts=de', g)
        self.assertIn('menu title Label', i)


if __name__ == '__main__':
    unittest.main()
