"""Patch-Journal: macht jeden Patch reversibel, ohne das Image zu kopieren.

Alle Patches dieses Tools sind in-place und groessengleich (PS2-ISOs verlieren
sonst ihre Erkennung, siehe README). Damit genuegt es, pro geaenderter Stelle
Offset + Originalbytes zu sichern, ein paar hundert Byte statt mehrerer GB.
"""
import json
import os
import hashlib
import datetime

from .i18n import t

SUFFIX = '.pal2ntsc.json'


class PatchError(Exception):
    pass


def journal_path(image_path):
    return image_path + SUFFIX


def _quick_fingerprint(path, size):
    """Cheap identity check: size + hash of a few sample regions.

    Hashing multi-GB images on every operation would be unusable, so we sample
    the head, the middle and the tail instead.
    """
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(path, 'rb') as f:
        for pos in (0, size // 2, max(0, size - 65536)):
            f.seek(pos)
            h.update(f.read(65536))
    return h.hexdigest()


class Journal:
    def __init__(self, image_path):
        self.image_path = image_path
        self.path = journal_path(image_path)
        self.data = None
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)

    @property
    def applied(self):
        return bool(self.data and self.data.get('patches'))

    def applied_names(self):
        if not self.data:
            return []
        return [p['name'] for p in self.data.get('patches', [])]

    def record(self, platform, game_id, title, patches):
        """patches: list of dict(name, offset, original(bytes), patched(bytes), note)"""
        size = os.path.getsize(self.image_path)
        existing = (self.data or {}).get('patches', [])
        known = {(p['name'], p['offset']) for p in existing}
        for p in patches:
            key = (p['name'], p['offset'])
            if key in known:
                continue
            existing.append(dict(
                name=p['name'],
                offset=p['offset'],
                original=p['original'].hex(),
                patched=p['patched'].hex(),
                note=p.get('note', ''),
            ))
        self.data = dict(
            tool='PAL2NTSC',
            format=1,
            image=os.path.basename(self.image_path),
            size=size,
            platform=platform,
            game_id=game_id,
            title=title,
            fingerprint=_quick_fingerprint(self.image_path, size),
            modified=datetime.datetime.now().isoformat(timespec='seconds'),
            patches=existing,
        )
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def revert(self, verify=True, names=None):
        """Originalbytes zurueckschreiben. Returns (reverted, skipped).

        names schraenkt auf bestimmte Patches ein; die uebrigen bleiben
        angewendet und im Journal stehen. So laesst sich ein einzelner
        Eingriff zuruecknehmen, ohne die anderen zu verlieren.
        """
        if not self.applied:
            raise PatchError(t('err_no_journal'))
        size = os.path.getsize(self.image_path)
        if size != self.data['size']:
            raise PatchError(t('err_size_changed', now=size, then=self.data['size']))
        wanted = None if names is None else set(names)
        reverted = skipped = 0
        keep = []
        with open(self.image_path, 'r+b') as f:
            for p in self.data['patches']:
                if wanted is not None and p['name'] not in wanted:
                    keep.append(p)
                    continue
                orig = bytes.fromhex(p['original'])
                patched = bytes.fromhex(p['patched'])
                f.seek(p['offset'])
                cur = f.read(len(patched))
                if verify and cur != patched:
                    if cur == orig:
                        skipped += 1          # already back to original
                        continue
                    raise PatchError(t('err_neither', off=p['offset'], found=cur.hex()))
                f.seek(p['offset'])
                f.write(orig)
                reverted += 1
            f.flush()
            os.fsync(f.fileno())
        if keep:
            self.data['patches'] = keep
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        else:
            os.remove(self.path)
            self.data = None
        return reverted, skipped


def apply_patches(image_path, platform, game_id, title, patches, make_backup=False,
                  progress=None):
    """Apply patches in-place after verifying every original byte still matches.

    patches: list of dict(name, offset, original, patched, note)
    """
    if not patches:
        raise PatchError(t('err_no_patches'))
    # verify first, write second, never leave a half-patched image
    with open(image_path, 'rb') as f:
        for p in patches:
            f.seek(p['offset'])
            cur = f.read(len(p['original']))
            if cur == p['patched']:
                raise PatchError(t('err_already', name=p['name'], off=p['offset']))
            if cur != p['original']:
                raise PatchError(t('err_unexpected', off=p['offset'],
                                   found=cur.hex(), want=p['original'].hex()))
    if make_backup:
        bak = image_path + '.bak'
        if not os.path.exists(bak):
            import shutil
            if progress:
                progress(t('backup_running'))
            shutil.copy2(image_path, bak)
    with open(image_path, 'r+b') as f:
        for p in patches:
            f.seek(p['offset'])
            f.write(p['patched'])
        f.flush()
        os.fsync(f.fileno())
    j = Journal(image_path)
    j.record(platform, game_id, title, patches)
    return j
