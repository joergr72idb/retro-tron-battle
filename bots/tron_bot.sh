#!/usr/bin/env bash
#
# tron_bot.sh - simulates a retro Tron client over TCP.
#
# Speaks the same line-based protocol as the real Atari/C64/Amstrad clients,
# so you can pair it against a real machine to test the server without
# needing every machine plugged in at once.
#
# Behaviour: connects, sends HELLO, then - once the game has started -
# polls on a short timer (not tick-driven, since the server no longer
# broadcasts per-tick board data; the board only exists server-side now)
# and has a 1-in-N chance each poll of turning in a random (non-current)
# direction, just enough movement to be a live sparring partner. Prints
# everything the server sends so you can watch the match from the terminal.
#
# Usage:
#   ./tron_bot.sh [HOST] [PORT] [PLATFORM] [NAME] [TURN_CHANCE]
#
# Examples:
#   ./tron_bot.sh 192.168.1.50 6502 C64 Commodore64
#   ./tron_bot.sh 192.168.1.50 6502 CPC AmstradCPC 8
#
# NOTE: the server pairs the first two connections it sees. Start only ONE
# bot if you want it to wait for your real Atari client to be the second
# player - starting two bots at once will pair them with each other.

set -uo pipefail

HOST="${1:-127.0.0.1}"
PORT="${2:-6502}"
PLATFORM="${3:-C64}"
NAME="${4:-Bot}"
TURN_CHANCE="${5:-12}"   # roughly 1-in-N poll ticks triggers a turn
PIN="${6:-}"             # optional: a visitor PIN, to test the photo/logo feature
POLL_INTERVAL="0.2"      # seconds between "should I turn?" checks

if ! command -v nc >/dev/null 2>&1; then
    echo "This script needs netcat (nc) installed." >&2
    exit 1
fi

echo "[$PLATFORM/$NAME] connecting to $HOST:$PORT ..."

# Open a persistent, bidirectional netcat connection as a coprocess so we
# can both read server messages and write MOVE commands on the same socket.
coproc NC { nc "$HOST" "$PORT"; }

send() {
    printf '%s\n' "$1" >&"${NC[1]}" 2>/dev/null
}

if [ -n "$PIN" ]; then
    send "HELLO $PLATFORM $NAME $PIN"
else
    send "HELLO $PLATFORM $NAME"
fi

CURDIR="R"
STARTED=0
IDLE_COUNT=0
MAX_IDLE=150   # ~30s of nothing at all (not even after connecting) = give up

while true; do
    if read -r -u "${NC[0]}" -t "$POLL_INTERVAL" line; then
        line="${line%$'\r'}"
        IDLE_COUNT=0
        case "$line" in
            WAIT)
                echo "[$PLATFORM/$NAME] waiting for an opponent..."
                ;;
            START*)
                # START <w> <h> <x1> <y1> <x2> <y2> <yourplayernum> <p1plat> <p2plat>
                read -r _ W H X1 Y1 X2 Y2 PNUM P1PLAT P2PLAT <<< "$line"
                if [ "$PNUM" = "1" ]; then CURDIR="R"; else CURDIR="L"; fi
                STARTED=1
                echo "[$PLATFORM/$NAME] game start! I'm player $PNUM - watch the server's window"
                ;;
            "END WIN"*)
                echo "[$PLATFORM/$NAME] $line"
                STARTED=0
                ;;
            "END DRAW")
                echo "[$PLATFORM/$NAME] draw game."
                STARTED=0
                ;;
            STATS*)
                echo "[$PLATFORM/$NAME] $line"
                break
                ;;
            *)
                echo "[$PLATFORM/$NAME] < $line"
                ;;
        esac
    else
        # Timed out waiting for a line - this is normal now (no tick spam).
        IDLE_COUNT=$((IDLE_COUNT + 1))
        if [ "$IDLE_COUNT" -ge "$MAX_IDLE" ]; then
            echo "[$PLATFORM/$NAME] no response from server for a while, giving up."
            break
        fi
        if [ "$STARTED" -eq 1 ] && [ $(( RANDOM % TURN_CHANCE )) -eq 0 ]; then
            case "$CURDIR" in
                U) OPTS=(D L R) ;;
                D) OPTS=(U L R) ;;
                L) OPTS=(U D R) ;;
                R) OPTS=(U D L) ;;
                *) OPTS=(U D L R) ;;
            esac
            NEWDIR="${OPTS[$(( RANDOM % ${#OPTS[@]} ))]}"
            CURDIR="$NEWDIR"
            send "MOVE $NEWDIR"
        fi
    fi
done

if [ -n "${NC[1]:-}" ]; then
    send "BYE" 2>/dev/null || true
    exec {NC[1]}>&- 2>/dev/null || true
fi
if [ -n "${NC_PID:-}" ]; then
    wait "$NC_PID" 2>/dev/null || true
fi
echo "[$PLATFORM/$NAME] disconnected."
