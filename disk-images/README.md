# Reference disk images

Ready-made, bootable/loadable disk images, as actually used when
setting up the real hardware for this project. The `.bas` source in
[`clients/`](../clients/) remains the authoritative source — these
images are practical starting points/reference, not a replacement for
it (may contain older client versions).

## `n-handler.atr`

Atari disk image (FujiNet SD card content) with the `N:` network
handler the Atari client needs for TCP/HTTP over FujiNet, plus an
older version of the Atari client. Useful as a starting point when
setting up a new FujiNet SD card (put the handler on it, then update
the current
[`clients/atari/tron_atari_client.bas`](../clients/atari/tron_atari_client.bas)
via paste in Altirra/Fujisan) — see `CLAUDE.md`, section "Transferring
clients to the target systems".

## `cpcclient2.dsk`

Schneider/Amstrad CPC disk image with an older version of the CPC
client (AMSDOS header already set correctly, see the "Line too long"
lesson in `CLAUDE.md`). Reference for the WinAPE workflow when
creating a new M4 disk.

## `fotofix.d64`

Original disk from Andreas Beermann ("andi6510"), from which
`FOTOFIX.C000` (the WiC64 driver routine in
[`clients/c64/wic64-driver/`](../clients/c64/wic64-driver/)) was
extracted. Also contains `fotofix` (the complete FOTOFIX example
program) and `rtbwic64` (an already-typed-in copy of an earlier
version of our own WiC64 client on the disk). See
[`clients/c64/wic64-driver/README.md`](../clients/c64/wic64-driver/README.md)
for details/credit.
