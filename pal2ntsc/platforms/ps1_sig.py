"""Erkennung von SetVideoMode in PS1-Executables.

Grundlage ist die Methode des Werkzeugs PALNTSC (KEuBo, 1999), dessen README
den Eingriff im Klartext zeigt:

    LUI  v0,0x8007
    LW   v0,0x2594
    LUI  at,0x8007
    JR   ra
  * SW   a0,0x2594   <-- PATCH -->   SW  zero,0x2594

Sonys libgpu haelt den Videomodus in einer globalen Variablen; SetVideoMode
schreibt den Parameter dorthin. Wird stattdessen $zero geschrieben, landet
immer 0 = NTSC in der Variablen, unabhaengig davon, was das Spiel uebergibt.
Adresse und Offset (HI/LO) unterscheiden sich je Spiel, die Struktur nicht,
deshalb wird nach dem Muster gesucht, nicht nach festen Bytes.

Zwei Anordnungen kommen vor (verschiedene SDK-Staende):

  A  SetVideoMode und GetVideoMode als getrennte Funktionen, direkt
     hintereinander, auf dieselbe Variable:
         lui at,HI ; jr ra ; sw a0,LO(at) ; lui v0,HI ; lw v0,LO(v0) ; jr ra
     Sehr kennzeichnend, gegen 108 Executables geprueft: 50 Titel genau ein
     Treffer, 29 Titel zwei bis drei (Spiele, die libgpu je Overlay einbinden).

  B  SetVideoMode gibt den alten Wert zurueck, alles in einer Funktion:
         lui v0,HI ; lw v0,LO(v0) ; lui at,HI ; sw a0,LO(at) ; jr ra
     Das ist zugleich das allgemeine Muster jedes "lesen und setzen"-Paars der
     libgpu. In der Stichprobe lieferte es bei 20 Titeln fuenf bis sechs
     Treffer, also ueberwiegend andere Variablen. Variante B wird daher nur
     gemeldet, nie automatisch gepatcht.
"""
import struct

JR_RA = 0x03E00008


def _w(code, i):
    n = len(code)
    return struct.unpack_from('<I', code, i)[0] if 0 <= i <= n - 4 else None


def find_variant_a(code):
    """Eindeutiges Setter/Getter-Paar. Rueckgabe: Liste von dicts."""
    out = []
    for i in range(0, len(code) - 24, 4):
        a = _w(code, i)
        if a is None or (a >> 26) != 0x0F or ((a >> 16) & 31) != 1:
            continue                                   # lui at, HI
        hi = a & 0xFFFF
        if _w(code, i + 4) != JR_RA:                   # jr ra
            continue
        c = _w(code, i + 8)                            # sw a0, LO(at)
        if c is None or (c >> 26) != 0x2B or ((c >> 21) & 31) != 1 \
           or ((c >> 16) & 31) != 4:
            continue
        lo = c & 0xFFFF
        if _w(code, i + 12) != (0x3C020000 | hi):      # lui v0, HI
            continue
        if _w(code, i + 16) != (0x8C420000 | lo):      # lw v0, LO(v0)
            continue
        if _w(code, i + 20) != JR_RA:
            continue
        out.append(dict(code_off=i + 8, func_off=i, hi=hi, lo=lo, ins=c,
                        variant='A', var_addr=_var(hi, lo)))
    return out


def find_variant_b(code):
    """Lesen-und-setzen in einer Funktion. Mehrdeutig, nur zur Meldung."""
    out = []
    for i in range(0, len(code) - 20, 4):
        a = _w(code, i)
        if a is None or (a >> 26) != 0x0F or ((a >> 16) & 31) != 2:
            continue                                   # lui v0, HI
        hi = a & 0xFFFF
        b = _w(code, i + 4)                            # lw v0, LO(v0)
        if b is None or (b >> 26) != 0x23 or ((b >> 21) & 31) != 2 \
           or ((b >> 16) & 31) != 2:
            continue
        lo = b & 0xFFFF
        if _w(code, i + 8) != (0x3C010000 | hi):       # lui at, HI
            continue
        d = _w(code, i + 12)                           # sw a0, LO(at)
        if d is None or (d >> 26) != 0x2B or ((d >> 21) & 31) != 1 \
           or ((d >> 16) & 31) != 4 or (d & 0xFFFF) != lo:
            continue
        if _w(code, i + 16) != JR_RA:
            continue
        out.append(dict(code_off=i + 12, func_off=i, hi=hi, lo=lo, ins=d,
                        variant='B', var_addr=_var(hi, lo)))
    return out


def _var(hi, lo):
    return (hi << 16) + (lo - 0x10000 if lo & 0x8000 else lo)


def patched_word(ins):
    """sw a0,LO(at)  ->  sw zero,LO(at)   (rt-Feld auf $zero)"""
    return ins & ~(31 << 16)


# ---------------------------------------------------------------- Pruefung,
LOAD_OPS = (0x23, 0x24, 0x25, 0x20, 0x21)      # lw, lbu, lhu, lb, lh
STORE_OPS = (0x2B, 0x28, 0x29)                 # sw, sb, sh
ADDIU_A0_4 = 0x24840004                        # addiu $a0,$a0,4


def count_refs(code, addr):
    """Lese- und Schreibzugriffe auf eine Adresse zaehlen (lui+offset-Form).

    Die Videomodus-Variable wird ausschliesslich von ihrem eigenen Getter
    gelesen und nur von SetVideoMode geschrieben. Gegen 114 Fundstellen
    geprueft: die echten Treffer haben durchweg 2 Leser und 1 Schreiber,
    waehrend gleich gebaute andere libgpu-Funktionen auf 1 Leser und 3-4
    Schreiber kommen.
    """
    hi = (addr >> 16) & 0xFFFF
    lo = addr & 0xFFFF
    if lo & 0x8000:                 # lui-Konstante ist um 1 hoeher bei neg. Offset
        hi = (hi + 1) & 0xFFFF
    rd = wr = 0
    for i in range(0, len(code) - 4, 4):
        a = _w(code, i)
        if a is None or (a >> 26) != 0x0F or (a & 0xFFFF) != hi:
            continue
        rX = (a >> 16) & 31
        for k in (1, 2, 3, 4):
            b = _w(code, i + 4 * k)
            if b is None:
                break
            if ((b >> 21) & 31) != rX or (b & 0xFFFF) != lo:
                continue
            op = b >> 26
            if op in LOAD_OPS:
                rd += 1
            elif op in STORE_OPS:
                wr += 1
            break
    return rd, wr


def plausible(code, hit):
    """Zugriffsprofil bewerten: 2 = passt genau, 1 = Grenzfall, 0 = verworfen.

    Mehr als ein Schreiber schliesst SetVideoMode aus, das ist das Profil der
    gleich gebauten anderen libgpu-Funktion (1 Leser, 3-4 Schreiber), die sonst
    faelschlich mitgepatcht wuerde. Viele Leser sind dagegen nur ungewoehnlich,
    nicht ausgeschlossen; solche Stellen bleiben als Kandidat erhalten.
    """
    rd, wr = count_refs(code, hit['var_addr'])
    hit['readers'], hit['writers'] = rd, wr
    if wr != 1:
        return 0
    return 2 if rd <= 3 else 1


def has_clear_loop(code, func_off, span=8):
    """libgpu-Clear-Schleife unmittelbar vor der Funktion.

    Zusatzindiz: kommt vor 46 der 74 echten Fundstellen vor und bei keiner
    einzigen der 40 Fehltreffer. Trifft also nicht immer, aber wenn, dann
    verlaesslich, gut geeignet, um zwischen mehreren Kandidaten zu waehlen.
    """
    for k in range(1, span + 1):
        o = func_off - 4 * k
        if o < 0:
            return False
        if _w(code, o) == ADDIU_A0_4:
            return True
    return False


def find_setvideomode(code):
    """Alle plausiblen SetVideoMode-Stellen, beste zuerst.

    Variante A gilt als gesichert. Variante B ist mehrdeutig: dieselbe Bauform
    nutzen auch andere libgpu-Setter, deshalb wird sie nur uebernommen, wenn
    das Zugriffsprofil passt, und selbst dann als unsicher markiert.
    """
    sure, maybe = [], []
    for h in find_variant_a(code):
        score = plausible(code, h)
        if not score:
            continue
        h['clear_loop'] = has_clear_loop(code, h['func_off'])
        h['confident'] = (score == 2)
        (sure if score == 2 else maybe).append(h)
    if sure:
        return sure
    # Variante B nur heranziehen, wenn A nichts Sicheres geliefert hat.
    cands = []
    for h in find_variant_b(code):
        if not plausible(code, h):
            continue
        h['clear_loop'] = has_clear_loop(code, h['func_off'])
        h['confident'] = False
        cands.append(h)
    # Hat genau einer die Clear-Schleife davor, ist die Sache entschieden:
    # dieses Indiz trat bei keinem der 40 Fehltreffer auf.
    loop = [h for h in cands if h['clear_loop']]
    if len(loop) == 1:
        loop[0]['confident'] = True
        return loop
    return maybe + cands
