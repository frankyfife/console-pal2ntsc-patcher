"""Baut pal2ntsc/data/pal60_db.json aus den gespeicherten Community-Seiten.

Quellen (in websites/ abgelegt):
  * ConsoleMods Wiki, GameCube: Games with Alternate Display Modes
  * ConsoleMods Wiki, PlayStation: PAL Optimized Titles
  * List of 60 Hz support in PAL PlayStation 2 games
  * Gaming information blog, Xbox titles with Pal60 support

Alle vier sind Community-Zusammentragungen, keine offiziellen Angaben. Das
wird im Ergebnis mitgefuehrt (confidence: community), damit im Werkzeug
sichtbar bleibt, worauf ein Hinweis beruht.

Aufruf:  python tools/import_db.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, 'websites')
OUT = os.path.join(ROOT, 'pal2ntsc', 'data', 'pal60_db.json')

YES = ('yes', 'ja', 'true')


def read_html(name):
    path = os.path.join(WEB, name)
    if not os.path.exists(path):
        return None
    for enc in ('utf-8', 'cp1252', 'latin1'):
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def strip_tags(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = (s.replace('&#160;', ' ').replace('&nbsp;', ' ').replace('&amp;', '&')
          .replace('&#39;', "'").replace('&quot;', '"').replace('\xa0', ' ')
          .replace('&lt;', '<').replace('&gt;', '>'))
    return s.strip()


def wiki_title(s):
    """'Aggressive Inline (video game)|Aggressive Inline' -> 'Aggressive Inline'"""
    if '|' in s:
        s = s.split('|')[-1]
    s = re.sub(r'\s*\((video game|game)\)\s*', ' ', s, flags=re.I)
    return s.strip()


def norm(s):
    """Normalised key for fuzzy title matching.

    Apostrophes are dropped rather than turned into spaces, so "Luigi's
    Mansion" and "Luigis Mansion" collapse to the same key.
    """
    s = s.lower()
    s = s.replace('&', ' and ')
    s = re.sub(r"['‘’´`]", '', s)
    s = re.sub(r'\b(the|a|an)\b', ' ', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def tables(html):
    return re.findall(r'<table.*?</table>', html, re.I | re.S)


def rows(tbl):
    out = []
    for r in re.findall(r'<tr.*?</tr>', tbl, re.I | re.S):
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', r, re.I | re.S)
        out.append([strip_tags(c) for c in cells])
    return out


# ------------------------------------------------------------------ sources,
def parse_gamecube():
    html = read_html('gamecube Games with Alternate Display Modes '
                     '– ConsoleMods Wiki.html')
    if not html:
        return {}, None
    best = max(tables(html), key=lambda t: len(rows(t)))
    rs = rows(best)
    hdr = [c.lower() for c in rs[0]]
    try:
        i_pal60 = hdr.index('pal60')
    except ValueError:
        return {}, None
    i_480p = hdr.index('ntsc 480p') if 'ntsc 480p' in hdr else None
    i_ws = hdr.index('widescreen') if 'widescreen' in hdr else None
    i_note = hdr.index('notes') if 'notes' in hdr else None
    out = {}
    for r in rs[1:]:
        if len(r) <= i_pal60 or not r[0]:
            continue
        title = wiki_title(r[0])
        if not title:
            continue
        val = r[i_pal60].strip().lower()
        entry = dict(title=title,
                     pal60=val.startswith('yes'),
                     pal60_raw=r[i_pal60].strip())
        if i_480p is not None and len(r) > i_480p:
            entry['ntsc480p'] = r[i_480p].strip().lower().startswith('yes')
        if i_ws is not None and len(r) > i_ws:
            entry['widescreen'] = r[i_ws].strip().lower().startswith('yes')
        if i_note is not None and len(r) > i_note and r[i_note]:
            entry['note'] = r[i_note]
        out[norm(title)] = entry
    return out, 'ConsoleMods Wiki: GameCube Games with Alternate Display Modes'


def parse_ps2():
    html = read_html('List of 60 Hz support in PAL PlayStation 2 games.html')
    if not html:
        return {}, None
    best = max(tables(html), key=lambda t: len(rows(t)))
    out = {}
    for r in rows(best)[1:]:
        if len(r) < 2 or not r[0]:
            continue
        title = r[0].strip()
        val = r[1].strip()
        low = val.lower()
        out[norm(title)] = dict(title=title,
                                pal60=low.startswith('yes'),
                                pal60_raw=val)
    return out, 'List of 60 Hz support in PAL PlayStation 2 games'


def parse_ps1():
    html = read_html('playstation PAL Optimized Titles – ConsoleMods Wiki.html')
    if not html:
        return {}, None
    best = max(tables(html), key=lambda t: len(rows(t)))
    rs = rows(best)
    hdr = [c.lower() for c in rs[0]]

    def idx(name):
        for i, h in enumerate(hdr):
            if name in h:
                return i
        return None

    i_full, i_part, i_un = idx('fully'), idx('partly'), idx('unoptimised')
    i_fpb, i_gsm, i_lib = idx('freepsxboot'), idx('gsm'), idx('libcrypt')
    out = {}
    for r in rs[1:]:
        if not r or not r[0]:
            continue
        title = r[0].strip()

        def cell(i):
            return r[i].strip() if (i is not None and len(r) > i) else ''

        full = cell(i_full).lower().startswith('yes')
        part = cell(i_part).lower().startswith('yes')
        entry = dict(title=title, optimised_full=full, optimised_partly=part,
                     unoptimised=cell(i_un).lower().startswith('yes'))
        # "Fully optimised" means the PAL release already runs like NTSC
        entry['pal60'] = full
        if cell(i_fpb):
            entry['freepsxboot'] = cell(i_fpb)
        if cell(i_gsm):
            entry['gsm'] = cell(i_gsm)
        if cell(i_lib).lower().startswith('yes'):
            entry['libcrypt'] = True
        if part and cell(i_part).lower() != 'yes':
            entry['note'] = cell(i_part)
        out[norm(title)] = entry
    return out, 'ConsoleMods Wiki: PlayStation PAL Optimized Titles'


def parse_xbox():
    html = read_html('Gaming information blog_ Xbox titles with Pal60 support.html')
    if not html:
        return {}, None
    body = re.sub(r'<(script|style|head)[^>]*>.*?</\1>', '', html, flags=re.I | re.S)
    i = body.find('post-body')
    seg = body[i:] if i >= 0 else body
    seg = re.sub(r'<br\s*/?>', '\n', seg, flags=re.I)
    seg = re.sub(r'</(p|div|li|h\d|tr|td|span)>', '\n', seg, flags=re.I)
    seg = strip_tags(seg)
    lines = [l.strip() for l in seg.splitlines() if l.strip()]
    # some entries got glued together: "...: NoAFL Live 2003: No"
    split_glued = re.compile(r':(\s*)(Yes|No)(?=[A-Z0-9])')
    fixed = []
    for l in lines:
        parts = split_glued.sub(lambda m: ':' + m.group(1) + m.group(2) + '\n',
                                l).split('\n')
        fixed.extend(p.strip() for p in parts if p.strip())
    pat = re.compile(r'^(.+?):\s*(Yes|No)\b(.*)$', re.I)
    out = {}
    for l in fixed:
        m = pat.match(l)
        if not m:
            continue
        title = m.group(1).strip(' .-')
        if len(title) < 2 or len(title) > 90:
            continue
        entry = dict(title=title, pal60=m.group(2).lower() == 'yes',
                     pal60_raw=m.group(2))
        extra = m.group(3).strip(' ()')
        if extra:
            entry['note'] = extra
        out[norm(title)] = entry
    return out, 'Gaming information blog: Xbox titles with Pal60 support'


# ------------------------------------------------------------------- verified,
# Aus eigener Pruefung in dieser Sammlung, nicht aus den Community-Listen.
VERIFIED_IDS = {
    'GLMP01': {
        'title': "Luigi's Mansion (PAL)",
        'platform': 'gamecube',
        'pal60': False,
        'confidence': 'verified',
        'source': 'eigene Pruefung: keine 50/60Hz-Texte im DOL',
        'note': 'Der bekannte 60fps-Patch setzt die spielinterne Videomodus-Variable '
                'bei DOL-Offset 0x52A4 fest (4 Byte).',
    },
}


def main():
    db = {
        'format': 2,
        '_comment': [
            'Erzeugt von tools/import_db.py aus den Seiten in websites/.',
            'Alle Listeneintraege sind Community-Angaben (confidence: community)',
            'und nicht selbst nachgeprueft. Eintraege unter "ids" stammen aus',
            'eigener Pruefung.',
            'Schluessel unter "titles" sind normalisierte Titel (Kleinschreibung,',
            'ohne Artikel und Sonderzeichen) fuer unscharfes Matching.',
        ],
        'sources': {},
        'titles': {},
        'ids': VERIFIED_IDS,
    }
    for plat, fn in (('gamecube', parse_gamecube), ('ps2', parse_ps2),
                     ('ps1', parse_ps1), ('xbox', parse_xbox)):
        entries, src = fn()
        db['titles'][plat] = entries
        if src:
            db['sources'][plat] = src
        n60 = sum(1 for e in entries.values() if e.get('pal60'))
        print('%-9s %4d Titel  (%d mit 60Hz/optimiert)  %s'
              % (plat, len(entries), n60, src or 'QUELLE FEHLT'))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=1, ensure_ascii=False)
    total = sum(len(v) for v in db['titles'].values())
    print('-> %s  (%d Titel gesamt)' % (OUT, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
