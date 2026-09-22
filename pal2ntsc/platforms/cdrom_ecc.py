"""EDC/ECC fuer CD-ROM-Rohsektoren (2352 Byte), nach ECMA-130.

PS1-Images liegen fast immer als Rohsektoren vor. Aendert man dort Nutzdaten,
passen EDC-Pruefsumme und Reed-Solomon-Paritaeten nicht mehr; echte Hardware
und strengere Emulatoren melden dann Lesefehler. Dieses Modul rechnet beides
nach einer Aenderung neu.

Sektorlayout
  Mode 1        : sync 0..11 | header 12..15 | data 16..2063 | EDC 2064..2067
                  | 8x00 2068..2075 | P 2076..2247 | Q 2248..2351
  Mode 2 Form 1 : sync | header | subheader 16..23 | data 24..2071
                  | EDC 2072..2075 | P 2076..2247 | Q 2248..2351
  Mode 2 Form 2 : data 24..2347 | EDC 2348..2351 (keine ECC)

Bei Mode 2 wird fuer die ECC-Rechnung der Header (12..15) als Null behandelt.
"""

SYNC = bytes([0x00] + [0xFF] * 10 + [0x00])

# ---------------------------------------------------------------- EDC ------
_EDC_POLY = 0xD8018001          # reflected form of x^32+x^31+x^16+x^15+x^4+x^3+x+1
_edc_table = []
for i in range(256):
    edc = i
    for _ in range(8):
        edc = (edc >> 1) ^ (_EDC_POLY if edc & 1 else 0)
    _edc_table.append(edc)


def edc_compute(data):
    edc = 0
    for b in data:
        edc = (edc >> 8) ^ _edc_table[(edc ^ b) & 0xFF]
    return edc & 0xFFFFFFFF


# ---------------------------------------------------------------- ECC ------
# GF(2^8), primitive polynomial x^8 + x^4 + x^3 + x^2 + 1  (0x11D)
_gf_log = [0] * 256
_gf_exp = [0] * 256
_x = 1
for _i in range(255):
    _gf_exp[_i] = _x
    _gf_log[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
_gf_exp[255] = 0


def _gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _gf_exp[(_gf_log[a] + _gf_log[b]) % 255]


# Tabellen des P/Q-Paritaetsgenerators (ECMA-130 Annex A).
# f[i] = i*2 im Galois-Feld, b ist die dazu passende Rueckabbildung.
_ecc_f = [0] * 256
_ecc_b = [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    _ecc_f[_i] = _j
    _ecc_b[_i ^ _j] = _i


def _ecc_block(sector, major_count, minor_count, major_mult, minor_inc, dest_off):
    """Generate one parity block (P or Q) into sector[dest_off:].

    Operates on bytes 12..2075 of the sector (header+subheader+data+EDC).
    """
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        la = lb = 0
        for _ in range(minor_count):
            b = sector[12 + index]
            index += minor_inc
            if index >= size:
                index -= size
            la ^= b
            lb ^= b
            la = _ecc_f[la]
        la = _ecc_b[_ecc_f[la] ^ lb]
        sector[dest_off + major] = la
        sector[dest_off + major + major_count] = la ^ lb


def ecc_generate(sector):
    """Fill P (2076..2247) and Q (2248..2351)."""
    _ecc_block(sector, 86, 24, 2, 86, 2076)     # P
    _ecc_block(sector, 52, 43, 86, 88, 2248)    # Q


def sector_mode(sector):
    return sector[15]


def sector_form(sector):
    """For mode 2: 1 or 2, taken from the subheader submode bit 5."""
    if sector_mode(sector) != 2:
        return 0
    return 2 if (sector[18] & 0x20) else 1


def data_offset(sector):
    m = sector_mode(sector)
    return 24 if m == 2 else 16


def data_length(sector):
    m = sector_mode(sector)
    if m == 1:
        return 2048
    if m == 2:
        return 2324 if sector_form(sector) == 2 else 2048
    return 2048


def rebuild(sector):
    """Recompute EDC + ECC in place. sector must be a mutable 2352-byte buffer."""
    if len(sector) != 2352:
        raise ValueError('Rohsektor muss 2352 Byte haben, hat %d' % len(sector))
    mode = sector_mode(sector)
    if mode == 1:
        sector[2064:2068] = edc_compute(sector[0:2064]).to_bytes(4, 'little')
        sector[2068:2076] = b'\x00' * 8
        keep = bytes(sector[12:16])
        sector[12:16] = b'\x00\x00\x00\x00'      # header excluded from ECC
        ecc_generate(sector)
        sector[12:16] = keep
    elif mode == 2:
        form = sector_form(sector)
        if form == 1:
            sector[2072:2076] = edc_compute(sector[16:2072]).to_bytes(4, 'little')
            keep = bytes(sector[12:16])
            sector[12:16] = b'\x00\x00\x00\x00'
            ecc_generate(sector)
            sector[12:16] = keep
        else:
            sector[2348:2352] = edc_compute(sector[16:2348]).to_bytes(4, 'little')
            # Form 2 carries no ECC
    return sector


def verify(sector):
    """True if the sector's stored EDC matches a freshly computed one."""
    mode = sector_mode(sector)
    if mode == 1:
        stored = int.from_bytes(sector[2064:2068], 'little')
        return stored == edc_compute(sector[0:2064])
    if mode == 2:
        if sector_form(sector) == 1:
            stored = int.from_bytes(sector[2072:2076], 'little')
            return stored == edc_compute(sector[16:2072])
        stored = int.from_bytes(sector[2348:2352], 'little')
        return stored == 0 or stored == edc_compute(sector[16:2348])
    return True
