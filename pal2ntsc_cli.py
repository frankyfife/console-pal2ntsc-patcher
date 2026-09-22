"""PAL2NTSC, Kommandozeile.

  python pal2ntsc_cli.py scan   <datei|ordner> [...]     nur analysieren
  python pal2ntsc_cli.py patch  <datei> [--all] [--backup] [--only NAME]
  python pal2ntsc_cli.py revert <datei>                  Patch zuruecknehmen

Ohne --all werden nur die empfohlenen Patches angewendet (optionale wie
Region-/ID-Aenderungen bleiben aussen vor).

Autor / author: frankyfife
Lizenz / licence: MIT, siehe LICENSE / see LICENSE
https://github.com/frankyfife/console-pal2ntsc-patcher
"""
import argparse
import os
import sys

# Die Windows-Konsole steht oft auf cp1252; ohne das werden Zeichen wie
# Gedankenstrich oder Auslassungspunkte zu Fragezeichen.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pal2ntsc
from pal2ntsc.i18n import t, set_language, LANGUAGES
from pal2ntsc.help_text import HELP
from pal2ntsc.platforms import IMAGE_EXT, PROTECTED_EXT


def plat(p):
    return t('plat_' + p)


def iter_images(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                for fn in sorted(files):
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in IMAGE_EXT and ext != '.cue':
                        yield os.path.join(root, fn)
        else:
            yield p


def show(info, verbose=True):
    print('  %-10s: %s' % (t('ui_col_platform'), plat(info.platform)))
    print('  %-10s: %s' % (t('cli_title'), info.title))
    print('  %-10s: %s   %s: %s' % ('ID', info.game_id, t('ui_col_region'), info.region))
    for n in info.notes:
        print('  %-10s: %s' % (t('cli_notes'), n))
    if not info.patches:
        print('  %-10s: %s' % (t('cli_patches'), t('cli_none')))
        return
    print('  %s:' % t('cli_patches'))
    for p in info.patches:
        mark = '[ ]' if p.optional else '[x]'
        risky = ' (!)' if p.risky else ''
        print('    %s %-28s %s%s' % (mark, p.name, p.title, risky))
        if verbose and p.note:
            print('          %s' % p.note)
        if verbose:
            # Bei Rohsektor-Patches ist der Blob 2352 Byte gross; dann nur die
            # tatsaechlich abweichenden Bytes zeigen.
            diff = [k for k in range(len(p.original)) if p.original[k] != p.patched[k]]
            if len(p.original) > 32 and diff:
                # Rohsektor: nur die eigentliche Stelle zeigen. Dass sich weiter
                # hinten viel aendert, sind die neu berechneten EDC/ECC-Felder.
                a = diff[0]
                b = min(a + 8, len(p.original))
                print('          Offset 0x%X (+%d, %d Byte geaendert inkl. EDC/ECC): '
                      '%s -> %s'
                      % (p.offset, a, len(diff),
                         p.original[a:b].hex(), p.patched[a:b].hex()))
            else:
                print('          Offset 0x%X: %s -> %s'
                      % (p.offset, p.original.hex(), p.patched.hex()))


def cmd_scan(args):
    n = ok = 0
    for path in iter_images(args.paths):
        n += 1
        name = os.path.basename(path)
        try:
            info = pal2ntsc.analyse(path)
        except ValueError as e:
            print('\n== %s\n  %s' % (name, t('cli_skipped', err=e)))
            continue
        except Exception as e:
            print('\n== %s\n  %s' % (name, t('cli_error', err=e)))
            continue
        if info is None:
            print('\n== %s\n  %s' % (name, t('cli_notrecog')))
            continue
        ok += 1
        print('\n== %s' % name)
        show(info, verbose=args.verbose)
    print('\n' + t('cli_summary', n=n, ok=ok))
    return 0


def cmd_patch(args):
    path = args.path
    info = pal2ntsc.analyse(path)
    if info is None:
        print(t('cli_notrecog_path', path=path))
        return 2
    print('== %s' % os.path.basename(path))
    show(info)
    if not info.patches:
        return 1
    if args.only:
        selected = args.only
    elif args.all:
        selected = [p.name for p in info.patches]
    else:
        selected = [p.name for p in info.default_patches()]
    if not selected:
        print('\n' + t('cli_nothing_sel'))
        return 1
    print('\n' + t('cli_applying', list=', '.join(selected)))
    if not args.yes:
        try:
            ans = input(t('cli_confirm')).strip().lower()
            if not ans or ans[0] not in t('cli_yes'):
                print(t('cli_aborted'))
                return 1
        except EOFError:
            print(t('cli_noinput'))
            return 1
    try:
        j = pal2ntsc.patch(info, selected=selected, make_backup=args.backup,
                           progress=lambda m: print('  %s' % m))
    except pal2ntsc.PatchError as e:
        print(t('cli_failed', err=e))
        return 3
    print(t('cli_done', journal=os.path.basename(j.path)))
    print(t('cli_undo_hint', path=path))
    return 0


def cmd_revert(args):
    if args.list:
        names = pal2ntsc.applied_patches(args.path)
        if not names:
            print(t('err_no_journal'))
            return 1
        print(t('cli_applied_list'))
        for n in names:
            print('   %s' % n)
        return 0
    try:
        rev, skipped = pal2ntsc.revert(args.path, names=args.only)
    except pal2ntsc.PatchError as e:
        print(t('cli_failed', err=e))
        return 3
    extra = t('cli_reverted_extra', n=skipped) if skipped else ''
    print(t('cli_reverted', n=rev, extra=extra))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='pal2ntsc_cli',
        description='PAL->NTSC Patcher fuer PS1/PS2/GameCube/Xbox  |  '
                    'PAL to NTSC patcher for PS1/PS2/GameCube/Xbox')
    ap.add_argument('--lang', choices=[c for c, _ in LANGUAGES],
                    help='Ausgabesprache / output language (de, en)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('help', help='ausfuehrliche Hilfe / full help')
    s.set_defaults(func=lambda a: (print(HELP.get(
        a.lang or 'de', HELP['en']).strip()), 0)[1])

    s = sub.add_parser('scan', help='Images analysieren')
    s.add_argument('paths', nargs='+')
    s.add_argument('-v', '--verbose', action='store_true')
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser('patch', help='Patch anwenden')
    s.add_argument('path')
    s.add_argument('--all', action='store_true', help='auch optionale Patches')
    s.add_argument('--only', nargs='+', metavar='NAME', help='nur diese Patches')
    s.add_argument('--backup', action='store_true', help='zusaetzlich Vollkopie .bak')
    s.add_argument('-y', '--yes', action='store_true', help='ohne Rueckfrage')
    s.set_defaults(func=cmd_patch)

    s = sub.add_parser('revert', help='Patch zuruecknehmen')
    s.add_argument('path')
    s.add_argument('--only', nargs='+', metavar='NAME',
                   help='nur diese Patches zuruecknehmen (Rest bleibt)')
    s.add_argument('--list', action='store_true',
                   help='angewendete Patches auflisten')
    s.set_defaults(func=cmd_revert)

    args = ap.parse_args(argv)
    if args.lang:
        set_language(args.lang)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
