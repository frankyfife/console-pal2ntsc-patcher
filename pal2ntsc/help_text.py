"""Hilfetext fuer das Hilfe-Fenster / help text shown in the Help window."""

HELP = {
'de': """
PAL2NTSC: Kurzanleitung

  1.  Disc-Images ins Fenster ziehen (oder oben "Dateien…" / "Ordner…").
  2.  Eintrag in der Liste anklicken, darunter erscheinen Infos und Patches.
  3.  Gewuenschte Patches ankreuzen und auf "Patchen" klicken.
  4.  Gefaellt das Ergebnis nicht: "Ruecknahme" stellt das Original wieder her.

  "Alle patchen" wendet die empfohlenen Patches auf jedes Image der Liste an.
  Optionale Eingriffe (Region, Game-ID) bleiben dabei bewusst aussen vor.


WARUM UEBERHAUPT PATCHEN?

  PAL-Fassungen laufen mit 50 Hz statt 60 Hz. Auf die NTSC-Fassung auszuweichen
  loest das zwar, kostet aber meist die deutsche Sprachfassung. Dieses Werkzeug
  stellt stattdessen die PAL-Fassung auf NTSC um, Lokalisierung bleibt, das
  Bild laeuft mit 60 Hz.


ALLES BLEIBT UMKEHRBAR

  Jede Aenderung wird an Ort und Stelle und mit exakt gleicher Byteanzahl
  geschrieben. Das ist keine Marotte: Sobald sich Groesse oder
  Inhaltsverzeichnis eines PS2-Images aendern, wird es nicht mehr als PS2-Disc
  erkannt.

  Weil nur wenige Bytes ersetzt werden, genuegt zum Rueckgaengigmachen eine
  kleine Journaldatei neben dem Image:

      spiel.iso                    4.600.725.504 Bytes
      spiel.iso.pal2ntsc.json                631 Bytes

  Darin stehen Offset sowie Original- und Patchbytes. "Ruecknahme" schreibt die
  Originalbytes zurueck: Sekunden statt einer Vollkopie. Vor jedem Schreiben
  wird geprueft, ob an der Zieladresse wirklich noch die erwarteten Bytes
  stehen; sonst bricht der Vorgang ab, statt etwas zu zerstoeren.

  Die Vollkopie (.bak) ist zusaetzlich moeglich, aber fuer die Ruecknahme nicht
  noetig. Bitte die Journaldatei neben dem Image liegen lassen.


WAS AUF WELCHER PLATTFORM PASSIERT

  PlayStation 2: zuverlaessig
      Sonys libgraph richtet die Grafik ueber sceGsResetGraph ein. Deren
      dritter Parameter waehlt die Videonorm (2 = NTSC, 3 = PAL). Der Patch
      legt ihn auf NTSC fest. Die Funktion wird ueber ihren GS-Reset erkannt,
      nicht ueber Symbole: das klappt auch ohne Debug-Informationen.
      Gegen 40 PAL-Titel geprueft: 37 erkannt.

  GameCube: zuverlaessig
      Im main.dol liegt fuer jede Videonorm eine 60-Byte-Struktur
      (GXRModeObj). Der Patch ueberschreibt die PAL-Struktur mit der
      EURGB60-Struktur, die im selben Spiel bereits vorhanden ist. Die
      Zielwerte werden also nicht erfunden, sondern stammen aus dem Spiel
      selbst.

  PlayStation: zuverlaessig, wo die Signatur greift
      Die libgpu haelt den Videomodus in einer globalen Variablen, die
      SetVideoMode beschreibt. Der Patch ersetzt dort "sw $a0" durch
      "sw $zero", damit landet immer 0 = NTSC darin, egal was das Spiel
      uebergibt. Die Methode stammt aus dem Werkzeug PALNTSC (KEuBo, 1999).
      Gesucht wird nach dem Muster, nicht nach festen Bytes, denn die Adresse
      unterscheidet sich je Spiel.

      Das Codemuster allein genuegt nicht: eine andere libgpu-Funktion ist
      genauso gebaut. Unterschieden werden beide ueber das Zugriffsprofil der
      Variablen, der Videomodus wird nur vom eigenen Getter gelesen und an
      genau einer Stelle geschrieben (2 Leser, 1 Schreiber). Die Verwechslung
      kommt auf 1 Leser und 3-4 Schreiber und wird verworfen.

      Ergebnis in dieser Sammlung: 69 von 76 PAL-Titeln patchbar, jeweils genau
      eine Stelle. Bleiben Kandidaten uebrig, ohne dass einer eindeutig ist,
      sind sie nicht vorausgewaehlt, dann einzeln anwenden und das Spiel
      pruefen; die Ruecknahme stellt jederzeit das Original her.

      Weil PS1-Images als Rohsektoren vorliegen, wird nach jeder Aenderung
      EDC/ECC neu berechnet (gegen echte Pressungen geprueft).

  Xbox: nur Region
      Der Videostandard steckt bei der Xbox nicht im Image, sondern im EEPROM
      der Konsole. Ein Image-Patch kann das nicht ersetzen; in xemu stellt man
      die Videonorm auf NTSC-M. Das Werkzeug kann die Regionskennung im XBE
      aufweiten, damit ein Titel nicht an einer Regionspruefung scheitert.

  Wii-Images werden erkannt, aber nicht angefasst, ihre Daten liegen in
  verschluesselten Partitionen. In Dolphin laesst sich der Modus direkt setzen.


DIE DATENBANK

  Vor dem Patchen wird nachgeschlagen, ob das Spiel bereits selbst zwischen
  50 und 60 Hz umschalten kann. Dann eruebrigt sich der Eingriff meist.

  1648 Titel aus vier zusammengetragenen Community-Listen. Alle Angaben sind
  Ueberlieferung, nicht selbst nachgeprueft, jeder Eintrag fuehrt seine
  Herkunft mit. Zusaetzlich durchsucht das Werkzeug jedes Image selbst nach
  50/60-Hz-Texten; das erkennt auch Titel, die in keiner Liste stehen.

  Ein nur unscharf zugeordneter Treffer wird als solcher gekennzeichnet,
  in dem Fall bitte den Titel gegenpruefen.


SPIELSPEZIFISCHE PATCHES (ABGESCHNITTENES BILD)

  Bei manchen Spielen sitzt das Bild nach dem Moduswechsel unten abgeschnitten,
  das HUD verschwindet halb. Ursache ist nicht die Bildlage, sondern die
  RENDERHOEHE: Das Spiel zeichnet weiter fuer PAL (512 Zeilen), waehrend NTSC
  nur 448 anzeigt. Im Code steht dann eine Auswahl zwischen beiden Werten,
  wird sie auf den NTSC-Wert festgelegt, sitzt alles richtig. So geloest bei
  "The Simpsons: Hit & Run".

  Verallgemeinern laesst sich das nicht: Jedes Spiel trifft diese Auswahl
  anders. Solche Faelle stehen deshalb einzeln in data/game_patches.json, nach
  Game-ID. Passen die erwarteten Bytes nicht, wird der Eintrag verworfen, dann
  ist es eine andere Spielfassung. Als "geprueft" gilt ein Eintrag erst, wenn
  seine Wirkung im Spiel nachgesehen wurde.

  Nicht verwechseln: Die Bildlage (DISPLAY-Register, DX/DY) verschiebt nur, wo
  das Bild sitzt, gegen das Abschneiden hilft sie nicht.

  Neue Faelle findet  tools/find_height_select.py <image.iso>


WAS EIN PATCH LEISTET, UND WAS NICHT

  Umgestellt wird die Videonorm. Ob daraus auch fluessigere 60 fps werden,
  haengt vom Spiel ab:

    •  Viele Titel haengen ihre Logik am Bildaufbau, sie laufen dann
       tatsaechlich schneller und fluessiger.
    •  Andere behalten PAL-Timing bei; dann wird nur das Bild in 60 Hz
       ausgegeben.
    •  Manche PAL-Fassungen rendern weiterhin mehr Zeilen. Das Bild kann dann
       vertikal verschoben wirken oder unten beschnitten sein.

  Reagiert ein Spiel unerwartet, stellt "Ruecknahme" den Originalzustand her.


SICHERUNGSDATEIEN

  Dateien mit der Endung .old oder .bak werden nie gepatcht, sie gelten als
  Sicherung. Bei Xbox-Images betrifft das die Original-Dumps, die
  extract-xiso beim Neuaufbau zuruecklaesst; gepatcht wird die aktive .iso.


ZEICHEN IN DER LISTE

  [x]  empfohlener Patch, standardmaessig aktiv
  [ ]  optionaler Patch, bewusst nicht vorausgewaehlt
  (!)  Nebenwirkungen beachten, der Hinweistext darunter sagt welche
""",

'en': """
PAL2NTSC: Quick guide

  1.  Drop disc images onto the window (or use "Files…" / "Folder…" above).
  2.  Click an entry in the list, details and patches appear below.
  3.  Tick the patches you want and press "Patch".
  4.  Don't like the result? "Revert" restores the original.

  "Patch all" applies the recommended patches to every image in the list.
  Optional changes (region, game ID) are deliberately left out.


WHY PATCH AT ALL?

  PAL releases run at 50 Hz instead of 60 Hz. Switching to the NTSC release
  fixes that but usually costs you the localised language track. This tool
  converts the PAL release to NTSC instead: the localisation stays, the
  picture runs at 60 Hz.


EVERYTHING STAYS REVERSIBLE

  Every change is written in place and at exactly the same byte count. That
  is not a quirk: as soon as the size or table of contents of a PS2 image
  changes, it is no longer recognised as a PS2 disc.

  Because only a few bytes are replaced, a small journal file next to the
  image is enough to undo everything:

      game.iso                     4,600,725,504 bytes
      game.iso.pal2ntsc.json                 631 bytes

  It holds the offset plus the original and patched bytes. "Revert" writes the
  original bytes back: seconds instead of a full copy. Before each write the
  tool checks that the expected bytes are still at the target address;
  otherwise it aborts rather than destroying anything.

  A full copy (.bak) is available as well but is not needed for reverting.
  Please keep the journal file next to the image.


WHAT HAPPENS ON EACH PLATFORM

  PlayStation 2: reliable
      Sony's libgraph sets up graphics through sceGsResetGraph. Its third
      parameter selects the video standard (2 = NTSC, 3 = PAL). The patch pins
      it to NTSC. The function is located through its GS reset rather than
      through symbols, so it works without debug information.
      Checked against 40 PAL titles: 37 detected.

  GameCube: reliable
      main.dol holds a 60-byte structure (GXRModeObj) per video standard. The
      patch overwrites the PAL structure with the EURGB60 structure already
      present in the same game. The target values are therefore not invented,
      they come from the game itself.

  PlayStation: reliable where the signature matches
      libgpu keeps the video mode in a global variable written by
      SetVideoMode. The patch replaces "sw $a0" there with "sw $zero", so the
      variable always receives 0 = NTSC no matter what the game passes in. The
      method comes from the tool PALNTSC (KEuBo, 1999). The search is for the
      pattern rather than fixed bytes, since the address differs per game.

      The code pattern alone is not enough: another libgpu function is built
      the same way. The two are told apart by the access profile of their
      variable, the video mode is read only by its own getter and written in
      exactly one place (2 readers, 1 writer). The look-alike comes to 1 reader
      and 3-4 writers and is discarded.

      Result in this collection: 69 of 76 PAL titles patchable, exactly one
      site each. Where only candidates remain and none is conclusive, they are
      not preselected, apply one at a time and check the game; revert restores
      the original at any point.

      Because PS1 images come as raw sectors, EDC/ECC is recomputed after
      every change (verified against real pressings).

  Xbox: region only
      On the Xbox the video standard lives in the console's EEPROM, not in the
      image. An image patch cannot replace that; in xemu set the video standard
      to NTSC-M. The tool can widen the region flag in the XBE so a title does
      not fail a region check.

  Wii images are recognised but left alone: their data sits in encrypted
  partitions. Dolphin can set the mode directly.


THE DATABASE

  Before patching, the tool checks whether the game can already switch between
  50 and 60 Hz by itself. If so, the change is usually unnecessary.

  1648 titles from four community-compiled lists. All of it is received
  wisdom, not independently verified, each entry carries its provenance. In
  addition the tool searches each image itself for 50/60 Hz strings, which
  catches titles missing from every list.

  A merely approximate match is flagged as such: please verify the title in
  that case.


GAME-SPECIFIC PATCHES (CROPPED PICTURE)

  On some games the picture ends up cropped at the bottom after the mode
  switch, with half the HUD gone. The cause is not the screen position but the
  RENDER HEIGHT: the game still draws for PAL (512 lines) while NTSC shows only
  448. The code then holds a choice between the two values, pin it to the NTSC
  one and everything sits correctly. That is how "The Simpsons: Hit & Run" was
  solved.

  This does not generalise: every game makes that choice differently. Such
  cases are listed individually in data/game_patches.json, keyed by game ID. If
  the expected bytes do not match, the entry is discarded, then it is a
  different revision. An entry counts as verified only once its effect has been
  checked in the game.

  Not to be confused: the screen position (DISPLAY register, DX/DY) only moves
  where the picture sits, it does nothing about the cropping.

  New cases can be found with  tools/find_height_select.py <image.iso>


WHAT A PATCH DOES: AND DOES NOT DO

  What changes is the video standard. Whether that also yields smoother 60 fps
  depends on the game:

    •  Many titles tie their logic to the frame refresh, those genuinely run
       faster and smoother.
    •  Others keep PAL timing; then only the picture is output at 60 Hz.
    •  Some PAL releases still render more scanlines. The picture may then sit
       vertically offset or look cropped at the bottom.

  If a game misbehaves, "Revert" restores the original state.


BACKUP FILES

  Files ending in .old or .bak are never patched, they count as backups. For
  Xbox images this covers the original dumps that extract-xiso leaves behind
  when rebuilding; the active .iso is what gets patched.


MARKERS IN THE LIST

  [x]  recommended patch, enabled by default
  [ ]  optional patch, deliberately not preselected
  (!)  mind the side effects, the note underneath says which
""",
}
