# PAL2NTSC

*[English version: README.md](README.md)*

Stellt PAL-Disc-Images von **PlayStation, PlayStation 2, GameCube und Xbox**
auf NTSC um, damit sie mit 60 Hz statt 50 Hz laufen.

Der Punkt dabei ist die Sprache. PAL-Fassungen bringen meist die deutsche
Vertonung und Übersetzung mit, die der US-Version fehlt, laufen dafür aber 17 %
langsamer und mit schwarzen Balken. Dieses Werkzeug ändert die Videonorm
innerhalb der PAL-Fassung selbst, damit die Lokalisierung bleibt und das Bild
trotzdem mit 60 Hz läuft.

Jede Änderung wird an Ort und Stelle geschrieben, byteweise gleich groß, und
lässt sich jederzeit zurücknehmen.

![PAL2NTSC](docs/screenshot.png)

```
python pal2ntsc_cli.py patch "Final Fantasy X (PAL).iso"
```

oder das Image ins Fenster ziehen:

```
PAL2NTSC.bat
```

## Was es kann

* **Vier Plattformen**: PlayStation, PlayStation 2, GameCube, Xbox
* **Vollständig umkehrbar**: Eine kleine Journaldatei neben dem Image merkt
  sich die Originalbytes, die Rücknahme dauert Sekunden statt eine Sicherung
  zurückzuspielen
* **Nichts wird geraten**: Jeder Patch wird über die Struktur im Executable
  gefunden, vor dem Schreiben Byte für Byte geprüft und abgelehnt, wenn das
  Image nicht passt
* **Weiß, wann nichts zu tun ist**: Eine Datenbank mit 1648 Titeln sagt, ob ein
  Spiel bereits selbst auf 60 Hz umschalten kann
* **Deutsch und Englisch**, Oberfläche, Meldungen und Hilfe im Programm
* Oberfläche mit Drag and Drop, dazu eine Kommandozeile für ganze Ordner

## Voraussetzungen

Python 3.8 oder neuer. Für Drag and Drop optional:

```
pip install tkinterdnd2
```

Alles andere funktioniert auch ohne. Weitere Abhängigkeiten gibt es nicht.

## Bedienung

### Oberfläche

`PAL2NTSC.bat` starten (oder `pythonw PAL2NTSC.pyw`), Images ins Fenster
ziehen, Patches ankreuzen, *Patchen* drücken. Die Sprachauswahl sitzt oben
rechts.

### Kommandozeile

```
python pal2ntsc_cli.py scan   <datei|ordner> [...]   nur analysieren
python pal2ntsc_cli.py patch  <datei> [--all] [--backup] [-y]
python pal2ntsc_cli.py revert <datei> [--only NAME ...] [--list]
python pal2ntsc_cli.py help
```

Mit `--lang de` oder `--lang en` lässt sich die Ausgabesprache umstellen.
`scan` nimmt auch ganze Ordner. Ohne `--all` werden nur die empfohlenen Patches
angewendet, optionale wie Regionskennungen bleiben außen vor.

## Wie es arbeitet

Jede Änderung wird **an Ort und Stelle und mit exakt gleicher Byteanzahl**
geschrieben. Das ist keine Stilfrage: Sobald sich Größe oder
Inhaltsverzeichnis eines PS2-Images ändern, wird es nicht mehr als PS2-Disc
erkannt.

Daraus folgt der angenehme Nebeneffekt beim Rückgängigmachen. Weil nur wenige
Bytes ersetzt werden, genügt eine kleine Journaldatei neben dem Image:

```
Final Fantasy X (PAL).iso              4.600.725.504 Bytes
Final Fantasy X (PAL).iso.pal2ntsc.json          631 Bytes
```

Das Journal enthält Offset sowie Original- und Patchbytes. *Rücknahme* schreibt
die Originalbytes zurück. Vor jedem Schreibvorgang wird geprüft, ob an der
Zieladresse wirklich noch die erwarteten Bytes stehen, sonst bricht der Vorgang
ab, statt etwas zu zerstören. Eine Vollkopie (`.bak`) lässt sich zusätzlich
ankreuzen, für die Rücknahme ist sie nicht nötig.

### PlayStation 2

Sonys `libgraph` initialisiert die Grafik über
`sceGsResetGraph(mode, interlace, omode, ffmd)`. Der dritte Parameter wählt die
Videonorm: 2 steht für NTSC, 3 für PAL. Im Funktionsprolog wird er mit
`sra rd, a2, 16` vorzeichenrichtig aus dem Argument geholt; der Patch ersetzt
das durch `addiu rd, zero, 2` und legt NTSC damit fest.

Gefunden wird die Funktion über ihren GS-Reset, das Schreiben von `0x200` nach
`0x12001000` (GS_CSR), nicht über Symbole. Das funktioniert auch ohne
Debug-Informationen.

> Gegen eine Sammlung von 40 PAL-Titeln geprüft: **37 erkannt**. Die drei
> Ausnahmen sind 007-Titel mit sehr kleinen Loader-Executables, die das
> eigentliche Spiel erst nachladen.

### GameCube

Das SDK legt im `main.dol` für jede Videonorm eine 60 Byte große Struktur
(`GXRModeObj`) ab: NTSC, MPAL, PAL, EURGB60. Ein PAL-Spiel greift zur Laufzeit
auf die PAL-Struktur zu, also überschreibt der Patch deren Inhalt mit der
EURGB60-Struktur, die in derselben Datei bereits vorliegt.

Der Vorteil: Die Zielwerte müssen nicht erfunden werden, sie stammen aus dem
Spiel selbst. Die Spiellogik bleibt unangetastet.

### PlayStation

`libgpu` hält den Videomodus in einer globalen Variablen, die `SetVideoMode`
beschreibt. Der Patch ersetzt dort `sw $a0` durch `sw $zero`, damit immer 0
und somit NTSC in der Variablen landet, unabhängig davon, was das Spiel
übergibt. Die Methode stammt aus dem Werkzeug PALNTSC von KEuBo aus dem Jahr
1999, dessen README den Eingriff im Klartext zeigt.

Das Codemuster allein genügt nicht, denn eine andere `libgpu`-Funktion ist
identisch gebaut. Unterschieden werden beide über das Zugriffsprofil ihrer
Variablen: Die Videomodus-Variable wird nur von ihrem eigenen Getter gelesen
und an genau einer Stelle geschrieben.

| Profil | Bedeutung | Fundstellen |
|---|---|---:|
| 2 Leser, 1 Schreiber | echtes `SetVideoMode` | 74 |
| 1 Leser, 3 bis 4 Schreiber | andere Funktion, nicht patchen | 40 |

Ohne diese Prüfung würden bei 30 Titeln zusätzliche, falsche Stellen
mitgepatcht.

> Gegen die PAL-Titel der Sammlung geprüft: **69 von 76 patchbar (90 %)**,
> jeweils genau eine Fundstelle pro Spiel.

Da PS1-Images fast immer als Rohsektoren vorliegen, wird nach jeder Änderung
EDC/ECC nach ECMA-130 neu berechnet, sonst schlüge die Fehlerkorrektur an.

> Die EDC/ECC-Berechnung wurde gegen echte Pressungen geprüft: 48 von 48
> Sektoren aus vier Spielen wurden bitgenau reproduziert.

### Xbox

Offen gesagt: Der Videostandard der Xbox steckt **nicht im Image**. Die Konsole
liefert ihn aus dem EEPROM (Dashboard-Einstellung), Spiele fragen ihn über
`XGetVideoStandard()` ab. Ein Image-Patch kann das nicht ersetzen. Der richtige
Hebel ist die Konsolen- oder Emulatoreinstellung, in xemu die Videonorm NTSC-M.

Was das Modul leisten kann: die Regionskennung im XBE-Zertifikat aufweiten,
damit ein Titel nicht an einer Regionsprüfung scheitert. Erkannt werden sowohl
Redump-Images als auch mit `extract-xiso` neu gebaute. Dateien mit der Endung
`.old` oder `.bak` werden nie gepatcht, sie gelten als Sicherung.

## Die Titeldatenbank

`pal2ntsc/data/pal60_db.json` sagt vor dem Patchen, ob ein Spiel bereits selbst
zwischen 50 und 60 Hz umschalten kann. Wenn ja, erübrigt sich der Eingriff
meist.

| Plattform | Titel | davon 60-Hz-fähig |
|---|---:|---:|
| PlayStation 2 | 978 | 276 |
| GameCube | 248 | 76 |
| Xbox | 208 | 112 |
| PlayStation | 214 | 75 |

Die Zuordnung läuft über die Game-ID oder, wo die Quellen nur Titel führen,
über einen normalisierten Titelvergleich. Ein nur unscharfer Treffer wird als
solcher gekennzeichnet.

**Alle Angaben sind Community-Wissen, nicht selbst nachgeprüft.** Jeder Eintrag
führt seine Herkunft mit. Unabhängig von den Listen durchsucht das Werkzeug
jedes Image selbst nach 50/60-Hz-Texten, das erkennt auch Titel, die in keiner
Liste stehen. Die Quellen stehen am Ende dieser Datei.

## Was ein Patch leistet, und was nicht

Umgestellt wird die Videonorm. Ob daraus auch flüssigere 60 fps werden, hängt
vom Spiel ab:

* Viele Titel hängen ihre Logik am Bildaufbau, sie laufen dann tatsächlich
  schneller und flüssiger.
* Andere behalten PAL-Timing bei, dann wird nur das Bild mit 60 Hz ausgegeben.
* Manche PAL-Fassungen rendern weiterhin mehr Zeilen, als NTSC anzeigt. Das
  Bild kann dann unten beschnitten wirken, siehe nächster Abschnitt.

Reagiert ein Spiel unerwartet, stellt *Rücknahme* den Originalzustand her.

## Spielspezifische Patches

Gelegentlich sitzt nach dem Wechsel das Bild unten abgeschnitten, das HUD
verschwindet halb. Die Ursache ist nicht die Bildlage, sondern die
**Renderhöhe**: Das Spiel zeichnet weiterhin für PAL mit 512 Zeilen, während
NTSC nur 448 anzeigt.

Beispiel *The Simpsons: Hit & Run* (PAL), bei `0x003734C0`:

```
addiu $v1, $zero, 0x1c0   ; 448  (NTSC)
addiu $a0, $zero, 0x200   ; 512  (PAL)
lw    $v0, 4($a1)         ; PAL-Flag
movn  $v1, $a0, $v0       ; setzt auf 512
sw    $v1, 0x28($s0)      ; als Renderhöhe ablegen
```

Ein `nop` auf das `movn` lässt den NTSC-Wert stehen, damit ist es behoben.

Verallgemeinern lässt sich das nicht, denn jedes Spiel trifft diese Auswahl
anders. Solche Fälle stehen in `pal2ntsc/data/game_patches.json`, nach Game-ID
abgelegt und einzeln erweiterbar. Die Offsets beziehen sich auf das Executable,
nicht auf das Image, und jede Fundstelle wird byteweise geprüft. Ein Eintrag
gilt erst als `"verified": true`, wenn seine Wirkung im Spiel nachgesehen
wurde, nicht schon, wenn der Code plausibel aussieht.

Neue Fälle findet:

```
python tools/find_height_select.py "<image.iso>"
```

Das Werkzeug gibt einen fertigen Datenbankeintrag aus. Findet es nichts, meldet
es, ob die Höhenkonstanten überhaupt im Code vorkommen. Das unterscheidet
"Spiel ist nicht betroffen" von "andere Bauart, von Hand nachsehen".

## Aufbau

```
PAL2NTSC.pyw            Oberfläche (Drag and Drop, DE/EN)
pal2ntsc_cli.py         Kommandozeile
pal2ntsc/
  __init__.py           analyse() / patch() / revert(), Datenbankanbindung
  i18n.py               zweisprachiger Meldungskatalog
  help_text.py          Hilfe im Programm
  journal.py            Patch-Journal, Prüfung und Rücknahme
  gamepatch.py          spielspezifische Patches aus der Datenbank
  platforms/
    common.py           Patch- und GameInfo-Typen
    ps2.py  gamecube.py  ps1.py  ps1_sig.py  xbox.py
    cdrom_ecc.py        EDC/ECC nach ECMA-130 für PS1-Rohsektoren
  data/
    pal60_db.json       Titeldatenbank
    game_patches.json   spielspezifische Patches
    ps1_signatures.json zusätzliche PS1-Signaturen
tools/
  import_db.py          baut die Titeldatenbank aus gespeicherten Quellen
  find_height_select.py findet Renderhöhen-Auswahlen
```

## Rechtliches

Dieses Werkzeug verändert Disc-Images, die man bereits besitzt. Es enthält
keinen Spielcode, keine Schlüssel und keine urheberrechtlich geschützten
Spieldaten. Eine Sicherungskopie eigener Medien ist in vielen Rechtsordnungen
zulässig, aber nicht in allen, bitte die örtliche Rechtslage prüfen. Das
Beschaffen oder Verbreiten von Spielen, die man nicht besitzt, ist es nicht.

## Dank

* **PALNTSC** (KEuBo, TEAM STufF, 1999) beschreibt den PS1-Eingriff an
  `SetVideoMode` in seiner README, darauf beruht die PlayStation-Methode hier.
  Der Code in diesem Repository ist eine eigenständige Umsetzung.
* **PALadin** von [ticky](https://github.com/ticky/paladin) wies auf
  `PutDispEnv` und die Behandlung der Y-Position hin.
* Die Titeldatenbank entstand aus Community-Listen: dem ConsoleMods Wiki
  (GameCube-Anzeigemodi, PAL-optimierte PlayStation-Titel), einer Liste zur
  60-Hz-Unterstützung in PAL-PlayStation-2-Spielen sowie einer
  Blogspot-Zusammenstellung von Xbox-Titeln mit PAL60-Unterstützung.

## Autor und Lizenz

Geschrieben von **frankyfife**.

Veröffentlicht unter der [MIT-Lizenz](LICENSE).
