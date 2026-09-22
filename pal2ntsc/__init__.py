"""PAL2NTSC, Regionspatcher fuer PS1-, PS2-, GameCube- und Xbox-Images.

Grundregel des Werkzeugs: jede Aenderung ist groessengleich und erfolgt an Ort
und Stelle. PS2-Images verlieren sonst ihre Erkennung, sobald sich Groesse oder
Inhaltsverzeichnis verschieben. Aus derselben Regel folgt, dass ein Undo kein
Vollbackup braucht, es genuegt, die ersetzten Bytes im Journal zu sichern.

Autor / author: frankyfife
Lizenz / licence: MIT, siehe LICENSE / see LICENSE
https://github.com/frankyfife/console-pal2ntsc-patcher
"""
import difflib
import json
import os
import re

from .platforms import identify
from .journal import Journal, apply_patches, PatchError, journal_path
from .i18n import t, set_language, get_language, LANGUAGES

__version__ = '0.9.0'

_DB = None
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'pal60_db.json')

# Klammerzusaetze aus Dateinamen: (Europe), (En,Fr,De), (v1.00), [!] ...
_FILENAME_NOISE = re.compile(r'\((?:[^()]*)\)|\[[^\]]*\]')
_DISC = re.compile(r'\b(disc|cd|track)\s*\d+\b', re.I)


def load_db():
    global _DB
    if _DB is None:
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                _DB = json.load(f)
        except Exception:
            _DB = {'titles': {}, 'ids': {}, 'sources': {}}
    return _DB


def norm_title(s):
    """Muss identisch zu tools/import_db.norm() bleiben."""
    s = (s or '').lower().replace('&', ' and ')
    s = re.sub(r"['‘’´`]", '', s)
    s = re.sub(r'\b(the|a|an)\b', ' ', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def _candidate_titles(info, path):
    """Titel-Kandidaten, absteigend nach Verlaesslichkeit."""
    out = []
    base = os.path.splitext(os.path.basename(path))[0]
    clean = _DISC.sub(' ', _FILENAME_NOISE.sub(' ', base))
    out.append(clean)
    if info.title:
        out.append(info.title)
    vol = info.extra.get('volume')
    if vol:
        out.append(vol)
    out.append(base)
    seen = set()
    res = []
    for t in out:
        n = norm_title(t)
        if n and n not in seen:
            seen.add(n)
            res.append((t, n))
    return res


def lookup_db(info, path):
    """Return (entry, how) or (None, None)."""
    db = load_db()
    ids = db.get('ids', {})
    key = (info.game_id or '').upper()
    if key in ids:
        return ids[key], 'db_how_id'
    for k, v in ids.items():
        if k.replace('_', '').replace('.', '') == key.replace('_', '').replace('.', ''):
            return v, 'db_how_id'
    table = db.get('titles', {}).get(info.platform, {})
    if not table:
        return None, None
    for raw, n in _candidate_titles(info, path):
        if n in table:
            return table[n], 'db_how_title'
    # unscharf, aber streng genug um Fehlgriffe zu vermeiden
    for raw, n in _candidate_titles(info, path):
        close = difflib.get_close_matches(n, list(table), n=1, cutoff=0.88)
        if close:
            e = dict(table[close[0]])
            e['_fuzzy'] = close[0]
            return e, 'db_how_fuzzy'
    return None, None


def analyse(path):
    """Identify the image, attach database knowledge. Returns GameInfo|None."""
    info = identify(path)
    if info is None:
        return None
    img = info.extra.get('image_path', path)
    entry, how = lookup_db(info, info.extra.get('source_path', path))
    info.db = entry
    if entry:
        src = load_db().get('sources', {}).get(info.platform, '?')
        conf = entry.get('confidence', 'community')
        name = entry.get('title', '?')
        key = 'db_has60' if entry.get('pal60') else 'db_no60'
        info.insert_note(0, key, title=name, how=t(how), conf=conf)
        if entry.get('_fuzzy'):
            info.insert_note(1, 'db_fuzzy')
        info.extra['db_source'] = src
    j = Journal(img)
    if j.applied:
        info.insert_note(0, 'already_patched', names=', '.join(j.applied_names()))
    info.extra['journal'] = j
    return info


def patch(info, selected=None, make_backup=False, progress=None):
    """Apply the chosen patches. selected = list of patch names (None = defaults)."""
    if selected is None:
        chosen = info.default_patches()
    else:
        chosen = [p for p in info.patches if p.name in selected]
    if not chosen:
        raise PatchError(t('err_none_selected'))
    return apply_patches(
        info.extra['image_path'], info.platform, info.game_id, info.title,
        [p.as_dict() for p in chosen], make_backup=make_backup, progress=progress)


def revert(path, names=None):
    """Patches zuruecknehmen. names=None nimmt alle zurueck."""
    target = path
    try:
        info = identify(path)
        if info:
            target = info.extra.get('image_path', path)
    except Exception:
        pass
    return Journal(target).revert(names=names)


def applied_patches(path):
    """Namen der aktuell angewendeten Patches."""
    target = path
    try:
        info = identify(path)
        if info:
            target = info.extra.get('image_path', path)
    except Exception:
        pass
    return Journal(target).applied_names()
