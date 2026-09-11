# FOTOFIX.C000 — WiC64-Treiber

Diese Maschinencode-Routine (laedt nach `$C000`/49152) uebernimmt die
WiC64-Low-Level-Details (User-Port-Protokoll zum ESP32-Modul) und stellt
einen einzigen wiederverwendbaren Einsprungpunkt bereit:
`SYS 49152,U$,Zieladresse` — ruft die URL in `U$` ab und schreibt die
Antwort byteweise (nullterminiert) ab der angegebenen Speicheradresse.
Init vorher per `SYS 50497` (siehe `tron_c64_wic64_client.bas`).

**Autor: Andreas Beermann** ("andi6510"), urspruenglich Teil eines
FOTOFIX-Beispielprogramms fuer Classic Computing (Besucherfoto +
Event-Bildabruf per WiC64). Fuer `tron_c64_wic64_client.bas` wird
ausschliesslich der bestehende `SYS 49152`-Einsprungpunkt wiederverwendet
— keine eigene WiC64-Assembler-Routine geschrieben, siehe
[`CLAUDE.md`](../../../CLAUDE.md).

## Datei

`FOTOFIX.C000` muss auf derselben Diskette/demselben SD2IEC-Image wie
`tron_c64_wic64_client.bas` liegen (gleicher Dateiname, per `LOAD"FOTOFIX.C000",8,1`
geladen). Extrahiert aus der von Andreas Beermann bereitgestellten
`fotofix.d64` (Original-Diskette enthaelt zusaetzlich `fotofix` — das
vollstaendige FOTOFIX-Beispielprogramm — und `rtbwic64`, eine bereits auf
die Diskette getippte Kopie unseres eigenen WiC64-Clients fuers Testen auf
echter Hardware).

## Bekannter Fehlerstring in der Routine

Ein `NETWORK TIMEOUT` (als PETSCII-Text im Code gefunden) deutet darauf
hin, dass die Routine bei einem WiC64-Timeout selbst einen Fehlertext in
den Zielspeicher schreibt statt nur `PEEK(783)` zu setzen — noch nicht
weiter verifiziert, siehe offener Punkt in `CLAUDE.md`.
