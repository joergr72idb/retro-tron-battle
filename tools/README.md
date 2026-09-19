# Tools

## Eigene Diagnose-/Testprogramme

Kleine, isolierte `.bas`-Testprogramme, entstanden beim Eingrenzen von
Plattform-Eigenheiten (siehe `CLAUDE.md`) - kein Teil des eigentlichen
Spiels, aber nützlich als Ausgangspunkt für ähnliche Diagnosen auf einer
neuen Plattform:

- `atari_http_test.bas` - isolierter FujiNet-`N:HTTP`-Test
- `atari_joystick_test.bas` / `joystick_network_test.bas` - Atari-Joystick-Port-Tests
  (Standalone bzw. mit Networking, siehe unten)
- `c64_joystick_test.bas` - Standalone-Joystick-Test fuer C64, zeigt Port 1
  ($dc01) und Port 2 ($dc00) gleichzeitig live an, um das Keyboard-Scan-
  Ghosting-Problem (siehe `CLAUDE.md`) direkt sichtbar zu machen
- `cpc_joystick_test.bas` - Standalone-Joystick-Test fuer Schneider CPC
  (`JOY(0)`, raw + dekodiert)
- `meatloaf_netztest.bas` - isolierter Meatloaf-HTTP-Test

## Externe Tools (nicht mehr im Repo gebündelt)

Vorher lagen hier lokale Kopien der beiden folgenden Drittanbieter-Tools;
um das Repo klein zu halten, sind sie jetzt nur noch verlinkt - bei Bedarf
selbst von dort herunterladen:

### d64-inspector

GTK4-Programm zum Inspizieren/Editieren von D64-Diskettenimages (siehe
`CLAUDE.md`, Abschnitt "Testen ohne echte Hardware", zum Verpacken von
BASIC-Programmen in ein D64-Image für VICE-Tests).

**Autor: P. David Buchan** (pdbuchan@gmail.com), Lizenz: GPLv3.
Repo: <https://github.com/pdbuchan/d64-inspector>

**Bauen unter Ubuntu/Debian:**

```bash
sudo apt install build-essential pkg-config libgtk-4-dev
cd d64-inspector/src
make
```

Für die PETSCII-Anzeige vorher die C64-TrueType-Fonts installieren, siehe
unten.

### C64 TrueType

Die "C64 TrueType"-Fontfamilie, von `d64-inspector` für die
PETSCII-Ansicht verwendet.

**Autor: "Style"** (style64.org), Lizenz siehe Downloadseite (u.a.: nicht
umbenennen/verändern, nur als Teil einer frei verfügbaren
Software-Sammlung weitergeben). Download/Projektseite:
<https://style64.org/c64-truetype>
