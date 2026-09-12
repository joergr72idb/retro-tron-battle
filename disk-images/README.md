# Referenz-Disk-Images

Fertige, boot-/ladefähige Disk-Images, wie sie beim Aufsetzen der echten
Hardware für dieses Projekt tatsächlich benutzt wurden. Der `.bas`-Quelltext
in [`clients/`](../clients/) bleibt die maßgebliche Quelle — diese Images
sind praktische Startpunkte/Referenz, kein Ersatz dafür (können ältere
Client-Stände enthalten).

## `n-handler.atr`

Atari-Diskettenimage (FujiNet-SD-Karten-Inhalt) mit dem `N:`-Netzwerk-Handler,
den der Atari-Client für TCP/HTTP über FujiNet braucht, sowie einem älteren
Stand des Atari-Clients. Nützlich als Startpunkt beim Neuaufsetzen einer
FujiNet-SD-Karte (Handler drauf, dann den aktuellen
[`clients/atari/tron_atari_client.bas`](../clients/atari/tron_atari_client.bas)
per Paste in Altirra/Fujisan aktualisieren) — siehe `CLAUDE.md`, Abschnitt
"Clients auf die Zielsysteme übertragen".

## `cpcclient2.dsk`

Schneider/Amstrad-CPC-Diskettenimage mit einem älteren Stand des
CPC-Clients (AMSDOS-Header bereits korrekt gesetzt, siehe die
"Line too long"-Lektion in `CLAUDE.md`). Referenz für den
WinAPE-Workflow beim Erstellen einer neuen M4-Diskette.

## `fotofix.d64`

Original-Diskette von Andreas Beermann ("andi6510"), aus der
`FOTOFIX.C000` (die WiC64-Treiberroutine in
[`clients/c64/wic64-driver/`](../clients/c64/wic64-driver/)) extrahiert
wurde. Enthält zusätzlich `fotofix` (das vollständige FOTOFIX-
Beispielprogramm) und `rtbwic64` (eine bereits auf die Diskette getippte
Kopie eines früheren Stands unseres eigenen WiC64-Clients). Siehe
[`clients/c64/wic64-driver/README.md`](../clients/c64/wic64-driver/README.md)
für Details/Credit.
