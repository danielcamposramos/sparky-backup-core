# SPDX-License-Identifier: GPL-3.0-or-later
"""Staging behavior; actual Debian firmware boot evidence is a separate check."""
from pathlib import Path
import runpy
import tempfile
import unittest

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'lib/stage-boot-files.py'))


class BootStaging(unittest.TestCase):
    def test_current_inputs_replace_old_programs_without_replacing_menus(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            system, iso = root / 'system', root / 'iso'
            for relative in set(MODULE['FILES'].values()):
                path = system / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(relative.encode())
            menu = iso / 'boot/grub/grub.cfg'
            menu.parent.mkdir(parents=True)
            menu.write_text('profile menu with nokaslr\n')
            old = iso / 'boot/grub/i386-efi'
            old.mkdir()
            (old / 'old.mod').write_bytes(b'obsolete module')
            MODULE['stage'](iso, system)
            for relative, source in MODULE['FILES'].items():
                self.assertEqual((iso / relative).read_bytes(), (system / source).read_bytes())
            self.assertEqual(menu.read_text(), 'profile menu with nokaslr\n')
            self.assertFalse(old.exists())

    def test_missing_input_and_target_escape_fail_before_copying(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            system, iso = root / 'system', root / 'iso'
            with self.assertRaisesRegex(ValueError, 'Missing boot dependency'):
                MODULE['stage'](iso, system)
            self.assertFalse(iso.exists())
            for relative in set(MODULE['FILES'].values()):
                path = system / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            iso.mkdir()
            (iso / 'isolinux').symlink_to(system, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'escapes'):
                MODULE['stage'](iso, system)
            self.assertFalse((system / 'isolinux.bin').exists())


if __name__ == '__main__':
    unittest.main()
