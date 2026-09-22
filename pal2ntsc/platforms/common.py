"""Gemeinsame Datentypen fuer alle Plattform-Module.
Shared data types for all platform modules.

Texte werden als (Schluessel, Parameter) gehalten und erst beim Anzeigen
uebersetzt, so wirkt ein Sprachwechsel sofort.
Texts are held as (key, params) and translated on display, so a language
switch takes effect immediately.
"""
from ..i18n import t


class Patch:
    """Eine einzelne, groessengleiche Byte-Aenderung im Image."""

    def __init__(self, name, offset, original, patched, title_key, title_args=None,
                 note_key=None, note_args=None, optional=False, risky=False,
                 note_suffix=None, title_text=None, note_text=None):
        assert len(original) == len(patched), \
            'Patches muessen groessengleich sein (%d != %d)' % (len(original), len(patched))
        self.name = name
        self.offset = offset
        self.original = original
        self.patched = patched
        self.title_key = title_key
        self.title_args = title_args or {}
        self.note_key = note_key
        self.note_args = note_args or {}
        self.note_suffix = note_suffix        # (key, args) angehaengt
        # Fertige Texte haben Vorrang, so koennen Eintraege aus der
        # Spieldatenbank ihre Beschreibung mitbringen, ohne den Katalog zu
        # aendern.
        self.title_text = title_text
        self.note_text = note_text
        self.optional = optional              # nicht per Default aktiviert
        self.risky = risky                    # kann Bildlage/Zuordnung beeinflussen

    @staticmethod
    def _pick(text):
        """Fertigen Text waehlen. Ein dict {'de':..., 'en':...} wird erst beim
        Anzeigen aufgeloest, damit ein Sprachwechsel sofort greift."""
        if isinstance(text, dict):
            from ..i18n import get_language
            return text.get(get_language()) or text.get('en') or next(iter(text.values()), '')
        return text

    @property
    def title(self):
        if self.title_text:
            return self._pick(self.title_text)
        return t(self.title_key, **self.title_args)

    @property
    def note(self):
        parts = []
        if self.note_text:
            parts.append(self._pick(self.note_text))
        if self.note_key:
            parts.append(t(self.note_key, **self.note_args))
        if self.note_suffix:
            k, a = self.note_suffix
            parts.append(t(k, **(a or {})))
        return ' | '.join(parts)

    def as_dict(self):
        return dict(name=self.name, offset=self.offset, original=self.original,
                    patched=self.patched, note=self.note)

    def __repr__(self):
        return '<Patch %s @0x%X %s->%s>' % (self.name, self.offset,
                                            self.original.hex(), self.patched.hex())


class GameInfo:
    """Ergebnis der Analyse eines Images."""

    def __init__(self, platform, game_id, title, region='?', extra=None):
        self.platform = platform
        self.game_id = game_id
        self.title = title
        self.region = region
        self.extra = extra or {}
        self.patches = []
        self._notes = []          # Liste von (key, kwargs)
        self.db = None            # Eintrag aus der Datenbank, falls vorhanden

    # --- Meldungen -------------------------------------------------------
    def add_note(self, key, **kw):
        self._notes.append((key, kw))

    def insert_note(self, pos, key, **kw):
        self._notes.insert(pos, (key, kw))

    @property
    def notes(self):
        return [t(k, **a) for k, a in self._notes]

    @property
    def patchable(self):
        return bool(self.patches)

    def default_patches(self):
        return [p for p in self.patches if not p.optional]


def vmode_line_patch(raw, base_offset, want='NTSC', name='systemcnf_vmode'):
    """Ersetzt 'VMODE = PAL' laengengleich durch 'VMODE =NTSC'.

    SYSTEM.CNF darf ihre Groesse nicht aendern, sonst muesste der
    Verzeichniseintrag mitwandern. Die Laenge wird ueber die Leerzeichen
    um das '=' ausgeglichen.
    """
    import re
    m = re.search(rb'VMODE[ \t]*=[ \t]*(PAL|NTSC)', raw, re.I)
    if not m:
        return None
    old = raw[m.start():m.end()]
    cur = m.group(1).decode('latin1').upper()
    if cur == want.upper():
        return None
    minimal = b'VMODE=' + want.encode()
    if len(old) < len(minimal):
        return None                      # kein Platz ohne Laengenaenderung
    pad = len(old) - len(minimal)
    new = b'VMODE' + b' ' * pad + b'=' + want.encode()
    assert len(new) == len(old)
    return Patch(
        name=name,
        offset=base_offset + m.start(),
        original=old,
        patched=new,
        title_key='vmode_title', title_args=dict(cur=cur, want=want.upper()),
        note_key='vmode_note', note_args=dict(new=new.decode('latin1')),
        optional=True,
    )
