#!/usr/bin/env python3
"""Borderlands 2 (Unreal Engine 3) shader records from its caches.

Ported from seedds/nxnative dm/gfx/tools/shader_split.py (MIT): ue3_package / ue3_body / ue3_shaders and the
helpers they need (CTL/GFX/CS magics, sph_stage, check, ctl_len). The record layout is documented in
nxnative docs/reference/shaders.md "Unreal Engine 3 shader caches (Oodle packages)":

  GlobalShaderCache-Switch.bin  magic BMSG, not compressed.
  CombinedShaderCache-Switch.xxx  an Unreal package (tag 0x9E2A83C1, file version 864) whose chunks hold the
  records; a block stored whole has equal compressed / raw sizes, zlib blocks start with 0x78, others are Oodle
  (needs the game's own decoder; this module refuses them with a clear message).

  one record: u32 length | u32 code-area length | u32 control length (0x880) | [global cache: one more u32]
              code area | control section

Usage:
  bl2_ue3_shaders.py report <file>...     counts by stage, first bad record reasons
  bl2_ue3_shaders.py dump <file> <outdir> writes <outdir>/<label>#UE3@<off>.<stage>.ctl / .code
"""
import hashlib
import os
import re
import struct
import sys
import zlib

CTL_MAGIC, GFX_MAGIC, CS_MAGIC = bytes.fromhex('34127698'), bytes.fromhex('78563412'), bytes.fromhex('79563412')
UE3_TAG = bytes.fromhex('c1832a9e')
SPH_STAGE = {1: 'vs', 2: 'hs', 3: 'ds', 4: 'gs', 5: 'ps'}


def red(msg):
    sys.exit('[RED] ' + msg)


def span(d, at, n, where):
    if not (0 <= at and 0 <= n <= len(d) - at):
        red(f'{where}: {n:#x} bytes at {at:#x} lie outside the {len(d):#x} bytes there are')
    return d[at:at + n]


def sph_stage(code):
    """A graphics code area's stage from its SPH word 0 (bits 10..13)."""
    if len(code) < 0x34:
        return None
    w = struct.unpack_from('<I', code, 0x30)[0]
    return 'vs' if (w >> 10) & 0xf == 0 and w & 0x1f == 1 else SPH_STAGE.get((w >> 10) & 0xf)


def ctl_len(ctl):
    n = struct.unpack_from('<I', ctl, 0x20)[0]
    return n if 0x760 <= n < 0x880 else 0x880


def check(where, st, ctl, code):
    """control section and code area consistent; returns the reason if not."""
    if ctl[:4] != CTL_MAGIC or len(ctl) < 0x24 or len(ctl) < ctl_len(ctl):
        return 'bad control section'
    if st == 'cs' and code[:4] in (CS_MAGIC, GFX_MAGIC) and code[:4] != CS_MAGIC or st != 'cs' and code[:4] != GFX_MAGIC:
        return 'code area header magic does not match the stage'
    if struct.unpack_from('<I', ctl, 0x704)[0] != len(code):
        return 'control +0x704 does not match the code area length'
    return None


def ue3_package(head):
    return head[:4] == UE3_TAG and len(head) >= 6 and 0 < struct.unpack_from('<H', head, 4)[0] < 0x8000


def oodle(comp, n):
    red(f'an Oodle block ({len(comp)} -> {n} bytes) needs the game\'s own decoder; '
        'this module only inflates zlib blocks (pass a decoded file instead)')


def ue3_body(d, label):
    """An Unreal Engine 3 package with its compressed chunks decoded. Zlib blocks are inflated here, the others go
    to `oodle`. A package without chunks is returned as it is."""
    i = d.find(UE3_TAG, 4)
    if i < 0:
        return d
    out = [d[:i]]
    while i < len(d):
        if d[i:i + 4] != UE3_TAG or i + 16 > len(d):
            # Borderlands pads cooked packages to a 32 KiB boundary after the last chunk.
            if d.count(0, i) == len(d) - i:
                break
            red(f'{label}: no compressed chunk at {i:#x} (the chunks do not run to the end of the package)')
        bs, cs, us = struct.unpack_from('<III', d, i + 4)
        if not bs:
            red(f'{label}: chunk at {i:#x} has block size 0')
        nb = (us + bs - 1) // bs
        o = i + 16 + 8 * nb
        for k in range(nb):
            c, u = struct.unpack_from('<II', d, i + 16 + 8 * k)
            blk = span(d, o, c, f'{label} chunk at {i:#x} block {k}')
            out.append(blk if c == u else zlib.decompress(blk) if blk[:1] == b'\x78' else oodle(blk, u))
            o += c
        i = o
    return b''.join(out)


def ue3_shaders(d, label):
    """Shader records of an Unreal Engine 3 shader cache: found by the control section's magic, its code-area
    length (+0x704) back to the code area's magic, and the two lengths in front of the code area."""
    out = []
    for m in re.finditer(re.escape(CTL_MAGIC), d):
        c = m.start()
        if c + 0x708 > len(d):
            continue
        n = struct.unpack_from('<I', d, c + 0x704)[0]
        a = c - n
        if a < 12 or d[a:a + 4] not in (GFX_MAGIC, CS_MAGIC):
            continue
        nctl = next((lc for k in (4, 8) if a - k - 4 >= 0
                     for ln, lc in [struct.unpack_from('<II', d, a - k - 4)]
                     if ln == n and 0x760 <= lc <= 0x1000), None)
        if nctl is None or c + nctl > len(d):
            continue
        ctl, code = d[c:c + nctl], d[a:c]
        st = 'cs' if code[:4] == CS_MAGIC else sph_stage(code)
        why = check(label, st, ctl, code) if st else 'no stage in the code area header'
        if why:
            red(f'{label}: shader record at {c:#x} ({st}): {why}')
        out.append((f'{label}#UE3@{c:x}', st, ctl, code))
    return out


def load(path, decode=True):
    d = open(path, 'rb').read()
    label = os.path.basename(path)
    if d[:4] == b'BMSG':
        return d, label
    if decode and ue3_package(d[:8]):
        return ue3_body(d, label), label
    return d, label


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, files = argv[0], argv[1:]
    decode = '--decoded' not in files
    files = [f for f in files if f != '--decoded']
    expanded = []
    for f in files:
        q = os.path.isdir(f)
        if q:
            expanded += sorted(os.path.join(f, x) for x in os.listdir(f)
                               if x.endswith(('.xxx', '.upk', '.bin')))
        else:
            expanded.append(f)
    files = expanded
    if cmd == 'report':
        total = 0
        for path in files:
            d, label = load(path, decode)
            recs = ue3_shaders(d, label)
            by = {}
            for _, st, _, _ in recs:
                by[st] = by.get(st, 0) + 1
            total += len(recs)
            print(f'{os.path.basename(path)}: {len(recs)} shaders {dict(sorted(by.items()))}', flush=True)
        print('total', total)
    elif cmd == 'dump':
        outdir, files = files[0], files[1:]
        os.makedirs(outdir, exist_ok=True)
        n = 0
        for path in files:
            d, label = load(path)
            for name, st, ctl, code in ue3_shaders(d, label):
                base = os.path.join(outdir, name.replace(':', '_'))
                open(base + f'.{st}.ctl', 'wb').write(ctl)
                open(base + f'.{st}.code', 'wb').write(code)
                n += 1
        print('wrote', n, 'records to', outdir)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
