#!/usr/bin/env python3
"""Find NVN shader containers in Borderlands 2's files without unpacking them.

Borderlands 2 (UE3) keeps no BNSH/BAHS at the top level: the programs sit inside
RomFS containers (.xxx/.upk/.bin) and inside the program modules. Two magics mark them:
  GLSLCoutput  91 68 86 19  (u32 LE 0x19866891) -- an NVN program (control section + GPU code)
  NVN control  34 12 76 98  (u32 LE 0x98761234) -- the control section a GLSLCoutput carries

Usage: bl2_shader_scan.py <romfs dir> [more dirs/files...] [-o report.tsv]
Output: one row per file with hits: path, glslc count, control count, first glslc offset.
The count is a lower bound (chunks overlap by 3 bytes, so a magic split across a
chunk boundary is still seen once).
"""
import argparse
import os
import sys
from pathlib import Path

G = b'\x91\x68\x86\x19'
C = b'\x34\x12\x76\x98'
CHUNK = 8 << 20
OVER = 3


def scan_file(p):
    glslc = control = 0
    first = -1
    pos = 0
    tail = b''
    with p.open('rb') as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            buf = tail + b
            base = pos - len(tail)
            i = 0
            while True:
                i = buf.find(G, i)
                if i < 0:
                    break
                glslc += 1
                if first < 0:
                    first = base + i
                i += 1
            control += buf.count(C)
            tail = buf[-OVER:]
            pos += len(b)
    return glslc, control, first


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('paths', nargs='+')
    ap.add_argument('-o', '--out', default='')
    a = ap.parse_args(argv)
    rows = []
    files = []
    for raw in a.paths:
        p = Path(raw)
        if p.is_dir():
            files += [q for q in p.rglob('*') if q.is_file()]
        elif p.is_file():
            files.append(p)
    print(f'{len(files)} files', flush=True)
    for n, p in enumerate(files, 1):
        try:
            g, c, first = scan_file(p)
        except OSError as e:
            print(f'ERR {p}: {e}', file=sys.stderr, flush=True)
            continue
        if g or c:
            rows.append((str(p), g, c, first))
            print(f'HIT {p} glslc={g} control={c} first={first:#x}', flush=True)
        if n % 200 == 0:
            print(f'  {n}/{len(files)}', flush=True)
    rows.sort(key=lambda r: -r[1])
    print(f'{len(rows)} files with shader magic, {sum(r[1] for r in rows)} GLSLCoutput total', flush=True)
    if a.out:
        Path(a.out).write_text('path\tglslc\tcontrol\tfirst_glslc\n' +
                               ''.join(f'{p}\t{g}\t{c}\t{first:#x}\n' for p, g, c, first in rows))
        print('report ->', a.out, flush=True)


if __name__ == '__main__':
    main()
