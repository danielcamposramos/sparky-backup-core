#!/usr/bin/python3
# Writes the Stereo profile's boot menus for sparky-backup-core-stereo (run from 9/: stereo/gen-menus.py lib/stereo lib/isolinux/isolinux.cfg):
#   <out>/boot/grub/grub.cfg   (UEFI: shim, then Debian's signed GRUB)
#   <out>/isolinux/isolinux.cfg (BIOS)
# Every UEFI live entry tries the stereo kernel (live/vmlinuz) first. Under Secure Boot GRUB refuses it
# until the Sparky Stereo OS key is enrolled ("bad shim loader signature"); the entry then boots
# Debian's signed kernel (live/vmlinuz2) instead, so a machine without the key still starts.
import os, sys

out = sys.argv[1]
NAME = 'Sparky Stereo OS'
FALLBACK_MSG = "The Sparky Stereo OS key is not enrolled: starting Debian's signed kernel instead."

LANGS = [('Arabic', 'ar_AE'), ('Bengali', 'bn_BD'), ('Bulgarian', 'bg_BG'), ('Chinese CN', 'zh_CN'),
         ('Chinese TW', 'zh_TW'), ('Croatian', 'hr_HR'), ('Czech', 'cs_CZ'), ('Danish', 'da_DK'),
         ('Dutch', 'nl_NL'), ('Finnish', 'fi_FI'), ('French', 'fr_FR'), ('German', 'de_DE'), ('Greek', 'el_GR'),
         ('Hebrew', 'he_IL'), ('Hindi', 'hi_IN'), ('Hungarian', 'hu_HU'), ('Indonesian', 'id_ID'),
         ('Italian', 'it_IT'), ('Japanese', 'ja_JP'), ('Korean', 'ko_KR'), ('Norwegian', 'no_NO'),
         ('Polish', 'pl_PL'), ('Portuguese BR', 'pt_BR'), ('Portuguese PT', 'pt_PT'), ('Romanian', 'ro_RO'),
         ('Russian', 'ru_RU'), ('Slovak', 'sk_SK'), ('Slovenian', 'sl_SI'), ('Spanish', 'es_ES'),
         ('Swedish', 'sv_SE'), ('Thai', 'th_TH'), ('Turkish', 'tr_TR'), ('UK English', 'en_GB'),
         ('Ukrainian', 'uk_UA'), ('Urdu', 'ur_PK')]
KEYMAP = {'de_DE': 'de', 'fr_FR': 'fr', 'pl_PL': 'pl', 'pt_BR': 'br', 'pt_PT': 'pt', 'es_ES': 'es',
          'it_IT': 'it', 'cs_CZ': 'cz', 'hu_HU': 'hu', 'en_GB': 'gb', 'ru_RU': 'ru', 'uk_UA': 'ua',
          'sv_SE': 'se', 'da_DK': 'dk', 'fi_FI': 'fi', 'no_NO': 'no', 'nl_NL': 'nl', 'tr_TR': 'tr',
          'sk_SK': 'sk', 'sl_SI': 'si', 'hr_HR': 'hr', 'ro_RO': 'ro', 'bg_BG': 'bg', 'el_GR': 'gr',
          'ja_JP': 'jp', 'ko_KR': 'kr'}


def lang_args(loc):
    a = f'locales={loc}.UTF-8'
    if loc in KEYMAP:
        a += f' keyboard-layouts={KEYMAP[loc]}'
    return a


def grub_entry(title, args, indent=''):
    i = indent
    return (f'{i}menuentry "{title}" {{\n'
            f'{i}    if linux /live/vmlinuz {args}; then\n'
            f'{i}        initrd /live/initrd.img\n'
            f'{i}    else\n'
            f'{i}        echo "{FALLBACK_MSG}"\n'
            f'{i}        sleep 4\n'
            f'{i}        linux /live/vmlinuz2 {args}\n'
            f'{i}        initrd /live/initrd2.img\n'
            f'{i}    fi\n'
            f'{i}}}\n')


LIVE = 'boot=live components'
FIND = 'findiso=${iso_path}'
g = ['source /boot/grub/config.cfg', '',
     '# Live boot. Under Secure Boot the stereo kernel starts once the Sparky Stereo OS key is enrolled;',
     "# until then each entry starts Debian's signed kernel instead (live/vmlinuz2).", '']
g.append(grub_entry(f'{NAME} (live)', f'{LIVE} quiet splash {FIND}'))
g.append(grub_entry(f'{NAME} (live, Deutsch)', f'{LIVE} {lang_args("de_DE")} quiet splash {FIND}'))
g.append(f'menuentry "{NAME} with Debian\'s signed kernel (no key needed, no stereo kernel)" {{\n'
         f'    linux   /live/vmlinuz2 {LIVE} quiet splash {FIND}\n'
         f'    initrd  /live/initrd2.img\n}}\n')
g.append('if [ "$grub_platform" = efi ]; then\n'
         '    menuentry "Enrol the Sparky Stereo OS key (MokManager, Secure Boot)" {\n'
         '        chainloader /EFI/boot/mmx64.efi\n'
         '    }\n'
         'fi\n')
g.append(grub_entry('Safe graphics (nomodeset)', f'{LIVE} nomodeset nosplash {FIND}'))
g.append(grub_entry('NoSplash', f'{LIVE} nosplash {FIND}'))
g.append(grub_entry('Failsafe mode', f'{LIVE} memtest noapic noapm nodma nomce nolapic nosmp nosplash vga=788 {FIND}'))
g.append(grub_entry('Copy ToRAM', f'{LIVE} toram quiet splash {FIND}'))
g.append(grub_entry('Text mode', f'{LIVE} quiet nosplash systemd.unit=multi-user.target {FIND}'))
g.append('menuentry "Memory Test x64.efi" {\n    linux   /boot/memtest86+x64.efi\n}\n')
g.append('menuentry "uEFI firmware setup" {\n    fwsetup\n}\n')
g.append("submenu --hotkey=m 'More Languages...' {\n    set color_normal=light-gray/black\n    set color_highlight=white/black\n")
for name, loc in LANGS:
    g.append(grub_entry(f'{NAME} {name}', f'{LIVE} {lang_args(loc)} quiet splash {FIND}', '    '))
g.append('}\n')
os.makedirs(f'{out}/boot/grub', exist_ok=True)
open(f'{out}/boot/grub/grub.cfg', 'w').write('\n'.join(g))

head = open(sys.argv[2]).read().split('\nlabel live\n')[0]
il = [head, '']


def il_entry(label, title, args, kernel='/live/vmlinuz', initrd='/live/initrd.img'):
    return f'label {label}\n\tmenu label {title}\n\tkernel {kernel}\n\tappend initrd={initrd} {args}\n'


CFG = 'boot=live config'
il.append(il_entry('live', '__LIVELABEL__ (live)', f'{CFG} quiet splash'))
il.append(il_entry('livede', '__LIVELABEL__ (live, Deutsch)', f'{CFG} {lang_args("de_DE")} quiet splash'))
il.append(il_entry('livedebian', "__LIVELABEL__ with Debian's kernel", f'{CFG} quiet splash', '/live/vmlinuz2', '/live/initrd2.img'))
il.append(il_entry('livenosplash', 'NoSplash', f'{CFG} quiet nosplash'))
il.append(il_entry('livefailsafe', 'Failsafe', f'{CFG} noapic noapm nodma nomce nolapic pci=nomsi nomodeset radeon.modeset=0 nouveau.modeset=0 nosmp vga=normal nosplash'))
il.append(il_entry('livetoram', 'Copy ToRAM', f'{CFG} toram nosplash'))
il.append(il_entry('livetext', 'Text mode', f'{CFG} systemd.unit=multi-user.target nosplash'))
il.append('label hd\n\tmenu label Boot the first hard disk\n\tCOM32 chain.c32\n\tAPPEND hd0\n')
il.append('menu begin More Languages...\n')
for name, loc in LANGS:
    il.append(il_entry('live', f'__LIVELABEL__ {name}', f'{CFG} quiet splash {lang_args(loc)}'))
il.append('menu end\n')
il.append('label memtest\n\tmenu label Memory Test\n\tkernel /isolinux/memtest\n\tappend -\n')
il.append('label hdt\n\tmenu label Hardware Detection\n\tkernel /isolinux/hdt.c32\n\tappend -\n')
os.makedirs(f'{out}/isolinux', exist_ok=True)
open(f'{out}/isolinux/isolinux.cfg', 'w').write('\n'.join(il))
