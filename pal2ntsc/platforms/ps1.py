"""PlayStation 1: PAL -> NTSC.

Stand der Dinge, offen benannt: Fuer PS1 gibt es (anders als bei PS2 und
GameCube) kein einzelnes, verlaesslich auffindbares Idiom. Der Videomodus
steckt in der statisch gelinkten libgpu, die die GPU-Adresse ueber eine
Zeigervariable anspricht, eine reine Instruktionssuche laeuft ins Leere.
Die historischen Werkzeuge (z.B. PAL4U 2000) arbeiten deshalb mit einer
Handvoll fester Bytesignaturen plus einem Y-Positions-Fix.

Dieses Modul bringt die vollstaendige Infrastruktur mit, Rohsektor-Zugriff,
EXE-Lokalisierung, groessengleiches Patchen samt EDC/ECC-Neuberechnung, und
laedt die Videomodus-Signaturen aus data/ps1_signatures.json. Solange dort
keine verifizierten Muster stehen, meldet die Analyse das ehrlich, statt zu
raten.
"""
import json
import os
import struct

from .common import Patch, GameInfo
from . import cdrom_ecc as ECC
from . import ps1_sig

RAW = 2352
COOKED = 2048

SIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'data', 'ps1_signatures.json')

PAL_PREFIXES = ('SLES', 'SCES', 'SLED', 'SCED')
NTSC_U_PREFIXES = ('SLUS', 'SCUS')
NTSC_J_PREFIXES = ('SLPS', 'SCPS', 'SLPM', 'SCPM')


class RawImage:
    """Read/write access to a PS1 track file, raw (2352) or cooked (2048)."""

    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(path)
        with open(path, 'rb') as f:
            head = f.read(16)
        self.raw = head[:12] == ECC.SYNC
        self.sector_size = RAW if self.raw else COOKED
        self.nsec = self.size // self.sector_size

    def _open(self, mode='rb'):
        return open(self.path, mode)

    def read_sector_raw(self, lba):
        with self._open() as f:
            f.seek(lba * self.sector_size)
            return f.read(self.sector_size)

    def data_offset(self, lba):
        """File offset of the user-data area of this sector."""
        if not self.raw:
            return lba * COOKED
        s = self.read_sector_raw(lba)
        return lba * RAW + ECC.data_offset(bytearray(s))

    def read(self, lba, length):
        out = bytearray()
        with self._open() as f:
            while len(out) < length:
                f.seek(lba * self.sector_size)
                s = f.read(self.sector_size)
                if len(s) < self.sector_size:
                    break
                if self.raw:
                    b = bytearray(s)
                    o = ECC.data_offset(b)
                    n = ECC.data_length(b)
                    out += s[o:o + n]
                else:
                    out += s
                lba += 1
        return bytes(out[:length])

    def sector_patch(self, lba, offset_in_data, new_bytes):
        """Build a whole-sector Patch so EDC/ECC stay consistent.

        The journal stores original and patched as complete raw sectors; that
        keeps the generic in-place/undo machinery working unchanged.
        """
        raw = bytearray(self.read_sector_raw(lba))
        if len(raw) != self.sector_size:
            raise ValueError('Sektor %d unvollstaendig' % lba)
        original = bytes(raw)
        if self.raw:
            o = ECC.data_offset(raw)
            raw[o + offset_in_data:o + offset_in_data + len(new_bytes)] = new_bytes
            ECC.rebuild(raw)
        else:
            raw[offset_in_data:offset_in_data + len(new_bytes)] = new_bytes
        return lba * self.sector_size, original, bytes(raw)


def _read_dir(img, lba, size):
    """Eintraege eines ISO9660-Verzeichnisses: (name, lba, size, flags)."""
    d = img.read(lba, max(size, COOKED))
    out = []
    i = 0
    while i < len(d):
        L = d[i]
        if L == 0:
            i = (i // COOKED + 1) * COOKED
            if i >= len(d):
                break
            continue
        e = d[i:i + L]
        if len(e) < 33:
            break
        nl = e[32]
        out.append((e[33:33 + nl].decode('latin1', 'replace'),
                    int.from_bytes(e[2:6], 'little'),
                    int.from_bytes(e[10:14], 'little'),
                    e[25]))
        i += L
    return out


def _iso_root(img, max_depth=4):
    """Dateiliste des Images, Unterverzeichnisse eingeschlossen.

    Manche Spiele legen ihr Executable nicht ins Wurzelverzeichnis, sondern in
    einen Unterordner (Tekken 3: \\TEKKEN3\\SCES_012.37). Ohne Rekursion
    findet man dort weder EXE noch Videomodus.
    """
    pvd = img.read(16, COOKED)
    if pvd[1:6] != b'CD001':
        return None, None
    root = pvd[156:190]
    lba = int.from_bytes(root[2:6], 'little')
    ln = int.from_bytes(root[10:14], 'little')
    out = []
    seen = set()

    def walk(l, s, depth):
        if depth > max_depth or l in seen:
            return
        seen.add(l)
        for name, el, es, flags in _read_dir(img, l, s):
            if name in ('\x00', '\x01'):        # '.' und '..'
                continue
            if flags & 0x02:                    # Verzeichnis
                walk(el, es, depth + 1)
            else:
                out.append((name, el, es))

    walk(lba, ln, 0)
    return pvd, out


def _load_signatures():
    if not os.path.exists(SIG_FILE):
        return []
    try:
        with open(SIG_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return []
    sigs = []
    for s in raw.get('signatures', []):
        if not s.get('verified', False):
            continue
        try:
            sigs.append(dict(name=s['name'],
                             find=bytes.fromhex(s['find']),
                             replace=bytes.fromhex(s['replace']),
                             title=s.get('title', s['name']),
                             note=s.get('note', ''),
                             optional=s.get('optional', False)))
        except Exception:
            continue
    return sigs


def parse_boot_line(line):
    r"""Dateinamen aus einer BOOT/BOOT2-Zeile holen.

    Vorkommende Schreibweisen:
        BOOT  = cdrom:\SLES_123.45;1
        BOOT  = cdrom:SLES_123.45;1      (ohne Backslash)
        BOOT2 = cdrom0:\SLUS_123.45;1
    """
    v = line.split('=', 1)[1] if '=' in line else line
    v = v.strip().strip('"')
    # alles vor dem letzten Trenner (Backslash, Slash, Doppelpunkt) verwerfen
    for sep in ('\\', '/', ':'):
        if sep in v:
            v = v.rsplit(sep, 1)[-1]
    return v.strip().split(';')[0].strip()


def region_of(boot_id):
    b = (boot_id or '').upper().replace('_', '').replace('.', '')
    for p in PAL_PREFIXES:
        if b.startswith(p):
            return 'PAL'
    for p in NTSC_U_PREFIXES:
        if b.startswith(p):
            return 'NTSC-U'
    for p in NTSC_J_PREFIXES:
        if b.startswith(p):
            return 'NTSC-J'
    return '?'


def probe(path):
    img = RawImage(path)
    if img.nsec < 20:
        return None
    pvd, files = _iso_root(img)
    if not pvd:
        return None
    cnf = None
    for n, l, s in files:
        if n.upper().startswith('SYSTEM.CNF'):
            cnf = img.read(l, s).decode('latin1', 'replace')
    boot = None
    if cnf:
        for line in cnf.splitlines():
            if line.upper().strip().startswith('BOOT'):
                boot = parse_boot_line(line)
    if not boot:
        for n, l, s in files:
            if n.upper().endswith('.EXE;1'):
                boot = n.split(';')[0]
                break
    if not boot:
        return None
    volume = pvd[40:72].decode('latin1').strip()
    info = GameInfo(platform='ps1', game_id=boot, title=volume or boot,
                    region=region_of(boot),
                    extra=dict(raw=img.raw, sector_size=img.sector_size,
                               sectors=img.nsec))
    ent = None
    for n, l, s in files:
        if n.upper().startswith(boot.upper()):
            ent = (n, l, s)
    if not ent:
        info.add_note('ps1_note_no_boot', boot=boot)
        return info
    n, l, s = ent
    exe = img.read(l, s)
    info.extra.update(exe_name=n, exe_lba=l, exe_size=s)
    if exe[:8] != b'PS-X EXE':
        info.add_note('ps1_note_not_exe')
        return info
    t_addr, t_size = struct.unpack_from('<II', exe, 0x18)
    info.extra.update(load_addr=t_addr, text_size=t_size)

    # --- SetVideoMode aus libgpu (Methode PALNTSC 1999, siehe ps1_sig.py)
    code_base = 0x800
    code = exe[code_base:code_base + t_size]
    hits = ps1_sig.find_setvideomode(code)
    info.extra['sig_hits'] = len(hits)
    info.extra['sig_confident'] = sum(1 for h in hits if h.get('confident'))

    for h in hits:
        byte_in_exe = code_base + h['code_off']
        lba = l + byte_in_exe // COOKED
        off_in_sec = byte_in_exe % COOKED
        if off_in_sec + 4 > COOKED:
            info.add_note('ps1_note_crosses', name='SetVideoMode')
            continue
        new_ins = struct.pack('<I', ps1_sig.patched_word(h['ins']))
        off, orig, patched = img.sector_patch(lba, off_in_sec, new_ins)
        sure = h.get('confident', False)
        info.patches.append(Patch(
            name='ps1_setvideomode_%06x' % h['code_off'],
            offset=off,
            original=orig,
            patched=patched,
            title_key='ps1_svm_title' if sure else 'ps1_svm_title_maybe',
            note_key='ps1_svm_note',
            note_args=dict(var=h['var_addr'], vaddr=t_addr + h['code_off']),
            note_suffix=('ps1_sig_note_suffix', dict(lba=lba)),
            optional=not sure,
            risky=not sure,
        ))
    sure = [h for h in hits if h.get('confident')]
    if len(sure) > 1:
        info.add_note('ps1_note_multi_a', n=len(sure))
    elif hits and not sure:
        info.add_note('ps1_note_candidates', n=len(hits))
    elif not hits:
        info.add_note('ps1_note_no_sig')

    if info.region != 'PAL':
        info.add_note('ps1_note_not_pal', region=info.region)

    # --- zusaetzliche feste Bytesignaturen aus data/ps1_signatures.json
    for sig in _load_signatures():
        start = 0
        while True:
            idx = exe.find(sig['find'], start)
            if idx < 0:
                break
            start = idx + 1
            lba = l + idx // COOKED
            off_in_sec = idx % COOKED
            if off_in_sec + len(sig['find']) > COOKED:
                info.add_note('ps1_note_crosses', name=sig['name'])
                continue
            off, orig, patched = img.sector_patch(lba, off_in_sec, sig['replace'])
            info.patches.append(Patch(
                name='ps1_' + sig['name'],
                offset=off, original=orig, patched=patched,
                title_key='ps1_sig_title', title_args=dict(title=sig['title']),
                note_key='ps1_sig_note', note_args=dict(note=sig['note']),
                note_suffix=('ps1_sig_note_suffix', dict(lba=lba)),
                optional=sig['optional'],
            ))
    return info
