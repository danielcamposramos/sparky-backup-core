#!/usr/bin/python3
# Created by Paweł "pavroo" Pijanowski and Daniel Ramos (Capitain Jack) 2026/10/15
# Copyright 2026 under the GNU GPL3 License
# Last update 2026/10/25
"""The Stereo profile's boot menus, written by sparkybackup-stereo from what the image and the ISO tree hold:

  gen-menus.py ISOTMP --label ISOLABEL --live-label LIVECDLABEL [--languages "de_DE ..."]

  ISOTMP/boot/grub/grub.cfg       UEFI: shim, Debian's signed GRUB, the live kernels
  ISOTMP/isolinux/isolinux.cfg    BIOS: ISOLINUX, the same kernels (header: the profile's isolinux-head.cfg)
  ISOTMP/.disk/info               the line GRUB's EFI image searches for
  ISOTMP/boot/grub/live-theme/theme.txt   the terminal takes the whole screen

Nothing is fixed here; each part comes from where it lives:
- the kernels: /live/vmlinuz (the profile's LIVEKERNEL) and every /live/vmlinuz-RELEASE with its initrd.img-RELEASE
  (each further kernel the image holds, staged by sparkybackup under its release name);
- the Secure Boot enrolment: offered when the EFI image's folder EFI/boot holds MokManager (mmx64.efi, from shim's
  package) and a certificate (*.der, MOKCERT), whose file name the steps name;
- the languages: those of the base menus' "More Languages..." submenu (/usr/lib/sparkybackup/boot/grub/grub.cfg),
  with their locales, and the keyboard layout of each locale from the profile's keyboard-layouts file; --languages
  (LIVELANGUAGES) puts some of them on the first page too;
- the texts in the nine required languages: the profile's lang/ files (lang/en, lang/de, ...).
Under Secure Boot, shim refuses a kernel whose key is not in the MOK list ("bad shim loader signature",
grub-core/kern/efi/sb.c): every live entry then explains it in the nine languages and opens the menu again with the
enrolment selected (GRUB puts "default" back after an entry, grub_menu_execute_entry in grub-core/normal/menu.c,
hence configfile and sparky_default). The explanation shows only when GRUB set shim_lock (Secure Boot on,
grub_shim_lock_verifier_setup). sleep --interruptible stops on Esc, F4 or Shift (grub_key_is_interrupt).
"""
import argparse
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_MENU = os.environ.get('SPARKYBACKUP_BASE_MENU', '/usr/lib/sparkybackup/boot/grub/grub.cfg')
REQUIRED = ['en', 'pl', 'pt_BR', 'fr', 'de', 'ja', 'ko', 'zh_CN', 'zh_TW']
COLUMNS = 98   # GRUB's gfxterm at 800x600 (config.cfg) with Unifont 16: 100 columns
LIVE = 'boot=live components'
FIND = 'findiso=${iso_path}'
CFG = 'boot=live config'


def strings(code):
    values = {}
    try:
        for line in open(os.path.join(HERE, 'lang', code), encoding='utf-8'):
            if '=' in line:
                k, v = line.rstrip('\n').split('=', 1)
                values[k] = v.strip().strip('"')
    except OSError:
        pass
    return values


def width(text):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)


def wrap(text, columns=COLUMNS):
    """Lines of at most COLUMNS display columns: at spaces, and after CJK punctuation or anywhere inside CJK text."""
    lines, line = [], ''
    for word in re.sub(r'([、，。])', r'\1\0', text).replace(' ', '\0 ').split('\0'):
        if not word:
            continue
        candidate = line + word if line else word.lstrip(' ')
        if width(candidate) <= columns:
            line = candidate
            continue
        if line:
            lines.append(line.rstrip(' '))
        line = ''
        for c in word.lstrip(' '):
            if width(line + c) > columns:
                lines.append(line)
                line = ''
            line += c
    if line:
        lines.append(line.rstrip(' '))
    return lines


def echo_lines(key, cert, indent):
    out = []
    for code in REQUIRED:
        s = strings(code)
        if key not in s:
            continue
        text = s[key].replace('{cert}', cert)
        assert not set('$"\\') & set(text), (code, key)
        for line in wrap('%s: %s' % (s.get('NAME', code), text)):
            out.append('%secho "%s"' % (indent, line))
    return out


def languages():
    """(English name, locale, keyboard layout or '') of the base menus' language submenu."""
    found = []
    try:
        text = open(BASE_MENU, encoding='utf-8').read()
    except OSError:
        return found
    for m in re.finditer(r'menuentry\s+["\']\S+\s+([^"\']+)["\']\s*\{([^}]*)\}', text):
        locale = re.search(r'locales=(\S+)', m.group(2))
        if not locale:
            continue
        keys = re.search(r'keyboard-layouts=(\S+)', m.group(2))
        loc = locale.group(1).replace('.UTF-8', '')
        found.append((m.group(1).strip(), loc, keys.group(1) if keys else layouts().get(loc, '')))
    return found


def layouts():
    """locale -> keyboard layout, from the profile's keyboard-layouts file."""
    table = {}
    try:
        for line in open(os.path.join(HERE, 'keyboard-layouts'), encoding='utf-8'):
            parts = line.split()
            if len(parts) == 2 and not line.startswith('#'):
                table[parts[0]] = parts[1]
    except OSError:
        pass
    return table


def lang_args(locale, keys):
    return 'locales=%s.UTF-8%s' % (locale, ' keyboard-layouts=' + keys if keys else '')


def kernels(tree):
    """[(label suffix, kernel path, initrd path)]: the default kernel first, then each further one by release."""
    live = os.path.join(tree, 'live')
    found = []
    if os.path.isfile(os.path.join(live, 'vmlinuz')):
        found.append(('', '/live/vmlinuz', '/live/initrd.img'))
    for f in sorted(os.listdir(live)) if os.path.isdir(live) else []:
        if f.startswith('vmlinuz-') and os.path.isfile(os.path.join(live, 'initrd.img-' + f[8:])):
            found.append((f[8:], '/live/' + f, '/live/initrd.img-' + f[8:]))
    return found


def enrolment(tree):
    """The certificate's file name when the EFI image's folder holds MokManager and a certificate, else None."""
    efi = os.path.join(tree, 'EFI', 'boot')
    names = os.listdir(efi) if os.path.isdir(efi) else []
    certs = sorted(n for n in names if n.lower().endswith('.der'))
    if 'mmx64.efi' in names and certs:
        return certs[0]
    return None


def grub_cfg(name, tree, first_page):
    ks = kernels(tree)
    cert = enrolment(tree)
    langs = languages()
    g = ['source /boot/grub/config.cfg',
         'if [ -n "$sparky_default" ]; then',
         '    set default="$sparky_default"',
         'fi', '']

    def entry(title, args, kernel, initrd, indent=''):
        i = indent
        refused = (['%s    else' % i, '%s        sparky_no_key' % i] if cert else [])
        return '\n'.join(['%smenuentry "%s" {' % (i, title),
                          '%s    if linux %s %s; then' % (i, kernel, args),
                          '%s        initrd %s' % (i, initrd)] + refused + ['%s    fi' % i, '%s}' % i, ''])

    if cert:
        # the enrolment entry's texts name the certificate; the explanation opens the menu again with it selected
        g += ['function sparky_no_key {',
              '    if [ "$shim_lock" = y ]; then',
              *echo_lines('NO_KEY', cert, '        '),
              '        sleep --interruptible --verbose 60',
              '        set sparky_default=sparky-enroll',
              '        export sparky_default',
              '        configfile /boot/grub/grub.cfg',
              '    fi',
              '}', '']
    default = ks[0] if ks else ('', '/live/vmlinuz', '/live/initrd.img')
    g.append(entry('%s (live)' % name, '%s quiet splash %s' % (LIVE, FIND), default[1], default[2]))
    for english, locale, keys in [l for l in langs if l[1] in first_page]:
        native = strings(locale) .get('NAME') or strings(locale.split('_')[0]).get('NAME') or english
        g.append(entry('%s (live, %s)' % (name, native), '%s %s quiet splash %s' % (LIVE, lang_args(locale, keys), FIND),
                       default[1], default[2]))
    for release, kernel, initrd in ks[1:]:
        g.append(entry('%s (live, %s)' % (name, release), '%s quiet splash %s' % (LIVE, FIND), kernel, initrd))
    if cert:
        # MokManager is a 64-bit program: only on 64-bit UEFI (GRUB's script has no &&: one if inside the other)
        title = strings('en').get('ENROLL_TITLE', 'Secure Boot: enroll the key')
        g.append('\n'.join(['if [ "$grub_platform" = efi ]; then',
                            '    if [ "$grub_cpu" = x86_64 ]; then',
                            '        menuentry "%s" --id sparky-enroll {' % title,
                            *echo_lines('STEPS', cert, '            '),
                            '            sleep --interruptible --verbose 60',
                            '            terminal_output console',
                            '            chainloader /EFI/boot/mmx64.efi',
                            '        }',
                            '    fi',
                            'fi', '']))
    for title, args in (('Safe graphics (nomodeset)', 'nomodeset nosplash'), ('NoSplash', 'nosplash'),
                        ('Failsafe mode', 'memtest noapic noapm nodma nomce nolapic nosmp nosplash vga=788'),
                        ('Copy ToRAM', 'toram quiet splash'), ('Text mode', 'quiet nosplash systemd.unit=multi-user.target')):
        g.append(entry(title, '%s %s %s' % (LIVE, args, FIND), default[1], default[2]))
    g.append('menuentry "Memory Test x64.efi" {\n    linux   /boot/memtest86+x64.efi\n}\n')
    g.append('menuentry "uEFI firmware setup" {\n    fwsetup\n}\n')
    if langs:
        g.append("submenu --hotkey=m 'More Languages...' {\n    set color_normal=light-gray/black\n"
                 "    set color_highlight=white/black\n")
        for english, locale, keys in langs:
            g.append(entry('%s %s' % (name, english), '%s %s quiet splash %s' % (LIVE, lang_args(locale, keys), FIND),
                           default[1], default[2], '    '))
        g.append('}\n')
    return '\n'.join(g)


def isolinux_cfg(head, name, label, tree, first_page):
    ks = kernels(tree)
    langs = languages()
    default = ks[0] if ks else ('', '/live/vmlinuz', '/live/initrd.img')

    def entry(tag, title, args, kernel=default[1], initrd=default[2]):
        return 'label %s\n\tmenu label %s\n\tkernel %s\n\tappend initrd=%s %s\n' % (tag, title, kernel, initrd, args)
    il = [head.replace('__LIVECDLABEL__', label).replace('__LIVELABEL__', name), '',
          entry('live', '%s (live)' % name, '%s quiet splash' % CFG)]
    for english, locale, keys in [l for l in langs if l[1] in first_page]:
        native = strings(locale).get('NAME') or strings(locale.split('_')[0]).get('NAME') or english
        il.append(entry('live' + locale.split('_')[0], '%s (live, %s)' % (name, native),
                        '%s %s quiet splash' % (CFG, lang_args(locale, keys))))
    for n, (release, kernel, initrd) in enumerate(ks[1:]):
        il.append(entry('livekernel%d' % n, '%s (live, %s)' % (name, release), '%s quiet splash' % CFG, kernel, initrd))
    il += [entry('livenosplash', 'NoSplash', '%s quiet nosplash' % CFG),
           entry('livefailsafe', 'Failsafe', '%s noapic noapm nodma nomce nolapic pci=nomsi nomodeset radeon.modeset=0 '
                 'nouveau.modeset=0 nosmp vga=normal nosplash' % CFG),
           entry('livetoram', 'Copy ToRAM', '%s toram nosplash' % CFG),
           entry('livetext', 'Text mode', '%s systemd.unit=multi-user.target nosplash' % CFG),
           'label hd\n\tmenu label Boot the first hard disk\n\tCOM32 chain.c32\n\tAPPEND hd0\n']
    if langs:
        il.append('menu begin More Languages...\n')
        for english, locale, keys in langs:
            il.append(entry('live', '%s %s' % (name, english), '%s quiet splash %s' % (CFG, lang_args(locale, keys))))
        il.append('menu end\n')
    il += ['label memtest\n\tmenu label Memory Test\n\tkernel /isolinux/memtest\n\tappend -\n',
           'label hdt\n\tmenu label Hardware Detection\n\tkernel /isolinux/hdt.c32\n\tappend -\n']
    return '\n'.join(il)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tree')
    ap.add_argument('--label', required=True, help='the menu title (ISOLABEL)')
    ap.add_argument('--live-label', required=True, help='the system name in the entries (LIVECDLABEL)')
    ap.add_argument('--languages', default='', help='locales also on the first page (LIVELANGUAGES)')
    a = ap.parse_args()
    tree = a.tree
    first_page = a.languages.split()
    if not kernels(tree):
        sys.exit('gen-menus: no kernel in %s/live' % tree)
    os.makedirs(os.path.join(tree, 'boot/grub'), exist_ok=True)
    with open(os.path.join(tree, 'boot/grub/grub.cfg'), 'w', encoding='utf-8') as f:
        f.write(grub_cfg(a.live_label, tree, first_page))
    head = open(os.path.join(HERE, 'isolinux-head.cfg'), encoding='utf-8').read().rstrip('\n')
    os.makedirs(os.path.join(tree, 'isolinux'), exist_ok=True)
    with open(os.path.join(tree, 'isolinux/isolinux.cfg'), 'w', encoding='utf-8') as f:
        f.write(isolinux_cfg(head, a.live_label, a.label, tree, first_page))
    try:
        os.unlink(os.path.join(tree, 'isolinux/isolinux-head.cfg'))
    except OSError:
        pass
    os.makedirs(os.path.join(tree, '.disk'), exist_ok=True)
    with open(os.path.join(tree, '.disk/info'), 'w', encoding='utf-8') as f:
        f.write('%s LIVE/INSTALL\n' % a.label)
    theme = os.path.join(tree, 'boot/grub/live-theme/theme.txt')
    if os.path.exists(theme):
        text = open(theme, encoding='utf-8').read()
        if 'terminal-width' not in text:
            # the terminal (a running entry, the editor, the command line) takes the whole screen: the Secure Boot
            # texts in the nine languages need its 100 columns and 37 lines at 800x600
            with open(theme, 'w', encoding='utf-8') as f:
                f.write('terminal-left: "0"\nterminal-top: "0"\nterminal-width: "100%"\nterminal-height: "100%"\n'
                        'terminal-border: "0"\n' + text)


if __name__ == '__main__':
    main()
