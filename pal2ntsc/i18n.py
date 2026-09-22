"""Zweisprachigkeit / bilingual strings (Deutsch, English).

Meldungen werden nicht als fertiger Text gespeichert, sondern als Schluessel
plus Parameter (siehe GameInfo.add_note / Patch). Erst beim Anzeigen wird
uebersetzt, so wirkt ein Sprachwechsel sofort, ohne neu einzulesen.

Messages are stored as key + parameters rather than finished text, so switching
language takes effect immediately without re-analysing anything.
"""

_LANG = 'de'
LANGUAGES = (('de', 'Deutsch'), ('en', 'English'))


def set_language(code):
    global _LANG
    if code in dict(LANGUAGES):
        _LANG = code


def get_language():
    return _LANG


def t(key, **kw):
    table = CATALOG.get(_LANG) or CATALOG['en']
    s = table.get(key)
    if s is None:
        s = CATALOG['en'].get(key, key)
    try:
        return s.format(**kw) if kw else s
    except (KeyError, IndexError):
        return s


def tr(entry):
    """Translate a (key, kwargs) tuple, or pass a plain string through."""
    if isinstance(entry, tuple):
        key, kw = entry
        return t(key, **(kw or {}))
    return entry


CATALOG = {
    # ================================================================ DEUTSCH
    'de': {
        # --- Plattformnamen
        'plat_ps1': 'PlayStation',
        'plat_ps2': 'PlayStation 2',
        'plat_gamecube': 'GameCube',
        'plat_xbox': 'Xbox',
        'plat_wii': 'Wii',

        # --- PS2
        'ps2_patch_title': 'Videomodus auf NTSC zwingen (sceGsResetGraph omode=2)',
        'ps2_patch_note': 'sra ${reg},$a2,16 -> addiu ${reg},$zero,2 @ vaddr 0x{vaddr:08X}',
        'ps2_forced_pal_title': 'Fest verdrahtetes PAL auf NTSC aendern',
        'ps2_forced_pal_note': 'addiu ${reg},$zero,3 -> 2 @ vaddr 0x{vaddr:08X}',
        'ps2_note_already_ntsc': 'sceGsResetGraph ist bereits auf NTSC festgelegt.',
        'ps2_note_forced_pal': 'sceGsResetGraph ist fest auf PAL gesetzt (omode=3).',
        'ps2_note_no_hits': 'sceGsResetGraph nicht gefunden. Das Spiel setzt den '
                            'Videomodus anders (eigene GS-Routine oder Loader-Architektur).',
        'ps2_note_no_elf': 'Boot-ELF "{boot}" nicht im Wurzelverzeichnis gefunden.',
        'ps2_note_not_elf': 'Boot-Datei ist kein ELF (evtl. verschluesselt oder Loader).',
        'ps2_note_small_elf': 'Sehr kleines Boot-ELF ({kb} KB), vermutlich nur ein Loader, '
                              'der das eigentliche Spiel nachlaedt. Der Videomodus sitzt '
                              'dann woanders.',
        'ps2_note_vmode_skip': 'VMODE-Zeile in SYSTEM.CNF liesse sich nicht laengengleich '
                               'umschreiben, uebersprungen.',
        'vmode_title': 'SYSTEM.CNF: VMODE {cur} -> {want}',
        'vmode_note': 'Laengengleich geschrieben ({new}), damit Dateigroesse und '
                      'Inhaltsverzeichnis unveraendert bleiben.',

        # --- GameCube
        'gc_patch_title': 'Videomodus {src} -> {dst} ({w}x{h} @60Hz)',
        'gc_patch_note': 'GXRModeObj im main.dol, 60 Byte aus der spieleigenen '
                         '{dst}-Struktur kopiert (DOL+0x{soff:X} -> DOL+0x{doff:X}).',
        'gc_note_already': 'PAL-Videomodus zeigt bereits auf {dst}.',
        'gc_note_no_pal': 'Keine PAL-Videomodus-Struktur im DOL gefunden '
                          '(evtl. bereits NTSC oder eigene Videoroutine).',
        'gc_note_no_src': 'Kein 60Hz-Modus (EURGB60/NTSC) im DOL vorhanden, aus dem '
                          'sich Werte uebernehmen liessen.',
        'gc_note_no_dol': 'main.dol konnte nicht gelesen werden.',
        'gc_country_title': 'Country-Code PAL -> USA (bi2.bin)',
        'gc_country_note': 'Nur fuer Regionspruefungen relevant, nicht fuer den Videomodus.',
        'gc_gameid_title': 'Game-ID {gid} -> {new} (Regionskennung)',
        'gc_gameid_note': 'Achtung: Dolphin ordnet Speicherstaende und Spielprofile ueber '
                          'die Game-ID zu, nach diesem Patch gelten andere Zuordnungen.',
        'gc_menu_hint': 'Hinweise auf ein eigenes 50/60Hz-Menue im Spiel gefunden ({hits}). '
                        'Moeglicherweise genuegt die spieleigene Einstellung.',
        'wii_note': 'Wii-Image erkannt. Die Spieldaten liegen in verschluesselten '
                    'Partitionen; dieses Werkzeug patcht sie nicht. In Dolphin laesst '
                    'sich der Videomodus direkt erzwingen.',

        # --- Xbox
        'xbox_region_title': 'Regionskennung {cur} -> alle Regionen',
        'xbox_region_note': 'XBE-Zertifikat dwGameRegion 0x{cur:08X} -> 0x{new:08X}. '
                            'Hebt Regionssperren auf, aendert aber NICHT den Videostandard.',
        'xbox_note_all_regions': 'XBE ist bereits fuer alle Regionen freigegeben.',
        'xbox_note_eeprom': 'Videostandard: Die Xbox liest ihn aus dem EEPROM, nicht aus '
                            'dem Image. Fuer 60Hz die Konsole bzw. den Emulator umstellen '
                            '(xemu: Videonorm NTSC-M).',
        'xbox_note_hz_strings': 'Das XBE enthaelt 50/60Hz-Texte ({hits}), das Spiel bringt '
                                'vermutlich eine eigene Umschaltung mit.',
        'xbox_note_no_cert': 'Zertifikat liegt ausserhalb der XBE-Datei.',
        'xbox_note_bad_xbe': 'default.xbe hat keine gueltige XBEH-Signatur.',

        # --- PS1
        'ps1_note_no_sigs': 'Keine verifizierten PS1-Videomodus-Signaturen hinterlegt '
                            '(data/ps1_signatures.json). Analyse ja, Patch noch nicht - '
                            'lieber kein Blindschuss ins Executable.',
        'ps1_note_pal_hint': 'Region laut Boot-ID: PAL. Als Zwischenloesung erzwingt '
                             'DuckStation "NTSC-Timings" ohne Eingriff ins Image.',
        'ps1_note_no_match': 'Keine der hinterlegten Videomodus-Signaturen gefunden.',
        'ps1_note_no_boot': 'Boot-Datei "{boot}" nicht gefunden.',
        'ps1_note_not_exe': 'Boot-Datei ist keine PSX-EXE.',
        'ps1_note_crosses': 'Signatur {name} liegt ueber einer Sektorgrenze, uebersprungen.',
        'ps1_sig_note_suffix': 'ganzer Rohsektor LBA {lba}, EDC/ECC neu berechnet',
        'ps1_sig_title': '{title}',
        'ps1_sig_note': '{note}',
        'ps1_svm_title': 'Videomodus auf NTSC zwingen (libgpu SetVideoMode)',
        'ps1_svm_title_maybe': 'Videomodus auf NTSC zwingen, KANDIDAT, bitte einzeln testen',
        'ps1_note_candidates': '{n} moegliche SetVideoMode-Stellen, keine davon '
                               'eindeutig. Sie sind nicht vorausgewaehlt: bitte einzeln '
                               'anwenden und das Spiel pruefen; die Ruecknahme stellt '
                               'jederzeit den Originalzustand her.',
        'ps1_svm_note': 'sw $a0 -> sw $zero @ vaddr 0x{vaddr:08X}; die Modusvariable '
                        '0x{var:08X} bekommt damit immer 0 = NTSC',
        'ps1_note_multi_a': '{n} SetVideoMode-Stellen gefunden. Das ist bei Spielen '
                            'normal, die libgpu je Overlay einbinden, alle werden '
                            'gepatcht.',
        'ps1_note_only_b': 'Kein eindeutiges SetVideoMode gefunden. Es gibt {n} '
                           'Kandidaten der mehrdeutigen Bauform (lesen und setzen), '
                           'die auch andere libgpu-Variablen betreffen koennen - '
                           'die werden bewusst nicht angefasst.',
        'ps1_note_no_sig': 'Keine SetVideoMode-Signatur gefunden. Das Spiel nutzt eine '
                           'andere libgpu-Fassung oder setzt den Modus selbst.',
        'ps1_note_not_pal': 'Region ist {region}, nicht PAL, ein NTSC-Patch aendert '
                            'hier vermutlich nichts.',

        # --- Datenbank
        'db_has60': 'Laut Datenbank bietet "{title}" bereits 60Hz/NTSC von sich aus '
                    '(Treffer ueber {how}, {conf}). Ein Patch ist dann meist unnoetig - '
                    'zuerst die Spieloptionen pruefen.',
        'db_no60': 'Laut Datenbank hat "{title}" keinen eigenen 60Hz-Modus '
                   '(Treffer ueber {how}, {conf}), ein Patch lohnt sich.',
        'db_fuzzy': 'Achtung: Der Datenbank-Treffer ist nur unscharf zugeordnet - '
                    'bitte den Titel gegenpruefen.',
        'db_how_id': 'Game-ID',
        'db_how_title': 'Titel',
        'db_how_fuzzy': 'Titel (unscharf)',
        'already_patched': 'Dieses Image wurde bereits mit PAL2NTSC gepatcht ({names}). '
                           'Ruecknahme ist moeglich.',

        # --- Journal / Fehler
        'err_protected': 'Das ist eine Sicherungsdatei ({ext}). Solche Dateien werden '
                         'nicht gepatcht, bitte das aktive Image verwenden.',
        'err_no_track': 'In der CUE-Datei liess sich keine Datenspur finden.',
        'err_missing': 'Datei nicht gefunden: {path}',
        'err_no_journal': 'Kein Journal vorhanden, nichts zurueckzunehmen.',
        'err_size_changed': 'Groesse weicht ab ({now} statt {then}). Das Image wurde '
                            'ausserhalb dieses Werkzeugs veraendert; Ruecknahme abgebrochen.',
        'err_neither': 'Bytes an Offset 0x{off:X} sind weder gepatcht noch original '
                       '(gefunden {found}). Ruecknahme abgebrochen, damit nichts '
                       'zerstoert wird.',
        'err_already': 'Patch "{name}" ist bereits angewendet (Offset 0x{off:X}).',
        'err_unexpected': 'Unerwartete Bytes an Offset 0x{off:X}: {found} statt {want}. '
                          'Falsche Version oder anders gepatcht.',
        'err_no_patches': 'Keine Patches uebergeben.',
        'err_none_selected': 'Keine Patches ausgewaehlt.',
        'backup_running': 'Vollkopie wird angelegt (das dauert)...',

        # --- GUI
        'ui_title': 'PAL2NTSC  -  PAL zu NTSC Patcher fuer PS1 / PS2 / GameCube / Xbox',
        'ui_head': 'PAL → NTSC',
        'ui_sub': 'Images hineinziehen oder Ordner waehlen',
        'ui_files': 'Dateien…',
        'ui_folder': 'Ordner…',
        'ui_clear': 'Liste leeren',
        'ui_help': 'Hilfe',
        'ui_col_file': 'Datei',
        'ui_col_platform': 'Plattform',
        'ui_col_region': 'Region',
        'ui_col_status': 'Status',
        'ui_patches': ' Patches ',
        'ui_backup': 'Zusaetzlich Vollkopie (.bak) anlegen – langsam, fuer die '
                     'Ruecknahme nicht noetig',
        'ui_patch': 'Patchen',
        'ui_undo': 'Ruecknahme',
        'ui_patch_all': 'Alle patchen',
        'ui_none_selected': 'Kein Image gewaehlt',
        'ui_ready_dnd': 'Bereit. Images per Drag & Drop ablegen oder oben auswaehlen.',
        'ui_ready_nodnd': 'Bereit. (tkinterdnd2 fehlt, Drag & Drop aus, bitte '
                          '"Dateien..." / "Ordner..." benutzen.)',
        'ui_reading': 'wird gelesen…',
        'ui_unrecognised': 'nicht erkannt',
        'ui_unusable': 'nicht verwendbar',
        'ui_notrecog_long': 'Format nicht erkannt',
        'ui_st_patched': 'bereits gepatcht',
        'ui_st_patched_more': 'gepatcht, {n} weitere(r) moeglich',
        'ui_st_available': '{n} Patch(es) verfuegbar',
        'ui_st_optional': 'nur optionale Patches',
        'ui_st_none': 'kein Patch noetig/moeglich',
        'ui_no_patches': 'Fuer dieses Image sind keine Patches verfuegbar.',
        'ui_no_notes': 'Keine Besonderheiten.',
        'ui_applied_mark': '   [bereits angewendet]',
        'ui_added': '{n} Image(s) hinzugefuegt, analysiere…',
        'ui_nothing_new': 'Nichts Neues gefunden.',
        'ui_ask_patch': 'Folgende Patches auf\n\n{file}\n\nanwenden?\n\n  • {list}',
        'ui_ask_caution': '\n\nAchtung: {text}',
        'ui_no_checked': 'Kein Patch angekreuzt.',
        'ui_ask_undo': 'Alle PAL2NTSC-Patches an\n\n{file}\n\nzuruecknehmen?',
        'ui_ask_all': 'Empfohlene Patches auf {n} Image(s) anwenden?\n\n'
                      'Optionale Patches (Region, Game-ID) bleiben aussen vor.\n'
                      'Jede Aenderung bleibt einzeln widerrufbar.',
        'ui_all_nothing': 'Nichts zu tun, kein Image mit empfohlenen Patches offen.',
        'ui_done_n': '{file}: {n} Patch(es) angewendet.',
        'ui_failed': '{file}: FEHLGESCHLAGEN - {err}',
        'ui_patched_short': '{file}: gepatcht.',
        'ui_all_done': 'Fertig: {done} gepatcht, {fail} uebersprungen.',
        'ui_undone': '{file}: {n} Patch(es) zurueckgenommen.',
        'ui_undo_failed': '{file}: Ruecknahme fehlgeschlagen - {err}',
        'ui_choose_files': 'Disc-Images waehlen',
        'ui_choose_folder': 'Ordner mit Images waehlen',
        'ui_filter_images': 'Disc-Images',
        'ui_filter_all': 'Alle Dateien',
        'ui_language': 'Sprache',
        'ui_close': 'Schliessen',
        # --- CLI
        'cli_title': 'Titel',
        'cli_notes': 'Hinweis',
        'cli_patches': 'Patches',
        'cli_none': 'keine anwendbar',
        'cli_skipped': 'uebersprungen: {err}',
        'cli_error': 'FEHLER: {err}',
        'cli_notrecog': 'nicht erkannt',
        'cli_summary': '{n} Datei(en) geprueft, {ok} erkannt.',
        'cli_notrecog_path': 'Nicht erkannt: {path}',
        'cli_nothing_sel': 'Nichts ausgewaehlt (nur optionale Patches vorhanden - '
                           'mit --all oder --only anwenden).',
        'cli_applying': 'Anwenden: {list}',
        'cli_confirm': 'Fortfahren? [j/N] ',
        'cli_yes': 'jy',
        'cli_aborted': 'Abgebrochen.',
        'cli_noinput': 'Keine Eingabe moeglich, bitte --yes verwenden.',
        'cli_failed': 'FEHLGESCHLAGEN: {err}',
        'cli_done': 'Fertig. Journal: {journal}',
        'cli_undo_hint': 'Ruecknahme jederzeit mit:  python pal2ntsc_cli.py revert "{path}"',
        'cli_reverted': '{n} Patch(es) zurueckgenommen{extra}.',
        'cli_reverted_extra': ', {n} bereits im Originalzustand',
        'cli_applied_list': 'Angewendete Patches:',
    },

    # ================================================================ ENGLISH
    'en': {
        'plat_ps1': 'PlayStation',
        'plat_ps2': 'PlayStation 2',
        'plat_gamecube': 'GameCube',
        'plat_xbox': 'Xbox',
        'plat_wii': 'Wii',

        'ps2_patch_title': 'Force video mode to NTSC (sceGsResetGraph omode=2)',
        'ps2_patch_note': 'sra ${reg},$a2,16 -> addiu ${reg},$zero,2 @ vaddr 0x{vaddr:08X}',
        'ps2_forced_pal_title': 'Change hard-wired PAL to NTSC',
        'ps2_forced_pal_note': 'addiu ${reg},$zero,3 -> 2 @ vaddr 0x{vaddr:08X}',
        'ps2_note_already_ntsc': 'sceGsResetGraph is already fixed to NTSC.',
        'ps2_note_forced_pal': 'sceGsResetGraph is hard-wired to PAL (omode=3).',
        'ps2_note_no_hits': 'sceGsResetGraph not found. This game sets the video mode '
                            'differently (custom GS routine or loader architecture).',
        'ps2_note_no_elf': 'Boot ELF "{boot}" not found in the root directory.',
        'ps2_note_not_elf': 'Boot file is not an ELF (possibly encrypted or a loader).',
        'ps2_note_small_elf': 'Very small boot ELF ({kb} KB), likely just a loader that '
                              'pulls in the actual game. The video mode lives elsewhere.',
        'ps2_note_vmode_skip': 'The VMODE line in SYSTEM.CNF could not be rewritten at '
                               'equal length, skipped.',
        'vmode_title': 'SYSTEM.CNF: VMODE {cur} -> {want}',
        'vmode_note': 'Written at identical length ({new}) so file size and table of '
                      'contents stay untouched.',

        'gc_patch_title': 'Video mode {src} -> {dst} ({w}x{h} @60Hz)',
        'gc_patch_note': 'GXRModeObj in main.dol, 60 bytes copied from the game\'s own '
                         '{dst} structure (DOL+0x{soff:X} -> DOL+0x{doff:X}).',
        'gc_note_already': 'The PAL video mode already points at {dst}.',
        'gc_note_no_pal': 'No PAL video mode structure found in the DOL (already NTSC, '
                          'or a custom video routine).',
        'gc_note_no_src': 'No 60Hz mode (EURGB60/NTSC) present in the DOL to copy values '
                          'from.',
        'gc_note_no_dol': 'main.dol could not be read.',
        'gc_country_title': 'Country code PAL -> USA (bi2.bin)',
        'gc_country_note': 'Only relevant for region checks, not for the video mode.',
        'gc_gameid_title': 'Game ID {gid} -> {new} (region letter)',
        'gc_gameid_note': 'Note: Dolphin maps save files and game profiles via the game '
                          'ID, this patch changes those associations.',
        'gc_menu_hint': 'Found signs of a built-in 50/60Hz menu ({hits}). The game\'s own '
                        'setting may already be enough.',
        'wii_note': 'Wii image detected. Its data sits in encrypted partitions and is not '
                    'patched by this tool. Dolphin can force the video mode directly.',

        'xbox_region_title': 'Region flag {cur} -> all regions',
        'xbox_region_note': 'XBE certificate dwGameRegion 0x{cur:08X} -> 0x{new:08X}. '
                            'Lifts region locks but does NOT change the video standard.',
        'xbox_note_all_regions': 'The XBE is already cleared for all regions.',
        'xbox_note_eeprom': 'Video standard: the Xbox reads it from the EEPROM, not from '
                            'the image. For 60Hz change the console or emulator setting '
                            '(xemu: video standard NTSC-M).',
        'xbox_note_hz_strings': 'The XBE contains 50/60Hz strings ({hits}), the game '
                                'likely offers its own switch.',
        'xbox_note_no_cert': 'The certificate lies outside the XBE file.',
        'xbox_note_bad_xbe': 'default.xbe has no valid XBEH signature.',

        'ps1_note_no_sigs': 'No verified PS1 video-mode signatures on file '
                            '(data/ps1_signatures.json). Analysis yes, patching not yet - '
                            'better than a blind guess into the executable.',
        'ps1_note_pal_hint': 'Region per boot ID: PAL. As an interim measure DuckStation '
                             'can force NTSC timings without touching the image.',
        'ps1_note_no_match': 'None of the stored video-mode signatures matched.',
        'ps1_note_no_boot': 'Boot file "{boot}" not found.',
        'ps1_note_not_exe': 'Boot file is not a PSX-EXE.',
        'ps1_note_crosses': 'Signature {name} straddles a sector boundary, skipped.',
        'ps1_sig_note_suffix': 'whole raw sector LBA {lba}, EDC/ECC recomputed',
        'ps1_sig_title': '{title}',
        'ps1_sig_note': '{note}',
        'ps1_svm_title': 'Force video mode to NTSC (libgpu SetVideoMode)',
        'ps1_svm_title_maybe': 'Force video mode to NTSC, CANDIDATE, test individually',
        'ps1_note_candidates': '{n} possible SetVideoMode sites, none of them '
                               'conclusive. They are not preselected: apply one at a '
                               'time and check the game; revert restores the original '
                               'state at any point.',
        'ps1_svm_note': 'sw $a0 -> sw $zero @ vaddr 0x{vaddr:08X}; the mode variable '
                        '0x{var:08X} therefore always receives 0 = NTSC',
        'ps1_note_multi_a': 'Found {n} SetVideoMode sites. That is normal for games '
                            'that link libgpu into each overlay, all of them are '
                            'patched.',
        'ps1_note_only_b': 'No unambiguous SetVideoMode found. There are {n} candidates '
                           'of the ambiguous shape (read and set) which may well be '
                           'other libgpu variables, deliberately left alone.',
        'ps1_note_no_sig': 'No SetVideoMode signature found. The game uses a different '
                           'libgpu build or sets the mode itself.',
        'ps1_note_not_pal': 'Region is {region}, not PAL, an NTSC patch will probably '
                            'change nothing here.',

        'db_has60': 'The database says "{title}" already offers 60Hz/NTSC by itself '
                    '(matched by {how}, {conf}). A patch is usually unnecessary, check '
                    'the in-game options first.',
        'db_no60': 'The database says "{title}" has no 60Hz mode of its own '
                   '(matched by {how}, {conf}), patching is worthwhile.',
        'db_fuzzy': 'Careful: this database match is only approximate, please verify '
                    'the title.',
        'db_how_id': 'game ID',
        'db_how_title': 'title',
        'db_how_fuzzy': 'title (approximate)',
        'already_patched': 'This image has already been patched by PAL2NTSC ({names}). '
                           'It can be reverted.',

        'err_protected': 'This is a backup file ({ext}). Such files are never patched - '
                         'please use the active image.',
        'err_no_track': 'No data track could be found in the CUE file.',
        'err_missing': 'File not found: {path}',
        'err_no_journal': 'No journal present, nothing to revert.',
        'err_size_changed': 'Size differs ({now} instead of {then}). The image was '
                            'changed outside this tool; revert aborted.',
        'err_neither': 'Bytes at offset 0x{off:X} are neither patched nor original '
                       '(found {found}). Revert aborted so nothing gets destroyed.',
        'err_already': 'Patch "{name}" is already applied (offset 0x{off:X}).',
        'err_unexpected': 'Unexpected bytes at offset 0x{off:X}: {found} instead of '
                          '{want}. Wrong revision, or patched by something else.',
        'err_no_patches': 'No patches supplied.',
        'err_none_selected': 'No patches selected.',
        'backup_running': 'Creating full backup copy (this takes a while)...',

        'ui_title': 'PAL2NTSC  -  PAL to NTSC patcher for PS1 / PS2 / GameCube / Xbox',
        'ui_head': 'PAL → NTSC',
        'ui_sub': 'Drop images here, or pick a folder',
        'ui_files': 'Files…',
        'ui_folder': 'Folder…',
        'ui_clear': 'Clear list',
        'ui_help': 'Help',
        'ui_col_file': 'File',
        'ui_col_platform': 'Platform',
        'ui_col_region': 'Region',
        'ui_col_status': 'Status',
        'ui_patches': ' Patches ',
        'ui_backup': 'Also create a full copy (.bak) – slow, and not needed for revert',
        'ui_patch': 'Patch',
        'ui_undo': 'Revert',
        'ui_patch_all': 'Patch all',
        'ui_none_selected': 'No image selected',
        'ui_ready_dnd': 'Ready. Drag & drop images, or use the buttons above.',
        'ui_ready_nodnd': 'Ready. (tkinterdnd2 missing, drag & drop disabled, please use '
                          '"Files..." / "Folder...".)',
        'ui_reading': 'reading…',
        'ui_unrecognised': 'not recognised',
        'ui_unusable': 'unusable',
        'ui_notrecog_long': 'Format not recognised',
        'ui_st_patched': 'already patched',
        'ui_st_patched_more': 'patched, {n} more available',
        'ui_st_available': '{n} patch(es) available',
        'ui_st_optional': 'optional patches only',
        'ui_st_none': 'no patch needed/possible',
        'ui_no_patches': 'No patches are available for this image.',
        'ui_no_notes': 'Nothing noteworthy.',
        'ui_applied_mark': '   [already applied]',
        'ui_added': '{n} image(s) added, analysing…',
        'ui_nothing_new': 'Nothing new found.',
        'ui_ask_patch': 'Apply the following patches to\n\n{file}?\n\n  • {list}',
        'ui_ask_caution': '\n\nCaution: {text}',
        'ui_no_checked': 'No patch ticked.',
        'ui_ask_undo': 'Revert all PAL2NTSC patches on\n\n{file}?',
        'ui_ask_all': 'Apply recommended patches to {n} image(s)?\n\n'
                      'Optional patches (region, game ID) are left out.\n'
                      'Every change stays individually revertible.',
        'ui_all_nothing': 'Nothing to do, no image with recommended patches pending.',
        'ui_done_n': '{file}: {n} patch(es) applied.',
        'ui_failed': '{file}: FAILED - {err}',
        'ui_patched_short': '{file}: patched.',
        'ui_all_done': 'Done: {done} patched, {fail} skipped.',
        'ui_undone': '{file}: {n} patch(es) reverted.',
        'ui_undo_failed': '{file}: revert failed - {err}',
        'ui_choose_files': 'Choose disc images',
        'ui_choose_folder': 'Choose a folder containing images',
        'ui_filter_images': 'Disc images',
        'ui_filter_all': 'All files',
        'ui_language': 'Language',
        'ui_close': 'Close',
        # --- CLI
        'cli_title': 'Title',
        'cli_notes': 'Note',
        'cli_patches': 'Patches',
        'cli_none': 'none applicable',
        'cli_skipped': 'skipped: {err}',
        'cli_error': 'ERROR: {err}',
        'cli_notrecog': 'not recognised',
        'cli_summary': '{n} file(s) checked, {ok} recognised.',
        'cli_notrecog_path': 'Not recognised: {path}',
        'cli_nothing_sel': 'Nothing selected (only optional patches present - '
                           'use --all or --only).',
        'cli_applying': 'Applying: {list}',
        'cli_confirm': 'Continue? [y/N] ',
        'cli_yes': 'y',
        'cli_aborted': 'Aborted.',
        'cli_noinput': 'No input possible, please use --yes.',
        'cli_failed': 'FAILED: {err}',
        'cli_done': 'Done. Journal: {journal}',
        'cli_undo_hint': 'Revert any time with:  python pal2ntsc_cli.py revert "{path}"',
        'cli_reverted': '{n} patch(es) reverted{extra}.',
        'cli_reverted_extra': ', {n} already at original state',
        'cli_applied_list': 'Applied patches:',
    },
}
