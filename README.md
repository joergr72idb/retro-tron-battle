# Retro Tron Battle

A network lightcycle duel for real retro computers (Atari XL/XE,
Commodore 64, Schneider/Amstrad CPC) with server-side rendering — built
for [Classic Computing 2026](https://www.classic-computing.de/cc2026/)
in Celle (10–11 October 2026).

Detailed background, design decisions, and hard-won platform quirks
live in [`CLAUDE.md`](./CLAUDE.md) — please read it before making
bigger changes.

## Hardware interfaces

Each of the retro computers connects to the server over a WiFi
interface:

- **Atari XL/XE:** [FujiNet](https://fujinet.online/)
- **Commodore 64:** [Meatloaf](https://github.com/idolpx/meatloaf)
  (standard client) or [WiC64](https://www.wic64.de/) (experimental)
- **Schneider/Amstrad CPC:** [M4 Board](https://www.cpcwiki.eu/index.php/M4_Board)

## Quickstart

```bash
pip install pygame
python3 server/tron_server.py [host] [tcp_port] [http_port]
# Defaults: 0.0.0.0 6502 8080
```

The server window shows the playfield, visitor photos, logos, and a
demo scroll text while waiting for players.

## Project structure

```
server/     The Python server (game logic + pygame display)
clients/    BASIC clients per platform
  atari/    Atari XL/XE + FujiNet (raw TCP)
  c64/      Commodore 64 - two variants:
              tron_c64_client.bas       (Meatloaf, HTTP polling, stable)
              tron_c64_wic64_client.bas (WiC64, experimental)
  cpc/      Schneider/Amstrad CPC + M4 board (HTTP polling)
  apple2/   Apple II + FujiNet (raw TCP) - experimental, unverified,
            see CLAUDE.md
bots/       Automated test bots (Bash/PowerShell) to play without
            real hardware, e.g. for demos or load tests
tools/      Diagnostic/test programs per platform, plus links to
            external third-party tools (d64-inspector, C64 TrueType
            font) - see README there
docs/       PDF documentation (protocol, extending to further platforms,
            hardware test checklist, PAP flowcharts for explaining the
            game to visitors)
disk-images/ Ready-made reference disk images (Atari/CPC/C64) for
            setting up real hardware, see README there
archive/    Abandoned approaches, kept for reference
```

## Setting up clients

Each `.bas` client has a short config block right at the top (server
IP, port, player name) — edit before use. The WiC64 client
(`clients/c64/tron_c64_wic64_client.bas`) additionally needs the file
`FOTOFIX.C000` on the same disk — already provided under
[`clients/c64/wic64-driver/`](./clients/c64/wic64-driver/) (WiC64
driver assembly by Andreas Beermann, see `CLAUDE.md`).

## Server configuration

All settings (photos/FTP/HTTP, logos, scroll text, playfield size,
speed) are clearly marked blocks at the top of
`server/tron_server.py` — edit them directly there, no separate
config file.

## AI notice

This project was developed with AI assistance (Claude) — the server
permanently shows a corresponding notice in the footer.
