"""PlayStation 2: PAL -> NTSC.

Hebel ist sceGsResetGraph(mode, interlace, omode, ffmd) aus Sonys libgraph.
Der dritte Parameter (omode) waehlt den Videostandard: 2 = NTSC, 3 = PAL.
Im Prolog wird er per 'sra rd, a2, 16' vorzeichenrichtig aus dem Argument
geholt; wir ersetzen das durch 'addiu rd, zero, 2' und nageln so NTSC fest.

Die Funktion wird ueber ihren GS_CSR-Reset erkannt (Schreiben von 0x200 nach
0x12001000), nicht ueber Symbole, das funktioniert auch ohne Debug-Infos.
Gegen die PAL-Sammlung des Autors getestet: 37 von 40 Titeln erkannt.
"""
import struct

from .common import Patch, GameInfo, vmode_line_patch

REG = ['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
       's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra']

SECTOR = 2048
OMODE_NTSC = 2
OMODE_PAL = 3


# ---------------------------------------------------------------- ISO9660 ---
def read_pvd(f):
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    return pvd if pvd[1:6] == b'CD001' else None


def list_root(f, pvd):
    root = pvd[156:190]
    lba = int.from_bytes(root[2:6], 'little')
    ln = int.from_bytes(root[10:14], 'little')
    f.seek(lba * SECTOR)
    d = f.read(max(ln, SECTOR))
    out = []
    i = 0
    while i < len(d):
        L = d[i]
        if L == 0:
            i = (i // SECTOR + 1) * SECTOR
            if i >= len(d):
                break
            continue
        e = d[i:i + L]
        nl = e[32]
        out.append((e[33:33 + nl].decode('latin1', 'replace'),
                    int.from_bytes(e[2:6], 'little'),
                    int.from_bytes(e[10:14], 'little')))
        i += L
    return out


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


def parse_system_cnf(text):
    boot = ver = vmode = None
    for line in text.splitlines():
        u = line.upper().strip()
        if u.startswith('BOOT2') or u.startswith('BOOT '):
            boot = parse_boot_line(line)
        elif u.startswith('VMODE'):
            vmode = line.split('=', 1)[1].strip()
        elif u.startswith('VER'):
            ver = line.split('=', 1)[1].strip()
    return boot, ver, vmode


# -------------------------------------------------------------- ELF search ---
def _segments(elf):
    if elf[:4] != b'\x7fELF':
        return []
    e_phoff = struct.unpack_from('<I', elf, 28)[0]
    e_phentsize, e_phnum = struct.unpack_from('<HH', elf, 42)
    segs = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        if o + 32 > len(elf):
            break
        t, off, va, pa, fsz, msz = struct.unpack_from('<IIIIII', elf, o)
        if t == 1 and fsz:
            segs.append((off, va, fsz))
    return segs


def find_gsresetgraph(elf):
    """Return list of dicts describing the omode instruction in sceGsResetGraph."""
    segs = _segments(elf)
    res = []
    for po, pv, pf in segs:
        blk = elf[po:po + pf]
        n = len(blk) - 4
        for i in range(0, n, 4):
            ins = struct.unpack_from('<I', blk, i)[0]
            if (ins >> 26) != 0x0F or (ins & 0xFFFF) != 0x1200:   # lui rX,0x1200
                continue
            rX = (ins >> 16) & 31
            if not _has_ori(blk, i, n, rX, 0x1000):               # -> 0x12001000
                continue
            if not _has_imm(blk, i, n, 0x200):                    # CSR reset value
                continue
            fstart = _prologue(blk, i)
            if fstart is None:
                continue
            hit = _omode_insn(blk, fstart, i, po, pv)
            if hit:
                res.append(hit)
    return res


def _has_ori(blk, i, n, reg, val):
    for k in range(1, 9):
        o = i + 4 * k
        if o > n:
            return False
        x = struct.unpack_from('<I', blk, o)[0]
        if (x >> 26) == 0x0D and ((x >> 21) & 31) == reg and \
           ((x >> 16) & 31) == reg and (x & 0xFFFF) == val:
            return True
    return False


def _has_imm(blk, i, n, val):
    for k in range(-8, 12):
        o = i + 4 * k
        if 0 <= o <= n:
            x = struct.unpack_from('<I', blk, o)[0]
            if (x >> 26) in (0x09, 0x0D) and (x & 0xFFFF) == val:
                return True
    return False


def _prologue(blk, i):
    """walk back to 'addiu sp,sp,-N'"""
    for k in range(1, 80):
        o = i - 4 * k
        if o < 0:
            return None
        b = struct.unpack_from('<I', blk, o)[0]
        if (b >> 26) == 0x09 and ((b >> 21) & 31) == 29 and \
           ((b >> 16) & 31) == 29 and (b & 0x8000):
            return o
    return None


def _omode_insn(blk, fstart, stop, po, pv):
    """find 'sra rd,a2,16' (original) or 'addiu rd,zero,2|3' (already patched)"""
    for k in range(0, 40):
        o = fstart + 4 * k
        if o >= stop:
            break
        b = struct.unpack_from('<I', blk, o)[0]
        # sra rd, a2, 16
        if (b >> 26) == 0 and (b & 0x3F) == 3 and ((b >> 16) & 31) == 6 and \
           ((b >> 6) & 31) == 16:
            rd = (b >> 11) & 31
            return dict(elf_off=po + o, vaddr=pv + o, reg=rd, regname=REG[rd],
                        original=struct.pack('<I', b),
                        patched=struct.pack('<I', 0x24000002 | (rd << 16)),
                        state='original')
        # addiu rd, zero, imm  -> someone already forced a mode here
        if (b >> 26) == 0x09 and ((b >> 21) & 31) == 0 and (b & 0xFFFF) in (2, 3):
            rd = (b >> 16) & 31
            if REG[rd].startswith('s'):
                return dict(elf_off=po + o, vaddr=pv + o, reg=rd, regname=REG[rd],
                            original=struct.pack('<I', b),
                            patched=struct.pack('<I', 0x24000002 | (rd << 16)),
                            state='forced-%d' % (b & 0xFFFF))
    return None


# ------------------------------------------------------------------ public ---
def probe(path):
    """Return GameInfo if this is a PS2 disc image, else None."""
    with open(path, 'rb') as f:
        pvd = read_pvd(f)
        if not pvd:
            return None
        files = list_root(f, pvd)
        cnf_txt = None
        for n, l, s in files:
            if n.upper().startswith('SYSTEM.CNF'):
                f.seek(l * SECTOR)
                cnf_txt = f.read(s).decode('latin1', 'replace')
        if not cnf_txt:
            return None
        boot, ver, vmode = parse_system_cnf(cnf_txt)
        if not boot:
            return None
        volume = pvd[40:72].decode('latin1').strip()
        info = GameInfo(platform='ps2', game_id=boot, title=volume,
                        region='PAL' if (vmode or '').upper() == 'PAL' else
                               ('NTSC' if vmode else '?'),
                        extra=dict(vmode=vmode, version=ver))
        # locate boot ELF
        ent = None
        for n, l, s in files:
            if n.upper().startswith(boot.upper()):
                ent = (n, l, s)
        if not ent:
            info.add_note('ps2_note_no_elf', boot=boot)
            return info
        n, l, s = ent
        f.seek(l * SECTOR)
        elf = f.read(s)
        info.extra['elf_name'] = n
        info.extra['elf_lba'] = l
        info.extra['elf_size'] = s
        if elf[:4] != b'\x7fELF':
            info.add_note('ps2_note_not_elf')
            return info
        if s < 300 * 1024:
            info.add_note('ps2_note_small_elf', kb=s // 1024)
        hits = find_gsresetgraph(elf)
        info.extra['hits'] = hits
        base = l * SECTOR
        for h in hits:
            iso_off = base + h['elf_off']
            if h['state'] == 'original':
                info.patches.append(Patch(
                    name='ps2_gsresetgraph_ntsc',
                    offset=iso_off,
                    original=h['original'],
                    patched=h['patched'],
                    title_key='ps2_patch_title',
                    note_key='ps2_patch_note',
                    note_args=dict(reg=h['regname'], vaddr=h['vaddr']),
                ))
            elif h['state'] == 'forced-2':
                info.add_note('ps2_note_already_ntsc')
            elif h['state'] == 'forced-3':
                info.add_note('ps2_note_forced_pal')
                info.patches.append(Patch(
                    name='ps2_gsresetgraph_ntsc',
                    offset=iso_off,
                    original=h['original'],
                    patched=h['patched'],
                    title_key='ps2_forced_pal_title',
                    note_key='ps2_forced_pal_note',
                    note_args=dict(reg=h['regname'], vaddr=h['vaddr']),
                ))
        if not hits:
            info.add_note('ps2_note_no_hits')
        # spielspezifische Patches (z.B. Bildlage), siehe gamepatch.py
        try:
            from ..gamepatch import build_patches
            extra = build_patches(boot, elf, l * SECTOR)
            if extra:
                info.patches.extend(extra)
                info.extra['game_patches'] = len(extra)
        except Exception:
            pass
        # SYSTEM.CNF VMODE (laengengleich, siehe common.vmode_line_patch)
        if vmode and vmode.upper() == 'PAL':
            for n2, l2, s2 in files:
                if n2.upper().startswith('SYSTEM.CNF'):
                    f.seek(l2 * SECTOR)
                    raw = f.read(s2)
                    p = vmode_line_patch(raw, l2 * SECTOR, 'NTSC',
                                         name='ps2_systemcnf_vmode')
                    if p:
                        p.name = 'ps2_systemcnf_vmode'
                        info.patches.append(p)
                    else:
                        info.add_note('ps2_note_vmode_skip')
        return info
