#!/usr/bin/env python3
"""
Retro Tron Battle Server (v3 - zwei Teilnahme-Methoden)
=====================================================

Ein Spiel-Server fuer ein 2-Spieler Tron/Lightcycle-Duell, gespielt von
echten Retro-Computern ueber ein Netzwerk:

  - Atari XL/XE  + FujiNet   (N:TCP/IP-Geraet)   -> rohes TCP, Port 6502
  - Commodore 64 + Meatloaf                      -> HTTP-Polling, Port 8080
  - Amstrad CPC  + M4-Board                      -> HTTP-Polling, Port 8080

DESIGN
------
Die Retro-Computer STEUERN nur - sie zeichnen das Spielfeld nicht selbst.
Das Spielfeld wird hier gezeichnet, auf dem PC, der diesen Server betreibt,
in einem pygame-Fenster (gut geeignet fuer einen Beamer/groszen Monitor bei
einer Veranstaltung). Dadurch bleibt die Aufgabe jedes Retro-Clients fast
auf nichts beschraenkt auszer: Joystick lesen, bei Aenderung ein MOVE
senden, und gelegentlich pruefen, ob das Spiel vorbei ist. Das wiederum
bedeutet, dass die Retro-Clients nur sehr wenig Zeit damit verbringen, vom
Socket zu lesen, waehrend gespielt wird - das umgeht Unzuverlaessigkeiten,
die manche FujiNet-Setups zeigen, wenn Lese-/Schreibzugriffe auf demselben
Kanal zu eng ineinander verschachtelt werden.

Benoetigt: pip install pygame

ZWEI WEGE ZUM MITSPIELEN - WARUM ES BEIDE GIBT
------------------------------------------------
Nicht jede Retro-Netzwerkerweiterung kann aus reinem BASIC heraus einen
dauerhaften rohen TCP-Socket offen halten. FujiNet (Atari) kann das, daher
spricht es das TCP-Protokoll weiter unten direkt auf Port 6502. Meatloaf
(C64) und das M4-Board (Amstrad CPC) sind stattdessen auf einfache,
einmalige HTTP-Anfragen ausgelegt - einen rohen Socket durch sie
hindurchzuzwingen ist entweder aus BASIC heraus technisch gar nicht
moeglich (M4) oder hat sich ueber viele Runden echter Hardware-Tests als
unzuverlaessig erwiesen (Meatloaf). Beide fragen deshalb stattdessen eine
kleine HTTP-Bruecke auf einem zweiten Port ab - siehe "HTTP-POLLING" weiter
unten. Beide Zugangswege laufen durch exakt dieselbe Spiellogik
(run_game() weiter unten); welchen Weg eine bestimmte Plattform nutzt, ist
nur eine Frage dessen, was ihre Netzwerk-Hardware aus BASIC heraus
tatsaechlich kann, kein Unterschied im Spiel selbst.

PROTOKOLL 1: ROHES TCP (Port 6502, z.B. Atari/FujiNet)
--------------------------------------------------------
Client -> Server:
    HELLO <PLATTFORM> <NAME> [PIN]  z.B. "HELLO ATARI Zorg AFC6GHJ"
                                   PIN ist optional - eine Besucher-Foto-ID
                                   vom Event. Einfach weglassen (oder nichts
                                   nach NAME senden), um ohne Foto zu
                                   spielen.
    MOVE <U|D|L|R>                Richtungswechsel (wird ignoriert, falls
                                   es eine direkte Kehrtwende in die eigene
                                   Spur waere)
    BYE                           Verbindung trennen / aufgeben

Server -> Client:
    WAIT                          verbunden, wartet auf Gegner
    START <w> <h> <x1> <y1> <x2> <y2> <deinespielernr> <p1plat> <p2plat>
                                   signalisiert "Steuerung beginnt jetzt" -
                                   Clients muessen mit den Feldern nichts
                                   weiter tun, auszer zu bemerken, dass die
                                   Zeile angekommen ist
    END WIN <PLATTFORM> <NAME>    Spiel vorbei, jemand hat gewonnen
    END DRAW                      Spiel vorbei, gleichzeitiger Crash
    STATS GAMES <n> <PLATTFORM> <n> <PLATTFORM> <n> ... DRAWS <n>
                                   direkt nach END gesendet, laufende
                                   Gesamtzahlen

Es gibt in diesem Protokoll keinen TICK-Broadcast - das Spielfeld existiert
nur im Speicher dieses Prozesses und auf dem Bildschirm. Bots, die das
Spiel "sehen" wollen (wie tron_bot.sh), sollten einen eigenen Timer nutzen,
um zu entscheiden, wann sie abbiegen, statt auf eingehende Tick-Daten zu
reagieren.

Zwischen dem Paaren und dem ersten Tick gibt es einen kurzen Countdown auf
dem Bildschirm (3, 2, 1, dann ein abschlieszender Spruch), sichtbar im
pygame-Fenster. Richtungswechsel, die waehrend des Countdowns gesendet
werden, werden schon eingelesen und angewendet, aber niemand bewegt sich
tatsaechlich, bis der Spruch erscheint - das ist rein eine Pause auf der
Anzeige-Seite, keine neuen Protokollnachrichten.

Es spielen immer nur zwei Spieler gleichzeitig; wer sich verbindet,
waehrend ein Spiel laeuft, wartet auf den naechsten freien Platz.

PROTOKOLL 2: HTTP-POLLING (Port 8080, z.B. C64/Meatloaf, CPC/M4)
--------------------------------------------------------------------
Weder Meatloaf noch das M4-Board koennen das obige TCP-Protokoll aus BASIC
heraus offen halten, daher fragen diese Clients stattdessen zwei einfache
HTTP-GET-Routen auf einem zweiten Port ab:

    GET /join/<plattform>/<name>/<pin-oder-NONE>  -> "SESSION <id>\n" + WAIT/START
    GET /tick/<session>/<richtung-oder-N>          -> was auch immer fuer
                                                       ihn ansteht, oder
                                                       "ERR UNKNOWN SESSION"
                                                       sobald die Session weg ist

Eine Session verhaelt sich wie ein Briefkasten: /join legt eine an und gibt
eine ID zurueck; jedes /tick liefert sowohl ein MOVE (oder "N" fuer "keine
Aenderung") ab, als auch alles, was der Server seit dem letzten Abruf fuer
diesen Spieler hinterlegt hat - das kann nichts sein, eine START-Zeile,
oder END+STATS sobald das Spiel zu Ende ist. Sessions bleiben nach
Spielende noch eine kurze Gnadenfrist gueltig (siehe HTTPPlayerConn.close())
damit der naechste Abruf eines Clients das Endergebnis auch ueber einen
langsamen, echten HTTP-Roundtrip hinweg noch abholen kann - kommt der
Abruf eines Clients erst nach dieser Gnadenfrist an, bekommt er
"ERR UNKNOWN SESSION" und sollte das als "das Match ist definitiv vorbei,
starte eine neue Session" behandeln.

Diese Bruecke erzeugt intern exakt dieselben Player-artigen Objekte und
laeuft durch exakt dasselbe run_game() wie die TCP-Clients - es ist nur
eine andere Vordertuer (siehe HTTPPlayerConn weiter unten).

Aufruf mit:
    python3 tron_server.py [host] [tcp_port] [http_port]
Standard: 0.0.0.0 6502 8080
"""

import asyncio
import colorsys
import csv
import ftplib
import math
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime

# =============================================================================
# VERSION - bei jeder inhaltlichen Aenderung erhoehen (siehe Konsole + Fenster)
# =============================================================================
SERVER_BUILD = 8
# =============================================================================

# =============================================================================
# DEMO-SCROLLTEXT - LAEUFT DURCHS SPIELFELD, SOLANGE AUF SPIELER GEWARTET WIRD
# =============================================================================
SCROLL_TEXT = ("   RETRO TRON BATTLE *** "
               "800XL, C64 AND CPC6128 ARE CLASSICAL HOME COMPUTER *** "
               "WHICH ONE WILL WIN THE MOST BATTLES? *** "
               "Video game warriors escaping game grid. This is an illegal exit. You must return to game grid. Repeat! This is an illegal exit. You must return to the grid.") # <-- EDIT: EIGENER TEXT
SCROLL_FONT_PATH = "assets/font/Flynn-4v54.ttf"  # <-- EDIT: pfad zu einer eigenen .ttf-datei,
                                     # oder "" leer lassen fuer die standard-schrift
SCROLL_SPEED = 4            # pixel pro frame (bei ~30fps)
SCROLL_FONT_SIZE = 180       # schriftgroesse in pixel - 64=doppelt, 96=dreifach
SCROLL_WAVE_AMPLITUDE = 120  # pixel, hoehe der sinuswelle
SCROLL_WAVE_FREQ = 0.10      # radiant pro zeichen, "enge" der welle
SCROLL_WAVE_SPEED = 0.12     # radiant pro frame, geschwindigkeit der welle
SCROLL_COLOR_SPEED = 0.02    # farbverlauf pro frame (regenbogen)
# =============================================================================

# =============================================================================
# ERGEBNIS-PROTOKOLL (CSV) - EDIT FUER EUER SETUP
# =============================================================================
# Nach jedem beendeten Spiel wird eine Zeile an diese Datei angehaengt. Beim
# Serverstart wird die Datei (falls vorhanden) eingelesen und der Punktestand
# (Spiele gesamt, Siege pro Plattform, Unentschieden) daraus wiederhergestellt.
# Fehlt die Datei, wird einfach bei 0 gestartet.
RESULTS_CSV_PATH = "tron_results.csv"  # <-- EDIT: Pfad zur Ergebnis-CSV
CSV_FIELDNAMES = ["timestamp", "p1_platform", "p1_name", "p2_platform", "p2_name",
                   "result", "winner_platform", "winner_name"]
# =============================================================================

# =============================================================================
# EVENT-FOTO / LOGO-KONFIGURATION - DIESEN BLOCK FUER EURE VERANSTALTUNG ANPASSEN
# =============================================================================
# Besucher bekommen eine PIN (z.B. "MUSTER"), die mit einem Foto von ihnen
# verknuepft ist, organisiert auf dem fotofix-Server als ein Ordner pro PIN
# mit einem festen Dateinamen (HTTP_PHOTO_FILENAME, standardmaeszig
# "photo.jpg") - z.B. PIN "MUSTER" -> ".../MUSTER/photo.jpg". Dieser Server
# holt dieses Foto entweder per HTTP oder per FTP, je nach PHOTO_SOURCE
# weiter unten, und zeigt es neben der Spielfeldseite dieses Besuchers,
# zusammen mit dem Logo seines Computer-Herstellers. Beide Abrufmethoden
# nutzen genau denselben <PIN>/<HTTP_PHOTO_FILENAME>-Pfad - HTTP braucht
# nur eine vollstaendige URL (HTTP_PHOTO_BASE_URL), FTP braucht nur einen
# Host (FTP_HOST, typischerweise eine IP-Adresse statt eines Hostnamens).
PHOTO_SOURCE = "HTTP"  # <-- EDIT: "FTP" oder "HTTP" - schaltet die abrufmethode um

# --- FTP-Variante: Pfad auf dem FTP-Server = <FTP_REMOTE_DIR>/<PIN>/
#     <HTTP_PHOTO_FILENAME> (dieselbe struktur wie unten bei HTTP, nur mit
#     FTP_HOST als host statt einer kompletten URL) ---
FTP_HOST = "192.168.17.158"     # <-- EDIT: die IP-Adresse des fotofix-servers
FTP_PORT = 21
FTP_USER = "anonymous"           # <-- EDIT falls der FTP-server einen login braucht
FTP_PASS = "anonymous@"          # <-- EDIT
FTP_REMOTE_DIR = ""       # <-- EDIT: uebergeordneter ordner auf dem FTP-server,
                           #     falls die PIN-ordner nicht direkt im root liegen

# --- HTTP-Variante: URL = HTTP_PHOTO_BASE_URL + "/" + <PIN> + "/" +
#     HTTP_PHOTO_FILENAME, z.B. PIN "MUSTER" ->
#     http://fotofix.classic-computing.de/MUSTER/photo.jpg ---
HTTP_PHOTO_BASE_URL = "http://fotofix.classic-computing.de"  # <-- EDIT
HTTP_PHOTO_FILENAME = "photo.jpg"                             # <-- EDIT falls sich das je aendert
                                                                #     (gilt fuer FTP UND HTTP)

PHOTO_CACHE_DIR = "photo_cache"  # heruntergeladene fotos werden hier gecacht (automatisch angelegt)

# Lokaler, frei editierbarer Ordner fuer die drei Firmenlogos UND das
# Vereinslogo der Veranstaltung (oben rechts, dauerhaft sichtbar). Jederzeit
# Bilddateien hier reinlegen - fuer die Firmenlogos ist kein Neustart noetig
# (werden bei jedem neuen Match frisch geladen); das Vereinslogo wird nur
# einmal beim Start geladen (siehe event_logo_surf in pygame_loop()), ein
# Neustart IST also noetig, falls sich dieses aendert. Jeder dieser
# Dateinamen funktioniert pro Plattform (erster Treffer gewinnt):
# atari.png/.jpg, commodore.png/.jpg, c64.png/.jpg, schneider.png/.jpg,
# cpc.png/.jpg, amstrad.png/.jpg - plus "logo.png/.jpg/..." fuer das
# Vereinslogo. Endungs-Abgleich ist unter Linux gross-/kleinschreibungs-
# abhaengig, daher werden sowohl klein- als auch grossgeschriebene
# Endungen geprueft (LOGO_EXTENSIONS weiter unten).
LOGO_DIR = "assets/logos"               # <-- EDIT falls die logos woanders liegen sollen
LOGO_NAME_CANDIDATES = {
    "ATARI": ["atari"],
    "C64": ["commodore", "c64"],
    "CPC": ["schneider", "cpc", "amstrad"],
}
LOGO_EXTENSIONS = [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG", ".gif", ".GIF", ".bmp", ".BMP"]
# =============================================================================

GRID_W = 60
GRID_H = 32
TICK_RATE = 8  # ticks/sek - bescheiden halten, das sind langsame clients auf echtem silizium

CELL = 18             # pixelgroesse einer gitterzelle im anzeigefenster
HUD_HEIGHT = 120      # pixelhoehe des stats/status-headers
FOOTER_HEIGHT = 28    # pixelhoehe des footers (KI-hinweis)
PANEL_W = 170         # breite jedes seitenpanels (logo + besucherfoto)
FIELD_X = PANEL_W     # spielfeld beginnt rechts vom linken panel
WINDOW_W = PANEL_W * 2 + GRID_W * CELL
WINDOW_H = HUD_HEIGHT + GRID_H * CELL + FOOTER_HEIGHT

# Farben, die an den ikonischen Bildschirm-Look jeder Maschine erinnern.
PLATFORM_COLORS = {
    "ATARI": (108, 174, 216),   # Atari BASIC light blue
    "C64": (183, 173, 35),      # Commodore 64 gold/gelb
    "CPC": (70, 200, 110),      # Schneider/Amstrad CPC green phosphor
}
DEFAULT_COLOR = (200, 200, 200)
BG_COLOR = (10, 10, 18)
GRID_LINE_COLOR = (30, 30, 42)
HUD_BG_COLOR = (18, 18, 28)
TEXT_COLOR = (230, 230, 230)
DIM_TEXT_COLOR = (140, 140, 150)

DIRS = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}
OPPOSITE = {"U": "D", "D": "U", "L": "R", "R": "L"}


def fetch_photo_ftp_blocking(pin: str):
    """Download <pin>/<HTTP_PHOTO_FILENAME> (dieselbe Ordner+Dateiname-
    Struktur wie die HTTP-Variante, nur ueber FTP statt HTTP, z.B. Host als
    IP-Adresse) in den lokalen Cache und gibt den lokalen Pfad zurueck, oder
    None falls nicht gefunden/keine PIN. Macht blockierendes Netzwerk-I/O -
    nur ueber run_in_executor aufrufen, nie direkt aus der Event-Loop."""
    pin = (pin or "").strip()
    if not pin or pin.upper() in ("NONE", "-"):
        return None

    os.makedirs(PHOTO_CACHE_DIR, exist_ok=True)
    cached = os.path.join(PHOTO_CACHE_DIR, pin + ".jpg")
    if os.path.exists(cached):
        return cached

    remote_path = f"{pin}/{HTTP_PHOTO_FILENAME}"
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=8)
        ftp.login(FTP_USER, FTP_PASS)
        if FTP_REMOTE_DIR:
            ftp.cwd(FTP_REMOTE_DIR)
        with open(cached, "wb") as f:
            ftp.retrbinary(f"RETR {remote_path}", f.write)
        ftp.quit()
        return cached
    except Exception as e:
        print(f"[ftp] couldn't fetch photo for PIN '{pin}' ({remote_path}): {e}")
        try:
            os.remove(cached)
        except OSError:
            pass
    return None


def fetch_photo_http_blocking(pin: str):
    """Laedt <PIN>/<HTTP_PHOTO_FILENAME> von HTTP_PHOTO_BASE_URL in den
    lokalen Cache und gibt den lokalen Pfad zurueck, oder None falls nicht
    gefunden/keine PIN. Gleicher blockierender I/O-Vertrag wie
    fetch_photo_ftp_blocking - nur ueber run_in_executor aufrufen, nie
    direkt aus der asyncio-Event-Loop."""
    pin = (pin or "").strip()
    if not pin or pin.upper() in ("NONE", "-"):
        return None

    os.makedirs(PHOTO_CACHE_DIR, exist_ok=True)
    cached = os.path.join(PHOTO_CACHE_DIR, pin + ".jpg")
    if os.path.exists(cached):
        return cached

    url = f"{HTTP_PHOTO_BASE_URL}/{urllib.parse.quote(pin)}/{HTTP_PHOTO_FILENAME}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RetroTronBattle/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        with open(cached, "wb") as f:
            f.write(data)
        return cached
    except Exception as e:
        print(f"[http-photo] couldn't fetch photo for PIN '{pin}' from {url}: {e}")
    return None


def fetch_photo_blocking(pin: str):
    """Dispatcher - ruft je nach PHOTO_SOURCE entweder den FTP- oder den
    HTTP-Fotoabruf auf, ohne dass sich an der Aufrufstelle etwas aendert.
    Blockierend - nur ueber run_in_executor aufrufen, nie direkt aus der
    Event-Loop."""
    if PHOTO_SOURCE.upper() == "HTTP":
        return fetch_photo_http_blocking(pin)
    return fetch_photo_ftp_blocking(pin)


def logo_path_for(platform: str):
    """Sucht ein Firmenlogo-Bild fuer eine Plattform in LOGO_DIR. Guenstige
    lokale Dateisystem-Pruefung - sicher direkt aus der Event-Loop aufrufbar."""
    for base in LOGO_NAME_CANDIDATES.get(platform, []):
        for ext in LOGO_EXTENSIONS:
            p = os.path.join(LOGO_DIR, base + ext)
            if os.path.exists(p):
                return p
    return None


def event_logo_path():
    """Sucht das Vereinslogo der Veranstaltung ("logo.jpg" o.ae.) im selben
    Ordner wie die Firmenlogos. Gleiche guenstige lokale Pruefung wie
    logo_path_for()."""
    for ext in LOGO_EXTENSIONS:
        p = os.path.join(LOGO_DIR, "logo" + ext)
        if os.path.exists(p):
            return p
    return None


@dataclass
class Player:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    platform: str
    name: str
    x: int
    y: int
    direction: str
    alive: bool = True
    trail: set = field(default_factory=set)
    pin: str = ""
    photo_task: object = field(default=None, repr=False)  # asyncio.Future von run_in_executor
    inbuf: object = field(default_factory=lambda: LineBuffer(), repr=False)


class Stats:
    """Verfolgt die Gesamtzahl gespielter Spiele und Siege pro Retro-Plattform."""

    def __init__(self):
        self.games_played = 0
        self.wins = {}  # plattform -> anzahl siege
        self.draws = 0

    def record_win(self, platform: str):
        self.games_played += 1
        self.wins[platform] = self.wins.get(platform, 0) + 1

    def record_draw(self):
        self.games_played += 1
        self.draws += 1

    def summary_line(self) -> str:
        parts = [f"GAMES {self.games_played}"]
        for platform, count in sorted(self.wins.items()):
            parts.append(f"{platform} {count}")
        parts.append(f"DRAWS {self.draws}")
        return "STATS " + " ".join(parts)

    def print_console(self):
        print(f"  Total games played: {self.games_played}")
        for platform, count in sorted(self.wins.items(), key=lambda kv: -kv[1]):
            print(f"    {platform:10s} wins: {count}")
        print(f"    {'DRAWS':10s} : {self.draws}")


def load_stats_from_csv():
    """Liest vorhandene Ergebnisse aus RESULTS_CSV_PATH und baut daraus den
    aktuellen Punktestand wieder auf (ueber die normalen record_win/record_draw
    Methoden, damit exakt dieselbe Logik wie live verwendet wird). Fehlt die
    Datei, wird einfach bei 0 gestartet. Fehlerhafte einzelne Zeilen werden
    uebersprungen statt den Start abzubrechen."""
    if not os.path.exists(RESULTS_CSV_PATH):
        print(f"[stats] keine {RESULTS_CSV_PATH} gefunden - starte bei 0")
        return
    loaded = 0
    skipped = 0
    try:
        with open(RESULTS_CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    if row.get("result") == "WIN":
                        stats.record_win(row["winner_platform"])
                        loaded += 1
                    elif row.get("result") == "DRAW":
                        stats.record_draw()
                        loaded += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1
    except Exception as e:
        print(f"[stats] konnte {RESULTS_CSV_PATH} nicht lesen, starte bei 0: {e}")
        return
    msg = f"[stats] {loaded} vorherige Spiele aus {RESULTS_CSV_PATH} geladen"
    if skipped:
        msg += f" ({skipped} fehlerhafte Zeile(n) uebersprungen)"
    print(msg)
    stats.print_console()


def append_result_to_csv(p1: "Player", p2: "Player", result: str,
                          winner_platform: str = "", winner_name: str = ""):
    """Haengt eine Zeile fuer das gerade beendete Spiel an RESULTS_CSV_PATH an
    (legt die Datei inkl. Kopfzeile an, falls sie noch nicht existiert). Ein
    Schreibfehler (z.B. Rechte-Problem) wirft den Server nicht um, sondern
    gibt nur eine Konsolenwarnung aus."""
    try:
        is_new = not os.path.exists(RESULTS_CSV_PATH)
        with open(RESULTS_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            if is_new:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "p1_platform": p1.platform, "p1_name": p1.name,
                "p2_platform": p2.platform, "p2_name": p2.name,
                "result": result,
                "winner_platform": winner_platform,
                "winner_name": winner_name,
            })
    except Exception as e:
        print(f"[stats] konnte Ergebnis nicht in {RESULTS_CSV_PATH} schreiben: {e}")


stats = Stats()
load_stats_from_csv()
waiting_player: Player | None = None
lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Gemeinsam genutzter Render-State. Die asyncio-Seite (Netzwerk-Thread)
# schreibt hier unter render_lock hinein; die pygame-Seite (Haupt-Thread)
# liest etwa 30 Mal pro Sekunde unter demselben Lock. Updates guenstig
# halten - kleine Strukturen hineinkopieren, keine lebenden Referenzen auf
# veraenderliche Spielobjekte herausgeben.
# ---------------------------------------------------------------------------
render_lock = threading.Lock()
render_state = {
    "phase": "waiting",          # waiting | countdown | playing | ended
    "status": "Waiting for lightcycles to connect...",
    "p1_name": "", "p1_plat": "",
    "p2_name": "", "p2_plat": "",
    "trail1": set(), "trail2": set(),
    "pos1": None, "pos2": None,
    "photo1": None, "photo2": None,
    "logo1": None, "logo2": None,
    "countdown": "",
    "games_played": stats.games_played,
    "wins": dict(stats.wins),
    "draws": stats.draws,
}


def update_render(**kwargs):
    with render_lock:
        render_state.update(kwargs)


def snapshot_render():
    with render_lock:
        return {
            "phase": render_state["phase"],
            "status": render_state["status"],
            "p1_name": render_state["p1_name"], "p1_plat": render_state["p1_plat"],
            "p2_name": render_state["p2_name"], "p2_plat": render_state["p2_plat"],
            "trail1": set(render_state["trail1"]), "trail2": set(render_state["trail2"]),
            "pos1": render_state["pos1"], "pos2": render_state["pos2"],
            "photo1": render_state["photo1"], "photo2": render_state["photo2"],
            "logo1": render_state["logo1"], "logo2": render_state["logo2"],
            "countdown": render_state["countdown"],
            "games_played": render_state["games_played"],
            "wins": dict(render_state["wins"]),
            "draws": render_state["draws"],
        }


class LineBuffer:
    """Sammelt rohe Bytes von einem Socket und entnimmt vollstaendige
    Zeilen, tolerant gegenueber \\r, \\n oder \\r\\n als Terminator - manche
    Retro-Netzwerk-Stacks (besonders Commodore/IEC) nutzen traditionell ein
    einzelnes CR statt LF. Behaelt unvollstaendige Zeilen ueber mehrere
    Aufrufe hinweg, damit eine ueber zwei Reads verteilte Zeile nie
    beschaedigt oder verworfen wird."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf.extend(data)

    def pop_line(self):
        for i, b in enumerate(self.buf):
            if b in (0x0D, 0x0A):
                line = bytes(self.buf[:i])
                rest = self.buf[i + 1:]
                # Ein gepaartes zweites Terminator-Byte verschlucken (CRLF oder LFCR).
                if rest[:1] in (b"\r", b"\n") and rest[:1] != bytes([b]):
                    rest = rest[1:]
                self.buf = rest
                return line.decode("ascii", errors="ignore")
        return None


async def send(writer: asyncio.StreamWriter, line: str):
    try:
        writer.write((line + "\r\n").encode("ascii", errors="ignore"))
        await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass


async def read_line(reader: asyncio.StreamReader, timeout: float | None = None):
    """Einmaliges Zeilen-Lesen (nur fuer den anfaenglichen HELLO-Handshake
    genutzt) - CR/LF-tolerant ueber einen wegwerfbaren LineBuffer, der
    haeppchenweise gefuettert wird."""
    lb = LineBuffer()
    try:
        while True:
            line = lb.pop_line()
            if line is not None:
                return line
            if timeout:
                data = await asyncio.wait_for(reader.read(256), timeout=timeout)
            else:
                data = await reader.read(256)
            if not data:
                return None
            lb.feed(data)
    except (asyncio.TimeoutError, ConnectionResetError):
        return None


async def pair_and_maybe_start(platform: str, name: str, pin: str,
                                reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                                peer_desc: str = ""):
    """Gemeinsame Paarungslogik, genutzt sowohl vom TCP-Pfad (ein echter
    Socket) als auch vom HTTP-Polling-Pfad (ein HTTPPlayerConn-Platzhalter).
    Registriert entweder als wartender Spieler (sendet WAIT) oder paart mit
    wer auch immer schon wartet und startet das Spiel als Hintergrund-Task."""
    global waiting_player

    print(f"[+] {platform}/{name} connected{(' from ' + peer_desc) if peer_desc else ''}" +
          (f" (pin {pin})" if pin else ""))

    photo_task = asyncio.get_running_loop().run_in_executor(None, fetch_photo_blocking, pin)

    async with lock:
        if waiting_player is None:
            p = Player(reader, writer, platform, name, x=5, y=GRID_H // 2, direction="R",
                       pin=pin, photo_task=photo_task)
            waiting_player = p
            await send(writer, "WAIT")
            update_render(status=f"{platform}/{name} is waiting for an opponent...")
            return
        else:
            p1 = waiting_player
            waiting_player = None
            p2 = Player(reader, writer, platform, name, x=GRID_W - 6, y=GRID_H // 2, direction="L",
                        pin=pin, photo_task=photo_task)

    asyncio.create_task(run_game(p1, p2))


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    hello = await read_line(reader, timeout=20)
    if not hello or not hello.upper().startswith("HELLO"):
        writer.close()
        return

    parts = hello.split()
    platform = parts[1].upper() if len(parts) > 1 else "UNKNOWN"
    name = parts[2] if len(parts) > 2 else platform
    pin = parts[3] if len(parts) > 3 else ""

    await pair_and_maybe_start(platform, name, pin, reader, writer, peer_desc=str(peer))


# =============================================================================
# HTTP-POLLING-BRUECKE FUER C64/MEATLOAF UND AMSTRAD CPC/M4
# =============================================================================
# Weder Meatloaf noch das M4-Board koennen aus reinem BASIC heraus
# zuverlaessig einen dauerhaften rohen TCP-Socket offen halten (M4 kann das
# aus BASIC heraus ohne handgeschriebenen Z80-Assemblercode schlicht nicht;
# Meatloaf kann technisch einen oeffnen, aber das hat sich ueber viele
# Runden echter Hardware-Tests als unzuverlaessig erwiesen). Beide koennen
# aber aus BASIC heraus einfache HTTP-GET-Anfragen stellen, daher fragen
# beide Clients stattdessen kleine HTTP-Anfragen ab, statt eine Verbindung
# offen zu halten: einmal /join, dann wiederholt /tick (schickt eine
# etwaige Richtungsaenderung, bekommt zurueck was ansteht - WAIT, START,
# oder irgendwann END + STATS). Alles Folgende passt dieses Anfrage-/
# Antwort-Polling einfach in dieselbe Player-/run_game-Maschinerie ein, die
# auch der TCP-Client (Atari) nutzt, ueber einen duck-typed Platzhalter fuer
# (StreamReader, StreamWriter).
# =============================================================================
http_sessions: dict = {}


class HTTPPlayerConn:
    """Steht stellvertretend fuer ein (StreamReader, StreamWriter)-Paar bei
    einem HTTP-abgefragten Spieler. Zeilen, die AN diese "Verbindung"
    gesendet werden (ueber send()/writer.write()), sammeln sich in einer
    Outbox, die der naechste /tick-Abruf entnimmt und zurueckgibt. Zeilen,
    die VOM Spieler ankommen (MOVE-Befehle aus /tick-Anfragen), werden in
    eine asyncio.Queue gelegt, aus der readline() liest - so funktioniert
    run_game()s bestehendes 10ms-Timeout-Lesemuster unveraendert auch hier."""

    def __init__(self, session_id: str = ""):
        self._inbox = asyncio.Queue()
        self._outbox = []
        self.closed = False
        self.session_id = session_id

    async def readline(self):
        return await self._inbox.get()

    async def read(self, n=256):
        # n wird ignoriert - abgelegte elemente sind immer klein, vorgefertigte
        # "zeile\n"-byte-happen von feed_line() - gleicher vertrag wie ein
        # echter sockets read(), das "was auch immer gerade verfuegbar ist"
        # zurueckgibt.
        return await self._inbox.get()

    def at_eof(self):
        return self.closed

    def feed_line(self, text: str):
        self._inbox.put_nowait((text + "\n").encode("ascii"))

    def write(self, data: bytes):
        self._outbox.append(data.decode("ascii", errors="ignore"))

    async def drain(self):
        pass

    def close(self):
        self.closed = True
        # Anders als bei einem echten TCP-Socket-Close ist eine HTTP-
        # "Verbindung" nur dieses Objekt, das in http_sessions liegt. Wuerden
        # wir es sofort entfernen, kaeme der eine /tick-Abruf, der das
        # finale END+STATS abholen soll, fast immer zu spaet - ein voller
        # HTTP-Roundtrip (oeffnen, lesen, schlieszen) braucht echte
        # Wanduhr-Zeit, waehrend das Befuellen der Outbox und das Loeschen
        # der Session hier unmittelbar hintereinander ohne nennenswerte
        # Luecke passieren. Stattdessen also: Session fuer eine Gnadenfrist
        # am Leben halten, damit der Client genug Chancen hat, abzufragen
        # und die finale Nachricht tatsaechlich zu erhalten, und erst danach
        # aufraeumen.
        if self.session_id:
            loop = asyncio.get_running_loop()
            loop.call_later(15, self._expire)

    def _expire(self):
        if self.session_id and http_sessions.get(self.session_id) is self:
            del http_sessions[self.session_id]

    def get_extra_info(self, *a, **k):
        return None

    def pop_outbox(self) -> str:
        text = "".join(self._outbox)
        self._outbox.clear()
        return text


HTTP_DIR_MAP = {"U": "MOVE U", "D": "MOVE D", "L": "MOVE L", "R": "MOVE R"}


async def http_handle_request(path: str) -> str:
    """Leitet einen geparsten HTTP-GET-Pfad an die join-/tick-Logik weiter
    und gibt den zurueckzusendenden Klartext-Body zurueck. path hat keinen
    fuehrenden '?'-Query-String - alles sind Pfad-Segmente (wie die
    Geraete-Firmware '?'/'&' in |HTTPGET-Anfragen behandelt, ist nicht
    dokumentiert/bestaetigt, daher wird das hier bewusst vermieden):
    /join/<plattform>/<name>/<pin-oder-NONE> und /tick/<session>/<richtung-oder-N>"""
    segments = [s for s in path.strip("/").split("/") if s != ""]

    if not segments:
        return "TRON SERVER OK"

    if segments[0] == "join" and len(segments) >= 3:
        platform = segments[1].upper()
        name = segments[2]
        pin = segments[3] if len(segments) > 3 and segments[3].upper() != "NONE" else ""

        session_id = uuid.uuid4().hex[:8].upper()
        conn = HTTPPlayerConn(session_id)
        http_sessions[session_id] = conn
        print(f"[http] JOIN: neue session gespeichert: {session_id!r}  (aktuelle keys: {list(http_sessions.keys())!r})")

        asyncio.create_task(pair_and_maybe_start(platform, name, pin, conn, conn, peer_desc="HTTP"))
        # Dem Pairing einen kurzen Moment geben, damit ein Match im selben
        # Augenblick sofort START zurueckgibt, statt einen weiteren
        # Roundtrip zu erzwingen.
        await asyncio.sleep(0.05)
        return f"SESSION {session_id}\n" + conn.pop_outbox()

    if segments[0] == "tick" and len(segments) >= 2:
        session_id = segments[1].upper()  # meatloaf scheint beim GET# irgendwo
        # zwischen ascii/petscii hin- und herzuwandeln, wobei die gross-/klein-
        # schreibung durcheinanderkommt - deshalb hier bewusst tolerant sein
        direction = segments[2].upper() if len(segments) > 2 else "N"
        conn = http_sessions.get(session_id)
        if conn is None:
            print(f"[http] TICK: gesuchte session {session_id!r} NICHT gefunden. "
                  f"aktuelle keys: {list(http_sessions.keys())!r}")
            return "ERR UNKNOWN SESSION"
        if direction in HTTP_DIR_MAP:
            conn.feed_line(HTTP_DIR_MAP[direction])
        return conn.pop_outbox()

    return "ERR UNKNOWN REQUEST"


async def handle_http_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=5)
        if not request_line:
            writer.close()
            return
        # Restliche Anfrage-Header einlesen und verwerfen.
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=2)
            if not line or line in (b"\r\n", b"\n"):
                break

        try:
            method, raw_path, _ = request_line.decode("ascii", errors="ignore").split()
        except ValueError:
            print(f"[http] konnte request line nicht parsen: {request_line!r}")
            writer.close()
            return

        path = urllib.parse.unquote(raw_path)
        print(f"[http] {method} {path!r}  (raw request line: {request_line!r})")
        body = await http_handle_request(path) if method == "GET" else "ERR METHOD"

        response = (
            "HTTP/1.0 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n" + body
        )
        writer.write(response.encode("ascii", errors="ignore"))
        await writer.drain()
    except Exception as e:
        print(f"[http] request error: {e}")
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def drain_moves(players):
    """Non-blockierend anstehende MOVE/BYE-Kommandos fuer jeden Spieler
    einlesen und anwenden. Wird sowohl waehrend des Countdowns (damit
    Richtungswechsel nicht verloren gehen) als auch im normalen Spiel-Tick
    verwendet, damit beide Stellen exakt gleich funktionieren."""
    for p in players:
        try:
            data = await asyncio.wait_for(p.reader.read(256), timeout=0.01)
        except asyncio.TimeoutError:
            data = b""
        except (ConnectionResetError, BrokenPipeError):
            p.alive = False
            continue
        if data:
            p.inbuf.feed(data)
        elif data == b"" and isinstance(p.reader, asyncio.StreamReader) and p.reader.at_eof():
            p.alive = False
            continue
        while True:
            line = p.inbuf.pop_line()
            if line is None:
                break
            line = line.strip().upper()
            if line.startswith("MOVE"):
                tokens = line.split()
                if len(tokens) > 1 and tokens[1] in DIRS:
                    d = tokens[1]
                    if d != OPPOSITE.get(p.direction):
                        p.direction = d
            elif line == "BYE":
                p.alive = False


async def resolve_photo(p: Player, timeout: float = 3.0):
    if p.photo_task is None:
        return None
    try:
        return await asyncio.wait_for(p.photo_task, timeout=timeout)
    except Exception:
        return None


async def run_game(p1: Player, p2: Player):
    p1.trail = {(p1.x, p1.y)}
    p2.trail = {(p2.x, p2.y)}

    await send(p1.writer, f"START {GRID_W} {GRID_H} {p1.x} {p1.y} {p2.x} {p2.y} 1 {p1.platform} {p2.platform}")
    await send(p2.writer, f"START {GRID_W} {GRID_H} {p1.x} {p1.y} {p2.x} {p2.y} 2 {p1.platform} {p2.platform}")
    print(f"[*] Game start: {p1.platform}/{p1.name} vs {p2.platform}/{p2.name}")

    photo1, photo2 = await asyncio.gather(resolve_photo(p1), resolve_photo(p2))

    update_render(
        phase="countdown",
        status="",
        p1_name=p1.name, p1_plat=p1.platform,
        p2_name=p2.name, p2_plat=p2.platform,
        trail1=set(p1.trail), trail2=set(p2.trail),
        pos1=(p1.x, p1.y), pos2=(p2.x, p2.y),
        photo1=photo1, photo2=photo2,
        logo1=logo_path_for(p1.platform), logo2=logo_path_for(p2.platform),
        countdown="",
    )

    players = [p1, p2]

    # --- Countdown: 3, 2, 1, dann der abschliessende Spruch (siehe unten) -
    # Richtungswechsel werden schon eingelesen (damit nichts verloren geht),
    # aber niemand bewegt sich. ---
    for count in (3, 2, 1):
        update_render(countdown=str(count))
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            await drain_moves(players)
            if not (p1.alive and p2.alive):
                break  # jemand hat BYE geschickt, waehrend gewartet wurde
            await asyncio.sleep(0.05)

    update_render(countdown="Go, get in there! Move!")
    await asyncio.sleep(0.6)
    update_render(phase="playing", countdown="")

    while p1.alive and p2.alive:
        tick_start = time.monotonic()

        await drain_moves(players)

        for p in players:
            dx, dy = DIRS[p.direction]
            p.x += dx
            p.y += dy

        for p in players:
            if not (0 <= p.x < GRID_W and 0 <= p.y < GRID_H):
                p.alive = False
            elif (p.x, p.y) in p1.trail or (p.x, p.y) in p2.trail:
                p.alive = False

        if p1.alive:
            p1.trail.add((p1.x, p1.y))
        if p2.alive:
            p2.trail.add((p2.x, p2.y))

        update_render(trail1=set(p1.trail), trail2=set(p2.trail),
                      pos1=(p1.x, p1.y), pos2=(p2.x, p2.y))

        elapsed = time.monotonic() - tick_start
        await asyncio.sleep(max(0.0, (1 / TICK_RATE) - elapsed))

    if p1.alive and not p2.alive:
        winner = p1
    elif p2.alive and not p1.alive:
        winner = p2
    else:
        winner = None

    if winner:
        stats.record_win(winner.platform)
        append_result_to_csv(p1, p2, "WIN", winner.platform, winner.name)
        result = f"END WIN {winner.platform} {winner.name}"
        status = f"{winner.platform}/{winner.name} WINS!"
        print(f"[=] {winner.platform}/{winner.name} wins!")
    else:
        stats.record_draw()
        append_result_to_csv(p1, p2, "DRAW")
        result = "END DRAW"
        status = "DRAW - SIMULTANEOUS CRASH!"
        print("[=] Draw (simultaneous crash)")

    update_render(phase="ended", status=status,
                  games_played=stats.games_played, wins=dict(stats.wins), draws=stats.draws)

    await send(p1.writer, result)
    await send(p2.writer, result)

    stat_line = stats.summary_line()
    await send(p1.writer, stat_line)
    await send(p2.writer, stat_line)
    stats.print_console()

    for p in (p1, p2):
        try:
            p.writer.close()
        except Exception:
            pass

    await asyncio.sleep(4)  # ergebnis noch ein paar sekunden auf dem bildschirm stehen lassen
    update_render(phase="waiting", status="Waiting for lightcycles to connect...",
                  trail1=set(), trail2=set(), pos1=None, pos2=None,
                  photo1=None, photo2=None, logo1=None, logo2=None)


async def server_main(host: str, port: int, http_port: int):
    tcp_server = await asyncio.start_server(handle_client, host, port)
    http_server = await asyncio.start_server(handle_http_connection, host, http_port)
    addrs = ", ".join(str(sock.getsockname()) for sock in tcp_server.sockets)
    http_addrs = ", ".join(str(sock.getsockname()) for sock in http_server.sockets)
    print(f"Retro Tron server (build {SERVER_BUILD}) listening on {addrs}")
    print(f"HTTP-polling bridge (C64/Meatloaf, CPC/M4) listening on {http_addrs}")
    print("Waiting for two lightcycles to connect...")
    async with tcp_server, http_server:
        await asyncio.gather(tcp_server.serve_forever(), http_server.serve_forever())


def network_thread(host: str, port: int, http_port: int):
    try:
        asyncio.run(server_main(host, port, http_port))
    except Exception as e:
        print(f"[server thread] fatal error: {e}")


def color_for(platform: str):
    return PLATFORM_COLORS.get(platform, DEFAULT_COLOR)


def pygame_loop():
    import pygame

    pygame.init()
    pygame.display.set_caption("Classic Computing 2026: Retro Tron Battle")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont("couriernew,monospace", 28, bold=True)
    font_huge = pygame.font.SysFont("couriernew,monospace", 96, bold=True)
    font_mid = pygame.font.SysFont("couriernew,monospace", 20, bold=True)
    font_small = pygame.font.SysFont("couriernew,monospace", 16)
    font_tiny = pygame.font.SysFont("couriernew,monospace", 14)
    if SCROLL_FONT_PATH and os.path.exists(SCROLL_FONT_PATH):
        scroll_font = pygame.font.Font(SCROLL_FONT_PATH, SCROLL_FONT_SIZE)
    else:
        if SCROLL_FONT_PATH:
            print(f"[display] Scroll-Font nicht gefunden: {SCROLL_FONT_PATH} - nutze Standardschrift")
        scroll_font = pygame.font.SysFont("couriernew,monospace", SCROLL_FONT_SIZE, bold=True)

    # Demo-Scroller Zustand: laeuft nur weiter/wird nur gezeichnet, solange
    # die Server-Phase "waiting" ist (siehe Hauptschleife weiter unten).
    scroll_char_widths = [scroll_font.size(c)[0] for c in SCROLL_TEXT]
    scroll_total_width = sum(scroll_char_widths)
    scroll_x = WINDOW_W
    scroll_wave_phase = 0.0
    scroll_hue = 0.0

    # Geladene+skalierte Bilder nach (pfad, max_b, max_h) cachen, damit wir
    # nicht bei jedem einzelnen Frame dasselbe JPEG/PNG neu dekodieren.
    image_cache = {}

    def load_scaled(path, max_w, max_h):
        if not path:
            return None
        key = (path, max_w, max_h)
        if key in image_cache:
            return image_cache[key]
        try:
            img = pygame.image.load(path)
            img = img.convert_alpha() if img.get_flags() else img.convert()
            iw, ih = img.get_size()
            scale = min(max_w / iw, max_h / ih)
            new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
            scaled = pygame.transform.smoothscale(img, new_size)
        except Exception as e:
            print(f"[display] couldn't load image {path}: {e}")
            scaled = None
        image_cache[key] = scaled
        return scaled

    # Vereinslogo: einmalig direkt nach dem Start geladen, bleibt danach
    # das ganze Programm ueber im Speicher und wird in JEDER Phase gezeigt
    # (Warten, Countdown, Spiel, Ergebnis) - nicht bei jedem Frame neu vom
    # Dateisystem geprueft.
    event_logo_surf = load_scaled(event_logo_path(), PANEL_W - 20, 70)
    if event_logo_surf is None:
        print(f"[display] Vereinslogo nicht gefunden (erwartet: logo.jpg/.png/... in {LOGO_DIR})")
        try:
            actual_files = os.listdir(LOGO_DIR)
            print(f"[display] tatsaechlich vorhanden in {LOGO_DIR}: {actual_files}")
        except Exception as e:
            print(f"[display] konnte {LOGO_DIR} nicht auflisten: {e}")

    def draw_panel(x0, name, plat, photo_path, logo_path):
        color = color_for(plat)
        pygame.draw.rect(screen, HUD_BG_COLOR, (x0, HUD_HEIGHT, PANEL_W, GRID_H * CELL))
        pygame.draw.rect(screen, color, (x0, HUD_HEIGHT, PANEL_W, GRID_H * CELL), 2)

        y = HUD_HEIGHT + 12
        logo_surf = load_scaled(logo_path, PANEL_W - 20, 70)
        if logo_surf:
            rect = logo_surf.get_rect(centerx=x0 + PANEL_W // 2, top=y)
            screen.blit(logo_surf, rect)
            y = rect.bottom + 10
        else:
            y += 80

        photo_surf = load_scaled(photo_path, PANEL_W - 20, 220)
        if photo_surf:
            rect = photo_surf.get_rect(centerx=x0 + PANEL_W // 2, top=y)
            screen.blit(photo_surf, rect)
            y = rect.bottom + 10
        else:
            ph = pygame.Rect(x0 + 10, y, PANEL_W - 20, 180)
            pygame.draw.rect(screen, GRID_LINE_COLOR, ph)
            tip = font_tiny.render("no photo", True, DIM_TEXT_COLOR)
            screen.blit(tip, tip.get_rect(center=ph.center))
            y = ph.bottom + 10

        if name:
            label = font_small.render(f"{plat}", True, color)
            screen.blit(label, label.get_rect(centerx=x0 + PANEL_W // 2, top=y))
            y += 20
            label2 = font_small.render(name[:16], True, TEXT_COLOR)
            screen.blit(label2, label2.get_rect(centerx=x0 + PANEL_W // 2, top=y))

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        state = snapshot_render()

        screen.fill(HUD_BG_COLOR)

        # --- HUD (kopfzeile mit titel, status, punktestand) ---
        title = font_big.render("Classic Computing 2026:RETRO TRON BATTLE", True, TEXT_COLOR)
        screen.blit(title, (16, 10))

        if state["phase"] == "playing":
            p1c = color_for(state["p1_plat"])
            p2c = color_for(state["p2_plat"])
            vs = font_mid.render(
                f"{state['p1_plat']}/{state['p1_name']}  vs  {state['p2_plat']}/{state['p2_name']}",
                True, TEXT_COLOR)
            screen.blit(vs, (16, 46))
            pygame.draw.rect(screen, p1c, (16, 70, 16, 16))
            pygame.draw.rect(screen, p2c, (200, 70, 16, 16))
        else:
            msg = font_mid.render(state["status"], True, TEXT_COLOR)
            screen.blit(msg, (16, 46))

        wins_parts = []
        for plat, count in sorted(state["wins"].items(), key=lambda kv: -kv[1]):
            wins_parts.append(f"{plat}:{count}")
        wins_str = "  ".join(wins_parts) if wins_parts else "no wins yet"
        stats_line = font_small.render(
            f"Games played: {state['games_played']}   Wins - {wins_str}   Draws: {state['draws']}",
            True, DIM_TEXT_COLOR)
        screen.blit(stats_line, (16, 96))

        # --- Vereinslogo oben rechts, einmalig geladen (siehe oben),
        # in jeder Phase permanent sichtbar ---
        if event_logo_surf:
            rect = event_logo_surf.get_rect(right=WINDOW_W - 16, top=10)
            screen.blit(event_logo_surf, rect)

        # --- Seitenpanels (logo + besucherfoto) ---
        if state["phase"] in ("countdown", "playing", "ended"):
            draw_panel(0, state["p1_name"], state["p1_plat"], state["photo1"], state["logo1"])
            draw_panel(FIELD_X + GRID_W * CELL, state["p2_name"], state["p2_plat"],
                       state["photo2"], state["logo2"])

        # --- Spielfeld ---
        field_rect = pygame.Rect(FIELD_X, HUD_HEIGHT, GRID_W * CELL, GRID_H * CELL)
        pygame.draw.rect(screen, BG_COLOR, field_rect)
        for gx in range(GRID_W + 1):
            x = FIELD_X + gx * CELL
            pygame.draw.line(screen, GRID_LINE_COLOR, (x, HUD_HEIGHT), (x, WINDOW_H))
        for gy in range(GRID_H + 1):
            y = HUD_HEIGHT + gy * CELL
            pygame.draw.line(screen, GRID_LINE_COLOR, (FIELD_X, y), (FIELD_X + GRID_W * CELL, y))

        # --- Demo-Scroller: laeuft nur, solange auf spieler gewartet wird ---
        if state["phase"] == "waiting":
            scroll_x -= SCROLL_SPEED
            scroll_wave_phase += SCROLL_WAVE_SPEED
            scroll_hue = (scroll_hue + SCROLL_COLOR_SPEED) % 1.0
            if scroll_x < -scroll_total_width:
                scroll_x = WINDOW_W

            baseline = HUD_HEIGHT + (GRID_H * CELL) // 2
            cx = scroll_x
            for i, ch in enumerate(SCROLL_TEXT):
                cw = scroll_char_widths[i]
                if -cw <= cx <= WINDOW_W:
                    hue = (scroll_hue + i * 0.02) % 1.0
                    rr, gg, bb = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
                    color = (int(rr * 255), int(gg * 255), int(bb * 255))
                    y_off = math.sin(scroll_wave_phase + i * SCROLL_WAVE_FREQ) * SCROLL_WAVE_AMPLITUDE
                    ch_surf = scroll_font.render(ch, True, color)
                    screen.blit(ch_surf, (cx, baseline + y_off))
                cx += cw

        def draw_trail(cells, plat, head):
            color = color_for(plat)
            for (gx, gy) in cells:
                rect = (FIELD_X + gx * CELL + 1, HUD_HEIGHT + gy * CELL + 1, CELL - 2, CELL - 2)
                pygame.draw.rect(screen, color, rect)
            if head:
                hx, hy = head
                rect = (FIELD_X + hx * CELL + 1, HUD_HEIGHT + hy * CELL + 1, CELL - 2, CELL - 2)
                pygame.draw.rect(screen, (255, 255, 255), rect, 2)

        if state["phase"] in ("countdown", "playing", "ended"):
            draw_trail(state["trail1"], state["p1_plat"], state["pos1"])
            draw_trail(state["trail2"], state["p2_plat"], state["pos2"])

        if state["phase"] == "countdown" and state["countdown"]:
            cd_color = (120, 255, 140) if state["countdown"] == "Go, get in there! Move!" else (255, 220, 80)
            cd_font = font_huge if len(state["countdown"]) <= 2 else font_big
            big = cd_font.render(state["countdown"], True, cd_color)
            bg_rect = big.get_rect(center=(FIELD_X + (GRID_W * CELL) // 2, HUD_HEIGHT + (GRID_H * CELL) // 2))
            pad = pygame.Rect(bg_rect.x - 20, bg_rect.y - 14, bg_rect.width + 40, bg_rect.height + 28)
            pygame.draw.rect(screen, (0, 0, 0), pad)
            pygame.draw.rect(screen, cd_color, pad, 3)
            screen.blit(big, bg_rect)

        if state["phase"] == "ended":
            big = font_big.render(state["status"], True, (255, 220, 80))
            bg_rect = big.get_rect(center=(FIELD_X + (GRID_W * CELL) // 2, HUD_HEIGHT + (GRID_H * CELL) // 2))
            pad = pygame.Rect(bg_rect.x - 12, bg_rect.y - 8, bg_rect.width + 24, bg_rect.height + 16)
            pygame.draw.rect(screen, (0, 0, 0), pad)
            pygame.draw.rect(screen, (255, 220, 80), pad, 2)
            screen.blit(big, bg_rect)

        # --- Footer: KI-Hinweis, permanent sichtbar unter dem Spielfeld ---
        footer_y = HUD_HEIGHT + GRID_H * CELL
        pygame.draw.rect(screen, HUD_BG_COLOR, (0, footer_y, WINDOW_W, FOOTER_HEIGHT))
        footer_text = font_tiny.render(
            "Dieses Spiel wurde mit AI-Unterstuetzung generiert.",
            True, DIM_TEXT_COLOR)
        screen.blit(footer_text, footer_text.get_rect(center=(WINDOW_W // 2, footer_y + FOOTER_HEIGHT // 2)))
        version_text = font_tiny.render(f"build {SERVER_BUILD}", True, DIM_TEXT_COLOR)
        screen.blit(version_text, version_text.get_rect(right=WINDOW_W - 10, centery=footer_y + FOOTER_HEIGHT // 2))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


def main(host: str, port: int, http_port: int):
    t = threading.Thread(target=network_thread, args=(host, port, http_port), daemon=True)
    t.start()
    pygame_loop()  # blockiert im Haupt-Thread, bis das Fenster geschlossen wird


if __name__ == "__main__":
    h = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    p = int(sys.argv[2]) if len(sys.argv) > 2 else 6502
    hp = int(sys.argv[3]) if len(sys.argv) > 3 else 8080
    try:
        main(h, p, hp)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        stats.print_console()
