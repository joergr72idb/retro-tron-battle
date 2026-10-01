# FOTOFIX.C000 — WiC64 driver

This machine-code routine (loads to `$C000`/49152) handles the WiC64
low-level details (User Port protocol to the ESP32 module) and
provides a single reusable entry point: `SYS 49152,U$,target-address`
— fetches the URL in `U$` and writes the response byte by byte
(null-terminated) starting at the given memory address. Init first
via `SYS 50497` (see `tron_c64_wic64_client.bas`).

**Author: Andreas Beermann** ("andi6510"), originally part of a
FOTOFIX example program for Classic Computing (visitor photo + event
image retrieval via WiC64). `tron_c64_wic64_client.bas` exclusively
reuses the existing `SYS 49152` entry point — no custom WiC64
assembly routine was written, see [`CLAUDE.md`](../../../CLAUDE.md).

## File

`FOTOFIX.C000` must be on the same disk/SD2IEC image as
`tron_c64_wic64_client.bas` (same filename, loaded via
`LOAD"FOTOFIX.C000",8,1`). Extracted from the `fotofix.d64` provided
by Andreas Beermann (the original disk also contains `fotofix` — the
complete FOTOFIX example program — and `rtbwic64`, an already-typed-in
copy of our own WiC64 client for testing on real hardware). The
complete original image is at
[`disk-images/c64/fotofix.d64`](../../../disk-images/c64/fotofix.d64).

## Known error string in the routine

A `NETWORK TIMEOUT` (found as PETSCII text in the code) suggests that
on a WiC64 timeout the routine itself writes an error text to the
target memory instead of just setting `PEEK(783)` — not yet further
verified, see the open item in `CLAUDE.md`.
