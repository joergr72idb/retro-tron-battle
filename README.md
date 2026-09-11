# Retro Tron Battle

Ein Netzwerk-Lightcycle-Duell für echte Retro-Computer (Atari XL/XE,
Commodore 64, Schneider/Amstrad CPC) mit serverseitiger Darstellung —
gebaut für Classic Computing 2026.

Ausführliche Hintergründe, Design-Entscheidungen und mühsam erarbeitete
Plattform-Eigenheiten stehen in [`CLAUDE.md`](./CLAUDE.md) — bitte vor
größeren Änderungen lesen.

## Schnellstart

```bash
pip install pygame
python3 server/tron_server.py [host] [tcp_port] [http_port]
# Standard: 0.0.0.0 6502 8080
```

Das Server-Fenster zeigt Spielfeld, Besucherfotos, Logos und einen
Demo-Scrolltext, solange auf Spieler gewartet wird.

## Projektstruktur

```
server/     Der Python-Server (Spiellogik + pygame-Anzeige)
clients/    BASIC-Clients pro Plattform
  atari/    Atari XL/XE + FujiNet (rohes TCP)
  c64/      Commodore 64 - zwei Varianten:
              tron_c64_client.bas       (Meatloaf, HTTP-Polling, stabil)
              tron_c64_wic64_client.bas (WiC64, experimentell)
  cpc/      Schneider/Amstrad CPC + M4-Board (HTTP-Polling)
bots/       Automatisierte Test-Bots (Bash/PowerShell) zum Spielen ohne
            echte Hardware, z.B. für Demos oder Lasttests
tools/      Diagnose-/Testprogramme für einzelne Plattformen
docs/       PDF-Dokumentation (Protokoll, Erweiterung um weitere Plattformen)
archive/    Verworfene Ansätze, aus Referenzgründen aufbewahrt
```

## Clients einrichten

Jeder `.bas`-Client hat einen kurzen Konfigurationsblock ganz oben
(Server-IP, Port, Spielername) — vor der Nutzung anpassen. Der WiC64-
Client (`clients/c64/tron_c64_wic64_client.bas`) braucht zusätzlich die
Datei `FOTOFIX.C000` auf derselben Diskette (siehe `CLAUDE.md`).

## Server-Konfiguration

Alle Einstellungen (Fotos/FTP/HTTP, Logos, Scrolltext, Spielfeldgröße,
Geschwindigkeit) stehen als klar markierte Blöcke am Anfang von
`server/tron_server.py` — direkt dort anpassen, kein separates
Config-File.

## KI-Hinweis

Dieses Projekt wurde mit KI-Unterstützung (Claude) entwickelt — der
Server zeigt einen entsprechenden Hinweis permanent im Footer an.
