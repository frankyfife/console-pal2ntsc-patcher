"""Plattform-Erkennung: probiert die Module der Reihe nach durch."""
import os

from . import gamecube, ps2, xbox, ps1
from .common import Patch, GameInfo
from ..i18n import t

# Reihenfolge zaehlt: GameCube/Xbox haben eindeutige Magic-Werte und kommen
# zuerst; PS2 vor PS1, weil beide ISO9660 nutzen, PS2 sich aber ueber
# SYSTEM.CNF/BOOT2 sicher identifiziert.
MODULES = [
    ('gamecube', gamecube),
    ('xbox', xbox),
    ('ps2', ps2),
    ('ps1', ps1),
]

IMAGE_EXT = {'.iso', '.bin', '.img', '.gcm', '.xiso', '.cue'}
PROTECTED_EXT = {'.old', '.bak'}


def _resolve_cue(path):
    """Fuer .cue die erste Datenspur (BINARY/MODE*) heraussuchen."""
    base = os.path.dirname(path)
    track = None
    try:
        with open(path, 'r', encoding='latin1') as f:
            text = f.read()
    except OSError:
        return None
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith('FILE'):
            q = s.find('"')
            if q >= 0:
                e = s.find('"', q + 1)
                cur = s[q + 1:e]
            else:
                cur = s.split()[1]
        elif s.upper().startswith('TRACK') and cur:
            if 'MODE' in s.upper():
                track = cur
                break
    if not track:
        return None
    cand = os.path.join(base, track)
    return cand if os.path.exists(cand) else None


def identify(path):
    """Return GameInfo or None. Raises ValueError for protected/missing files."""
    if not os.path.exists(path):
        raise ValueError(t('err_missing', path=os.path.basename(path)))
    ext = os.path.splitext(path)[1].lower()
    if ext in PROTECTED_EXT:
        raise ValueError(t('err_protected', ext=ext))
    target = path
    if ext == '.cue':
        target = _resolve_cue(path)
        if not target:
            raise ValueError(t('err_no_track'))
    for name, mod in MODULES:
        try:
            info = mod.probe(target)
        except Exception as exc:
            continue
        if info is not None:
            info.extra['image_path'] = target
            info.extra['source_path'] = path
            return info
    return None
