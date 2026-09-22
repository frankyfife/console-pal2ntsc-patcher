"""Kandidaten fuer den Renderhoehen-Patch in PS2-Images suchen.

Hintergrund: Nach dem Wechsel auf NTSC sitzt bei manchen Spielen das Bild
unten abgeschnitten, das HUD verschwindet halb aus dem Bild. Ursache ist
nicht die Bildlage, sondern die Renderhoehe: Das Spiel zeichnet weiter fuer
PAL (512 Zeilen), waehrend NTSC nur 448 anzeigt.

Typischerweise steht im Executable eine Auswahl zwischen beiden Werten:

    addiu $v1, $zero, 0x1c0   ; 448  (NTSC)
    addiu $a0, $zero, 0x200   ; 512  (PAL)
    lw    $v0, 4($a1)         ; PAL-Flag
    movn  $v1, $a0, $v0       ; auf 512 setzen
    sw    $v1, 0x28($s0)      ; als Renderhoehe ablegen

Ein 'nop' auf das movn/movz laesst den NTSC-Wert stehen. Genau so wurde
"The Simpsons: Hit & Run" (SLES_518.97) geloest.

Dieses Skript sucht solche Stellen und gibt einen fertigen Eintrag fuer
data/game_patches.json aus. Es raet nicht: Es meldet Kandidaten, die von Hand
im Disassembly geprueft und im Spiel getestet werden muessen. Erst dann in der
Datenbank auf "verified": true setzen.

Aufruf:  python tools/find_height_select.py "<image.iso>" [...]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pal2ntsc.platforms import ps2 as P

# NTSC-/PAL-Hoehenpaare, wie sie in libgraph-nahem Code vorkommen
HEIGHT_PAIRS = [
    (448, 512, 'Vollbild  448 / 512'),
    (224, 256, 'Halbbild  224 / 256'),
    (447, 511, 'DH-Wert   447 / 511'),
    (223, 255, 'DH-Wert   223 / 255'),
]
MOVZ, MOVN = 0x0A, 0x0B
STORE_OPS = (0x2B, 0x29)          # sw, sh


def load_elf(path):
    with open(path, 'rb') as f:
        pvd = P.read_pvd(f)
        if not pvd:
            return None
        files = P.list_root(f, pvd)
        cnf = None
        for n, l, s in files:
            if n.upper().startswith('SYSTEM.CNF'):
                f.seek(l * 2048)
                cnf = f.read(s).decode('latin1', 'replace')
        if not cnf:
            return None
        boot, ver, vmode = P.parse_system_cnf(cnf)
        for n, l, s in files:
            if boot and n.upper().startswith(boot.upper()):
                f.seek(l * 2048)
                elf = f.read(s)
                if elf[:4] == b'\x7fELF':
                    return dict(boot=boot, vmode=vmode, elf=elf, lba=l)
    return None


def segments(elf):
    e_phoff = struct.unpack_from('<I', elf, 28)[0]
    ps, pn = struct.unpack_from('<HH', elf, 42)
    out = []
    for i in range(pn):
        o = e_phoff + i * ps
        t, off, va, pa, fsz, msz = struct.unpack_from('<IIIIII', elf, o)
        if t == 1 and fsz:
            out.append((off, va, fsz))
    return out


def find(elf, window=8):
    """Auswahl zwischen NTSC- und PAL-Hoehe, deren Ergebnis abgelegt wird."""
    segs = segments(elf)

    def f2v(o):
        for po, pv, pf in segs:
            if po <= o < po + pf:
                return pv + (o, po)
        return 0

    def w(i):
        return struct.unpack_from('<I', elf, i)[0] if 0 <= i <= len(elf) - 4 else None

    res = []
    for i in range(0, len(elf) - 4, 4):
        ins = w(i)
        if (ins >> 26) != 0 or (ins & 0x3F) not in (MOVZ, MOVN):
            continue
        rd = (ins >> 11) & 31
        rs = (ins >> 21) & 31
        consts = {}
        for k in range(-window, window + 1):
            o = i + 4 * k
            if o == i or not (0 <= o <= len(elf) - 4):
                continue
            a = w(o)
            if (a >> 26) in (0x09, 0x0D) and ((a >> 21) & 31) == 0:
                consts[(a >> 16) & 31] = a & 0xFFFF
        # das movz/movn muss genau zwischen einem NTSC- und einem PAL-Wert waehlen
        lo, hi = consts.get(rd), consts.get(rs)
        if lo is None or hi is None:
            continue
        for ntsc, pal, label in HEIGHT_PAIRS:
            if lo == ntsc and hi == pal:
                # wird das Ergebnis danach gespeichert?
                stored = None
                for k in range(1, 6):
                    a = w(i + 4 * k)
                    if a is None:
                        break
                    if (a >> 26) in STORE_OPS and ((a >> 16) & 31) == rd:
                        stored = a & 0xFFFF
                        break
                res.append(dict(off=i, vaddr=f2v(i), kind='movn' if (ins & 0x3F) == MOVN
                                else 'movz', label=label, ntsc=ntsc, pal=pal,
                                stored_at=stored,
                                find=struct.pack('<I', ins).hex(),
                                replace='00000000'))
                break
    return res


def const_census(elf):
    """Wie oft kommen die Hoehenwerte ueberhaupt als Konstante vor?

    Fehlt der NTSC-Wert ganz, kennt das Spiel keine NTSC-Geometrie, dann ist
    hier nichts zu holen, und das ist eine andere Aussage als 'Muster nicht
    erkannt'.
    """
    from collections import Counter
    c = Counter()
    watch = set()
    for a, b, _ in HEIGHT_PAIRS:
        watch.add(a)
        watch.add(b)
    for i in range(0, len(elf) - 4, 4):
        w = struct.unpack_from('<I', elf, i)[0]
        if (w >> 26) in (0x09, 0x0D) and ((w >> 21) & 31) == 0:
            v = w & 0xFFFF
            if v in watch:
                c[v] += 1
    return c


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    for path in argv:
        print('\n=== %s' % os.path.basename(path))
        try:
            r = load_elf(path)
        except Exception as e:
            print('  Fehler: %s' % e)
            continue
        if not r:
            print('  kein PS2-Image / kein ELF')
            continue
        hits = find(r['elf'])
        print('  %s  VMODE=%s  -> %d Kandidat(en)' % (r['boot'], r['vmode'], len(hits)))
        if not hits:
            c = const_census(r['elf'])
            pairs = []
            for ntsc, pal, label in HEIGHT_PAIRS:
                if c.get(ntsc) or c.get(pal):
                    pairs.append('%s: %dx / %dx' % (label, c.get(ntsc, 0), c.get(pal, 0)))
            if pairs:
                print('     Hoehenkonstanten im Code (NTSC / PAL):')
                for p in pairs:
                    print('       %s' % p)
                print('     -> Werte vorhanden, aber keine Auswahl der bekannten Bauart.')
                print('        Von Hand nachsehen, oder das Spiel hat das Problem nicht.')
            else:
                print('     Keine der bekannten Hoehenkonstanten im Code -')
                print('     das Spiel duerfte hier nicht betroffen sein.')
        for h in hits:
            store = ('wird nach 0x%X gespeichert' % h['stored_at']) if h['stored_at'] is not None \
                    else 'kein direkter Speicherzugriff erkannt'
            print('     vaddr 0x%08X  %s  %s  (%s)'
                  % (h['vaddr'], h['kind'], h['label'], store))
            print('       Eintrag fuer game_patches.json:')
            print('         { "offset": "0x%X", "find": "%s", "replace": "%s" }'
                  % (h['off'], h['find'], h['replace']))
        if hits:
            print('\n  Bitte im Disassembly gegenpruefen und im Spiel testen,')
            print('  bevor der Eintrag auf "verified": true gesetzt wird.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
