#!/usr/bin/env python3
"""Borderlands 2 shader jobs in the format dmsh_vk_xc2.py / xgs_pack.py read (DOS2's dos2_shader_jobs.py output).

Inputs: the decoded UE3 packages (bl2_oodle_job.py rebuild) and GlobalShaderCache-Switch.bin.
Outputs in <out>: rec/<key>.rec (0x38 zero header + code + control), jobs.tsv, programs.tsv,
shader_map.tsv, shader_facts.tsv, xfb.tsv, report.txt.

The key is the host's: sha256(control[:its own length] + code[:the length at +0x704])[:16]
(d3_shader_jobs.host_key). Unreal Engine 3 combines vertex and pixel shaders per draw, so each stage is
written as a single-stage program (separable pairs), as the Batman profile does.

Usage: bl2_shader_jobs.py <decoded dir> <GlobalShaderCache-Switch.bin> <out dir>
"""
import collections
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bl2_ue3_shaders as ue3
from d3_shader_jobs import host_key, xfb_layout

GFX = bytes.fromhex('78563412')
CS = bytes.fromhex('79563412')


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 3:
        sys.exit(__doc__)
    src_dir, global_cache, out_dir = Path(argv[0]), Path(argv[1]), Path(argv[2])
    (out_dir / 'rec').mkdir(parents=True, exist_ok=True)
    meta, where, rep, xfbs, progs, bad = {}, collections.defaultdict(list), collections.Counter(), {}, [], []
    files = sorted(src_dir.glob('*.xxx'))
    total = 0
    for n, p in enumerate(files + [global_cache], 1):
        label = p.name
        d = p.read_bytes()
        recs = ue3.ue3_shaders(d, label)
        total += len(recs)
        for lab, st, ctl, code in recs:
            k = host_key(ctl, code)
            where[k].append(lab)
            rec = bytes(0x38) + code + ctl
            if k in meta:
                if (out_dir / 'rec' / f'{k}.rec').read_bytes() != rec:
                    bad.append(f'{k}: same key, different bytes ({lab})')
                continue
            (out_dir / 'rec' / f'{k}.rec').write_bytes(rec)
            c1o, c1t = struct.unpack_from('<2I', ctl, 0x700)
            own, = struct.unpack_from('<I', ctl, 0x20)
            xfb = st == 'vs' and any(struct.unpack_from('<4H', ctl, 0x6dc))
            if xfb:
                xfbs[k] = xfb_layout(ctl)
            m = {'stage': st, 'code': len(code), 'ctrl': len(ctl), 'kl': own if 0x760 <= own < 0x880 else 0x880,
                 'c1': c1t - c1o, 'src': lab, 'xfb': xfb, 'progs': 1, 'next': set()}
            if st == 'cs':
                lc = list(struct.unpack_from('<3I', ctl, 0x748))
                sh, = struct.unpack_from('<I', ctl, 0x754)
                if not all(1 <= x <= 1024 for x in lc) or lc[0] * lc[1] * lc[2] > 1024 or sh > 49152:
                    bad.append(f'{lab}: local {lc} shared {sh}')
                m['facts'] = {'local': lc, 'shared': (sh + 15) // 16 * 16}
            meta[k] = m
            rep[f'{st} control {len(ctl):#x}'] += 1
            progs.append((lab, k if st == 'vs' else '-', k if st == 'gs' else '-',
                          k if st == 'ps' else '-', k if st == 'cs' else '-'))
        if n % 100 == 0:
            print(f'  {n}/{len(files) + 1} files, {len(meta)} keys', flush=True)
    with open(out_dir / 'programs.tsv', 'w', newline='\n', encoding='utf-8') as fp:
        fp.write('label\tvs\tgs\tps\tcs\n' + ''.join('\t'.join(r) + '\n' for r in progs))
    with open(out_dir / 'jobs.tsv', 'w', newline='\n', encoding='utf-8') as fp:
        fp.write('key\tstage\tcode_bytes\tctrl_bytes\tctl_key_bytes\tc1_bytes\txfb\tprograms\tnext\tsource\n')
        for k in sorted(meta):
            v = meta[k]
            fp.write(f"{k}\t{v['stage']}\t{v['code']}\t{v['ctrl']}\t{v['kl']}\t{v['c1']}\t{int(v['xfb'])}\t"
                     f"{v['progs']}\t-\t{v['src']}\n")
    with open(out_dir / 'shader_map.tsv', 'w', newline='\n', encoding='utf-8') as fp:
        fp.write('key\tstage\tfiles\n')
        for k in sorted(meta):
            fp.write(f"{k}\t{meta[k]['stage']}\t{' | '.join(where[k])}\n")
    with open(out_dir / 'shader_facts.tsv', 'w', newline='\n', encoding='utf-8') as fp:
        fp.write('# BL2 translation-query facts: key <TAB> facts JSON (local / shared for compute)\n')
        for k in sorted(meta):
            f = dict(meta[k].get('facts') or {})
            if f:
                fp.write(k + '\t' + json.dumps(f, separators=(',', ':')) + '\n')
    with open(out_dir / 'xfb.tsv', 'w', newline='\n', encoding='utf-8') as fp:
        fp.write('# vertex shaders whose control section declares transform feedback\n')
        for k in sorted(xfbs):
            for b, stride, o in xfbs[k]:
                fp.write(f'{k}\t{b}\t{stride}\t{" ".join(f"{l}:{c}" for l, c in o)}\n')
    sc = collections.Counter(v['stage'] for v in meta.values())
    lines = [f'files: {len(files)} packages + {global_cache.name}; records {total}',
             f'unique keys: {len(meta)} ({", ".join(f"{s} {n}" for s, n in sorted(sc.items()))}); problems: {len(bad)}',
             f'transform feedback: {" ".join(sorted(xfbs)) or "none"}'] + \
            [f'  {n:6d}  {k}' for k, n in sorted(rep.items())] + \
            [f'  PROBLEM {b}' for b in bad[:40]]
    (out_dir / 'report.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:20]))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
