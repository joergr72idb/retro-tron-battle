# Reference disk images

Ready-made, bootable/loadable disk images, as actually used when
setting up the real hardware for this project. The `.bas` source in
[`clients/`](../clients/) remains the authoritative source — these
images are practical starting points/reference, not a replacement for
it (may contain older client versions).

One folder per platform: `atari/`, `c64/`, `cpc/` (Schneider/Amstrad).
The client images are named `rtb.<ext>`.

## `c64/rtb.d64`

Fresh C64 disk image with the current clients: `rtb` (Meatloaf client),
`rtbwic` (WiC64 client). `rtbwic` also needs `fotofix.c000` (the WiC64
driver it loads itself) on the same disk - not included, see
[`clients/c64/wic64-driver/`](../clients/c64/wic64-driver/). Load with `LOAD"RTB",8` or `LOAD"RTBWIC",8`, then `RUN`.
Regenerate (VICE tools):

```
petcat -w2 -o rtb.prg -- clients/c64/tron_c64_client.bas
petcat -w2 -o rtbwic.prg -- clients/c64/tron_c64_wic64_client.bas
c1541 -format "retrotronbattle,26" d64 disk-images/c64/rtb.d64 \
    -write rtb.prg rtb -write rtbwic.prg rtbwic
# optionally, with a local copy of the driver:
c1541 -attach disk-images/c64/rtb.d64 \
    -write clients/c64/wic64-driver/FOTOFIX.C000 fotofix.c000
```

## `atari/rtb.atr`

Fresh Atari DOS 2.0S boot disk for FujiNet, made from `n-handler.atr`
below: `DOS.SYS`, `AUTORUN.SYS` (the `N:` handler), the FujiNet
`N*.COM`/`CONFIG`/`COPY` tools, and the current client as `RTB.LST`
(ATASCII listing; old test programs removed, their sectors zeroed).
After booting into BASIC: `ENTER"D:RTB.LST"`, then `SAVE"D:RTB.BAS"`
once, `RUN`. Regenerate the client file on it:

```
python3 tools/atr_dos2_put.py disk-images/atari/rtb.atr \
    --put clients/atari/tron_atari_client.bas RTB.LST
```

## `atari/n-handler.atr`

Atari disk image (FujiNet SD card content) with the `N:` network
handler the Atari client needs for TCP/HTTP over FujiNet, plus an
older version of the Atari client. Useful as a starting point when
setting up a new FujiNet SD card (put the handler on it, then update
the current
[`clients/atari/tron_atari_client.bas`](../clients/atari/tron_atari_client.bas)
via paste in Altirra/Fujisan) — see `CLAUDE.md`, section "Transferring
clients to the target systems".

## `cpc/rtb.dsk`

Schneider/Amstrad CPC disk image. `RTB.BAS` is the current CPC
client (build 11), stored as a headerless ASCII file - load it with
`RUN"RTB"` (AMSDOS detects ASCII automatically; loading is a bit
slower than tokenized BASIC). It is the only file on the image.
Regenerate after changing the client source:

```
python3 tools/cpc_dsk_put.py disk-images/cpc/rtb.dsk \
    clients/cpc/tron_cpc_client.bas RTB.BAS
```

## `c64/fotofix.d64` (not included)

Not included (third-party). Original disk from Andreas Beermann
("andi6510") with the FOTOFIX example program, from which
`FOTOFIX.C000` (the WiC64 driver routine) was extracted. If you have
it, keep it here locally - the path is gitignored. See
[`clients/c64/wic64-driver/README.md`](../clients/c64/wic64-driver/README.md)
for details/credit.
