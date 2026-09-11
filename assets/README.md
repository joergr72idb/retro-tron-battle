# assets/

Lokale Bild- und Font-Dateien fuer den Server (`server/tron_server.py`),
referenziert per relativem Pfad ab dem Projekt-Root — dorthin kopieren
und committen, dann laeuft der Server auf jeder Maschine ohne Pfade
anzupassen.

## assets/logos/

Firmenlogos + Vereinslogo. Dateiname pro Plattform (erste passende
Erweiterung gewinnt: .png, .jpg, .jpeg, .gif, .bmp, jeweils gross-
oder kleingeschrieben):

- `atari.*` — Atari
- `commodore.*` oder `c64.*` — Commodore 64
- `schneider.*`, `cpc.*` oder `amstrad.*` — Schneider/Amstrad CPC
- `logo.*` — Vereinslogo der Veranstaltung (oben rechts, dauerhaft
  sichtbar)

Firmenlogos werden bei jedem neuen Match neu geladen (kein Neustart
noetig). Das Vereinslogo wird nur einmal beim Serverstart geladen.

## assets/font/

Die `.ttf`-Datei fuer den Demo-Scrolltext, siehe `SCROLL_FONT_PATH` in
`server/tron_server.py`. Leer lassen (`SCROLL_FONT_PATH = ""`) fuer die
Standard-Schrift, falls keine eigene Font verwendet werden soll.

**Lizenz beachten:** Falls die Font (z.B. ein "Flynn"/TRON-Fanfont)
nur fuer den persoenlichen Gebrauch freigegeben ist, ggf. vor einem
oeffentlichen Push pruefen, ob eine Weiterverteilung ueber das
Git-Repo erlaubt ist.
