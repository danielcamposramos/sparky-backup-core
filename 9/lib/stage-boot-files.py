#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Daniel Campos Ramos
"""Stage current Debian boot programs, leaving the profile's menus intact.

Usage: stage-boot-files.py ISO_TREE [SYSTEM_ROOT]
SYSTEM_ROOT defaults to /; an extracted dependency tree is useful for tests.
"""
from pathlib import Path
import shutil
import sys


FILES = {
    "isolinux/isolinux.bin": "usr/lib/ISOLINUX/isolinux.bin",
    "isolinux/memtest": "boot/mt86+x64",
    "boot/memtest86+x64.bin": "boot/mt86+x64",
    "boot/memtest86+x64.efi": "boot/mt86+x64",
    "EFI/boot/bootia32.efi": "usr/lib/grub/i386-efi/monolithic/gcdia32.efi",
}
for module in ("vesamenu", "libutil", "libgpl", "ldlinux", "hdt", "libmenu", "chain", "libcom32"):
    FILES[f"isolinux/{module}.c32"] = f"usr/lib/syslinux/modules/bios/{module}.c32"


def stage(destination, system=Path("/")):
    destination, system = Path(destination).resolve(), Path(system).resolve()
    if destination == Path('/') or destination == system:
        raise ValueError('The destination must be a separate ISO staging tree')
    # Check the complete dependency set before changing the generated tree.
    for relative, source in FILES.items():
        path = system / source
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing boot dependency: {path}")
        target = destination / relative
        if not target.resolve().is_relative_to(destination):
            raise ValueError(f"Boot target escapes the ISO tree: {target}")
    for relative, source in FILES.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(system / source, target)
        target.chmod(0o644)
    # The CD image embeds its own modules. Old 2.06 modules cannot be mixed
    # with a new Debian image; the existing amd64 path does the same cleanup.
    modules = destination / "boot/grub/i386-efi"
    if modules.is_symlink():
        modules.unlink()
    elif modules.exists():
        shutil.rmtree(modules)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    try:
        stage(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else Path("/"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"Cannot stage Debian boot files: {error}") from error
