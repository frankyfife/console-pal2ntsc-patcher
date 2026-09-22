"""Spielspezifische Patches aus data/game_patches.json.

Manches laesst sich nicht generisch loesen. Beispiel Bildlage: Nach dem
Wechsel auf NTSC sitzt bei manchen Spielen das Bild zu tief, weil sie den
vertikalen Versatz des GS-DISPLAY-Registers selbst setzen und dafuer eine
eigene Videomodus-Variable auswerten, die der generische Patch nicht erreicht.
Wo dieselben Konstanten in anderen Titeln geprueft wurden, kam bei 29 von 30
kein verwertbares Muster heraus, solche Faelle gehoeren deshalb in eine
Datenbank, nicht in eine Heuristik.

Die Eintraege sind nach Game-ID abgelegt und beziehen sich auf Offsets
*innerhalb des Executables*, nicht auf das Image: dieselbe Fassung liegt in
verschiedenen Images an verschiedenen Stellen. Vor dem Schreiben wird geprueft,
dass an der Zieladresse wirklich die erwarteten Bytes stehen.
"""
import json
import os

from .platforms.common import Patch

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'data', 'game_patches.json')
_DB = None


def load():
    global _DB
    if _DB is None:
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                _DB = json.load(f).get('games', {})
        except Exception:
            _DB = {}
    return _DB


def _norm(gid):
    return (gid or '').upper().replace('_', '').replace('.', '').replace('-', '')


def entries_for(game_id):
    db = load()
    key = _norm(game_id)
    for k, v in db.items():
        if _norm(k) == key:
            return v
    return []


def build_patches(game_id, exe_bytes, exe_base, lang=None):
    """Patch-Objekte fuer dieses Spiel erzeugen.

    exe_base ist der Offset des Executables im Image; die in der Datenbank
    gespeicherten Offsets sind relativ zum Executable. Beschriftungen werden in
    allen Sprachen mitgegeben und erst beim Anzeigen ausgewaehlt, damit ein
    Sprachwechsel ohne erneutes Einlesen wirkt.
    Sites, deren Originalbytes nicht passen, werden uebersprungen (andere
    Fassung), der Patch wird dann gar nicht erst angeboten.
    """
    out = []
    for e in entries_for(game_id):
        sites = e.get('sites', [])
        if not sites:
            continue
        ok = True
        prepared = []
        for s in sites:
            try:
                off = int(s['offset'], 16) if isinstance(s['offset'], str) else s['offset']
                find = bytes.fromhex(s['find'])
                repl = bytes.fromhex(s['replace'])
            except Exception:
                ok = False
                break
            if len(find) != len(repl) or off + len(find) > len(exe_bytes):
                ok = False
                break
            cur = exe_bytes[off:off + len(find)]
            if cur != find and cur != repl:
                ok = False           # weder Original noch bereits gepatcht
                break
            prepared.append((off, find, repl))
        if not ok:
            continue
        for idx, (off, find, repl) in enumerate(prepared):
            out.append(Patch(
                name='%s_%d' % (e.get('name', 'game_patch'), idx),
                offset=exe_base + off,
                original=find,
                patched=repl,
                title_key='',
                title_text={'de': e.get('title_de') or e.get('title_en') or e.get('name'),
                            'en': e.get('title_en') or e.get('title_de') or e.get('name')},
                note_text={'de': e.get('note_de') or e.get('note_en') or '',
                           'en': e.get('note_en') or e.get('note_de') or ''},
                optional=e.get('optional', False),
                risky=e.get('risky', False),
            ))
    return out
