"""Microsoft Xbox: Region-Kennung im XBE.

Wichtige Einordnung: Anders als bei PS1/PS2/GameCube steckt der Videostandard
der Xbox NICHT im Spiel-Image. Die Konsole liefert ihn aus dem EEPROM
(Dashboard-Einstellung "60Hz"/Videonorm); Spiele fragen ihn ueber
XGetVideoStandard()/XGetVideoFlags() ab. Ein ISO-Patch kann das nicht
zuverlaessig ersetzen, der richtige Hebel ist die EEPROM-/Emulator-
Einstellung (in xemu: Videonorm auf NTSC-M umstellen).

Was dieses Modul kann: die Region-Kennung im XBE-Zertifikat aufweiten, damit
ein PAL-Titel nicht an einer Regionspruefung scheitert, und melden, ob das
Spiel eigene 50/60Hz-Strings mitbringt.
"""
import struct

from .common import Patch, GameInfo

SEC = 2048
VOL_SECTOR = 32
MAGIC = b'MICROSOFT*XBOX*MEDIA'
# Redump-Images enthalten vorne die Video-Partition, xiso-Rebuilds nicht.
BASES = [0, 0x18300000, 0xFD90000, 0x2080000]

REGION_BITS = [(0x00000001, 'NA'), (0x00000002, 'Japan'),
               (0x00000004, 'Rest-of-World'), (0x80000000, 'Manufacturing')]
REGION_ALL = 0x00000007


def _find_base(f):
    for b in BASES:
        f.seek(b + VOL_SECTOR * SEC)
        if f.read(20) == MAGIC:
            return b
    return None


def _read_dir(f, base, sector, size):
    f.seek(base + sector * SEC)
    data = f.read(((size + SEC - 1) // SEC) * SEC)
    out = []
    seen = set()

    def walk(off):
        if off in seen or off * 4 + 14 > len(data):
            return
        seen.add(off)
        l, r = struct.unpack_from('<HH', data, off * 4)
        start, fsize, attr = struct.unpack_from('<IIB', data, off * 4 + 4)
        nlen = data[off * 4 + 13]
        name = data[off * 4 + 14:off * 4 + 14 + nlen].decode('latin1', 'replace')
        if l and l != 0xFFFF:
            walk(l)
        out.append((name, start, fsize, attr))
        if r and r != 0xFFFF:
            walk(r)

    try:
        walk(0)
    except RecursionError:
        pass
    return out


def _region_names(v):
    n = [name for bit, name in REGION_BITS if v & bit]
    return ', '.join(n) if n else 'keine'


def probe(path):
    with open(path, 'rb') as f:
        base = _find_base(f)
        if base is None:
            return None
        f.seek(base + VOL_SECTOR * SEC + 20)
        rsec, rsize = struct.unpack('<II', f.read(8))
        files = _read_dir(f, base, rsec, rsize)
        xbe = None
        for n, s, z, a in files:
            if n.lower() == 'default.xbe':
                xbe = (n, s, z)
                break
        if not xbe:
            return None
        n, s, z = xbe
        iso_off = base + s * SEC
        f.seek(iso_off)
        data = f.read(z)
        info = GameInfo(platform='xbox', game_id='?', title='?',
                        extra=dict(base=base, xbe_off=iso_off, xbe_size=z))
        if data[:4] != b'XBEH':
            info.add_note('xbox_note_bad_xbe')
            return info
        img_base = struct.unpack_from('<I', data, 0x104)[0]
        cert_addr = struct.unpack_from('<I', data, 0x118)[0]
        coff = cert_addr - img_base
        if coff < 0 or coff + 0xB0 > len(data):
            info.add_note('xbox_note_no_cert')
            return info
        title = data[coff + 12:coff + 12 + 80].decode('utf-16-le', 'replace')
        title = title.split('\x00')[0].strip()
        title_id = struct.unpack_from('<I', data, coff + 8)[0]
        region = struct.unpack_from('<I', data, coff + 0xA0)[0]
        info.game_id = '%08X' % title_id
        info.title = title
        info.region = _region_names(region)
        info.extra['region_value'] = region
        region_off = iso_off + coff + 0xA0

        if region != REGION_ALL:
            info.patches.append(Patch(
                name='xbox_region_all',
                offset=region_off,
                original=struct.pack('<I', region),
                patched=struct.pack('<I', REGION_ALL),
                title_key='xbox_region_title',
                title_args=dict(cur=_region_names(region)),
                note_key='xbox_region_note',
                note_args=dict(cur=region, new=REGION_ALL),
            ))
        else:
            info.add_note('xbox_note_all_regions')

        hints = {}
        for pat in (b'60Hz', b'50Hz', b'60 Hz', b'50 Hz',
                    b'6\x000\x00H\x00z\x00', b'5\x000\x00H\x00z\x00'):
            c = data.count(pat)
            if c:
                hints[pat.decode('latin1').replace('\x00', '')] = c
        if hints:
            info.add_note('xbox_note_hz_strings',
                          hits=', '.join('%s x%d' % (k, v) for k, v in hints.items()))

        info.add_note('xbox_note_eeprom')
        if base == 0:
            info.extra['layout'] = 'xiso-rebuild'
        else:
            info.extra['layout'] = 'redump (base 0x%X)' % base
        return info
