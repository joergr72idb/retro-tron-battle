#!/usr/bin/env python3
"""Put a BASIC source file onto a CPC .DSK image as a headerless ASCII file.

Usage: cpc_dsk_put.py IMAGE.DSK SOURCE.bas NAME.EXT

Replaces NAME.EXT on the image if it already exists. The file is written
without an AMSDOS header, with CRLF line endings and ^Z padding - AMSDOS
treats that as an ASCII file, so LOAD"NAME" / RUN"NAME" work directly
(slower to load than tokenized BASIC, but no tokenizer needed).

Only handles the standard DATA format (sector IDs &C1-&C9, 1K blocks,
directory in blocks 0-1, 64 entries), as created by WinAPE.
"""
import sys

SECS = 9
SECSIZE = 512
BLOCK = 1024


def load(path):
    d = bytearray(open(path, 'rb').read())
    if not d.startswith(b'EXTENDED CPC DSK'):
        sys.exit('only EXTENDED CPC DSK images are supported')
    ntracks, nsides = d[0x30], d[0x31]
    if nsides != 1:
        sys.exit('only single-sided images are supported')
    sectors = {}  # (track, sector id) -> offset of sector data in d
    off = 0x100
    for tr in range(ntracks):
        size = d[0x34 + tr] * 256
        if size == 0:
            continue
        hdr = d[off:off + 256]
        p = off + 256
        for i in range(hdr[0x15]):
            info = hdr[0x18 + 8 * i:0x20 + 8 * i]
            ln = info[6] | (info[7] << 8)
            sectors[(hdr[0x10], info[2])] = p
            p += ln
        off += size
    return d, sectors


def block_offsets(sectors, blk):
    res = []
    for s in (blk * 2, blk * 2 + 1):
        res.append(sectors[(s // SECS, 0xC1 + s % SECS)])
    return res


def main():
    image, src, name = sys.argv[1:4]
    base, _, ext = name.upper().partition('.')
    fname = base.ljust(8)[:8].encode() + ext.ljust(3)[:3].encode()

    text = open(src).read().splitlines()
    data = ('\r\n'.join(text) + '\r\n').encode('ascii')
    data += b'\x1a' * (-len(data) % 128 or 128)

    d, sectors = load(image)
    ntracks = d[0x30]
    total_blocks = ntracks * SECS * SECSIZE // BLOCK
    dir_offs = block_offsets(sectors, 0) + block_offsets(sectors, 1)
    entries = [(o + 32 * i) for o in dir_offs for i in range(SECSIZE // 32)]

    used = {0, 1}
    for e in entries:
        if d[e] == 0xE5:
            continue
        if bytes(x & 0x7F for x in d[e + 1:e + 12]) == fname:
            d[e] = 0xE5  # delete old version
            continue
        used.update(b for b in d[e + 16:e + 32] if b)

    free = [b for b in range(total_blocks) if b not in used]
    nblocks = -(-len(data) // BLOCK)
    if nblocks > len(free):
        sys.exit('disk full')
    blocks = free[:nblocks]

    for i, blk in enumerate(blocks):
        chunk = data[i * BLOCK:(i + 1) * BLOCK].ljust(BLOCK, b'\x1a')
        for j, o in enumerate(block_offsets(sectors, blk)):
            d[o:o + SECSIZE] = chunk[j * SECSIZE:(j + 1) * SECSIZE]

    free_entries = [e for e in entries if d[e] == 0xE5]
    records = len(data) // 128
    for ex in range(-(-nblocks // 16)):
        if not free_entries:
            sys.exit('directory full')
        e = free_entries.pop(0)
        eb = blocks[ex * 16:(ex + 1) * 16]
        rc = min(128, records - ex * 128)
        d[e:e + 32] = (bytes([0]) + fname + bytes([ex, 0, 0, rc])
                       + bytes(eb).ljust(16, b'\0'))

    open(image, 'wb').write(d)
    print(f'{name.upper()}: {len(data)} bytes, blocks {blocks}')


if __name__ == '__main__':
    main()
