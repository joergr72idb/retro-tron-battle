# Tools

## Eigene Diagnose-/Testprogramme

Kleine, isolierte `.bas`-Testprogramme, entstanden beim Eingrenzen von
Plattform-Eigenheiten (siehe `CLAUDE.md`) - kein Teil des eigentlichen
Spiels, aber nützlich als Ausgangspunkt für ähnliche Diagnosen auf einer
neuen Plattform:

- `atari_http_test.bas` - isolierter FujiNet-`N:HTTP`-Test
- `joystick_test.bas` / `joystick_network_test.bas` - Joystick-Port-Tests
- `meatloaf_netztest.bas` - isolierter Meatloaf-HTTP-Test

## Gebündelte Drittanbieter-Tools

### `d64-inspector/`

GTK4-Programm zum Inspizieren/Editieren von D64-Diskettenimages (siehe
`CLAUDE.md`, Abschnitt "Testen ohne echte Hardware", zum Verpacken von
BASIC-Programmen in ein D64-Image für VICE-Tests). Quellcode aus dem
Original-Git-Clone übernommen (ohne `.git`- und Build-Artefakte).

**Autor: P. David Buchan** (pdbuchan@gmail.com), Lizenz: GPLv3.
Original-Repo: <https://github.com/pdbuchan/d64-inspector>

**Bauen unter Ubuntu/Debian:**

```bash
sudo apt install build-essential pkg-config libgtk-4-dev
```

Für die PETSCII-Anzeige vorher die TrueType-Fonts aus
[`C64_TrueType_v1.2.1-STYLE/`](./C64_TrueType_v1.2.1-STYLE/) installieren
(z.B. nach `~/.local/share/fonts/` kopieren und `fc-cache -f` ausführen).
Danach:

```bash
cd d64-inspector/src
make
```

Das fertige Programm heißt `inspector` (nicht Teil dieses Repos, wird
lokal gebaut).

### `C64_TrueType_v1.2.1-STYLE/`

Die "C64 TrueType"-Fontfamilie, von `d64-inspector` für die
PETSCII-Ansicht verwendet. Unveränderte Original-Distribution.

**Autor: "Style"** (style64.org), siehe `license.txt` in diesem Ordner
für die genauen Nutzungsbedingungen (u.a.: nicht umbenennen/verändern,
nur als Teil einer frei verfügbaren Software-Sammlung weitergeben).
Projektseite: <https://style64.org/c64-truetype>
