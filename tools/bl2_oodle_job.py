#!/usr/bin/env python3
"""Oodle job files for Borderlands 2's Unreal Engine 3 packages, and the decoded packages back.

hle_oodle.c (ported from seedds/nxnative, DM_OODLE_JOB mode) runs the game's own Oodle decoder right before
nnMain: a job file "DMOJ", u32 count, then per record u32 compressed length, u32 raw length, the bytes; it
writes "<job>.out" = "DMOR", u32 count, then per record u32 decoded length (0 = failed) and the bytes, and exits.

This tool cuts every compressed block out of the given .xxx packages into one job file and keeps a sidecar so
the decoded packages can be put back together:

  bl2_oodle_job.py build <job> <package.xxx>...
  bl2_oodle_job.py rebuild <job.out> <job.json> <out dir>

A package is: [summary][chunk 0][chunk 1]... ; a chunk is {tag 0x9E2A83C1, u32 block size, u32 compressed,
u32 raw, per block u32 compressed and u32 raw} then the blocks. A block whose two sizes are equal is stored, not
compressed, and goes to neither the job nor the decoder.
"""
import json
import os
import struct
import sys
from pathlib import Path

TAG = bytes.fromhex('c1832a9e')


def chunks(d, path):
    i = d.find(TAG, 4)
    if i < 0:
        return None
    chunks_ = []
    while i < len(d):
        if d[i:i + 4] != TAG or i + 16 > len(d):
            if d.count(0, i) == len(d) - i:
                break
            sys.exit(f'{path}: no compressed chunk at {i:#x}')
        bs, cs, us = struct.unpack_from('<III', d, i + 4)
        nb = (us + bs - 1) // bs
        o = i + 16 + 8 * nb
        blocks = []
        for k in range(nb):
            c, u = struct.unpack_from('<II', d, i + 16 + 8 * k)
            blocks.append((o, c, u))
            o += c
        chunks_.append(blocks)
        i = o
    return i, chunks_


def build(job, packages):
    expanded = []
    for p in packages:
        q = Path(p)
        if q.is_dir():
            expanded += [str(x) for x in sorted(q.glob('*.xxx')) + sorted(q.glob('*.upk'))]
        else:
            expanded.append(p)
    packages = expanded
    records = []
    packages_meta = []
    for p in packages:
        d = Path(p).read_bytes()
        r = chunks(d, p)
        if r is None:
            print(f'skip (no chunk): {p}')
            continue
        summary_len, ch = r
        meta = {'path': os.path.abspath(p), 'summary': summary_len, 'blocks': []}
        for blocks in ch:
            for off, c, u in blocks:
                if c == u:
                    meta['blocks'].append(['store', off, c])
                else:
                    meta['blocks'].append(['job', len(records)])
                    records.append((d[off:off + c], u))
        packages_meta.append(meta)
    os.makedirs(os.path.dirname(os.path.abspath(job)), exist_ok=True)
    with open(job, 'wb') as f:
        f.write(b'DMOJ')
        f.write(struct.pack('<I', len(records)))
        for comp, raw_len in records:
            f.write(struct.pack('<II', len(comp), raw_len))
            f.write(comp)
    Path(job + '.json').write_text(json.dumps({'packages': packages_meta}, indent=1))
    print(f'{job}: {len(records)} records, {len(packages_meta)} packages, {os.path.getsize(job)/2**20:.2f} MB')


def rebuild(out_file, sidecar, outdir):
    side = json.loads(Path(sidecar).read_text())
    data = Path(out_file).read_bytes()
    if data[:4] != b'DMOR':
        sys.exit('not a DMOR file')
    n, = struct.unpack_from('<I', data, 4)
    o = 8
    decoded = []
    for _ in range(n):
        ln, = struct.unpack_from('<I', data, o)
        o += 4
        decoded.append(data[o:o + ln])
        o += ln
    os.makedirs(outdir, exist_ok=True)
    for meta in side['packages']:
        src = Path(meta['path']).read_bytes()
        out = bytearray(src[:meta['summary']])
        for item in meta['blocks']:
            if item[0] == 'store':
                _, a, b = item
                out += src[a:a + b]
            else:
                out += decoded[item[1]]
        dst = Path(outdir) / Path(meta['path']).name
        dst.write_bytes(out)
        print(dst, len(out))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 3:
        sys.exit(__doc__)
    if argv[0] == 'build':
        build(argv[1], argv[2:])
    elif argv[0] == 'rebuild':
        if len(argv) < 4:
            sys.exit(__doc__)
        rebuild(argv[1], argv[2], argv[3])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
