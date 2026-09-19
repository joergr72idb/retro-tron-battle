#!/usr/bin/env python3
"""
Retro Tron Battle Server (v3 - two participation methods)
=====================================================

A game server for a 2-player Tron/lightcycle duel, played by real
retro computers over a network:

  - Atari XL/XE  + FujiNet   (N:TCP/IP device)   -> raw TCP, port 6502
  - Commodore 64 + Meatloaf                      -> HTTP polling, port 8080
  - Amstrad CPC  + M4 board                      -> HTTP polling, port 8080

DESIGN
------
The retro computers only STEER - they don't draw the playfield
themselves. The playfield is drawn here, on the PC running this
server, in a pygame window (well suited for a projector/large monitor
at an event). This keeps each retro client's job down to almost
nothing except: read the joystick, send a MOVE on change, and
occasionally check whether the game is over. That in turn means the
retro clients spend very little time reading from the socket while
playing - which sidesteps unreliability some FujiNet setups show when
reads/writes on the same channel get nested too tightly.

Requires: pip install pygame

TWO WAYS TO JOIN - WHY BOTH EXIST
------------------------------------------------
Not every retro network add-on can keep a persistent raw TCP socket
open from plain BASIC. FujiNet (Atari) can, so it speaks the TCP
protocol below directly on port 6502. Meatloaf (C64) and the M4 board
(Amstrad CPC) are instead built for simple, one-off HTTP requests -
forcing a raw socket through them is either technically impossible
from BASIC (M4) or has proven unreliable over many rounds of real
hardware testing (Meatloaf). Both therefore poll a small HTTP bridge
on a second port instead - see "HTTP POLLING" below. Both access paths
run through exactly the same game logic (run_game() below); which path
a given platform uses is purely a question of what its network
hardware can actually do from BASIC, not a difference in the game
itself.

PROTOCOL 1: RAW TCP (port 6502, e.g. Atari/FujiNet)
--------------------------------------------------------
Client -> Server:
    HELLO <PLATFORM> <NAME> [PIN]   e.g. "HELLO ATARI Zorg AFC6GHJ"
                                   PIN is optional - a visitor photo ID
                                   from the event. Just leave it out
                                   (or send nothing after NAME) to play
                                   without a photo.
    MOVE <U|D|L|R>                 direction change (ignored if it
                                   would be a direct reversal into your
                                   own trail)
    BYE                            disconnect / give up

Server -> Client:
    WAIT                           connected, waiting for an opponent
    START <w> <h> <x1> <y1> <x2> <y2> <yourplayernum> <p1plat> <p2plat>
                                   signals "steering starts now" -
                                   clients don't need to do anything
                                   further with the fields, other than
                                   notice that the line arrived
    END WIN <PLATFORM> <NAME>     game over, someone won
    END DRAW                      game over, simultaneous crash
    STATS GAMES <n> <PLATFORM> <n> <PLATFORM> <n> ... DRAWS <n>
                                   sent right after END, running totals

This protocol has no TICK broadcast - the playfield only exists in
this process's memory and on the screen. Bots that want to "see" the
game (like tron_bot.sh) should use their own timer to decide when to
turn, instead of reacting to incoming tick data.

Between pairing and the first tick there's a short countdown on
screen (3, 2, 1, then a closing line), visible in the pygame window.
Direction changes sent during the countdown are already read in and
applied, but nobody actually moves until the closing line appears -
that's purely a pause on the display side, not new protocol messages.

Only ever two players play at a time; anyone connecting while a game
is running waits for the next free slot.

PROTOCOL 2: HTTP POLLING (port 8080, e.g. C64/Meatloaf, CPC/M4)
--------------------------------------------------------------------
Neither Meatloaf nor the M4 board can keep the TCP protocol above open
from BASIC, so these clients instead poll two simple HTTP GET routes
on a second port:

    GET /join/<platform>/<name>/<pin-or-NONE>  -> "SESSION <id>\n" + WAIT/START
    GET /tick/<session>/<direction-or-N>        -> whatever is pending
                                                    for them, or
                                                    "ERR UNKNOWN SESSION"
                                                    once the session is gone

A session behaves like a mailbox: /join creates one and returns an ID;
every /tick both delivers a MOVE (or "N" for "no change") and picks up
whatever the server has queued for that player since the last poll -
that can be nothing, a START line, or END+STATS once the game is over.
Sessions stay valid for a short grace period after the game ends (see
HTTPPlayerConn.close()) so that a client's next poll can still pick up
the final result even across a slow, real HTTP round trip - if a
client's poll arrives only after this grace period, it gets
"ERR UNKNOWN SESSION" and should treat that as "the match is
definitely over, start a new session".

This bridge internally creates exactly the same Player-like objects
and runs through exactly the same run_game() as the TCP clients - it's
just a different front door (see HTTPPlayerConn below).

Run with:
    python3 tron_server.py [host] [tcp_port] [http_port]
Defaults: 0.0.0.0 6502 8080
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
# VERSION - increment on every content change (shown in console + window)
# =============================================================================
SERVER_BUILD = 8
# =============================================================================

# =============================================================================
# REPO BASE DIRECTORY - all relative paths below (font, logos, CSV, photo
# cache) are resolved from here, NOT from the current working directory. This
# way the server works unchanged no matter where it's started from, as long
# as the repo's folder structure (server/ next to assets/) is preserved -
# e.g. after copying the whole repo to another machine.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# =============================================================================

# =============================================================================
# DEMO SCROLL TEXT - RUNS ACROSS THE PLAYFIELD WHILE WAITING FOR PLAYERS
# =============================================================================
SCROLL_TEXT = (" RETRO TRON BATTLE - RTB ON THE CC 2026 AT CELLE ") # <-- EDIT: YOUR OWN TEXT
SCROLL_FONT_PATH = os.path.join(BASE_DIR, "assets/font/Flynn-4v54.ttf")  # <-- EDIT: path to your own .ttf file,
                                     # or leave "" for the default font
SCROLL_SPEED = 8           # pixels per frame (at ~30fps)
SCROLL_FONT_SIZE = 180       # font size in pixels - 64=double, 96=triple
SCROLL_WAVE_AMPLITUDE = 120  # pixels, height of the sine wave
SCROLL_WAVE_FREQ = 0.10      # radians per character, "tightness" of the wave
SCROLL_WAVE_SPEED = 0.12     # radians per frame, speed of the wave
SCROLL_COLOR_SPEED = 0.02    # color gradient shift per frame (rainbow)
# =============================================================================

# =============================================================================
# HIGH-SCORE DISPLAY - ALTERNATES WITH THE SCROLL TEXT WHILE WAITING
# =============================================================================
SCROLL_LOOPS_BEFORE_HIGHSCORE = 2  # the high-score list shows after this many full loops
HIGHSCORE_DURATION = 20            # seconds the list stays up before the scroller resumes
# =============================================================================

# =============================================================================
# RESULTS LOG (CSV) - EDIT FOR YOUR SETUP
# =============================================================================
# A line is appended to this file after every finished game. On server
# start, the file (if present) is read back in and the score (total
# games, wins per platform, draws) is restored from it. If the file is
# missing, it simply starts at 0.
RESULTS_CSV_PATH = os.path.join(BASE_DIR, "tron_results.csv")  # <-- EDIT: path to the results CSV
CSV_FIELDNAMES = ["timestamp", "p1_platform", "p1_name", "p2_platform", "p2_name",
                   "result", "winner_platform", "winner_name"]
# =============================================================================

# =============================================================================
# LOG FILE - IN ADDITION TO THE CONSOLE, FOR DEBUGGING DURING HARDWARE TESTS
# =============================================================================
# Everything output via log() (instead of print()) lands both on the
# console and appended to this file - among other things steering
# commands (see drain_moves()) and a searchable header per game start.
LOG_FILE_PATH = os.path.join(BASE_DIR, "tron_server.log")  # <-- EDIT: path to the log file
# =============================================================================

# =============================================================================
# EVENT PHOTO / LOGO CONFIGURATION - ADAPT THIS BLOCK FOR YOUR EVENT
# =============================================================================
# Visitors get a PIN (e.g. "MUSTER") linked to a photo of them,
# organized on the fotofix server as one folder per PIN with a fixed
# filename (HTTP_PHOTO_FILENAME, "photo.jpg" by default) - e.g. PIN
# "MUSTER" -> ".../MUSTER/photo.jpg". This server fetches that photo
# either via HTTP or via FTP, depending on PHOTO_SOURCE below, and
# shows it next to that visitor's side of the playfield, together with
# their computer manufacturer's logo. Both fetch methods use exactly
# the same <PIN>/<HTTP_PHOTO_FILENAME> path - HTTP just needs a
# complete URL (HTTP_PHOTO_BASE_URL), FTP just needs a host (FTP_HOST,
# typically an IP address rather than a hostname).
PHOTO_SOURCE = "HTTP"  # <-- EDIT: "FTP" or "HTTP" - switches the fetch method

# --- FTP variant: path on the FTP server = <FTP_REMOTE_DIR>/<PIN>/
#     <HTTP_PHOTO_FILENAME> (same structure as HTTP below, just with
#     FTP_HOST as the host instead of a full URL) ---
FTP_HOST = "192.168.17.158"     # <-- EDIT: the fotofix server's IP address
FTP_PORT = 21
FTP_USER = "anonymous"           # <-- EDIT if the FTP server needs a login
FTP_PASS = "anonymous@"          # <-- EDIT
FTP_REMOTE_DIR = ""       # <-- EDIT: parent folder on the FTP server,
                           #     if the PIN folders aren't directly in the root

# --- HTTP variant: URL = HTTP_PHOTO_BASE_URL + "/" + <PIN> + "/" +
#     HTTP_PHOTO_FILENAME, e.g. PIN "MUSTER" ->
#     http://fotofix.classic-computing.de/MUSTER/photo.jpg ---
HTTP_PHOTO_BASE_URL = "http://fotofix.classic-computing.de"  # <-- EDIT
HTTP_PHOTO_FILENAME = "photo.jpg"                             # <-- EDIT if this ever changes
                                                                #     (applies to FTP AND HTTP)

PHOTO_CACHE_DIR = os.path.join(BASE_DIR, "photo_cache")  # downloaded photos get cached here (created automatically)

# Local, freely editable folder for the three company logos AND the
# event's club logo (top right, always visible). Drop image files in
# here any time - no restart needed for the company logos (freshly
# loaded on every new match); the club logo is only loaded once at
# startup (see event_logo_surf in pygame_loop()), so a restart IS
# needed if that one changes. Any of these filenames works per
# platform (first match wins): atari.png/.jpg, commodore.png/.jpg,
# c64.png/.jpg, schneider.png/.jpg, cpc.png/.jpg, amstrad.png/.jpg -
# plus "logo.png/.jpg/..." for the club logo. Extension matching is
# case-sensitive on Linux, so both lower- and uppercase extensions are
# checked (LOGO_EXTENSIONS below).
LOGO_DIR = os.path.join(BASE_DIR, "assets/logos")               # <-- EDIT if the logos should live elsewhere
LOGO_NAME_CANDIDATES = {
    "ATARI": ["atari"],
    "C64": ["commodore", "c64"],
    "CPC": ["schneider", "cpc", "amstrad"],
    "APPLE2": ["apple2", "apple"],
}
LOGO_EXTENSIONS = [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG", ".gif", ".GIF", ".bmp", ".BMP"]
# =============================================================================

# =============================================================================
# TRIBUTE SCREEN - THIRD WAITING-SCREEN VIEW (AFTER THE SCROLL TEXT AND
# HIGH-SCORE LIST), CREDITS THE PROJECTS BEHIND THE WIFI INTERFACES
# =============================================================================
TRIBUTE_TITLE = "SPECIAL THANKS TO"  # <-- EDIT: your own text
TRIBUTE_DURATION = 30  # seconds the tribute screen stays up
TRIBUTE_ENTRIES = [  # (image, credit text, url to display) - <-- EDIT for your own credits
    (os.path.join(BASE_DIR, "assets/logos/projects/fujinet.jpg"),
     "THE FUJINET PROJECT", "fujinet.online"),
    (os.path.join(BASE_DIR, "assets/logos/projects/meatloaf.png"),
     "JAMIE JOHNSTON (IDOLPX) - MEATLOAF", "github.com/idolpx/meatloaf"),
    (os.path.join(BASE_DIR, "assets/logos/projects/m4.png"),
     "DUKE - M4 INTERFACE", "github.com/M4Duke/m4hardware"),
    (os.path.join(BASE_DIR, "assets/logos/projects/wic64.png"),
     "THE WIC64 PROJECT", "wic64.net/web/"),
]
# =============================================================================

# =============================================================================
# FOTOFIX THANKS - FOURTH WAITING-SCREEN VIEW (AFTER THE TRIBUTE SCREEN),
# a single thank-you - e.g. to a person/project that doesn't need a
# slot in the TRIBUTE_ENTRIES list above (currently: the FOTOFIX
# project, see clients/c64/wic64-driver/README.md)
# =============================================================================
GREETING_IMAGE = os.path.join(BASE_DIR, "assets/logos/greetings/greeting.jpg")  # <-- EDIT
GREETING_TEXT = "THANKS A LOT!"  # <-- EDIT
GREETING_DURATION = 20  # seconds the thank-you screen stays up
# =============================================================================

GRID_W = 60
GRID_H = 32
TICK_RATE = 8  # ticks/sec - keep modest, these are slow clients on real silicon

CELL = 18             # pixel size of one grid cell in the display window
HUD_HEIGHT = 120      # pixel height of the stats/status header
FOOTER_HEIGHT = 44    # pixel height of the footer (AI notice + credits, 2 lines)
PANEL_W = 170         # width of each side panel (logo + visitor photo)
FIELD_X = PANEL_W     # playfield starts right of the left panel
WINDOW_W = PANEL_W * 2 + GRID_W * CELL
WINDOW_H = HUD_HEIGHT + GRID_H * CELL + FOOTER_HEIGHT

# Colors evoking each machine's iconic screen look.
PLATFORM_COLORS = {
    "ATARI": (108, 174, 216),   # Atari BASIC light blue
    "C64": (183, 173, 35),      # Commodore 64 gold/gelb
    "CPC": (70, 200, 110),      # Schneider/Amstrad CPC green phosphor
    "APPLE2": (220, 110, 60),   # Apple II - amber monochrome monitor
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
    """Downloads <pin>/<HTTP_PHOTO_FILENAME> (same folder+filename structure
    as the HTTP variant, just over FTP instead of HTTP, e.g. host as an
    IP address) into the local cache and returns the local path, or
    None if not found/no PIN. Does blocking network I/O - only call via
    run_in_executor, never directly from the event loop."""
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
    """Downloads <PIN>/<HTTP_PHOTO_FILENAME> from HTTP_PHOTO_BASE_URL into
    the local cache and returns the local path, or None if not
    found/no PIN. Same blocking I/O contract as fetch_photo_ftp_blocking
    - only call via run_in_executor, never directly from the asyncio
    event loop."""
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
    """Dispatcher - calls either the FTP or the HTTP photo fetch depending
    on PHOTO_SOURCE, with nothing changing at the call site. Blocking -
    only call via run_in_executor, never directly from the event loop."""
    if PHOTO_SOURCE.upper() == "HTTP":
        return fetch_photo_http_blocking(pin)
    return fetch_photo_ftp_blocking(pin)


def logo_path_for(platform: str):
    """Looks for a company logo image for a platform in LOGO_DIR. Cheap
    local filesystem check - safe to call directly from the event loop."""
    for base in LOGO_NAME_CANDIDATES.get(platform, []):
        for ext in LOGO_EXTENSIONS:
            p = os.path.join(LOGO_DIR, base + ext)
            if os.path.exists(p):
                return p
    return None


def event_logo_path():
    """Looks for the event's club logo ("logo.jpg" or similar) in the same
    folder as the company logos. Same cheap local check as
    logo_path_for()."""
    for ext in LOGO_EXTENSIONS:
        p = os.path.join(LOGO_DIR, "logo" + ext)
        if os.path.exists(p):
            return p
    return None


def log(msg: str) -> None:
    """Like print(), additionally appends msg to LOG_FILE_PATH (see config
    above). File-access errors should never abort the game - worst case
    the message just ends up on the console only."""
    print(msg)
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError as e:
        print(f"[log] couldn't write to {LOG_FILE_PATH}: {e}")


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
    photo_task: object = field(default=None, repr=False)  # asyncio.Future from run_in_executor
    inbuf: object = field(default_factory=lambda: LineBuffer(), repr=False)


class Stats:
    """Tracks the total number of games played and wins per retro platform."""

    def __init__(self):
        self.games_played = 0
        self.wins = {}  # platform -> win count
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
    """Reads existing results from RESULTS_CSV_PATH and rebuilds the current
    score from them (via the normal record_win/record_draw methods, so
    it's exactly the same logic used live). If the file is missing, it
    simply starts at 0. Individual malformed rows are skipped instead of
    aborting startup."""
    if not os.path.exists(RESULTS_CSV_PATH):
        print(f"[stats] no {RESULTS_CSV_PATH} found - starting at 0")
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
        print(f"[stats] couldn't read {RESULTS_CSV_PATH}, starting at 0: {e}")
        return
    msg = f"[stats] loaded {loaded} previous games from {RESULTS_CSV_PATH}"
    if skipped:
        msg += f" ({skipped} malformed row(s) skipped)"
    print(msg)
    stats.print_console()


def append_result_to_csv(p1: "Player", p2: "Player", result: str,
                          winner_platform: str = "", winner_name: str = ""):
    """Appends a line for the just-finished game to RESULTS_CSV_PATH
    (creates the file including a header row if it doesn't exist yet).
    A write error (e.g. a permissions problem) doesn't crash the
    server, it just prints a console warning."""
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
        print(f"[stats] couldn't write result to {RESULTS_CSV_PATH}: {e}")


stats = Stats()
load_stats_from_csv()
waiting_player: Player | None = None
lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Shared render state. The asyncio side (network thread) writes here
# under render_lock; the pygame side (main thread) reads roughly 30
# times a second under the same lock. Keep updates cheap - copy in
# small structures, never hand out live references to mutable game
# objects.
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
    """Collects raw bytes from a socket and extracts complete lines,
    tolerant of \\r, \\n or \\r\\n as terminators - some retro network
    stacks (especially Commodore/IEC) traditionally use a single CR
    instead of LF. Keeps incomplete lines across multiple calls, so a
    line split across two reads is never corrupted or dropped."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf.extend(data)

    def pop_line(self):
        for i, b in enumerate(self.buf):
            if b in (0x0D, 0x0A):
                line = bytes(self.buf[:i])
                rest = self.buf[i + 1:]
                # Swallow a paired second terminator byte (CRLF or LFCR).
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
    """Reads a single line (only used for the initial HELLO handshake) -
    CR/LF-tolerant via a disposable LineBuffer, fed in chunks."""
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
    """Shared pairing logic, used by both the TCP path (a real socket) and
    the HTTP-polling path (an HTTPPlayerConn stand-in). Either registers
    as the waiting player (sends WAIT) or pairs with whoever's already
    waiting and starts the game as a background task."""
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
# HTTP-POLLING BRIDGE FOR C64/MEATLOAF AND AMSTRAD CPC/M4
# =============================================================================
# Neither Meatloaf nor the M4 board can reliably keep a persistent raw
# TCP socket open from plain BASIC (M4 simply can't from BASIC without
# hand-written Z80 assembly; Meatloaf can technically open one, but
# that's proven unreliable over many rounds of real hardware testing).
# Both can, however, make simple HTTP GET requests from BASIC, so both
# clients poll small HTTP requests instead of keeping a connection
# open: once /join, then repeatedly /tick (sends any direction change,
# gets back whatever's pending - WAIT, START, or eventually END +
# STATS). Everything below just fits this request/response polling
# into the same Player/run_game machinery the TCP client (Atari) uses,
# via a duck-typed stand-in for (StreamReader, StreamWriter).
# =============================================================================
http_sessions: dict = {}
# Remembers the expiry time (time.monotonic()) of recently removed
# sessions - a pure diagnostic aid for "session not found": tells apart
# "session genuinely expired" from "never existed" (e.g. because of a
# mangled join response on the client side).
recently_expired_sessions: dict = {}


class HTTPPlayerConn:
    """Stands in for a (StreamReader, StreamWriter) pair for an
    HTTP-polled player. Lines sent TO this "connection" (via
    send()/writer.write()) collect in an outbox that the next /tick
    poll drains and returns. Lines arriving FROM the player (MOVE
    commands from /tick requests) go into an asyncio.Queue that
    readline() reads from - so run_game()'s existing 10ms-timeout read
    pattern works unchanged here too."""

    def __init__(self, session_id: str = ""):
        self._inbox = asyncio.Queue()
        self._outbox = []
        self.closed = False
        self.session_id = session_id
        self.platform = ""
        self.name = ""
        self.last_tick_at = None  # monotonic() at the last /tick, for the
        # tick-latency logging in http_handle_request() below

    async def readline(self):
        return await self._inbox.get()

    async def read(self, n=256):
        # n is ignored - queued elements are always small, ready-made
        # "line\n" byte chunks from feed_line() - same contract as a real
        # socket's read(), which returns "whatever's currently available".
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
        # Unlike a real TCP socket close, an HTTP "connection" is just
        # this object sitting in http_sessions. If we removed it right
        # away, the one /tick poll meant to pick up the final END+STATS
        # would almost always arrive too late - a full HTTP round trip
        # (open, read, close) takes real wall-clock time, while filling
        # the outbox and deleting the session here happen back to back
        # with no meaningful gap. So instead: keep the session alive for
        # a grace period, so the client has enough chances to poll and
        # actually receive the final message, and only clean up after
        # that.
        if self.session_id:
            loop = asyncio.get_running_loop()
            loop.call_later(15, self._expire)

    def _expire(self):
        if self.session_id and http_sessions.get(self.session_id) is self:
            del http_sessions[self.session_id]
            recently_expired_sessions[self.session_id] = time.monotonic()

    def get_extra_info(self, *a, **k):
        return None

    def pop_outbox(self) -> str:
        text = "".join(self._outbox)
        self._outbox.clear()
        return text


HTTP_DIR_MAP = {"U": "MOVE U", "D": "MOVE D", "L": "MOVE L", "R": "MOVE R"}


async def http_handle_request(path: str) -> str:
    """Routes a parsed HTTP GET path to the join/tick logic and returns the
    plain-text body to send back. path has no leading '?' query string -
    everything is path segments (how the device firmware handles '?'/'&'
    in |HTTPGET requests isn't documented/confirmed, so this deliberately
    avoids it): /join/<platform>/<name>/<pin-or-NONE> and
    /tick/<session>/<direction-or-N>"""
    segments = [s for s in path.strip("/").split("/") if s != ""]

    if not segments:
        return "TRON SERVER OK"

    if segments[0] == "join" and len(segments) >= 3:
        platform = segments[1].upper()
        name = segments[2]
        pin = segments[3] if len(segments) > 3 and segments[3].upper() != "NONE" else ""

        session_id = uuid.uuid4().hex[:8].upper()
        conn = HTTPPlayerConn(session_id)
        conn.platform = platform
        conn.name = name
        http_sessions[session_id] = conn
        print(f"[http] JOIN: new session stored: {session_id!r}  (current keys: {list(http_sessions.keys())!r})")

        asyncio.create_task(pair_and_maybe_start(platform, name, pin, conn, conn, peer_desc="HTTP"))
        # Give the pairing a brief moment, so a match at the exact same
        # instant returns START right away instead of forcing another
        # round trip.
        await asyncio.sleep(0.05)
        return f"SESSION {session_id}\n" + conn.pop_outbox()

    if segments[0] == "tick" and len(segments) >= 2:
        session_id = segments[1].upper()  # meatloaf appears to convert
        # between ascii/petscii somewhere during GET#, scrambling the
        # case - so be deliberately tolerant about it here
        direction = segments[2].upper() if len(segments) > 2 else "N"
        conn = http_sessions.get(session_id)
        if conn is None:
            expired_ago = recently_expired_sessions.get(session_id)
            reason = (f"expired {time.monotonic() - expired_ago:.1f}s ago"
                      if expired_ago is not None else "never existed here")
            print(f"[http] TICK: requested session {session_id!r} NOT found "
                  f"({reason}). current keys: {list(http_sessions.keys())!r}")
            return "ERR UNKNOWN SESSION"
        now = time.monotonic()
        if conn.last_tick_at is not None:
            gap_ms = (now - conn.last_tick_at) * 1000
            log(f"[tick-latency] {conn.platform}/{conn.name}: {gap_ms:.0f} ms since last /tick")
        conn.last_tick_at = now
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
        # Read and discard the remaining request headers.
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=2)
            if not line or line in (b"\r\n", b"\n"):
                break

        try:
            method, raw_path, _ = request_line.decode("ascii", errors="ignore").split()
        except ValueError:
            print(f"[http] couldn't parse request line: {request_line!r}")
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
    """Non-blockingly reads and applies any pending MOVE/BYE commands for
    each player. Used both during the countdown (so direction changes
    aren't lost) and in the normal game tick, so both spots behave
    exactly the same."""
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
                    if d == OPPOSITE.get(p.direction):
                        log(f"[move] {p.platform}/{p.name}: {d} ignored (reverse of {p.direction})")
                    elif d != p.direction:
                        log(f"[move] {p.platform}/{p.name}: {p.direction} -> {d}")
                        p.direction = d
                    # else: client is resending the same direction (normal for
                    # HTTP-polling clients, e.g.) - don't log it, or it'd flood
                    # the file with no new information.
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
    log("=" * 60)
    log(f"[*] GAME START {datetime.now().isoformat(timespec='seconds')} - "
        f"{p1.platform}/{p1.name} vs {p2.platform}/{p2.name}")
    log("=" * 60)

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

    # --- Countdown: 3, 2, 1, then the closing line (see below) - direction
    # changes are already read in (so nothing gets lost), but nobody
    # actually moves. ---
    for count in (3, 2, 1):
        update_render(countdown=str(count))
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            await drain_moves(players)
            if not (p1.alive and p2.alive):
                break  # someone sent BYE while waiting
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
        log(f"[=] GAME END {datetime.now().isoformat(timespec='seconds')} - "
            f"{winner.platform}/{winner.name} wins!")
    else:
        stats.record_draw()
        append_result_to_csv(p1, p2, "DRAW")
        result = "END DRAW"
        status = "DRAW - SIMULTANEOUS CRASH!"
        log(f"[=] GAME END {datetime.now().isoformat(timespec='seconds')} - draw (simultaneous crash)")

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

    await asyncio.sleep(4)  # leave the result on screen for a few more seconds
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
    tron_font_found = bool(SCROLL_FONT_PATH and os.path.exists(SCROLL_FONT_PATH))
    if not tron_font_found and SCROLL_FONT_PATH:
        print(f"[display] Scroll font not found: {SCROLL_FONT_PATH} - using default font")

    def load_tron_font(size):
        """Same font file as the demo scroller (SCROLL_FONT_PATH), just at a
        different size - with the same default-font fallback."""
        if tron_font_found:
            return pygame.font.Font(SCROLL_FONT_PATH, size)
        return pygame.font.SysFont("couriernew,monospace", size, bold=True)

    scroll_font = load_tron_font(SCROLL_FONT_SIZE)
    highscore_title_font = load_tron_font(84)
    highscore_row_font = load_tron_font(42)
    tribute_title_font = load_tron_font(40)
    tribute_caption_font = load_tron_font(24)
    tribute_url_font = load_tron_font(16)

    # Demo-scroller state: only advances/gets drawn while the server phase
    # is "waiting" (see the main loop further below).
    scroll_char_widths = [scroll_font.size(c)[0] for c in SCROLL_TEXT]
    scroll_total_width = sum(scroll_char_widths)
    scroll_x = WINDOW_W
    scroll_wave_phase = 0.0
    scroll_hue = 0.0

    # The waiting screen cycles through, for as long as the server is
    # waiting for players: scroll text (SCROLL_LOOPS_BEFORE_HIGHSCORE full
    # loops) -> high-score list (HIGHSCORE_DURATION seconds) -> tribute
    # screen (TRIBUTE_DURATION seconds) -> fotofix thanks (GREETING_DURATION
    # seconds) -> back to scroll text, etc. (see config above).
    waiting_mode = "scroll"
    scroll_loop_count = 0
    highscore_shown_until = 0.0
    tribute_shown_until = 0.0
    greeting_shown_until = 0.0

    # Cache loaded+scaled images by (path, max_w, max_h), so we don't
    # re-decode the same JPEG/PNG on every single frame.
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

    # Club logo: loaded once right after startup, stays in memory for the
    # rest of the program and is shown in EVERY phase (waiting, countdown,
    # game, result) - not re-checked against the filesystem every frame.
    event_logo_surf = load_scaled(event_logo_path(), PANEL_W - 20, 70)
    if event_logo_surf is None:
        print(f"[display] club logo not found (expected: logo.jpg/.png/... in {LOGO_DIR})")
        try:
            actual_files = os.listdir(LOGO_DIR)
            print(f"[display] actually present in {LOGO_DIR}: {actual_files}")
        except Exception as e:
            print(f"[display] couldn't list {LOGO_DIR}: {e}")

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

    def draw_highscore(wins, draws, games_played):
        """Classic high-score list, platform with the most wins first - one
        of the alternating waiting-screen views, see waiting_mode in the
        main loop."""
        cx = FIELD_X + (GRID_W * CELL) // 2
        top = HUD_HEIGHT + 40

        title = highscore_title_font.render("HIGH SCORES", True, (255, 220, 80))
        screen.blit(title, title.get_rect(centerx=cx, top=top))
        y = top + title.get_height() + 30

        ranked = sorted(wins.items(), key=lambda kv: -kv[1])
        if not ranked:
            line = highscore_row_font.render("NO GAMES PLAYED YET", True, DIM_TEXT_COLOR)
            screen.blit(line, line.get_rect(centerx=cx, top=y))
            y += line.get_height() + 10
        else:
            for rank, (plat, count) in enumerate(ranked, start=1):
                color = color_for(plat)
                text = f"{rank}.  {plat}   {count} WIN{'S' if count != 1 else ''}"
                line = highscore_row_font.render(text, True, color)
                screen.blit(line, line.get_rect(centerx=cx, top=y))
                y += line.get_height() + 14

        y += 20
        footer = font_small.render(
            f"Games played: {games_played}   Draws: {draws}", True, DIM_TEXT_COLOR)
        screen.blit(footer, footer.get_rect(centerx=cx, top=y))

    def wrap_text(text, font, max_width):
        """Splits text into lines that each fit within max_width (wrapped by
        word) - for credit texts of unknown/varying length in
        draw_tribute()."""
        words = text.split(" ")
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if not cur or font.size(test)[0] <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw_tribute():
        """Credits the projects behind the WiFi interfaces (TRIBUTE_ENTRIES
        in the config above) - third alternating waiting-screen view, see
        waiting_mode in the main loop."""
        cx = FIELD_X + (GRID_W * CELL) // 2
        top = HUD_HEIGHT + 30

        title = tribute_title_font.render(TRIBUTE_TITLE, True, (255, 220, 80))
        screen.blit(title, title.get_rect(centerx=cx, top=top))

        n = len(TRIBUTE_ENTRIES)
        if n == 0:
            return
        col_w = (GRID_W * CELL) // n
        img_top = top + title.get_height() + 30
        img_max_w = col_w - 40
        img_max_h = 220

        for idx, (path, credit, url) in enumerate(TRIBUTE_ENTRIES):
            col_cx = FIELD_X + col_w * idx + col_w // 2

            img = load_scaled(path, img_max_w, img_max_h)
            if img:
                rect = img.get_rect(centerx=col_cx, top=img_top)
                screen.blit(img, rect)

            y = img_top + img_max_h + 16
            for line in wrap_text(credit, tribute_caption_font, col_w - 20):
                line_surf = tribute_caption_font.render(line, True, TEXT_COLOR)
                screen.blit(line_surf, line_surf.get_rect(centerx=col_cx, top=y))
                y += line_surf.get_height() + 4

            y += 8
            url_surf = tribute_url_font.render(url, True, DIM_TEXT_COLOR)
            screen.blit(url_surf, url_surf.get_rect(centerx=col_cx, top=y))

    def draw_greeting():
        """A single thank-you (GREETING_IMAGE/GREETING_TEXT in the config
        above) - fourth alternating waiting-screen view, see waiting_mode
        in the main loop."""
        cx = FIELD_X + (GRID_W * CELL) // 2
        y = HUD_HEIGHT + 40

        img = load_scaled(GREETING_IMAGE, GRID_W * CELL - 160, 340)
        if img:
            rect = img.get_rect(centerx=cx, top=y)
            screen.blit(img, rect)
            y = rect.bottom + 30
        else:
            y += 30

        for line in wrap_text(GREETING_TEXT, tribute_title_font, GRID_W * CELL - 80):
            line_surf = tribute_title_font.render(line, True, (255, 220, 80))
            screen.blit(line_surf, line_surf.get_rect(centerx=cx, top=y))
            y += line_surf.get_height() + 6

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        state = snapshot_render()

        screen.fill(HUD_BG_COLOR)

        # --- HUD (header with title, status, score) ---
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

        # --- Club logo top right, loaded once (see above), permanently
        # visible in every phase ---
        if event_logo_surf:
            rect = event_logo_surf.get_rect(right=WINDOW_W - 16, top=10)
            screen.blit(event_logo_surf, rect)

        # --- Side panels (logo + visitor photo) ---
        if state["phase"] in ("countdown", "playing", "ended"):
            draw_panel(0, state["p1_name"], state["p1_plat"], state["photo1"], state["logo1"])
            draw_panel(FIELD_X + GRID_W * CELL, state["p2_name"], state["p2_plat"],
                       state["photo2"], state["logo2"])

        # --- Playfield ---
        field_rect = pygame.Rect(FIELD_X, HUD_HEIGHT, GRID_W * CELL, GRID_H * CELL)
        pygame.draw.rect(screen, BG_COLOR, field_rect)
        for gx in range(GRID_W + 1):
            x = FIELD_X + gx * CELL
            pygame.draw.line(screen, GRID_LINE_COLOR, (x, HUD_HEIGHT), (x, WINDOW_H))
        for gy in range(GRID_H + 1):
            y = HUD_HEIGHT + gy * CELL
            pygame.draw.line(screen, GRID_LINE_COLOR, (FIELD_X, y), (FIELD_X + GRID_W * CELL, y))

        # --- Waiting screen: scroll text, high-score list and tribute
        # screen alternate, only runs while waiting for players ---
        if state["phase"] == "waiting":
            if waiting_mode == "highscore":
                draw_highscore(state["wins"], state["draws"], state["games_played"])
                if time.monotonic() >= highscore_shown_until:
                    waiting_mode = "tribute"
                    tribute_shown_until = time.monotonic() + TRIBUTE_DURATION
            elif waiting_mode == "tribute":
                draw_tribute()
                if time.monotonic() >= tribute_shown_until:
                    waiting_mode = "greeting"
                    greeting_shown_until = time.monotonic() + GREETING_DURATION
            elif waiting_mode == "greeting":
                draw_greeting()
                if time.monotonic() >= greeting_shown_until:
                    waiting_mode = "scroll"
            else:
                scroll_x -= SCROLL_SPEED
                scroll_wave_phase += SCROLL_WAVE_SPEED
                scroll_hue = (scroll_hue + SCROLL_COLOR_SPEED) % 1.0
                if scroll_x < -scroll_total_width:
                    scroll_x = WINDOW_W
                    scroll_loop_count += 1
                    if scroll_loop_count >= SCROLL_LOOPS_BEFORE_HIGHSCORE:
                        scroll_loop_count = 0
                        waiting_mode = "highscore"
                        highscore_shown_until = time.monotonic() + HIGHSCORE_DURATION

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

        # --- Footer: AI notice + credits, permanently visible below the
        # playfield, two lines (see FOOTER_HEIGHT) ---
        footer_y = HUD_HEIGHT + GRID_H * CELL
        pygame.draw.rect(screen, HUD_BG_COLOR, (0, footer_y, WINDOW_W, FOOTER_HEIGHT))
        row_h = FOOTER_HEIGHT // 2
        row1_y = footer_y + row_h // 2
        row2_y = footer_y + row_h + row_h // 2

        footer_text = font_tiny.render(
            "This game was generated with AI assistance.",
            True, DIM_TEXT_COLOR)
        screen.blit(footer_text, footer_text.get_rect(center=(WINDOW_W // 2, row1_y)))
        version_text = font_tiny.render(f"build {SERVER_BUILD}", True, DIM_TEXT_COLOR)
        screen.blit(version_text, version_text.get_rect(right=WINDOW_W - 10, centery=row1_y))

        credits_text = font_tiny.render(
            "Flynn font: Neale Davidson (Pixel Sagas)  ·  "
            "WiC64 HTTP-Requester: Andreas Beermann (andi6510) · "
            "Jürgen Leber (JogiBaer) made my M4 ;-)",
            True, DIM_TEXT_COLOR)
        screen.blit(credits_text, credits_text.get_rect(center=(WINDOW_W // 2, row2_y)))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


def main(host: str, port: int, http_port: int):
    t = threading.Thread(target=network_thread, args=(host, port, http_port), daemon=True)
    t.start()
    pygame_loop()  # blocks on the main thread until the window is closed


if __name__ == "__main__":
    h = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    p = int(sys.argv[2]) if len(sys.argv) > 2 else 6502
    hp = int(sys.argv[3]) if len(sys.argv) > 3 else 8080
    try:
        main(h, p, hp)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        stats.print_console()
