#!/usr/bin/env python3
"""Edit a single-density Atari DOS 2.0S .ATR image (720 x 128 bytes).

Usage: atr_dos2_put.py IMAGE.ATR [--rm NAME.EXT ...] [--put SOURCE NAME.EXT ...]

--rm deletes files. --put adds (or replaces) a file; a .LST/.TXT target
is converted to ATASCII (EOL = $9B), so it can be loaded with
ENTER"D:NAME.LST" - everything else is copied as-is. Freed/unused
sectors are zeroed and deleted directory slots at the end of the
directory are cleared, so old file contents don't linger on the image.
The VTOC is rebuilt from the file chains afterwards.
"""
import sys

SS = 128
NSEC = 720
VTOC = 360
DIR = range(361, 369)


class Atr:
    def __init__(self, path):
        self.path = path
        self.d = bytearray(open(path, 'rb').read())
        if self.d[0:2] != b'\x96\x02' or (self.d[4] | self.d[5] << 8) != SS:
            sys.exit('only single-density ATR images are supported')
        if len(self.d) != 16 + NSEC * SS:
            sys.exit('unexpected image size')

    def off(self, n):
        return 16 + (n - 1) * SS

    def sec(self, n):
        return self.d[self.off(n):self.off(n) + SS]

    def entry(self, idx):
        return self.off(DIR[0] + idx // 8) + 16 * (idx % 8)

    def chain(self, idx):
        e = self.entry(idx)
        n = self.d[e + 3] | self.d[e + 4] << 8
        out = []
        while n:
            s = self.sec(n)
            if s[125] >> 2 != idx:
                sys.exit(f'file number mismatch in sector {n}')
            out.append(n)
            n = (s[125] & 3) << 8 | s[126]
        return out

    def live(self):
        return [i for i in range(64) if self.d[self.entry(i)] & 0x40]

    def used_sectors(self):
        used = set(range(0, 4)) | {VTOC, *DIR, NSEC}
        for i in self.live():
            used.update(self.chain(i))
        return used

    def find(self, fname):
        for i in self.live():
            e = self.entry(i)
            if bytes(self.d[e + 5:e + 16]) == fname:
                return i
        return None

    def rm(self, fname):
        i = self.find(fname)
        if i is None:
            sys.exit(f'{fname!r} not found')
        self.d[self.entry(i)] = 0x80

    def put(self, data, fname):
        if self.find(fname) is not None:
            self.rm(fname)
        free_slots = [i for i in range(64) if not self.d[self.entry(i)] & 0x40]
        if not free_slots:
            sys.exit('directory full')
        idx = free_slots[0]
        used = self.used_sectors()
        free = [n for n in range(1, NSEC) if n not in used]
        chunks = [data[i:i + 125] for i in range(0, len(data), 125)] or [b'']
        if len(chunks) > len(free):
            sys.exit('disk full')
        secs = free[:len(chunks)]
        for k, (n, c) in enumerate(zip(secs, chunks)):
            nxt = secs[k + 1] if k + 1 < len(secs) else 0
            s = c.ljust(125, b'\0') + bytes([idx << 2 | nxt >> 8, nxt & 0xFF, len(c)])
            self.d[self.off(n):self.off(n) + SS] = s
        e = self.entry(idx)
        self.d[e:e + 16] = bytes([0x42, len(secs) & 0xFF, len(secs) >> 8,
                                  secs[0] & 0xFF, secs[0] >> 8]) + fname

    def finish(self):
        used = self.used_sectors()
        for n in range(1, NSEC + 1):
            if n not in used:
                self.d[self.off(n):self.off(n) + SS] = bytes(SS)
        # clear trailing deleted slots (0 = end of directory for DOS)
        last = max(self.live(), default=-1)
        for i in range(last + 1, 64):
            e = self.entry(i)
            self.d[e:e + 16] = bytes(16)
        for i in range(last + 1):
            e = self.entry(i)
            if self.d[e] == 0x80:
                self.d[e + 1:e + 16] = bytes(15)
        v = self.off(VTOC)
        bitmap = bytearray(90)
        nfree = 0
        for n in range(NSEC):
            if n not in used:
                bitmap[n // 8] |= 0x80 >> (n % 8)
                nfree += 1
        self.d[v + 3] = nfree & 0xFF
        self.d[v + 4] = nfree >> 8
        self.d[v + 10:v + 100] = bitmap
        open(self.path, 'wb').write(self.d)


def atari_name(name):
    base, _, ext = name.upper().partition('.')
    return base.ljust(8)[:8].encode() + ext.ljust(3)[:3].encode()


def main():
    args = sys.argv[1:]
    atr = Atr(args.pop(0))
    while args:
        op = args.pop(0)
        if op == '--rm':
            atr.rm(atari_name(args.pop(0)))
        elif op == '--put':
            src, name = args.pop(0), args.pop(0)
            if name.upper().endswith(('.LST', '.TXT')):
                lines = open(src).read().splitlines()
                data = b''.join(l.encode('ascii') + b'\x9b' for l in lines)
            else:
                data = open(src, 'rb').read()
            atr.put(data, atari_name(name))
            print(f'{name.upper()}: {len(data)} bytes')
        else:
            sys.exit(f'unknown option {op}')
    atr.finish()


if __name__ == '__main__':
    main()
