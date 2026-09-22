"""Nintendo GameCube: PAL -> NTSC / PAL60.

Hebel ist die GXRModeObj-Tabelle im main.dol. Das SDK legt dort fuer jeden
Videostandard eine 60-Byte-Struktur ab (NTSC, MPAL, PAL, EURGB60). Ein
PAL-Spiel waehlt zur Laufzeit die PAL-Struktur, wir ueberschreiben deren
Inhalt mit dem der EURGB60-Struktur (640x480 @60Hz), die im selben DOL bereits
vorhanden ist. Dadurch bleibt die Spiellogik unangetastet und wir muessen keine
Timing-Werte erfinden: die Zielwerte stammen aus dem Spiel selbst.

Zusaetzlich optional: Country-Code in bi2.bin und die Region-Kennung der
Game-ID. Beides ist nicht noetig fuer 60Hz, hilft aber bei Region-Pruefungen.
"""
import struct

from .common import Patch, GameInfo

GC_MAGIC = 0xC2339F3D          # bei 0x1C
WII_MAGIC = 0x5D1C9EA3         # bei 0x18
MODE_SIZE = 0x3C               # sizeof(GXRModeObj)

# viTVmode = (format << 2) | interlace-mode
TV_NAMES = {
    0: 'NTSC_INT', 1: 'NTSC_DS', 2: 'NTSC_PROG', 3: 'NTSC_3D',
    4: 'PAL_INT', 5: 'PAL_DS',
    8: 'MPAL_INT', 9: 'MPAL_DS',
    20: 'EURGB60_INT', 21: 'EURGB60_DS', 22: 'EURGB60_PROG',
}
PAL_MODES = (4, 5)
NTSC60_MODES = (20, 21, 22, 0, 1, 2)

COUNTRY = {0: 'JAP', 1: 'USA', 2: 'PAL'}


def _dol_bounds(f, dol_off):
    f.seek(dol_off)
    h = f.read(0x100)
    if len(h) < 0x100:
        return 0
    offs = struct.unpack('>18I', h[0:72])
    sizes = struct.unpack('>18I', h[0x90:0x90 + 72])
    ends = [o + s for o, s in zip(offs, sizes) if o]
    return max(ends) if ends else 0


def _scan_modes(dol):
    """Find GXRModeObj structures by their very regular field layout."""
    found = []
    for i in range(0, len(dol) - MODE_SIZE, 4):
        tv = struct.unpack_from('>I', dol, i)[0]
        if tv not in TV_NAMES:
            continue
        fbw, efb, xfb, xorg, yorg, viw, vih = struct.unpack_from('>7H', dol, i + 4)
        if fbw != 640 or viw not in (640, 704):
            continue
        if efb not in (240, 264, 448, 456, 480, 528) or xfb not in (240, 264, 448, 456, 480, 528):
            continue
        if vih not in (240, 264, 448, 456, 480, 528):
            continue
        found.append(dict(off=i, tv=tv, name=TV_NAMES[tv], fbw=fbw, efb=efb,
                          xfb=xfb, xorg=xorg, yorg=yorg, viw=viw, vih=vih))
    return found


def _menu_hint(dol):
    """Cheap evidence that the game has its own 50/60Hz menu."""
    hits = {}
    for pat in (b'60Hz', b'50Hz', b'60 Hz', b'50 Hz', b'PAL60', b'PAL 60',
                b'Bildwiederhol', b'Bildfrequenz'):
        n = dol.count(pat)
        if n:
            hits[pat.decode()] = n
    return hits


def probe(path):
    with open(path, 'rb') as f:
        head = f.read(0x460)
        if len(head) < 0x460:
            return None
        if struct.unpack_from('>I', head, 0x18)[0] == WII_MAGIC:
            info = GameInfo(platform='wii', game_id=head[:6].decode('latin1', 'replace'),
                            title=head[0x20:0x60].split(b'\x00')[0].decode('latin1', 'replace'),
                            region='?')
            info.add_note('wii_note')
            return info
        if struct.unpack_from('>I', head, 0x1C)[0] != GC_MAGIC:
            return None
        gid = head[:6].decode('latin1', 'replace')
        title = head[0x20:0x60].split(b'\x00')[0].decode('latin1', 'replace').strip()
        region_char = gid[3] if len(gid) > 3 else '?'
        country = struct.unpack_from('>I', head, 0x458)[0]
        dol_off, fst_off, fst_size = struct.unpack_from('>III', head, 0x420)
        info = GameInfo(platform='gamecube', game_id=gid, title=title,
                        region={'P': 'PAL', 'E': 'NTSC-U', 'J': 'NTSC-J',
                                'D': 'PAL-DE', 'F': 'PAL-FR', 'S': 'PAL-ES',
                                'I': 'PAL-IT'}.get(region_char, region_char),
                        extra=dict(country=country,
                                   country_name=COUNTRY.get(country, str(country)),
                                   dol_off=dol_off))
        dol_size = _dol_bounds(f, dol_off)
        if not dol_size:
            info.add_note('gc_note_no_dol')
            return info
        f.seek(dol_off)
        dol = f.read(dol_size)
        modes = _scan_modes(dol)
        info.extra['modes'] = modes
        info.extra['menu_hint'] = _menu_hint(dol)

        pal = [m for m in modes if m['tv'] in PAL_MODES]
        src = [m for m in modes if m['tv'] == 20]                 # EURGB60_INT
        if not src:
            src = [m for m in modes if m['tv'] == 0]              # NTSC_INT
        if pal and src:
            s = src[0]
            donor = dol[s['off']:s['off'] + MODE_SIZE]
            for m in pal:
                cur = dol[m['off']:m['off'] + MODE_SIZE]
                if cur == donor:
                    info.add_note('gc_note_already', dst=s['name'])
                    continue
                info.patches.append(Patch(
                    name='gc_vimode_%s_to_%s' % (m['name'].lower(), s['name'].lower()),
                    offset=dol_off + m['off'],
                    original=cur,
                    patched=donor,
                    title_key='gc_patch_title',
                    title_args=dict(src=m['name'], dst=s['name'], w=s['viw'], h=s['vih']),
                    note_key='gc_patch_note',
                    note_args=dict(dst=s['name'], soff=s['off'], doff=m['off']),
                ))
        elif not pal:
            info.add_note('gc_note_no_pal')
        elif not src:
            info.add_note('gc_note_no_src')

        # optional: Country-Code in bi2.bin
        if country == 2:
            info.patches.append(Patch(
                name='gc_country_usa',
                offset=0x458,
                original=struct.pack('>I', 2),
                patched=struct.pack('>I', 1),
                title_key='gc_country_title',
                note_key='gc_country_note',
                optional=True,
            ))
        # optional: Game-ID Regionsbuchstabe
        if region_char in 'PDFSIH':
            info.patches.append(Patch(
                name='gc_gameid_region',
                offset=0x03,
                original=region_char.encode('latin1'),
                patched=b'E',
                title_key='gc_gameid_title',
                title_args=dict(gid=gid, new=gid[:3] + 'E' + gid[4:]),
                note_key='gc_gameid_note',
                optional=True,
                risky=True,
            ))
        hints = info.extra['menu_hint']
        if hints:
            info.add_note('gc_menu_hint',
                          hits=', '.join('%s x%d' % (k, v) for k, v in hints.items()))
        return info
