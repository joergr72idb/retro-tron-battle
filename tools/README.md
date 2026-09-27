# Tools

## Own diagnostic/test programs

Small, isolated `.bas` test programs, written while narrowing down
platform quirks (see `CLAUDE.md`) - not part of the actual game, but
useful as a starting point for similar diagnostics on a new platform:

- `atari_http_test.bas` - isolated FujiNet `N:HTTP` test
- `atari_joystick_test.bas` / `joystick_network_test.bas` - Atari joystick
  port tests (standalone and with networking, respectively, see below)
- `c64_joystick_test.bas` - standalone joystick test for C64, shows port 1
  ($dc01) and port 2 ($dc00) live at the same time, to directly visualize
  the keyboard-scan ghosting problem (see `CLAUDE.md`)
- `cpc_joystick_test.bas` - standalone joystick test for Schneider CPC
  (`JOY(0)`, raw + decoded)
- `meatloaf_netztest.bas` - isolated Meatloaf HTTP test
- `meatloaf_latency_probe.bas` - compares per-tick fresh open/close
  (device 8, sec.addr. 3, today's client method) against one open +
  reused channel (sec.addr. 2, Meatloaf's full HTTP client protocol)
  over N requests each, timed via the jiffy clock - written to check
  whether connection reuse is worth adopting for lower `/tick` latency
  before committing to a protocol change (see `CLAUDE.md`)

## Build helpers

- `cpc_dsk_put.py` - writes a `.bas` source onto a CPC `.DSK` image
  (WinAPE DATA format) as a headerless ASCII file, replacing an existing
  file of the same name - used to refresh `disk-images/cpcclient.dsk`
  (see `disk-images/README.md`)

## External tools (no longer bundled in the repo)

Local copies of the following two third-party tools used to live here;
to keep the repo small, they're now just linked - download from there
yourself if needed:

### d64-inspector

GTK4 program for inspecting/editing D64 disk images (see `CLAUDE.md`,
section "Testing without real hardware", for packing BASIC programs
into a D64 image for VICE tests).

**Author: P. David Buchan** (pdbuchan@gmail.com), license: GPLv3.
Repo: <https://github.com/pdbuchan/d64-inspector>

**Building on Ubuntu/Debian:**

```bash
sudo apt install build-essential pkg-config libgtk-4-dev
cd d64-inspector/src
make
```

For the PETSCII view, install the C64 TrueType fonts first, see below.

### C64 TrueType

The "C64 TrueType" font family, used by `d64-inspector` for the
PETSCII view.

**Author: "Style"** (style64.org), license see the download page
(among other things: don't rename/modify, only redistribute as part
of a freely available software collection). Download/project page:
<https://style64.org/c64-truetype>
