# CLAUDE.md — Context & lessons learned for this project

This document is for anyone (AI assistant or human) continuing work on
this project. It summarizes what was painstakingly figured out during
the original development session (Claude, over several weeks) — much
of it isn't documented on any official reference page.
**Please read before tinkering with the clients — otherwise you'll
likely repeat mistakes that have already been made and fixed.**

## Project overview

A Tron/lightcycle duel for a retro-computing exhibition, built for
[Classic Computing 2026](https://www.classic-computing.de/cc2026/) in
Celle (10–11 October 2026, Hall 10 / CD-Kaserne). Three real retro
computers (Atari XL/XE, Commodore 64, Schneider/Amstrad CPC) face off
against each other. A Python server on a modern PC handles the entire
game logic and draws everything itself (pygame window, good for a
projector) — the retro computers only steer via joystick.

Each retro computer needs a matching WiFi interface to reach the
server:

- **Atari XL/XE:** [FujiNet](https://fujinet.online/)
- **Commodore 64 (standard client):** [Meatloaf](https://github.com/idolpx/meatloaf)
- **Commodore 64 (experimental client):** [WiC64](https://www.wic64.de/)
- **Schneider/Amstrad CPC:** [M4 Board](https://www.cpcwiki.eu/index.php/M4_Board)

## Architecture in brief

- **`server/tron_server.py`** — the one and only server. Runs the game
  logic, draws the playfield, manages photos/logos/scroll text/stats.
  The main docstring in the code itself is the primary protocol
  documentation — check/update it first whenever the protocol changes.
- **Two participation methods**, depending on hardware capability:
  - **Raw TCP** (port 6502) — for Atari/FujiNet, which can keep a
    persistent socket open from BASIC.
  - **HTTP polling** (port 8080, routes `/join` and `/tick`) — for C64
    (Meatloaf) and Schneider CPC (M4), which can't do that reliably.
- Both paths run through **the same** `run_game()` logic server-side.

## The most important lessons (chronological by platform)

### Commodore 64 + Meatloaf

- **PETSCII gotcha (the single most important finding in the whole
  project):** Meatloaf **actually converts to lowercase** HTTP text
  content received via `GET#` — not a display quirk, a real byte
  conversion. Server sends e.g. `START`, C64 receives `start`.
  **Consequence:** every string comparison on both the client AND
  server side must tolerate this (see `session_id.upper()` on the
  server, and the doubled `="start" OR ="START"` checks in the C64
  client).
- **Joystick port: back to port 2 (2026-09-14, final) — C64-specific
  exception to the "first joystick port" convention:** both C64
  clients read the joystick from port 1 (`PEEK(56321)`, CIA#1 Port B,
  `$DC01`) for a while, to consistently use "always the first joystick
  port" across platforms. But port 1 shares `$DC01` with the KERNAL
  keyboard scan (runs via IRQ 60x/sec in the background, independent
  of the BASIC program) — the theoretical "ghosting" risk was actually
  observed on real hardware on 2026-09-14 (see the PIN-entry lesson
  below: a phantom keypress corrupted the PIN prompt after a restart).
  **Fix:** both C64 clients now read the joystick from **port 2**
  again (`PEEK(56320)`, CIA#1 Port A, `$DC00`) — bit layout identical
  to port 1 (bits 0-3 = up/down/left/right, active-low), only the peek
  address changes. Port 2 shares no lines with the keyboard matrix, so
  it's ghosting-free. **Consequence:** the C64 clients (Meatloaf AND
  WiC64) are thus a deliberate, documented exception to the "same
  joystick port on every platform" convention (see pattern 7 below) —
  reliability at the exhibition takes priority over consistency. Only
  affects reading the joystick in the main loop; the PIN-entry
  validation (length/whitespace check, see below) stays in place as a
  second layer of defense.
- **`TI` is a reserved system variable** (jiffy clock) in Commodore
  BASIC — just like `PI` on the CPC (see below), it can't be used as a
  variable name. Symptom: `?SYNTAX ERROR` at a spot that, on close
  inspection, contains nothing suspicious at all. **Happened twice:**
  once originally, then again on 2026-09-12 as the `ti` loop variable
  in the typing-effect subroutine (line 4010, `tron_c64_client.bas`) —
  the WiC64 client has the same subroutine but already correctly calls
  the variable `tc` there. For new code in this subroutine (or copies
  of it), **always use `tc`, never `ti`**.
- **Unchecked join response → session mismatch (2026-09-12, found on
  real hardware):** the Meatloaf client extracted the session ID from
  the `/join` response purely by position (first space to end of
  line), without first checking whether the response actually starts
  with `SESSION`/`session` — the exact same bug already found and
  fixed once on the WiC64 client (see the WiC64 section below), but
  overlooked here in the Meatloaf client. Symptom on hardware: server
  log shows `/tick` calls with a session ID that never existed
  server-side (`current keys: []`) — looks like a case-sensitivity
  problem, but is actually an invalid/empty ID extracted from a
  response that was never recognized as a success. **Fix:** the join
  response is now checked for a `SESSION`/`session` prefix before the
  ID gets used further (short pause + retry otherwise) — mirroring the
  WiC64 fix. Preemptively applied to the CPC client at the same time,
  since it's structurally identical code (same `/join` response
  format).
- **Port-1 joystick can corrupt the PIN entry (2026-09-14, found on
  real hardware):** joystick port 1 hangs off the same CIA1 register
  ($DC01/56321) that the KERNAL keyboard scan (runs via IRQ 60x/sec in
  the background, independent of the BASIC program) uses to read the
  keyboard matrix rows. With the joystick in port 1, this can
  theoretically (see the joystick-port lesson above) produce a phantom
  keypress — a phantom cursor-up+RETURN was observed exactly during
  the `INPUT PI$` PIN prompt after a restart. The C64 screen editor
  treats the current screen line as input for the `INPUT` command: if
  the cursor lands on the already-printed prompt line ("enter your pin
  or press enter:") via a phantom keypress and a phantom RETURN fires
  there, the prompt line itself gets read in as the PIN and sent to
  `/join` (server log then shows exactly the prompt text as the PIN;
  symptom for the player: the photo fetch fails with a 404). **Actual
  steering is NOT affected** — the main loop reads the joystick via
  direct `PEEK`, never via the keyboard/screen input path (which this
  bug affects). **Fix (two layers):** (1) check `pi$` after `INPUT`
  for length (>10 chars) and whitespace, reset to `""` (→ `"NONE"`) if
  suspicious — in both `tron_c64_client.bas` AND
  `tron_c64_wic64_client.bas`. (2) Root cause fixed: both clients have
  read the joystick from **port 2** instead of port 1 since 2026-09-14
  (see the joystick-port lesson above) — avoids the line conflict
  entirely instead of just catching its symptom. The PIN length/
  whitespace check still stays in the code as a second, cheap layer of
  defense.
- **HTTP session race condition:** a `/tick` that arrives exactly at
  game end must still have time to pick up `END`+`STATS` before the
  session gets cleaned up server-side. Solution: a 15-second grace
  period after `close()`, before the session actually gets deleted
  (`HTTPPlayerConn._expire`).
- **`GET#` byte by byte:** use the byte first, THEN check `ST` (not
  the other way around) — otherwise the last byte before the
  connection ends gets lost.
- **Main loop only checked `START`/`ERR`/`END` in lowercase — client
  stayed "silent" during a running game (2026-09-20, noticed by the
  user on real hardware: no indication at all when the game started):**
  the same bug as on the WiC64 client (see there, "WiC64 main loop only
  checked START/END/ERR in uppercase") — but here on the Meatloaf
  client, which was actually considered stable. The `/join` response
  check (line 160) accepted both `SESSION`/`session` from the start,
  but the main-loop checks for `start`/`err`/`end` (lines
  320/493/495/510) only checked lowercase — if the server (or some
  intermediate step) ever does let uppercase through, the screen stays
  stuck on "waiting for opponent..." even though the game has long
  since started. **Fix:** all four spots now accept both cases,
  mirroring the WiC64 fix. **Lesson:** when porting a fix from one
  client to a structurally similar one (here: WiC64 → Meatloaf, both
  C64/HTTP-polling), always carry it to ALL affected spots, not just
  the first one found.

### Schneider/Amstrad CPC + M4 board

- **`PI` is a reserved keyword** (circle constant π) in Locomotive
  BASIC. `PI$` as a variable name produces a `Syntax error` that, when
  listed back, shows a telltale space before the `$`
  (`INPUT PI $` instead of `INPUT PI$`). General pattern in case this
  comes up again: short, unassuming variable names can collide with
  reserved words (`TIME`, `MAX`, `MIN`, `FIX`, `TAG`, `MASK`, `TEST`
  are further candidates in Locomotive BASIC).
- **`|HTTPMEM` loads into a memory buffer**, not a string variable —
  handy, since CPC strings (like C64) are limited to 255 characters.
  Pre-fill the buffer with zeros before every fetch, then scan up to
  the first null byte.
- **The "Line too long" error on load** had NOTHING to do with actual
  line length (every line was well under the ~255-character limit).
  The cause was a missing/wrong AMSDOS header when uploading via the
  M4 web interface. The eventual solution was **WinAPE's "Auto Type"**
  (types a text file in character by character, exactly like the
  Atari emulator paste) — this sidesteps the header problem entirely.

### Atari XL/XE + FujiNet

- **`N:TCP://`** (for the actual game) and **`N:HTTP://`** (for the
  ASCII-art fetch) behave **differently**, even though both go through
  the same `N:` device:
  - TCP: `AUX2=2` (CR/LF translation) is correct — confirmed over
    hundreds of test games.
  - HTTP: `AUX2` means something different there — `AUX2=0`, not `2`.
  - In HTTP mode, **no XIO 77 needed** — that was a wrong assumption on
    my (Claude's) part from too literal a reading of the docs, which
    caused error 146 ("function not supported").
  - `ST` after a `GET#` in HTTP mode is **not reliable** as a
    "finished" signal (led to endlessly printing null bytes, ATASCII
    `CHR$(0)` = heart symbol). Treating a null byte itself as the
    end-of-data signal worked reliably.
  - **Firmware version is critical:** with FujiNet firmware 1.4
    (October 2024), HTTP mode barely worked at all (always just 1
    byte, then silence). With 1.51 it worked. Official doc examples
    only match reasonably current firmware.
- **Having two different channels (`#1` for the game, `#2` for the
  image) "known" at the same time** caused error 144 when switching
  from the image to the game. Fix: use **strictly the same channel**
  for both, one after another (open, use, close, then reopen).
- **`GOTO` to restart isn't enough** — after a completed game, the
  *second* ASCII-art fetch stopped working reliably, even though the
  *first* worked flawlessly. Switching from `GOTO <restart-line>`
  (stays within the same program run) to an actual `RUN` (complete
  restart, all variables gone, apparently also a more thorough reset
  at the OS/FujiNet level) fixed it. If similar "works the first time,
  not the second" symptoms show up again: consider **`RUN` instead of
  `GOTO`** as a test.
- Atari BASIC has **no line length over ~120 characters** — split long
  compound statements (chained with `:`) across multiple lines if
  needed. Symptom: "ERROR during transfer" when uploading.

### Commodore 64 + WiC64 (newest, experimental client)

- WiC64 hangs off the **User Port** (not the serial/IEC bus like
  Meatloaf) — completely different hardware, its own protocol.
- Instead of writing custom assembly: a sample program the user
  provided (`FOTOFIX.C000`, extracted from a D64 image) already
  contains a **reusable** `SYS 49152,U$,target-address` routine that
  encapsulates the WiC64 low-level details. Instead of rebuilding
  that: **just load it and call it with our own URLs** (`archive/`
  contains the original, abandoned approach of "write our own driver
  from scratch" — don't pursue that, the approach above is more
  promising). **Author of `FOTOFIX.C000`: Andreas Beermann**
  ("andi6510", see the disk label of the original `fotofix.d64`) — the
  file now lives under `clients/c64/wic64-driver/` in the repo, see
  the README there for details/credit.
- **"USE JOYSTICK" never printed for a second player who joined via
  HTTP and got matched instantly (2026-09-20, found while porting this
  protocol to a sibling multi-game project, not yet observed as a
  player complaint on real hardware here):** the `/join` response body
  is `"SESSION <id>\n"` followed by whatever was already queued for
  that player — for a second player who gets paired immediately, that
  queued content is very commonly `START ...` itself, not `WAIT`, since
  `run_game()` already sent it before the 50ms post-`/join` sleep
  elapses. The client's "did we get a START" check (`ifleft$(r$,5)=
  "START"orleft$(r$,5)="start"then400`) tested this against `r$` as a
  whole, which at that point still starts with `"SESSION ..."` — so the
  check could never actually match, and the client fell through to
  printing `"waiting for opponent..."` even though the match had, in
  fact, already started. Steering itself was never affected (the main
  loop's joystick-read/`/tick` send doesn't depend on this flag), only
  the one status line and the `gs` flag (which then also never gets set
  to 1 later, since `START` isn't re-sent on a later `/tick` once
  already consumed here). **Fix:** extract whatever comes after the
  `"session <id>"` line into its own `rs$` right after `sn$` is
  extracted, and check `rs$` instead of `r$` for the `START` prefix —
  `tron_c64_wic64_client.bas`, build 9. **Same underlying mistake also
  affected the Meatloaf and CPC clients** (they have the identical
  `left$(r$,5)="start"`-against-the-whole-response pattern right after
  session-id extraction) — ported the identical fix to both on
  2026-09-20, see the entry further below.
- **Cause found for the "`/join` looks ok, `/tick` consistently 'ERR
  UNKNOWN SESSION'" bug (2026-09-11, not yet verified on real
  hardware):** the definitely-working reference example `fotofix.prg`
  shipped in the repo (on the same disk) calls `SYS 49152` exclusively
  with **lowercase** URLs
  (`"http://fotofix.classic-computing.de/"+id$+...`). Our WiC64 client,
  by contrast, built the join/tick URLs with **uppercase**
  (`"HTTP://"+ho$+":"+po$+"/JOIN/..."` and `"/TICK/..."`). On top of
  that, the session-ID extraction didn't check whether the response
  actually started with `SESSION` — on an error response (e.g. the
  server returning `"ERR UNKNOWN REQUEST"` if the path's uppercase
  confused it), the text after the first space was simply taken as the
  supposed session ID. That explains the impression that "`/join`
  worked" (`r$` wasn't empty, looked like an ID), even though in truth
  no valid session existed — every subsequent `/tick` was then bound
  to fail. **Fix in `tron_c64_wic64_client.bas`:** all URLs (join,
  tick, ASCII-art fetch) switched to lowercase (matching
  `fotofix.prg`); the join response is now checked for a
  `SESSION`/`session` prefix before the session ID gets used further
  (short pause + retry otherwise); added debug output on `/tick`
  errors (shows `r$` and `sn$` on screen), mirroring the join debug
  print that already existed. **Next step:** test on real hardware —
  if the `/tick` problem persists, the new debug output at least shows
  the raw server response now instead of guessing in the dark.
- Load trick: after `LOAD"fotofix.c000",8,1`, the BASIC program stops
  (standard behavior for `LOAD` from within a running program, even if
  the load fails — a `FILE NOT FOUND` is a normal BASIC runtime error
  and stops it just the same). The classic trick to work around this:
  `POKE631,82:POKE632,85:POKE633,78:POKE634,13:POKE198,4` (writes
  "RUN"+Return into the keyboard buffer) right before the `LOAD`.
  Detecting "is the driver already loaded" via `PEEK(49152)=32` (first
  byte of the routine — a normal BASIC variable wouldn't survive a
  `RUN`).
- **`petcat` tokenizes uppercase letters in string literals as
  "shifted" PETSCII (128+), not the expected unshifted PETSCII — this
  breaks `LOAD`/`SAVE` filenames (2026-09-14, found on real hardware,
  confirmed by byte comparison against the actual disk directory):**
  the old assumption "text content in quotes stays untouched, whatever
  the case" (see below) turns out to be **not quite right** — it only
  holds for text displayed AFTER switching to the lowercase character
  set (`CHR$(14)`) (there, the "shifted" codes 193-218 actually render
  as readable uppercase letters). For anything relying on EXACT byte
  values — first and foremost a `LOAD`/`SAVE` filename compared
  1:1 against the disk directory entry — it's wrong:
  `tron_c64_wic64_client.bas` wrote `LOAD"FOTOFIX.C000",8,1`
  (uppercase in the source), and petcat tokenized that to byte values
  198,207,212,207,198,201,216,... (= letter+128), while the actual
  disk directory (verified via `c1541 -dir` and directly parsing the
  D64 directory sectors) stores the filename with the PLAIN/unshifted
  values 70,79,84,79,70,73,88,... Result: `LOAD` NEVER finds the file
  — the same byte values also render as graphics symbols instead of
  text in the default character set (still active at `LOAD` time,
  BEFORE the `CHR$(14)` switch), hence the impression of "garbage on
  line 30" when `LIST`ing. **Symptom during testing:** the driver's
  auto-load fails, affected users had to type the `LOAD` command
  manually at the READY prompt before they could start the main
  program — and since the driver then NEVER loads automatically on a
  regular basis, subsequent `SYS49152` calls stay ineffective on a
  cold start (client "connects" but then visibly does nothing
  further). **Fix:** ALWAYS write `LOAD`/`SAVE` filenames in lowercase
  in the source (`"fotofix.c000"` instead of `"FOTOFIX.C000"`) — that
  produces the unshifted byte values matching the disk directory.
  Confirmed via a petcat test run: the tokenized bytes of
  `"fotofix.c000"` exactly match the real directory bytes from
  `fotofix.d64`.
- **`petcat` wants commands/variable names in lowercase** — otherwise
  tokenization errors. Plain display text in quotes (printed AFTER the
  `CHR$(14)` character-set switch) may stay in whatever case you want
  it displayed in — **exception: filenames for `LOAD`/`SAVE` still
  have to be lowercase**, see the lesson directly above.
- **WiC64 main loop only checked `START`/`END`/`ERR` in uppercase —
  client stayed "silent" during a running game (2026-09-14, found on
  real hardware):** the join-response check accepted both `SESSION`
  and `session` from the start (see the fix entry above), but the main
  loop (`tron_c64_wic64_client.bas`, checks for `START`/`END`/`ERR`)
  only checked uppercase. Since the exact same driver/connection has
  demonstrably also been converting outgoing text to lowercase (see
  the fix above — server log shows incoming requests consistently
  lowercase, even though the client code uses uppercase), it's very
  likely that incoming server responses also arrive lowercase — the
  pure uppercase comparisons would then NEVER have matched. Symptom on
  hardware: client connects, shows "waiting for opponent...", but even
  after a second player joins and the match runs/ends server-side, the
  screen stays unchanged (no "use joystick", no "game over") — server
  log meanwhile shows endless `/tick` polling with direction `n` long
  past game end. **Fix:** the `START`/`END`/`ERR` checks in the main
  loop now accept both cases, mirroring the `SESSION`/`session`
  pattern already in place for the join response.
- **Instant-START join-response fix (see the entry further above)
  ported to Meatloaf and CPC (2026-09-20):** the same
  `left$(r$,5)="start"`-against-the-whole-response bug (found on the
  WiC64 client while porting the protocol to a sibling project) was
  confirmed present, byte-for-byte identical, in both
  `tron_c64_client.bas` (Meatloaf, build 17) and
  `tron_cpc_client.bas` (CPC, build 6) — both extract the session ID
  from `r$` with the exact same `ss`/`se` loop, then immediately check
  `START` against `r$` itself instead of what comes after the session
  line. **Fix, mirroring the WiC64 build-9 change exactly:** extract
  `rs$` (whatever follows the `"session <id>"` line) right after
  `sn$`, check `rs$` instead of `r$` for the `START` prefix. Meatloaf
  bumped to build 18, CPC to build 7. `client.prg` (Meatloaf) rebuilt
  via `petcat -w2`; the CPC client still needs the WinAPE/M4 upload
  step done manually. Not yet re-verified on real hardware — next
  hardware test should specifically try pairing two players who join
  back-to-back (the failure only shows for the second player when the
  match starts before their post-`/join` sleep elapses).
- **"`/join` ok, `/tick` = 'ERR UNKNOWN SESSION'" bug:** see the fix
  entry further above (uppercase URLs + missing prefix check on the
  join response) — still to be verified on hardware.
- **Still open:** whether `SYS 49152` is just as reliable for very
  frequent, repeated polling (our `/tick` polling, many calls per
  second) as for the rare single calls the original program was
  designed for — if the fix above doesn't fully solve the problem,
  tackle this next (e.g. test pacing/delay between `/tick` calls).
  - **First measurement (2026-09-19):** at least partially answers the
    question above — with the new `[tick-latency]` logging (see
    `HTTPPlayerConn.last_tick_at` in `server/tron_server.py`), the time
    between consecutive `/tick` calls from the WiC64 client (VICE
    emulator, opponent was a real TCP bot on the Atari side, not
    another bot) sat consistently at **1272–1290 ms** — at
    `TICK_RATE=8` (125 ms/tick) that's roughly **10 server ticks per
    WiC64 input**. The tight spread (only ~18 ms variance) points more
    towards a fixed, deterministic overhead in the WiC64
    protocol/driver (User-Port handshake with the ESP module) than
    plain network jitter. **Test environment:** Ubuntu Linux, Intel
    i5, 16 GB RAM, VICE compiled from git source itself (not verified
    on real WiC64 hardware — the emulator could time this
    differently/more slowly than real hardware). **Takeaway:** do NOT
    lower `TICK_RATE` globally because of this — that would slow the
    game down for every platform, Atari most of all with practically
    no input latency, without actually making WiC64 competitive.
    WiC64 stays the experimental bonus client, Meatloaf stays the
    reliable standard C64 client for CC2026.
  - **Comparison measurement, Meatloaf (2026-09-19, real game against
    `bots/tron_bot.sh`):** steady state of **294–306 ms** per `/tick`
    — roughly **4x faster than WiC64** (~1280 ms), but still a good
    **2.4x slower than `TICK_RATE=8`** (125 ms/tick) — so even the
    "reliable" HTTP-polling client only gets a new input through
    roughly every 2-3 server ticks, not every one. An outlier of
    1444 ms was observed — meanwhile recognized (see "Reproducible
    latency outlier" further below) as a recurring, well-explained
    pattern, not chance. Confirms: HTTP polling generally has a
    noticeable latency floor compared to Atari's raw TCP, but that's
    apparently acceptable for Meatloaf (the client is considered
    stable after many real games) - WiC64's ~1280 ms is a whole
    different order of magnitude.
  - **Comparison measurement, CPC/M4 (2026-09-19, REAL HARDWARE - not
    an emulator):** steady state of **542–559 ms** per `/tick`
    (solo test) resp. **543–551 ms** (in the subsequent real game
    against the Meatloaf client, see below) — sits between Meatloaf
    (~300 ms) and WiC64 (~1280 ms), roughly **1.8x slower than
    Meatloaf**, but **2.3x faster than WiC64**. At `TICK_RATE=8`
    (125 ms/tick) that's roughly **4.4 server ticks per CPC input**.
    Plausibly explained by the `|HTTPMEM` property already documented
    in `CLAUDE.md` of blocking all other processing during the call.
    Here too, an outlier (1095 ms instead of ~550 ms) was observed in
    a later game, same picture as the Meatloaf outlier above — also
    part of the reproducible pattern documented below.
  - **Ranking after this first round of measurements (fastest
    first):** Atari (raw TCP, practically zero delay) < Meatloaf
    (~300 ms, ~2.4 ticks) < CPC/M4 (~550 ms, ~4.4 ticks) < WiC64
    (~1280 ms, ~10 ticks). All three HTTP-polling values sit well
    above `TICK_RATE`'s 125 ms, and the game still works reliably
    after many games regardless - still an argument against changing
    `TICK_RATE` in response (see the takeaway above).
  - **`TICK_RATE` changed 8 -> 4 (125ms -> 250ms/tick) on 2026-09-20,
    revising the takeaway above:** discussed with the user - unlike
    lowering it to accommodate WiC64's ~10x outlier (still not worth
    it, see above), this is a moderate adjustment targeted at the two
    platforms actually fielded at the event. `TICK_RATE` doesn't
    change each platform's network round-trip time, but it does
    change how many wrong-direction grid cells get travelled during
    that fixed latency window - a real, spatial fairness effect, not
    just cosmetic. At 250ms: Meatloaf's ~295ms drops from ~2.4 to
    **~1.2 ticks** behind (nearly every tick gets a fresh input, close
    to Atari's feel), CPC's ~500ms drops from ~4.4 to **~2.0 ticks**
    behind. Trade-off: the whole board now moves at half the previous
    speed for every platform, Atari included - possibly a wash or even
    a plus for a public exhibition, since a slower-paced duel is
    likely easier for a crowd around a projector to follow. Not yet
    playtested at the new setting - if it feels too sluggish (or CPC
    still feels outmatched), reconsider a value between 125ms and
    250ms rather than reverting outright.
  - **First real-hardware crossplay smoke test (2026-09-19) —
    CORRECTION, not an actual gameplay test:** CPC/M4 vs. C64/Meatloaf,
    both on real hardware, ended with "draw (simultaneous crash)"
    after ~7 seconds. **Important caveat (clarified afterwards by the
    user):** both clients ran with NO joystick connected (joysticks +
    upscaler weren't there yet at test time, both "on the way") — so
    neither player ever actually moved (`STICK`/`PEEK` constantly
    reads "no input", server gets direction "N" throughout), the
    "draw" presumably just came from the countdown/game logic running
    its course on both sides simultaneously, not from real steering.
    **What it does show, regardless:** pairing, the `/join`+`/tick`
    protocol, latency measurement, and the end-of-game flow all work
    end-to-end on real hardware for both platforms at once - that was
    still useful. **What it does NOT show:** whether steering via
    joystick actually works on both platforms, and what a *real* duel
    (incl. collision avoidance/detection under active steering) feels
    like. This pairing from the test checklist
    (`docs/hardware_test_checklist.pdf`, section 5) therefore still
    counts as open, once joysticks + the upscaler arrive.
    **Update (2026-09-20): joysticks have arrived, now genuinely
    verified** — see the following two entries.
  - **Reproducible latency outlier, always the 2nd `/tick` after
    `GAME START` (2026-09-20):** across four real matches (CPC vs.
    Atari, CPC vs. Meatloaf x3), the same outlier from the
    measurements above turns out not to be chance but a reproducible
    pattern: **always exactly the second logged `/tick` latency after
    the `GAME START` header** sits well above the usual steady state
    (e.g. CPC 917/883/895 ms instead of ~550 ms; C64 1490 ms instead
    of ~350 ms in one of the matches) — doesn't always affect the same
    platform, but apparently whoever happens to be polling during the
    window in question shortly after game start. One obvious cause was
    checked and ruled out: the visitor-photo fetch
    (`resolve_photo`/`fetch_photo_blocking`) already correctly runs
    via `run_in_executor` on a separate thread, so it doesn't block
    the event loop. Actual cause still open (suspect: something in the
    countdown transition in `run_game()` - the 3-2-1 countdown +
    "Go, get in there!" pause), but not critical: happens exactly once
    per match, always before the player is actually steering (during
    the countdown/shortly after), every tick *during* the actual duel
    stays stable at the steady state. Don't chase this before CC2026
    unless it suddenly also shows up mid-game.
  - **First REAL hardware crossplay test with steering (2026-09-20):**
    with joysticks connected, several real matches of CPC/M4 vs. Atari
    and CPC/M4 vs. C64/Meatloaf were played (each multiple times) -
    both sides visibly steered (`[move]` log entries on both
    platforms), results alternated between both sides (no one-sided
    advantage apparent). Also confirms on real hardware at the same
    time: the 2026-09-20 Meatloaf fix (`START`/`ERR`/`END` case
    handling) holds - "USE JOYSTICK" now shows up reliably at game
    start. This means the pairings **Atari vs. CPC** and **C64
    (Meatloaf) vs. CPC** from the test checklist (section 5) are now
    verified with real steering.

## UI simplification of all clients (2026-09-12)

After the 2026-09-12 Meatloaf hardware test (see the session-mismatch
finding above) — which also showed that the ASCII-art display wasn't
rendering correctly on the C64 — all four clients
(`tron_atari_client.bas`, `tron_c64_client.bas`,
`tron_c64_wic64_client.bas`, `tron_cpc_client.bas`) were deliberately,
radically simplified:

- **Removed, in all four clients:**
  - The ASCII-art digitization of the visitor photo (subroutine `3000`
    per client, including the HTTP/`|HTTPMEM`/`SYS49152` fetch of
    `ascii-terminal.txt`).
  - The character-by-character "terminal typing effect" for printed
    text (subroutine `4000` per client).
  - The MCP storyline (`"MCP:> ..."` texts like "WELCOME TO THE GRID",
    "MASTER CONTROL PROGRAM SEARCH PHOTO", "YOU'VE GRANTED ACCESS...").
- **What's left is terse, purely functional text output** (direct
  `PRINT`, no more detour through `tx$`+`GOSUB`): PIN prompt
  (`"ENTER YOUR PIN OR PRESS ENTER:"`), connecting
  (`"CONNECTING..."`), waiting for an opponent
  (`"WAITING FOR OPPONENT..."`), joystick hint (`"USE JOYSTICK"`),
  game end + result (`"GAME OVER"` + the raw server response line),
  and restart (`"RESTARTING..."`).
- **Not affected:** the server-side photo feature (visitor photo in
  the pygame side panel) is unchanged — that's entirely server-side
  (`fetch_photo_ftp_blocking`/`fetch_photo_http`) and independent of
  the now-removed client-side ASCII preview. The PIN is still passed
  to `/join` resp. `HELLO` completely normally.
- **Why:** less code per client means less surface area for exactly
  the kind of bugs that have cost this project the most time so far
  (see the lessons above) — and a broken digitization screen is worse
  at an exhibition than no digitization screen at all.

## General, cross-platform patterns

1. **Reserved variable names are a recurring trap.** ALWAYS check
   short variable names (2-3 letters) against the respective BASIC's
   reference before using them — `PI` (CPC), `TI` (C64) were both
   exactly this kind of bug, with the same symptom pattern (syntax
   error at an unremarkable spot).
2. **Never assume case for network text.** Both Meatloaf and WiC64
   (via the Fotofix routine) transform text when sending/receiving.
   Always keep server-side comparisons case-insensitive (`.upper()`).
3. **String length limit on 8-bit BASIC (255 characters)** — never
   accumulate a complete HTTP response into a string variable if it
   could potentially get large (e.g. the ASCII art). Process it
   character by character from memory instead.
4. **On "works once, then not again" symptoms**: suspect an
   incompletely reset connection/device state after reusing a
   channel/connection. Best solutions found so far: either use the
   same channel strictly sequentially, or (the Atari case) do a
   complete `RUN` restart instead of `GOTO`.
5. **For every new failure mode: create visibility first, then
   guess.** Diagnostic output (error code, raw response, byte count)
   has led to a solution faster in almost every case than a second or
   third guess without new data.
6. **Check BASIC line-number consistency after every change** (no
   duplicates, ascending, no line over the respective platform limit —
   Atari ~120 characters, C64/CPC considerably more relaxed). A small
   Python script for this is worthwhile, see the example below.
7. **Convention: all clients use the first joystick port of their
   computer — with one deliberate, documented exception for the C64.**
   Atari (`STICK(JSPORT)` with `JSPORT=0`) and CPC (`JOY(0)`) have
   correctly used their respective first port from the start. The C64
   (Meatloaf AND WiC64) was switched to port 1 (`PEEK(56321)`/`$DC01`)
   as a trial, then reverted to **port 2** (`PEEK(56320)`/`$DC00`) on
   2026-09-14 — port 1 shares lines with the keyboard matrix and
   produced real phantom keypresses on real hardware (see the
   joystick-port lesson and the PIN-entry lesson above). For the C64,
   reliability at the exhibition takes priority over pure port-number
   consistency across platforms.

```python
# Quick BASIC line-number consistency check
with open("file.bas") as f:
    lines = f.read().splitlines()
nums = [int(l.split()[0]) for l in lines if l.strip() and l.split()[0].isdigit()]
assert len(set(nums)) == len(nums), "Duplicates!"
assert all(nums[i] < nums[i+1] for i in range(len(nums)-1)), "Not ascending!"
```

## Transferring clients to the target systems

How the `.bas` source code actually ends up on each retro computer
(a workflow the user tested themselves, not obvious from the code):

### Atari (FujiNet)

Install FujiNet + Altirra on a PC. Copy a disk with the N: device onto
the simulated SD card via FujiNet and boot from it. In the BASIC
interpreter, the program can be pasted in via right-click ("Paste"),
then saved. Transfer the finished disk image to the FujiNet's real SD
card afterwards.

#### Automation alternative: editing `.atr` images directly (not yet tested)

The approach above (Altirra paste) is meant for individual, manual
transfers. For an automated script/pipeline setup on Ubuntu, there are
several command-line tools that can edit `.atr` images directly —
normal Linux tools like `mtools` do NOT work here, because Atari
filesystems (DOS 2.0, DOS 2.5, MyDOS, SpartaDOS) aren't FAT:

- **[atrfs](https://github.com/pcrow/atari_8bit_utils)** — mounts an
  `.atr` image via FUSE as a normal Ubuntu directory (no root needed),
  after which normal `cp`/file manager use works:
  ```
  mkdir ./atari_disk
  atrfs --name=game_disk.atr ./atari_disk
  cp myprog.bas ./atari_disk/
  fusermount -u ./atari_disk
  ```
  Fully supports DOS 2.0/LiteDOS, MyDOS/SpartaDOS with limitations.
- **franny** — command-line tool for listing/extracting/inserting
  without mounting, suitable for scripts among other things:
  `franny -l image.atr` (list contents), `franny -g image.atr
  ATARIFILE.BAS localfile.bas` (extract), `franny -a image.atr
  localfile.bas ATARIFILE.BAS` (insert). Can also create new blank
  images.
- **[atari-tools](https://github.com/jhallen/atari-tools)** by Joseph
  Allen — builds quickly via `make`, produces an `atr` binary:
  `atr image.atr ls` (list), `atr image.atr put file.txt` (insert).
- **GUI alternative:** Altirra has a disk explorer under System → Disk
  Drives → Select Drive → Explore, into which files can be dragged
  directly from the Ubuntu desktop (including optional line-ending
  conversion) — `atari800` (`sudo apt install atari800`) also has a
  native Linux emulator as an alternative to Altirra/Wine.

**Important for plain ASCII `.bas` text files:** the Atari expects
ATASCII line endings — a single `CR` (`\r`, ASCII 155), NOT Linux `LF`
(`\n`) or Windows `CRLF` (`\r\n`). If a script-generated `.bas` file
doesn't load cleanly (`ENTER "D:MYPROG.BAS"`), convert the line
endings to `\r` with `awk`/`sed` first.

**Status:** adopted from AI research, **not yet tried** — useful as a
starting point if the manual Altirra paste ever gets replaced by a
script (e.g. for automated rollout of new client versions to multiple
FujiNet SD cards).

### Commodore 64 (Meatloaf)

Install VICE — it includes `petcat`, which stores a text file as
tokens: `petcat -w2 -o OUT.PRG -- IN.TXT` (`xyz.bas` becomes
`xyz.prg`). Then upload it to the flash storage via the Meatloaf web
interface.

**Watch out:** an HTTP call from within BASIC apparently changes the
destination directory for device 8. Reset it with `LOAD"CD^",8`
(up-arrow character, PETSCII `$5E`), then `LOAD"$",8` — after that,
everything's back to normal.

### Schneider/Amstrad CPC (M4)

A special case because of the AMSDOS header (see also the "Line too
long" lesson above). Workflow: start WinAPE, create and format a new
disk, paste the BASIC program into the emulation, save it to the
virtual disk. Then copy that disk onto the M4's SD card via the M4 web
interface, select it there, and start the program via browser on the
CPC.

Known limitation: during an `|HTTPMEM` call (CALL to the HTTP page),
all other processing (in particular joystick polling) is blocked —
game feel on the CPC is noticeably less smooth than on the other
platforms as a result. A reduced buffer helps a little, but the limits
remain clearly noticeable.

#### Possibly simpler route: `MERGE` instead of the WinAPE detour (not yet tested)

The WinAPE detour above is necessary because a **tokenized** BASIC
file (a normal `SAVE"file"`) needs a correct 128-byte AMSDOS header,
which the M4 web interface doesn't generate on its own when uploading
a raw text file (see the "Line too long" lesson above). There is,
however, a possible way to sidestep this header problem entirely by
not needing a tokenized file at all:

- The CPC can read and execute a **raw ASCII text file** (equivalent
  to `SAVE"file",A`) directly — with no tokenization/header at all —
  via the `MERGE` command:
  ```
  NEW
  MERGE "filename.txt"
  RUN
  ```
  `MERGE` reads the text file in line by line exactly as if it were
  being typed in by hand (similar to WinAPE's "Auto Type"/Atari paste,
  just handled directly by the CPC interpreter instead of the
  emulator).
- Alternative to that, as a pure line read with no BASIC
  interpretation:
  ```
  OPENIN "filename.txt":LINE INPUT #9,a$:CLOSEIN
  ```
- **Why this is particularly interesting for the M4:** the M4 board
  exposes the SD card as a normal FAT32 filesystem — `MERGE` needs no
  `.DSK` image. The generated `.bas`/`.txt` file could therefore be
  copied straight onto the SD card; made visible on the CPC with
  `|DIR`, then loaded via `MERGE "filename.txt"` — potentially
  entirely without the WinAPE/emulator detour.
- If a direct `RUN"filename"` without a prior `MERGE` is wanted after
  all: a 128-byte AMSDOS header can also be prepended to the text file
  afterwards via a command-line tool (e.g. `2cpc`, `cpcfs` with
  `-t 0`/`-t 1` when importing into a `.DSK` image) — but that makes
  the file-by-file handling more complicated again than the `MERGE`
  route above.

**Status:** adopted from AI research, **not yet verified on real M4
hardware** — if it works, it makes the WinAPE detour unnecessary when
transferring new client versions. Worth trying with a small test file
before the next hardware test, before running the whole client code
through it.

## Testing without real hardware

For the server, there's a minimal `pygame` stub (in the original
sandbox environment under `/home/claude/faketest/pygame_stub/`) that
lets the server run headless and be driven through end-to-end tests
via a raw TCP socket (Python's `socket` module) (send HELLO, wait for
WAIT/START, etc.), without needing an actual pygame window. This stub
is NOT part of this repo (it was just a sandbox helper) — easy to
rebuild yourself if needed (see `pygame.font`, `pygame.init`,
`pygame.display` as the minimal surface to stub).

For the BASIC clients, there's no way to test meaningfully without an
actual emulator (Altirra/Fujisan for Atari, VICE for C64, WinAPE/CPCEmu
for CPC) — every change to a `.bas` client should at least be checked
for line-number consistency before shipping (see above); real
functional testing is only possible via emulator/hardware, by the
user.

**State of emulator testing per platform (from user experience):**

- **Atari:** Fujisan 2.0.5beta on Linux works reliably as a test
  environment for the FujiNet client. The same setup does **not** work
  on Windows — cause unknown so far, not yet investigated.
- **C64 (WiC64):** VICE can emulate the WiC64 client, i.e. the
  experimental WiC64 client can be tested **without real hardware**
  using it — especially useful since WiC64 hardware is rarely
  available.
- **CPC (M4):** CPCEmu simulates an M4 interface, but this is **not
  tested yet** — status unclear, could serve as a next step for
  hardware-free CPC testing.
- **Packing BASIC programs into a D64 image** (for C64 tests, e.g.
  with VICE): [d64-inspector](https://github.com/pdbuchan/d64-inspector)
  (author: P. David Buchan, GPLv3) has proven useful for this — no
  longer bundled in the repo (see [`tools/README.md`](./tools/README.md)
  for download/build links, including the
  [C64 TrueType](https://style64.org/c64-truetype) font family needed
  for the PETSCII view, author: "Style"). Ready-made reference disk
  images (incl. for Atari/CPC) live under
  [`disk-images/`](./disk-images/), see the README there.

### Simulating the photo/FTP infrastructure locally

Without the real event photo server, `PHOTO_SOURCE = "FTP"` can be
tested locally with a simple FTP server (started from the images
directory):

```bash
# Linux
sudo python -m pyftpdlib -p 21
# Windows
python -m pyftpdlib -p 21
```

Visitor PINs already used for testing: `0001`, `0002`, `4711`, `0815`.

**Ready-made test fixture:** [`assets/test_ftproot/`](./assets/test_ftproot/)
contains a demo photo (`photo.jpg`) and an ASCII-art file
(`ascii-terminal.txt`) under PIN `MUSTER`, downloaded from the real
`fotofix.classic-computing.de` server. `ascii-terminal.txt` hasn't
been fetched by any client since the 2026-09-12 client simplification,
but stays in place as a fixture (harmless, minimal upkeep). Just start
the pyftpdlib command above from `assets/test_ftproot/` and test with
PIN `MUSTER`, instead of setting up your own test images.

## Ideas for later

- **Consider `pygame` → `pygame-ce`/`pygame-ng`:** classic `pygame` is
  unmaintained; a community fork would bring more current
  maintenance/fixes. No urgent need to act, but keep it in mind for
  bigger server changes.
- **Sound effects from the Tron movie (1982):** a few short audio
  clips (bit-style "yes"/"no", MCP-style lines) are ready locally for
  possible later integration (e.g. as sound effects in the server at
  game start/end). **Deliberately not added to the repo/git** — these
  are excerpts from copyrighted film material (Disney), which should
  be deliberately weighed again before any use/publication, especially
  if the repo is ever hosted publicly.
- **Fourth platform: Apple II via FujiNet (only if time is left at the
  end):** FujiNet officially also supports Apple II/III, with the same
  `N:` network-device concept as the Atari, including raw TCP —
  method 1 (port 6502) should therefore apply directly, with no server
  change (see the "Extending to further retro computers" section
  above). No Apple II in the project's own hardware collection so far,
  first test planned via the "FujiNet Go" emulator on phone/tablet —
  purely a nice-to-have idea, no priority before CC2026.
  Quickstart: <https://github.com/FujiNetWIFI/fujinet-firmware/wiki/Apple-II-&-III-FujiNet-Quickstart-Guide>
  - **A first client draft already exists:**
    [`clients/apple2/tron_apple2_client.bas`](./clients/apple2/tron_apple2_client.bas)
    — **completely unverified, never run**, neither on real hardware
    nor in an emulator. Unlike the Atari client (CIO
    `OPEN`/`PRINT#`/`INPUT#`), networking on the Apple II runs through
    FujiNet-specific Applesoft "ampersand" routines
    (`&NOPEN`/`&NREAD`/`&NWRITE`/`&NCLOSE`/`&NSTATUS`), which first
    have to be loaded via `BLOAD /FUJI.APPLE/FUJIAPPLE` + `CALL 16384`.
    No complete working TCP example program could be found on the
    FujiNet wiki (pages "Applesoft Network extensions" and "N: SIO
    Command 'R' — Read") — the client is built from the plain
    parameter reference, not from a confirmed example. **Known open
    points, to keep in mind before the first test run:**
    - Whether `&NREAD`/`&NWRITE` block or return immediately isn't
      specified in the docs — the client follows the recommended
      pattern of "always check `&NSTATUS` for bytes-waiting first,
      only then `&NREAD` that exact byte count" (the docs explicitly
      warn of an error if more bytes are requested than are actually
      waiting).
    - How a failed `&NOPEN` (e.g. server unreachable) makes itself
      known is unknown — no Applesoft `ONERR GOTO` error handling
      built in yet (unlike the `TRAP`-based one on the Atari client).
    - `PDL(0)`/`PDL(1)` for joystick reading: center (`CX`/`CY`) and
      deadzone (`DZ`) are placeholders (128/40) at the top of the
      client — real paddle/joystick hardware tends to need
      per-device calibration.
    - Applesoft historically only distinguishes variable names by
      their first two characters — the PIN-entry variable was
      deliberately named `PN$` (not `PIN$`), since `PI` is a reserved
      keyword in Applesoft (circle constant, the same trap as on the
      CPC, see pattern 1 above).
    - Server-side, `"APPLE2"` is already registered in
      `PLATFORM_COLORS`/`LOGO_NAME_CANDIDATES` in
      `server/tron_server.py` (amber trail color), no
      `assets/logos/apple2.*` image exists yet.
- **Fifth platform: TI-99/4A via PicoPEB (also only if time is left
  over):** PicoPEB is a DIY recreation of the TI Peripheral Expansion
  Box based on a Raspberry Pi Pico W, and among other things emulates
  an RS232 device with a plain client TCP socket (`PI.TCP=...` in
  `autoload.cfg`) — addressed from TI BASIC/Extended BASIC via
  `OPEN #1:"RS232/2..."` (or the `PI.TCP` variant) and
  `PRINT #1:`/`INPUT #1:`, in principle like the Atari's serial `N:`
  device. Would therefore also map onto method 1 (raw TCP, port 6502),
  with no server change. The exact `OPEN` syntax for the TCP client
  socket wasn't fully specified in the available docs — pure hands-on
  discovery on real hardware, like every platform so far. Additional
  hurdles: PicoPEB is a solder-it-yourself board (incl. SMD parts),
  stock TI BASIC is slow/string-limited (an Extended BASIC module is
  probably needed), and there's no TI-99/4A in the project's own
  hardware collection — purely a nice-to-have idea, no priority before
  CC2026. Docs: <https://github.com/hexbus/ppebcr-docs>

## Current status (see also git log for details)

- **Server**: stable, tested in production use over many games.
- **All four clients** (Atari, C64/Meatloaf, C64/WiC64, CPC): radically
  simplified on the UI side on 2026-09-12 — ASCII-art display,
  terminal typing effect and MCP storyline removed, see the "UI
  simplification of all clients" section above. C64/Meatloaf and
  CPC/M4 re-verified on real hardware after the simplification on
  2026-09-19 (see directly below); Atari and C64/WiC64 still have
  that ahead of them.
- **Atari client**: stable so far (before the simplification).
  Confirmed on 2026-09-20 in several real, steered cross-platform
  matches against the CPC client (see below).
- **C64 client (Meatloaf)**: session-mismatch bug (unchecked join
  response) found and fixed on real hardware on 2026-09-12.
  Re-verified on real hardware on 2026-09-19 (`/tick` latency
  ~300 ms, see the comparison measurement in the WiC64 section above)
  - the fix holds. The further case-sensitivity fix from 2026-09-20
  ("main loop only checked START/ERR/END in lowercase", see the
  Meatloaf section above) confirmed the same day in several real,
  steered cross-platform matches against the CPC client - "USE
  JOYSTICK" now shows up reliably.
- **CPC client**: stable so far (before the simplification); got the
  same join-response fix as the Meatloaf client as a precaution.
  Verified on real hardware after the simplification on 2026-09-19
  (`/tick` latency ~550 ms, see the comparison measurement above). On
  2026-09-20, now with joysticks connected, several real steered
  cross-platform matches played against Atari and against Meatloaf -
  results alternated between both sides, no one-sided disadvantage
  apparent despite the differing `/tick` latency. See "First REAL
  hardware crossplay test with steering" in the WiC64 section above.
- **C64 client (WiC64)**: experimental, no physical hardware available
  (see "Ideas for later"/test checklist). The game connection
  (`/join`/`/tick`) had a bug (URL uppercase + missing response
  check), fixed on 2026-09-11. Played successfully in the VICE
  emulator against a TCP bot on 2026-09-19 (works in principle) - but
  a `/tick` latency of 1272–1290 ms was measured in the process, see
  the detail entry in the WiC64 section above. Still not verified on
  real WiC64 hardware.
