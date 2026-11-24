# C/C++ 分隔符门：捕获手工三方合并的结构截断，不替代编译器。
# C/C++ delimiter gate: catch structural truncation during manual three-way merges; not a compiler replacement.
from pathlib import Path
import re
root=Path(__file__).resolve().parents[4]
def first_branch(s):   # keep only the first branch of #if / #else (both branches would count a brace twice)
    out=[];skip=[]
    for ln in s.split('\n'):
        t=ln.strip()
        if t.startswith('#if'):skip.append(bool(skip and skip[-1]));out.append('');continue
        if t.startswith('#el') and skip:skip[-1]=True;out.append('');continue
        if t.startswith('#endif') and skip:skip.pop();out.append('');continue
        out.append('' if (skip and skip[-1]) else ln)
    return '\n'.join(out)
def delimiter_gate():   # -> names of files whose delimiters do not balance (NB-20a: runs after the draw-path check, same verdict)
    bad=[]
    for name in ['gfx/vulkan/engine/xbg_game.cpp','gfx/nvn/hle_nvn.c','android/vulkan_present.cpp']:
        s=(root/name).read_text(encoding='utf-8')
        s=re.sub(r"""/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'""", "", s,flags=re.S)
        s=first_branch(s)   # NB-20a: #if / #else branches counted once
        stack=[];ok=True
        for ch in s:
            if ch in '({[':stack.append(ch)
            elif ch in ')}]':
                if not stack or stack.pop()!={')':'(',']':'[','}':'{'}[ch]:ok=False;break
        if not ok or stack:bad.append(name);print('FAIL: delimiter gate: %s (%d left open)'%(name,len(stack)))
    if not bad:print('PASS: C/C++ balanced delimiters for engine, NVN and Android presenter (not a compile)')
    return bad

# NB-20a (docs/dos2/NATIVE_BACKEND_PLAN.md, "NB-20a findings"): every namespace-scope variable and every `static` local of the
# translate-thread draw path, by class, for multi-threaded pass recording (DM_NB_MT, NB-20b..d). Name-based grep, not a parser:
# a NEW name in the draw path fails here -> classify it in the NB-20a table and add it below (a name that left the path only prints).
#   C = per-recording-context (moves into the worker's context)   K = counter (per-context block, summed at the pass join)
#   L = shared cache / lock / atomic                              S = serial: pass / barrier / layout / slot decisions (plan pre-pass)
#   R = read-only after init (switches, device facts)              D = diagnostic (DM_NB_MT stays serial while armed)
#   N = name collision: a global of another namespace whose name the path uses for a local / member
NB20A_DRAW_GLOBALS = {
 'C': 'command_pool cx_sh draw_timing nvn_stage P cand ps_called snap_how',   # not moved yet (cx_sh / draw_timing: diagnostics; P / cand: nbdesc; ps_called / snap_how: NR-ZERO Z3 - scratch of the draw / the snapshot() call in hand); the rest: NB20B_CTX below
 'K': 'alpha_draws alpha_refused alpha_variants async_skips bad barrier_by binds_skipped changed compile_ns create_max_ns create_ns '
      'creates depth_bounds_dropped depth_feedback_reads depth_idle_passes desc_abandoned desc_chained desc_memo_hits desc_memo_misses '
      'desc_memo_texel_fail desc_memo_why desc_ns dirty_pages fallbacks fb_creates fb_hits hits key_diff lazy_storage_saved '
      'memo_front_hits memo_simg_hits mid_chunk_ns mismatches missing_program_skips msaa_passes noload_passes noload_why noout_masked '
      'offset_changed_at offset_changes pass_end_by pass_end_lines pass_fast_hits pending_misses perf pipe_draw_fast_hits pipe_memo_hits '
      'pipe_memo_misses pipe_pod_hits pipe_pod_misses pipeline_counts pipeline_fast_hits pipeline_ns read_break_why reversed_depth_draws '
      'set_bind_offsets set_binds set_binds_offsets_only skipped_draws snap_front_hits span_calls span_t0 stats texel_hits tile_war_barriers xmemo_hits '
      'xview_races s bytes draws hist idx inst multi plain u8 store_kept xlq_draw_pipes xlq_twin_pipes idvs_point_pipes',   # + DM_GFX_VTX_STATS counters (VERTEX.md)
 'L': 'any built count exhausted failed gskip_n id_keys ids images_epoch lazy_info memo_check_gen memo_mod_gen memo_pinned modules mu '
      'mutex nregions persistent_framebuffers pipeline_cache pipeline_fast pipeline_objects pipeline_tick pipelines pipelines_unsaved '
      'regions render_pass_cache snapshot_epoch tracked',
 'S': 'barrier_seq bi_dc counter_epoch cur cur_ok desc_serial0 epochs frag_seq frame last_pass lazy lazy_ok lazy_pending open_occlusion '
      'inside open_pass passes_since_full pclear_n pending_reports pending_writebacks slot_index slot_rec_begin slot_serial slots storage_dirty '
      'storage_image_draw storage_unbarriered write_seq cmd index cur_at lazy_at ui_rec frag_first nrrp_fresh_mask need_full area red live g twin_draw fused_draw',   # fused_draw: NR-LIGHTFUSE, the draw in hand (like twin_draw)   # g: NR-UIX vertex box of the draw in hand   # live: NR-30 prepass (the override draw in hand, like nrdraw cur)   # ui_rec: NR-12 (nrdraw, like its cur)   # + NR-10b DM_NR_COVER: the area decision of the pass being begun, the area pass being recorded   # + NR-10 DM_NR_RP: first draw's read kind, fresh mask of the pass being begun   # + DM_GFX_SAMPLES_TS=4 shared stamp of the open pass (samplets::cmd / index, VERTEX.md)
 'R': 'bind_cache_enabled cfg depth16_as_d24 depth_bias_x2 desc_memo_enabled dmode draw_detail draw_reads_on enabled gpu_driver_id img_fast '
      'lazy_clear_on lazy_storage max_regions missing_program nb_rp_mode no_occlusion_queries noload_enabled noout_mask_on '
      'occlusion_batch_enabled persistent_fb_enabled pipe_memo pipeline_fast_enabled pipeline_object_limit properties read_frag_only '
      'read_preflight readback_cached serial slot_pools_enabled snap_no_sync store_hist_mode texel_memo_enabled tile_barrier_on '
      'tile_frag_stages timestamp_bits xmemo_enabled xview_guard hist_on fresh nr_xlq xlq_twin nr_idvs area_mode cache_mode rb_mode shfar',   # shfar: N6 nrhack (DM_HACK_SHFAR, read once at the first draw / sampler)   # + NR-UIX switches, NR-32/33B xlq_twin   # fresh: nrrp::fresh (DM_NR_RP_FRESH)
 'D': 'mode active armed on bi_kind bi_store capture draw_log_fp draw_log_n end_img end_line end_why eng_mask last_attachment_trace last_writer '
      'late notes open pass_prof_draws pass_prof_enabled pass_prof_frame pass_prof_log pass_prof_next pass_prof_period pass_prof_queries '
      'pass_prof_query_limit pass_prof_skipped_slots pass_prof_slot_limit pass_prof_slots pass_prof_until pass_prof_verts passes pend '
      'pipe_stats pipeline provenance_file pstat_logged pstat_use sub told in_op mute sh_b sh_f nr_mute nr_sh_b nr_sh_f rd_lost',   # + NB-08 DM_NB_OPBARRIER=2 shadow (opbar::)
 'N': 'guard layout line ok pool result sets slot t0 uint8_t valid want why state',   # state: astccache::state (the State of the draw path is a context variable, NB20B_CTX)
}
# static locals of draw(prim, first, count, ...): C scratch vectors, D log-once counters, R one-time env parse, N scanner artefact
NB20A_DRAW_STATICS = {'C': 'attachments attributes bindings fast fkey stages', 'D': 'n noted notes told unb', 'R': 'skip_init skip_sh', 'N': 'uint32_t'}
NB20A_PATH = ('draw create_pass pass_deps descriptors descriptors_stable prepare_read prepare_attachment mark_storage_images begin_open '
              'end_open_pass full_barrier snapshot stream_buffer first_draw_covers nbrp_begin lazy_clear_open lazy_clear_begin '
              'occlusion_query pass_prof_draw pipeline_lookup recording_slot pipe_memo_fill get_image').split()


def _nb20a_strip(s):
    bs = chr(92); out = []; i = 0; n = len(s)
    while i < n:
        c = s[i]
        if s.startswith('//', i):
            j = s.find('\n', i); j = n if j < 0 else j; out.append(' ' * (j - i)); i = j
        elif s.startswith('/*', i):
            j = s.find('*/', i + 2); j = n if j < 0 else j + 2; out.append(re.sub(r'[^\n]', ' ', s[i:j])); i = j
        elif c in '"\'' and not (c == "'" and i and s[i - 1].isalnum()):
            j = i + 1
            while j < n and s[j] != c:
                j += 2 if s[j] == bs else 1
            out.append(c + ' ' * (j - i - 1) + c); i = j + 1
        elif c == '#' and s[s.rfind('\n', 0, i) + 1:i].strip() == '':
            j = i
            while True:
                e = s.find('\n', j); e = n if e < 0 else e
                if s[e - 1:e] == bs: j = e + 1; continue
                break
            out.append(re.sub(r'[^\n]', ' ', s[i:e])); i = e
        else:
            out.append(c); i += 1
    return ''.join(out)


def _nb20a_scan(text):
    """-> (namespace-scope variable names, {function name: [bodies]}) of one translation unit (both #if branches are seen)."""
    s = _nb20a_strip(text); stack = []; st0 = 0; paren = 0; names = set(); bodies = {}
    fn_head = re.compile(r'([A-Za-z_~]\w*)\s*\(([^;{}]*)\)\s*(?:const)?\s*(?:noexcept)?\s*$')
    top = lambda: all(k == 'ns' for k in stack)
    for i, c in enumerate(s):
        if c == '(': paren += 1
        elif c == ')': paren -= 1
        elif c == '{' and paren == 0:
            head = s[st0:i]
            if top() and re.search(r'\bnamespace\s*\w*\s*$', head): stack.append('ns'); st0 = i + 1
            elif top():
                h = head.strip(); m = fn_head.search(h)
                if m and not re.match(r'(template\s*<[^>]*>\s*)?(struct|class|union|enum)\b', h) and not h.endswith('='):
                    stack.append(('fn', m.group(1), i))
                else: stack.append(('other', '', i))
            else: stack.append('x')
        elif c == '}' and paren == 0:
            k = stack.pop()
            if k == 'ns': st0 = i + 1
            elif top() and k[0] == 'fn': bodies.setdefault(k[1], []).append(s[k[2]:i + 1]); st0 = i + 1
        elif c == ';' and paren == 0 and top():
            t = re.sub(r'\s+', ' ', s[st0:i]).strip(); st0 = i + 1
            if not t or re.match(r'(using|typedef|template|friend|static_assert|namespace)\b', t): continue
            if re.match(r'(struct|class|union)\b[^{]*\{', t): t = re.sub(r'^.*\}\s*', '', t)
            d = 0; parts = ['']
            for ch in t:
                d += ch in '({[<'; d -= ch in ')}]>'
                if ch == ',' and d == 0: parts.append('')
                else: parts[-1] += ch
            if re.search(r'\w\s*\(.*\)\s*(const|noexcept)?\s*$', parts[0].split('=')[0].strip()): continue  # prototype
            if re.match(r'(struct|class|enum|union)\s+\w+\s*$', parts[0].strip()): continue
            for pt in parts:
                q = re.sub(r'\{.*$', '', re.sub(r'\[[^\]]*\]', '', pt.split('=')[0])).strip()
                m = re.search(r'([A-Za-z_]\w*)$', q)
                if m: names.add(m.group(1))
    return names, bodies


def nb20a_check():
    names, bodies = _nb20a_scan((root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8'))
    gone = [f for f in NB20A_PATH if f not in bodies]
    assert not gone, 'NB-20a: draw-path functions not found (renamed? update NB20A_PATH): %s' % gone
    used = set(); statics = set()
    for f in NB20A_PATH:
        for b in bodies[f]:
            used |= {m.group(1) for m in re.finditer(r'(?<![\w.>])([A-Za-z_]\w*)', b) if m.group(1) in names}
            if f == 'draw' and len(b) > 20000:   # draw(prim, first, count, ...), not pgraph::draw()
                statics |= {m.group(1) for m in re.finditer(r'\bstatic\s+[\w:<>,\s\*&]+?\b([A-Za-z_]\w*)\s*(?=[=;{\[,])', b)}
    for what, table, found in (('global', NB20A_DRAW_GLOBALS, used), ('static local of draw()', NB20A_DRAW_STATICS, statics)):
        known = {}
        for cls, v in table.items():
            for nm in v.split():
                assert nm not in known, 'NB-20a: %s listed twice (%s, %s)' % (nm, known[nm], cls); known[nm] = cls
        new = sorted(found - set(known))
        assert not new, ('NB-20a: new %s on the translate-thread draw path: %s -> classify it (C/K/L/S/R/D/N) in '
                         'docs/dos2/NATIVE_BACKEND_PLAN.md "NB-20a findings" and in NB20A_DRAW_* here' % (what, ' '.join(new)))
        left = sorted(set(known) - found)
        if left: print('note: NB-20a %s no longer on the draw path (drop from the table): %s' % (what, ' '.join(left)))
    counts = {c: len(v.split()) for c, v in NB20A_DRAW_GLOBALS.items()}
    print('PASS: NB-20a draw-path globals classified: %d (%s), draw() static locals: %d'
          % (len(used), ' '.join('%s=%d' % kv for kv in counts.items()), len(statics)))


# NB-19 (docs/dos2/NATIVE_BACKEND_PLAN.md "NB-19 findings"): DM_NB_TRANSIENT wiring. Every hook in xbg_game.cpp is gated by nbtr::mode
# (off = one test, output unchanged); every non-attachment use of an image reaches nbtr::touch before it needs other usage; every host
# pass begin path goes through lrz_touch_before (nbtr::begin); the planned paths call nbtr::decide right before it.
def nb19_check():
    s = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nb_transient.inc').read_text(encoding='utf-8')
    names, bodies = _nb20a_scan(s)
    calls = list(re.finditer(r'nbtr::(touch|begin|decide|frame|gone)\(', s))
    assert len(calls) >= 9, 'NB-19: nbtr hooks missing (%d)' % len(calls)
    for m in calls:
        line = s[s.rfind('\n', 0, m.start()) + 1:s.find('\n', m.start())]
        assert 'nbtr::mode>0' in line or 'nbtr.transient' in line, 'NB-19: ungated hook: %s' % line.strip()[:160]
    tr = s[s.find('void transition(VkCommandBuffer cmd,VkImageLayout next'):][:1600]   # nr-all: NR-10 + NR-11 hooks lengthen the head
    assert 'nbtr::touch(*this,NB_TRF_XFER)' in tr and tr.find('nbtr::touch') < tr.find('b.oldLayout=layout'), \
        'NB-19: the transition hook must run before the barrier reads layout / image'
    vw = s[s.find('VkImageView view(const view_t *v,bool attachment=false'):][:400]
    assert 'if(!attachment && nbtr::mode>0)nbtr::touch(*this,NB_TRF_READ)' in vw, 'NB-19: view hook (sampled / storage view)'
    for fn, hook in (('prepare_read', 'nbtr::touch(im,NB_TRF_READ)'), ('upgrade_mutable', 'nbtr::touch(im,NB_TRF_XFER)'),
                     ('lrz_touch_before', 'nbtr::begin(p)'), ('nbrp_begin', 'nbtr::decide(p,t.dc,store)'),
                     ('nbrp_lazy_begin', 'nbtr::decide(lazy.pass,')):
        b = bodies.get(fn, [''])[0]
        assert hook in b, 'NB-19: %s lacks %s' % (fn, hook)
        if fn.startswith('nbrp'):
            assert b.find('nbtr::decide') < b.find('lrz_touch_before('), 'NB-19: decide() must precede lrz_touch_before in %s' % fn
    code = _nb20a_strip(s)
    begins = len(re.findall(r'vkCmdBeginRenderPass\(', code))
    lrz = len(re.findall(r'\blrz_touch_before\((?!const)', code))
    assert lrz == 6 and begins == 7, ('NB-19: host pass begin paths changed (%d vkCmdBeginRenderPass, %d lrz_touch_before calls): a new '
                                      'begin path must call lrz_touch_before (nbtr::begin) - the ClearTexture view pass is the 7th' % (begins, lrz))
    assert 'nbtr::init();' in s and 'getenv("DM_NB_TRANSIENT")' in inc and 'TRANSIENT_ATTACHMENT_BIT' in inc and 'LAZILY_ALLOCATED_BIT' in inc
    print('PASS: NB-19 DM_NB_TRANSIENT hooks gated (%d calls); transition / view / prepare_read / upgrade_mutable touch; %d host pass '
          'begins through lrz_touch_before' % (len(calls), lrz))


# NB-20b (docs/dos2/NATIVE_BACKEND_PLAN.md "NB-20b findings"): DM_NB_MT records the slot's command buffer on a worker by turning every
# vkCmd* of the translation unit into a packet (xbg_nb_mt.inc). That only holds while NO call reaches the command buffer around the
# wrappers: a vkCmd* name without a wrapper, a command called through a function pointer, the command buffer handed to another file, or
# a begin / end of the slot's command buffer outside the nbmt bracket would write into it while the worker does.
# The draw path's globals (NB-20a table above) are untouched by NB-20b: the worker reads none of them (it gets copies of the arguments).
def nb20b_check():
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    mt = (eng / 'xbg_nb_mt.inc').read_text(encoding='utf-8')
    wrapped = set(re.findall(r'^#define (vkCmd\w+) nbmt::Cmd\w+\s*$', mt, flags=re.M))
    assert len(wrapped) >= 31, 'NB-20b: wrapper list of xbg_nb_mt.inc not found (%d)' % len(wrapped)
    for w in sorted(wrapped):
        assert re.search(r'#define %s nbmt::C%s\s*$' % (w, w[3:]), mt, flags=re.M), 'NB-20b: %s is mapped to another wrapper' % w
        body = mt[mt.find('inline void C%s(VkCommandBuffer c' % w[3:]):]
        assert body.startswith('inline void C') and 'NBMT_REAL(%s)' % w in body[:body.find('\n}') + 2 if '{ pod<' not in body[:400] else body.find('\n') + 1], \
            'NB-20b: wrapper of %s does not reach the real %s' % (w, w)
    code = _nb20a_strip(s)
    inc_at = s.find('#include "xbg_nb_mt.inc"')
    first = re.search(r'\bvkCmd\w+', code)
    assert 0 < inc_at < first.start(), 'NB-20b: xbg_nb_mt.inc must be included before the first vkCmd* of xbg_game.cpp'
    used = set(re.findall(r'\bvkCmd\w+', code))
    files = ['xbg_game.cpp']
    for f in sorted(eng.glob('*.inc')):
        if f.name == 'xbg_nb_mt.inc': continue
        t = f.read_text(encoding='utf-8')   # every engine .inc is part of this translation unit (some through another .inc)
        used |= set(re.findall(r'\bvkCmd\w+', _nb20a_strip(t))); files.append(f.name)
        at = s.find('#include "%s"' % f.name)
        assert at < 0 or at > inc_at, 'NB-20b: %s is included before xbg_nb_mt.inc' % f.name
    missing = sorted(used - wrapped)
    assert not missing, ('NB-20b: vkCmd* without a wrapper in xbg_nb_mt.inc (with DM_NB_MT it would be written into the command buffer '
                         'while the worker records): %s' % ' '.join(missing))
    assert '#undef vkCmd' not in s, 'NB-20b: a vkCmd* wrapper is undefined in xbg_game.cpp'
    # commands reached through function pointers: declared PFN_vkCmd* variables may only be passed to nbmt::P*, never called
    ptrs = set(re.findall(r'PFN_vkCmd\w+\s+(\w+)\s*=\s*nullptr', code))
    assert {'pbegin', 'pend', 'pfn_draw_indexed_indirect_count', 'pfn_draw_indirect_count'} <= ptrs, 'NB-20b: PFN_vkCmd* variables moved (%s)' % sorted(ptrs)
    for nm in sorted(ptrs):
        m = re.search(r'(?<![\w])(?:\w+\s*\.\s*)?%s\s*\(' % nm, code)
        assert not m, 'NB-20b: %s is called directly (use the nbmt::P* wrapper): %s' % (nm, code[max(0, m.start() - 40):m.end() + 20].strip())
    assert len(re.findall(r'nbmt::P(?:Begin|End)ConditionalRendering\(|nbmt::PDraw(?:Indexed)?IndirectCount\(', code)) == 4, 'NB-20b: the four pointer commands go through nbmt::P*'
    # the bracket: one begin and one end of the slot's command buffer, each with its hook right next to it
    names, bodies = _nb20a_scan(s)
    assert len(re.findall(r'vkBeginCommandBuffer\(s\.cmd\b', code)) == 1 and len(re.findall(r'vkEndCommandBuffer\(s\.cmd\b', code)) == 1, \
        'NB-20b: the slot command buffer is begun / ended in more than one place'
    rs = bodies['recording_slot'][0]; b0 = rs.find('vkBeginCommandBuffer(s.cmd'); h0 = rs.find('nbmt::begin(s.cmd,')
    assert 0 < b0 < h0 and not re.search(r'\bvkCmd\w+', rs[b0:h0]), 'NB-20b: nbmt::begin must follow vkBeginCommandBuffer(s.cmd) at once'
    assert 's.pool!=VK_NULL_HANDLE' in rs[h0:h0 + 80] and 'ab_off(' in rs[h0:h0 + 80], 'NB-20b: nbmt::begin needs the own-pool and A/B conditions'
    ss = bodies['submit_slots'][0]; h1 = ss.find('nbmt::end(s.cmd)'); e1 = ss.find('vkEndCommandBuffer(s.cmd')
    assert 0 < h1 < e1 and not re.search(r'\bvkCmd\w+', ss[h1:e1]), 'NB-20b: nbmt::end must be the last thing before vkEndCommandBuffer(s.cmd)'
    assert 'nbmt::stop()' in bodies['destroy_slots'][0] and s.count('nbmt::init();') == 1, 'NB-20b: nbmt::stop in destroy_slots / nbmt::init at the switches'
    # the command buffer never leaves the translation unit, and the worker takes nothing of the engine: no engine name in the queue header
    for h in sorted(eng.glob('*.h')):
        assert 'VkCommandBuffer' not in h.read_text(encoding='utf-8', errors='replace'), 'NB-20b: %s takes a command buffer (another file could record into the slot)' % h.name
    core = (root / 'gfx/nb/nb_mt.h').read_text(encoding='utf-8')
    assert 'vulkan' not in re.sub(r'//[^\n]*', '', core).lower() and 'cv_idle.wait(' in core and 'cv_work.wait(' in core and not re.search(r'\byield\b|sleep_for|usleep', core), \
        'NB-20b: nb_mt.h stays engine-free and waits on condition variables only'
    for sw in ('DM_NB_MT', 'DM_NB_MT_FLUSH', 'DM_NB_MT_CHUNK_KB', 'DM_NB_MT_QUEUE', 'DM_NB_MT_CPUS'):
        assert '"%s"' % sw in mt, 'NB-20b: switch %s' % sw
    assert re.search(r'num\("DM_NB_MT", 0, 0, 3\)', mt), 'NB-20b: DM_NB_MT defaults to 0'
    print('PASS: NB-20b DM_NB_MT: %d vkCmd* names of %s all wrapped (%d wrappers), %d pointer commands through nbmt::P*, begin / end / stop / init '
          'hooks in place, no command buffer in engine headers' % (len(used), ' + '.join(files[:1]) + ' + %d .inc' % (len(files) - 1), len(wrapped), len(ptrs)))
# 16.11 store-hist (docs/dos2/DOS2_PORT.md "store-hist: учёт выброшенного store"): every read / overwrite note is gated by hist_on (or sits
# in a function only called under it); both planned begin paths drop the store DONT_CARE of banned images before the twin is made, and the
# plan's discards are marked with the IR pass (nb_seq / nb_node) for the VIOLATION line.
def storehist_check():
    s = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    names, bodies = _nb20a_scan(s)
    inside = ('hist_note_read', 'hist_note_overwrite', 'hist_begin', 'store_hist_mask', 'hist_keep')
    nl = chr(10); spans = []
    for f in inside:   # the bookkeeping helpers themselves (called only under hist_on): from their definition to the next top-level line
        d = re.search(r'\n(?:void|uint32_t|unsigned) ' + f + r'\(', s); assert d, 'store-hist: %s not defined' % f
        e = re.search(r'\n(?![ \t])', s[d.end():]); spans.append((d.start(), d.end() + (e.start() if e else 0)))
    calls = 0
    for m in re.finditer(r'\b(hist_note_read|hist_note_overwrite|hist_begin)\(', s):
        line = s[s.rfind(nl, 0, m.start()) + 1:s.find(nl, m.start())]
        if re.match(r'\s*(void|struct Image;)', line): continue   # definitions / prototypes
        if any(x <= m.start() < y for x, y in spans): continue
        calls += 1
        assert 'hist_on' in line, 'store-hist: ungated bookkeeping: %s' % line.strip()[:160]
    assert calls >= 10, 'store-hist: bookkeeping hooks missing (%d)' % calls
    for fn in ('nbrp_begin', 'nbrp_lazy_begin'):
        b = bodies.get(fn, [''])[0]
        assert 'nb_rp_keep_store(&t,hist_keep(' in b and b.find('nb_rp_keep_store') < b.find('lazy_twin('), 'store-hist: %s keeps banned stores before the twin' % fn
        assert 'open_pass.nb_seq=' in b and "hist_begin(" in b, 'store-hist: %s marks / judges like the heuristic' % fn
    assert 'xbg_hist_discarded(' in bodies['store_hist_pass_end'][0] and 'hist_on=store_hist_mode!=0 || nb_rp_mode==1 || nb_rp_mode==3' in s
    assert 'store_hist_mode)hist_note_read' not in s and 'hist_dead' not in s, 'store-hist: old fields / gates left'
    print('PASS: store-hist bookkeeping gated by hist_on (%d hooks);' % calls + ' planned begins keep banned stores; plan discards marked with the IR pass')


# NB-20b ctx (docs/dos2/NATIVE_BACKEND_PLAN.md "NB-20b-ctx findings"): the class C globals moved into the recording context. Each is
# read through `#define <name> nbx::get(<name>_m0, nbx::K_<name>)` (xbg_nb_mx.inc): the main instance on every thread unless a window is
# open and the thread is a worker. The list here, the slot enum, the defines and the registrations must stay in step, nobody may name a
# main instance directly, and a pure header read after the defines must be pre-included by xbg_nb_mx.inc (its own identifiers would
# meet the macros).
NB20B_CTX = ('bind_cache buf_gen cur_op desc_memo_dyn desc_memo_images desc_memo_local desc_memo_recording desc_memo_texel draw_reads '
             'draw_reads_overflow g_ui_moff g_ui_moff_addr img_front in_descriptors memo_dyn_ok memo_front_gen memo_front_it memo_front_key '
             'memo_front_slot pipe_memo_key pipe_memo_next pipe_memo_pipeline pipe_memo_valid snap_site state storage_images_bound tex_gen').split()
def nb20b_ctx_check():
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    mx = (eng / 'xbg_nb_mx.inc').read_text(encoding='utf-8')
    known = set()
    for c, v in NB20A_DRAW_GLOBALS.items():
        if c != 'N': known |= set(v.split())
    both = sorted(set(NB20B_CTX) & known)
    assert not both, 'NB-20b ctx: listed in the NB-20a table and as a context variable: %s' % both
    m = re.search(r'enum Slot \{(.*?)\};', mx, flags=re.S)
    slots = [t.split('=')[0].strip() for t in m.group(1).split(',')]
    assert slots[-1] == 'K_COUNT' and sorted(x[2:] for x in slots[:-1]) == sorted(NB20B_CTX), \
        'NB-20b ctx: the slot enum of xbg_nb_mx.inc and NB20B_CTX differ: %s' % sorted(set(x[2:] for x in slots[:-1]) ^ set(NB20B_CTX))
    code = _nb20a_strip(s)   # no comments, strings or preprocessor lines
    first_def = len(s)
    for n in NB20B_CTX:
        d = '#define %s nbx::get(%s_m0,nbx::K_%s)' % (n, n, n)
        assert s.count(d) == 1, 'NB-20b ctx: %s needs exactly one `%s`' % (n, d)
        first_def = min(first_def, s.find(d))
        assert len(re.findall(r'nbx::reg\(nbx::K_%s,&%s_m0, *' % (n, n), code)) == 1, 'NB-20b ctx: %s is not registered once' % n
        uses = len(re.findall(r'\b%s_m0\b' % n, code))
        assert uses == (3 if n == 'in_descriptors' else 2), ('NB-20b ctx: the main instance %s_m0 is named %d times outside its declaration and registration '
                                                              '(use %s: a worker has its own)' % (n, uses, n))
        assert '#undef %s' % n not in s, 'NB-20b ctx: %s is undefined somewhere' % n
    assert s.find('#include "xbg_nb_mx.inc"') > s.find('#include "xbg_nb_mt.inc"') > 0 and s.find('#include "xbg_nb_mx.inc"') < first_def, 'NB-20b ctx: xbg_nb_mx.inc right after xbg_nb_mt.inc, before the defines'
    pre = set(re.findall(r'^#include "([^"]+)"', mx, flags=re.M))
    late = set(re.findall(r'^#include "((?:\.\./\.\./nb/|xbg_)[^"]+\.h)"', s[first_def:], flags=re.M))
    for f in sorted(eng.glob('*.inc')):
        if f.name in ('xbg_nb_mt.inc', 'xbg_nb_mx.inc'): continue
        late |= set(re.findall(r'^#include "((?:\.\./\.\./nb/|xbg_)[^"]+\.h)"', f.read_text(encoding='utf-8'), flags=re.M))
    missing = sorted(h for h in late if h not in pre)
    assert not missing, 'NB-20b ctx: headers read after the context defines but not pre-included by xbg_nb_mx.inc: %s' % missing
    names, bodies = _nb20a_scan(s)
    assert 'nbx::submit(n,handles,budget,ab_off(' in bodies['xbg_submit_now'][0] and s.count('nbx::init();') == 1 and 'nbx::stop();' in bodies['destroy_slots'][0], \
        'NB-20b ctx: nbx::submit in xbg_submit_now / nbx::init at the switches / nbx::stop in destroy_slots'
    core = (root / 'gfx/nb/nb_mx.h').read_text(encoding='utf-8')
    assert 'vulkan' not in re.sub(r'//[^\n]*', '', core).lower() and not re.search(r'\byield\b|sleep_for|usleep', core), 'NB-20b ctx: nb_mx.h stays engine-free, waits on condition variables only'
    assert re.search(r'num\("DM_NB_MX", 0, 0, 1\)', mx) and re.search(r'num\("DM_NB_MX_PROF", 0, 0, 1\)', mx), 'NB-20b ctx: DM_NB_MX / DM_NB_MX_PROF default to 0'
    print('PASS: NB-20b ctx: %d context variables (slot enum = defines = registrations, no direct use of a main instance), %d late headers '
          'pre-included, submit / init / stop hooks in place' % (len(NB20B_CTX), len(late)))


# NR-10 (DM_NR_RP, docs/dos2/nr/NR-10.md): render-pass visibility points. Default 0 = the old barriers: every hook is gated by the switch.
def nr10_check():
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    inc = (eng / 'xbg_nb.inc').read_text(encoding='utf-8')
    hit = (eng / 'xbg_nb_hit.inc').read_text(encoding='utf-8')
    pol = (eng / 'xbg_vendor_policy.h').read_text(encoding='utf-8')
    hdr = (root / 'gfx/nr/nr_rp.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_rp_default(XbgGpuFamily f){return xbg_tile_family(f)?1:0;}' in pol, 'NR-10 (audit P0): DM_NR_RP 1 on the tile families only'
    assert 'inline bool xbg_nr_rp_fresh_default(XbgGpuFamily f){return xbg_tile_family(f);}' in pol, 'NR-10 (tiler plan step 1, batch D D_rp3): DM_NR_RP_FRESH 1 on the tile families only'
    assert 'nrrp::fresh=nrrp::mode==3 || (nrrp::mode==1 && (fresh_env?atoi(e)!=0:xbg_nr_rp_fresh_default(gpu_policy)));' in s, 'NR-10: FRESH only with DM_NR_RP=1 (3 poisons), dm/env DM_NR_RP_FRESH=0 turns the family default off'
    assert '(DM_NR_RP_FRESH=1, family default)' in s and '(DM_NR_RP_FRESH=1, env)' in s, 'NR-10: the start line says where FRESH came from (phone check of the default)'
    assert 'nrrp::mode=e&&*e?atoi(e):xbg_nr_rp_default(gpu_policy);if(nrrp::mode<0 || nrrp::mode>3)nrrp::mode=0;' in s, 'NR-10: DM_NR_RP is read once, 0..3, else off'
    assert 'namespace nrrp{int mode=0;' in s and 'inline bool apply(){return mode==1 || mode==3;}' in s, 'NR-10: nrrp::mode starts 0; apply = 1 / 3'
    n = 0
    for text in (s, inc):
        for m in re.finditer(r'\b(nrrp_pass_end|nrrp_read|nrrp_open|nrrp_fresh)\(', text):
            line = text[text.rfind('\n', 0, m.start()) + 1:text.find('\n', m.start())]
            if re.match(r'\s*(void|uint32_t) nrrp_', line) or line.lstrip().startswith('//'): continue   # the definitions / comments
            assert 'nrrp::mode' in line, 'NR-10: ungated hook: %s' % line.strip()[:160]
            n += 1
    assert n >= 5, 'NR-10: hooks missing (%d)' % n
    assert 'inline uint64_t lw(const Image &im){return apply() && im.last_write<=(read_frag_only?im.nrvis_frag:im.nrvis_full)?0:im.last_write;}' in s, 'NR-10: lw is last_write unless 1 / 3'
    assert 'const bool written=nrrp::lw(im)>seen || (!as_storage && im.storage_write>seen);' in s and 'x.last_write=nrrp::lw(im);' in hit, 'NR-10: prepare_read and the hit-fast path use the same last_write'
    assert 'bool bar=true;if(nrrp::apply() && in_open' in s and 'if(bar){if(read_frag_only)frag_barrier(cmd);else full_barrier(cmd);}' in s, 'NR-10: the read barrier is dropped only at 1 / 3'
    pb = inc[inc.find('void prebar(const Pass &p'):inc.find('bool open(const Pass &p')]
    old = 'if(write_seq>barrier_seq || storage_unbarriered){full_barrier(cmd);for(auto *im:p.images)im->last_write=++write_seq;++s.prebar_bar;}'
    assert old in pb and pb.find('if(nrrp::mode){') < pb.find(old) and 'if(nrrp::apply()){' in pb, 'NR-10: the old pre-pass barrier stays the path of 0 / 2'
    assert 'if(nrrp::fresh && nrrp::apply() && nrrp_fresh_mask)' in s and 'pi->aspects==VK_IMAGE_ASPECT_COLOR_BIT' in s, 'NR-10: fresh loads only with the switch, colour only'
    assert '#include <vulkan' not in hdr and 'hle.h' not in hdr and '#include <stdint.h>' in hdr and 'getenv' not in hdr, 'NR-10: nr_rp.h stays pure'
    print('PASS: NR-10: DM_NR_RP default 1 on the tile families (Mali / PowerVR), 0 elsewhere, %d hooks gated by nrrp::mode, old read / pre-pass barriers unchanged at 0 / 2, fresh loads behind DM_NR_RP_FRESH (colour only)' % n)

# NR-10b (DM_NR_COVER, docs/dos2/nr/NR-10b.md): the coverage proof for computed vertex positions. Default 0 = first_draw_covers decides
# as before: every hook is gated by nrcov::mode / nrcov::red.on (red.on is only set by an area pass, i.e. with the switch at 1 / 3).
# NR-UIX (docs/dos2/nr/NR-UIX.md, tiler plan step 1): DM_NR_UIX_DS / DM_NR_UIX_AREA 1 on the tile families by default, RB / CACHE 0;
# read once in uix::init from the policy family (DM_GFX_SIM_GPU included), dm/env overrides (0 turns a part off); the start line names the source.
def nruix_check():
    eng = root / 'gfx/vulkan/engine'
    pol = (eng / 'xbg_vendor_policy.h').read_text(encoding='utf-8')
    inc = (eng / 'xbg_nr_uix.inc').read_text(encoding='utf-8')
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_uix_default(XbgGpuFamily f,int which){return (which==0 || which==1) && xbg_tile_family(f)?1:0;}' in pol, 'NR-UIX: DS + AREA 1 on the tile families only, RB / CACHE 0'
    assert 'ds_mode=env_mode("DM_NR_UIX_DS",xbg_nr_uix_default(fam,0),3);area_mode=env_mode("DM_NR_UIX_AREA",xbg_nr_uix_default(fam,1),3);' in inc, 'NR-UIX: DS / AREA from dm/env, else the family default'
    assert 'rb_mode=env_mode("DM_NR_UIX_RB",xbg_nr_uix_default(fam,2),2);cache_mode=env_mode("DM_NR_UIX_CACHE",xbg_nr_uix_default(fam,3),2);' in inc, 'NR-UIX: RB / CACHE from dm/env, else the family default (0)'
    assert 'int env_mode(const char *name,int def,int hi){const char *e=getenv(name);int v=e && *e?atoi(e):def;' in inc, 'NR-UIX: an env value (0 included) wins over the default'
    assert 'uix::init(gpu_policy);' in s and s.index('gpu_policy=xbg_effective_family(gpu_family,sim_gpu);') < s.index('uix::init(gpu_policy);'), 'NR-UIX: init after the policy family (DM_GFX_SIM_GPU) is known'
    assert '"[nr] uix (NR-UIX, policy family %s): DM_NR_UIX_DS=%d (%s; %s), DM_NR_UIX_AREA=%d (%s; %s)' in inc and 'src("DM_NR_UIX_DS")' in inc and 'src("DM_NR_UIX_AREA")' in inc, 'NR-UIX: the start line names the family and env / family default'
    print('PASS: NR-UIX defaults (DS / AREA on the tile families, env override, start line source)')

def nr10b_check():
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    inc = (eng / 'xbg_nr_cover.inc').read_text(encoding='utf-8')
    pol = (eng / 'xbg_vendor_policy.h').read_text(encoding='utf-8')
    hdr = (root / 'gfx/nr/nr_cover.h').read_text(encoding='utf-8')
    pos = (eng / 'xbg_spirv_pos.cpp').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_cover_default(XbgGpuFamily){return 0;}' in pol, 'NR-10b: the default is 0 on every family'
    assert 'namespace nrcov{int mode=0;bool armed=false;' in s, 'NR-10b: nrcov::mode starts 0, nothing armed'
    assert 'mode=e&&*e?atoi(e):xbg_nr_cover_default(fam);if(mode<0 || mode>3)mode=0;' in inc and s.count('nrcov::init(gpu_policy);') == 1, 'NR-10b: DM_NR_COVER is read once, 0..3, else off'
    old = 'first_draw_covers(p,prim,first,count,indexed,vertex_buffers,ib,index_type)'
    a = 'nbrp::cur.cover && !gi && p.pass_noload && quad_indices.empty() && !ab_off("noload") && ui_uy==0 && ui_vs==1 && ' + old + ');}'
    b = '!gi && p.pass_noload && quad_indices.empty() && !ab_off("noload") && ui_uy==0 && ui_vs==1 && ' + old + '){begin_open(p,c,true);++noload_passes;}'
    assert s.count(a) == 1 and s.count(b) == 1 and s.count('nrcov::mode?nrcov::at_begin(') == 2, 'NR-10b: both begin sites keep the old expression as the mode-0 branch'
    n = 0
    for m in re.finditer(r'nrcov::(at_begin|pre|before_clear|begun|area_twin)\(', s):
        line = s[s.rfind('\n', 0, m.start()) + 1:s.find('\n', m.start())]
        if line.lstrip().startswith('//'): continue
        assert re.search(r'nrcov::mode|nrcov::red\.on|nrcov::armed', line[:m.start() - s.rfind('\n', 0, m.start())]), 'NR-10b: ungated hook: %s' % line.strip()[:160]
        n += 1
    assert n >= 6, 'NR-10b: hooks missing (%d)' % n
    assert 'if((nrcov::mode || uix::area_mode) && h.stage==0){p->pos=std::make_unique<nr_cv_prog>();' in s, 'NR-10b / NR-UIX: the position program is built only with one of the switches on'
    assert 'VkRenderPass nr_nl=p.pass_noload;if(noload && !nr_nl){' in s, 'NR-10b: begin_open takes the twin only when the pass has no noload render pass (never at 0: the old proof needs one)'
    # an area pass: bookkeeping keeps the attachments LOADed (the DONT_CARE bits are not in t.dc) and never discards a store
    assert 'const uint32_t extra=ta.dc&~t.dc;' in inc and 't.mask&=~(0x1ffull<<18);' in inc and 'lazy_twin(p.pass,t.mask|(uint64_t(nr_adc)<<32))' in s, 'NR-10b: area twin = load op only, STORE kept'
    assert 'if(use_area && nb && store_hist_mode!=3 && nb_rp_mode!=3 && nrrp::mode!=3){armed=true;' in inc, 'NR-10b: no area pass under a poison mode that clears the whole target'
    assert 'void end_open_pass(int line){if(open_pass.cmd){nrcov::red.on=false;' in s, 'NR-10b: the area pass ends with the open pass'
    assert 'if(mode==2' in inc and 'bool covered=old;' in inc and 'if(mode==1 || mode==3){' in inc, 'NR-10b: =2 executes the old decision'
    assert 'draw_reads_overflow' in inc and 'fs->discards' in inc and 'state.color.blend_en>>i&1' in inc and 'condr::cg' in inc, 'NR-10b: the refusals of the old proof are kept (+ conditional draws)'
    for name, text in (('nr_cover.h', hdr), ('xbg_spirv_pos.cpp', pos)):
        assert '#include <vulkan' not in text and 'hle.h' not in text and 'getenv' not in text and 'xbg_game' not in text, 'NR-10b: %s stays pure' % name
    assert '#define NR_CV_MARGIN 0.25' in hdr and 'v[k][3] != 1.0f' in hdr, 'NR-10b: pixel-centre proof with a margin; w must be exactly 1'
    assert '${E}/xbg_spirv_pos.cpp' in (root / 'gfx/vulkan/CMakeLists.txt').read_text(encoding='utf-8'), 'NR-10b: xbg_spirv_pos.cpp is built'
    print('PASS: NR-10b: DM_NR_COVER default 0 on every family, %d hooks gated, the old expression is the mode-0 branch at both begin sites, area passes keep STORE and the LOAD bookkeeping' % n)

# NR-01 (engine object registry of the native renderer, DM_NR, default 0): the wiring that keeps "off" byte-identical.
#   - hle_nvn.c: exactly four tap lines, one per entry point (nvnTextureInitialize, nvnProgramSetShaders, nvnSamplerInitialize,
#     nvnBufferInitialize), each an NRT(...) = a test of g_dm_nr; the tap functions only read the host object;
#   - hle_dos2_nr.c: g_dm_nr starts 0 and is set only inside dm_dos2_nr_install, which returns before allocating / hooking anything
#     unless DM_NR is 1 or 2; hooks (dn_hook / dn_install_rc) are installed nowhere else; every hook is NR_HOOK (never a tail call:
#     a sibling call would write its stack arguments into the game's caller frame), calls its own trampoline once with all 28
#     forwarded values, and is listed once in k_nr_site;
#   - main.c calls the install after the NB one, inside the DOS2 block; the registry core stays free of engine / host / game addresses.
def nr01_check():
    def code(text):   # no comments, no strings
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):   # the brace-matched body after the first `head`
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    nvn = code((root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8'))
    inc_raw = (root / 'gfx/nvn/nvn_nr_tap.inc').read_text(encoding='utf-8')
    inc = code(inc_raw)
    host_raw = (root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8')
    host = code(host_raw)
    # the tap
    assert (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8').count('#include "nvn_nr_tap.inc"') == 1, 'NR-01: hle_nvn.c includes nvn_nr_tap.inc once'
    assert nvn.count('NRT(') == 4 + 8 + 3, 'NR-01 / NR-02 / NR-05: hle_nvn.c has exactly 4 + 8 + 3 NRT(...) tap lines (four initialise taps, NR-02: bind + seven draws, NR-05: finalize, two WriteTexels), found %d' % nvn.count('NRT(')
    for fn, args in (('nvnTextureWriteTexels', 'r, src, 0, 0'), ('nvnTextureWriteTexelsStrided', 'r, src, row, img')):
        assert 'write_texels(CTX(t), GVIEW(v), %s); NRT(nrt_texture_written(CTX(t))); if (lk) nvn_texel_unlock();' % args in body(nvn, 'NVN(%s,' % fn),             'NR-05: %s reports the write right after write_texels, inside the texel lock' % fn
    fin = body(nvn, 'NVN(nvnTextureFinalize,')
    assert re.match(r'\{\s*NRT\(nrt_texture_gone\(TX\(t\)\)\);', fin), 'NR-05: the finalize tap is the first statement of nvnTextureFinalize (before magic is cleared)'
    for fn, call in (('nvnTextureInitialize', 'NRT(nrt_texture(o));'), ('nvnProgramSetShaders', 'NRT(nrt_program(o));'), ('nvnSamplerInitialize', 'NRT(nrt_sampler(o));'),
                     ('nvnBufferInitialize', 'NRT(dm_nr_tap_buffer(o, o->size, o->mem));')):
        b = body(nvn, 'NVN(%s,' % fn)
        assert b.count('NRT(') == 1 and call in b, 'NR-01: %s needs the one tap line `%s`' % (fn, call)
        tail = b[b.index(call) + len(call):]
        assert re.fullmatch(r'\s*return 1;\s*\}', tail), 'NR-01: in %s the tap line is the last statement before `return 1;` (the object is complete, the result unchanged)' % fn
    assert '#define NRT(x) do { if (__builtin_expect(g_dm_nr != 0, 0)) { x; } } while (0)' in inc_raw, 'NR-01: NRT is a guarded line (g_dm_nr != 0)'
    assert re.search(r'#ifdef DM_GAME_DOS2.*#define NRT\(x\) do \{ if.*#else\s*#define NRT\(x\) do \{ \} while \(0\)\s*#endif', inc_raw, flags=re.S), 'NR-01: NRT is empty outside DOS2'
    for fn in ('nrt_texture', 'nrt_texture_gone', 'nrt_texture_written', 'nrt_program', 'nrt_sampler'):
        b = body(inc, 'static void %s(const ' % fn)
        assert not re.search(r'(?<![=!<>])=(?!=)', b), 'NR-01: %s only reads the host object' % fn
    # the front end
    assert re.search(r'^int g_dm_nr;', host, flags=re.M), 'NR-01: g_dm_nr has no initialiser (0 = off)'
    inst = body(host, 'void dm_dos2_nr_install(void) {')
    gate = 'if (mode != 1 && mode != 2) return;'
    assert 'getenv("DM_NR")' in body(host_raw, 'void dm_dos2_nr_install(void) {') and gate in inst and 'const int asked = e ? atoi(e) : 0, ts = se ? atoi(se) : 0, tex = te ? atoi(te) : ts >= 1 && ts <= 2 ? 1 : 0;' in inst \
        and 'const int mode = asked == 2 ? 2 : asked == 1 || (tex >= 1 && tex <= 3) ? 1 : 0;' in inst, 'NR-01: DM_NR unset / 0 / anything but 1, 2 (and no DM_NR_TEX 1..3) returns at once (default 0)'
    for later in ('nr_reg_new(', 'dn_hook(', 'dn_install_rc(', 'g_dm_nr = mode', 'dn_main('):
        assert later in inst and inst.index(gate) < inst.index(later), 'NR-01: `%s` only after the DM_NR gate' % later
    rest = host.replace(inst, '')
    assert 'dn_hook(' not in rest.replace('int dn_hook(module_t', '') and 'dn_install_rc(' not in rest.replace('int dn_install_rc(const', ''), 'NR-01: hooks are installed only by dm_dos2_nr_install'
    assert len(re.findall(r'\bg_dm_nr\s*=(?!=)', host)) == 2 and len(re.findall(r'\bg_dm_nr\s*=(?!=)', rest)) == 0, 'NR-01: g_dm_nr is set only inside the install'
    assert '#define NR_HOOK static __attribute__((disable_tail_calls)) uint64_t' in host_raw, 'NR-01: NR_HOOK forbids tail calls'
    hooks = re.findall(r'^NR_HOOK (nr_h_\w+)\(NR_A\)', host, flags=re.M)
    assert len(hooks) >= 18 and len(set(hooks)) == len(hooks) and not re.search(r'^static\s+uint64_t\s+nr_h_', host, flags=re.M), 'NR-01: every hook is declared NR_HOOK'
    table = body(host, 'k_nr_site[] =')
    for h in hooks:
        b = body(host, 'NR_HOOK %s(NR_A)' % h)
        orig = 'g_o_' + h[len('nr_h_'):]
        assert b.count(orig + '(NR_F)') == 1 and len(re.findall(r'\bg_o_\w+\(', b)) == 1, 'NR-01: %s calls its own trampoline %s once with the forwarded arguments' % (h, orig)
        assert table.count('(void *)%s, &%s}' % (h, orig)) == 1, 'NR-01: %s is listed once in k_nr_site with %s' % (h, orig)
    assert table.count('(void *)nr_h_') == len(hooks), 'NR-01: k_nr_site rows = hooks'
    assert len(set(re.findall(r'\{(0x[0-9a-f]+), \{', table))) == len(hooks), 'NR-01: one site per hook, no address twice'
    assert 'if (!dn_words_ok(m, s->off, s->pro))' in inst and inst.index('if (!dn_words_ok(m, s->off, s->pro))') < inst.index('dn_hook('), 'NR-01: prologue words are compared before a site is patched'
    assert re.search(r'if \(op != 55 \|\| !pkt\) return;', body(host, 'static void nr_rc_pre(')), 'NR-01: the render-command handler leaves every opcode but 55 at once'
    assert 'malloc(' not in host and 'calloc(' not in host, 'NR-01: the front end allocates nothing itself (nr_reg_new at install only)'
    # NR-01 fix (docs/dos2/nr/NR-01-fix.md): the pack key reads the code only through nr_peek, and nr_peek retries what process_vm_readv
    # refuses (the VM_PFNMAP dma-buf pages of the zero-copy pools) through the pipe of nr_peek.h (copy_from_user: EFAULT, never a signal)
    pk = body(host, 'static int nr_pack_key(')
    assert 'xbg_shader_program_key_rd(control, (uint64_t)(uintptr_t)code, nr_peek, out)' in pk and 'xbg_shader_program_key(' not in pk, \
        'NR-01 fix: nr_pack_key keys through xbg_shader_program_key_rd + nr_peek, never by loads of the code'
    pe = body(host, 'static int nr_peek(void *dst')
    assert 'SYS_process_vm_readv' in pe and 'nr_peek_pipe(dst, addr, n)' in pe and pe.index('SYS_process_vm_readv') < pe.index('nr_peek_pipe(dst, addr, n)'), \
        'NR-01 fix: nr_peek tries process_vm_readv first, then the pipe'
    assert 'nr_pipe_read(g_nr_pfd, dst, addr, n)' in body(host, 'static int nr_peek_pipe('), 'NR-01 fix: the pipe read is nr_peek.h nr_pipe_read'
    peek_h = code((root / 'gfx/nr/nr_peek.h').read_text(encoding='utf-8'))
    assert 'signal' not in peek_h and 'sigaction' not in peek_h and 'setjmp' not in peek_h, 'NR-01 fix: nr_peek.h reads without any signal handler'
    key_c = (root / 'gfx/vulkan/engine/xbg_shader_key.c').read_text(encoding='utf-8')
    assert 'int xbg_shader_program_key_rd(' in key_c, 'NR-01 fix: xbg_shader_key.c has the reader form of the pack key'
    # main.c
    main_c = (root / 'host/main.c').read_text(encoding='utf-8')
    a, b_ = main_c.find('dm_dos2_nb_install(); }'), main_c.find('{ void dm_dos2_nr_install(void); dm_dos2_nr_install(); }')
    dos2 = main_c.rfind('#ifdef DM_GAME_DOS2', 0, b_)
    assert 0 < a < b_ and main_c.count('dm_dos2_nr_install();') == 1 and dos2 > 0 and '#endif' not in main_c[dos2:b_], 'NR-01: main.c calls dm_dos2_nr_install once, after the NB install, inside the DOS2 block'
    # the registry core: host-testable
    sites = set(re.findall(r'\{(0x[0-9a-f]+), \{', table))
    for name in ('nr_reg.h', 'nr_reg.c'):
        core_raw = (root / 'gfx/nr' / name).read_text(encoding='utf-8'); core = code(core_raw)
        assert 'vulkan' not in core.lower() and 'hle.h' not in core_raw and 'pthread' not in core and 'getenv' not in core, 'NR-01: %s stays free of the engine, the host and the environment' % name
        assert not any(s in core for s in sites), 'NR-01: %s holds no game address' % name
    rows = re.findall(r'^    \{"\w+", 0x[0-9a-f]+, 0x[0-9a-f]+, \d+, \d+, \d+\},$', (root / 'gfx/nr/nr_reg.c').read_text(encoding='utf-8'), flags=re.M)
    assert len(rows) == 63, 'NR-01: the engine format table has 63 rows (found %d)' % len(rows)
    for cm in ('android/CMakeLists.txt', 'harmony/native/CMakeLists.txt'):
        assert '${DM}/gfx/nr/*.c' in (root / cm).read_text(encoding='utf-8'), 'NR-01: %s builds dm/gfx/nr' % cm
    print('PASS: NR-01: 4 guarded tap lines (last statement before return), DM_NR default 0 gate before any hook / allocation, %d hooks (NR_HOOK, own trampoline once, '
          'listed once), opcode 55 only, registry core engine-free, 63 format rows' % len(hooks))


# NR-05 (DM_NR_TEX, default 0; docs/dos2/nr/NR-05.md): material textures by engine events. "Off" stays the old path:
#   - the core dm/gfx/nr/nr_tex.{h,c} is free of the engine, the host, threads and the environment (host-tested: tests/nr_tex_test.c);
#   - hle_dos2_nr.c: g_dm_nr_tex starts 0 and is set only by nrt_start, which the install calls only after the DM_NR gate with
#     DM_NR_TEX 1..3; the create event runs only under g_dm_nr_tex; every function the engine calls returns at once while it is 0;
#   - xbg_game.cpp: every use of namespace nrtex outside its body is gated by nrtex::mode>0 (or by a value only mode > 0 produces:
#     the blob nrb, nr_used, the served key nr); Image::nr is set only by nrtex::on_create (and cleared on an alias).
def nr05_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    for name in ('nr_tex.h', 'nr_tex.c'):
        raw = (root / 'gfx/nr' / name).read_text(encoding='utf-8'); c = code(raw)
        assert 'vulkan' not in c.lower() and 'hle.h' not in raw and 'pthread' not in c and 'getenv' not in c, 'NR-05: %s stays free of the engine, the host, threads and the environment' % name
    host = code((root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8'))
    assert re.search(r'^int g_dm_nr_tex;', host, flags=re.M), 'NR-05: g_dm_nr_tex has no initialiser (0 = off)'
    sets = re.findall(r'\bg_dm_nr_tex\s*=(?!=)', host)
    assert len(sets) == 1 and 'g_dm_nr_tex = mode;' in body(host, 'static int nrt_start(int mode, int ts) {'), 'NR-05: g_dm_nr_tex is set only inside nrt_start'
    inst = body(host, 'void dm_dos2_nr_install(void) {')
    gate = 'if (mode != 1 && mode != 2) return;'
    assert host.count('nrt_start(') == 2 and 'if (tex >= 1 && tex <= 3 && in && nrt_start(tex, ts))' in inst and inst.index(gate) < inst.index('nrt_start('), \
        'NR-05: the install starts the texture table only after the DM_NR gate and only for DM_NR_TEX 1..3'
    assert host.count('nr_tex_engine_gone(') == 1 and 'if (g_dm_nr_tex && obj) { pthread_mutex_lock(&g_nrt_mu); nr_tex_engine_gone(g_nrt, obj); pthread_mutex_unlock(&g_nrt_mu); }' in body(host, 'NR_HOOK nr_h_dt(NR_A)'),         'NR-05: the deferred destroy marks engine-dead entries only under g_dm_nr_tex'
    assert host.count('nrt_event(') == 2 and 'if (g_dm_nr_tex && have) nrt_event(a1, e.src, efmt, b);' in host, 'NR-05: the create event runs only under g_dm_nr_tex'
    for fn in ('void dm_nr_tap_texture_gone(uint64_t serial) {', 'void dm_nr_tap_texture_written(uint64_t serial) {', 'int dm_nr_tex_find(uint64_t serial, nrt_info *out) {', 'void *dm_nr_tex_take(', 'void dm_nr_tex_drop(void *blob, uint64_t bytes) {',
               'int dm_nr_tex_key(uint64_t serial, const void *mem, uint64_t size, uint32_t *crc, uint32_t *adler) {', 'void dm_nr_tex_verdict(unsigned nvn_format, int ok) {', 'void dm_nr_tex_want_key(int on) {'):
        b = body(host, fn)
        assert re.match(r'\{\s*if \(!(blob \|\| !)?g_dm_nr_tex\)', b), 'NR-05: %s returns at once while DM_NR_TEX is off' % fn.split('(')[0]
    eng_raw = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    eng = code(eng_raw)
    ns = body(eng, 'namespace nrtex {')
    outside = eng.replace(ns, '').replace(body(eng, 'namespace nrts {'), '')
    gates = ('nrtex::mode>0', 'if(nrb', 'if(nr_used)', 'if(nr &&', 'if(nr){', 'nrtex::init();', 'namespace nrtex{extern', 'nrts::mode>0', 'if(ts_got.pre', 'if(nrtex::pending)nrtex::poll();')
    uses = 0
    for m in re.finditer(r'nrtex::', outside):
        line = outside[outside.rfind('\n', 0, m.start()) + 1:outside.find('\n', m.start())]
        assert any(g in line for g in gates), 'NR-05: ungated nrtex use: %s' % line.strip()[:200]
        uses += 1
    assert re.search(r'const bool nr=nrtex::mode>0 && dm_nr_tex_key && dm_nr_tex_key\(', outside), 'NR-05: the served ASTC key needs mode > 0'
    assert 'nr_used=true;' in outside and outside.count('nr_used=true') == 2 and outside.count('nr_used=true') == outside.count('if(ts_got.pre && ts_got.pre->kind==NRT_TS_DESW && nrts::mode==1') + 1 and re.search(r'if\(nrtex::mode>0 && im\.nr && !reupload[^\n]*nrb=nrtex::take\(', outside), 'NR-05: a blob is taken only with mode > 0'
    nr_sets = re.findall(r'(?:\bp\.|->|\bim\.)nr=(?!=)', eng)
    assert len(nr_sets) == 2 and 'p.nr=uint8_t(' in body(ns, 'void on_create(') and 'it->second->nr=0;' in outside, 'NR-05: Image::nr is set only by on_create (and cleared on an alias), found %d' % len(nr_sets)
    assert re.search(r'nrtex::mode>0 && im\.nr==1 && upload && im\.uploaded && !im\.gpu_written && im\.checked_submission!=stats\.submissions\)nrtex::check\(im,t\);\s*else if\(upload && im\.uploaded', outside), \
        'NR-05: the probe check replaces the hash / tex-dirty checks only for static images'
    # NR-05 fix (docs/dos2/nr/NR-05-fix.md): the engine's device init ran ~190 ms before nrt_start on the phone (it read 0, NR-05 / NR-22
    # stayed off). The host publishes g_dm_nr_tex_set when its install returns (any path); the engine starts only from it:
    #   - hle_dos2_nr.c: g_dm_nr_tex_set has no initialiser, is set only by the install's cleanup (release), the install's first statement;
    #   - xbg_game.cpp: mode is assigned only in start() (and reset in init); init starts only if the flag is published and 1, else pending;
    #     pending is cleared only by poll(), which starts after reading the flag; poll runs (only while pending) in get_image_slow before the
    #     first image is looked up / created and in perf_frame before nrts::frame; start() asks for worker keys if the ASTC cache is up.
    assert re.search(r'^int g_dm_nr_tex_set;', host, flags=re.M), 'NR-05 fix: g_dm_nr_tex_set has no initialiser (0 = not decided)'
    assert len(re.findall(r'\bg_dm_nr_tex_set\b', host)) == 2 and '__atomic_store_n(&g_dm_nr_tex_set, 1, __ATOMIC_RELEASE);' in body(host, 'static void nr_install_done(int *unused) {'),         'NR-05 fix: g_dm_nr_tex_set is set only by nr_install_done (release)'
    assert re.match(r'\{\s*int nr_done __attribute__\(\(cleanup\(nr_install_done\)\)\) = 0;', inst), 'NR-05 fix: the install publishes g_dm_nr_tex_set on every return (cleanup, first statement)'
    assert 'extern int g_dm_nr_tex_set __attribute__((weak));' in eng, 'NR-05 fix: the engine reads g_dm_nr_tex_set weakly'
    assert len(re.findall(r'(?<![\w:.>])mode=(?!=)', ns)) == 3 and 'int mode=0;' in ns and 'mode=m;' in body(ns, 'void start(int m){') and 'mode=0;' in body(ns, 'void init(){'),         'NR-05 fix: nrtex::mode is set only in start() (defined 0, reset in init)'
    ini, pol = body(ns, 'void init(){'), body(ns, 'void poll(){')
    assert re.search(r'if\(!nrt_engine_decide\(host_mode\(\),&g_dm_nr_tex_set,&m\)\)\{pending=true;return;\}start\(m\);', ini), 'NR-05 fix: init defers (pending) while the install has not returned'
    assert re.search(r'if\(!nrt_engine_decide\(host_mode\(\),&g_dm_nr_tex_set,&m\)\)return;pending=false;started_late=true;start\(m\);', pol), 'NR-05 fix: poll starts only after the decision'
    assert 'g_dm_nr_tex' not in ns.replace('&g_dm_nr_tex:nullptr', '').replace('&g_dm_nr_tex &&', '').replace('&g_dm_nr_tex_set', ''), 'NR-05 fix: nrtex reads the front end only through nrt_engine_decide'
    assert len(re.findall(r'(?<![\w:.>])pending=(?!=)', ns)) == 4, 'NR-05 fix: pending is set only in init / poll (and its definition)'
    hdr = (root / 'gfx/nr/nr_tex.h').read_text(encoding='utf-8')
    assert 'static inline int nrt_engine_decide(const int *host_mode, const int *host_set, int *mode) {' in hdr and 'if (host_set && !__atomic_load_n(host_set, __ATOMIC_ACQUIRE)) return 0;' in hdr,         'NR-05 fix: the decision (tested by tests/nr_tex_start_test.cpp) waits for the published flag'
    assert 'astccache::state==1 && dm_nr_tex_want_key' in body(ns, 'void start(int m){'), 'NR-05 fix: a late start asks for worker keys when the ASTC cache is already up'
    assert outside.count('if(nrtex::pending)nrtex::poll();') == 2, 'NR-05 fix: poll in get_image_slow and perf_frame only'
    gis = body(eng, 'Image &get_image_slow(const tex_t *t,bool upload){')
    assert gis.index('if(nrtex::pending)nrtex::poll();') < gis.index('astccache::lookup(') and gis.index('if(nrtex::pending)nrtex::poll();') < gis.index('nrtex::on_create('),         'NR-05 fix: get_image_slow polls before the ASTC lookup and on_create of a new image'
    pf = body(eng, 'void perf_frame(){')
    assert pf.index('if(nrtex::pending)nrtex::poll();') < pf.index('nrts::frame()'), 'NR-05 fix: perf_frame polls before nrts::frame'
    print('PASS: NR-05 fix: the engine starts NR-05 / NR-22 only after the front end has published its decision (g_dm_nr_tex_set), late start polled in get_image_slow / perf_frame')
    print('PASS: NR-05: nr_tex core engine-free, g_dm_nr_tex 0 until nrt_start (after the DM_NR gate, DM_NR_TEX 1..3), 8 entry points return while off, %d engine uses of nrtex gated, Image::nr only from on_create' % uses)


# NR-16 (docs/dos2/nr/NR-16.md): the CPU attribution counters. Off by default everywhere: DM_NR_CPU and DM_NVN_PROF are read, never set
# by the app; every hook is a flag test before any work; the G wrappers pass every other mutex straight through; =2 is the only NVN mode
# installed in nvn_lookup.
def nr16_check():
    def code(s): return re.sub(r"""/\*.*?\*/|//[^\n]*""", "", s, flags=re.S)
    jni = code((root / 'android/jni_android.c').read_text(encoding='utf-8'))
    assert 'DM_NR_CPU' not in jni and '"DM_NVN_PROF"' not in jni, 'NR-16: the app sets neither DM_NR_CPU nor DM_NVN_PROF'
    cp = code((root / 'host/hle_cpuprof.c').read_text(encoding='utf-8'))
    assert re.search(r'getenv\("DM_NR_CPU"\); g_cp_on = e && atoi\(e\) > 0;\s*if \(!g_cp_on\) return;', cp), 'NR-16: hle_cpuprof.c starts nothing unless DM_NR_CPU > 0'
    assert cp.count('dm_gate_prof = gate_prof') == 1 and cp.find('dm_gate_prof = gate_prof') > cp.find('static void *sampler('), 'NR-16: the gate hook is set only by the sampler thread'
    hle = code((root / 'host/hle.c').read_text(encoding='utf-8'))
    disp = hle[hle.find('uint64_t gate_dispatch('):]
    assert disp.count('dm_gate_prof != 0') == 3 and 'return svc_dispatch(g->arg, regs, g->orig);' in disp, 'NR-16: gate_dispatch tests the hook on the clock, obs and svc paths and keeps the plain svc call'
    th = code((root / 'host/hle_thread.c').read_text(encoding='utf-8'))
    g = th.find('static pthread_mutex_t G = PTHREAD_MUTEX_INITIALIZER;'); m = th.find('#define pthread_mutex_lock(m) gs_lock(m)')
    assert 0 < g < th.find('static int gs_lock(') < m, 'NR-16: the G wrappers come right after G, the macros after them'
    for fn, plain in (('gs_lock', 'return pthread_mutex_lock(m);'), ('gs_cwait', 'return pthread_cond_wait(c, m);'), ('gs_ctwait', 'return pthread_cond_timedwait(c, m, dl);')):
        body = th[th.find('static int %s(' % fn):]; body = body[:body.find('\n}\n')]
        assert 'if (m != &G || !gs_on()) ' + plain in body, 'NR-16: %s passes every other mutex (and G when off) straight through' % fn
    assert 'if (m == &G && gs_on() && t_gs_t0)' in th, 'NR-16: gs_unlock counts only G'
    assert re.search(r'getenv\("DM_NR_CPU"\); g_gs_on = e && atoi\(e\) > 0;', th), 'NR-16: G is counted only with DM_NR_CPU > 0'
    inc = code((root / 'gfx/nvn/nvn_cpuprof.inc').read_text(encoding='utf-8'))
    assert 'if (!e || atoi(e) != 2) return;' in inc, 'NR-16: the sampled NVN timing installs only with DM_NVN_PROF=2'
    nvn = code((root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8'))
    assert nvn.count('nvn_p2_install();') == 1 and nvn.find('nvn_p2_install();') > nvn.find('nvn_bigstack_entry; } }'), 'NR-16: nvn_p2_install once in nvn_lookup, after the big-stack wrapper'
    assert 'atoi(getenv("DM_NVN_PROF")) == 1' in nvn and '&& !g_p2_on' in nvn, 'NR-16: the old DM_NVN_PROF wrapper only for =1, its present-time block not with =2'
    sub = nvn[nvn.find('NVN(nvnQueueSubmitCommands'):]; sub = sub[:sub.find('\n}\n')]
    assert sub.count('nvn_p2_enter()') == 1 and sub.rstrip().endswith('nvn_p2_leave(p2_t0);'), 'NR-16: the submit stamps its start and closes / opens the window as its last statement'
    x = code((root / 'gfx/vulkan/engine/xbg_cpuprof.inc').read_text(encoding='utf-8'))
    assert 'on = e && atoi(e) > 0;' in x, 'NR-16: the translator counters only with DM_NR_CPU > 0'
    for fn in ('pass_open', 'set_bind', 'tcpu'): assert re.search(r'inline \w+ %s\([^)]*\) \{ if \(!?on\)' % fn, x), 'NR-16: cpf::%s tests the flag first' % fn
    for fn in ('draw', 'gpu_span', 'presented', 'submitted'): assert re.search(r'inline void %s\([^)]*\) \{\s*if \(!on\) return;' % fn, x), 'NR-16: cpf::%s returns at once when off' % fn
    game = code((root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8'))
    for hook in ('cpf::pass_open(', 'if(cpf::on)cpf::draw(', 'cpf::set_bind();', 'cpf::gpu_span(', 'cpf::submitted(', 'cpf::presented(', 'cpf::init();'):
        assert game.count(hook) == 1, 'NR-16: xbg_game.cpp calls %s once' % hook
    print('PASS: NR-16: DM_NR_CPU / DM_NVN_PROF=2 default off (not set by the app), gate hook set only by the sampler, G wrappers pass-through, NVN window at the submit, translator hooks flag-first')

# NR-22 (DM_NR_TEXSTREAM, default 0; docs/dos2/nr/NR-22.md): the NR-05 worker makes the VkImage + memory and fills its own staging.
# "Off" stays NR-05 / the old path:
#   - hle_dos2_nr.c: g_dm_nr_texstream starts 0 and is set (with the sink) only inside nrt_start, only for DM_NR_TEXSTREAM 1..2, not with
#     DM_NR_TEX=2, and only when the engine's four xbg_nrts_* entry points exist; the two new engine calls return at once while it is 0;
#     the worker calls the engine's idle hook only under it;
#   - xbg_game.cpp: nrts::mode starts 0 and is set only by nrts::init, which needs NR-05 in mode 1 / 3; ready (the makers' gate) only by
#     nrts::frame, called only under nrts::mode>0; both makers refuse until ready; every nrts use outside its namespace and the extern "C"
#     entry points is gated by nrts::mode (or by ts_got / a Taken that only gated code fills, or by nrtex::mode>0 for its counters);
#   - the old Vulkan calls of image creation stay in place, behind ts_got.adopt only.
def nr22_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    host = code((root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8'))
    assert re.search(r'^int g_dm_nr_texstream;', host, flags=re.M) and re.search(r'^uint64_t g_dm_nr_texstream_cap;', host, flags=re.M), 'NR-22: g_dm_nr_texstream / _cap have no initialiser (0 = off)'
    st = body(host, 'static int nrt_start(int mode, int ts) {')
    sets = re.findall(r'\bg_dm_nr_texstream\s*=(?!=)', host)
    assert len(sets) == 1 and 'g_dm_nr_texstream = ts;' in st and host.count('nr_tex_set_sink(') == 1 and 'nr_tex_set_sink(g_nrt, &sk);' in st, 'NR-22: the sink and g_dm_nr_texstream are set only inside nrt_start'
    assert 'const int ts_on = ts >= 1 && ts <= 2 && mode != NRT_VERIFY;' in st
    gate = 'if (ts_on) {'
    wk = 'if (xbg_nrts_make && xbg_nrts_make_astc && xbg_nrts_release && xbg_nrts_idle) {'
    assert gate in st and wk in st and st.index(gate) < st.index(wk) < st.index('nr_tex_set_sink(') < st.index('g_dm_nr_texstream = ts;') < st.index('pthread_create('), \
        'NR-22: the sink only for DM_NR_TEXSTREAM 1..2 without DM_NR_TEX=2, only with the engine makers, before the worker starts'
    for fn in ('int dm_nr_tex_take_ts(', 'void dm_nr_tex_unhold(uint64_t bytes) {'):
        b = body(host, fn + ('uint64_t serial' if fn.endswith('(') else ''))
        assert re.match(r'\{\s*if \(!g_dm_nr_tex \|\| !g_dm_nr_texstream\)', b), 'NR-22: %s returns at once while DM_NR_TEXSTREAM is off' % fn.split('(')[0]
    assert 'if (g_dm_nr_texstream) { pthread_mutex_unlock(&g_nrt_mu); xbg_nrts_idle(); pthread_mutex_lock(&g_nrt_mu); }' in body(host, 'static void *nrt_worker(void *arg) {'), 'NR-22: the worker calls the idle hook only under g_dm_nr_texstream'
    eng = code((root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8'))
    ns = body(eng, 'namespace nrts {')
    assert re.search(r'\bint mode=0,', ns) and len(re.findall(r'(?<![\w:.>])mode=(?!=)', ns)) == 2, 'NR-22: nrts::mode starts 0 and is set once (init)'
    ini = body(ns, 'void init(){')
    assert '(nrtex::mode==NRT_ON || nrtex::mode==NRT_KEEP)' in ini and 'mode=m==1 || m==2?m:0;' in ini, 'NR-22: nrts::init needs NR-05 in mode 1 / 3'
    assert len(re.findall(r'(?<!ts_)ready\.store\(true', eng)) == 1 and 'ready.store(true' in body(ns, 'void frame(){') and eng.count('nrts::frame();') == 1 and 'if(nrts::mode>0)nrts::frame();' in eng, \
        'NR-22: the makers open only from nrts::frame, called only with nrts::mode>0'
    makers = {}
    for name in ('xbg_nrts_make(', 'xbg_nrts_make_astc(', 'xbg_nrts_release(', 'xbg_nrts_idle('):
        head = 'extern "" void *' + name if 'make' in name else 'extern "" void ' + name   # code() blanks the "C"
        b = body(eng, head); makers[name] = b
    for name in ('xbg_nrts_make(', 'xbg_nrts_make_astc('):
        assert re.match(r'\{\s*using namespace nrts;if\(!ready\.load\(std::memory_order_acquire\)', makers[name]), 'NR-22: %s refuses until ready' % name[:-1]
    outside = eng.replace(ns, '')
    for b in makers.values(): outside = outside.replace(b, '')
    gates = ('nrts::mode>0', 'nrts::mode==', 'if(ts_got.', 'ts_got.pre', 'if(ts', 'nrtex::mode>0', 'namespace nrts{', 'nrts::Taken ts_got;', 'nrts::Taken *g=nullptr', 'nrts::Taken* =nullptr', 'nrts::init();', 'nrts::report();', 'const bool ts=g &&', 'nrts::use(ts_got)')   # init / report: inside nrtex::init / report, mode checked inside
    uses = 0
    for m in re.finditer(r'nrts::', outside):
        line = outside[outside.rfind('\n', 0, m.start()) + 1:outside.find('\n', m.start())]
        assert any(g in line for g in gates), 'NR-22: ungated nrts use: %s' % line.strip()[:200]
        uses += 1
    for call in ('nrts::claim(', 'nrts::take('):
        for m in re.finditer(re.escape(call), outside):
            line = outside[outside.rfind('\n', 0, m.start()) + 1:outside.find('\n', m.start())]
            assert 'nrts::mode>0' in line, 'NR-22: %s only under nrts::mode>0: %s' % (call, line.strip()[:160])
    assert 'up_bytes=astccache::upload(im,t,pro,nrts::mode>0?&ts_got:nullptr);' in outside, 'NR-22: the ASTC upload sees the worker object only with nrts::mode>0'
    slow = body(eng, 'Image &get_image_slow(const tex_t *t,bool upload){')
    assert slow.count('VK(vkCreateImage(cfg.device,&ci,nullptr,&p->image));') == 1 and 'if(ts_got.adopt){p->image=ts_got.pre->image;r=ts_got.pre->req;}else{VK(vkCreateImage(cfg.device,&ci,nullptr,&p->image));vkGetImageMemoryRequirements(cfg.device,p->image,&r);}' in slow, \
        'NR-22: the old vkCreateImage stays, skipped only for an adopted image'
    assert 'if(ts_got.adopt){p->memory=ts_got.pre->memory;' in slow and slow.count('VK(vkAllocateMemory(cfg.device,&ai,nullptr,&p->memory));VK(vkBindImageMemory(cfg.device,p->image,p->memory,0));') == 1, 'NR-22: the old allocation stays, skipped only for an adopted image'
    assert len(re.findall(r'\.adopt=true', eng)) == 1 and 'g.adopt=true;' in body(ns, 'void claim(Image &p,const tex_t *t,const VkImageCreateInfo &ci,Taken &g){'), 'NR-22: adopt is set only by claim (mode 1, same create info and kind)'
    print('PASS: NR-22: g_dm_nr_texstream 0 until nrt_start (DM_NR_TEXSTREAM 1..2, not with DM_NR_TEX=2, engine makers present), 2 entry points return while off, nrts::mode only from init (NR-05 1 / 3), makers closed until frame(), %d engine uses of nrts gated, old create / allocate kept' % uses)
    # NR-22 fix (docs/dos2/nr/NR-22-fix.md): the =2 check of a deswizzled staging compares what the copies read (subresources of
    # nr_tex_layout + the old path's copy regions), not one memcmp of the whole run (the 16-byte alignment gaps were 214 false reds);
    # the call is the only one, under nrts::mode==2, after the old path built its copies; mode 1 never uses the worker's staging for an
    # ASTC-overlay substitute image.
    cd = body(ns, 'void compare_desw(const tex_t *t,const Taken &g,const uint8_t *staged,uint64_t n,const std::vector<VkBufferImageCopy> &copies,VkDeviceSize base){')
    assert 'nr_tex_regions_match(&t->d,&t->L,r,k,&at)' in cd and 'nr_tex_cmp_staged(&t->d,&t->L,g.pre->p,g.pre->bytes,staged,n,&at,&off)' in cd and 'memcmp' not in cd, \
        'NR-22 fix: the deswizzled compare goes through nr_tex_regions_match + nr_tex_cmp_staged only'
    assert 'if(c==NRT_CMP_PAD){++v_pad;return;}' in cd, 'NR-22 fix: a gap-only difference is counted, not a mismatch'
    calls = re.findall(r'[^\n]*nrts::compare_desw\([^\n]*', outside)
    assert len(calls) == 1 and 'nrts::mode==2 && !copies.empty())nrts::compare_desw(t,ts_got,static_cast<const uint8_t*>(staging.mapped),up_bytes,copies,staging.offset);' in calls[0], \
        'NR-22 fix: one compare_desw call, mode 2, with the old path\'s copies and stream offset'
    assert outside.count('nrts::compare(t,') == 1 and outside.count('nrts::compare(t,*g,dst,e.data_bytes);') == 1, 'NR-22 fix: the whole-run compare is left only for the ASTC blocks (tightly packed)'
    assert 'nrts::mode==1 && im.nr==1 && !im.subst && nrtex::copies_of(im,t,copies,ts_got.n)' in slow, 'NR-22 fix: mode 1 uses the worker staging only for a non-substitute image'
    print('PASS: NR-22 fix: =2 compares the deswizzled staging per subresource + copy regions (gaps counted, not red), one call; ASTC keeps its contiguous compare; mode 1 skips substitute images')

# NR-03 (native conditional rendering, DM_NR_OCC, default 0; docs/dos2/nr/NR-03.md): "off" stays byte-identical.
#   - xbg_game.cpp: every nrocc hook sits behind `nrocc::mode>0` (mode starts -1, read once by nrocc::config: unset / 0 / out of range = 0),
#     except the two `nrocc::in_pair()` keep-reasons (prepass, async pipelines), which return false at once unless mode > 0, init() (reads
#     the switch) and destroy() (frees only what exists); xbg_nr_occ.inc is included once, before draw();
#   - hle_nvn.c records OP_X_RENDER_COND only for DM_GFX_COND_RENDER != 0 or DM_NR_OCC 1..3; vulkan_present.cpp asks for the extension
#     only for DM_GFX_COND_RENDER=1 or DM_NR_OCC 1 / 3;
#   - the decision core dm/gfx/nr/nr_occ.h stays engine-free (no Vulkan, no getenv) and has no field the backend #defines (`state`).
def nr03_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    g_raw = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8'); g = code(g_raw)
    inc_raw = (root / 'gfx/vulkan/engine/xbg_nr_occ.inc').read_text(encoding='utf-8'); inc = code(inc_raw)
    assert g_raw.count('#include "xbg_nr_occ.inc"') == 1 and g_raw.index('#include "xbg_nr_occ.inc"') < g_raw.index('void draw(int prim,int first,int count,const p_draw_idx *indexed'), 'NR-03: xbg_nr_occ.inc included once, before draw()'
    uses = [m.start() for m in re.finditer(r'nrocc::(\w+)', g)]
    names = re.findall(r'nrocc::(\w+)', g)
    gated = 0
    for pos, nm in zip(uses, names):
        line = g[g.rfind('\n', 0, pos) + 1:g.find('\n', pos)]
        if 'namespace nrocc{' in line: continue   # the forward declarations
        if nm in ('in_pair', 'init', 'destroy', 'mode'): continue
        if nm == 'after_draw' and line.strip().startswith('if(nro_bits)'): continue   # nro_bits is 0 unless mode > 0
        assert re.search(r'nrocc::mode\s*>\s*0', line), 'NR-03: the hook `nrocc::%s` is not behind nrocc::mode>0: %s' % (nm, line.strip()[:160])
        gated += 1
    assert gated >= 12, 'NR-03: expected the 12 gated hook lines, found %d' % gated
    assert re.search(r'^int mode=-1,', inc, flags=re.M) and 'mode=nro_clamp_mode(e && *e?atol(e):0);if(!mode)return 0;' in inc, 'NR-03: DM_NR_OCC unset / 0 = off, read once'
    assert re.search(r'bool in_pair\(\)\{if\(mode<=0', inc), 'NR-03: in_pair() is false at once when off'
    assert 'void init(){\n    if(config()<=0 || pbuf)return;' in inc_raw, 'NR-03: init() allocates nothing when off'
    nvn = (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8')
    assert 'v = (e && *e && atoi(e) != 0) || (o && *o && atoi(o) >= 1 && atoi(o) <= 3);' in nvn, 'NR-03: hle_nvn.c records conditions only for COND_RENDER != 0 or DM_NR_OCC 1..3'
    pres = (root / 'android/vulkan_present.cpp').read_text(encoding='utf-8')
    assert 'const bool nro_ext=nro && (atoi(nro)==1 || atoi(nro)==3);' in pres and '(ce && atoi(ce)==1) || nro_ext' in pres, 'NR-03: the extension only for COND_RENDER=1 or DM_NR_OCC 1 / 3'
    core_raw = (root / 'gfx/nr/nr_occ.h').read_text(encoding='utf-8'); core = code(core_raw)
    assert 'vulkan' not in core.lower() and 'getenv' not in core and not re.search(r'\bstate\b', core), 'NR-03: nr_occ.h engine-free, no `state` identifier'
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_occ_path_default(XbgGpuFamily f){return xbg_tile_family(f) || f==XBG_GPU_MALEOON?2:1;}' in pol, 'NR-03: path default per family'
    print('PASS: NR-03: %d gated hook lines, DM_NR_OCC default 0 (no record, no query, no allocation), extension / record only for 1..3, core engine-free' % gated)

# NR-11 (docs/dos2/nr/NR-11.md, DM_NR_PRESENT, default 0): the wiring that keeps "off" byte-identical in the engine and the presenter.
def nr11_check():
    s = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_present.inc').read_text(encoding='utf-8')
    pres = (root / 'android/vulkan_present.cpp').read_text(encoding='utf-8')
    logic = (root / 'gfx/nr/nr_present.h').read_text(encoding='utf-8')
    calls = [m for m in re.finditer(r'nrpres::(\w+)\(', s)]
    allowed_ungated = {'init'}
    for m in calls:
        line = s[s.rfind('\n', 0, m.start()) + 1:s.find('\n', m.start())]
        if m.group(1) in allowed_ungated: continue
        if m.group(1) == 'give': assert 'nrv!=NRP_V_OLD?nrpres::give(' in line, 'NR-11: give only for a frame present() took (nrv)'; continue
        if m.group(1) == 'framebuffer': assert 'if(nrp_sub)p.framebuffer=nrpres::framebuffer(' in line; continue
        assert 'nrpres::mode' in line, 'NR-11: ungated hook: %s' % line.strip()[:160]
    assert len(calls) >= 12, 'NR-11: hooks missing (%d)' % len(calls)
    assert s.count('#include "xbg_nr_present.inc"') == 1 and s.find('#include "xbg_nr_present.inc"') > s.find('inline bool viewport_ll()'), 'NR-11: the bodies come after taafix'
    assert 'case OP_SET_RT:state.rt=payload<p_set_rt>(p,n);if(nrpres::mode)nrpres::set_rt();break;' in s, 'NR-11: the start decision right after the render targets are set'
    assert re.search(r'int mode=0;', inc) and 'getenv("DM_NR_PRESENT")' in inc and 'nrp_clamp_mode' in inc, 'NR-11: engine switch DM_NR_PRESENT, default 0'
    # mode 2 never takes an image nor splits: take / split only behind mode!=2
    sr = inc[inc.find('void set_rt(){'):inc.find('// create_pass, each attachment')]
    assert 'if(mode==2)x.presenter=dm_present_nrp_query(' in sr and 'if(mode==2)return;' in sr and sr.find('if(mode==2)return;') < sr.find('split();'), 'NR-11: =2 asks, never takes / splits'
    # submit: the split slot submits the first buffer before the tail, the tail batch waits for the acquire, the restore follows the submit
    sub = s[s.find('void submit_slots(bool wait){'):]
    sub = sub[:sub.find('\n}\n')]
    assert sub.find('if(s.nrp_split)cbs[ncb-1]=s.nrp_main;') < sub.find('nrpres::batches(') < sub.find('ptq::submit(cfg.queue,nsi,si,s.fence)') < sub.find('nrpres::submitted(s)'), 'NR-11: submit order'
    assert 'si[1].pWaitSemaphores=&s.nrp_wait' in inc and 'VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT|VK_PIPELINE_STAGE_TRANSFER_BIT' in inc, 'NR-11: only the tail batch waits, at colour output / transfer'
    # presenter: mode 0 = no usage change, no views, no parking, no snapshot
    assert 'if(nrp::on() && nrp::usage_ok)ci.imageUsage|=nrp_usage;' in pres, 'NR-11: extra swapchain usage only with DM_NR_PRESENT=1/3'
    assert 'if(nrp::mode){   // [DOS2] NR-11: colour-attachment views' in pres and 'if(nrp::on()){std::lock_guard<std::mutex> rl(render_mutex);nrp_park_next();}' in pres, 'NR-11: views / snapshot / parking gated'
    assert pres.count('if(nrp::mode)nrp::drop();') == 2, 'NR-11: views dropped with every swapchain'
    assert 'getenv("DM_NR_PRESENT")' in pres and 'nrp::mode=e && *e?nrp_clamp_mode(atol(e)):0;' in pres, 'NR-11: presenter switch, default 0'
    head = re.sub(r'//.*', '', logic.split('#ifdef VK_VERSION_1_0')[0])
    assert 'vulkan' not in head.lower() and 'Vk' not in head, 'NR-11: the rules are Vulkan-free (host test)'
    print('PASS: NR-11: %d gated engine hooks, start at OP_SET_RT, =2 never takes or splits, tail batch waits, presenter usage / views / parking gated' % len(calls))


# NR-20 (docs/dos2/nr/NR-20.md, DM_NR_ROTATE, default 0): the presenter's pre-rotation stays out of every path unless the switch is set.
def nr20_check():
    pres = (root / 'android/vulkan_present.cpp').read_text(encoding='utf-8')
    logic = (root / 'gfx/nr/nr_rotate.h').read_text(encoding='utf-8')
    assert 'getenv("DM_NR_ROTATE")' in pres and 'nrr::mode=e && *e?nrr_clamp_mode(atol(e)):nrr_default_mode();' in pres, 'NR-20: presenter switch DM_NR_ROTATE'
    assert 'static inline int nrr_default_mode(void) { return NRR_MODE_OFF; }' in logic, 'NR-20: the default stays 0 until dumpsys data fills the policy'
    # create_swap: preTransform / extent / usage change only behind the switch and the decision (decide answers IDENTITY unless 1 / 3 and OK)
    cs = pres[pres.find('int create_swap(){'):pres.find('// 诊断（标记 gfx-membench）')]
    assert 'ci.preTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;' in cs and 'if(nrr::mode){nrr_pre=nrr::decide(' in cs, 'NR-20: identity unless asked'
    assert 'if(nrr_pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR){ci.preTransform=nrr_pre;ci.imageUsage|=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;nrr_image_extent(' in cs, 'NR-20: rotated swapchain fields together'
    assert 'return on() && reason==NRR_R_OK?VkSurfaceTransformFlagBitsKHR(turn):VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;' in pres, 'NR-20: =2 never rotates'
    assert cs.count('return create_swap();') == 2 and cs.find('nrr::fail("vkCreateSwapchainKHR') < cs.find('if(r)return r;swap_format=sf.format;'), 'NR-20: a failed rotated swapchain -> identity at once'
    assert 'if(nrr::mode){nrr::pre=nrr_pre;' in cs and pres.count('if(nrr::mode)nrr::drop();') == 2, 'NR-20: pre set only with the switch, dropped with every swapchain'
    assert 'nrp::snap.identity=ci.preTransform==VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;' in cs, 'NR-20: NR-11 sees the rotation (refuses: pre-rotated)'
    # present_body: the turned draw only for a rotated swapchain; probes / stats only behind the switch
    pb = pres[pres.find('int present_body(VkImage source,VkFormat source_format,uint32_t width,uint32_t height,const int32_t crop[4],int pre_index,uint64_t pre_gen){'):pres.find('int nrp_direct_present(')]
    assert 'const bool turned=nrr::pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;' in pb and 'if(!turned)vkCmdPipelineBarrier(' in pb and 'if(!turned && (dx || dy' in pb, 'NR-20: old barrier / letterbox clear unless turned'
    assert 'if(turned){' in pb and pb.find('if(turned){') < pb.find('vkCmdBlitImage(') and 'VkPipelineStageFlags stage=turned?VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT:VK_PIPELINE_STAGE_TRANSFER_BIT;' in pb, 'NR-20: draw instead of blit, acquire wait at colour output'
    for m in re.finditer(r'nrr::(\w+)\(', pb):
        line = pb[pb.rfind('\n', 0, m.start()) + 1:pb.find('\n', m.start())]
        if m.group(1) in ('draw', 'fail'): assert 'turned' in pb[pb.rfind('if(turned){', 0, m.start()):m.start()] or 'nrr::draw(' in line, line; continue
        assert 'nrr::mode' in line, 'NR-20: ungated presenter hook: %s' % line.strip()[:160]
    assert 'if(nrr::pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR)return;' in pres[pres.find('void nrp_park_next(){'):], 'NR-20: NR-11 parks nothing for a rotated swapchain'
    for st in ('vert', 'frag'):
        inc = (root / ('android/shaders/nr_rotate.%s.spv.inc' % st)).read_text(encoding='utf-8')
        assert inc.lstrip().startswith('0x07230203,') and (root / ('android/shaders/nr_rotate.%s' % st)).exists(), 'NR-20: SPIR-V of nr_rotate.%s' % st
    head = re.sub(r'//.*', '', logic)
    assert 'vulkan' not in head.lower() and 'Vk' not in head, 'NR-20: the rules are Vulkan-free (host test)'
    # NR-20-rcas: RCAS sharpens inside the turned draw (no refusal when its pipeline is made); the filter is rcas.comp's, the map nrr_rcas_map's
    frag = (root / 'android/shaders/nr_rotate_rcas.frag').read_text(encoding='utf-8')
    comp = (root / 'android/shaders/rcas.comp').read_text(encoding='utf-8')
    inc = (root / 'android/shaders/nr_rotate_rcas.frag.spv.inc').read_text(encoding='utf-8')
    assert inc.lstrip().startswith('0x07230203,'), 'NR-20-rcas: SPIR-V of nr_rotate_rcas.frag'
    def body(t, centre):   # the filter from the neighbourhood fetch to the result, comments dropped, the centre texel renamed
        b = t[t.find('vec3 b = at('):t.find('vec3 c = (lobe')]
        b = re.sub(r'//[^\n]*', '', b).replace(centre + ' + ivec2', 'P + ivec2').replace('at(' + centre + ')', 'at(P)')
        return re.sub(r'\s+', ' ', b).strip()
    assert body(frag, 't').replace('p.sharpness', 'pc.sharpness') == body(comp, 'p') and 'lobeRGB' in body(frag, 't'), 'NR-20-rcas: the turned draw filters exactly as rcas.comp'
    assert 'vec3 c = (lobe * (b + d + f + h) + e) / (4.0 * lobe + 1.0);' in frag and 'color = vec4(clamp(c, 0.0, 1.0), 1.0);' in frag, 'NR-20-rcas: rcas.comp output'
    assert 'layout(offset = 32) ivec4 m;' in frag and 'ivec2 ab = ivec2(gl_FragCoord.xy) - p.o.xy;' in frag and 'ivec2 q = ivec2(p.m.x * ab.x + p.m.y * ab.y, p.m.z * ab.x + p.m.w * ab.y) + p.o.zw;' in frag \
        and 'ivec2 t = clamp(p.s.xy + ivec2(floor((vec2(q) + 0.5) * p.k)), ivec2(0), p.s.zw - 1);' in frag, 'NR-20-rcas: the shader map = nrr_rcas_src_texel'
    assert 'const int32_t qx = pc->m[0] * a + pc->m[1] * b + pc->o[2], qy = pc->m[2] * a + pc->m[3] * b + pc->o[3];' in logic and 'enum { NRR_RCAS_PC_OFFSET = 32 };' in logic, 'NR-20-rcas: the CPU reference of the shader map'
    assert 'static_assert(offsetof(RcasPush,r)==NRR_RCAS_PC_OFFSET && sizeof(RcasPush)==92' in pres, 'NR-20-rcas: push-constant layout'
    assert 'nrr_pre=nrr::decide(cap,sf.format,(cap.supportedUsageFlags&VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT)!=0,rcas::enabled());' in cs, 'NR-20-rcas: decide makes the sharpening draw when RCAS is on'
    assert 'reason=nrr_decide(mode,cur,uint32_t(cap.supportedTransforms),usage_ok,made==NRR_R_SHARPEN,made!=NRR_R_PIPELINE,failed,&turn);' in pres, 'NR-20-rcas: RCAS refuses pre-rotation only when its draw failed'
    assert 'const bool sharpen=rcas::enabled() && (source_format==VK_FORMAT_R8G8B8A8_UNORM || source_format==VK_FORMAT_B8G8R8A8_UNORM);' in pb \
        and "if(!enabled() || (format!=VK_FORMAT_R8G8B8A8_UNORM && format!=VK_FORMAT_B8G8R8A8_UNORM))return false;" in pres, 'NR-20-rcas: sharpens exactly the frames rcas::record would'
    assert pb.find('sharpened=rcas::record(') > pb.find('if(turned){') and 'else{\n    sharpened=rcas::record(' in pb, 'NR-20-rcas: identity swapchains keep RCAS + blit'
    print('PASS: NR-20: DM_NR_ROTATE default 0, identity swapchain unless 1 / 3 decide OK, failure -> identity, draw instead of blit only when turned, hooks gated, NR-11 refuses / parks nothing; RCAS in the turned draw = rcas.comp filter, map = nrr_rcas_src_texel')
def nr19_check():   # [NR-19] port-common desc-memo-keys (VK-DRIVER-KEY d2ffc82 + VK-UBO-MEMO 2f4f2b1 / e6e9611): kept, and nothing bypasses it
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    rule = 'else if(!UBO_DYN(dmode,b) && b.source==XBG_SOURCE_UNIFORM && r.address && r.size){ok=false;++desc_memo_why[5];break;}'
    assert g.count(rule) == 1 and g.index(rule) < g.index('else{key.push_back(r.address);key.push_back(r.size);'), 'NR-19: the VK-UBO-MEMO rule sits once before the address+size key words'
    assert 'b.source==XBG_SOURCE_DRIVER0?buf_gen[ns]:tex_gen[ns]' in g and 'b.source==XBG_SOURCE_DRIVER0?tex_gen[ns]:buf_gen[ns]' not in g, 'NR-19: VK-DRIVER-KEY (DRIVER0 = buf_gen, DRIVER2 = tex_gen)'
    assert '/store%.1f/ubosnap%.1f"' in g and ',desc_memo_why[4]/f,desc_memo_why[5]/f);' in g, 'NR-19: the setcache line reports ubosnap (desc_memo_why[5])'
    # NB-11 DM_NB_DESC=1 skips the key walk: sound only because a reuse needs the previous call's memo entry (P.valid: reset on every
    # call, set by commit() on a hit / insert only) - a set the rule refused never becomes one.
    assert 'nbdesc::P.valid=false;}' in g and g.count('nbdesc::commit(') == 2, 'NR-19: NB-11 reuse starts only from a memoized set'
    print('PASS: NR-19: VK-UBO-MEMO rule (ubosnap) before the address+size key, VK-DRIVER-KEY, NB-11 reuse only from a memo entry')

# NR-27 (DM_NR_UBOVEC, xbg_spirv_ubovec.cpp): scalar uniform-block reads of one vec4 merged into one vec4 load, at shader load.
#   - off (0) returns before anything is computed; the rewrite is the last step of tidy_rewrite (both module loaders, the warm-up
#     threads included), so the bundle bytes and their head (what DM_GFX_NATIVE_SHADERS / DM_NB_POST compare) are never touched;
#   - a rewrite is used only when xbg_spirv_ubovec_check accepts it, and never in mode 2;
#   - the default comes from xbg_nr_ubovec_default: 1 on Mali only (0 on Adreno: Turnip merges the loads itself);
#   - the pass has no engine / Vulkan dependency (tests/ubovec_test.cpp and tests/ubovec_scan.cpp build it alone).
def nr27_check():
    s = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8'); end = chr(10) + '}' + chr(10)
    a = s.index('void ubovec_rewrite(std::vector<uint32_t> &words,const char *key){'); body = s[a:s.index(end, a)]
    assert body.splitlines()[1].strip() == 'if(!nr_ubovec)return;', 'NR-27: DM_NR_UBOVEC=0 leaves ubovec_rewrite at once'
    assert body.count('words.swap(out)') == 1 and 'if(nr_ubovec!=2)words.swap(out);' in body, 'NR-27: the rewritten module is taken in one place, never in mode 2'
    assert body.index('xbg_spirv_ubovec_check(') < body.index('if(*bad){') < body.index('else{const uint64_t n=ubovec_modules') < body.index('words.swap(out)'), 'NR-27: the swap sits in the branch where the check passed'
    assert s.count('ubovec_rewrite(') == 2, 'NR-27: ubovec_rewrite is called once'
    t = s.index('void tidy_rewrite(std::vector<uint32_t> &words,const char *key=nullptr){'); tb = s[t:s.index(end, t)]
    assert tb.rstrip().splitlines()[-1].strip().startswith('ubovec_rewrite(words,key);'), 'NR-27: the rewrite is the last step of tidy_rewrite'
    assert s.count('tidy_rewrite(words,key.c_str())') == 1 and s.count('tidy_rewrite(w,key.c_str())') == 1 and s.count('tidy_rewrite(') == 3, 'NR-27: both module loaders pass their key'
    assert 'nr_ubovec=e&&*e?atoi(e):xbg_nr_ubovec_default(gpu_policy);if(nr_ubovec<0 || nr_ubovec>3)nr_ubovec=0;' in s, 'NR-27: env wins, else the family default; out of range = off'
    assert (chr(10) + 'int nr_ubovec=0;') in s, 'NR-27: nr_ubovec starts 0'
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_ubovec_default(XbgGpuFamily f){return f==XBG_GPU_MALI?1:0;}' in pol, 'NR-27: default 1 on Mali only'
    core = (root / 'gfx/vulkan/engine/xbg_spirv_ubovec.cpp').read_text(encoding='utf-8') + (root / 'gfx/vulkan/engine/xbg_spirv_ubovec.h').read_text(encoding='utf-8')
    code = re.sub('//[^' + chr(10) + ']*', '', core)
    assert 'vulkan' not in code.lower() and 'getenv' not in code and 'xbg_game' not in code, 'NR-27: the pass stays free of the engine, Vulkan and the environment'
    assert '${E}/xbg_spirv_ubovec.cpp' in (root / 'gfx/vulkan/CMakeLists.txt').read_text(encoding='utf-8'), 'NR-27: gfx/vulkan/CMakeLists.txt builds the pass'
    print('PASS: NR-27: DM_NR_UBOVEC off returns at once, last step of tidy_rewrite in both loaders, swap only after the check and not in mode 2, Mali-only default, pass engine-free')

# NR-32 (DM_NR_XLQ, xbg_spirv_vsout.cpp): per pipeline, vertex stores to output components the fragment shader never reads are dropped.
#   - 0 leaves everything as it was: no masks at load, no words kept for it, the draw-time block and the warm-up "#vo" build are behind
#     nr_xlq (and the warm-up refuses "#vo" keys in modes 0 / 2);
#   - a trimmed module is created only after xbg_spirv_vsout_check accepts it, and never in mode 2;
#   - only vertex + fragment pipelines (any other stage in the list keeps the old module); NR-04 fragment shaders are not analysed;
#   - the default comes from xbg_nr_xlq_default: 1 on Mali / PowerVR / Maleoon, 0 on Adreno / Xclipse / other;
#   - the pass has no engine / Vulkan dependency (tests/vsout_test.cpp and tests/vsout_scan.cpp build it alone);
#   - NRVS: it is the tree's only vertex-output trim: NR-33B's "#dz" twin pipelines get it in mode 1 while xlq_twin (DM_NR_MAT 1 / 3 with
#     DM_NR_MAT_VS=1), every other pipeline follows DM_NR_XLQ alone; the trim mode is part of the module cache key; the warm-up builds the
#     twin's "#vo<0>_<0>" key while xlq_twin, and upgrades "<fs>#dz" records to it.
def nr32_check():
    s = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    assert (chr(10) + 'int nr_xlq=0,xlq_twin=0;') in s, 'NR-32: nr_xlq (and the NR-33B twin flag) start 0'
    assert 'nr_xlq=e&&*e?atoi(e):xbg_nr_xlq_default(gpu_policy);if(nr_xlq<0 || nr_xlq>3)nr_xlq=0;' in s, 'NR-32: env wins, else the family default; out of range = off'
    assert 'if((nr_xlq || xlq_twin) && h.stage==0)p->vo_written=' in s and 'if(nr_xlq && h.stage==4 && p->nr_sh<0)p->vo_read=' in s, 'NR-32: masks only while on; NR-04 fragment shaders keep ALL'
    assert 'if(vtx_retype_mode() || nr_xlq || p->psk==1)p->words=words;}' in s, 'NR-32: vertex words kept only for the retype, this switch or an NR-PRESKIN candidate'
    dh = 'if((nr_xlq || xlq_twin) && state.shader[0] && state.shader[4]){const Shader &vs=*state.shader[0],&fs=*state.shader[4];const int xm=fs.nm_is_twin && xlq_twin?1:nr_xlq;'
    assert s.count('vsout_module(*state.shader[0],') == 1 and dh in s, 'NR-32: one draw-time call, behind the switch (NR-33B twins: mode 1 while xlq_twin)'
    d = s.index(dh); db = s[d:s.index('vsout_module(*state.shader[0],', d)]
    assert 'else if(st.stage!=VK_SHADER_STAGE_FRAGMENT_BIT)vf=false;' in db and 'if(vf && vst)' in s[d:d + 1200], 'NR-32: vertex + fragment pipelines only'
    a = s.index('VkShaderModule vsout_module(Shader &s,'); body = s[a:s.index('s.vo.emplace(ck,m);return m;}', a)]
    assert body.index('xbg_spirv_vsout_check(') < body.index('if(mode==2)') < body.index('bundle_module(out,&v,'), 'NR-32: check first, mode 2 counts only, the module after'
    assert 'const auto ck=std::make_tuple(code64,read,decl,mode);' in body and 'xlq_keep(read,mode)' in body and 'nr_xlq' not in body.replace('DM_NR_XLQ', ''), 'NRVS: the trim mode comes from the caller and keys the cache'
    assert 'vsout_module(*state.shader[0],xlq_vi,vst->module,fs.vo_read,fs.vo_decl,xm);' in s, 'NRVS: the draw passes the effective mode'
    assert 'xlq_twin=(m==1 || m==3) && vsmode;' in (root / 'gfx/vulkan/engine/xbg_nr_mat.inc').read_text(encoding='utf-8'), 'NRVS: xlq_twin only from DM_NR_MAT 1 / 3 with DM_NR_MAT_VS'
    assert body.count('bundle_module(') == 1, 'NR-32: one module creation'
    w = s.index('const size_t vo_cut=key.find("#vo");'); wb = s[w:w + 1400]
    assert 'const bool vo_twin=vo && xlq_twin && !vo_read && !vo_decl;' in wb and 'if(vo_cut!=std::string::npos && (!vo || (!xlq_builds() && !vo_twin)))return VK_NULL_HANDLE;' in wb and 'xbg_spirv_vsout_check(' in wb, 'NR-32: warm-up builds "#vo" only while on (or the twin key while xlq_twin), after the check'
    assert 'inline bool xlq_builds(){return nr_xlq==1 || nr_xlq==3;}' in s, 'NR-32: modes 1 / 3 build'
    xw = s[s.index('VkShaderModule xlq_warm_module('):s.index('std::atomic<uint64_t> xlq_upgraded{0};')]
    assert 'if(!xlq_twin && !xlq_builds())return VK_NULL_HANDLE;' in xw and 'load_module(vs+"#vo0000000000000000_0000000000000000")' in xw and xw.index('"#dz"') < xw.index('if(!xlq_builds())return VK_NULL_HANDLE;'), 'NRVS: a twin record upgrades to the read 0 key; others only while DM_NR_XLQ builds'
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_xlq_default(XbgGpuFamily f){return f==XBG_GPU_MALI || f==XBG_GPU_POWERVR || f==XBG_GPU_MALEOON?1:0;}' in pol, 'NR-32: family default'
    core = (root / 'gfx/vulkan/engine/xbg_spirv_vsout.cpp').read_text(encoding='utf-8') + (root / 'gfx/vulkan/engine/xbg_spirv_vsout.h').read_text(encoding='utf-8')
    code = re.sub('//[^' + chr(10) + ']*', '', core)
    assert 'vulkan' not in code.lower() and 'getenv' not in code and 'xbg_game' not in code, 'NR-32: the pass stays free of the engine, Vulkan and the environment'
    assert '${E}/xbg_spirv_vsout.cpp' in (root / 'gfx/vulkan/CMakeLists.txt').read_text(encoding='utf-8'), 'NR-32: gfx/vulkan/CMakeLists.txt builds the pass'
    print('PASS: NR-32: DM_NR_XLQ off = old modules, check before any trimmed module, mode 2 counts only, vertex + fragment only, warm-up gated, family default, pass engine-free; NR-33B twins share the trim')

# T2 (DM_NR_IDVS, xbg_spirv_idvs.cpp, docs/dos2/nr/NR-IDVS.md): the translator's gl_PointSize store dropped from vertex shaders at load.
#   - off (0) = old modules: idvs_rewrite returns before anything when the switch is 0; 2 counts and keeps the words;
#   - the strip runs in both places that make final words (load_shader, warm::bundle_words) right after tidy_rewrite, so every derived
#     module (retype, "#vo", warm-up) is built from the same words; the check gates it;
#   - a point / tessellation / geometry pipeline gets the unstripped module ("#ps", bundle_words idvs=false); warm-up builds plain "#ps" only;
#   - default 0 on every family (owner rule: tile families only when proven on a device).
def nr_idvs_check():
    s = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    body = s[s.index('void idvs_rewrite('):s.index('w.swap(out);}', s.index('void idvs_rewrite('))]
    assert body.index('if(!nr_idvs || stage!=0)return;') < body.index('xbg_spirv_idvs_strip('), 'IDVS: off returns first'
    assert body.index('xbg_spirv_idvs_check(') < body.index('if(nr_idvs==2)'), 'IDVS: the check before any use; mode 2 only counts'
    assert 'tidy_rewrite(words,key.c_str());idvs_rewrite(words,h.stage,key.c_str());' in s, 'IDVS: load_shader strips after tidy_rewrite'
    assert 'tidy_rewrite(w,key.c_str());if(idvs)idvs_rewrite(w,h.stage,key.c_str());' in s, 'IDVS: bundle_words strips after tidy_rewrite (idvs=false keeps it)'
    assert s.count('idvs_rewrite(') == 3, 'IDVS: one definition, two call sites'
    assert 'nr_idvs=e&&*e?atoi(e):xbg_nr_idvs_default(gpu_policy);if(nr_idvs<0 || nr_idvs>2)nr_idvs=0;' in s, 'IDVS: env wins, else the family default; out of range = off'
    g = s.index('nr_idvs=e&&*e?atoi(e):xbg_nr_idvs_default(gpu_policy);')
    assert g < s.index('nrmat::on();   // [DOS2] NR-33B: DM_NR_MAT / DM_NR_MAT_VS read now'), 'IDVS: read at start-up with DM_NR_XLQ, before any load / warm-up'
    assert 'if(nr_idvs==1 && h.stage==0)p->ps_dropped=xbg_spirv_idvs_stripped(' in s, 'IDVS: the fallback flag only in mode 1'
    dh = 'if(nr_idvs==1 && state.shader[0] && state.shader[0]->ps_dropped)'
    assert dh in s and s.count('idvs_point_module(*state.shader[0],xlq_vi)') == 1, 'IDVS: one draw-time fallback, behind the switch'
    d = s[s.index(dh):s.index('++idvs_point_pipes;', s.index(dh))]
    assert 'VK_PRIMITIVE_TOPOLOGY_POINT_LIST' in d and 'fillModeNonSolid' in d and 'VK_SHADER_STAGE_FRAGMENT_BIT' in d, 'IDVS: points, polygon POINT and pre-raster stages keep PointSize'
    assert s.index(dh) > s.index('vsout_module(*state.shader[0],xlq_vi,vst->module,'), 'IDVS: the fallback after the NR-32 trim (replaces its module)'
    pm = s[s.index('VkShaderModule idvs_point_module('):s.index('s.ps_full.emplace(code64,m);return m;}')]
    assert 'warm::bundle_words(s.key,w,stage,"idvs-points",false)' in pm and 'key+="#ps";' in pm, 'IDVS: unstripped words, "#ps" key'
    wl = s[s.index('VkShaderModule load_module(const std::string &key){'):s.index('struct Reader{')]
    assert 'if(nr_idvs!=1 || key.find('#')!=key.size()-3)return VK_NULL_HANDLE;' in wl and '"warm",false)' in wl, 'IDVS: warm-up builds plain "#ps" only in mode 1'
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_idvs_default(XbgGpuFamily f){return f==XBG_GPU_MALI || f==XBG_GPU_POWERVR || f==XBG_GPU_MALEOON?1:0;}' in pol, 'IDVS: default 1 on Mali / PowerVR / Maleoon (19.11)'
    core = (root / 'gfx/vulkan/engine/xbg_spirv_idvs.cpp').read_text(encoding='utf-8') + (root / 'gfx/vulkan/engine/xbg_spirv_idvs.h').read_text(encoding='utf-8')
    code = re.sub('//[^' + chr(10) + ']*', '', core)
    assert 'vulkan' not in code.lower() and 'getenv' not in code and 'xbg_game' not in code, 'IDVS: the pass stays free of the engine, Vulkan and the environment'
    assert '${E}/xbg_spirv_idvs.cpp' in (root / 'gfx/vulkan/CMakeLists.txt').read_text(encoding='utf-8'), 'IDVS: gfx/vulkan/CMakeLists.txt builds the pass'
    print('PASS: T2 DM_NR_IDVS: off = old modules, check before use, mode 2 counts only, both word makers strip, point / pre-raster fallback, warm-up gated, default 0, pass engine-free')

# NR-23 (docs/dos2/nr/NR-23.md, DM_NR_NOCALL, default 0): the wiring that keeps "off" the old behaviour and "on" provable.
#   - hle_nvn.c: four NCT(...) capture lines (BindTexture, DrawElements, DrawElementsInstanced, SetRenderEnable), dead unless g_nc_cap;
#     the per-thread call counter is one guarded line in nvn_bigstack_top; nvn_nr_nocall.inc is included twice (capture / entries) and
#     its flags are written only by nvn_nc_enable; the direct entries call the h_ bodies and nothing else;
#   - hle_dos2_native.c: without a native handler the draw hook calls the engine's function exactly as before;
#   - hle_dos2_nr_nocall.inc: g_nc_want only from nc_arm after the three code hashes matched, g_nr_nocall only from nc_install (last
#     statement before its log); the flush hook runs nk_draw first and ends in the forwarded original; nc_flush_take and nc_draw_take
#     return 0 (the engine's function runs) before the first write to the renderer and the first native call;
#   - hle_dos2_nr.c: armed behind the DM_NR gate, nc_arm before the flush hook goes in, nc_install after it;
#   - the model nr_nocall.h stays free of the engine, the host, threads and the environment; the app never sets the switch.
def nr23_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    nvn = code((root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8'))
    assert nvn.count('NCT(') == 4, 'NR-23: four capture lines in hle_nvn.c, found %d' % nvn.count('NCT(')
    for fn, line in (('nvnCommandBufferBindTexture,', 'NCT(nc_cap_bind(c, (int)st, i, (uint64_t)h));'), ('nvnCommandBufferDrawElements,', 'NCT(nc_cap_draw(c, (int)pr, (int)it, n, (uint64_t)ib, -1));'),
                     ('nvnCommandBufferDrawElementsInstanced,', 'NCT(nc_cap_draw(c, (int)pr, (int)it, n, (uint64_t)ib, bv || bi ? -2 : inst));'), ('nvnCommandBufferSetRenderEnable,', 'NCT(nc_cap_ren(c, en));')):
        assert body(nvn, 'NVN(' + fn).count(line) == 1, 'NR-23: %s has its capture line' % fn.rstrip(',')
    top = body(nvn, 'void *nvn_bigstack_top(uintptr_t sp) {')
    assert top.count('t_nc_calls') == 1 and 'if (__builtin_expect(g_nc_count, 0)) t_nc_calls++;' in top, 'NR-23: the call counter is one guarded line in nvn_bigstack_top'
    nvn_raw = (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8')
    assert nvn_raw.count('#include "nvn_nr_nocall.inc"') == 2 and nvn_raw.count('#define NVN_NC_ENTRIES 1') == 1 and \
        nvn_raw.index('#include "nvn_nr_nocall.inc"') < nvn_raw.index('NVN(nvnCommandBufferBindTexture,') < nvn_raw.index('#define NVN_NC_ENTRIES 1') < nvn_raw.rindex('#include "nvn_nr_nocall.inc"'), \
        'NR-23: nvn_nr_nocall.inc twice: the capture before the entry points, the direct entries at the end'
    inc = code((root / 'gfx/nvn/nvn_nr_nocall.inc').read_text(encoding='utf-8'))
    assert re.search(r'^static int g_nc_cap;', inc, flags=re.M) and '#define NCT(x) do { if (__builtin_expect(g_nc_cap, 0)) { x; } } while (0)' in inc, 'NR-23: NCT is dead while g_nc_cap is 0'
    en = body(inc, 'void nvn_nc_enable(int mode) {')
    assert len(re.findall(r'\bg_nc_cap\s*=(?!=)', inc)) == 1 and len(re.findall(r'\bg_nc_count\s*=(?!=)', inc + nvn)) == 1 and 'g_nc_cap = mode == 2; g_nc_count = mode == 2;' in en, \
        'NR-23: the capture and the counter are armed only by nvn_nc_enable, only for mode 2'
    for fn in ('void nvn_nc_bind(', 'void nvn_nc_ren(', 'void nvn_nc_draw('):
        b = body(inc, fn)
        called = set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', b)) - {'if', 'uintptr_t', 'NVNcommandBuffer', 'NVNshaderStage', 'NVNdrawPrimitive', 'NVNindexType', 'NVNbufferAddress'}
        assert called and all(c.startswith('h_nvn') for c in called), 'NR-23: %s calls the entry point bodies only: %s' % (fn, sorted(called))
    rd = body(inc, 'int nvn_nc_ready(')
    assert rd.count('nc_impl(i) != want[k]') == 1 and 'int ok = g_nc_mode != 0;' in rd, 'NR-23: nvn_nc_ready compares every slot implementation with the body the direct entry calls'
    nat = code((root / 'host/hle_dos2_native.c').read_text(encoding='utf-8'))
    dc = body(nat, 'static uint64_t dn_draw_common(')
    assert 'if (!nv) v = orig(r, a1, a2, a3, a4, a5);' in dc and 'else if (!nv->take(op, r, a1, a2, a4)) { v = orig(r, a1, a2, a3, a4, a5); nv->after(op, r); }' in dc and dc.count('orig(') == 2, \
        'NR-23: without a native handler (or when it declines) the draw hook calls the engine function with its arguments'
    assert len(re.findall(r'\bg_draw_nv\s*=(?!=)', nat)) == 1 and 'g_draw_nv = h;' in body(nat, 'int dn_install_draw_native(const dn_draw_native *h) {'), 'NR-23: the native draw handler is set only by dn_install_draw_native'
    nc = code((root / 'host/hle_dos2_nr_nocall.inc').read_text(encoding='utf-8'))
    arm = body(nc, 'static void nc_arm(module_t *m) {'); inst = body(nc, 'static void nc_install(void) {')
    assert len(re.findall(r'\bg_nc_want\s*=(?!=)', nc)) == 2 and arm.rstrip('} \n').endswith('g_nc_want = v;') and 'g_nc_want = 0;' in inst and arm.index('if (h != code[i].fnv)') < arm.index('g_nc_want = v;'), \
        'NR-23: g_nc_want is set at the end of nc_arm, after the code hashes matched (and cleared when the flush hook is missing)'
    assert 'if (v != 1 && v != 2)' in arm and re.match(r'\{\s*const char \*e = getenv\(""\);\s*const int v = e \? atoi\(e\) : 0;\s*if \(!v\) return;', arm), 'NR-23: DM_NR_NOCALL unset / 0 returns at once'
    assert len(re.findall(r'\bg_nr_nocall\s*=(?!=)', nc)) == 1 and 'g_nr_nocall = v;' in inst and 'if (!g_nr_key) { g_nc_want = 0;' in inst, 'NR-23: g_nr_nocall is set only by nc_install, and only with the flush hook in'
    hook = body(nc, 'NR_HOOK nr_h_tf_nc(NR_A) {')
    assert re.match(r'\{\s*const uint64_t lr = \(uint64_t\)\(uintptr_t\)__builtin_return_address\(0\);\s*nk_draw\(a0, lr\);', hook) and hook.rstrip('} \n').endswith('return g_o_tf(NR_F);') and \
        'if (g_nr_nocall == 1) { if (nc_flush_take(a0, lr)) return 0; }' in hook, 'NR-23: the flush hook = nk_draw, then the native flush only for mode 1, else the forwarded original'
    assert 'static void *nc_tf_hook(void *dflt) { return g_nc_want ? (void *)nr_h_tf_nc : dflt; }' in nc, 'NR-23: the old hook function unless DM_NR_NOCALL is armed'
    ft = body(nc, 'static int nc_flush_take(uint64_t r, uint64_t lr) {')
    first = min(ft.index('nvn_on_bigstack('), ft.index('nrnc_flush_reset('))
    assert ft.count('return 0;') == 5 and ft.rindex('return 0;') < first and ft.index('nc_live()') < ft.index('nrnc_flush_plan(') < first, \
        'NR-23: nc_flush_take declines (5 reasons) before the first bind and the first store'
    dt = body(nc, 'static int nc_draw_take(')
    m1 = dt[dt.index('if (!(g_nc_parts & 2)) return 0;'):]
    first = min(m1.index('g_nc_ubo_fill('), m1.index('nk_draw('), m1.index('nvn_on_bigstack('), m1.index('g_o_tf('))
    assert m1.count('return 0;') == 3 and m1.rindex('return 0;') < first and m1.index('nc_live()') < m1.index('nrnc_draw_pre(') < first and m1.rstrip('} \n').endswith('return 1;'), \
        'NR-23: nc_draw_take declines before the uniform functions, the identity, the flush and the tail'
    m2 = dt[:dt.index('if (!(g_nc_parts & 2)) return 0;')]
    assert 'nvn_on_bigstack(' not in m2 and 'g_nc_ubo_fill(' not in m2 and 'g_o_tf(' not in m2 and m2.count('return 0;') == 2, 'NR-23: mode 2 of nc_draw_take only reads and always lets the engine function run'
    for fn in ('static void nc2_flush_pre(', 'static void nc2_flush_post(', 'static void nc_draw_after('):
        b = body(nc, fn)
        assert 'nvn_nc_bind(' not in b and 'nvn_on_bigstack(' not in b and not re.search(r'\bR\s*\[[^\]]*\]\s*=(?!=)|nrnc_flush_reset|nrnc_flush_run|nrnc_draw_tail|nrnc_w16', b), 'NR-23: %s only reads' % fn.split('(')[0]
    host = code((root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8'))
    ni = body(host, 'void dm_dos2_nr_install(void) {')
    gate = 'if (mode != 1 && mode != 2) return;'
    assert ni.count('nc_arm(m);') == 1 and ni.count('nc_install();') == 1 and ni.index(gate) < ni.index('nc_arm(m);') < ni.index('nk_install(') < ni.index('nk_draw_install(') < ni.index('nc_install();'), \
        'NR-23: armed behind the DM_NR gate: nc_arm before the flush hook goes in, nc_install after it'
    key = code((root / 'host/hle_dos2_nr_key.inc').read_text(encoding='utf-8'))
    assert 'dn_hook(m, s->off, s->pro, nc_tf_hook(s->hook), &o)' in key and 'if (g_nr_nocall) nc_report(frames);' in key, 'NR-23: the flush hook function is picked by nc_tf_hook; the report line is gated'
    core_raw = (root / 'gfx/nr/nr_nocall.h').read_text(encoding='utf-8'); core = code(core_raw)
    assert 'vulkan' not in core.lower() and 'hle.h' not in core_raw and 'pthread' not in core and 'getenv' not in core and not re.search(r'#include "', core_raw), 'NR-23: nr_nocall.h stays free of the engine, the host, threads and the environment'
    for fn in ('static inline int nrnc_flush_plan(', 'static inline uint64_t nrnc_ib_rec(', 'static inline int nrnc_draw_pre(', 'static inline void nrnc_draw_expect(', 'static inline int nrnc_flush_clean(', 'static inline uint64_t nrnc_cb('):
        assert 'const uint8_t *R' in core[core.index(fn):core.index(')', core.index(fn))], 'NR-23: %s takes the renderer read-only' % fn.split('(')[0]
    jni = code((root / 'android/jni_android.c').read_text(encoding='utf-8'))
    assert 'DM_NR_NOCALL' not in (root / 'android/jni_android.c').read_text(encoding='utf-8'), 'NR-23: the app does not set DM_NR_NOCALL'
    asm = (root / 'gfx/nvn/nvn_entry.S').read_text(encoding='utf-8')
    ob = asm[asm.index('_nvn_on_bigstack:'):]
    assert ob.count('bl _nvn_bigstack_top') == 1 and ob.index('mov sp, x9') < ob.index('blr x17') < ob.index('mov sp, x29') and ob.rstrip().endswith('ret'), 'NR-23: nvn_on_bigstack switches, calls, switches back'
    assert (root / 'gfx/vulkan/engine/tests/nr_nocall_test.c').is_file() and (root / 'gfx/vulkan/engine/tests/nr_nocall_oracle.py').is_file(), 'NR-23: the model tests exist'
    print('PASS: NR-23: 4 capture lines + 1 counter line dead unless DM_NR_NOCALL=2, direct entries = the entry point bodies (nvn_nc_ready), the draw hook unchanged without a '
          'native handler, DM_NR_NOCALL armed behind the DM_NR gate after the code hashes, the flush hook = nk_draw + original unless mode 1 takes it, both native paths '
          'decline before their first write / call, mode 2 only reads, model engine-free')


# NR-24 (docs/dos2/nr/NR-24.md): the HLE fast gates. Off by default: DM_NR_GATE_TICK / ARB / YIELD are read once, never set by the app;
# with them off the KGATE slot holds _dm_gate, the clock gate and svc 0x1E keep their old formula, the loader binds nothing new, the
# six arbitration SVCs and the yields take the G path / yield_for as before.
def nr24_check():
    def code(s): return re.sub(r"""/\*.*?\*/|//[^\n]*""", "", s, flags=re.S)
    jni = code((root / 'android/jni_android.c').read_text(encoding='utf-8'))
    for sw in ('DM_NR_GATE_TICK', 'DM_NR_GATE_ARB', 'DM_NR_GATE_YIELD'):
        assert sw not in jni, 'NR-24: the app does not set %s' % sw
    hle = code((root / 'host/hle.c').read_text(encoding='utf-8'))
    assert 'void *dm_gate_entry(void) { return dm_tick_init() == 1 ? (void *)dm_gate_fast : (void *)dm_gate; }' in hle, 'NR-24: _dm_gate_fast only with DM_NR_GATE_TICK=1'
    disp = hle[hle.find('uint64_t gate_dispatch('):]
    assert 'if (g_tick_mode == 1) {' in disp and 'uint64_t t = guest_ns() * 12 / 625;' in disp, 'NR-24: the clock gate keeps the old formula unless mode 1'
    os_ = code((root / 'host/hle_os.c').read_text(encoding='utf-8'))
    assert re.search(r'getenv\("DM_NR_GATE_TICK"\); int m = e && \*e \? atoi\(e\) : 0;\s*if \(m <= 0\) return;', os_), 'NR-24: DM_NR_GATE_TICK unset = no tick block, mode 0'
    assert 'if (dm_tick_init() != 1 || strcmp(mod, "main")) return NULL;' in os_, 'NR-24: the loader binds GetSystemTick only in mode 1 and only main'
    assert 'static void tick_freeze(int on) {\n    if (!g_tick_mode) return;' in os_.replace('\r', ''), 'NR-24: freezes touch the tick blocks only when the domain runs'
    ld = code((root / 'host/loader.c').read_text(encoding='utf-8'))
    assert ld.count('dm_tick_bind(') == 1 and ld.find('dm_tick_bind(') > ld.find('force_lookup(m->strtab'), 'NR-24: one bind hook, after the forced take-over'
    th = code((root / 'host/hle_thread.c').read_text(encoding='utf-8'))
    assert 'if (__builtin_expect(g_arb_mode > 0, 0) && arb_svc(num, regs)) return 1;' in th and 'if (__builtin_expect(g_yw_mode == 1, 0)) yw_progress(num, regs);' in th, 'NR-24: both hooks test their mode first'
    assert 'if (!moved && !(g_yw_mode > 0 && yw_wait(me, y0 - me->yrun_t0))) yield_for(me, y0 - me->yrun_t0);' in th, 'NR-24: the yield wait only with DM_NR_GATE_YIELD'
    inc = code((root / 'host/hle_thread_arb.inc').read_text(encoding='utf-8'))
    assert re.search(r'getenv\("DM_NR_GATE_ARB"\); int m = e && \*e \? atoi\(e\) : 0;', inc) and 'arb_init();' in th, 'NR-24: DM_NR_GATE_ARB read once at the main thread registration'
    for case in ('0x1A', '0x1B', '0x1C', '0x1D', '0x34', '0x35'):
        assert 'case %s:' % case in inc, 'NR-24: the bucket path handles svc %s' % case
    assert 'st32(key, 1);\n        t->wkey = key; t->waddr = addr; t->wtag = (uint32_t)regs[2];\n        if (to != 0) arb_link(bk, t, 2);\n        arb_lock_handoff(bl, addr);' in inc.replace('\r', ''), \
        'NR-24: 0x1C on buckets publishes key = 1 and links before it releases the lock (t_condvar order)'
    es = (root / 'host/entry.S').read_text(encoding='utf-8')
    fast = es[es.find('_dm_gate_fast:'):es.find('Lfg_tail:')]
    for bad in ('subs ', 'adds ', 'cmp ', 'cmn ', 'tst ', 'ands ', 'ccmp', 'msr nzcv', ' q0', ' v0', ' d0', ' s0'):
        assert bad not in fast, 'NR-24: _dm_gate_fast must not touch NZCV or SIMD registers (%r)' % bad
    assert fast.count('b _dm_gate\n') == 1 or fast.count('b _dm_gate\r\n') == 1, 'NR-24: one pass-on branch to _dm_gate'
    print('PASS: NR-24: DM_NR_GATE_TICK / ARB / YIELD default off (not set by the app), _dm_gate_fast only in tick mode 1 and flag- / SIMD-free, clock formula and loader unchanged when off, '
          'arbiter / yield hooks mode-first, 0x1C key-before-release order on buckets')


nb20a_check()
nb19_check()
nr19_check()
nb20b_check()
nb20b_ctx_check()
storehist_check()
# NR-02 (draw identity, DM_NR_KEY, default 0): the wiring that keeps "off" byte-identical and the key layer host-testable.
#   - hle_nvn.c: one NRT(dm_nr_tap_bind(c, p, stages)) as the first statement of nvnCommandBufferBindProgram and one NRT(dm_nr_tap_draw(c))
#     as the first statement of each of the seven draw entry points; both tap functions return at once unless g_nr_key;
#   - hle_dos2_nr_key.inc: g_nr_key is set only in nk_install (called by dm_dos2_nr_install, i.e. behind the DM_NR gate, and only when
#     nk_mode() read DM_NR_KEY 1 / 2); the hook of the texture flush is NR_HOOK, calls its trampoline once with NR_F, and is listed in
#     k_nr_key_site; the key front end never writes guest memory (no store through R / the renderer);
#   - the key core nr_key.{h,c}: no engine, host, environment or game address; built by the dm/gfx/nr glob.
def nr02_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    nvn = code((root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8'))
    b = body(nvn, 'NVN(nvnCommandBufferBindProgram,')
    assert re.match(r'\{\s*NRT\(dm_nr_tap_bind\(c, p, stages\)\);', b) and b.count('NRT(') == 1, 'NR-02: BindProgram starts with its one tap line'
    draws = ('nvnCommandBufferDrawArrays', 'nvnCommandBufferDrawElementsInstanced', 'nvnCommandBufferDrawElements', 'nvnCommandBufferDrawElementsBaseVertex',
             'nvnCommandBufferDrawArraysInstanced', 'nvnCommandBufferDrawArraysIndirect', 'nvnCommandBufferDrawElementsIndirect')
    for fn in draws:
        b = body(nvn, 'NVN(%s,' % fn)
        assert re.match(r'\{\s*NRT\(dm_nr_tap_draw\(c\)\);', b) and b.count('NRT(') == 1, 'NR-02: %s starts with its one tap line' % fn
    assert nvn.count('NRT(dm_nr_tap_draw(c));') == len(draws) and nvn.count('NRT(dm_nr_tap_bind(') == 1, 'NR-02: no other key tap lines'
    inc_raw = (root / 'host/hle_dos2_nr_key.inc').read_text(encoding='utf-8'); inc = code(inc_raw)
    host = code((root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8'))
    for fn in ('void dm_nr_tap_bind(', 'void dm_nr_tap_draw('):
        b = body(inc, fn)
        assert re.match(r'\{\s*if \(g_nr_key( != 2)?\) return;|\{\s*if \(!g_nr_key\) return;', b), 'NR-02: %s returns at once while DM_NR_KEY is off' % fn
    assert re.search(r'^static int g_nr_key;', host, flags=re.M), 'NR-02: g_nr_key starts 0'
    inst = body(inc, 'static void nk_install(')
    assert len(re.findall(r'\bg_nr_key\s*=(?!=)', inc)) == 2 and len(re.findall(r'\bg_nr_key\s*=(?!=)', inst)) == 2 and not re.findall(r'\bg_nr_key\s*=(?!=)', host), \
        'NR-02: g_nr_key is set only in nk_install (on, or back to 0 when the hook fails)'
    assert 'dn_hook(' in inst and inst.index('dn_words_ok(') < inst.index('dn_hook('), 'NR-02: the flush site is compared before it is patched'
    assert 'dn_hook(' not in inc.replace(inst, ''), 'NR-02: the key front end hooks only in nk_install'
    ni = body(host, 'void dm_dos2_nr_install(void) {')
    gate = 'if (mode != 1 && mode != 2) return;'
    assert ni.index(gate) < ni.index('nk_mode()') < ni.index('nk_install(') and ni.count('nk_install(') == 1, 'NR-02: DM_NR_KEY is read and armed only behind the DM_NR gate'
    assert 'if (key) nk_install(m, key, rc == 0);' in ni and 'dn_install_rc(key ? &k_nk_rc : &k_nr_rc)' in ni, 'NR-02: off = the NR-01 handler and no key install'
    assert re.search(r'NR_HOOK nr_h_tf\(NR_A\) \{\s*nk_draw\(a0, \(uint64_t\)\(uintptr_t\)__builtin_return_address\(0\)\);\s*return g_o_tf\(NR_F\);\s*\}', inc), \
        'NR-02: the flush hook reads, then calls its own trampoline once with the forwarded arguments'
    assert body(inc, 'k_nr_key_site[] =').count('(void *)nr_h_tf, &g_o_tf}') == 1, 'NR-02: nr_h_tf is listed in k_nr_key_site'
    d = body(inc, 'static void nk_draw(')
    assert not re.search(r'\bR\s*\[[^\]]*\]\s*=(?!=)|\(\s*R\s*\+[^)]*\)\s*=(?!=)|memcpy\(\s*R\b|memcpy\(\s*\(void \*\)\s*R', d) and 'const uint8_t *R' in d, 'NR-02: the state cache is only read'
    assert 'malloc(' not in inc and 'calloc(' not in inc, 'NR-02: the front end allocates only through nr_keys_new'
    tc = body(host, 'static void nr_tex_commit(')
    assert tc.index('pthread_mutex_unlock(&g_nr_mu);') < tc.index('nk_texture('), 'NR-02: lock order key -> registry: nr_tex_commit calls nk_texture after releasing g_nr_mu'
    rp = body(host, 'static void nr_report(')
    assert rp.index('pthread_mutex_unlock(&g_nr_mu);') < rp.index('nk_report('), 'NR-02: lock order: nk_report runs after nr_report released g_nr_mu'
    for name in ('nr_key.h', 'nr_key.c'):
        core_raw = (root / 'gfx/nr' / name).read_text(encoding='utf-8'); core = code(core_raw)
        assert 'vulkan' not in core.lower() and 'hle.h' not in core_raw and 'pthread' not in core and 'getenv' not in core, 'NR-02: %s stays engine / host free' % name
        assert not re.search(r'0x9[0-9a-f]{5}\b|0x1[0-9a-f]{6}\b', core), 'NR-02: %s holds no game address' % name
    assert (root / 'gfx/vulkan/engine/tests/nr_key_test.cpp').is_file(), 'NR-02: nr_key_test.cpp exists'
    print('PASS: NR-02: 8 guarded key tap lines (first statements), DM_NR_KEY behind the DM_NR gate, one NR_HOOK on the flush (own trampoline once, '
          'listed), state cache read only, key core engine-free')


# NR-06 (docs/dos2/nr/NR-06.md, DM_NR_BUF, default 0): the wiring that keeps "off" byte-identical.
#   - xbg_game.cpp: xbg_nr_buf.inc included once after the zero-copy namespace and before snapshot(); one guarded line as the first
#     step of snapshot() (vertex / index sites only, never with snap_no_sync) and of uniform_snapshot() (before NB-12's nbubo line);
#     snapshot_invalidate, the submission entry, the pool finalize and the shutdown each call nrbuf once;
#   - xbg_nr_buf.inc: every mode starts off and DM_NR_BUF defaults to 0 (init returns before anything else); the CPU-write hook is
#     gated by the mode;
#   - hle_dos2_nr.c: g_nr_buf starts 0, is set once (in the install, after the DM_NR gate), and every event / ring hand-over is gated
#     by it; the decision core nr_buf.{h,c} stays engine-free.
def nr06_check():
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    inc = (eng / 'xbg_nr_buf.inc').read_text(encoding='utf-8')
    host = (root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8')
    inc_at = s.find('#include "xbg_nr_buf.inc"')
    assert s.count('#include "xbg_nr_buf.inc"') == 1 and s.find('namespace zc {') < inc_at < s.find('Buffer snapshot(uint64_t address,size_t bytes,VkDeviceSize align=4)'), \
        'NR-06: xbg_nr_buf.inc once, after namespace zc and before snapshot()'
    snap = s[s.find('Buffer snapshot(uint64_t address,size_t bytes,VkDeviceSize align=4){'):].split('\n')
    assert snap[1].lstrip().startswith('if(nrbuf::st_mode>0 && !nrbuf::busy && (snap_site==1 || snap_site==2) && !snap_no_sync){'), 'NR-06: the static line is the first step of snapshot(), gated'
    us = s[s.find('Buffer uniform_snapshot(uint64_t address,size_t copy){'):].split('\n')
    assert us[1].lstrip().startswith('if(nrbuf::ring_mode>0 && !nrbuf::busy){') and us[2].lstrip().startswith('if(nbubo::mode>0'), 'NR-06: the ring line is the first step of uniform_snapshot(), before nbubo'
    inv = body(s, 'void snapshot_invalidate(uint64_t address,uint64_t bytes){')
    assert inv.count('nrbuf::cpu_write_hook(address,bytes);') == 1, 'NR-06: snapshot_invalidate tells nrbuf once'
    assert re.search(r'void cpu_write_hook\(uint64_t a,uint64_t n\)\{if\(mode>0\)cpu_write\(a,n\);\}', inc), 'NR-06: the CPU-write hook is gated by the mode'
    for call, n in (('nrbuf::submission();', 1), ('nrbuf::release();', 1), ('nrbuf::drop_pool(', 1)):
        assert s.count(call) == n, 'NR-06: `%s` %d time(s) in xbg_game.cpp' % (call, n)
    assert 'nrbuf::submission();snapshot_reset();' in s, 'NR-06: nrbuf::submission at the guest submission entry (before its snapshot_reset)'
    assert 'int mode=-1,ring_mode=0,st_mode=0;' in inc and 'mode=num("DM_NR_BUF",0,0,3);if(!mode)return;' in inc, 'NR-06: DM_NR_BUF defaults to 0, all paths start off'
    assert 'state' not in re.sub(r'//[^\n]*|"[^"\n]*"', '', inc).replace('static_', ''), 'NR-06: xbg_nr_buf.inc must not name `state` (a context macro of xbg_game.cpp)'
    # host
    assert re.search(r'^static int g_nr_buf;', host, flags=re.M), 'NR-06: g_nr_buf has no initialiser (0 = off)'
    assert len(re.findall(r'\bg_nr_buf\s*=(?!=)', host)) == 1, 'NR-06: g_nr_buf is set once'
    inst = body(host, 'void dm_dos2_nr_install(void) {')
    assert 'g_nr_buf =' in inst and inst.index('if (mode != 1 && mode != 2) return;') < inst.index('g_nr_buf ='), 'NR-06: g_nr_buf only after the DM_NR gate'
    assert 'if (!g_nr_buf || !xbg_nr_buf_event) return;' in body(host, 'static void nr_buf_created(') and 'if (g_nr_buf && xbg_nr_buf_event)' in body(host, 'static void nr_buf_destroyed(') \
        and 'if (!g_nr_buf || !xbg_nr_ring_set || !r) return;' in body(host, 'static void nr_ring_probe(uint64_t r) {'), 'NR-06: events and the ring hand-over are gated by g_nr_buf'
    for f in ('gfx/nr/nr_buf.h', 'gfx/nr/nr_buf.c'):
        t = re.sub(r'//[^\n]*', '', (root / f).read_text(encoding='utf-8'))
        assert not re.search(r'\bVk|vulkan|xbg_|#include "(?!nr_buf\.h)', t), 'NR-06: %s stays engine-free' % f
    print('PASS: NR-06: xbg_nr_buf.inc wired at 6 points (first steps of snapshot / uniform_snapshot gated), DM_NR_BUF default 0, host events gated, core engine-free')

# NR-08 (docs/dos2/nr/NR-08.md, DM_NR_DESC, default 0): the wiring that keeps "off" byte-identical.
#   - xbg_game.cpp: xbg_nr_desc.inc included once, between namespace nbdesc and descriptors(); descriptors() makes one nrdesc::Scope right
#     after its memo gate (mode 0: the constructor returns at once, the destructor does nothing); descriptors_build hands its writes over
#     only while nrdesc::cap_on; dyn_mode_for returns the new mode 3 only while nrdesc::split_on; UBO_DYN's mode-3 clause; release at
#     shutdown before NR-06's; no other use of nrdesc outside the .inc;
#   - xbg_nr_desc.inc: the mode starts unread (-1), DM_NR_DESC defaults to 0, cap_on / split_on start false; cap_on is raised only around
#     the two capture builds and dropped right after them; split_on only by init (DM_NR_DESC=1) and release;
#   - the decision core nr_desc.{h,c} stays engine-free and is pre-included by xbg_nb_mx.inc (ahead of the context defines).
def nr08_check():
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    inc = (eng / 'xbg_nr_desc.inc').read_text(encoding='utf-8')
    inc_at = s.find('#include "xbg_nr_desc.inc"')
    assert s.count('#include "xbg_nr_desc.inc"') == 1 and s.find('namespace nbdesc{') < inc_at < s.find('void descriptors(Descriptors &out,Commands &commands,bool compute){struct InDesc'), \
        'NR-08: xbg_nr_desc.inc once, after namespace nbdesc and before descriptors()'
    d = s[s.find('void descriptors(Descriptors &out,Commands &commands,bool compute){struct InDesc'):].split('\n')
    gate = [i for i, l in enumerate(d[:40]) if l.lstrip().startswith('bool ok=desc_memo_enabled && !compute')]
    assert len(gate) == 1 and d[gate[0] + 1].lstrip().startswith('nrdesc::Scope nrs(ok,compute,out,commands);if(nrs.served)return;'), 'NR-08: the Scope line follows the memo gate of descriptors()'
    b = s[s.find('void descriptors_build(Descriptors &out,Commands &commands,bool compute){CPU_SCOPE(Descriptor);'):].split('\n')
    srt = [i for i, l in enumerate(b[:400]) if l.lstrip().startswith('std::sort(dynamic_list.begin(),dynamic_list.end());out.dynamic_offsets.clear();')]
    assert len(srt) == 1 and b[srt[0] + 1].lstrip().startswith('if(nrdesc::cap_on){nrdesc::captured(writes);return;}'), 'NR-08: the capture line follows the dynamic offsets of descriptors_build, gated by cap_on'
    dm = body(s, 'unsigned dyn_mode_for(bool compute,bool *no_ubo=nullptr){')
    assert dm.count('nrdesc::') == 2 and 'if(nrdesc::split_on && !compute && vary>lim && !(all && all<=lim) && nrdesc::split_pick(lim))return 3;' in dm \
        and dm.index('if(!ubo_dynamic_on)return 0;') < dm.index('nrdesc::split_on'), 'NR-08: dyn_mode_for gives mode 3 only under split_on, after the dynamic-off policy'
    assert '|| ((mode)==3 && nrdesc::split_has(&(b))))' in s and s.count('nrdesc::split_has(') == 1, 'NR-08: UBO_DYN has the one mode-3 clause'   # NR-08b appends its clause after it
    assert s.count('nrdesc::release();') == 1 and 'nrdesc::release();nrbuf::release();' in s, 'NR-08: released at shutdown, before NR-06'
    assert s.count('nrdesc::') == 7 and s.count('namespace nrdesc{') == 1, 'NR-08: no other use of nrdesc in xbg_game.cpp (found %d)' % s.count('nrdesc::')
    assert 'int mode=-1,cmp_n=8;bool cap_on=false,split_on=false;' in inc, 'NR-08: the mode starts unread, cap_on / split_on false'
    ini = body(inc, 'void init(){')
    assert 'const char *e=getenv("DM_NR_DESC");int m=e && *e?atoi(e):0;' in ini and ini.rstrip().endswith('mode=m;}') and len(re.findall(r'(?<![:\w])mode=(?!=)', re.sub(r'"(?:\.|[^"\
])*"', '""', ini))) == 1, 'NR-08: DM_NR_DESC defaults to 0; init sets the mode once'
    assert re.search(r'Scope\(bool ok,bool compute,Descriptors &o,Commands &c\):out\(o\),commands\(c\)\{\s*if\(mode==0\)return;', inc), 'NR-08: mode 0 leaves the Scope constructor at once'
    assert '~Scope(){if(cmp)compare(out,commands);}' in inc and 'bool served=false,cmp=false;' in inc, 'NR-08: the Scope destructor only compares (mode 2)'
    code_inc = re.sub(r'//[^\n]*', '', inc)
    assert len(re.findall(r'\bcap_on=true', code_inc)) == 2 and len(re.findall(r'\bcap_on=false', code_inc)) == 3 \
        and all(re.search(r'cap_on=true;.{0,60}descriptors_build\(\w+,commands,false\);\s*cap_on=false;', body(code_inc, h), flags=re.S) for h in ('int build_entry(', 'void compare(')), \
        'NR-08: cap_on is raised only around the two capture builds'
    assert len(re.findall(r'\bsplit_on=(?!=)', code_inc)) == 3 and 'split_on=m==1 && ubo_dynamic_on' in ini and 'split_on=false;}' in body(code_inc, 'void release(){'), \
        'NR-08: split_on only from init (DM_NR_DESC=1) and release'
    assert 'state.' not in re.sub(r'state\.(shader|viewport|texture_pool|sampler_pool|tex\[|samp\[|ub\[)', '', code_inc), 'NR-08: the .inc reads only the shader / pool / slot tables of the state'
    assert not re.search(r'\bstate\.[a-z_\[\]\.0-9]+\s*=(?!=)', code_inc), 'NR-08: the .inc never writes the state'
    for f in ('gfx/nr/nr_desc.h', 'gfx/nr/nr_desc.c'):
        t = re.sub(r'//[^\n]*', '', (root / f).read_text(encoding='utf-8'))
        assert not re.search(r'\bVk|vulkan|xbg_|getenv|#include "(?!nr_desc\.h)', t), 'NR-08: %s stays engine-free' % f
    assert '#include "../../nr/nr_desc.h"' in (eng / 'xbg_nb_mx.inc').read_text(encoding='utf-8'), 'NR-08: nr_desc.h is pre-included ahead of the context defines'
    assert (eng / 'tests/nr_desc_test.c').is_file(), 'NR-08: nr_desc_test.c exists'
    print('PASS: NR-08: xbg_nr_desc.inc wired at 5 points (Scope after the memo gate, capture line, dyn_mode_for mode 3, UBO_DYN clause, release), '
          'DM_NR_DESC default 0, cap_on / split_on false unless on, state read only, core engine-free')


# NR-07 (pipelines, DM_NR_PIPE, default 0; docs/dos2/nr/NR-07.md): the warm-up ordered by engine events. "Off" = the old warm-up:
#   - xbg_game.cpp: xbg_nr_pipe.inc is included once, inside namespace warm right before worker(); worker() hands over only under
#     nr::mode; start() calls nr::start() before the threads and nr::threads(n) only under nr::mode; shutdown() wakes the workers before the
#     joins and frees the scheduler; take() calls nr::took only under nr::mode; pipeline_lookup asks nr::need only behind warm::nr::mode,
#     after warm::take and before the async request; the draw path's own driver build is bracketed by DrawBuild (inside the build braces);
#     the two extern "C" entry points exist once each;
#   - xbg_nr_pipe.inc: DM_NR_PIPE read once; mode 2 neither claims nor waits (need() returns before any wait), mode 3 needs hints;
#   - hle_dos2_nr.c: g_nr_pipe set only in dm_dos2_nr_install after the "nothing hooked" return; every hint call is behind g_nr_pipe;
#   - nr_pipe.{h,c}: no engine, host, environment or game address.
def nr07_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    g_raw = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8'); g = code(g_raw)
    assert g_raw.count('#include "xbg_nr_pipe.inc"') == 1, 'NR-07: xbg_nr_pipe.inc included once'
    wi = g_raw.index('#include "xbg_nr_pipe.inc"')
    seg = code(g_raw[g_raw.rfind('namespace warm {', 0, wi):wi])
    seg = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", seg)
    assert seg.count('{') - seg.count('}') == 1, 'NR-07: the include is inside namespace warm (brace depth 1)'
    assert re.match(r'#include "xbg_nr_pipe.inc"[^\n]*\nvoid worker\(\)\{\n    if\(nr::mode\)\{nr::worker\(\);return;\}', g_raw[wi:]), 'NR-07: right before worker(), whose first statement hands over under nr::mode'
    st = body(g[g.index('void seed(){'):], 'void start(){')
    assert st.index('nr::start();') < st.index('threads.emplace_back(worker)') and 'if(nr::mode)n=nr::threads(n);' in st, 'NR-07: nr::start before the threads; the count only under nr::mode'
    sd = body(g[g.index('void seed(){'):], 'void shutdown(){')
    assert sd.index('nr::wake();') < sd.index('.join()') and 'nr::reset();' in sd, 'NR-07: shutdown wakes the workers before the joins and frees the scheduler'
    tk = body(g, 'bool take(const std::string &bytes,VkPipeline &out){')
    assert 'if(nr::mode)nr::took(bytes);' in tk and tk.count('nr::') == 2, 'NR-07: take() reports to the scheduler only under nr::mode'
    pl = body(g, 'void pipeline_lookup(')
    need = '(warm::take(bytes,out.pipeline) || (warm::nr::mode && warm::nr::need(bytes,out.pipeline)))'
    assert pl.count(need) == 1 and pl.count('warm::nr::need(') == 1 and pl.index(need) < pl.index('warm::async_request('), 'NR-07: need() behind warm::nr::mode, after take, before the async request'
    assert pl.count('{warm::nr::DrawBuild nrb;gpguard::Lock serial;made=vkCreateGraphicsPipelines(') == 1, 'NR-07: the draw path build is bracketed by DrawBuild'
    assert g_raw.count('extern "C" void xbg_nr_pipe_hint(') == 1 and g_raw.count('extern "C" void xbg_nr_pipe_source(') == 1, 'NR-07: one hint / source entry point each'
    inc = code((root / 'gfx/vulkan/engine/xbg_nr_pipe.inc').read_text(encoding='utf-8'))
    assert (root / 'gfx/vulkan/engine/xbg_nr_pipe.inc').read_text(encoding='utf-8').count('getenv("DM_NR_PIPE")') == 1, 'NR-07: DM_NR_PIPE read once'
    nd = body(inc, 'bool need(const std::string &bytes,VkPipeline &out){')
    assert 'nrp_need(&S,i,now,mode!=2)' in nd and nd.index('if(mode==2)return false;') < nd.index('cv.wait_for('), 'NR-07: mode 2 neither claims nor waits'
    sm = body(inc, 'void start(){')
    assert 'if(mode==3 && !source.load())' in sm, 'NR-07: lazy without hints falls back to 1'
    host = code((root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8'))
    ni = body(host, 'void dm_dos2_nr_install(void) {')
    sets = re.findall(r'\bg_nr_pipe\s*=(?!=)', host)
    assert len(sets) == 1 and len(re.findall(r'\bg_nr_pipe\s*=(?!=)', ni)) == 1 and ni.index('if (!in && rc)') < ni.index('g_nr_pipe = pm;'), \
        'NR-07: g_nr_pipe set once, after the nothing-hooked return'
    tp = body(host, 'void dm_nr_tap_program(')
    assert tp.count('nr_pipe_hint(') == 3 and len(re.findall(r'if \(g_nr_pipe\) nr_pipe_hint\(', tp)) == 3, 'NR-07: every hint call in the program tap is behind g_nr_pipe'
    for name in ('nr_pipe.h', 'nr_pipe.c'):
        core_raw = (root / 'gfx/nr' / name).read_text(encoding='utf-8'); core = code(core_raw)
        assert 'vulkan' not in core.lower() and 'hle.h' not in core_raw and 'pthread' not in core and 'getenv' not in core, 'NR-07: %s stays engine / host free' % name
        assert not re.search(r'0x9[0-9a-f]{5}\b|0x1[0-9a-f]{6}\b', core), 'NR-07: %s holds no game address' % name
    assert (root / 'gfx/vulkan/engine/tests/nr_pipe_test.c').is_file(), 'NR-07: nr_pipe_test.c exists'
    # NR-0407 fix (phone run nr4_b2, docs/dos2/nr/NR-0407-fix.md): the warm-up's records of our fused post draws ("F1.<host>",
    # "F1A.<host>") are hinted by the host's program and built from the fused pack, not read from the game's pack
    assert 'nrp_stage_key(recs[i].keys[k].data(),recs[i].keys[k].size(),&f)' in sm and 'nrp_key_parse' not in sm, 'NR-0407: record stage keys through nrp_stage_key'
    hn = body(inc, 'void hint(const char *key,unsigned len){')
    assert 'nrp_key_parse(key,len)' in hn and 'nrp_stage_key' not in hn, 'NR-0407: hints stay plain game keys'
    bw = body(g, 'bool bundle_words(const std::string &key,std::vector<uint32_t> &w,uint32_t &stage,const char *site,bool idvs=true){')   # T2 DM_NR_IDVS: idvs
    assert 'nbpost::fused_name(key)?nbpost::warm_bundle(key,b):xpack::read(key,b,from_pack)' in bw, 'NR-0407: the warm-up reads fused stages through nbpost::warm_bundle'
    post = code((root / 'gfx/vulkan/engine/xbg_nb_post.inc').read_text(encoding='utf-8'))
    pg = body(post, 'bool pack_get(const std::string &key,std::vector<uint8_t> &out){')
    assert re.match(r'\{\s*std::call_once\(ponce,', pg), 'NR-0407: the fused pack is opened once under call_once (warm-up workers + render thread)'
    pr = body(post, 'bool prepare(int k){'); wb = body(post, 'bool warm_bundle(const std::string &key,std::vector<uint8_t> &out){')
    assert pr.count('compose(x.key,hkey(k),x,why)') == 1 and wb.count('compose(key,host,x,why)') == 1, 'NR-0407: the draw path and the warm-up compose a fused bundle with one function'
    assert 'settings(m,a,l)' in wb and 'mode' not in re.sub(r'DM_NB_POST', '', wb) and 'F[' not in wb, 'NR-0407: warm_bundle reads no render-thread state (settings from the environment, a local Fx)'
    print('PASS: NR-07: warm-up hooks gated by nr::mode (worker / start / shutdown / take / pipeline_lookup need + DrawBuild), DM_NR_PIPE read once, '
          'mode 2 never claims or waits, hints behind g_nr_pipe after the DM_NR gate, scheduler core engine-free; NR-0407: fused post records hinted by '
          'their host program (nrp_stage_key) and built by the warm-up from the fused pack (warm_bundle / compose, pack opened under call_once)')


# NR-09 (docs/dos2/nr/NR-09.md, DM_NR_DRAW, default 0): OP_X_NR_DRAW (OP_X_NB_DRAW + NBD_F_NR + nrd_tail) and nr_draw. "Off" = the old stream
# and the old draw():
#   - hle_nvn.c / nvn_nb_draw.inc: g_nrd_on is 0 until nvn_nr_draw_enable; nbd_draw sets NBD_F_NR and writes the tail only under `nr`
#     (g_nrd_on and an identity for this draw);
#   - hle_dos2_nr_key.inc / hle_dos2_nr.c: g_nr_draw is set once, in nk_draw_install, after the DM_NR gate and only with the flush hook in;
#     dm_nr_draw_ident hands nothing over while it is 0; the identity lives for the one NVN draw after the flush (idp -> idn in the tap);
#   - xbg_game.cpp: xbg_nr_draw.inc included once, after the NB includes and before execute(); draw() asks nrdraw::lane in ONE line right
#     after create_pass, behind nrdraw::cur (null unless an OP_X_NR_DRAW's draw is running), and nrdraw::done in ONE line behind
#     nrdraw::armed right before its last statements; the state reset reads the switch, the shutdown frees the table;
#   - xbg_nb.inc: record / stale only behind nrdraw::mode;
#   - xbg_nr_draw.inc: DM_NR_DRAW read once, mode starts 0; in lane() every fallback (return fail / the mode 2 return) comes before the
#     first command or counter of the draw, so a draw is recorded by exactly one path; nrbuf::place is set only in init;
#   - nr_draw.h: no engine, host, environment or game address.
def nr09_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    g_raw = (eng / 'xbg_game.cpp').read_text(encoding='utf-8'); g = code(g_raw)
    assert g_raw.count('#include "xbg_nr_draw.inc"') == 1, 'NR-09: xbg_nr_draw.inc included once'
    at = g_raw.index('#include "xbg_nr_draw.inc"')
    assert g_raw.index('#include "xbg_nb_own.inc"') < at < g_raw.index('void execute(const uint8_t *pc,unsigned depth,uint64_t &budget){'), 'NR-09: after the NB includes, before execute()'
    head = 'void draw(int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances=1,uint32_t first_instance=0,const GpuIndirect *gi=nullptr){'
    di = g_raw.index(head); dr = g_raw[di:g_raw.index('\n}', di)]
    assert g_raw.index('namespace nrdraw{enum{F_GI=1') < di, 'NR-09: declared ahead of draw()'
    assert dr.count('nrdraw::lane(') == 1 and dr.count('nrdraw::done(') == 1 and dr.count('nrdraw::cur') == 3 and dr.count('nrdraw::armed') == 1, 'NR-09: draw() has the lane line and the done line (NR-ZERO Z3: + the span clock and the nrz3 hook, both behind nrdraw::cur), nothing else'
    assert re.search(r'    create_pass\(p,c\);DRAW_MARK\(2\);\n(?:#ifdef DM_GAME_DOS2\n(?:    if\(nrlf::fused_draw && pgm::mode\)\{pgm::note_lightfuse\(c\.command\);\+\+nrlf::s\.gmem;\}[^\n]*\n)?    if\(nroc::mode>0 && !nroc::adjust\(p,c\)\)\{[^\n]*\n(?:        [^\n]*\n){2}#endif\n    \}   // z3r!=2\n    Descriptors &d=\*dp;\n)?(?:    if\(__builtin_expect\(nrpo::mode!=0,0\)\)nrpo::decide\([^\n]*\n)?(?:    if\(__builtin_expect\(nrps::mode!=0,0\)\)\{if\(!\(z3r==2 && nrz3::ps_called\)\)nrps::decide\([^\n]*\n)?    if\(z3r!=2 && \(nrdraw::cur \|\| \(nrdraw::ui_rec && nrdraw::ui_pick\(\)\)\) && nrdraw::lane\(c,d,p,prim,first,count,indexed,instances,first_instance,[^\n]*,draw_fast\)\)return;', dr), \
        'NR-09: the lane line is the first statement after create_pass, behind nrdraw::cur (NR-12: or a picked UI draw)'
    assert re.search(r'\n    if\(nrdraw::armed\)nrdraw::done\(pipeline\.pipeline,pipeline\.transient,bindings,zero_binding,vertex_buffers,ib,index_type,viewport,sc,indexed,first\);[^\n]*\n    drecy::done\(d\);', dr), \
        'NR-09: the done line is behind nrdraw::armed, right before drecy::done'
    assert g.count('nbpipe::reset();nrdraw::reset();') == 1 and g.count('nrdraw::release();nrdesc::release();') == 1, 'NR-09: switch read at the state reset, table freed at shutdown'
    nb = code((eng / 'xbg_nb.inc').read_text(encoding='utf-8'))
    assert nb.count('nrdraw::record(') == 1 and nb.count('nrdraw::stale(') == 1 and nb.count('if(__builtin_expect(nrdraw::mode,0))nrdraw::record(') == 1 and \
        nb.count('if(__builtin_expect(nrdraw::mode,0))nrdraw::stale();') == 1, 'NR-09: nbdraw::apply hands the tail over only behind nrdraw::mode'
    inc_raw = (eng / 'xbg_nr_draw.inc').read_text(encoding='utf-8'); inc = code(inc_raw)
    assert inc_raw.count('getenv("DM_NR_DRAW")') == 1 and 'int mode=0,fold=3,ui_mode=0;' in inc, 'NR-09: DM_NR_DRAW read once, mode starts 0 (NR-12: ui_mode too)'
    assert len(re.findall(r'(?<![\w:.])mode\s*=(?!=)', inc)) == 3 and len(re.findall(r'nrbuf::place\s*=(?!=)', inc)) == 1 and 'mode=m;nrbuf::place=m?fold:0;' in body(inc, 'void init(){'), \
        'NR-09: mode set in its definition, init and release only; nrbuf::place only in init'
    # [NR-ZERO Z3] the lane is lane() (the resolution: gates, variant, table) + lane_tail() (everything after; nrz3 calls the same tail)
    lh = body(inc, 'bool lane(Commands &c,Descriptors &d,Pass &p,int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances,uint32_t first_instance,unsigned flags,int draw_fast){')
    assert 'vkCmd' not in lh and lh.count('return lane_tail(') == 1 and lh.rindex('return fail(') < lh.index('return lane_tail(') and 'return true;' not in lh and 'return false;' not in lh, 'NR-09: lane() resolves and ends in the tail'
    assert lh.index('H.t=*cur;cur=nullptr;') < lh.index('return fail('), 'NR-09: the identity is consumed before any return'
    ln = body(inc, 'unsigned flags,bool ui,int lm,uint32_t active_colors,const Tm &tm){')
    cut = ln.index('if(lm==2){H.pred=true;armed=true;return false;}')
    first_cmd = min(ln.index(x) for x in ('vkCmd', 'uiarea::pre(', 'open_pass.depth_used=', '++perf.draws', 'stats.draws', 'drecy::done(', 'BindCache &bc=bind_cache'))
    assert cut < first_cmd, 'NR-09: mode 2 returns before anything is recorded or counted for the draw'
    assert ln.rindex('return fail(') < cut and ln.count('return false;') == 1 and ln.count('return true;') == 1, 'NR-09: every fallback comes before the first command; one mode-2 return, one served return'
    for w in ('vkCmdBindPipeline', 'vkCmdBindDescriptorSets', 'vkCmdBindVertexBuffers', 'vkCmdBindIndexBuffer', 'vkCmdDrawIndexed', 'vkCmdDraw(', 'vkCmdSetViewport', 'vkCmdSetScissor'):
        assert ln.count(w) == 1, 'NR-09: lane records %s once' % w
    assert len(re.findall(r'vkCmd\w+', ln)) == 8, 'NR-09: lane records the eight commands of the old tail and no other'
    dn = body(inc, 'void done(VkPipeline pipe,bool transient,')
    assert 'vkCmd' not in dn and dn.index('if(!ok)return;') < dn.index('nrp_tab_put('), 'NR-09: done() records nothing; only a finished, non-transient pipeline enters the table'
    tap = code((root / 'gfx/nvn/nvn_nb_draw.inc').read_text(encoding='utf-8'))
    assert len(re.findall(r'\bg_nrd_on\s*=(?!=)', tap)) == 1 and 'void nvn_nr_draw_enable(int on) { g_nrd_on = on && dm_nr_draw_ident; }' in tap, 'NR-09: g_nrd_on set only by nvn_nr_draw_enable'
    nd = body(tap, 'static int nbd_draw(NVNcommandBuffer *c, int kind,')
    assert 'const int nr = __builtin_expect(g_nrd_on, 0) && dm_nr_draw_ident(' in nd and 'if (nr) h->flags |= NBD_F_NR;' in nd and 'if (nr) nrd_tail_put(' in nd and \
        nd.count('NBD_F_NR') == 1 and nd.count('nrd_tail_put(') == 1 and nd.count('sizeof(nrd_tail)') == 1, 'NR-09: the tail and its flag only under `nr`'
    key = code((root / 'host/hle_dos2_nr_key.inc').read_text(encoding='utf-8'))
    host = code((root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8'))
    assert len(re.findall(r'\bg_nr_draw\s*=(?!=)', key)) == 1 and len(re.findall(r'\bg_nr_draw\s*=(?!=)', host)) == 0, 'NR-09: g_nr_draw set once'
    ki = body(key, 'static void nk_draw_install(module_t *m, int rc_ok) {')
    assert ki.index('if (!g_nr_key) {') < ki.index('g_nr_draw = v;') < ki.index('nvn_nr_draw_enable(1);') and ki.index('if (v != 1 && v != 2)') < ki.index('nk_install(m, 3, rc_ok)'), \
        'NR-09: armed only for DM_NR_DRAW 1 / 2 with the flush hook in'
    ni = body(host, 'void dm_dos2_nr_install(void) {')
    assert ni.count('nk_draw_install(m, rc == 0);') == 1 and ni.index('if (!in && rc)') < ni.index('nk_draw_install(') and ni.index('if (key) nk_install(') < ni.index('nk_draw_install('), \
        'NR-09: after the DM_NR gate and after DM_NR_KEY'
    idn = body(key, 'int dm_nr_draw_ident(uint32_t *key, uint32_t *texset, unsigned *why, unsigned *site) {')
    assert idn.index('if (!g_nr_draw || !t_nk.idn)') < idn.index('t_nk.idn = 0;') < idn.index('*key = t_nk.id_key;'), 'NR-09: nothing handed over while off; an identity is taken once'
    td = body(key, 'void dm_nr_tap_draw(const void *cb) {')
    assert td.index('if (!g_nr_key) return;') < td.index('t_nk.idn = t_nk.idp; t_nk.idp = 0;'), 'NR-09: the identity belongs to the one NVN draw after the flush'
    assert len(re.findall(r'\bt_nk\.idp\s*=\s*1', key)) == 2, 'NR-09: the identity is set by the flush hook (census path and identity-only path)'
    core_raw = (root / 'gfx/nr/nr_draw.h').read_text(encoding='utf-8'); core = code(core_raw)
    assert 'vulkan' not in core.lower() and 'hle.h' not in core_raw and 'pthread' not in core and 'getenv' not in core and 'Vk' not in core, 'NR-09: nr_draw.h stays engine / host free'
    assert not re.search(r'0x9[0-9a-f]{5}\b|0x1[0-9a-f]{6}\b', core), 'NR-09: nr_draw.h holds no game address'
    hdr = (root / 'gfx/nvn/nvn_nb_draw.h').read_text(encoding='utf-8')
    assert 'NBD_F_CHECK = 8, NBD_F_NR = 16 };' in hdr and 'typedef struct { uint32_t key, texset; uint16_t why; uint8_t ver, site; uint32_t _pad; } nrd_tail;' in hdr, 'NR-09: the record flag and tail'
    buf = code((eng / 'xbg_nr_buf.inc').read_text(encoding='utf-8'))
    assert 'int place=0;uint32_t stride_hint=0;' in buf and len(re.findall(r'(?<![\w:.])place\s*=(?!=)', buf)) == 1 and \
        'copy_alloc(bytes,(place&1) && e->kind!=NRS_KIND_VB?1:0,(place&2) && e->kind==NRS_KIND_VB?VkDeviceSize(stride_hint):1)' in buf, 'NR-09: NR-06 copies placed as before unless nrbuf::place'
    assert (eng / 'tests/nr_draw_test.c').is_file(), 'NR-09: nr_draw_test.c exists'
    print('PASS: NR-09: OP_X_NR_DRAW tail only under an identity (g_nrd_on / g_nr_draw 0 until armed after the DM_NR gate), draw() has one lane line behind nrdraw::cur and one '
          'done line behind nrdraw::armed, lane() falls back before its first command (8 commands, each once), DM_NR_DRAW read once (default 0), nrbuf::place only from its init, '
          'core engine-free')

# NR-21 (DM_NR_SORT, default 0; docs/dos2/nr/NR-21.md): the draws of an order-free segment recorded in another order. "Off" stays the old
# command stream and every reorder stays inside one segment:
#   - nrsort::pend (the command buffer with waiting draws) is set non-null only by take(); mode starts 0, DM_NR_SORT is read once;
#   - every vkCmd* wrapper of xbg_nb_mt.inc, nbmt::end and nbmt::sync run NBMT_PRE first (xbg_game.cpp defines it before the include):
#     any other command on that command buffer records the waiting draws first (tests/nr_sort_hook_test.cpp runs it on the mock);
#   - every reader of the bind cache on a draw path (draw()'s old tail, lane()'s own commands) records the waiting draws first;
#   - lane() asks take() after its bookkeeping and before its commands, its 8 commands only when the draw did not join the segment;
#   - take() records nothing; flush() records only through emit(), which records the 8 commands of lane() once each;
#   - a new command buffer finds no waiting draw (cb_begun before nbmt::begin); the pipeline registry of DM_NR_SORT=2 is off otherwise.
def nr21_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i + len(head) - 1); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    g_raw = (eng / 'xbg_game.cpp').read_text(encoding='utf-8'); g = code(g_raw)
    inc_raw = (eng / 'xbg_nr_sort.inc').read_text(encoding='utf-8'); inc = code(inc_raw)
    mt_raw = (eng / 'xbg_nb_mt.inc').read_text(encoding='utf-8'); mt = code(mt_raw)
    nd = code((eng / 'xbg_nr_draw.inc').read_text(encoding='utf-8'))
    assert g_raw.count('#include "xbg_nr_sort.inc"') == 1 and g_raw.index('#include "xbg_nr_draw.inc"') < g_raw.index('#include "xbg_nr_sort.inc"') < \
        g_raw.index('void execute(const uint8_t *pc,unsigned depth,uint64_t &budget){'), 'NR-21: xbg_nr_sort.inc right after xbg_nr_draw.inc, before execute()'
    pre = '#define NBMT_PRE(c,op) do{if(__builtin_expect((c)==nrsort::pend.load(std::memory_order_relaxed),0) && (c))nrsort::cut((c),(op));}while(0)'
    assert g_raw.count(pre) == 1 and g_raw.index(pre) < g_raw.index('#include "xbg_nb_mt.inc"'), 'NR-21: NBMT_PRE defined (pend compare first) before xbg_nb_mt.inc'
    # every wrapper starts with the hook (or delegates to pod / podf, which start with it)
    n = 0
    for m in re.finditer(r'inline void (Cmd\w+|P\w+)\(', mt):
        b = body(mt, m.group(0))[1:].lstrip(); n += 1
        assert b.startswith('NBMT_PRE(c, OP_') or b.startswith('pod<') or b.startswith('podf<'), 'NR-21: wrapper %s does not start with NBMT_PRE / pod / podf' % m.group(1)
        if b.startswith('NBMT_PRE'):
            nm = m.group(1)[1:] if m.group(1).startswith('P') else m.group(1)[3:]
            assert b.startswith('NBMT_PRE(c, OP_%s);' % nm), 'NR-21: wrapper %s passes another op' % m.group(1)
    assert n == 36, 'NR-21: 36 wrappers (%d; NR-ONCHIP: + CmdNextSubpass)' % n
    for head in ('inline void pod(VkCommandBuffer c, A... a) {', 'inline void podf(Fn f, VkCommandBuffer c, A... a) {'):
        assert body(mt, head)[1:].lstrip().startswith('NBMT_PRE(c, OP);'), 'NR-21: %s starts with NBMT_PRE' % head
    assert body(mt, 'void end(VkCommandBuffer cmd) {')[1:].lstrip().startswith('NBMT_PRE(cmd, OP_COUNT + 1);'), 'NR-21: nbmt::end starts with NBMT_PRE (submission end)'
    assert 'inline void sync(VkCommandBuffer cmd) { NBMT_PRE(cmd, OP_COUNT + 2);' in mt, 'NR-21: nbmt::sync starts with NBMT_PRE'
    assert '#ifndef NBMT_PRE\n#define NBMT_PRE(c, op) ((void)0)' in mt_raw, 'NR-21: the host tests keep an empty NBMT_PRE'
    # pend: non-null only from take()
    tb = body(inc, 'bool take(Commands &c,Descriptors &d,Pass &p,')
    assert len(re.findall(r'\bpend\.store\(', inc)) == 4 and inc.count('pend.store(c.command,std::memory_order_relaxed);') == 1 and \
        'pend.store(c.command,std::memory_order_relaxed);' in tb, 'NR-21: pend set only by take() (release / cb_begun / a BeginRenderPass cut clear it)'
    assert inc.count('pend.exchange(VK_NULL_HANDLE') == 1 and 'pend.store(' not in g and 'pend.exchange(' not in g, 'NR-21: flush clears pend first; the engine never sets it'
    assert inc_raw.count('getenv("DM_NR_SORT")') == 1 and 'int mode=0,key=0;' in inc and len(re.findall(r'(?<![\w:.])mode\s*=(?!=)', inc)) == 3, 'NR-21: DM_NR_SORT read once, mode starts 0'
    # the readers of the bind cache on a draw path record the waiting draws first
    fl = 'if(nrsort::pend.load(std::memory_order_relaxed))nrsort::flush_draw();'
    head = 'void draw(int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances=1,uint32_t first_instance=0,const GpuIndirect *gi=nullptr){'
    di = g_raw.index(head); dr = code(g_raw[di:g_raw.index('\n}', di)])
    for where, t in (('draw()', dr), ('lane()', nd)):
        uses = [m.start() for m in re.finditer(r'BindCache &bc=bind_cache;', t)]
        assert len(uses) == 1, 'NR-21: %s reads the bind cache once' % where
        at = t.rfind(fl, 0, uses[0])
        assert at >= 0 and re.fullmatch(r'\s*', t[at + len(fl):uses[0]]), 'NR-21: %s records the waiting draws right before it reads the bind cache' % where
    assert g.count('BindCache &bc=bind_cache;') == 1 and inc.count('BindCache &bc=bind_cache;') == 1, 'NR-21: no other reader of the bind cache'
    ln = body(nd, 'bool lane(Commands &c,Descriptors &d,Pass &p,int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances,uint32_t first_instance,unsigned flags,int draw_fast){') + body(nd, 'unsigned flags,bool ui,int lm,uint32_t active_colors,const Tm &tm){')   # [NR-ZERO Z3] lane() + lane_tail(): the lane as one text
    tk = ln.index('const bool queued=__builtin_expect(nrsort::mode!=0,0) && dr && nrsort::take(c,*dr,p,count,indexed,instances,first,first_instance);')   # dr: the draw's Descriptors record (null only for a draw nrz3 answers, and nrz3 answers none while DM_NR_SORT is on)
    assert ln.index('open_pass.color_targets=true;') < tk < ln.index('if(!queued){') < ln.index('BindCache &bc=bind_cache;') and ln.index('vkCmd') > tk and \
        ln.index('}else{DRAW_MARK(5);pass_prof_draw(c.command);}') > ln.rindex('vkCmd') and ln.count('nrsort::take(') == 1, 'NR-21: lane asks take() after its bookkeeping; its commands only when not queued'
    assert 'vkCmd' not in tb and 'emit(' not in tb, 'NR-21: take() records nothing'
    em = body(inc, 'inline void emit(VkCommandBuffer cmd,BindCache &bc,const Pk &k,nrs_count &em){')
    for w in ('vkCmdBindPipeline', 'vkCmdBindDescriptorSets', 'vkCmdBindVertexBuffers', 'vkCmdBindIndexBuffer', 'vkCmdDrawIndexed', 'vkCmdDraw(', 'vkCmdSetViewport', 'vkCmdSetScissor'):
        assert em.count(w) == 1, 'NR-21: emit records %s once' % w
    assert len(re.findall(r'vkCmd\w+', em)) == 8 and len(re.findall(r'vkCmd\w+', inc)) == 8, 'NR-21: emit records the eight commands of lane(), nothing else in nrsort records'
    fb = body(inc, 'void flush(unsigned why,bool exact){')
    assert fb.index('pend.exchange(') < fb.index('emit(') < fb.index('if(!exact){bc=BindCache{};bc.cmd=c;}') < fb.index('q.clear();'), 'NR-21: flush clears pend, records, then resets the cache unless exact'
    assert g_raw.count('nrsort::cb_begun();nbmt::begin(s.cmd,') == 1, 'NR-21: a new command buffer finds no waiting draw'
    assert g.count('nbpipe::reset();nrdraw::reset();nrsort::reset();') == 1 and g.count('nrsort::release();nrdraw::release();') == 1, 'NR-21: switch read after DM_NR_DRAW, queue freed at shutdown'
    assert body(inc, 'void note_pipeline(VkPipeline p,const VkGraphicsPipelineCreateInfo &ci){')[1:].lstrip().startswith('if(!reg_on.load(std::memory_order_relaxed) || !p)return;') and \
        'reg_on.store(m==2,std::memory_order_relaxed);' in body(inc, 'void init(){'), 'NR-21: the create-info registry only with DM_NR_SORT=2'
    assert 'if(m && nrdraw::mode!=1)' in body(inc, 'void init(){'), 'NR-21: needs DM_NR_DRAW=1'
    core_raw = (root / 'gfx/nr/nr_sort.h').read_text(encoding='utf-8'); core = code(core_raw)
    assert 'vulkan' not in core.lower() and 'hle.h' not in core_raw and 'pthread' not in core and 'getenv' not in core and 'Vk' not in core, 'NR-21: nr_sort.h stays engine / host free'
    for t in ('nr_sort_test.c', 'nr_sort_hook_test.cpp'): assert (eng / 'tests' / t).is_file(), 'NR-21: %s exists' % t
    print('PASS: NR-21: pend set only by take() (DM_NR_SORT read once, default 0), NBMT_PRE first in all 35 vkCmd* wrappers / nbmt::end / sync, both bind-cache readers record the '
          'waiting draws first, lane asks take() between bookkeeping and commands, take records nothing, emit the 8 commands of lane, registry only with =2, core engine-free')

# NR-12 (docs/dos2/nr/NR-12.md, DM_NR_UI, default 0): plain Iggy draw records through NR-09's lane. "Off" = the old stream and the old draw():
#   - xbg_game.cpp execute(): OP_DRAW / OP_DRAW_IDX set nrdraw::ui_rec and call nrdraw::ui_end only behind nrdraw::ui_mode (one load each
#     while off); draw()'s lane line asks nrdraw::ui_pick only behind ui_rec and only without a record identity (nrdraw::cur first);
#     Shader::nrui starts -1 (looked at once);
#   - xbg_nr_draw.inc: DM_NR_UI read once in init, ui_mode starts 0 and is set only there and in release; ui_rec is set true only by
#     execute() and cleared by ui_pick / ui_end; ui_pick hands over the one synthetic identity (key 0, site NRD_SITE_UI); in lane() the UI
#     draw's mode / counters come from its identity, the uiarea step is nr_ui_area's (the full uiarea::pre only for NRUA_FULL, after the
#     mode-2 return), the quad pattern is made only in lane() (one stream allocation) and bound instead of a per-draw list;
#   - nr_draw.h: the NR-12 helpers are pure (covered by NR-09's engine / host / address check of the whole header).
def nr12_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    g_raw = (eng / 'xbg_game.cpp').read_text(encoding='utf-8'); g = code(g_raw)
    for op in ('case OP_DRAW:{', 'case OP_DRAW_IDX:{'):
        at = g_raw.index(op); line = g_raw[at:g_raw.index('\n', at)]
        assert line.count('if(__builtin_expect(nrdraw::ui_mode,0))nrdraw::ui_rec=true;draw(') == 1 and line.count(');if(__builtin_expect(nrdraw::ui_mode,0))nrdraw::ui_end();break;}') == 1, \
            'NR-12: %s marks its draw() for the UI lane only behind nrdraw::ui_mode' % op
    assert len(re.findall(r'nrdraw::ui_rec\s*=', g)) == 2 and g.count('nrdraw::ui_end()') == 2, 'NR-12: ui_rec set only by the two plain draw records'
    head = 'void draw(int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances=1,uint32_t first_instance=0,const GpuIndirect *gi=nullptr){'
    di = g_raw.index(head); dr = g_raw[di:g_raw.index('\n}', di)]
    assert dr.count('nrdraw::ui_pick()') == 1 and '(nrdraw::cur || (nrdraw::ui_rec && nrdraw::ui_pick())) && nrdraw::lane(' in dr, 'NR-12: ui_pick only behind ui_rec, after the record identity'
    assert dr.count('quad_plain=true;') == 1 and 'if(prim==7 && !indexed){quad_plain=true;' in dr and 'quad_plain?nrdraw::F_QUAD|nrdraw::F_QUADP:nrdraw::F_QUAD' in dr, \
        'NR-12: F_QUADP only for a non-indexed QUADS draw (the pattern list)'
    assert 'int8_t nrui=-1;' in g_raw and 'F_QUADP=16' in g_raw, 'NR-12: Shader::nrui starts unknown; the QUADS-pattern flag'
    inc_raw = (eng / 'xbg_nr_draw.inc').read_text(encoding='utf-8'); inc = code(inc_raw)
    assert inc_raw.count('getenv("DM_NR_UI")') == 1 and 'getenv("DM_NR_UI")' in body(inc_raw, 'void init(){'), 'NR-12: DM_NR_UI read once, in init'
    assert len(re.findall(r'(?<![\w:.])ui_mode\s*=(?!=)', inc)) == 3 and 'ui_mode=um;' in body(inc, 'void init(){') and 'ui_mode=0;' in body(inc, 'void release(){'), \
        'NR-12: ui_mode set in its definition, init and release only'
    assert len(re.findall(r'(?<![\w:.])ui_rec\s*=\s*true', inc)) == 0 and len(re.findall(r'(?<![\w:.])ui_rec\s*=(?!=)', inc)) == 3, \
        'NR-12: the backend file never arms ui_rec (only clears it: definition, ui_pick, ui_end)'
    pk = body(inc, 'bool ui_pick(){')
    assert pk.index('ui_rec=false;') < pk.index('cur=&ui_tail;') and pk.count('cur=') == 1, 'NR-12: ui_pick consumes the mark and hands over the one synthetic identity'
    assert 'const nrd_tail ui_tail{0,0,0,NRD_VER,NRD_SITE_UI,0};' in inc_raw, 'NR-12: the identity = key 0, texture set 0, site NRD_SITE_UI'
    ln = body(inc, 'bool lane(Commands &c,Descriptors &d,Pass &p,int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances,uint32_t first_instance,unsigned flags,int draw_fast){') + body(inc, 'unsigned flags,bool ui,int lm,uint32_t active_colors,const Tm &tm){')   # [NR-ZERO Z3] lane() + lane_tail(): the lane as one text
    cut = ln.index('if(lm==2){H.pred=true;armed=true;return false;}')
    assert ln.index('const bool ui=H.t.site==NRD_SITE_UI && H.t.key==NRD_ROW_UI;') < ln.index('return fail('), 'NR-12: the UI identity is read before any fallback'
    assert 'const int ua=nr_ui_area(' in ln and ln.count('uiarea::pre(') == 2 and ln.index('if(ua==NRUA_FULL){uiarea::pre(p,c.command,true);') > cut and \
        ln.index('else if(ua==NRUA_SHORT){') > cut and 'if(ua==NRUA_OLD)return fail(NRW_UIAREA);' in ln, 'NR-12: the uiarea step by nr_ui_area, the full one only after the mode-2 return'
    assert ln.count('recording_slot().stream.alloc(') == 1 and ln.index('recording_slot().stream.alloc(') < cut and inc.count('recording_slot().stream.alloc(') == 1, \
        'NR-12: the quad pattern is made in lane() only, before the mode-2 return (both modes bind / compare the same list)'
    assert 'if((flags&~F_PP) && !(ui && flags==(F_QUAD|F_QUADP)))return fail(NRW_SPECIAL);' in ln and 'if(pp && ui)return fail(NRW_SPECIAL);' in ln, 'NR-12: only the UI lane takes QUADS, and only the pattern kind (NR-30: the pre-pass override only for engine draws)'
    dn = body(inc, 'void done(VkPipeline pipe,bool transient,')
    assert 'nr_quad_ok(' in dn and dn.index('if(H.qpat){') < dn.index('else if(indexed && ib){'), "NR-12: mode 2 compares a QUADS draw's old index list with the pattern"
    ue = body(inc, 'void ui_end(){')
    assert 'ui_rec=false;' in ue and 'stale();' in ue, 'NR-12: ui_end drops what an early return left behind'
    assert (eng / 'tests/nr_ui_test.c').is_file(), 'NR-12: nr_ui_test.c exists'
    print('PASS: NR-12: DM_NR_UI read once (default 0), execute() marks plain draw records only behind ui_mode, ui_pick behind ui_rec after the record identity, '
          'one synthetic identity, uiarea step by nr_ui_area (full step after the mode-2 return), the quad pattern made only in lane(), compared at mode 2')


def nr08b_check():
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    inc = (eng / 'xbg_nr_ubodyn.inc').read_text(encoding='utf-8')
    at = s.find('#include "xbg_nr_ubodyn.inc"')
    assert s.count('#include "xbg_nr_ubodyn.inc"') == 1 and s.find('struct Shader {') < at < s.find('VkResult bundle_module(const std::vector<uint32_t> &w,VkShaderModule *m,const std::string &key){'), \
        'NR-08b: xbg_nr_ubodyn.inc once, after struct Shader and right before bundle_module'
    macro = re.search(r'^#define UBO_DYN\(mode,b\).*$', s, re.M).group(0)
    assert macro.endswith(' && !(nrubd::ro && ((b).flags&(XBG_BIND_SCANNED|XBG_BIND_UNREAD))!=XBG_BIND_SCANNED))'), 'NR-08b: UBO_DYN ends with the read-only clause (one line: ubo_memo_snapshot_test reads it)'
    dm = body(s, 'unsigned dyn_mode_for(bool compute,bool *no_ubo=nullptr){')
    assert dm.count('nrubd::') == 1 and dm.index('if(!ubo_dynamic_on)return 0;') < dm.index('nrdesc::split_on') < dm.index('if(nrubd::ro)return vary && vary<=lim && dyn_partial_enabled?2:0;'), \
        'NR-08b: dyn_mode_for caps the rule at mode 2, after the policy and the NR-08 split'
    bm = body(s, 'VkResult bundle_module(const std::vector<uint32_t> &w,VkShaderModule *m,const std::string &key){')
    assert 'xbg_spvopt_lookup(w.data(),w.size(),opt,key.c_str()) && nrubd::opt_ok(w,opt,key);' in bm, 'NR-08b: the optimizer copy is checked before it is used'
    ls = body(s, 'Shader *load_shader_key(const std::string &key,const void *control,const void *code){')
    assert ls.count('nrubd::mark(*p,words);') == 1 and ls.index('load_t3=timing_clock();') < ls.index('nrubd::mark(*p,words);') < ls.index('VK(bundle_module(words,&p->module,key))'), \
        'NR-08b: modules are scanned on their final words, after every rewrite, before the module is created'
    assert s.count('nrubd::init(gpu_policy,xbg_ubo_dynamic_default(gpu_policy));') == 1 and \
        s.index('ubo_dynamic_on=xbg_env_or(getenv("DM_GFX_UBO_DYNAMIC")') < s.index('nrubd::init(gpu_policy') < s.index('xbg_logf("NVN gpu policy: pipe_serial=%d'), \
        'NR-08b: init right after the UBO policy, before its log line'
    assert s.count('nrubd::') == 10, 'NR-08b: no other use of nrubd in xbg_game.cpp (found %d)' % s.count('nrubd::')
    assert 'int mode=0;bool ro=false,scan=false;' in inc, 'NR-08b: off until init'
    ini = body(inc, 'void init(XbgGpuFamily fam,bool family_on){')
    assert 'ro=xbg_nr_ubodyn_active(m,uenv,family_on,fam);' in ini and 'if(ro)ubo_dynamic_on=true;' in ini and 'scan=mode==1 || mode==2;' in ini, 'NR-08b: init: rule from the policy function, scan only in 1 / 2'
    code_inc = re.sub(r'//[^\n]*', '', inc)
    assert len(re.findall(r'\bro=(?!=)', code_inc)) == 2 and len(re.findall(r'\bubo_dynamic_on=', code_inc)) == 1, 'NR-08b: ro / ubo_dynamic_on set only in init (+ the declaration)'
    assert 'state.' not in code_inc, 'NR-08b: the .inc does not touch the draw state'
    mk = body(inc, 'void mark(Shader &p,const std::vector<uint32_t> &words){')
    assert mk.lstrip('{').lstrip().startswith('if(!scan)return;'), 'NR-08b: mark returns at once when off'
    pol = (eng / 'xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_ubodyn_default(XbgGpuFamily f){return f==XBG_GPU_POWERVR?1:0;}' in pol, 'NR-08b: default 1 on PowerVR (17.11, SIM batch 12), 0 elsewhere'
    for f in ('gfx/nr/nr_ubodyn.h', 'gfx/nr/nr_ubodyn.c'):
        t = re.sub(r'//[^\n]*', '', (root / f).read_text(encoding='utf-8'))
        assert not re.search(r'\bVk|vulkan|xbg_|getenv|#include "(?!nr_ubodyn\.h)', t), 'NR-08b: %s stays engine-free' % f
    for f in ('tests/nr_ubodyn_test.c', 'tests/nr_ubodyn_engine_test.py'):
        assert (eng / f).is_file(), 'NR-08b: %s exists' % f
    print('PASS: NR-08b: xbg_nr_ubodyn.inc wired at 8 points (scan in load_shader_key, optimizer check, UBO_DYN clause, dyn_mode_for cap, init, NEVER counter, summary + its declaration), '
          'DM_NR_UBODYN default 0, core engine-free')
def nr04_check():   # NR-04 DM_NR_SH (docs/dos2/nr/NR-04.md): engine shaders by name
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\.|[^"\\n])*"', '""', text)
    tools = root.parent / 'tools'
    c = (root / 'gfx/nr/nr_sh.c').read_text(encoding='utf-8')
    rows = re.findall(r'^\s*\{"(\w+)",\s*"([0-9a-f]{16})",\s*NR_SH_(POST|LIGHT|SHADOW),\s*"(\w+)",\s*(\d),\s*(\d),\s*(0x[0-9a-f]+)\},$', c, flags=re.M)
    py = (tools / 'dos2_nr_sh_pack.py').read_text(encoding='utf-8')
    prow = re.findall(r"^\s*\('(\w+)', '([0-9a-f]{16})', '(post|light|shadow)', '(\w+)', (\d), (\d), (0x[0-9a-f]+)\),$", py, flags=re.M)
    assert rows and [(n, k, cl.lower(), v, int(pr), int(co), int(f, 16)) for n, k, cl, v, pr, co, f in rows] == \
        [(n, k, cl, v, int(pr), int(co), int(f, 16)) for n, k, cl, v, pr, co, f in prow], 'NR-04: nr_sh.c table = dos2_nr_sh_pack.py ENTRIES'
    for n, k, cl, v, pr, co, f in rows:
        src = tools / ('dos2_pcf/CascadedPCF_mobile.frag' if cl == 'SHADOW' else 'dos2_post/%s_mobile.frag' % n)
        assert src.is_file(), 'NR-04: the rewrite of %s exists (%s)' % (n, src.name)
        assert len(n) + 2 < 32 or 'if (strlen(s) + 2 > 31) s = nr_sh_table[i].key;' in c, 'NR-04: pack key of %s fits xgs_pack (31 characters; NR-33A: else the key)' % n
    for name in ('nr_sh.h', 'nr_sh.c'):
        raw = (root / 'gfx/nr' / name).read_text(encoding='utf-8'); core = code(raw)
        assert 'vulkan' not in core.lower() and 'getenv' not in core and 'pthread' not in core, 'NR-04: %s stays engine / host free' % name
        assert not re.search(r'0x9[0-9a-f]{5}\b|0x1[0-9a-f]{6}\b', core), 'NR-04: %s holds no game address' % name
    game = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    rd = game[game.index('bool read(const std::string &key,std::vector<uint8_t> &out,bool &from_pack){'):]
    rd = rd[:rd.index('return have;}') + 13]
    assert '#ifdef DM_GAME_DOS2' in rd and rd.index('nrsh::apply(key,out)') < rd.index('native::apply(key,out)'), 'NR-04: read() asks nrsh before native, DOS2 only'
    assert re.search(r'#ifdef DM_GAME_DOS2\n#include "xbg_nr_sh.inc"', game) and re.search(r'#ifdef DM_GAME_DOS2\n#include "xbg_nr_sh_pass.inc"', game), 'NR-04: both .inc DOS2 only'
    assert re.search(r'#ifdef DM_GAME_DOS2\n    p->nr_sh=h.stage==4\?xpack::nrsh::marked\(key\):-1;', game), 'NR-04: load_shader marks fragment shaders only'
    assert game.count('nrpass::choose(') == 1, 'NR-04: one pass choice in draw()'
    i = game.index('if(state.shader[4] && state.shader[4]->nr_sh>=0)nrpass::choose(*state.shader[4],stages,p.samples);')
    assert i < game.index('VkShaderModule m=alpha_module(*state.shader[4]', i), 'NR-04: the pass choice runs before the alpha-test variant in draw()'
    assert 'if(xpack::nrsh::mode)nrsh_tick();' in game, 'NR-04: the summary tick sits in the submission'
    inc = code((root / 'gfx/vulkan/engine/xbg_nr_sh.inc').read_text(encoding='utf-8'))
    assert re.search(r'getenv\(""\);int m=e && \*e\?atoi\(e\):xbg_nr_sh_default\(gpu_policy\);', inc), 'NR-04: DM_NR_SH default from the policy'
    assert inc.count('bytes.swap(nb)') == 1 and re.search(r'if\(mode==1\)\{bytes\.swap\(nb\);', inc), 'NR-04: only mode 1 swaps a bundle'
    ap = code(inc[inc.index('bool apply('):])
    assert ap.index('nr_sh_head_equal(') < ap.index('bytes.swap(nb)') and ap.index('nr_sh_bindings_ok(') < ap.index('bytes.swap(nb)') and ap.index('io(nb,') < ap.index('bytes.swap(nb)'), \
        'NR-04: head, descriptors and interface checked before the swap'
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_sh_pcf_default(XbgGpuFamily){return 3;}' in pol and 'inline int xbg_nr_sh_default(XbgGpuFamily){return 1;}' in pol, 'NR-04: DM_NR_SH default 1 (owner 17.11), DM_NR_SH_PCF default 0 on every family'
    setup = (tools / 'setup_dos2.py').read_text(encoding='utf-8')
    st8 = setup[setup.index('    t0 = stage(8)'):setup.index('    t0 = stage(9)')]
    assert 'step_postpack(L, a.yes)' in st8 and 'step_nrpack(L, a.yes)' in st8, 'NR-04: setup stage 8 builds native-nr.xgspack after native-post.xgspack'
    assert "'tools/dos2_nr_sh_pack.py'" in setup and 'L.nrpack_ok()' in setup, 'NR-04: the pack is stamped by its tools and shown by setup check'
    host = code((root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8'))
    assert host.count('nr_sh_names(name, path, key[1]);') == 1, 'NR-04: one name cross-check in the CreateShader hook'
    assert (root / 'gfx/vulkan/engine/tests/nr_sh_test.cpp').is_file(), 'NR-04: nr_sh_test.cpp exists'
    print('PASS: NR-04: table = pack tool (%d engine shaders, rewrites present), core engine-free, read() asks nrsh before native (DOS2 only), '
          'fragment shaders marked, pass choice before the alpha variant, DM_NR_SH / DM_NR_SH_PCF default 0, swap only after head / descriptors / '
          'interface, setup stage 8 builds the pack, one name cross-check' % len(rows))

def t11dref_check():   # PERF-X19 T11 (DM_NR_SH_PCF=3, docs/dos2/DOS2_PORT.md "Мобильный резолв теней"): hardware depth compare (Dref) for the shadows
    tools = root.parent / 'tools'
    c = (root / 'gfx/nr/nr_sh.c').read_text(encoding='utf-8'); h = (root / 'gfx/nr/nr_sh.h').read_text(encoding='utf-8')
    assert 'NR_SH_PCF_DREF = 3' in h and "pcf == NR_SH_PCF_DREF ? 'd' : 0" in c, 'T11: DM_NR_SH_PCF=3 -> pack variant d'
    rows = re.findall(r'\{"(CascadedPCF_\w+)",\s*"[0-9a-f]{16}",\s*NR_SH_SHADOW,\s*"(\w+)"', c)
    assert rows and all('d' in v for _, v in rows), 'T11: every shadow entry has the dref variant'
    assert 'uint64_t nr_sh_depth_bindings(const uint32_t *w, size_t n)' in c, 'T11: the depth-image scan is in the pure C core'
    frag = (tools / 'dos2_pcf/CascadedPCF_mobile.frag').read_text(encoding='utf-8')
    assert '#if PCF_MODE == 3\nlayout(set = 0, binding = 16) uniform sampler2DShadow Shadow;' in frag and \
        'textureLod(Shadow, vec3(clamp(uvz.xy + r * TAPS[j], lo, hi), ref), 0.0)' in frag and '#elif PCF_MODE == 1 || PCF_MODE == 3' in frag, \
        'T11: PCF_MODE 3 = mobile taps through sampler2DShadow at the atlas binding, explicit lod'
    pk = (tools / 'dos2_nr_sh_pack.py').read_text(encoding='utf-8')
    assert "PCF_MODE = {'x': 0, 'm': 1, 'd': 3}" in pk and 'dref_vs_mobile(' in pk, 'T11: the pack builds d from PCF_MODE 3 and compares it with m'
    inc = (root / 'gfx/vulkan/engine/xbg_nr_sh.inc').read_text(encoding='utf-8')
    assert 'if(q<0 || q>3)q=0;' in inc and 'if(m && q==NR_SH_PCF_DREF && !dref_device())q=NR_SH_PCF_MOBILE;' in inc, 'T11: 3 accepted; no linear compare -> mobile'
    dd = inc[inc.index('bool dref_device(){'):]; dd = dd[:dd.index('return ok;}')]
    assert 'depth16_as_d24?VK_FORMAT_X8_D24_UNORM_PACK32:VK_FORMAT_D16_UNORM' in dd and 'VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT' in dd and \
        'VK_FORMAT_FEATURE_2_SAMPLED_IMAGE_DEPTH_COMPARISON_BIT' in dd, 'T11: the device check uses the atlas storage format: linear filter + depth comparison'
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    assert 'uint64_t dref_bindings=0;' in g, 'T11: Shader::dref_bindings'
    assert '#ifdef DM_GAME_DOS2\n    if(h.stage==4 && p->nr_sh>=0)p->dref_bindings=nr_sh_depth_bindings(words.data(),words.size());' in g, \
        'T11: only named fragment bundles (DOS2) are scanned, on their final words'
    bind = 'if(b.binding<64 && (shader.dref_bindings>>b.binding&1))dref_sampler(parameters,texture,b.binding,shader.key);'
    assert g.count(bind) == 1, 'T11: one compare-sampler hook'
    assert re.search(r'#ifdef DM_GAME_DOS2\n +' + re.escape(bind) + r'[^\n]*\n#endif\n +ii\.sampler=sampler\(parameters,', g), \
        'T11: the compare sampler is set on the COMBINED_IMAGE_SAMPLER bind right before the VkSampler is made (DOS2 only)'
    ds = g[g.index('void dref_sampler(samp_par &p,'):]; ds = ds[:ds.index('\n#endif')]
    assert 'if(!p.cmp_mode){p.cmp_mode=1;p.cmp_func=2;p.minf|=1;p.magf=1;}' in ds and 'VK_IMAGE_ASPECT_DEPTH_BIT' in ds, 'T11: LESS (NVN 2 = Vk 1) + linear, depth textures only'
    assert '(uint64_t(b.binding<64 && (shader.dref_bindings>>b.binding&1))<<10)};img_cacheable=true;' in g, 'T11: the image cache keeps compare and plain samplers apart'
    sp = (root / 'gfx/vulkan/engine/xbg_sampler.cpp').read_text(encoding='utf-8')
    assert 's.compareEnable=p->compare_mode;s.compareOp=VkCompareOp(p->compare_func-1);' in sp, 'T11: NVN compare func = VkCompareOp + 1 (2 = LESS)'
    ps = (root / 'gfx/vulkan/engine/xbg_nr_sh_pass.inc').read_text(encoding='utf-8')
    assert ps.index('if(fs.dref_bindings)') < ps.index('const VkShaderModule m=alt(fs);'), 'T11: a Dref shader never falls back to the translated module (its sampler compares)'
    print('PASS: T11: DM_NR_SH_PCF=3 -> d bundles (sampler2DShadow, %d shadow entries), device check with mobile fallback, depth bindings scanned on named '
          'fragment bundles, LESS + linear on their sampler, image cache split, no translated fallback for Dref' % len(rows))

# NR-28 (docs/dos2/nr/NR-28.md, DM_NR_LEANCALL, default 0): the lean NVN call path. "Off" keeps the old slots, thunks and wrapper (one
# guarded line in nvn_bigstack_top); "on" changes only which entry / thunk set is in front of the same bodies, and the entry touches only
# scratch registers and calls no C before the body.
def nr28_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    raw_inc = (root / 'gfx/nvn/nvn_leancall.inc').read_text(encoding='utf-8')
    nvn_raw = (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8')
    nvn, inc = code(nvn_raw), code(raw_inc)
    assert 'DM_NR_LEANCALL' not in (root / 'android/jni_android.c').read_text(encoding='utf-8'), 'NR-28: the app does not set DM_NR_LEANCALL'
    ins = body(inc, 'static void nvn_lc_install(void) {')
    assert raw_inc.count('getenv("DM_NR_LEANCALL")') == 1 and len(re.findall(r'\bg_lc_mode\s*=(?!=)', inc)) == 1 and 'g_lc_mode = v;' in ins, \
        'NR-28: DM_NR_LEANCALL read once; g_lc_mode set only by nvn_lc_install'
    assert ins.index('if (v != 1 && v != 2)') < ins.index('g_lc_mode = v;') and ins.index('if (!n)') < ins.index('g_lc_mode = v;') and \
        ins.index('atoi(nc) == 2') < ins.index('g_lc_mode = v;'), 'NR-28: off for 0 / other values, without the big-stack wrapper, and =1 with DM_NR_NOCALL=2'
    assert len(re.findall(r'nvn_slot\[i\]\.fn\s*=\s*\(void \*\)nvn_lean_entry', nvn + inc)) == 1 and \
        'if (v == 1) for (unsigned i = 0; i < NVN_NFUNC; i++) if (nvn_slot[i].fn == (void *)nvn_bigstack_entry) nvn_slot[i].fn = (void *)nvn_lean_entry;' in ins, \
        'NR-28: only =1 puts the lean entry in, only in slots the big-stack wrapper holds'
    top = body(nvn, 'void *nvn_bigstack_top(uintptr_t sp) {')
    assert top.count('g_lc_mode') == 1 and 'if (__builtin_expect(g_lc_mode, 0)) return nvn_lc_top(sp);' in top and \
        top.index('t_nc_calls++') < top.index('g_lc_mode') < top.index('if (!t_big)'), 'NR-28: one guarded line in nvn_bigstack_top, after the NR-23 counter'
    assert nvn.count('nvn_lc_install();') == 1 and nvn.find('nvn_bigstack_entry; } }') < nvn.find('nvn_lc_install();') < nvn.find('nvn_p2_install();'), \
        'NR-28: the lean entry goes in after the big-stack wrapper and before DM_NVN_PROF=2 (which goes under it)'
    assert 'void *const *tab = nvn_thunk_tab();' in nvn and nvn_raw.count('#include "nvn_leancall.inc"') == 1, 'NR-28: nvn_lookup hands out nvn_thunk_tab()'
    sel = 'static void *const *nvn_thunk_tab(void) { return dm_cpu_lse() && g_lc_mode != 1 ? nvn_thunk : nvn_thunk_v80; }'
    assert sel in inc, 'NR-28: the plain set only for =1'
    plain = 'static void *const *nvn_thunk_tab(void) { return dm_cpu_lse() ? nvn_thunk : nvn_thunk_v80; }'
    for f in ('gfx/nvn/hle_nvn.c', 'gfx/nvn/nvn_cpuprof.inc', 'gfx/nvn/nvn_nr_nocall.inc', 'gfx/nvn/nvn_leancall.inc'):
        t = code((root / f).read_text(encoding='utf-8')).replace(plain, '')
        assert 'dm_cpu_lse() ? nvn_thunk : nvn_thunk_v80' not in t, 'NR-28: %s picks the thunk table only through nvn_thunk_tab()' % f
    p2 = code((root / 'gfx/nvn/nvn_cpuprof.inc').read_text(encoding='utf-8')); nc = code((root / 'gfx/nvn/nvn_nr_nocall.inc').read_text(encoding='utf-8'))
    assert 'if (NVN_BIG_FN(nvn_slot[i].fn)) return nvn_real_big[i];' in p2 and \
        'if (NVN_BIG_FN(nvn_slot[i].fn)) { nvn_real[i] = nvn_real_big[i]; nvn_real_big[i] = (void *)nvn_prof2_entry;' in p2 and \
        'if (NVN_BIG_FN(f)) f = nvn_real_big[i];' in nc, 'NR-28: DM_NVN_PROF=2 and NR-23 see the lean entry as the big-stack wrapper'
    sub = body(nvn, 'NVN(nvnQueueSubmitCommands')
    assert sub.count('NLC();') == 1 and '#define NLC() do { if (__builtin_expect(g_lc_mode, 0)) nvn_lc_submit(); } while (0)' in nvn, \
        'NR-28: one guarded report line in the submit'
    asm = (root / 'gfx/nvn/nvn_entry.S').read_text(encoding='utf-8')
    le = asm[asm.index('_nvn_lean_entry:'):asm.index('Llc_here:')]
    lines = [re.sub(r'//.*', '', l).strip() for l in le.split('\n')[1:]]; lines = [l for l in lines if l]
    before = lines[:lines.index('blr x17')]
    dst = set()
    for l in before:
        op, _, rest = l.partition(' ')
        if op in ('cmp', 'b.ne', 'b.ls'): continue
        if op in ('stp', 'str'):
            w = re.search(r'\[(x\d+|sp), #-?\d+\]!', rest)
            if w: dst.add(w.group(1))
            continue
        if op == 'ldp': dst.update(r.strip() for r in rest.split(',')[:2]); continue
        dst.add(rest.split(',')[0].strip())
    assert dst <= {'x9', 'x10', 'x11', 'x16', 'x17', 'x29', 'sp'} and not any(l.startswith('bl ') for l in lines), \
        'NR-28: before the body the lean entry writes only x9-x11 / x16 / x17 (+ the frame: x29 / sp) and calls nothing: %s' % sorted(dst)
    tab = int(re.search(r'#define NVN_LC_TAB (\d+)', raw_inc).group(1))
    assert 'and x9, x9, #%d' % (tab - 1) in le and 'uint64_t t = tp >> 12; t ^= t >> 10; t ^= t >> 20; return (unsigned)(t & (NVN_LC_TAB - 1));' in inc and \
        ['lsr x9, x17, #12', 'eor x9, x9, x9, lsr #10', 'eor x9, x9, x9, lsr #20'] == [l for l in lines if l.startswith(('lsr x9', 'eor x9'))], \
        'NR-28: the assembly hash = nvn_lc_hash'
    assert 'cmp x11, #256, lsl #12' in le and '#define NVN_BIGSTACK (1u << 20)' in nvn_raw, 'NR-28: the in-place range is NVN_BIGSTACK'
    assert asm[asm.index('Llc_slow:'):].split('\n')[1].strip() == 'b Lnvn_bigstack' and '_nvn_bigstack_entry:\nLnvn_bigstack:' in asm, \
        'NR-28: passing on is a local branch to the old wrapper (no PLT stub to clobber x16)'
    lc = body(inc, 'static __attribute__((noinline)) void *nvn_lc_top(uintptr_t sp) {')
    assert lc.index('__atomic_compare_exchange_n(&e->tp') < lc.index('__atomic_store_n(&e->top'), 'NR-28: a table entry is claimed (thread pointer) before its top is written'
    assert (root / 'gfx/vulkan/engine/tests/nr_leancall_test.py').is_file(), 'NR-28: the emulator test exists'
    print('PASS: NR-28: DM_NR_LEANCALL default 0 (not set by the app, read once), one guarded line in nvn_bigstack_top and in the submit, the lean entry only for =1 '
          'in the big-stack slots, thunk table through nvn_thunk_tab(), DM_NVN_PROF=2 / NR-23 see the lean entry, the entry writes only scratch registers before '
          'the body and calls no C, its hash = nvn_lc_hash, passing on = a local branch to the old wrapper')

def nr13_check():   # [DOS2] NR-13 / NR-26 DM_NR_LEAN (docs/dos2/nr/NR-13.md)
    eng = root / 'gfx/vulkan/engine'
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    fe, st, sth, key = rd('host/hle_dos2_nb.c'), rd('gfx/nvn/nvn_nb_state.inc'), rd('gfx/nvn/nvn_nb_state.h'), rd('gfx/nvn/nvn_nb_key.inc')
    nb, hit, bst, lean, hdr, game = rd('gfx/vulkan/engine/xbg_nb.inc'), rd('gfx/vulkan/engine/xbg_nb_hit.inc'), rd('gfx/vulkan/engine/xbg_nb_state.inc'), rd('gfx/vulkan/engine/xbg_nr_lean.inc'), rd('gfx/nr/nr_lean.h'), rd('gfx/vulkan/engine/xbg_game.cpp')
    jni = rd('android/jni_android.c')
    assert 'DM_NR_LEAN' not in jni, 'NR-13: the app does not set DM_NR_LEAN (default 0)'
    # the switch is read by nr_lean_parse only: once in the front end, once in the backend
    for name, text in (('hle_dos2_nb.c', fe), ('xbg_nr_lean.inc', lean)):
        assert text.count('getenv("DM_NR_LEAN")') == 1 and text.count('nr_lean_parse(') == 1, 'NR-13: %s reads DM_NR_LEAN once, through nr_lean_parse' % name
    assert 'if (!c->mode) c->parts = 0;' in hdr and 'if (c->mode != 1) c->ab = 0;' in hdr, 'NR-13: at 0 no part is armed; the A/B exists only at 1'
    # NRL_STATE, front end: armed only at mode 1 with the part and no consumer; then the state bits are not enabled (or, A/B, paused)
    assert 'g_nrl_state = g_nrl.mode == 1 && (g_nrl.parts & NRL_STATE) && g_nrl_state_why == NRL_ST_OK;' in fe, 'NR-13: NRL_STATE needs mode 1, its part bit and no consumer'
    assert 'g_nrl_state_why = nr_lean_state_why(st != 0, r && atoi(r) != 0, od && atoi(od) != 0);' in fe and 'getenv("DM_NB_RELOC"), *od = getenv("DM_NB_ORDER")' in fe, 'NR-13: the consumers are DM_NB_RELOC / DM_NB_ORDER as set'
    assert fe.count('nvn_nb_state_enable()') == 1, 'NR-13: one place enables the NB-13a capture'
    i = fe.index('if (st && g_nrl_state && !g_nrl.ab) {'); j = fe.index('} else if (st) {', i); k = fe.index('nvn_nb_state_enable(); g_nbs_ops = st;', j)
    assert i < j < k and 'g_nbs_ops' not in fe[i:j], 'NR-13: with NRL_STATE (no A/B) the state bits are not taken at all (g_nbs_ops stays 0: no bracket, no hook)'
    assert fe.index('nr_lean_parse(') < i, 'NR-13: the switch is read before the state bits are taken'
    assert fe.count('nvn_nb_state_pause(') == 2 and 'if (g_nrl_state && !nvn_nb_state_pause(g_nrl_want))' in fe, 'NR-13: the A/B pauses the capture only when NRL_STATE is armed, at one place'
    assert 'if (g_nrl.mode && g_nb.begins && now > g_nb.t_begin) nrl_frame(' in fe and 'if (g_nrl.ab && !g_nb.begins) nrl_phase();' in fe, 'NR-13: the front hooks are behind g_nrl.mode / g_nrl.ab (0: one load each)'
    # the pause: not inside a packet, only the owner, flush before off, forget everything before on
    p = st[st.index('int nvn_nb_state_pause(int off) {'):]; p = p[:p.index('\n}\n')]
    assert p.index('if (!g_nbs_ready || t_nbs_depth) return 0;') < p.index('g_nbs_on = 0;'), 'NR-13: no pause inside a packet / before the capture was enabled'
    assert '!t_nbs_own) return 0;' in p and p.index('nbs_flush();') < p.index('g_nbs_on = 0;'), 'NR-13: only the owner pauses; the shadow goes out before the capture stops'
    assert p.index('nbs_resume(&g_nbs, e)') < p.index('g_nbs_on = 1;') and 'g_nbs_cb = NULL' in p and 'g_nbs_pend.active = 0' in p, 'NR-13: the capture returns with nothing held and a new epoch'
    assert 'static inline void nbs_resume(nbs_state *s, uint32_t epoch) { nbs_unknown(s, (1u << NBS_KINDS) - 1u); s->dirty = 0; nbs_new_epoch(s, epoch); }' in sth, 'NR-13: nbs_resume forgets every kind and starts an epoch'
    # who reads the NB-13a blocks / ids: the replay, NB-17 order (DM_NB_ORDER), NB-14 keys (DM_NB_RELOC) - exactly what nr_lean_state_why lists
    users = set()
    for f in list(eng.glob('*.inc')) + list(eng.glob('*.cpp')) + list(eng.glob('*.h')) + list((root / 'gfx/nvn').glob('*')) + list((root / 'gfx/nb').glob('*.h')) + list((root / 'host').glob('*')):
        if not f.is_file() or f.suffix not in ('.inc', '.cpp', '.h', '.c'): continue
        t = f.read_text(encoding='utf-8', errors='replace')
        if re.search(r'\bnbs_parse\(|nbstate::defs\b|\bg_nbs\.d\[', t) and f.name not in ('nvn_nb_state.h', 'nvn_nb_state.inc'): users.add(f.name)
    assert users == {'xbg_nb_state.inc', 'xbg_nb_order.inc', 'nvn_nb_key.h', 'nvn_nb_key.inc'}, 'NR-13: a new reader of the NB-13a blocks / dictionary: %s - add it to nr_lean_state_why' % sorted(users)
    assert 'if (!g_nbs_on || !t_nbs_own' in key, 'NR-13: the NB-14 resolver refuses while the capture is off'
    assert 'if (reloc) return NRL_ST_RELOC;' in hdr and 'if (order) return NRL_ST_ORDER;' in hdr, 'NR-13: both consumers keep the capture'
    # NRL_UBO, backend: one skip decision, in apply, before the note; never at mode 2; only while NR-06 serves the ring
    assert nb.count('nrlean::skip_notes()') == 1 and 'if(nbubo::mode!=0 && !nrlean::skip_notes())nbubo::note(h,b);' in nb, 'NR-13: the ring notes are skipped at one place'
    s = lean[lean.index('inline bool skip_notes(){'):]; s = s[:s.index('\n// nbdraw::apply, after')]
    assert s.index('if(mode==2){') < s.index('const bool sk=') and 'return false;}   // counted, made' in s, 'NR-13: mode 2 makes every note'
    assert 'nr_lean_ubo_skip(part && phase.load(std::memory_order_relaxed),ring)' in s and 'ring=nrbuf::ring_mode>0' in s, 'NR-13: notes are skipped only while NR-06 serves the ring and the phase is on'
    assert 'static inline int nr_lean_ubo_skip(int live, int ring) { return live && ring; }' in hdr
    assert game.count('nrlean::ubo_off()') == 1 and 'if(nbubo::mode>0 && !nbubo::busy && !nrlean::ubo_off()){Buffer z;const int r=nbubo::fast(address,copy,z);' in game, 'NR-13: NB-12 is skipped at one place, after NR-06 had its turn'
    assert game.index('const int r=nrbuf::ubo(address,copy,z);') < game.index('nrlean::ubo_off()'), 'NR-13: NR-06 answers first'
    u = lean[lean.index('inline bool ubo_off(){'):]; u = u[:u.index('\n// nbdraw::apply, after')]
    assert 'if(__builtin_expect(mode<=0,1))return false;' in u and u.index('if(mode==2){') < u.index('const bool sk=') and 'nr_lean_ubo_skip(part && phase.load(std::memory_order_relaxed),ring)' in u, 'NR-13: NB-12 is asked at 0 and 2, and without the ring'
    assert 'if(!on())return false;' in s and 'inline bool on(){if(__builtin_expect(mode<0,0))init();return mode>0;}' in lean, 'NR-13: at 0 nothing is skipped'
    # the census hooks are behind nrlean::mode > 0 and change nothing
    for text, line in ((nb, 'if(__builtin_expect(nrlean::mode>0,0))nrlean::record('), (nb, 'if(__builtin_expect(nrlean::mode>0,0))nrlean::apply_ns(dt);'),
                       (bst, 'if(__builtin_expect(nrlean::mode>0,0))nrlean::state_block(cb);'), (hit, 'const bool nrl=e && __builtin_expect(nrlean::mode>0,0);')):
        assert text.count(line) == 1, 'NR-13: census hook %r' % line
    assert 'if(nrl)nrlean::ubo_read(why==NBU_DIRECT);' in hit
    for fn in ('record', 'apply_ns', 'ubo_read', 'state_block'):
        b = lean[lean.index('inline void %s(' % fn):]; b = b[:b.index('\n')]
        assert not re.search(r'\b(state|nbdesc|nbubo|tex_gen|buf_gen)\b[^:]', b.replace('state_block', '')), 'NR-13: nrlean::%s only counts' % fn
    assert game.index('#include "xbg_nr_buf.inc"') < game.index('#include "xbg_nr_lean.inc"') < game.index('#include "xbg_nb_hit.inc"'), 'NR-13: nrlean after nrbuf, before its hooks'
    assert 'nrdraw::reset();nrsort::reset();nrlean::on();' in game, 'NR-13: the switch is read at the state reset'
    assert '#include "../' not in hdr and 'Vk' not in hdr, 'NR-13: nr_lean.h is pure C'
    assert (eng / 'tests/nr_lean_test.c').is_file(), 'NR-13: the host test exists'
    print('PASS: NR-13 / NR-26: DM_NR_LEAN default 0 (not set by the app, read once per side through nr_lean_parse); NRL_STATE only at 1 with no reader of the NB-13a '
          'blocks (readers = replay, DM_NB_ORDER, DM_NB_RELOC - checked over the tree), then the state bits are not taken (A/B: paused by the owner between packets, '
          'flushed before, nbs_resume after); NRL_UBO: one skip in nbdraw::apply, only while NR-06 serves the ring, never at 2; census hooks only count')

# NR-29 (docs/dos2/nr/NR-29.md, DM_NR_MEM, default 1: it only lowers defaults; =0 = the old caps, no trims, no thread). The wiring:
#   - main.c installs the front end once, right before dm_dos2_nr_install (NR-05 / NR-22 read their caps there); the app does not set
#     DM_NR_MEM (the code default rules); mode 0 returns before the plan and the thread; mode 2 hands back the old default;
#   - every cache keeps an explicit DM_* MB variable first and asks dm_nr_mem_cap only for its default (NR-05, NR-22, NR-06, the ASTC
#     queue, the warm-up SPIR-V); NR-07 lazy only from mode 1;
#   - the NR-06 static copies are freed only on the translation thread (submission(), behind trim_req), the engine trim holds the engine
#     mutex and checks `initialized`; the usage reader never takes the engine mutex;
#   - the app: onTrimMemory -> nativeTrimMemory for DOS2 behind libraryLoaded; nativeMemInfo before nativeStart; both JNI entries weak;
#   - the rules nr_mem.{h,c} stay engine- and host-free.
def nr29_check():
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8')
    buf = (eng / 'xbg_nr_buf.inc').read_text(encoding='utf-8')
    mem_inc = (eng / 'xbg_nr_mem.inc').read_text(encoding='utf-8')
    pipe = (eng / 'xbg_nr_pipe.inc').read_text(encoding='utf-8')
    host = (root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8')
    fe = (root / 'host/hle_dos2_nr_mem.c').read_text(encoding='utf-8')
    main = (root / 'host/main.c').read_text(encoding='utf-8')
    jni = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    act = (root / 'android/app/src/main/java/com/xiaoboluo/d2r/DmActivity.java').read_text(encoding='utf-8')
    assert main.count('dm_dos2_nr_mem_install();') == 1 and main.index('dm_dos2_nr_mem_install();') < main.index('dm_dos2_nr_install();'), 'NR-29: the front end once, before dm_dos2_nr_install'
    assert not re.search(r'setenv\("DM_NR_MEM', jni), 'NR-29: the app does not set DM_NR_MEM'
    inst = body(fe, 'void dm_dos2_nr_mem_install(void) {')
    assert 'nm_env("DM_NR_MEM", 1, 0, 3)' in inst and inst.index('if (!mode) {') < inst.index('nrm_plan_make(') < inst.index('g_nm_mode = mode;') < inst.index('pthread_create('), \
        'NR-29: DM_NR_MEM default 1; 0 returns before the plan, the mode, the thread'
    assert re.search(r'^static int g_nm_mode;', fe, flags=re.M) and len(re.findall(r'\bg_nm_mode\s*=(?!=)', fe)) == 1, 'NR-29: g_nm_mode starts 0, set once'
    cap = body(fe, 'uint64_t dm_nr_mem_cap(int which, uint64_t dflt) {')
    assert cap.lstrip('{ \r\n').startswith('if (g_nm_mode <= 0') and 'return g_nm_mode == 2 ? dflt : v;' in cap, 'NR-29: off / verify hand back the default'
    assert 'return (g_nm_mode == 1 || g_nm_mode == 3) && g_nm_plan.tier <= NRM_T_6GB;' in fe, 'NR-29: NR-07 lazy only for modes 1 / 3 in the 6 GB class and below'
    assert 'if (g_nm_mode <= 0 || !g_nm_trim) return;' in body(fe, 'void dm_nr_mem_trim_request(int level) {'), 'NR-29: an app trim is only noted, and not at all when off'
    tb = body(fe, 'static void nm_trim(int tier, const char *why) {')
    assert tb.index('if (g_nm_mode == 2) {') < tb.index('dm_nr_tex_mem_trim()') and tb.index('return;') < tb.index('dm_nr_tex_mem_trim()'), 'NR-29: verify frees nothing'
    # each cache: an explicit variable first, the plan only for the default
    h = host.replace('\r', '')
    assert 'if (be && atol(be) > 0) mb = (uint64_t)atol(be);\n    else { mb = dm_nr_mem_cap(NRM_TEXBLOB, mb << 20) >> 20;' in h, 'NR-29: NR-05 DM_NR_TEX_PREP_MB first'
    assert 'ce && atol(ce) > 0 ? (uint64_t)atol(ce) << 20 : be && atol(be) > 0 ? 2 * budget : dm_nr_mem_cap(NRM_TEXSTREAM, 2 * (mb0 << 20))' in h, 'NR-29: NR-22 DM_NR_TEXSTREAM_MB first'
    assert 'budget=be && *be?uint64_t(num("DM_NR_BUF_MB",192,0,4096))<<20:dm_nr_mem_cap?dm_nr_mem_cap(NRM_BUFSTATIC,192ull<<20):192ull<<20;' in buf, 'NR-29: NR-06 DM_NR_BUF_MB first'
    assert 'queue=qe?uint64_t(std::max(8L,atol(qe)))<<20:std::max<uint64_t>(8ull<<20,dm_nr_mem_cap?dm_nr_mem_cap(NRM_ASTCQ,96ull<<20):96ull<<20);' in s, 'NR-29: DM_TEX_ASTC_QUEUE_MB first'
    assert 'if(dm_nr_mem_cap)warm::rewritten_cap=dm_nr_mem_cap(NRM_PIPE,UINT64_MAX);' in s and s.count('rewritten_bytes+=b;') == 1, 'NR-29: the warm-up SPIR-V cap'
    assert 'if(mode==1 && dm_nr_mem_pipe_lazy && dm_nr_mem_pipe_lazy()){mode=3;' in pipe, 'NR-29: NR-07 lazy only from DM_NR_PIPE=1'
    # NR-06: freed on the translation thread only
    assert buf.count('trim();') == 1 and 'if(trim_req.load(std::memory_order_relaxed))trim();' in body(buf, 'void submission(){'), 'NR-29: nrbuf::trim only from submission()'
    assert 'trim()' not in mem_inc.replace('trim_free()', '') and 'nrbuf::trim_req.compare_exchange_weak' in mem_inc, 'NR-29: the engine trim only asks NR-06'
    tr = body(mem_inc, 'extern "C" void xbg_nr_mem_trim(int tier,uint64_t *f){')
    assert 'std::lock_guard<std::recursive_mutex> lock(mutex);if(!initialized)return;' in tr, 'NR-29: the engine trim holds the engine mutex, the device alive'
    assert 'recursive_mutex' not in body(mem_inc, 'extern "C" void xbg_nr_mem_usage(uint64_t *u){'), 'NR-29: the usage reader never takes the engine mutex'
    assert s.count('#include "xbg_nr_mem.inc"') == 1 and s.index('extern "C" void xbg_nr_pipe_source(int on)') < s.index('#include "xbg_nr_mem.inc"'), 'NR-29: xbg_nr_mem.inc once, at file scope after the NR-07 entries'
    # the app
    trim_j = body(act, '@Override public void onTrimMemory(int level) {')
    assert 'if (DOS2 && libraryLoaded) { try { nativeTrimMemory(level); }' in trim_j, 'NR-29: onTrimMemory -> nativeTrimMemory (DOS2, library loaded, an older library tolerated)'
    assert act.index('nativeMemInfo(mi.totalMem, mi.threshold)') < act.index('int result = nativeStart('), 'NR-29: nativeMemInfo before nativeStart'
    for n in ('nativeMemInfo', 'nativeTrimMemory'):
        assert 'Java_com_xiaoboluo_d2r_DmActivity_' + n in jni, 'NR-29: JNI %s' % n
    assert 'void dm_nr_mem_java(int64_t total, int64_t threshold) __attribute__((weak));' in jni and 'void dm_nr_mem_trim_request(int level) __attribute__((weak));' in jni, 'NR-29: JNI entries weak'
    for f in ('gfx/nr/nr_mem.h', 'gfx/nr/nr_mem.c'):
        t = re.sub(r'//[^\n]*', '', (root / f).read_text(encoding='utf-8'))
        assert not re.search(r'\bVk|vulkan|xbg_|LOG\(|#include "(?!nr_mem\.h)', t), 'NR-29: %s stays engine- and host-free' % f
    assert (root / 'gfx/vulkan/engine/tests/nr_mem_test.c').is_file(), 'NR-29: the split test exists'
    print('PASS: NR-29: DM_NR_MEM default 1 (not set by the app; 0 = no plan / thread, 2 = old defaults), installed before NR-05, explicit DM_* MB first for NR-05 / 22 / 06 / '
          'ASTC queue / warm-up SPIR-V, NR-07 lazy only from 1, NR-06 freed only in submission(), engine trim under the engine mutex, usage without it, '
          'onTrimMemory / nativeMemInfo wired (weak JNI), rules engine-free')
def nr30_check():
    # NR-30 (docs/dos2/nr/NR-30.md): DM_DOS2_PREPASS by family + the NR-09 lane for the override draws
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    eng = root / 'gfx/vulkan/engine'
    g = code((eng / 'xbg_game.cpp').read_text(encoding='utf-8'))
    inc = code((eng / 'xbg_nr_draw.inc').read_text(encoding='utf-8'))
    pol = code((eng / 'xbg_vendor_policy.h').read_text(encoding='utf-8'))
    hdr = code((eng / 'xbg_prepass.h').read_text(encoding='utf-8'))
    jni = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    assert 'inline int xbg_dos2_prepass_default(XbgGpuFamily f){return xbg_tile_family(f)?1:0;}' in pol, 'NR-30: the family default = the tile families'
    assert 'DM_DOS2_PREPASS' not in code(jni), 'NR-30: the app does not set DM_DOS2_PREPASS (the policy decides; dm/env still wins)'
    gk = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', (eng / 'xbg_game.cpp').read_text(encoding='utf-8'), flags=re.S)   # comments out, strings kept
    _i = gk.index('struct Guard{bool on=false,done=false;ds_st saved{};uint64_t key=0;~Guard();};'); ns = gk[_i:gk.index('void read_break_log(', _i)]   # the namespace (the first 'namespace prepass{' is its forward declaration)
    cf = body(ns, 'inline int config(){')
    assert cf.index('getenv("DM_DOS2_PREPASS")') < cf.index('xbg_dos2_prepass_default(gpu_policy)') and 'mode=from_env?prepass_clamp_mode(atol(e)):fam_default;' in cf, \
        'NR-30: env first, then the family default'
    assert cf.index('#ifdef DM_GAME_DOS2') < cf.index('xbg_dos2_prepass_default(gpu_policy)') < cf.index('#else') < cf.index('const int fam_default=0;'), \
        'NR-30: the family default only in the DOS2 build'
    pre = body(ns, 'bool pre(Guard &g,int first,int count,const p_draw_idx *indexed,uint32_t instances,bool gi){')
    assert pre.index('if(prepass_frame_begin(pp,stats.presents.load()))retired();') < pre.index('prepass_note_pre(') < pre.index('prepass_note_gbuffer('), \
        'NR-30: the frame retires before any note'
    assert 'return prepass_note_pre(pp,d->serial,&in) && (mode==PREPASS_SKIP || mode==PREPASS_POISON);' in pre, 'NR-30: only modes 1 / 3 skip'
    assert pre.count('state.ds.df=PREPASS_NVN_LEQUAL;state.ds.dw=1;') == 1 and 'if(!prepass_note_gbuffer(pp,d->serial,&in) || mode!=PREPASS_SKIP)return false;' in pre \
        and pre.index('g.on=true;g.saved=state.ds;') < pre.index('state.ds.df=PREPASS_NVN_LEQUAL;') and 'live=&g;' in pre, 'NR-30: the override only in mode 1, saved first, live set'
    assert 'Guard::~Guard(){if(on){state.ds=saved;live=nullptr;if(!done && pp)prepass_note_lost(pp,key);}}' in ns, 'NR-30: the guard restores the state, clears live, reports a lost override'
    assert g.count('if(prepass::live)prepass::live->done=true;') == 1 and inc.count('if(prepass::live)prepass::live->done=true;') == 1, 'NR-30: both draw tails mark the override recorded'
    assert 'prepass::Guard ppg;if(prepass::mode && prepass::pre(ppg,first,count,indexed,instances,gi!=nullptr)){' in g, 'NR-30: the draw() entry hook'
    assert g.count('prepass::read(') == 4 and 'void image_read_hook(Image &im){if(prepass::mode>0)prepass::read(im.source.serial);' in g, \
        'NR-30: reads of the scene depth hooked (shader reads, transfer source, the two copies)'
    ln = body(inc, 'bool lane(Commands &c,Descriptors &d,Pass &p,int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances,uint32_t first_instance,unsigned flags,int draw_fast){') + body(inc, 'unsigned flags,bool ui,int lm,uint32_t active_colors,const Tm &tm){')   # [NR-ZERO Z3] lane() + lane_tail(): the lane as one text
    assert '!(pp?groups_pp():groups())' in ln and ln.index('const bool pp=(flags&F_PP)!=0;') < ln.index('!(pp?groups_pp():groups())'), \
        'NR-30: the lane re-reads the groups from the game state for an override draw'
    assert ln.count('groups()') == 1, 'NR-30: no other group read in lane()'
    assert 'if(pp)v.w[4]|=NR_DRAW_VAR_PP;' in ln and ln.index('if(pp)v.w[4]|=NR_DRAW_VAR_PP;') < ln.index('nrp_tab_find(&T,H.t.key,&H.var)'), 'NR-30: the variant carries the override bit'
    gp = body(inc, 'inline bool groups_pp(){')
    assert 'state.ds=prepass::live->saved;const bool ok=groups();state.ds=cur;' in gp, 'NR-30: groups_pp swaps the game depth state in and back'
    nd = code((root / 'gfx/nr/nr_draw.h').read_text(encoding='utf-8'))
    assert '#define NR_DRAW_VAR_PP (1ull << 30)' in nd, 'NR-30: the variant bit'
    assert 'static inline void prepass_note_read(' in hdr and 'PREPASS_K_FIRST' in hdr and 'prepass_hist_ok(' in hdr, 'NR-30: the header has the gates'
    assert (eng / 'tests/prepass_test.c').is_file(), 'NR-30: prepass_test.c exists'
    print('PASS: NR-30: DM_DOS2_PREPASS env first, then the DOS2-only family default (Mali / PowerVR 1); the frame retires before notes; skip only 1 / 3, '
          'override only 1 (saved, live, restored); depth reads hooked (4); the NR-09 lane takes override draws with groups from the game state and NR_DRAW_VAR_PP')
# NR-31 (the portable pipeline warm-up seed, DM_NR_SEED; docs/dos2/nr/NR-31.md): the hooks sit where the warm-up list is written / taken,
# the launch runs after every policy it reads is set, and the expander's model of draw() / create_pass() / descriptors() (dm/gfx/nr/nr_seed.c)
# still matches the code it mirrors (drift guard: a change to any of these lines fails here and points at nr_seed.c / xbg_nr_seed.inc).
# NR-09R (docs/dos2/nr/NR-09R.md, DM_NR_DIRECT, default 0): the engine draw recorded directly. "Off" = every hook is a load and a
# not-taken branch (the stream is byte for byte the old one); "on" writes through the functions the entry points use; a draw the recorder
# cannot take is decided before anything is written; what is left out is decided by the pure rules of dm/gfx/nr/nr_direct.h.
def nr09r_check():
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    nvn_raw, tap_raw, inc_raw, front_raw = rd('gfx/nvn/hle_nvn.c'), rd('gfx/nvn/nvn_nb_tap.inc'), rd('gfx/nvn/nvn_nr_direct.inc'), rd('host/hle_dos2_nr_direct.inc')
    nvn, tap, inc, front, nbd = code(nvn_raw), code(tap_raw), code(inc_raw), code(front_raw), code(rd('gfx/nvn/nvn_nb_draw.inc'))
    hdr = rd('gfx/nr/nr_direct.h')
    assert re.search(r'\{"DM_NR_DRAW", "1"\}, \{"DM_NR_DIRECT", "1"\},', rd('android/jni_android.c')), 'NR-09R: DOS2 default DM_NR_DRAW=1 DM_NR_DIRECT=1 in the app defaults table (owner 17.11)'
    assert set(re.findall(r'#include [<"]([^>"]+)[>"]', hdr)) == {'stddef.h', 'stdint.h', 'string.h'}, 'NR-09R: nr_direct.h is pure C (no engine / host / NVN / Vulkan header)'
    # the switch: read once per side, armed in one place each
    assert front_raw.count('getenv("DM_NR_DIRECT")') == 1 and rd('gfx/vulkan/engine/xbg_nr_direct.inc').count('getenv("DM_NR_DIRECT")') == 1 and 'getenv("DM_NR_DIRECT")' not in nvn_raw + inc_raw, \
        'NR-09R: DM_NR_DIRECT read once by the front end (nrd_arm) and once by the backend (nrdirect::init)'
    en = body(inc, 'void nvn_nrd_enable(int mode, int parts) {')
    assert len(re.findall(r'\bg_nrd_mode = ', inc + tap + nvn)) == 1 and len(re.findall(r'\bg_nrd_tap = ', inc + tap + nvn)) == 1 and len(re.findall(r'\bg_nrd_texf = ', inc + tap + nvn)) == 1 and \
        'g_nrd_mode = mode;' in en, 'NR-09R: the NVN side is armed only by nvn_nrd_enable'
    ins = body(front, 'static void nrd_install(void) {')
    assert front.count('nvn_nrd_enable(') == 1 and ins.index('if (!g_nr_draw)') < ins.index('nvn_nrd_enable(v, parts);') < ins.index('g_nrd = v;') and \
        "v == 1 && (parts & NRDP_DRAW) && dn_install_draw_native(&k_nrd_draw)" in ins, 'NR-09R: armed after DM_NR_DRAW, the native draw handler only for =1, g_nrd last'
    arm = body(front, 'static void nrd_arm(module_t *m) {')
    assert re.match(r'\{\s*const char \*e = getenv\(""\);\s*const int v = e \? atoi\(e\) : 0;\s*if \(!v\) return;', arm) and 'if (v != 1 && v != 2)' in arm and \
        'nrnc_fnv(' in arm and 'parts &= ~NRDP_DRAW' in arm, 'NR-09R: unset / 0 returns at once; other values off; the draw part needs the analysed code'
    # the include: twice, the hooks before the entry points, the recorder at the end
    assert tap_raw.count('#include "nvn_nr_direct.inc"') == 2 and tap_raw.index('#include "nvn_nr_direct.inc"') < tap_raw.index('static void nbt_bind(') < \
        tap_raw.index('#define NBF_DRAW(op) ((void)0)') < tap_raw.rindex('#include "nvn_nr_direct.inc"') and \
        nvn_raw.count('#include "nvn_nr_direct.inc"') == 1 and nvn_raw.count('#define NVN_NRD_ENTRIES 1') == 1 and \
        nvn_raw.index('#define NVN_NC_ENTRIES 1') < nvn_raw.index('#define NVN_NRD_ENTRIES 1') < nvn_raw.index('#include "nvn_nr_direct.inc"'), \
        'NR-09R: nvn_nr_direct.inc from the tap (the hooks; outside DOS2 its empty macros) and at the end of hle_nvn.c (the recorder), after the entries of NR-23'
    # every hook is one guarded line
    for name, guard in (('NRD_SIG', 'g_nrd_tap'), ('NRD_REGGEN', 'g_nrd_tap'), ('NRD_TAP_PRE', 'g_nrd_tap'), ('NRD_TAP_POST', 'g_nrd_tap'), ('NRD_BT', 'g_nrd_texf'), ('NRD_BT_BEGIN', 'g_nrd_texf'),
                        ('NRD_BT_NESTED', 'g_nrd_texf'), ('NRD_EXT_PUT', 'g_nrd_mode')):
        m = re.search(r'#define %s\([^)]*\) ([^\n]*)' % name, inc)
        assert m and '__builtin_expect(%s, 0)' % guard in m.group(1), 'NR-09R: %s is guarded by %s' % (name, guard)
    bh = body(nvn, 'static void bind_handles(NVNcommandBuffer *c, int op, int st, int first, int n, const uint64_t *h) {')
    assert nvn.count('NRD_BT(') == 1 and bh.index('NBT(nbt_bind(c, op, st, first, n, h));') < bh.index('const int nrd_same = NRD_BT(c, op, st, first, n, h);') < \
        bh.index('if (nrd_same == 2) { wt_use_ids(h, n); return; }') < bh.index('NBD_TEXGEN();') < bh.index('nbd_take_bind(') < bh.index('NRD_BT_FLAG(nrd_same);'), \
        'NR-09R: bind_handles: the tap first, a bind that is not sent keeps its use mark and returns before anything is recorded, the =2 flag only once the bind sits in the shadow'
    assert nvn.count('NRD_BT_BEGIN(') == 1 and 'NRD_BT_BEGIN(o);' in body(nvn, 'NVN(nvnCommandBufferBeginRecording,') and nvn.count('NRD_BT_NESTED(') == 2 and \
        'NRD_BT_NESTED(CB(c));' in body(nvn, 'NVN(nvnCommandBufferCopyCommands,') and 'NRD_BT_NESTED(CB(c));' in body(nvn, 'NVN(nvnCommandBufferCallCommands,'), \
        'NR-09R: the mirror is reset at BeginRecording and forgotten at CopyCommands / CallCommands'
    assert nvn.count('NRD_REGGEN(') == 1 and 'NRD_REGGEN();' in body(nvn, 'static void wt_register(int id, const tex_t *t) {'), 'NR-09R: a pool registration moves the tap memo\'s signature'
    assert tap.count('NRD_SIG(') == 1 and 'if (tab[s] != v) { NRD_SIG(op != OP_BIND_TEX, st, s, tab[s], v); tab[s] = v;' in body(tap, 'static void nbt_bind(') and \
        len(re.findall(r'g_nbt\.(?:tex|img)\[[^\]]*\]\[[^\]]*\] *=[^=]', tap + nvn)) == 0, 'NR-09R: the tap tables change only in nbt_bind, with the signature'
    dr = body(tap, 'static void nbt_draw(NVNcommandBuffer *c, uint64_t handle) {')
    assert tap.count('NRD_TAP_PRE(') == 1 and tap.count('NRD_TAP_POST(') == 1 and \
        dr.index('nb_draw(f, 0);') < dr.index('if (!f->open) return;') < dr.index('if (NRD_TAP_PRE(nrd, f, node, all, handle)) return;') < dr.index('nbt_mask_note(0, 5);') < \
        dr.index('nbt_reads(f, 0, 5, all);') < dr.index('g_nbt.rd_node = node;') < dr.index('NRD_TAP_POST(nrd, f, node, known, exact);'), \
        'NR-09R: nbt_draw counts the draw and syncs the pass before the memo is asked; the walk is skipped as a whole or not at all'
    pre = body(inc, 'static int nrd_tap_pre(')
    assert 'if (g_nrd_tap == 1) {' in pre and pre.index('nrd_tap_hit(') < pre.index('if (g_nrd_tap == 1) {') and 'if (all || !nrd_tap_hit(' in pre, 'NR-09R: only =1 skips the walk; never the first draw of a pass'
    post = body(inc, 'static void nrd_tap_post(')
    assert post.index('if (!known || !exact || nrd_mask_writes() != t->mw)') < post.index('nrd_tap_learn('), 'NR-09R: a walk is remembered only with every mask and the fs key published'
    rs = body(nbd, 'static void nbd_reset(void) {')
    nd = body(nbd, 'static int nbd_draw(')
    assert 'NRD_WF_RESET();' in rs and nbd.count('NRD_EXT_PUT(') == 1 and nd.index('if (nr) nrd_tail_put(') < nd.index('NRD_EXT_PUT(nr, p, size);'), 'NR-09R: the tail word after the tail, the flags reset with the shadow'
    # the recorder: the same functions as the entry points, nothing of its own in the stream
    can = body(inc, 'int nvn_nrd_can(uint64_t cb) {')
    for cond in ('g_nrd_mode == 1', 'g_nbd_on', 't_nbd.in', '!t_nbd.emitting', '!t_nbd_chk', '!t_nd.mode', '!g_nc_cap', 'o->recording'):
        assert cond in can, 'NR-09R: nvn_nrd_can checks %s' % cond
    assert not re.search(r'\w\s*(?:\+\+|--|[-+|&^]?=(?!=))', can.replace('==', '').replace('!=', '').replace('const cmd_t *o =', '')), 'NR-09R: nvn_nrd_can only reads'
    bind = body(inc, 'void nvn_nrd_bind(uint64_t cb, int stage, int slot, int32_t tex, int32_t smp) {')
    assert 'h_nvnDeviceGetTextureHandle(NULL, tex, smp)' in bind and 'bind_handles((NVNcommandBuffer *)(uintptr_t)cb, OP_BIND_TEX, stage, slot, 1, &v);' in bind and 'rec(' not in bind and 'REC' not in bind, \
        'NR-09R: the recorder\'s bind is bind_handles with the handle GetTextureHandle returns'
    drw = body(inc, 'void nvn_nrd_draw(')
    assert drw.index('NBT(nbt_draw(c, 0));') < drw.index('NBD_TAKE(c) && nbd_draw(c, NBD_DRAW_IDX, prim, (int)itype, count, 0, 0, inst, ib, 0)') and \
        '(p_draw_idx){prim, (int)itype, count, 0, 0, inst, ib}' in drw, 'NR-09R: the recorder\'s draw = the body of DrawElements / DrawElementsInstanced (tap, then the record)'
    for fn in ('NVN(nvnCommandBufferDrawElements,', 'NVN(nvnCommandBufferDrawElementsInstanced,'):
        b = body(nvn, fn)
        assert b.index('NBT(nbt_draw(c, 0));') < b.index('NBD_TAKE(c) && nbd_draw(c, NBD_DRAW_IDX,'), 'NR-09R: %s still has the order the recorder copies' % fn
    hook = body(inc, 'static int nrdm_bind_hook(NVNcommandBuffer *c, int op, int st, int first, int n, const uint64_t *h) {')
    assert 'const int in = g_nbd_on && t_nbd.in && !t_nbd.emitting, adopt = in && !t_nbd_chk;' in hook and 'if (!nrdm_filter(same, adopt, kind, n) || !nbd_bind_ok(NBD_B_TEX, st, first)) return 0;' in hook and \
        hook.index('nrdm_filter(') < hook.index('if (g_nrd_texf == 1)') < hook.index('return 2;'), 'NR-09R: a bind stays unsent only by nrdm_filter, inside an engine draw bracket, with =1'
    assert 'static inline int nrdm_filter(int same, int adopt, unsigned kind, int n) { return same && adopt && kind == NRDM_TEX && n == 1; }' in hdr, 'NR-09R: the filter rule'
    # the front end: nothing touched before the decision; the model drives the recorder
    take = body(front, 'static int nrd_draw_take(')
    order = [take.index(x) for x in ('if (!nrd_live())', 'if (!nrnc_draw_pre(R, (int)op, first, count, inst, &d))', 'if (!nvn_nrd_can(d.cb))', 'g_nrd_ubo_fill(r);', 'nvn_on_bigstack(nrd_job, &j);', 'return 1;')]
    assert order == sorted(order) and take.count('return 0;') == 3 and take.index('return 1;') > take.rindex('return 0;'), 'NR-09R: every refusal comes before the first write / call of a direct draw'
    head = take[:take.index('g_nrd_ubo_fill(r);')]
    assert not re.search(r'\bR\[[^\]]*\]\s*=[^=]|nrnc_w16|g_o_tf\(|nvn_nrd_bind|nvn_nrd_draw|nk_draw\(|nrd_ident\(', head), 'NR-09R: before the decision the renderer is only read'
    job = body(front, 'static void *nrd_job(void *a) {')
    assert 'nrnc_flush_run(j->R, j->p, j->cb, &k_nrd_ops, a);' in job and 'nrnc_draw_tail(j->R, j->d, g_nrd_isz, &k_nrd_ops, a);' in job and \
        'static const nrnc_ops k_nrd_ops = {nrd_op_bind, nrd_op_ren, nrd_op_draw};' in front, 'NR-09R: the model of NR-23 (nr_nocall.h) makes the calls, the recorder is its ops'
    od = body(front, 'static void nrd_op_draw(')
    assert od.index('dm_nr_tap_draw(') < od.index('nvn_nrd_draw('), 'NR-09R: the identity is handed over (the NR-02 tap line of the entry point) before the draw is recorded'
    key = code(rd('host/hle_dos2_nr_key.inc'))
    kd = body(key, 'static void nk_draw(uint64_t r, uint64_t lr) {')
    assert re.match(r'\{\s*if \(g_nr_key == 3\) \{\s*if \(g_nrd_lean == 1\) \{ nrd_ident_lr\(r, lr\); return; \}\s*nk_ident\(r, lr\);\s*if \(__builtin_expect\(g_nrd_lean == 2, 0\)\) nrd_ident_cmp\(r, lr\);\s*return;\s*\}', kd), \
        'NR-09R: the lean identity only in the identity-only mode of NR-09; =2 runs nk_ident and compares'
    assert 'g_nrd_lean = (parts & NRDP_IDENT) && g_nr_key == 3 && g_nr_draw == 1 ? v : 0;' in ins and len(re.findall(r'\bg_nrd_lean = ', front + key)) == 1, 'NR-09R: lean identity only without the census and with DM_NR_DRAW=1'
    idn = body(front, 'static void nrd_ident(uint64_t r, int si) {')
    assert 't_nk.id_ts = 0;' in idn and 'nk_ident(r,' in idn, 'NR-09R: the lean identity leaves the texture-set id 0 and falls back to nk_ident without memory'
    nr_c = rd('host/hle_dos2_nr.c')
    assert nr_c.index('nrd_arm(m);') < nr_c.index('nc_arm(m);') < nr_c.index('nk_draw_install(m, rc == 0);') < nr_c.index('nc_install();') < nr_c.index('nrd_install();') and \
        nr_c.index('#include "hle_dos2_nr_nocall.inc"') < nr_c.index('#include "hle_dos2_nr_direct.inc"'), 'NR-09R: armed before NR-23 (=2 arms its compare), installed after DM_NR_DRAW and NR-23'
    # the backend: the check before the binds land, one guarded line
    nb = code(rd('gfx/vulkan/engine/xbg_nb.inc'))
    ap = body(nb, 'void apply(const uint8_t *p,size_t n){')
    assert nb.count('nrdirect::pre(') == 1 and ap.index('if(__builtin_expect(nrdirect::mode,0)){if(nrdirect::mode<0)nrdirect::init();if(nrdirect::mode>0 && (h.flags&NBD_F_NR))nrdirect::pre(p,n,h,b);}') < \
        ap.index('nbd_apply(&h,b,state.tex,state.samp,state.img,ub_tab(),&ts,&bs)'), 'NR-09R: the backend looks at the tail word before the record\'s binds land'
    be = code(rd('gfx/vulkan/engine/xbg_nr_direct.inc'))
    assert not re.search(r'state\.\w+(?:\[[^\]]*\])*\s*=[^=]|vkCmd|tex_gen|buf_gen', be), 'NR-09R: the backend side only reads and counts'
    game = rd('gfx/vulkan/engine/xbg_game.cpp')
    assert game.index('#include "xbg_nr_direct.inc"') < game.index('#include "xbg_nb.inc"'), 'NR-09R: xbg_nr_direct.inc before xbg_nb.inc'
    assert (root / 'gfx/vulkan/engine/tests/nr_direct_test.c').is_file(), 'NR-09R: the host test exists'
    print('PASS: NR-09R: DM_NR_DIRECT default 0 (not set by the app, read once per side), every hook one guarded line, the recorder = the entry points\' own functions '
          '(bind_handles, the tap, nbd_draw) driven by the NR-23 model, refusals before the first write, binds left out only by nrdm_filter, the walk skipped only by the memo, '
          'lean identity only in identity-only mode, the backend checks before the binds land')

def nr09s_check():   # NR-09S DM_NR_STATE (docs/dos2/nr/NR-09S.md): opcode 21 as native code
    h = (root / 'gfx/nr/nr_state.h').read_text(encoding='utf-8')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stddef', 'stdint', 'string'] and 'LOG(' not in h and '#include "' not in h, 'NR-09S: nr_state.h is pure C'
    a = h.index('static inline int nrst_lookup('); b = h.index('static inline void nrst_commit(')
    model = h[a:b]
    assert not re.search(r'nrst_w(64|32)\(|\b[RPE]\[[^\]]*\]\s*=[^=]|NRST_PTR\([^)]*\)\[[^\]]*\]\s*=[^=]', model), 'NR-09S: the model (lookup, SetShader, SetBlend, VB, the packet) only reads guest memory'
    slots = re.findall(r'\{0x2bb[0-9a-f]+, "(nvn\w+)"\}', h)
    assert len(slots) == 19, 'NR-09S: 19 NVN slots'
    n = (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8')
    assert n.count('NST(NRST_F_') == 19, 'NR-09S: one NST line in each of the 19 entry points'
    for name in slots:
        i = n.index('NVN(%s, ' % name); body = n[n.index('{', i) + 1:].lstrip()
        body = re.sub(r'^(?:(?:NRT|NCT)\(.*\s*)+', '', body)   # NR-02's tap line / NR-23's capture line stay first where they are
        assert body.startswith('NST(NRST_F_'), 'NR-09S: the NST line is the first statement of %s' % name
    assert n.index('#include "nvn_nr_nocall.inc"') < n.index('#include "nvn_nr_state.inc"') < n.index('NVN(nvnCommandBufferBindProgram,'), 'NR-09S: the capture before the bodies'
    assert n.index('#define NVN_NC_ENTRIES 1') < n.index('#define NVN_NRS_ENTRIES 1') and n.rstrip().endswith('#include "nvn_nr_state.inc"   // [DOS2] NR-09S DM_NR_STATE: the executor of the native opcode-21 packet (second part)') or n.index('#define NVN_NRS_ENTRIES 1') > n.index('#define NVN_NRD_ENTRIES 1'), 'NR-09S: the executor after NR-23\'s direct entries (nc_slot / nc_impl)'
    v = (root / 'gfx/nvn/nvn_nr_state.inc').read_text(encoding='utf-8')
    fns = re.findall(r'NRST_F_(\w+) = 1', h) + re.findall(r'^    NRST_F_(\w+),', h, re.M)
    assert len(fns) == 19, 'NR-09S: 19 call kinds'
    ex = v[v.index('void nvn_nrs_exec('):]
    for k, f in enumerate(fns):
        m = re.search(r'case NRST_F_%s: h_(nvn\w+)\(' % f, ex)
        assert m and m.group(1) == slots[k], 'NR-09S: the executor calls the body of %s for NRST_F_%s' % (slots[k], f)
    want = re.findall(r'\(void \*\)h_(nvn\w+)', v[v.index('int nvn_nrs_ready('):v.index('void nvn_nrs_exec(')])
    assert want == slots, 'NR-09S: nvn_nrs_ready checks the bodies in NRST_SLOTS order'
    assert not re.search(r'cmd_alloc|\bREC\(|rec\(', ex), 'NR-09S: the executor writes nothing itself (the bodies do)'
    f = (root / 'host/hle_dos2_nr_state.inc').read_text(encoding='utf-8')
    take = f[f.index('static int nrs_take('):f.index('// ---- the 10 s lines')]
    assert take.rindex('return 0;') < take.index('nrst_commit(') < take.index('nvn_on_bigstack(nrs_job, s)'), 'NR-09S: every refusal comes before the first store / call'
    assert take.index('nvn_nrs_cap_begin();') < take.index('*len = dn_rc_call_orig(list, 21, pkt);\n        const uint64_t t3') < take.index('nvn_nrs_cap_end(&g)'), 'NR-09S: =2 captures around the engine\'s handler'
    assert take.index('if (!nrst_code21(') < take.index('if (g_nrs == 1) {\n        nrst_commit('), 'NR-09S: the model decides before anything is written'
    allsrc = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (root / 'host').iterdir() if p.suffix in ('.c', '.h', '.inc')) + (root / 'android/jni_android.c').read_text(encoding='utf-8')
    assert allsrc.count('getenv("DM_NR_STATE")') == 1 and '{"DM_NR_STATE", "4"}' in (root / 'android/jni_android.c').read_text(encoding='utf-8'), 'NR-09S: DM_NR_STATE read once, the app sets 4 (batch C, owner 19.11)'
    nat = (root / 'host/hle_dos2_native.c').read_text(encoding='utf-8')
    hk = nat[nat.index('static uint64_t dn_rc_hook('):nat.index('// ---- DM_NATIVE_DRAW=1 / 2 ----')]
    assert 'if (!(__builtin_expect(g_rc_take_ops != 0, 0) && c < 64 && (g_rc_take_ops >> c & 1) && g_rc_take(list, c, pkt, &len))) len = g_rc_orig(list, op, pkt, a3, a4, a5);' in hk, 'NR-09S: the original runs unless the native handler took the packet'
    assert hk.index('->pre(list, c, pkt)') < hk.index('g_rc_take(') < hk.index('->post(list, c, pkt, len)'), 'NR-09S: pre / post handlers (the NB-13a bracket) around the native handler'
    nr = (root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8')
    assert nr.index('nrd_install();') < nr.index('nrs_install();') and nr.count('nrs_report(df)') == 1, 'NR-09S: installed last, reported with the NR lines'
    for t in ('nr_state_test.c', 'nr_state_oracle.py'): assert (root / 'gfx/vulkan/engine/tests' / t).is_file(), 'NR-09S: %s exists' % t
    print('PASS: NR-09S: nr_state.h pure C, the model only reads (stores in nrst_commit), 19 NST lines first in their entry points, the executor = the 19 bodies in slot order, '
          'refusals before the first store, =2 captures around the engine\'s handler, DM_NR_STATE default 0 read once')

def nr09u_check():   # NR-09U DM_NR_UBO (docs/dos2/nr/NR-09U.md): the engine's uniform blocks of a direct draw as native code
    h = (root / 'gfx/nr/nr_ubo.h').read_text(encoding='utf-8')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint', 'string', 'sched'] and 'LOG(' not in h and '#include "' not in h, 'NR-09U: nr_ubo.h is pure C'
    d = h[h.index('static inline int nru_draw('):h.index('// =2, after the engine')]
    pre = d[:d.index('nru_rlock(s, GL);')]
    assert not re.search(r'nru_rebuild\(|nru_put\(|nru_w(64|32)\(|memcpy\(NRU_PTR|__atomic', pre), 'NR-09U: nothing is stored before r\'s read lock (the refusals there come first)'
    g = d[d.index('nru_rlock(s, GL);'):d.index('// ---- 0x925740 ----')]
    assert g.index('if (why) { if (!sim) nru_runlock(GL); s->why = why; return 0; }') < g.index('nru_rebuild('), 'NR-09U: the global list\'s refusals give r\'s lock back before any block store'
    assert d[d.index('if (why) { if (!sim) nru_runlock(GL); s->why = why; return 0; }') + 64:].count('return 0;') == 0, 'NR-09U: no refusal after the first rebuild'
    rb = h[h.index('static inline void nru_rebuild('):h.index('static inline void nru_put(')]
    assert rb.index('nru_wlock(s, D + NRU_D_LOCK);') < rb.index('__atomic_store_n((uint32_t *)(void *)(D + NRU_D_HEAD), h') < rb.index('old = __atomic_fetch_add((uint32_t *)(void *)(D + NRU_D_HEAD), size') < rb.index('nru_wunlock(D + NRU_D_LOCK);') < rb.index('nru_copy_fwd('), 'NR-09U: the ring allocation in the machine code\'s order (writer lock, plain head store, fetch-add, unlock, then the copy)'
    assert 'NRU_SPINS = 400' in h and 'NRU_YIELD_THREAD();' in h and 'NRU_LOCK_W = 0x100000, NRU_LOCK_R = 0xfffff' in h, 'NR-09U: the engine\'s spin (400 x yield, then YieldThread) and lock layout'
    assert len(re.findall(r'\{(0x[0-9a-f]+), (0x[0-9a-f]+), (0x[0-9a-f]+)ull, "', h)) == 4, 'NR-09U: four code hashes'
    n = (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8')
    i = n.index('NVN(nvnCommandBufferBindUniformBuffer, '); body = n[n.index('{', i) + 1:].lstrip()
    assert body.startswith('NUB(c, st, i, a, n);') and n.count('NUB(') == 1, 'NR-09U: one NUB line, first in the BindUniformBuffer body'
    assert n.index('#include "nvn_nr_state.inc"') < n.index('#include "nvn_nr_ubo.inc"') < i, 'NR-09U: the capture before the body'
    assert n.index('#define NVN_NC_ENTRIES 1') < n.index('#define NVN_NRU_ENTRIES 1'), 'NR-09U: the executor after NR-23\'s direct entries (nc_slot / nc_impl)'
    v = (root / 'gfx/nvn/nvn_nr_ubo.inc').read_text(encoding='utf-8')
    ex = v[v.index('void nvn_nru_exec('):]
    assert 'h_nvnCommandBufferBindUniformBuffer(' in ex and not re.search(r'cmd_alloc|\bREC\(|rec\(', ex), 'NR-09U: the executor = the body (writes nothing itself)'
    assert 'nc_impl(i) == (void *)h_nvnCommandBufferBindUniformBuffer' in v, 'NR-09U: nvn_nru_ready checks the body'
    f = (root / 'host/hle_dos2_nr_ubo.inc').read_text(encoding='utf-8')
    take = f[f.index('static const nru_run *nru_take('):f.index('static void nru_job_calls(')]
    one = take[take.index('if (g_nru == 1) {\n        const uint64_t t0'):take.index('// =2: the simulation')]
    assert one.index('if (!nru_draw(r, s, 0)) {') < one.index('return s;') and 'fill(r); bind(r); return NULL; }' in one, 'NR-09U: =1 refused -> the engine\'s functions, else the run goes to the job'
    two = take[take.index('// =2: the simulation'):]
    assert two.index('nru_draw(r, s, 1)') < two.index('nvn_nru_cap_begin();') < two.index('fill(r); bind(r);\n    const nru_call') < two.index('nvn_nru_cap_end(&got)') < two.index('nru_check('), 'NR-09U: =2 simulates, then captures around the engine\'s functions, then compares'
    dr = (root / 'host/hle_dos2_nr_direct.inc').read_text(encoding='utf-8')
    tk = dr[dr.index('static int nrd_draw_take('):dr.index('static void nrd_draw_after(')]
    assert tk.index('if (!nvn_nrd_can(d.cb)) {') < tk.index('ub = nru_take(r, g_nrd_ubo_fill, g_nrd_ubo_bind);') < tk.index('nvn_on_bigstack(nrd_job, &j);'), 'NR-09U: the model after the direct draw decided, before the job'
    jb = dr[dr.index('static void *nrd_job('):dr.index('static int nrd_draw_take(')]
    assert jb.index('if (j->ub) nru_job_calls(j->ub);') < jb.index('nrnc_flush_run(') < jb.index('nrnc_draw_tail('), 'NR-09U: the calls first in the job (the engine made them before the flush)'
    allsrc = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (root / 'host').iterdir() if p.suffix in ('.c', '.h', '.inc')) + (root / 'android/jni_android.c').read_text(encoding='utf-8')
    assert allsrc.count('getenv("DM_NR_UBO")') == 1 and '{"DM_NR_UBO", "1"}' in (root / 'android/jni_android.c').read_text(encoding='utf-8'), 'NR-09U: DM_NR_UBO read once, the app sets 1 (batch C, owner 19.11)'
    nr = (root / 'host/hle_dos2_nr.c').read_text(encoding='utf-8')
    assert nr.index('nrd_install();') < nr.index('nru_install(g_nrd, g_nrd_parts);') and nr.index('#include "hle_dos2_nr_ubo.inc"') < nr.index('#include "hle_dos2_nr_direct.inc"'), 'NR-09U: installed after NR-09R, included before it'
    for t in ('nr_ubo_test.c', 'nr_ubo_oracle.py'): assert (root / 'gfx/vulkan/engine/tests' / t).is_file(), 'NR-09U: %s exists' % t
    print('PASS: NR-09U: nr_ubo.h pure C, nothing stored before r\'s lock and every refusal before the first block store (the lock given back), the ring allocation in the '
          'machine code\'s order with its spin, one NUB line first in BindUniformBuffer, the executor = the body, =1 calls first in the direct job, =2 simulates / captures / '
          'compares, DM_NR_UBO default 0 read once')

def nr09s3_check():   # NR-09S3 DM_NR_STATE=4 / 5 (docs/dos2/nr/NR-09S.md §10): one OP_X_NR_STATE record per opcode-21 packet
    h = (root / 'gfx/nr/nr_state3.h').read_text(encoding='utf-8')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stddef', 'stdint', 'string'] and re.findall(r'#include "([\w.]+)"', h) == ['nr_state.h'] and 'LOG(' not in h, 'NR-09S3: nr_state3.h is pure C'
    b = h[h.index('static inline int nr3_build('):h.index('// The NB-13a kinds the record writes')]
    assert not re.search(r'memcpy\(NRST_PTR|NRST_PTR\([^)]*\)\[[^\]]*\]\s*=[^=]|nr3_writeback', b), 'NR-09S3: nr3_build writes no guest memory (setters on copies)'
    for hk in ('NR3_BLEND_DEF(&x->v)', 'NR3_BLEND_TARGET(&x->v, o->i)', 'NR3_COLOR_DEF(&x->v)', 'NR3_COLOR_ATEST(&x->v, o->i)', 'NR3_COLOR_BLEND(&x->v, o->i, (uint32_t)o->j)'):
        assert hk in b, 'NR-09S3: the setter %s runs on the packet\'s copy' % hk
    f = (root / 'gfx/nvn/nvn_nr_state3.inc').read_text(encoding='utf-8')
    for mac, body in (('NR3_BLEND_DEF', 'h_nvnBlendStateSetDefaults'), ('NR3_BLEND_TARGET', 'h_nvnBlendStateSetBlendTarget'), ('NR3_COLOR_DEF', 'h_nvnColorStateSetDefaults'),
                      ('NR3_COLOR_ATEST', 'h_nvnColorStateSetAlphaTest'), ('NR3_COLOR_BLEND', 'h_nvnColorStateSetBlendEnable'), ('NR3_SNAP_PROG', 'snap_prog')):
        assert re.search(r'#define %s\([^)]*\) [^\n]*\b%s\(' % (mac, body), f), 'NR-09S3: %s is the body %s' % (mac, body)
    ex = f[f.index('uint32_t nvn_nrs3_exec('):]
    m5 = ex[ex.index('if (mode == 5) {'):ex.index('b->r.flags = 0;')]
    assert 0 <= m5.index('b->r.flags = NR3_F_CHECK;') < m5.index('nr3_rec_write(c, &b->r);') < m5.index('nvn_nrs_exec(op, n);') < m5.index('e.flags = NR3_F_CHECK_END;') < m5.index('nr3_rec_write(c, &e);'), \
        'NR-09S3: =5 writes CHECK, makes the calls through the bodies, then CHECK_END'
    m4 = ex[ex.index('b->r.flags = 0;'):]
    assert 0 <= m4.index('NRT(dm_nr_tap_bind(c, p, st)); NBT(nbt_program(c, p, st));') < m4.index('nr3_writeback(b);') < m4.index('NBS_EXT_BEFORE();') < m4.index('nr3_rec_write(c, &b->r);') \
        < m4.index('NBS_EXT_AFTER(nr3_kinds(&b->r));') < m4.index('h_nvnCommandBufferSetRenderEnable(c,'), 'NR-09S3: =4 taps, write-back, shadow flush, the record, kinds unknown, then the render-enable bodies'
    assert ex.index('if (!nr3_build(b, op, n)) return 0;') < ex.index('nr3_rec_write('), 'NR-09S3: not representable = nothing written (the caller makes the calls)'
    n = (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8')
    assert n.rstrip().endswith('#include "nvn_nr_state3.inc"   // [DOS2] NR-09S3 DM_NR_STATE=4 / 5: the packet as one OP_X_NR_STATE record (empty outside DOS2)'), 'NR-09S3: included last in hle_nvn.c'
    st = (root / 'gfx/nvn/nvn_nb_state.inc').read_text(encoding='utf-8')
    assert 'if (g_nbs.dirty || __atomic_load_n(&g_nbs_xunk, __ATOMIC_RELAXED)) nbs_flush();' in st and 'nbs_settle(); nbs_unknown_k(kinds);' in st, 'NR-09S3: the shadow flushes before the record and forgets its kinds after it'
    # the backend: the program bind is execute()'s OP_BIND_PROGRAM case
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    e = (root / 'gfx/vulkan/engine/xbg_nr_state3.inc').read_text(encoding='utf-8')
    case = g[g.index('        case OP_BIND_PROGRAM:{CPU_SCOPE(Program);auto a=payload<p_bind_program>(p,n);') + len('        case OP_BIND_PROGRAM:{CPU_SCOPE(Program);auto a=payload<p_bind_program>(p,n);'):]
    case = case[:case.index('break;}\n') if 'break;}\n' in case else case.index('break;}\r\n')]
    case = re.sub(r'/\*.*?\*/', '', case)
    bind = e[e.index('template<class T> inline void bind('):]; bind = bind[bind.index('{') + 1:bind.index('}}\n') + 1 if '}}\n' in bind else bind.index('}}\r\n') + 1]
    norm = lambda t: re.sub(r'\s+', '', t)
    want = norm(case.replace('a.prog', 'prog').replace('a.stages', 'stages').replace('state.shader', 'S.shader').replace('missing_program', 'missing')
                .replace('if(!prog)break;', 'if(!prog)return;').replace('if(nbpost::mode)', 'if(publish && nbpost::mode)'))
    assert norm(bind).rstrip('}') == want.rstrip('}'), 'NR-09S3: nrstate3::bind is not execute()\'s OP_BIND_PROGRAM case'
    assert g.count('case OP_X_NR_STATE:nrstate3::exec(p,n);break;') == 1 and g.index('#include "xbg_nb_post.inc"') < g.index('#include "xbg_nr_state3.inc"') < g.index('void execute(const uint8_t *pc,unsigned depth,uint64_t &budget){'), \
        'NR-09S3: one execute() case, the namespace after nbpost (its program table) and before execute()'
    ex3 = e[e.index('void exec('):]
    assert ex3.index('if(!flags){need(apply_state(&state,p,n)==0') < ex3.index('nbpipe::G->dirty|=nr3_kinds_raw(p)') < ex3.index('else if(flags==NR3_F_CHECK){snap_of(&want,&state,missing_program);need(apply_snap(&want,p,n)==0'), \
        'NR-09S3: =4 applies to State and dirties its NB-13b groups; CHECK applies to the copy only'
    # the front end switch
    fr = (root / 'host/hle_dos2_nr_state.inc').read_text(encoding='utf-8')
    assert 'if (v != 1 && v != 2 && v != 4 && v != 5)' in fr and 'getenv("DM_NB_RELOC")' in fr and 'w = 1; }' in fr, 'NR-09S3: 4 / 5 accepted, DM_NB_RELOC turns them into 1'
    take = fr[fr.index('static int nrs_take('):fr.index('// ---- the 10 s lines')]
    assert take.index('if (g_nrs == 1) {\n') < take.index('} else if (g_nrs >= 4) {') < take.index('nvn_on_bigstack(nrs3_job, s)') < take.index('} else {   // =2'), 'NR-09S3: =4 / =5 after the model decided, one big-stack call'
    job = fr[fr.index('static void *nrs3_job('):fr.index('static void nrs_red(')]
    assert 'if (!got) nvn_nrs_exec(s->op, s->nops);' in job, 'NR-09S3: a packet the record cannot represent goes through the bodies'
    t = (root / 'gfx/vulkan/engine/tests/nr_state3_test.c').read_text(encoding='utf-8')
    assert '#include "../../../nr/nr_state3.h"' in t and 'NR3_DEFINE_APPLY_RAW(apply_model_raw' in t, 'NR-09S3: the test runs the header\'s builder and the backend\'s raw apply'
    print('PASS: NR-09S3: nr_state3.h pure C, the builder writes no guest memory (setters on copies = the bodies), =4 taps -> write-back -> shadow flush -> record -> kinds unknown -> '
          'render-enable bodies, =5 CHECK / bodies / CHECK_END, the backend\'s program bind = execute()\'s case, one execute() case, DM_NB_RELOC -> 1, fallback through the bodies')

def nr31_check():
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_seed.inc').read_text(encoding='utf-8')
    pol = (root / 'gfx/vulkan/engine/xbg_nr_seed_policy.inc').read_text(encoding='utf-8')
    core = (root / 'gfx/nr/nr_seed.c').read_text(encoding='utf-8'); hdr = (root / 'gfx/nr/nr_seed.h').read_text(encoding='utf-8')
    vp = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    jni = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    # hooks
    assert g.count('#include "xbg_nr_seed.inc"') == 1 and g.count('#include "xbg_nr_seed_policy.inc"') == 1, 'NR-31: the two includes once each'
    rec = body(g, 'void record(const VkGraphicsPipelineCreateInfo &ci,const XbgPipelineKey &key){')
    assert rec.count('if(pseed::mode)pseed::created(ci,bytes);') == 1 and rec.index('pseed::created') < rec.index('known.insert'), 'NR-31: record() reports every in-frame build before its known check'
    tk = body(g, 'bool take(const std::string &bytes,VkPipeline &out){')
    assert 'if(pseed::mode)pseed::took(bytes);' in tk and tk.index('ready.erase(it);') < tk.index('pseed::took'), 'NR-31: take() counts seed pipelines after taking'
    fl = body(g, 'void flush(){if(pseed::mode)')
    assert fl.startswith('{if(pseed::mode)pseed::merge(pending);') and fl.count('if(pseed::mode)pseed::mark();') == 2, 'NR-31: flush merges the seed records first, marks after a write or with nothing to write'
    sd = body(g, 'void shutdown(){')
    assert sd.index('.join()') < sd.index('pseed::reset();') and sd.rindex('std::lock_guard<std::mutex> l(mu);') < sd.index('pseed::reset();'), 'NR-31: reset after the joins, mu held (report)'
    ini = body(g, 'extern "C" int xbg_game_initialize(')
    la = ini.index('warm::pseed::launch(nrseed_policy());')
    assert ini.count('warm::pseed::launch(') == 1 and ini.index('d24s8_as_d32s8=(') < la and ini.index('depth16_as_d24=!d16_linear') < la and ini.index('warm::start();') < la \
        and ini.index('tile_barrier_on=xbg_env_or(') < la and re.match(r'warm::pseed::launch\(nrseed_policy\(\)\);[^\n]*\n    return 0;\n\}$', ini[la:]), 'NR-31: launch is the last statement, after every policy it reads'
    assert g.index('#include "xbg_nr_seed.inc"') > g.index('bool build(const Rec &rec){') and g.index('#include "xbg_nr_seed.inc"') < g.index('void start(){\n    seed();'), 'NR-31: the seed include after build(), before start()'
    assert inc.count('getenv("DM_NR_SEED")') == 1 and 'DM_NR_SEED' not in jni and 'inline int xbg_nr_seed_default(){return 1;}' in vp, 'NR-31: DM_NR_SEED read once at launch; the app sets nothing; the policy default'
    lw = body(inc, 'void worker(){')
    assert lw.index('nsd_expand(') < lw.index('known.insert(bytes)') < lw.index('build(rec)') and 'if(mode==2)continue;' in lw and lw.index('if(mode==2)continue;') < lw.index('known.insert'), \
        'NR-31: re-target, then dedupe against the list, then build; mode 2 builds nothing'
    assert lw.index('if(e){++refused[e];') < lw.index('build(rec)'), 'NR-31: a refused record is never built'
    assert 'format_properties' not in lw and 'format_properties' not in body(inc, 'int shader_cb(') and 'vertex_format_fallback(' not in inc, \
        'NR-31: the seed threads read only the tables filled at launch (format_properties is not thread safe)'
    # create_pass dependencies: one definition
    cp = body(g, 'bool create_pass(Pass &p,Commands &c,int clear_color=-1,bool clear_depth=false,bool soft=false){')
    assert 'VkSubpassDependency dep[2];pass_deps(dep);' in cp and 'dstStageMask=' not in cp, 'NR-31: create_pass takes its dependencies from pass_deps'
    pdb = body(g, 'void pass_deps(VkSubpassDependency dep[2]){')
    assert 'dep[0]={VK_SUBPASS_EXTERNAL,0,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT,VK_ACCESS_MEMORY_WRITE_BIT,VK_ACCESS_COLOR_ATTACHMENT_READ_BIT|VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT|VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT|VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT,0};' in pdb \
        and 'dep[1]={0,VK_SUBPASS_EXTERNAL,VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT|VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT,VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,0};' in pdb \
        and 'if(tile_barrier_on){dep[0].dstStageMask=tile_frag_stages;dep[1].dstStageMask=tile_frag_stages|VK_PIPELINE_STAGE_TRANSFER_BIT;}' in pdb, 'NR-31: pass_deps = nsd_pass_deps (the launch also compares them)'
    assert 'a.loadOp=VK_ATTACHMENT_LOAD_OP_LOAD;a.storeOp=VK_ATTACHMENT_STORE_OP_STORE;a.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_LOAD;a.stencilStoreOp=VK_ATTACHMENT_STORE_OP_STORE;a.initialLayout=a.finalLayout=VK_IMAGE_LAYOUT_GENERAL;' in cp, \
        'NR-31: create_pass definitions are LOAD / STORE / GENERAL (nsd_shape)'
    # descriptors(): dyn_mode_for, UBO_DYN, the layout key (nsd_layout)
    dm = body(g, 'unsigned dyn_mode_for(bool compute,bool *no_ubo=nullptr){')
    assert 'if(b.type==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER){all+=b.count;if(b.source==XBG_SOURCE_UNIFORM||b.source==XBG_SOURCE_DRIVER0||b.source==XBG_SOURCE_DRIVER2)vary+=b.count;}' in dm \
        and dm.index('if(!ubo_dynamic_on)return 0;') < dm.index('nrdesc::split_on') < dm.index('if(nrubd::ro)') \
        and dm.rstrip().endswith('return all && all<=lim?1:(vary && vary<=lim && dyn_partial_enabled?2:0);}'), "NR-31: dyn_mode_for = nsd_layout's mode"
    assert '#define UBO_DYN(mode,b) ((b).type==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER && ((mode)==1 || ((mode)==2 && ((b).source==XBG_SOURCE_UNIFORM||(b).source==XBG_SOURCE_DRIVER0||(b).source==XBG_SOURCE_DRIVER2)) || ((mode)==3 && nrdesc::split_has(&(b)))) && !(nrubd::ro' in g, 'NR-31: UBO_DYN'
    assert 'key.push_back(b.binding);key.push_back(UBO_DYN(dmode,b)?VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC:b.type);key.push_back(b.count);key.push_back(1u<<st);' in g \
        and 'need(b.count && b.count<=128 && (b.type<=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER || b.type==VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT),"Unsupported descriptor array/type");' in g, \
        'NR-31: the layout key loop (binding, type, count, 1 << stage; NR-ONCHIP: + the light.s2 twin INPUT_ATTACHMENT, never seeded: its module is not in the warm-up)'
    assert 'else mode = all && all <= lim ? 1 : (vary && vary <= lim && pol->dyn_partial ? 2 : 0);' in core, 'NR-31: nsd_layout mode'
    # NR-31b: dyn_mode_for's other two rules are modelled (nsd_layout): NR-08 split = refused (layout picked at run time), NR-08b read-only
    assert 'if(nrdesc::split_on && !compute && vary>lim && !(all && all<=lim) && nrdesc::split_pick(lim))return 3;' in dm \
        and 'if(nrubd::ro)return vary && vary<=lim && dyn_partial_enabled?2:0;' in dm, 'NR-31b: dyn_mode_for split / read-only rules (nsd_layout models these lines)'
    assert 'if (pol->split && vary > lim && !(all && all <= lim) && split_eligible(sh, nsh, lim)) return NSD_E_SPLIT;' in core \
        and 'if (pol->ubo_ro) mode = vary && vary <= lim && pol->dyn_partial ? 2 : 0;' in core and '&& !(pol->ubo_ro && !sh[s]->read[i]);' in core, 'NR-31b: nsd_layout split / ro'
    dsi = (root / 'gfx/vulkan/engine/xbg_nr_desc.inc').read_text(encoding='utf-8')
    sp = body(dsi, 'bool split_pick(unsigned lim){')
    assert 'if(x.source==XBG_SOURCE_DRIVER0 || x.source==XBG_SOURCE_DRIVER2){ok=false;break;}' in sp and 'if(x.source!=XBG_SOURCE_UNIFORM)continue;' in sp \
        and 'if(x.count!=1 || x.slot>=16 || n>=NRD_MAX_UBO){ok=false;break;}' in sp and 'if(ok && n>lim)' in sp and 'bool ok=lim>0;' in sp, 'NR-31b: split_pick = nr_seed.c split_eligible'
    assert 'split_on=m==1 && ubo_dynamic_on && (e && *e?atoi(e)!=0:xbg_nr_desc_split_default(ubo_dynamic_on));' in dsi \
        and 'p.split=e && atoi(e)==1 && ubo_dynamic_on && (sp && *sp?atoi(sp)!=0:xbg_nr_desc_split_default(ubo_dynamic_on));' in pol \
        and 'p.ubo_ro=nrubd::ro;' in pol and 'p.unmodelled=0;' in pol, 'NR-31b: the destination policy predicts nrdesc::init split_on and takes the NR-08b rule'
    ubi = (root / 'gfx/vulkan/engine/xbg_nr_ubodyn.inc').read_text(encoding='utf-8')
    assert 'b.flags|=XBG_BIND_SCANNED;if(!rd[k])b.flags|=XBG_BIND_UNREAD;' in ubi and 'nr_spv_binding_reads(words.data(),words.size(),bn.data(),unsigned(bn.size()),rd.data());' in ubi \
        and 'if(n)nr_spv_binding_reads(w.data(),w.size(),bn,n,rd);' in body(inc, 'int shader_cb('), 'NR-31b: the seed reads uniform bindings as nrubd::mark scans them (final words)'
    # NR-31b: fused post stages ("F1.<host>", "F1A.<host>") are composed as the draw path does; nsd_key_parse takes nbpost::fused_name's keys
    assert '(nbpost::fused_name(key)?nbpost::warm_bundle(key,b):xpack::read(key,b,from_pack))' in body(inc, 'int shader_cb('), 'NR-31b: shader_cb fused bundles'
    npost = (root / 'gfx/vulkan/engine/xbg_nb_post.inc').read_text(encoding='utf-8')
    assert "bool fused_name(const std::string &k){if(k.size()<=3 || k[0]!='F' || (k[1]!='1' && k[1]!='2'))return false;" in npost \
        and "const size_t d=k.find('.');return d!=std::string::npos && d>=2 && d<=4;}" in npost and "if (s[0] == 'F' && (s[1] == '1' || s[1] == '2')) {" in core, 'NR-31b: fused_name = nsd_key_parse'
    # draw() / format() / get_image: the fields the expander maps
    for line in ['if(rs.polygonMode!=VK_POLYGON_MODE_FILL && !cfg.enabled_core.fillModeNonSolid)',
                 'rs.depthBiasConstantFactor=state.bias[1]*(state.rt.depth && state.rt.depth->d.format==0x32 && depth16_as_d24?256.0f:1.0f)*(depth_bias_x2?2.0f:1.0f);',
                 'if(state.depth_clamp){if(cfg.enabled_core.depthClamp)rs.depthClampEnable=VK_TRUE;',
                 'if(rs.depthBiasClamp && !cfg.enabled_core.depthBiasClamp)',
                 'if(ds.depthBoundsTestEnable && !cfg.enabled_core.depthBounds)',
                 'if(noout_mask_on && !attachments.empty()){const Shader *fs=state.shader[4];if(!fs || (!fs->raster.outputs && !fs->raster.sample_mask)){for(auto &a:attachments)a.colorWriteMask=0;',
                 'if(cfg.enabled_core.logicOp){blend.logicOpEnable=VK_TRUE;blend.logicOp=VkLogicOp(state.color.logic_op);}',
                 'if((vtx_conv>>(2*a.location))&3)break;   // converted, not bitcast',
                 'const uint32_t want=xbg_vertex_format_class(int(a.format));if(want!=vs.input_classes[i])code|=(want+1)<<(2*a.location);break;}',
                 'VkFormat fmt=format(a.fmt);if(!(format_properties(fmt).bufferFeatures&VK_FORMAT_FEATURE_VERTEX_BUFFER_BIT)){uint32_t scaled_kind=0;fmt=vertex_format_fallback(fmt,loc,a.offset,state.stream[a.stream].stride,&scaled_kind);vtx_conv|=scaled_kind<<(2*loc);}',
                 'VkDynamicState dynamic[]={VK_DYNAMIC_STATE_VIEWPORT,VK_DYNAMIC_STATE_SCISSOR};',
                 'if(conv)snprintf(tag,sizeof tag,"#vi%08xc%08x",code,conv);else snprintf(tag,sizeof tag,"#vi%08x",code);',
                 'snprintf(tag,sizeof tag,"#at%u_%08x",func,bits);',
                 'if(v==VK_FORMAT_D24_UNORM_S8_UINT && d24s8_as_d32s8)return VK_FORMAT_D32_SFLOAT_S8_UINT;if(v==VK_FORMAT_X8_D24_UNORM_PACK32 && x8d24_as_d32)return VK_FORMAT_D32_SFLOAT;',
                 'if(t->d.format==0x32 && depth16_as_d24)p->fmt=VK_FORMAT_X8_D24_UNORM_PACK32;',
                 'if(depth16_as_d24 && x8d24_as_d32)depth16_as_d24=false;']:
        assert g.count(line) >= 1, 'NR-31 drift: a draw() / format() line the seed expander mirrors changed: ' + line[:90]
    vf = body(g, 'VkFormat vertex_format_fallback(VkFormat f,uint32_t loc,uint32_t offset,uint32_t stride,uint32_t *conv){')
    assert 'VkFormat t=VkFormat(integer);const bool widened=!usable(t);if(widened)t=xbg_vertex_widen(t);' in vf and 'if(!usable(t))return f;' in vf and '*conv=kind;return t;}' in vf \
        and 'const VkFormat w=xbg_vertex_widen(f);if(w==VK_FORMAT_UNDEFINED || !(format_properties(w).bufferFeatures&VK_FORMAT_FEATURE_VERTEX_BUFFER_BIT))return f;' in vf, \
        'NR-31 drift: vertex_format_fallback changed (xbg_nr_seed.inc launch mirrors it without its log lines)'
    num = {'R8G8B8_UNORM': 23, 'R8G8B8_SNORM': 24, 'R8G8B8_UINT': 27, 'R8G8B8_SINT': 28, 'R8G8B8A8_UNORM': 37, 'R8G8B8A8_SNORM': 38, 'R8G8B8A8_UINT': 41, 'R8G8B8A8_SINT': 42,
           'R16G16B16_UNORM': 84, 'R16G16B16_SNORM': 85, 'R16G16B16_UINT': 88, 'R16G16B16_SINT': 89, 'R16G16B16_SFLOAT': 90, 'R16G16B16A16_UNORM': 91, 'R16G16B16A16_SNORM': 92,
           'R16G16B16A16_UINT': 95, 'R16G16B16A16_SINT': 96, 'R16G16B16A16_SFLOAT': 97, 'R32G32B32_UINT': 104, 'R32G32B32_SINT': 105, 'R32G32B32_SFLOAT': 106,
           'R32G32B32A32_UINT': 107, 'R32G32B32A32_SINT': 108, 'R32G32B32A32_SFLOAT': 109}
    wb = body(vp, 'inline VkFormat xbg_vertex_widen(VkFormat f){')
    host = {num[a]: num[b] for a, b in re.findall(r'case VK_FORMAT_(\w+):return VK_FORMAT_(\w+);', wb)}
    mine = {int(a): int(b) for a, b in re.findall(r'case (\d+): return (\d+);', body(core, 'uint32_t nsd_vertex_widen(uint32_t f) {'))}
    assert host and host == mine, f'NR-31 drift: xbg_vertex_widen {host} != nsd_vertex_widen {mine}'
    assert set(re.findall(r'#include <(\w+)\.h>', core + hdr)) <= {'stddef', 'stdint', 'stdio', 'stdlib', 'string'} and 'vulkan' not in re.sub(r'//[^\n]*', '', core + hdr).lower(), 'NR-31: nr_seed.{h,c} pure C'
    print('PASS: NR-31: DM_NR_SEED read once (default xbg_nr_seed_default, the app sets nothing), hooks in record / take / flush / shutdown, launch last in '
          'xbg_game_initialize; seed threads re-target, dedupe, then build (refused never, mode 2 nothing) from tables filled at launch; create_pass / '
          'dyn_mode_for / UBO_DYN / layout key / draw() field mappings / format() stand-ins / vertex_format_fallback / xbg_vertex_widen match nr_seed.c')


def nrlightfuse_check():   # NR-LIGHTFUSE DM_NR_LIGHTFUSE (docs/dos2/nr/NR-LIGHTFUSE.md): Sky -> Light as one fused draw
    def code(t): return re.sub(r"""/\*.*?\*/|//[^
]*""", "", t, flags=re.S)
    eng = root / 'gfx/vulkan/engine'
    h = code((root / 'gfx/nr/nr_lightfuse.h').read_text(encoding='utf-8'))
    assert 'vulkan' not in h.lower() and 'getenv' not in h and '#include <' in h, 'NR-LIGHTFUSE: nr_lightfuse.h pure C'
    c = code((eng / 'xbg_game.cpp').read_text(encoding='utf-8')); inc = code((eng / 'xbg_nr_lightfuse.inc').read_text(encoding='utf-8'))
    oc = code((eng / 'xbg_nr_onchip.inc').read_text(encoding='utf-8')); pol = code((eng / 'xbg_vendor_policy.h').read_text(encoding='utf-8'))
    gm = code((eng / 'xbg_pass_gmem.inc').read_text(encoding='utf-8')); sh = code((eng / 'xbg_nr_sh.inc').read_text(encoding='utf-8'))
    assert 'inline int xbg_nr_lightfuse_default(XbgGpuFamily){return 1;}' in pol and 'inline int xbg_nr_lightfuse_fog_default(XbgGpuFamily){return 1;}' in pol, 'NR-LIGHTFUSE: default 1 + FOG 1 on every family (owner 19.11)'
    sm = (eng / 'xbg_safe_mode.h').read_text(encoding='utf-8')
    assert 'add("DM_NR_LIGHTFUSE","0");add("DM_NR_SH_PCF","0");add("DM_NR_PRESKIN","0");add("DM_NR_IDVS","0");' in sm, 'NR-LIGHTFUSE / T11: safe-mode step 1 turns the 19.11 defaults off on tilers'
    dr = c[c.find('void draw(int prim,int first,int count,'):]
    assert 0 <= dr.find('if(nrlf::mode>0 && nrlf::pre(lfg,prim,first,count,indexed!=nullptr,instances)){if(nbchk::armed)nbchk::draw();return;}') < dr.find('if(nroc::mode>0)nroc::pre(ocg);')         < dr.find('descriptors_stable(c,false)'), 'NR-LIGHTFUSE: the twins are set before the descriptors, before nroc'
    assert 0 <= dr.find('    create_pass(p,c);DRAW_MARK(2);') < dr.find('if(nrlf::fused_draw && pgm::mode){pgm::note_lightfuse(c.command);') < dr.find('nrdraw::lane('),         'NR-LIGHTFUSE: the GMEM note right after create_pass'
    assert 0 <= c.find('nrlf::init();') < c.find('nroc::init();') and 'if(nrlf::mode>0)nrlf::tick();' in c and 'constexpr int mode=0;constexpr bool fused_draw=false;' in c
    assert '&& !nrlf::fused_draw;' in c, 'NR-LIGHTFUSE: no descriptor memo for the fused draw (its extras come from the stash)'
    assert 'const int fe=nrlf::fe_mode(m);if(nrlf::mode)m=0;' in oc and 'dm_nr_onchip_publish(fe);' in oc, 'NR-LIGHTFUSE: supersedes the onchip backend, keeps the marks'
    assert "const bool lf=oc_var=='f' || oc_var=='g';" in sh and "lf?nr_lf_bindings_ok(" in sh and "(oc_var=='g'?no!=(to|2u):to!=no)" in sh and         "xpack::nrsh::oc_var=v;" in inc, 'NR-LIGHTFUSE: the f / g bundles through oc_apply with the extras check (g: out 1 more)'
    # fog (DM_NR_LIGHTFUSE_FOG): skipped only after a fused Light; the redirect ends at the target's next write / another submission
    fd = inc[inc.find('int fogdraw('):inc.find('void redirect(')]
    assert fd.find('if(!fused)return 0;') < fd.find('return 1;') and fd.count('return 1;') == 1 and 'rd.writer=ci.provenance_writer;' in fd, 'NR-LIGHTFUSE fog: skip only after the fused Light'
    rd_ = inc[inc.find('void redirect('):inc.find('int pre(')]
    assert 'rd.c->provenance_writer!=rd.writer' in rd_ and 'hd->seq!=rd.seq' in rd_ and '==rd.c){rd.on=false;return;}' in rd_, 'NR-LIGHTFUSE fog: redirect window'
    assert 'if(mrt){state.rt=rt;state.color.blend_en=blend_en;state.mask.mask=mask;}' in inc and 'state.tex[1][re_slot[i]]=re_h[i];' in inc, 'NR-LIGHTFUSE fog: Guard restores'
    assert 'o->known && !o->lf ? nrgm_decide(' in gm, 'NR-LIGHTFUSE: GMEM keeps the fused passes in sysmem'
    # the Sky draw keeps its pass (rasterizer discard twin, not a skipped draw); the Guard restores shader, discard and the spare slots
    assert 'state.rast_discard=1;' in inc and 'return 1' not in inc.split('void sky(')[1].split('void light(')[0], 'NR-LIGHTFUSE: Sky is drawn with discard, never dropped'
    g = inc[inc.find('struct Guard{'):]; g = g[:g.find('}};') + 3]
    assert 'state.shader[4]=fs' in g and 'state.rast_discard=was_disc' in g and '++tex_gen[1];++buf_gen[1];' in g, 'NR-LIGHTFUSE: Guard restores the state'
    # the extras table is the one the pack tool checks
    py = (root.parent / 'tools/dos2_lightfuse.py').read_text(encoding='utf-8')
    for f, k in re.findall(r'\{(\d+), (\d+), NR_LF_(?:TEX|UBO)\}', h):
        assert re.search(r'%s: \(%s, ' % (f, k), py), 'NR-LIGHTFUSE: extra %s <- %s in tools/dos2_lightfuse.py EXTRAS' % (f, k)
    print('PASS: NR-LIGHTFUSE: nr_lightfuse.h pure C, default 0; draw() hook before nroc and the descriptors, GMEM note after create_pass; onchip backend superseded '
          '(marks kept); f bundle via oc_apply with the extras check; Sky drawn with rasterizer discard; Guard restores; extras C == Python')


def nronchip_check():   # NR-ONCHIP DM_NR_ONCHIP (docs/dos2/nr/NR-ONCHIP.md §8): marks in the PASS headers, the merged Sky -> Light render pass
    def code(t): return re.sub(r"""/\*.*?\*/|//[^\n]*""", "", t, flags=re.S)
    eng = root / 'gfx/vulkan/engine'
    obj = (root / 'gfx/nvn/nvn_obj.h').read_text(encoding='utf-8'); tap = (root / 'gfx/nvn/nvn_nb_tap.inc').read_text(encoding='utf-8')
    ir = (root / 'gfx/nb/nb_ir.h').read_text(encoding='utf-8'); oc = (root / 'gfx/nb/nb_onchip.h').read_text(encoding='utf-8')
    fe = code((root / 'host/hle_dos2_nb.c').read_text(encoding='utf-8'))
    s = (eng / 'xbg_game.cpp').read_text(encoding='utf-8'); c = code(s); inc = code((eng / 'xbg_nr_onchip.inc').read_text(encoding='utf-8'))
    # header byte in the former padding, copied from the plan; the plan clears it first
    assert re.search(r'uint8_t end, flags, plan_ok, read_over;[^\n]*\n\s*uint8_t oc;', obj), 'NR-ONCHIP: p_nb_pass.oc right after read_over (byte 111)'
    assert 'static_assert(offsetof(p_nb_pass,oc)==111 && offsetof(p_nb_pass,cover_dc)==112 && sizeof(p_nb_pass)==512' in inc
    assert 'r->oc = np->oc;' in tap and re.search(r'uint8_t flags;[^\n]*\n\s*uint8_t oc;', ir), 'NR-ONCHIP: nb_node_plan.oc copied into the header'
    assert 'for (int i = 0; i < f->nnode; i++) pl->node[i].oc = 0;' in oc, 'NR-ONCHIP: nb_onchip_plan clears every mark first'
    # front end: plans only while the backend published a mode > 0, after the post plan, before the headers are patched
    pl = fe[fe.find('static void nb_ir_plan(void)'):]; pl = pl[:pl.find('\n}\n')]
    assert 0 <= pl.find('dm_nb_post_plan(f, &g_irpo)') < pl.find('nr_oc_plan(f, &g_irpo)') < pl.find('nvn_nb_tap_patch('), 'NR-ONCHIP: FE plan order'
    assert 'if (!rc && __atomic_load_n(&g_nr_oc, __ATOMIC_RELAXED) > 0) nr_oc_plan(f, &g_irpo);' in pl, 'NR-ONCHIP: FE plan gated by the published mode'
    # backend hooks, each gated (mode 0: nothing runs)
    eo = c[c.find('void end_open_pass(int line){'):]; eo = eo[:eo.find('void full_barrier(')]
    assert 0 <= eo.find('if(nroc::active)nroc::before_end(open_pass.cmd,line);') < eo.find('vkCmdEndRenderPass(open_pass.cmd);') and eo.count('nroc::') == 2, 'NR-ONCHIP: end_open_pass steps M first (with the call line: early-end sites)'
    dr = c[c.find('void draw(int prim,int first,int count,'):]
    assert 0 <= dr.find('if(nroc::mode>0)nroc::pre(ocg);') < dr.find('descriptors_stable(c,false)') < dr.find('    create_pass(p,c);DRAW_MARK(2);') \
        < dr.find('if(nroc::mode>0 && !nroc::adjust(p,c)){') < dr.find('Descriptors &d=*dp;') < dr.find('nrdraw::lane('), 'NR-ONCHIP: draw() order (twin before the descriptors, adjust after create_pass)'
    # [early end, 19.11 N_oc3mr] adjust() false never skips the draw: the game's shader back, descriptors + pass again, then the normal path
    rd = dr[dr.find('if(nroc::mode>0 && !nroc::adjust(p,c)){'):dr.find('Descriptors &d=*dp;')]
    assert 'return' not in rd and 0 <= rd.find('nroc::redo(ocg);') < rd.find('build_stages();') < rd.find('dp=&descriptors_stable(c,false);') < rd.find('create_pass(p,c);'),         'NR-ONCHIP: a twin draw that lost M is drawn as recorded (redo), never skipped'
    assert 'if(z3r!=3)dp=&descriptors_stable(c,false);' in dr and 'void redo(Guard &g){if(g.saved){state.shader[4]=g.saved;g.saved=nullptr;}nexting=twin_draw=false;' in inc
    assert 'if(nroc::active)nroc::note_read(im,why);' in c, 'NR-ONCHIP: the read that ends M is named (early-end site)'
    pr = inc[inc.find('void pre(Guard &g){'):inc.find('void redo(Guard &g)')]
    assert 'reads_ok(*state.shader[4],tws[tw],mode!=2,r.k)' in pr and 'else brk(why);return;' in pr and 'pre_why=why' not in pr and 'pre_why=r.k' not in pr,         'NR-ONCHIP: a member that cannot run in M (checks or its descriptor reads) ends M in pre(), before its descriptors'
    # [early clears, 19.11 P_oc3m] pending clears of the members' learned sampled images land at M's begin: after M's render pass exists,
    # before M's full barrier (and the begin); =2 only counts; learning in reads_ok covers every binding (the first bad one still decides)
    bg = inc[inc.find('bool begin(Pass &p,Commands &c,const p_nb_pass &hd){'):inc.find('void note_pass(')]
    assert 0 <= bg.find('end_open_pass();') < bg.find('if(!r){++s.refused[R_RP];return false;}') < bg.find('pre_flush(p.images[0],p.images[1],tl?ci:nullptr,tl,true);') \
        < bg.rfind('full_barrier(cmd);') < bg.find('vkCmdBeginRenderPass('), 'NR-ONCHIP: early clears land outside M, before its full barrier'
    pf = inc[inc.find('uint32_t pre_flush('):inc.find('bool begin(Pass &p,')]
    assert 'if(e.im!=a && e.im!=b && e.im!=c && nb_oc_learned_has(&learned,fog?2:1,e.im->source.serial)' in pf and 'if(exec)for(uint32_t i=0;i<n;i++)pclear_flush_image(*pick[i],0);' in pf \
        and pf.count('pclear_') == 1, 'NR-ONCHIP: only learned images with a pending clear, landed by pclear_flush_image (mode 2: none)'
    assert 'pre_flush(p.images[0],p.images[1],shadow_tail?ci:nullptr,shadow_tail,false);' in inc and inc.count('pre_flush(') == 3, 'NR-ONCHIP: =2 counts would-flush'
    ro = inc[inc.find('unsigned reads_ok('):inc.find('void pre(Guard &g){')]
    assert 'nb_oc_learn_reset(&learned,k);' in ro and 'if(role==3)nb_oc_learn_add(&learned,k,im->source.serial);\n            if(bad)continue;' in ro and 'if(bad)break;' not in ro, \
        'NR-ONCHIP: every sampled image of the member learned, the first bad binding decides'
    assert 'if(create_pass(p,c,-1,false,true)){\n#ifdef DM_GAME_DOS2\n                if(nroc::mode>0)nroc::adjust(p,c);' in s, 'NR-ONCHIP: in-pass clears go through adjust'
    assert 'ci.renderPass=p.pass;ci.subpass=p.subpass;' in c and 'uint8_t subpass=0;' in c, 'NR-ONCHIP: pipelines of M carry their subpass'
    assert '&& !nroc::twin_draw && !nrlf::fused_draw;' in c and 'if(b.type==VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT){ii.imageView=nroc::input_view(im);ii.imageLayout=VK_IMAGE_LAYOUT_GENERAL;}else{' in c, \
        'NR-ONCHIP: the input attachment descriptor (no memo, no sampled read)'
    assert c.count('if(nroc::usage_on && (usage&VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT)') == 2 and '|(usage&VK_IMAGE_USAGE_INPUT_ATTACHMENT_BIT)' in c, 'NR-ONCHIP: usage only while executing'
    assert c.count('VkImageUsageFlags(VK_IMAGE_USAGE_INPUT_ATTACHMENT_BIT),VkImageUsageFlags(VK_IMAGE_USAGE_STORAGE_BIT)') == 2, 'NR-ONCHIP: an unsupported input usage is dropped first'
    assert 'nroc::init();' in c and 'if(nroc::mode>0)nroc::tick();' in c and 'constexpr int mode=0;constexpr bool usage_on=false,active=false,twin_draw=false;' in c
    # the merged pass's own begin: one vkCmdBeginRenderPass, through lrz_touch_before (NB-19), nbtr::decide first; stores STORE; packets for NextSubpass
    assert inc.count('vkCmdBeginRenderPass(') == 1 and 0 <= inc.find('nbtr::decide(p,0,0)') < inc.find('lrz_touch_before(p,cmd)') < inc.find('vkCmdBeginRenderPass('), 'NR-ONCHIP: M begin path'
    assert 'VK_ATTACHMENT_STORE_OP_STORE' in inc and 'STORE_OP_DONT_CARE' not in inc, 'NR-ONCHIP: first version keeps every store'
    assert 'full_barrier(cmd);' in inc and 'VK_DEPENDENCY_BY_REGION_BIT' in inc and 'inputAttachmentCount=7' in inc
    mt = (eng / 'xbg_nb_mt.inc').read_text(encoding='utf-8')
    assert '#define vkCmdNextSubpass nbmt::CmdNextSubpass' in mt and 'OP_EndConditionalRendering, OP_NextSubpass, OP_COUNT' in mt
    # defaults and safe mode
    pol = (eng / 'xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_onchip_default(XbgGpuFamily f){return xbg_tile_family(f)?1:0;}' in pol, 'NR-ONCHIP: 1 on the tile families (19.11), 0 on Adreno'
    assert 'add("DM_NR_ONCHIP","0");' in (eng / 'xbg_safe_mode.h').read_text(encoding='utf-8')
    # the pack: light.s2 / light.s3 built by setup stage 8
    pk = (root.parent / 'tools/dos2_nr_sh_pack.py').read_text(encoding='utf-8')
    assert "OC_VARIANTS = {'ClusteredLightingWithSSAO': [('2', 0x40), ('3', 0xC0)]}" in pk
    sh = (eng / 'xbg_nr_sh.inc').read_text(encoding='utf-8')
    assert 'thread_local char oc_var=0;' in sh and 'bool oc_apply(const std::string &key,std::vector<uint8_t> &bytes){' in sh and         'if(have && !out.empty() && nrsh::oc_var)return nrsh::oc_apply(key,out) && have;' in c, 'NR-ONCHIP: the light.s2 bundle only while oc_var is set (twin_module)'
    print('PASS: NR-ONCHIP marks (header byte 111), FE plan gated, merged pass hooks gated (end / pre / adjust / clear / subpass / input descriptor / usage), default 0, safe mode step 1')


def safemode_check():   # [DOS2][safe-mode] docs/dos2/nr/SAFE-MODE.md (xbg_safe_mode.h / .inc; DOOM 2016 B&F 2.57): the GPU safe mode wiring
    def code(s): return re.sub(r"""/\*.*?\*/|//[^\n]*""", "", s, flags=re.S)
    def blk(s, head):   # the brace block that starts at head
        i = s.find(head); assert i >= 0, 'SAFE: %s not found' % head
        j = s.find('{', i + len(head) - 1); d = 0
        for k in range(j, len(s)):
            d += {'{': 1, '}': -1}.get(s[k], 0)
            if d == 0: return s[i:k + 1]
        raise AssertionError('SAFE: unbalanced %s' % head)
    eng = root / 'gfx/vulkan/engine'
    hdr = (eng / 'xbg_safe_mode.h').read_text(encoding='utf-8')
    sw = blk(hdr, 'inline int xbg_safe_switches(int step,XbgGpuFamily f,XbgSafeSwitch *out,int max){')
    keys = re.findall(r'add\("(DM_[A-Z0-9_]+)","([01])"\)', sw)
    assert len(keys) >= 30 and len({k for k, _ in keys}) == len(keys), 'SAFE: the step switches, each key once (%d)' % len(keys)
    # every key is a switch this tree reads (no dead names from DOOM's list)
    src = ''
    for d in ('gfx', 'host', 'android'):
        for f in (root / d).rglob('*'):
            if f.suffix in ('.c', '.cpp', '.h', '.inc') and 'tests' not in f.parts and f.is_file():
                src += f.read_text(encoding='utf-8', errors='replace')
    for k, _ in keys:
        assert re.search(r'getenv\("%s"\)|\{"%s", "[0-9a-fx]+"\}|"%s",' % (k, k, k), src), 'SAFE: %s is neither read (getenv) nor in a switch table' % k
    # step 3 = the v0.1.1 renderer: every NB / NR / present-thread entry of the app's default table (jni k_nb_on) is turned off by some step
    jni_raw = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    jni = code(jni_raw)
    tab = jni[jni.find('static const char *const k_nb_on[][2] = {'):]; tab = tab[:tab.find('};')]
    table = re.findall(r'\{"(DM_[A-Z0-9_]+)", "([^"]*)"\}', tab)
    assert len(table) >= 15, 'SAFE: jni k_nb_on not found'
    off = {k for k, _ in keys}
    for k, v in table:
        if k in ('DM_NB_OPS', 'DM_DOS2_PARTICLES_FULL'): continue   # NB's op mask (inert with DM_NB=0) and a game-side particle setting
        assert k in off, 'SAFE: the app default %s=%s is not undone by any safe-mode step (add it to xbg_safe_switches step 3)' % (k, v)
    # boot: in the presenter after the physical device, before DM_NR_ROTATE is read and before vkCreateDevice
    vp = code((root / 'android/vulkan_present.cpp').read_text(encoding='utf-8'))
    init = vp[vp.find('extern "C" int dm_android_vk_initialize(const char *path,char *error,size_t bytes){'):]
    b, ph, rot, dev = init.find('xbg_safe_mode_boot(sp.vendorID,sp.deviceName)'), init.find('physical=devices[0];'), init.find('getenv("DM_NR_ROTATE")'), init.find('vkCreateDevice(')
    assert 0 < ph < b < rot and (dev < 0 or b < dev) and init.count('getenv("DM_NR_ROTATE")') == 1, 'SAFE: boot after the physical device, before DM_NR_ROTATE / vkCreateDevice'
    assert '__attribute__((weak)) void xbg_safe_mode_boot(uint32_t vendor,const char *name);' in vp, 'SAFE: weak boot in the presenter'
    # engine: init right after the policy family, before the first family switch; the fatal records device-lost / hang; the per-present tick
    g = code((eng / 'xbg_game.cpp').read_text(encoding='utf-8'))
    i = g.find('safe_mode_engine_init();')
    assert g.count('safe_mode_engine_init();') == 1 and g.find('gpu_policy=xbg_effective_family(gpu_family,sim_gpu);') < i < g.find('gpguard::serial=xbg_env_or('), \
        'SAFE: safe_mode_engine_init after gpu_policy, before DM_GFX_PIPE_SERIAL is read'
    fat = g[g.find('extern "C" __attribute__((noreturn)) void xbg_fatalf('):]; fat = fat[:fat.find('\n')]
    assert 'xbg_safe_text_device_lost(error_text) || xbg_safe_text_gpu_hang(error_text)' in fat and 'xbg_safe_mode_record(w);' in fat and fat.find('xbg_safe_mode_record') < fat.find('cfg.fatal'), \
        'SAFE: xbg_fatalf counts a device-lost / GPU-hang fatal before the app hears of it'
    assert g.count('safemode::frame_tick();') == 1 and g.find('static void xbg_present_texture_now(') < g.find('safemode::frame_tick();'), 'SAFE: one test tick per present'
    assert g.count('#include "xbg_safe_mode.inc"') == 1 and 0 < g.find('std::atomic<bool> serial{false};') < g.find('#include "xbg_safe_mode.inc"'), 'SAFE: the .inc after gpguard'
    rec = blk(g, 'void record(const std::string &combo,VkResult r){')
    lock = blk(rec[1:], '{std::lock_guard<std::mutex> l(mu);')
    assert rec.count('live_pipe(combo,r);') == 1 and 'live_pipe' not in lock and rec.find('live_pipe(combo,r);') > rec.find(lock[-40:]), 'SAFE: gpguard::record calls live_pipe after its lock block'
    inc = code((eng / 'xbg_safe_mode.inc').read_text(encoding='utf-8'))
    assert 'setenv(sw[i].key,sw[i].value,1);' in inc and 'xbg_safe_should_set(have,pl)' in inc and 'dm_env_player?dm_env_player(sw[i].key):-1' in inc, 'SAFE: boot sets over the app table, keeps the player'
    assert inc.count('raise(SIGBUS);') == 1 and 'fake_rec_at.compare_exchange_strong(at,0)' in inc, 'SAFE: the rec test fires once'
    assert 'if(!eligible)return;' in blk(inc, 'extern "C" void xbg_crash_classify(int sig,const char *thread,const char *rec,uint64_t addr,const char *pc_lib,const char *lr_lib){'), 'SAFE: classify only on Mali / PowerVR'
    mt = (eng / 'xbg_nb_mt.inc').read_text(encoding='utf-8')
    assert 'template <auto F> inline void end_rp_call(VkCommandBuffer c) { NBMT_ENDRP_HOOK(); F(c); }' in mt and 'pod<end_rp_call<NBMT_REAL(vkCmdEndRenderPass)>, OP_EndRenderPass>(c)' in mt, \
        'SAFE: the rec hook sits in the EndRenderPass call (packet or direct)'
    # crash handler: classify, never for a signal another process sent
    cr = code((root / 'host/crash.c').read_text(encoding='utf-8'))
    oc = cr[cr.find('static void on_crash(int sig, siginfo_t *si, void *uc_) {'):]
    assert oc.count('xbg_crash_classify(sig, tn, 0,') == 1 and 'if (xbg_crash_classify && g_ext_pid <= 0) {' in oc and oc.find('g_report_hook(0,') < oc.find('xbg_crash_classify(sig'), \
        'SAFE: crash.c classifies after the report marker, not for external signals'
    # JNI: the player's keys (environment at start + dm/env), the marker dir, the two natives
    st = jni[jni.find('JNIEXPORT jint JNICALL Java_com_xiaoboluo_d2r_DmActivity_nativeStart('):]
    assert 0 < st.find('player_keys_from_environ();') < st.find('setenv(') and 'setenv("DM_SAFE_DIR", g_files, 1);' in st, 'SAFE: the start environment snapshot before any setenv of ours'
    le = blk(jni, 'static void load_env_file(const char *dir) {')
    assert 'setenv(line, eq + 1, 1); player_key(line, strlen(line));' in le, "SAFE: every dm/env key is the player's"
    for n in ('nativeSafeModeStatus', 'nativeSafeModeEvent'):
        assert ('Java_com_xiaoboluo_d2r_DmActivity_%s(' % n) in jni, 'SAFE: JNI %s' % n
    # Java: the DOS2 activity opts in, the gear row, the guard service
    jv = root / 'android/app/src/main/java/com/xiaoboluo/d2r'
    act = (jv / 'DmActivity.java').read_text(encoding='utf-8')
    assert 'if (DOS2) { safe = new SafeMode(this); safe.atStart(getIntent()); }' in act and 'if (safe != null) safe.gameStarted(view);' in act and 'safe.firstFrames()' in act \
        and 'if (safe != null) safe.onResume();' in act and '@Override public SafeMode safeMode() { return safe; }' in act, 'SAFE: DmActivity opts in for DOS2'
    tg = (jv / 'Tl2Gear.java').read_text(encoding='utf-8')   # 19.11: the DOS2 list is its own method (Tl2Gear.dos2Sections)
    assert 'l.add(GearPages.safeMode(a));' in tg[tg.index('static List<GearSettings.Section> dos2Sections('):tg.index('static GearSettings.Section group(')], 'SAFE: the gear row'
    man = (root / 'android/app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
    assert 'android:name=".DmGuard"' in man and 'android:process=":guard"' in man and 'android.permission.POST_NOTIFICATIONS' in man, 'SAFE: the guard service + notification permission'
    txt = (jv / 'GearText.java').read_text(encoding='utf-8')
    assert 'version 0.5' not in txt and 'версии 0.5' not in txt, "SAFE: the shared texts do not name DOOM's version"
    print('PASS: SAFE: %d step switches (each read by the tree), boot before DM_NR_ROTATE / the device, engine init after the policy, fatal / crash / pipe '
          'recording, the player rule, step 3 undoes every app NB / NR default, Java opt-in + gear row + guard' % len(keys))

def nrheat_check():   # [DOS2] NR-HEAT DM_NR_HEAT (docs/dos2/nr/NR-HEAT.md): the always-on shader / pass heat logger
    def code(s): return re.sub(r"""/\*.*?\*/|//[^\n]*""", "", s, flags=re.S)
    jni = code((root / 'android/jni_android.c').read_text(encoding='utf-8'))
    assert '{"DM_NR_HEAT", "1"}' in jni, 'NR-HEAT: DOS2 default on (k_nb_on, dm/env 0 wins)'
    li = jni[jni.find('static void log_init(void)'):]; li = li[:li.find('\n}\n')]
    assert 'setenv("DM_LOG_DIR", dir, 1);' in li, 'NR-HEAT: log_init exports the logs folder (shader-heat.tsv beside boot.log)'
    core = (root / 'gfx/nr/nr_heat.c').read_text(encoding='utf-8') + (root / 'gfx/nr/nr_heat.h').read_text(encoding='utf-8')
    cc = code(core)
    assert set(re.findall(r'#include <(\w+)\.h>', core)) <= {'stddef', 'stdint', 'stdio', 'stdlib', 'string'} and 'getenv' not in cc and 'vk' not in cc.lower().replace('lspk', ''), 'NR-HEAT: nr_heat.{h,c} pure C'
    game = code((root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8'))
    assert game.count('#include "xbg_nr_heat.inc"') == 1 and game.find('#include "xbg_nr_heat.inc"') > game.find('Shader *load_shader_key(const std::string &key,const void *control,const void *code){'), 'NR-HEAT: the .inc after the Shader struct and load_shader_key'
    i = game.find('nrheat::init();')
    assert game.count('nrheat::init();') == 1 and i > game.find('getenv("DM_GFX_PASS_PROF")') and i > game.find('timestamp_bits=queues[cfg.queue_family].timestampValidBits;'), 'NR-HEAT: init after DM_GFX_PASS_PROF and the timestamp bits'
    rs = game[game.find('Slot &recording_slot(){'):]; rs = rs[:rs.find('\n}\n')]
    assert 'if((pass_prof_enabled || nrheat::mode>0) && timestamp_bits){' in rs and 'else if(!pass_prof_enabled && pass_prof_frame!=frame && nrheat::due(frame))' in rs, 'NR-HEAT: heat picks frames only when DM_GFX_PASS_PROF does not'
    assert 's.prof_log=pass_prof_log;' in rs, 'NR-HEAT: each profiled slot knows whether it logs GPASS lines'
    pd = game[game.find('void pass_prof_draw(VkCommandBuffer cmd){'):]; pd = pd[:pd.find('\n}\n')]
    a, b, c = pd.find('nrheat::draw('), pd.find('if(!s.prof_log)return;'), pd.find('std::string keys;')
    assert pd.startswith('void pass_prof_draw(VkCommandBuffer cmd){Slot &s=slots[slot_index];if(!s.prof || cmd!=s.cmd)return;') and 0 < a < b < c, 'NR-HEAT: off-sample draws return at the old first test; heat-only frames build no GPASS key text'
    rt = game[game.find('void retire_slot(Slot &s){'):]; rt = rt[:rt.find('\n}\n')]
    assert 'if(heat)nrheat::pass(r,us);' in rt and 'if(!s.prof_log){' in rt and 'if(s.prof_log)xbg_logf("NVN GPASS frame=%llu slot=%u ring=%u summary' in rt and 'if(heat)nrheat::end_slot(s,span_us);' in rt, 'NR-HEAT: retire hands the records over, GPASS lines only for DM_GFX_PASS_PROF frames'
    dr = game[game.find('void draw(int prim,int first,int count,'):]; dr = dr[:dr.find('\n}\n')]
    assert len(dr) > 20000 and 'nrheat' not in dr and 'pass_prof_log' not in dr, 'NR-HEAT: nothing in draw() itself (the NR-09 lane / draw identity stay untouched)'
    inc = code((root / 'gfx/vulkan/engine/xbg_nr_heat.inc').read_text(encoding='utf-8'))
    assert 'if(!mode)return;' in inc and inc.find('boot_ns=timing_clock();') < inc.find('if(!mode)return;') < inc.find('start();}'), 'NR-HEAT: no thread / file when DM_NR_HEAT=0'
    assert 'std::thread(writer).detach();' in inc and 'setpriority(PRIO_PROCESS,0,10);' in inc, 'NR-HEAT: one detached low-priority writer thread'
    fs = code((root / 'host/hle_fs.c').read_text(encoding='utf-8'))
    assert fs.count('dm_dos2_heat_open(path, hp, fd, (mode & (MODE_WRITE | MODE_APPEND)) != 0);') == 1 and fs.count('if (h < 4096 && g_dm_dos2_heat_fd[h]) dm_dos2_heat_read((int)h, off, sz);') == 1, 'NR-HEAT: one open hook, one read hook (a byte test when off)'
    hh = code((root / 'host/hle_dos2_heat.c').read_text(encoding='utf-8'))
    assert hh.lstrip().startswith('#ifdef DM_GAME_DOS2') and 'g_dm_dos2_heat_fd[fd] = (uint8_t)mine;' in hh, 'NR-HEAT: DOS2 only; every open sets or clears its slot'
    print('PASS: NR-HEAT: DOS2 default 1 (dm/env wins), DM_LOG_DIR exported; pure core; frames picked only without DM_GFX_PASS_PROF, no GPASS text on heat-only '
          'frames, the off-sample draw path unchanged; retire hands over; no thread without the switch; fs hooks one each, DOS2 only')

nr01_check()
def nr33b_check():   # NR-33B DM_NR_MAT (docs/dos2/nr/NR-33B.md): depth-only material fragment shaders, unread vertex outputs
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\.|[^"\\n])*"', '""', text)
    for name in ('nr_mat.h', 'nr_mat.c'):
        core = code((root / 'gfx/nr' / name).read_text(encoding='utf-8'))
        assert 'vulkan' not in core.lower() and 'getenv' not in core and 'pthread' not in core, 'NR-33B: %s stays engine / host free' % name
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_mat.inc').read_text(encoding='utf-8')
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_mat_default(XbgGpuFamily f){return xbg_tile_family(f)?1:0;}' in pol, 'NR-33B: 1 on the tile families (19.11), 0 on Adreno'
    pp = g.index('prepass::Guard ppg;if(prepass::mode && prepass::pre(')
    mg = g.index('nrmat::Guard nmg;if(nrmat::mode>0)nrmat::pre(nmg);')
    assert pp < mg < g.index('const int draw_fast=draw_fast_mode();if(!draw_fast)build_stages();'), 'NR-33B: the twin is chosen after the pre-pass check, before the stages / memo'
    assert g.rfind('#ifdef DM_GAME_DOS2', 0, mg) > g.rfind('#endif', 0, mg), 'NR-33B: the draw hook is DOS2 only'
    assert '!state.shader[4]->nm_is_twin && alpha_test_on()){VkShaderModule m=alpha_module(' in g, 'NR-33B: no alpha variant of the twin'
    assert 'vs_choose' not in g and 'dp_module' not in code(inc) and 'nr_mat_prune' not in code(inc) and 'nm_dp' not in g, 'NRVS: no second vertex trim (NR-32 vsout_module trims the twin pipelines)'
    assert 't->nm_is_twin=true;t->vo_read=0;t->vo_decl=0;' in inc, 'NRVS: the twin reads / declares no varying, so NR-32 drops every Location output'
    assert g.index('VkShaderModule m=vtx_retype_module(') < g.index('vsout_module(*state.shader[0],') < g.index('VkShaderModule m=alpha_module(*state.shader[4]'), 'NRVS: the twin vertex trim after the retype pick (composes with #vi)'
    lm = g.index('const int r=nrmat::warm_module(key,nm);')
    assert g.index('VkShaderModule load_module(const std::string &key){') < lm < g.index('const bool alpha=alpha_tag(key,cut,func,bits);'), 'NR-33B: warm-up builds #dz stages'
    assert "if(on()<=0 || key[c+2]=='p' || c+3!=key.size())return -1;" in inc, 'NRVS: #dp keys (the earlier prune) are not built'
    m9 = g.index('nr_xlq=e&&*e?atoi(e):xbg_nr_xlq_default(gpu_policy);')
    assert m9 < g.index('nrmat::on();   // [DOS2] NR-33B: DM_NR_MAT / DM_NR_MAT_VS read now') < g.index('shader_reuse=0;', m9), 'NRVS: DM_NR_MAT read at start-up (xlq_twin before any load / warm-up)'
    assert 'nrmat::note(*p,words,bytes.data()+bytes.size()-h.spirv_bytes,h.spirv_bytes);' in g, 'NR-33B: load_shader classifies (raw SPIR-V for the gate hash)'
    assert 'if(nrmat::mode>0)nrmat::tick();' in g and '#include "xbg_nr_mat.inc"' in g, 'NR-33B: summary tick and include'
    assert 'delete nm_twin;' in g, 'NR-33B: the Shader owns its twin'
    pre = inc[inc.index('void pre(Guard &g){'):inc.index('// warm-up: 1 = a module of ours')]
    for need in ('state.rt.color[i])return;', 'state.shader[1] || state.shader[2] || state.shader[3] || state.rast_discard', 'state.ms.a2c',
                 'nr_mat_gate_eval(', 'nr_mat_alpha_pass(', 'if(mode==2){++s.would;return;}', 'g.saved=fs;state.shader[4]=t;'):
        assert need in pre, 'NR-33B pre(): %s' % need
    assert pre.index('state.rt.color[i])return;') < pre.index('g.saved=fs;'), 'NR-33B: only without colour attachments'
    assert 'struct Guard{Shader *saved=nullptr;~Guard(){if(saved)state.shader[4]=saved;}};' in inc, 'NR-33B: the game shader comes back after the draw'
    assert 'for(auto &w:pending_writebacks)if(xbg_wb_overlaps(a,4,w.addr,w.bytes))return 0;' in inc, 'NR-33B: a gate word under a pending writeback is unreadable'
    su = (root.parent / 'tools/setup_dos2.py').read_text(encoding='utf-8')
    assert 'step_matpack(L); print(' in su and "'dos2_nr_mat.py'" in su, 'NR-33B: setup stage 8 builds the gate records'
    t = (root.parent / 'tools/dos2_nr_mat.py').read_text(encoding='utf-8')
    assert 'MAGIC, VERSION = 0x314d4758, 1' in t and "'dg.%s.xgs' % k" in t, 'NR-33B: record format / pack key = nr_mat.c / xbg_nr_mat.inc'
    assert '"dg."+p.key.substr(0,16)' in inc and '0x314d4758u' in (root / 'gfx/nr/nr_mat.c').read_text(encoding='utf-8'), 'NR-33B: the host reads dg.<key> XGM1'
    print('PASS NR-33B DM_NR_MAT wiring')


def nr33c_check():   # NR-33C DM_NR_SH_SURF (docs/dos2/nr/NR-33C.md): surface materials with a wave-coherent early out
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\.|[^"\\n])*"', '""', text)
    for name in ('nr_surf.h', 'nr_surf.c'):
        core = code((root / 'gfx/nr' / name).read_text(encoding='utf-8'))
        assert 'vulkan' not in core.lower() and 'getenv' not in core and 'pthread' not in core, 'NR-33C: %s stays engine / host free' % name
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_surf.inc').read_text(encoding='utf-8')
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert 'inline int xbg_nr_surf_default(XbgGpuFamily){return 0;}' in pol, 'NR-33C: default 0 on every family'
    mg = g.index('nrmat::Guard nmg;if(nrmat::mode>0)nrmat::pre(nmg);')
    sg = g.index('nrsurf::Guard nsg;if(nrsurf::mode>0)nrsurf::pre(nsg);')
    assert mg < sg < g.index('const int draw_fast=draw_fast_mode();if(!draw_fast)build_stages();'), 'NR-33C: the twin is chosen after NR-33B, before the stages / memo'
    assert g.rfind('#ifdef DM_GAME_DOS2', 0, sg) > g.rfind('#endif', 0, sg), 'NR-33C: the draw hook is DOS2 only'
    lm = g.index('const int r=nrsurf::warm_module(key,nm);')
    assert g.index('const int r=nrmat::warm_module(key,nm);') < lm < g.index('const bool alpha=alpha_tag(key,cut,func,bits);'), 'NR-33C: warm-up builds #s<v> stages'
    assert 'nrsurf::note(*p,bytes.data(),bytes.size(),bytes.data()+bytes.size()-h.spirv_bytes,h.spirv_bytes);' in g, 'NR-33C: load_shader notes (raw SPIR-V for the record hash)'
    assert 'if(nrsurf::mode>0)nrsurf::tick();' in g and '#include "xbg_nr_surf.inc"' in g, 'NR-33C: summary tick and include'
    assert 'for(Shader *t:ns_twin)if(t!=this)delete t;' in g, 'NR-33C: the Shader owns its twins'
    pre = inc[inc.index('void pre(Guard &g){'):inc.index('// warm-up:')]
    for need in ('fs->ns_is_twin || fs->nm_is_twin', 'alpha_test_on()){++s.alpha_test;return;}', 'xbg_2d_blend_from_nvn(', 'state.ds.dw',
                 'state.stencil_write[0]', 'state.ms.a2c', 'state.color.logic_op!=3', 'state.count_samples || nrocc::in_pair()',
                 'nr_surf_alpha_gate(', 'nr_surf_choose(', 'if(mode==NR_SURF_CHECK){++s.would;return;}', 'g.saved=fs;state.shader[4]=t;'):
        assert need in pre, 'NR-33C pre(): %s' % need
    assert 'struct Guard{Shader *saved=nullptr;~Guard(){if(saved)state.shader[4]=saved;}};' in inc, 'NR-33C: the game shader comes back after the draw'
    assert 'VK_SUBGROUP_FEATURE_VOTE_BIT' in inc and 'VK_SHADER_STAGE_FRAGMENT_BIT' in inc, 'NR-33C: off without subgroup vote in fragment shaders'
    w = inc[inc.index('bool words('):inc.index('Shader *twin(')]
    chain = 'gscull_rewrite(w,4,key.c_str(),"nr-surf");lone_rewrite(w,4,key.c_str(),"nr-surf");early_tests_rewrite(w,4,key.c_str());invariant_rewrite(w,4,key.c_str());gather_ext_rewrite(w,key.c_str());gather_snap_rewrite(w,4,key.c_str());quad_rewrite(w,4,key.c_str(),"nr-surf");warp_rewrite(w,4,key.c_str(),"nr-surf");tidy_rewrite(w,key.c_str());'
    bw = g[g.index('bool bundle_words(const std::string &key'):g.index('// [DOS2] "<shader>#at<func>')]
    assert chain in w and chain.replace('(w,', '(w,').replace('"nr-surf"', 'site').replace('w,4,', 'w,h.stage,') in bw, \
        'NR-33C: a twin gets the load-time rewrites of bundle_words, in the same order'
    assert 'if((i<24 || i>=28) && head[i]!=b[i])return false;' in w, 'NR-33C: the variant carries the translated head byte for byte'
    assert '"sr."+p.key.substr(0,16)' in inc and 'h!=r.spirv_fnv' in inc, 'NR-33C: the record names the translated SPIR-V (FNV)'
    su = (root.parent / 'tools/setup_dos2.py').read_text(encoding='utf-8')
    assert 'step_surfpack(L); print(' in su and "'dos2_nr_surf.py'" in su, 'NR-33C: setup stage 8 builds the variants'
    t = (root.parent / 'tools/dos2_nr_surf.py').read_text(encoding='utf-8')
    c = (root / 'gfx/nr/nr_surf.c').read_text(encoding='utf-8')
    assert "struct.pack('<4sQII', b'XSR1', fnv64(spv), flags, 0)" in t and 'if (n != 20) return' in c and 'memcmp(b, "XSR1", 4)' in c, 'NR-33C: record format = nr_surf.c'
    assert "files['sr.%s' % key]" in t and "files['%s.%s' % (v, key)]" in t and 'std::string(1,v)+"."+fs_key.substr(0,16)' in inc, 'NR-33C: pack keys <v>.<key> / sr.<key>'
    assert "for v in 'kamp'" in t or "'kamp')" in t, 'NR-33C: variant letters k a m p'
    print('PASS NR-33C DM_NR_SH_SURF wiring')


nr02_check()
nr22_check()
nr05_check()
nr06_check()
nr07_check()
nr08_check()
nr09_check()
nr16_check()
nr21_check()
nr12_check()
nr08b_check()
nr03_check()
nr04_check()
t11dref_check()
nr10_check()
nruix_check()
nr10b_check()
nr11_check()
# NR-CPU (docs/dos2/nr/NR-CPU.md): the CPU cuts and splits of the Fort Joy CPU bottleneck.
#   - DM_CPU_SELF (hle_cpu_place.c): the self check runs only on the thread itself (tid == gettid), from the two per-frame hooks
#     (dm_cpu_place_translator at every present, dm_cpu_place_self from nvnQueuePresentTexture in DOS2); mode 2 never sets; the
#     widening is reached only from mode 1 and only for a one-core translator mask; the 2 s checks use the same widened mask;
#   - NRCPU_SCOPE: timed only with DM_NR_CPU=1 (nrcpu_on, set in cpf::init); the optional kinds are printed only when timed;
#   - NR-08's Scope stays alive over the old path (its =2 compare runs in the destructor): only serve() is timed;
#   - NR-TAPSET: nb_read answers "held" from the set only at rs_mode 1, at 2 the scan decides; the set is invalidated by nb_frame_reset;
#     the front end reads DM_NR_TAPSET once and does not set it by default (jni_android.c does not name it);
#   - the NB-MT profile and the main-thread state split change nothing without DM_NR_CPU / a timed draw.
def nrtrx_check():
    # [DOS2] NR-TRX (docs/dos2/nr/NR-TRX.md): DM_NR_TRX_ZC / DM_NR_TRX_STICKY default 0, read once, the old code behind one branch
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    assert g.count('trx::zcm=num("DM_NR_TRX_ZC");trx::stm=num("DM_NR_TRX_STICKY");') == 1, 'NR-TRX: both switches read once in trx_init'
    a = g.index('void trx_init(){'); ti = g[a:g.index('\n', g.index('trx::stm==3?', a))]
    assert g.count('getenv("DM_NR_TRX_') == 2 and ti.count('getenv("DM_NR_TRX_') == 2, 'NR-TRX: DM_NR_TRX_STICKY=3 / DM_NR_TRX_STICKY_AGE read in trx_init only'
    assert 'int v=e && *e?atoi(e):0;return v<0 || v>2?0:v;' in g, 'NR-TRX: default 0, only 0 / 1 / 2'
    a = g.index('Chunk *holder(uint64_t address){'); h = g[a:g.index('\n}\n', a)]
    assert h.index('if(__builtin_expect(trx::zcm!=0,0))') < h.index('return holder_scan(address);'), 'NR-TRX: holder() = the scan unless DM_NR_TRX_ZC'
    a = g.index('Chunk *holder_ix(uint64_t address){'); hx = g[a:g.index('\n}\n', a)]
    assert 'if(trx::zcm==2){Chunk *s=holder_scan(address);' in hx and 'r=s;}' in hx, 'NR-TRX: at 2 the scan decides'
    assert g.count('++trx::ver;') == 2, 'NR-TRX: the index is rebuilt after map_pool installs and retire'
    a = g.index('bool trx_sticky_ok(Chunk &c,uint64_t off,uint64_t bytes){'); so = g[a:g.index('\n}\n', a)]
    assert 'if(trx::stm<=0 || (snap_site!=1 && snap_site!=2))return false;' in so, 'NR-TRX: only vertex / index views are refined'
    assert 'if(k!=NRT_CLS_NEVER && k!=NRT_CLS_STABLE)return false;' in so, 'NR-TRX: only classes NEVER / STABLE are served'
    assert so.index('nrt_sv_note(&trx::sv,slot_serial,') < so.index('if(trx::stm!=2){++trx::served;++trx::srv_n[k];return true;}return false;'), 'NR-TRX: a serve is noted before it is served; 2 never serves'
    a = g.index('void mark(uint64_t address,uint64_t bytes){'); mk = g[a:g.index('\n}\n', a)]
    assert mk.index('trx_guard(address,bytes);') < mk.index('int n=count.load('), 'NR-TRX: the guard runs before the write is marked (and before the caller writes)'
    a = g.index('void trx_guard(uint64_t address,uint64_t bytes){'); gd = g[a:g.index('\n}\n', a)]
    assert 'const bool act=trx::stm!=2;' in gd and 'if(act)gpu_sync(trx::g_syncs);' in gd and 'if(act){for(int i=0;i<slot_count;i++){Slot *o=oldest_pending();' in gd, 'NR-TRX: the guard waits at 1 / 3, counts at 2'
    assert 'uint64_t trx_floor(){int p=0;for(int i=0;i<slot_count;i++)if(slots[i].pending)++p;' in g, 'NR-TRX: the floor = the oldest pending slot'
    for site in ('zc::mark(a[1],a[2]);invalidate_cpu_range(a[1],a[2]);memmove(', 'zc::mark(a[0],a[1]);invalidate_cpu_range(a[0],a[1]);memcpy(', 'zc::mark(a.addr,bytes);invalidate_cpu_range(a.addr,bytes);uint32_t *d=', 'zc::mark(addr,16);invalidate_cpu_range(addr,16);memset('):
        assert g.count(site) == 1, 'NR-TRX: every replay CPU write is marked (guarded) before it lands: ' + site
    assert g.count('zc::mark(') == 4, 'NR-TRX: a new replay CPU write site -> mark (guard) it before the write'
    a = g.index('bool view(uint64_t address,uint64_t bytes,VkDeviceSize align,Buffer &out){'); v = g[a:g.index('\n}\n', a)]
    assert 'if(__builtin_expect(trx::stm!=0,0) && trx_sticky_ok(*c,off,bytes))break;' in v and '++sticky_misses;return false;}' in v, 'NR-TRX: view() keeps the sticky miss otherwise'
    assert 'if(__builtin_expect(trx::stm!=0,0)){if(trx::stm<0)trx_init();if(trx::stm>=2)trx_base_note(*c,off,bytes);}' in v, 'NR-TRX: base-path views noted only at 2 / 3'
    t = (root / 'gfx/nr/nr_trx.h').read_text(encoding='utf-8')
    assert '#include <vulkan' not in t and '#include "../vulkan' not in t and 'Vk' not in t, 'NR-TRX: nr_trx.h is pure C'
    j = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    assert '{"DM_NR_TRX_STICKY", "1"}' in j and '{"DM_NR_TRX_ZC", "1"}' in j, 'NR-TRX: the app sets DM_NR_TRX_STICKY=1 and DM_NR_TRX_ZC=1 (batch C, owner 19.11)'

def nrcpu_check():
    c = (root / 'host/hle_cpu_place.c').read_text(encoding='utf-8')
    a = c.index('static void self_check(int r, int tid) {'); body = c[a:c.index('\n}\n', a)]
    assert 'tid != (int)gettid()) return;' in body.splitlines()[2], 'NR-CPU: the self check runs only on the thread itself'
    assert body.index('if (g_self_mode != 1) return;') < body.index('aff_set(0, want)'), 'NR-CPU: DM_CPU_SELF=2 never sets a mask'
    assert body.index('if (g_self_mode != 1) return;') < body.index('atomic_store(&g_xwide, strong)') and '!(want & (want - 1))' in body, 'NR-CPU: widening only in mode 1, one-core masks only'
    assert c.count('self_check(0, tid); }') == 1 and c.count('self_check(1, (int)gettid())') == 1, 'NR-CPU: two self-check entries'
    assert 'r == R_TRANSLATE ? xlate_mask(p)' in c, 'NR-CPU: the 2 s checks use the widened translator mask'
    n = (root / 'gfx/nvn/hle_nvn.c').read_text(encoding='utf-8')
    a = n.index('NVN(nvnQueuePresentTexture, void, NVNqueue *q, NVNwindow *w, int idx) {')
    assert 'if (dm_cpu_place_self) dm_cpu_place_self(); }' in n[a:a + 900] and n.count('dm_cpu_place_self()') == 1, 'NR-CPU: the main thread checks itself at its present, DOS2 only'
    j = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    assert 'DM_CPU_SELF' not in j and '{"DM_NR_TAPSET", "1"}' in j, 'NR-CPU: the app does not set DM_CPU_SELF (code default 1); DM_NR_TAPSET=1 by the app (batch C, owner 19.11)'
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    assert g.count('#define NRCPU_SCOPE(kind) XbgCpuTiming::Scope nrcpu_scope(__builtin_expect(nrcpu_on,0)?timing_now():nullptr,XbgCpuTiming::kind)') == 1, 'NR-CPU: NRCPU_SCOPE only with DM_NR_CPU=1'
    assert g.count('if(int(i)>=XbgCpuTiming::FirstOptional && !calls)continue;') == 1, 'NR-CPU: the optional parts are printed only when timed'
    assert g.count('NRCPU_SCOPE(') == 2 and 'NRCPU_SCOPE(NbState)' in (root / 'gfx/vulkan/engine/xbg_nb_state.inc').read_text(encoding='utf-8') and 'NRCPU_SCOPE(NbDraw)' in (root / 'gfx/vulkan/engine/xbg_nb.inc').read_text(encoding='utf-8') and 'nrdesc::Scope nrs(ok,compute,out,commands);if(nrs.served)return;' in g, 'NR-CPU: scopes (MtEnd + macro in xbg_game.cpp, NbState / NbDraw in their exec), NR-08 Scope untouched'
    pc = (root / 'gfx/vulkan/engine/xbg_cpuprof.inc').read_text(encoding='utf-8')
    assert 'nrcpu_on = on;' in pc, 'NR-CPU: DM_NR_CPU sets nrcpu_on'
    d = (root / 'gfx/vulkan/engine/xbg_nr_desc.inc').read_text(encoding='utf-8')
    assert 'if(mode==1){{NRCPU_SCOPE(NrDesc);served=serve(o,c);}' in d, 'NR-CPU: only serve() is timed inside the NR-08 Scope'
    t = (root / 'gfx/vulkan/engine/xbg_cpu_timing.h').read_text(encoding='utf-8')
    assert t.index('Snapshot,') < t.index('NbState, NbDraw, NrDesc, NrLane, MtEnd, NrZ3, Count };'), 'NR-CPU: the new kinds after the old ones (NrZ3: NR-ZERO Z3, last)'
    pl = (root / 'gfx/nb/nb_plan.c').read_text(encoding='utf-8')
    a = pl.index('int nb_read(nb_frame *f, int pass, uint64_t image) {'); rb = pl[a:pl.index('\n}\n', a)]
    assert rb.index('if (f->rs_mode == 2) {') < rb.index('held = scan;') < rb.index('if (held) { f->rs_hits++; return 0; }'), 'NR-TAPSET: at 2 the scan decides'
    assert 'f->rs_node = -1;' in pl[pl.index('void nb_frame_reset('):pl.index('static nb_node *new_node(')], 'NR-TAPSET: a reset part invalidates the set'
    hb = (root / 'host/hle_dos2_nb.c').read_text(encoding='utf-8')
    assert hb.count('getenv("DM_NR_TAPSET")') == 1, 'NR-TAPSET: read once'
    m = (root / 'gfx/nb/nb_mt.h').read_text(encoding='utf-8')
    assert 'if (__builtin_expect(prof_on, 0)) {' in m and '} else p->run(c->cb, p);' in m, 'NR-CPU: the NB-MT profile is one branch a packet when off'
    print('PASS: NR-CPU: DM_CPU_SELF on the thread itself (mode 2 counts only, widening one-core translator masks from mode 1), NRCPU_SCOPE only with DM_NR_CPU, NR-08 Scope kept, NR-TAPSET =2 scan decides, reset invalidates, app sets neither switch')

# NR-SHCACHE (shadow cascade layers, DM_NR_SHCACHE, default 0; docs/dos2/nr/NR-SHCACHE.md): "off" stays byte-identical.
#   - xbg_nr_shc.inc included once, after xbg_nr_occ.inc and before draw(); every hook in xbg_game.cpp sits behind nrshc::live (false
#     unless a range is open, which needs mode > 0) or nrshc::mode (> 0, or != 0 only at the FRAME record that reads the switch once);
#   - the draw() hook is the first statement of draw() (the ordinals of execution 2 count every draw() call), skips only when it says so
#     and then does what a skipped draw does elsewhere (nbchk::draw), never inside the post fusion's nested draw;
#   - the PASS_END hook runs before nbchk::pass_end (execution 2 runs inside the still open IR pass); execution 2 stops at the record's pc;
#   - the core dm/gfx/nr/nr_shc.h is engine-free (no Vulkan, no getenv, no `state`); the policy default is 0 on every family.
def nrshc_check():
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_shc.inc').read_text(encoding='utf-8')
    core = (root / 'gfx/nr/nr_shc.h').read_text(encoding='utf-8')
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    assert g.count('#include "xbg_nr_shc.inc"') == 1 and g.index('#include "xbg_nr_occ.inc"') < g.index('#include "xbg_nr_shc.inc"') < g.index('void draw(int prim,int first,int count,const p_draw_idx *indexed'), 'NR-SHCACHE: include once, after NR-03, before draw()'
    d = g.index('void draw(int prim,int first,int count,const p_draw_idx *indexed')
    first = g[d:].split('\n')[1]
    if 'nrhack::far_draw()' in first: first = g[d:].split(chr(10))[2]   # N6 DM_HACK_SHFAR comes first: a far-cascade draw it drops must never reach the cache
    assert first.strip().startswith('if(__builtin_expect(nrshc::live,0) && !nbpost::inside && nrshc::draw(') and '{if(nbchk::armed)nbchk::draw();return;}' in first, 'NR-SHCACHE: the draw() hook is its first statement'
    for line in g.split('\n'):
        if 'nrshc::' in line and '#include' not in line:
            assert re.search(r'nrshc::live|nrshc::mode\s*>\s*0|nrshc::mode\s*!=\s*0', line), 'NR-SHCACHE: hook not gated: ' + line.strip()[:160]
    hooks = ['nrshc::op(h.op,p,n)', 'nrshc::op_end(depth)', 'nrshc::clear_ds(a)', 'nrshc::frame(payload<p_nb_frame>(p,n))', 'nrshc::pass(payload<p_nb_pass>(p,n),pc,pc+h.size,depth,budget)', 'nrshc::pass_end(&e,pc,depth,budget)']
    for h in hooks: assert g.count(h) == 1, 'NR-SHCACHE: hook ' + h
    pe = g.index('nrshc::pass_end(&e,pc,depth,budget)'); assert pe < g.index('nbchk::pass_end(e)', pe), 'NR-SHCACHE: before nbchk::pass_end'
    assert 'if(__builtin_expect(nrshc::mode!=0,0))nrshc::frame(' in g and 'void frame(const p_nb_frame &f){if(mode==-1)init();if(mode==-3){release();mode=0;}if(mode<=0)return;' in inc, 'NR-SHCACHE: the switch is read once at a FRAME'
    assert 'again=how;ord=0;nbord::stop=stop;execute(R.start,R.depth,budget);nbord::stop=nullptr;' in inc, 'NR-SHCACHE: execution 2 = the range from its start, stopped at the end record'
    # [shc3] execution 2 opens the draw() hook (gated by live, which pass_end cleared: the phone's "execution 2 met 0 draws, execution 1 had 206"),
    # the uniform memo starts a new generation, the range's OP_UPDATE_UB are undone before it; the switch goes off through switch_off() (-3: the
    # FRAME hook frees the images once at the slot's retire), never by a bare mode = 0 inside a range
    ar = inc[inc.index('void again_run(int how'):inc.index('// ---- the hash of a draw')]
    assert 'undo_apply();put(R.snap,R.snap_missing);++memo_gen;' in ar and 'live=true;again=how;ord=0;nbord::stop=stop;execute(R.start,R.depth,budget);nbord::stop=nullptr;again=NRSHC_R_NONE;live=false;' in ar, 'NR-SHCACHE shc3: execution 2 sees its draws, updates undone, memo new'
    assert 'if(o==OP_UPDATE_UB){++memo_gen;if(!again && !R.refused)upd(p,n);return;}' in inc and 'nrshc_undo_note(ud,a[0],cur,uint32_t(a[1]))' in inc, 'NR-SHCACHE shc3: the old bytes of an update are noted before the record writes them'
    assert 'const bool simple=depth==R.depth && ends==R.ends0 && !ud->over;' in inc, 'NR-SHCACHE shc3: a full update log is not executable again'
    assert re.search(r'(?<![=!<>])mode=0;', inc.replace('if(mode==-3){release();mode=0;}', '').replace('mode=m;', '')) is None, 'NR-SHCACHE shc3: the switch goes off through switch_off()'
    assert 'if(R.refused || (mode<=0 && !again))return false;' in inc, 'NR-SHCACHE shc3: execution 2 counts its draws to the end'
    assert 'put(R.snap,R.snap_missing);' in inc and 'put(*end,end_missing);' in inc and 'nbpipe::reset();' in inc, 'NR-SHCACHE: the start state put back as NB-17 does, the end state after'
    assert 'if(act==NRSHC_A_HIT && (mode==NRSHC_ON) && A.S)copy_tile(*A.S,a,R.rect);' in inc, 'NR-SHCACHE: only mode 1 copies the layer (3 = poison)'
    assert 'return mode!=NRSHC_CHECK && skip;' in inc, 'NR-SHCACHE: check mode never skips'
    assert 'inline int xbg_nr_shcache_default(XbgGpuFamily f){return f==XBG_GPU_ADRENO?1:0;}' in pol, 'NR-SHCACHE: default 1 on Adreno only (owner 18.11)'
    c = re.sub(r'//[^\n]*', ' ', core)
    assert 'vulkan' not in c.lower() and 'getenv' not in c and not re.search(r'\bstate\b', c), 'NR-SHCACHE: nr_shc.h engine-free'
    # [shc2] the phone fix: the target's shape goes through nrshc_shape_why with BOUND colours counted (DOS2's SetRenderTargets(1, {NULL}, atlas)),
    # never `rt.n == 0`; an op of a refused range is no taint; every refusal / taint is counted by reason and printed in the "why" line
    a = inc[inc.index('void arm(){'):inc.index('void diag_draw(')]
    assert 'state.rt.n==0' not in inc and 'for(int i=0;i<state.rt.n && i<8;i++)if(state.rt.color[i])++sh.colours;' in a and 'const int rf=nrshc_shape_why(&sh);' in a         and 'if(rf!=NRSHC_RF_OK){R.refused=true;++s.refused;++s.rf[rf];ref_note(ap,R.pdraws);return;}' in a, 'NR-SHCACHE shc2: the shape test counts bound colours, refusals by reason'
    o = inc[inc.index('void op(uint32_t o,const uint8_t *p,size_t n){'):inc.index('void op_end(')]
    assert 'if(R.armed && rg->live){rg->tainted=1;++s.tainted;++s.top[o&127];}' in o and 'else ++s.ignored;' in o and 'case OP_BARRIER:return;' in o, 'NR-SHCACHE shc2: op classes'
    assert 'const int skip=nrshc_draw(cas[R.k],&par,rg,h,hs,hn,nrshc_vtag(V.j,V.p,V.t),v,tw==NRSHC_T_OK);' in inc and 'hs=h;return nrshc_mix(h,hu);}' in inc, 'NR-SHCACHE shc2: taint reason and structure hash'
    # [shc4] content versions (the phone's verify differ, 18.11): every byte range the backend writes into guest memory goes to the journal (first
    # statement of snapshot_invalidate), every pool that comes / goes too; each image upload / partial re-upload takes a new upload number; the
    # hash of execution 1 versions vertex streams, the index range, texel buffers and images (get_image first: the check the draw's own descriptors
    # would make), execution 2 takes execution 1's version per ordinal
    si = g[g.index('void snapshot_invalidate(uint64_t address,uint64_t bytes){'):]
    assert si.split(chr(10))[1].strip().startswith('if(__builtin_expect(nrshc::mode>0,0))nrshc::wrote(address,bytes);'), 'NR-SHCACHE shc4: the journal hook is the first statement of snapshot_invalidate'
    assert g.count('nrshc::pool_event(') == 2 and 'if(__builtin_expect(nrshc::mode>0,0))nrshc::pool_event(uint64_t(uintptr_t(p)),n);' in g and 'if(__builtin_expect(nrshc::mode>0,0))nrshc::pool_event(uint64_t(uintptr_t(p)),pit->second);' in g, 'NR-SHCACHE shc4: pool add / del versioned'
    assert 'im.uploaded=true;provenance_write(im,__LINE__);im.nrshc_up=++nrshc_up_seq;' in g and 'partial_upload(im,t,im.dirty_stamp,stamp)){im.dirty_stamp=stamp;im.nrshc_up=++nrshc_up_seq;}' in g, 'NR-SHCACHE shc4: uploads take a new upload number'
    tv = inc[inc.index('void texver(uint64_t hd,uint32_t type,Ver &V){'):inc.index('// [shc4] wv: execution 1')]
    assert tv.index('Image &im=get_image(&t,true);') < tv.index('im.nrshc_up') and 'if(im.gpu_written){V.salt=true;' in tv, 'NR-SHCACHE shc4: an image is checked before its upload number is read; GPU-written = no member'
    assert re.search(r'if\(wv && !\(vseen>>k&1\)\)\{vseen\|=1u<<k;(const uint64_t q0=tsplit\?timing_clock\(\):0;)?rv\(state\.vb\[k\]\.address,state\.vb\[k\]\.size,V\);', inc) and 'rv(ix->ibuf,uint64_t(uint32_t(count))<<ix->itype,V);' in inc and 'if(wv)texver(t,b.type,V);' in inc, 'NR-SHCACHE shc4: vertex streams, index range and textures versioned'
    assert 'uint64_t v;if(again)v=nrshc_again_v(rg,ord);else{' in inc and 'const uint64_t hn=hash(prim,first,count,ix,inst,first_inst,gi,tw,hs,!again,V);' in inc, 'NR-SHCACHE shc4: execution 2 reuses the version of execution 1'
    assert 'if(m.cls==1){++s.v_nocpu;return;}' in inc and 'if(nvn_dirty_version(p,size_t(n),&g,&inc)){' in inc and re.search(r'int nvn_dirty_version\(const void \*addr, size_t len, uint64_t \*gen, uint64_t \*inc\)', (root / 'gfx/nvn/nvn_dirty.c').read_text(encoding='utf-8')), 'NR-SHCACHE shc4: CPU-writable pools versioned by the tracker'
    assert 'if(!one){if(A.key && h.draws){for(unsigned i=0;i<h.natt && i<NB_REC_ATT;i++)if(h.att[i]==A.key){dirty=true;++s.outside;break;}}return;}' in inc, 'NR-SHCACHE shc4: an atlas pass outside a range dirties the frame'
    assert 'xbg_logf("[nr] shcache why (last 10 s): %s",t.b);' in inc and 'why_line(fr);' in inc, 'NR-SHCACHE shc2: the reasons line'
    assert re.search(r'static inline int nrshc_shape_why\(const nrshc_shape \*s\)', core) and 'if (s->colours) return NRSHC_RF_COLOUR;' in core, 'NR-SHCACHE shc2: nrshc_shape_why'
    print('PASS: NR-SHCACHE: hooks gated (live / mode), draw() hook first, PASS_END before nbchk, execution 2 from the kept start state, check never skips, default 0, core engine-free; shc2: shape by bound colours, reasons counted; shc3: execution 2 hashed, updates undone, switch_off; shc4: content versions (journal, tracker, uploads), execution 2 reuses them, atlas passes outside a range')

def nrubd_check():   # NR-UBD DM_NR_UBD (docs/dos2/nr/NR-UBD.md): a repeated uniform-buffer range of a served direct draw is not sent
    def code(text):
        text = re.sub(r'/\*.*?\*/|//[^\n]*', ' ', text, flags=re.S)
        return re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    def body(text, head):
        i = text.index(head); i = text.index('{', i); depth, j = 0, i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if not depth: return text[i:j + 1]
            j += 1
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    h = rd('gfx/nr/nr_ubd.h')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint', 'string'] and 'LOG(' not in h and '#include "' not in h, 'NR-UBD: nr_ubd.h is pure C'
    assert 'static inline int nrub_filter(int same, int adopt, int scope, int n) { return same && adopt && scope && n == 1; }' in h, 'NR-UBD: the filter rule'
    nb = body(h, 'static inline int nrub_bind(')
    assert 'n == 1 && *at == m->epoch && *va == a[0] && *vn == sz[0]' in nb and nb.index('else if (m->owner != me) { nrub_forget(m);') < nb.index('for (int i = 0; i < n; i++)'), \
        'NR-UBD: the same range = address and size of this recording; another thread forgets'
    n = code(rd('gfx/nvn/hle_nvn.c'))
    ub = body(n, 'NVN(nvnCommandBufferBindUniformBuffer, ')
    o = [ub.index(x) for x in ('NUB(c, st, i, a, n);', 'const int nrub_same = NRUB_BIND1(c, st, i, a, n);', 'if (nrub_same == 2) return;', 'NBT(nbt_note(c, NBN_UBO));',
                               'if (NBD_TAKE(c) && nbd_take_bind(c, NBD_B_UBO, st, i, a, n)) { NRUB_FLAG(nrub_same); return; }', '*REC(c, OP_BIND_UBO, p_bind_buf)')]
    assert o == sorted(o) and n.count('NRUB_BIND1(') == 1 and n.count('NRUB_FLAG(') == 1, \
        'NR-UBD: BindUniformBuffer: NR-09U capture first, a bind that is not sent returns before anything is recorded, the =2 flag only once it sits in the shadow'
    ubs = body(n, 'NVN(nvnCommandBufferBindUniformBuffers, ')
    assert ubs.lstrip('{ \n').startswith('NRUB_BINDS(c, st, first, n, rg);') and n.count('NRUB_BINDS(') == 1, 'NR-UBD: plural binds are learned first, never left out'
    assert n.count('NRUB_BEGIN(') == 1 and 'NRUB_BEGIN(o);' in body(n, 'NVN(nvnCommandBufferBeginRecording,') and n.count('NRUB_NESTED(') == 2 and \
        'NRUB_NESTED(CB(c));' in body(n, 'NVN(nvnCommandBufferCopyCommands,') and 'NRUB_NESTED(CB(c));' in body(n, 'NVN(nvnCommandBufferCallCommands,'), \
        'NR-UBD: the mirror is reset at BeginRecording and forgotten at CopyCommands / CallCommands'
    inc = rd('gfx/nvn/nvn_nr_direct.inc')
    for name in ('NRUB_BIND1', 'NRUB_BINDS', 'NRUB_BEGIN', 'NRUB_NESTED'):
        m = re.search(r'#define %s\([^)]*\) ([^\n]*)' % name, inc)
        assert m and '__builtin_expect(g_nrub, 0)' in m.group(1), 'NR-UBD: %s is guarded by g_nrub' % name
    hk = body(code(inc), 'const uint64_t *sz, int filt) {')
    assert 'adopt = in && !t_nbd_chk && !t_nd.mode;' in hk and 'if (!nrub_filter(same, adopt, t_nrub_scope, n)) return 0;' in hk and \
        hk.index('if (!filt || !t_nrub_scope) return 0;') < hk.index('nrub_filter(') < hk.index('if (g_nrub == 1)') < hk.index('return 2;'), \
        'NR-UBD: a bind stays unsent only by nrub_filter, single, inside a served direct draw\'s bracket, with =1'
    ext = body(code(inc), 'static inline uint32_t nrd_ext_take(void) {')
    assert 'if (g_nrd_texf == 2 || t_nrd_wf) { x = nrd_x_chk(x, t_nrd_wf); t_nrd_nf = 0; }' in ext, 'NR-UBD: its =2 flags ride in the NR-09R tail word (texture flags only with TEXF=2 as before)'
    fr = code(rd('host/hle_dos2_nr_direct.inc'))
    tk = body(fr, 'static int nrd_draw_take(')
    o = [tk.index(x) for x in ('if (!nvn_nrd_can(d.cb))', 'if (g_nrd_ubd) nvn_nrub_scope(1);', 'g_nrd_ubo_fill(r);', 'nvn_on_bigstack(nrd_job, &j);', 'if (g_nrd_ubd) nvn_nrub_scope(0);', 'return 1;')]
    assert o == sorted(o) and tk.count('nvn_nrub_scope(') == 2, 'NR-UBD: the scope of a served direct draw: after the decision, around its uniform blocks and its job'
    ins = body(fr, 'static void nrub_install(int direct, int parts) {')
    assert 'if (direct != 1 || !(parts & NRDP_DRAW))' in ins and '"DM_NB_ORDER", "DM_NB_RELOC", "DM_NB_MX"' in rd('host/hle_dos2_nr_direct.inc') and \
        ins.index('nvn_nrub_enable(v);') < ins.index('g_nrd_ubd = v;'), 'NR-UBD: needs served direct draws and in-order execution; armed last'
    host = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (root / 'host').iterdir() if p.suffix in ('.c', '.h', '.inc'))
    jni = rd('android/jni_android.c')
    assert host.count('getenv("DM_NR_UBD")') == 1 and rd('gfx/vulkan/engine/xbg_nr_direct.inc').count('getenv("DM_NR_UBD")') == 1 and '{"DM_NR_UBD", "1"}' in jni, \
        'NR-UBD: DM_NR_UBD read once per side, not set by the app (default 0)'
    nr = rd('host/hle_dos2_nr.c')
    assert nr.index('nru_install(g_nrd, g_nrd_parts);') < nr.index('nrub_install(g_nrd, g_nrd_parts);'), 'NR-UBD: installed after NR-09R / NR-09U'
    be = code(rd('gfx/vulkan/engine/xbg_nr_direct.inc'))
    pre = body(be, 'void pre(')
    assert 'if(e.kind==NBD_B_UBO)' in pre and 'state.ub[e.stage][e.slot]' in pre and not re.search(r'state\.\w+(?:\[[^\]]*\])*(?:\.\w+)?\s*=[^=]', pre), \
        'NR-UBD: the backend compares a flagged uniform bind with state.ub (after the earlier binds of the record) and only reads'
    ubo = code(rd('gfx/nr/nr_ubo.h'))
    rb = body(ubo, 'static inline void nru_rebuild(')
    sc = body(ubo, 'const uint8_t *B, const uint8_t *D) {')
    assert rb.index('nru_same_count(s, B, D);') < rb.index('nru_wlock(') and 'if (__builtin_expect(s->same_on, 0) && !s->sim)' in rb and \
        not re.search(r'nru_w(64|32)\(|memcpy\(|__atomic|\bB\[[^\]]*\]\s*=[^=]', sc), 'NR-UBD: the NR-09U count only reads, before the rebuild\'s stores, only when asked'
    assert (root / 'gfx/vulkan/engine/tests/nr_ubd_test.c').is_file(), 'NR-UBD: the host test exists'
    print('PASS: NR-UBD: nr_ubd.h pure C, BindUniformBuffer leaves out only by nrub_filter (=1, single, in a served direct draw\'s bracket) before anything is recorded, '
          'plural binds learned, reset / forget at Begin / nested, the =2 flags in the NR-09R tail word, the scope around the served draw, DM_NR_UBD default 0 read once per side, '
          'the backend only reads, the NR-09U count only reads')

def nrzero_check():   # [DOS2] NR-ZERO DM_NR_SHC_MEMO (docs/dos2/nr/NR-ZERO.md section 4): exact memos of the shadow-cache draw hash's lookups
    inc = (root / 'gfx/vulkan/engine/xbg_nr_shc.inc').read_text(encoding='utf-8')
    core = (root / 'gfx/nr/nr_shc.h').read_text(encoding='utf-8')
    dc = (root / 'gfx/nvn/nvn_dirty.c').read_text(encoding='utf-8')
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    # 0 = today's lookups: tfind / cur_tmap / rv take the old path first thing when zmode is 0
    assert 'if(!zmode){auto f=tt->find(id);return f==tt->end()?nullptr:&f->second;}' in inc, 'NR-ZERO: tfind at 0 is the map lookup'
    assert 'if(zmode && nvn_dirty_version_tok && nvn_dirty_tok_ok){' in inc and 'else if(nvn_dirty_version(p,size_t(n),&g,&inc)){V.p=nrshc_mix(nrshc_mix(V.p,g),inc);++s.v_cpu_ok;return;}' in inc, 'NR-ZERO: rv at 0 is today\'s tracker call'
    assert 'if(zmode){const PoolKey k=pool_key(&state.texture_pool);' in inc and inc.count('auto f=textures.find(pool_key(&state.texture_pool));return f==textures.end()?&legacy_textures:&f->second;}') == 1, 'NR-ZERO: cur_tmap at 0 unchanged'
    # the memos store only found answers, under images_epoch; =2 decides with the old answer
    assert 'else nrshc_pm_put(pm,tt,int32_t(id),images_epoch,r);' in inc and 'if (!node) return;   // only found answers' in core, 'NR-ZERO: only found nodes stored'
    assert 'const int fresh=nvn_dirty_version(p,size_t(n),&g,&inc);' in inc and 'if(fresh){V.p=nrshc_mix(nrshc_mix(V.p,g),inc);++s.v_cpu_ok;return;}' in inc, 'NR-ZERO: =2 hashes with today\'s tracker answer'
    assert 'the token gave up (an epoch moved under its scan): today\'s answer, no memo' in inc, 'NR-ZERO: =1 falls back to today\'s scan when the token scan gives up'
    # the tracker: the slot epoch bumps before a page can be written, at add and at remove; the token's epoch is read before the pages
    ur = dc[dc.index('static int unprotect_run(range_t *r, uintptr_t a, uintptr_t b) {'):]
    assert ur.index('atomic_fetch_add(&r->ep, 1);') < ur.index('int err = mp(r->base'), 'NR-ZERO: unprotect_run bumps ep before mprotect'
    ad = dc[dc.index('void nvn_dirty_add_range('):dc.index('void nvn_dirty_remove_range(')]
    assert ad.index('atomic_fetch_add(&r->ep, 1);') < ad.index('atomic_store_explicit(&r->live, 1, memory_order_release);'), 'NR-ZERO: add bumps ep before live'
    rm = dc[dc.index('void nvn_dirty_remove_range('):dc.index('int nvn_dirty_tracked(')]
    assert rm.index('atomic_fetch_add(&r->ep, 1);') < rm.index('atomic_store_explicit(&r->live, 0'), 'NR-ZERO: remove bumps ep'
    vt = dc[dc.index('int nvn_dirty_version_tok('):dc.index('int nvn_dirty_tok_ok(')]
    assert vt.index('const uint64_t ep = atomic_load(&r->ep);') < vt.index('for (uintptr_t i = p; i <= q; i++)') and 'atomic_load(&r->ep) != ep) return 0;' in vt, 'NR-ZERO: the token epoch is read before the pages and checked after'
    assert dc.count('atomic_fetch_add(&r->ep, 1)') == 3, 'NR-ZERO: ep bumped in exactly unprotect_run, add, remove'
    assert '__attribute__((weak)) int nvn_dirty_version_tok(' in g and '__attribute__((weak)) int nvn_dirty_tok_ok(uint64_t tok);' in g, 'NR-ZERO: weak like the rest of the tracker'
    # the switch: read with the shadow cache's, default 0, not set by the app
    assert 'const char *z=getenv("DM_NR_SHC_MEMO");int zm=z && *z?atoi(z):xbg_nr_shc_memo_default();' in inc and 'inline int xbg_nr_shc_memo_default(){return 1;}' in (root/'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8'), 'NR-ZERO: DM_NR_SHC_MEMO default 1 (19.11, Z_1b bad 0)'
    jni = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    assert 'DM_NR_SHC_MEMO' not in jni, 'NR-ZERO: the app does not set DM_NR_SHC_MEMO'
    # the split timing: 1 in 128 draws, its total kept apart from the old "hash us a draw"
    assert 'tsplit=timed && (s.hashed>>6&1);' in inc and 'if(tsplit){s.sp_all+=dt;++s.sp_n;tsplit=false;}else{s.hash_ns+=dt;++s.hash_timed;}' in inc, 'NR-ZERO: split draws apart'
    assert 'xbg_logf("[nr] shcache memo (DM_NR_SHC_MEMO=%d, NR-ZERO, last 10 s):' in inc, 'NR-ZERO: the 10 s line'
    # [NR-ZERO] the translator's two per-draw stages timed by part on 1 in 128 timed draws, apart from their old "ns a served draw" averages
    nd = (root / 'gfx/vulkan/engine/xbg_nr_desc.inc').read_text(encoding='utf-8')
    nl = (root / 'gfx/vulkan/engine/xbg_nr_draw.inc').read_text(encoding='utf-8')
    assert 'const bool sp=timed && (calls>>6&1);' in nd and 'if(sp){++s.sp_n;' in nd and '}else{s.ns+=te-t0;++s.timed;}}' in nd and '"[nr] desc by part (NR-ZERO,' in nd, 'NR-ZERO: NR-08 serve by part'
    assert 'tm.sp=tm.timed && (calls>>6&1);' in nl and 'if(sp){++S->sp_n;' in nl and '}else{S->ns+=te-t0;++S->timed;}}' in nl and '"[nr] draw by part (NR-ZERO,' in nl, 'NR-ZERO: NR-09 lane by part'
    print('PASS: NR-ZERO DM_NR_SHC_MEMO: 0 = old lookups, found nodes only, =2 decides with the old answers, tracker epoch bumped before mprotect / at add / remove and read before the pages, weak, default 0 (app does not set it), split timing apart')
def nrz3_check():   # [DOS2] NR-ZERO Z3 DM_NR_Z3 / Z5 DM_NR_Z5 (docs/dos2/nr/NR-ZERO.md sections 9 / 10): a resolved engine draw from a table
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    z = (root / 'gfx/vulkan/engine/xbg_nr_z3.inc').read_text(encoding='utf-8')
    h = (root / 'gfx/nr/nr_z3.h').read_text(encoding='utf-8')
    lane = (root / 'gfx/vulkan/engine/xbg_nr_draw.inc').read_text(encoding='utf-8')
    nd = (root / 'gfx/vulkan/engine/xbg_nr_desc.inc').read_text(encoding='utf-8')
    ua = (root / 'gfx/vulkan/engine/xbg_nb_uiarea.inc').read_text(encoding='utf-8')
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    sm = (root / 'gfx/vulkan/engine/xbg_safe_mode.h').read_text(encoding='utf-8')
    # defaults 0 on every family, read through the policy; the app sets neither; safe mode step 2 forces both off
    assert 'inline int xbg_nr_z3_default(){return 0;}' in pol and 'inline int xbg_nr_z5_default(){return 0;}' in pol, 'Z3 / Z5: default 0 on every family'
    assert 'const char *e=getenv("DM_NR_Z3");int m=e && *e?atoi(e):xbg_nr_z3_default();' in z, 'Z3: the switch through the policy default'
    for src in ('android/jni_android.c',):
        assert 'DM_NR_Z3' not in (root / src).read_text(encoding='utf-8') and 'DM_NR_Z5' not in (root / src).read_text(encoding='utf-8'), 'Z3 / Z5: the app does not set the switches'
    java = root / 'android/app/src/main/java'
    for p in java.rglob('*.java'):
        t = p.read_text(encoding='utf-8', errors='replace')
        assert 'DM_NR_Z3' not in t and 'DM_NR_Z5' not in t, 'Z3 / Z5: the app does not set the switches (%s)' % p.name
    assert 'add("DM_NR_Z3","0");add("DM_NR_Z5","0");' in sm and sm.index('if(step>=2){') < sm.index('add("DM_NR_Z3","0")') < sm.index('if(step>=3){'), 'Z3 / Z5: safe-mode step 2'
    # 0 = one load and a not-taken branch in draw(); the hook sits right after the command buffer is taken, before descriptors_stable
    hook = 'if(__builtin_expect(nrz3::mode!=0,0)){nrz3::begin();'
    assert g.count(hook) == 1 and g.index('DRAW_MARK(1);Commands c(true);') < g.index(hook) < g.index('if(z3r!=3)dp=&descriptors_stable(c,false);') < g.index('    create_pass(p,c);DRAW_MARK(2);'), 'Z3: the hook before the descriptors'
    assert 'if(nrdraw::cur && !gi && quad_indices.empty() && ui_uy==0 && ui_vs==1 && g_ui_moff==0){z3r=nrz3::draw(' in g and 'if(z3r==1)return;}}' in g, 'Z3: only a plain engine draw with a record identity asks'
    assert 'if(z3r!=2 && (nrdraw::cur || (nrdraw::ui_rec && nrdraw::ui_pick())) && nrdraw::lane(' in g, 'Z3: after return 2 the old tail runs as after a lane() that returned false'
    assert g.index('#include "xbg_nr_draw.inc"') < g.index('#include "xbg_nr_z3.inc"') < g.index('#include "xbg_nr_sort.inc"'), 'Z3: included right after the lane'
    assert 'if(mode<=0)return 0;' in z and 'void begin(){if(mode<0){init();if(mode<0)return;}K.ok=false;ps_called=false;}' in z, 'Z3: nothing runs at 0; the key of the draw before is dropped'
    # 3 does not exist; needs DM_NR_DRAW=1 and DM_NR_DESC=1; Z5 is not built
    assert 'DM_NR_Z3=3 does not exist' in z and 'if(m && (nrdraw::mode!=1 || nrdesc::mode!=1)){' in z and 'nrz5::init(nrdraw::mode);' in z, 'Z3: modes (DM_NR_Z5 is read by nrz5)'
    # the key: every part through nrz_key (the function the host test mutates); the engine build never mutates
    assert 'K.n=nrz_key(K.w,g,g+NRZ_KEY_SH,g+NRZ_KEY_SH+NRZ_KEY_FIXED,dpn.nimg,t.key,var.w[4],var.w[5],var.w[3]);' in z and 'nrdesc::gather(dpn,f,g)' in z, 'Z3: the key is NR-08\'s words + key id + variant bits + state ids + pass definition'
    assert 'NRZ_MUTATE' not in z and 'NRZ_MUTATE' not in g and 'NRZ_MUTATE' not in lane and '#define NRZ_MUTATE 0' in h, 'Z3: the mutation switch is the test\'s only'
    for part in ('NRZ_MUTATE == 1 ? 0 : sh[i]', 'NRZ_MUTATE == 2 ? 0 : fixed[i]', 'NRZ_MUTATE == 3 ? 0 : th[2 * i]', 'NRZ_MUTATE == 4 ? 0 : th[2 * i + 1]', 'NRZ_MUTATE == 5 ? 0 : (uint64_t)key_id',
                 'NRZ_MUTATE == 6 ? 0 : var4', 'NRZ_MUTATE == 7 ? 0 : var5', 'NRZ_MUTATE == 8 ? 0 : pass_def', 'NRZ_MUTATE != 9 + (int)i && a[i] != b[i]'):
        assert part in h, 'Z3: key part / stamp under the mutation test: %s' % part
    # the stamps: NR-08's id generation (flush, release), NR-09's clears (here and in nrp_tab_put), the object epoch
    assert z.count('{nrdesc::tab_gen,nrdraw::tab_gen(),nbpipe::epoch}') == 2, 'Z3: the same three stamps at the lookup and at the store'
    assert 'nr_dtab_clear(&tab);++tab_gen;' in nd and 'ents.clear();++tab_gen;' in nd, 'Z3: NR-08 flush / release move its generation'
    assert 'inline uint64_t tab_gen(){return tgen+T.full;}' in lane and 'if(T.n){nrp_tab_clear(&T);++s.tab_clears;}++tgen;epoch=nbpipe::epoch;}' in lane and lane.count('nrp_tab_clear(') == 1, 'Z3: every clear of NR-09\'s table moves its generation'
    assert 'if(nrdraw::epoch!=nbpipe::epoch)return out(NRZW_STALE);' in z, 'Z3: an object epoch the lane has not seen yet is not answered'
    assert 'if(!psk && (!pe || !pe->pipe))return out(NRZW_PIPE);' in z and 'H.ent=pe;H.pipe=VkPipeline(pe->pipe);H.used=pe->used;H.inst=pe->inst;H.zero=pe->zero;memcpy(H.stride,pe->stride,sizeof H.stride);' in z, 'Z3: the pipeline and bindings are read from NR-09\'s entry at every draw'
    # live checks, in the order of the path without the table; nothing is changed before the last check that can fail
    order = ['if(nrdesc::mode!=1 || nrdraw::mode!=1)return out(NRZW_GATE);', 'if(!desc_memo_enabled || capture.active || provenance_file || g_ui_moff!=0 || pgraph::armed || nroc::twin_draw || nrlf::fused_draw || read_preflight)return out(NRZW_GATE);',
             'if(nroc::mode>0 || nrpo::mode!=0 || nrps::mode<0 || nrsort::mode!=0 || nrmdi::mode!=0)return out(NRZW_GATE);', '!(pp?nrdraw::groups_pp():nrdraw::groups()))return out(NRZW_GATE);',
             'if(dpn.why || pl->retry || !pl->layout || !pl->layout->definition.valid)return out(NRZW_NO_PLAN);', 'if(memo_epoch!=nrdesc::my_epoch)return out(NRZW_DESC);', 'if(!pass_continues(c))return out(NRZW_PASS);',
             'const nrz_val *v=nrz_find(&T,K.h,K.w,K.n,stamp,&stale);', 'if(e.plan!=pl || !e.live || e.ring!=rb || !nrdesc::images_alive(e))return out(NRZW_DESC);', 'if(mode==2){P.valid=true;',
             'if(nrdesc::blocks(*pl,rb,off,tuple,false))return out(NRZW_BLOCK);', 'if(!sv)return out(NRZW_SET);', 'storage_images_bound.clear();pgraph::cx_sh=nullptr;nrrp::frag_first=tile_barrier_on && frag;',
             'Image &gi=get_image(ti.first,true);prepare_read(gi,c.command,-1);', 'if(slot_serial!=s0){c.command=recording_slot().cmd;return out(NRZW_IMAGE);}', 'nrdesc::note_last(*pl,v->did,f);',
             'if(nrd && !pass_continues(c)){', 'for(auto *im:zp.images){im->prior_write=im->last_write;im->last_write=++write_seq;im->gpu_written=true;}++pass_fast_hits;', 'nrdraw::cur=nullptr;',
             'if(nrdraw::lane_tail(c,nullptr,ds,zp,', 'dp=&d;p=zp;++s.why[NRZW_LATE];return 2;}']
    at = -1
    for o in order:
        assert z.count(o) == 1, 'Z3: %s' % o
        assert z.index(o) > at, 'Z3: order of the checks / effects: %s' % o
        at = z.index(o)
    # =2 takes nothing from the table: the prediction is made before the first statement with a side effect
    assert z.index('if(mode==2){P.valid=true;') < z.index('nrdesc::blocks(*pl,rb,off,tuple,false)'), 'Z3: =2 predicts before the blocks'
    # the same image rule, the same create_pass marks, the same tail as the path without the table
    img = 'const nr_dimg_in x{im.last_write,im.storage_write,im.opw,uint8_t(im.checked_submission==stats.submissions),uint8_t(im.uploaded),uint8_t(im.gpu_written),uint8_t(im.layout==VK_IMAGE_LAYOUT_GENERAL),uint8_t(hook)};'
    assert img in z and nd.count(img) == 2, 'Z3: serve()\'s image rule, word for word'
    assert 'p=last_pass.pass;for(auto *im:p.images){im->prior_write=im->last_write;im->last_write=++write_seq;im->gpu_written=true;}++pass_fast_hits;return true;}' in g, 'Z3: create_pass\'s fast path is what nrz3 repeats'
    assert 'if(plain_draw && !ua_detach && last_pass.valid && open_pass.cmd==c.command && open_pass.pass==last_pass.pass.pass && open_pass.framebuffer==last_pass.pass.framebuffer && !memcmp(&state.rt,&last_pass.rt,sizeof state.rt)){' in g and \
        'return last_pass.valid && open_pass.cmd==c.command && open_pass.pass==last_pass.pass.pass && open_pass.framebuffer==last_pass.pass.framebuffer && !memcmp(&state.rt,&last_pass.rt,sizeof state.rt);}' in z, 'Z3: create_pass\'s own test'
    assert 'const bool plain_draw=c.draw && clear_color<0 && !clear_depth && !soft && !provenance_file && !capture.active && !ab_off("passfast");' in g and 'ab_off("passfast")' in z, 'Z3: the gates of a plain draw'
    pk = ua[ua.index('int detach_peek(VkCommandBuffer cmd){'):ua.index('bool detach(VkCommandBuffer cmd){')]
    dt = ua[ua.index('bool detach(VkCommandBuffer cmd){'):]
    assert 'if(continues(cmd) && !memcmp(&state.rt,&cur.rt,sizeof state.rt)){' in pk and 'if(!cur.rec.detached || !uses)return cur.rec.detached?1:0;' in pk and 'if(uses || state.rt.n<1 || cls()==NB_UA_CLS_OTHER)return 0;' in pk, 'Z3: detach_peek'
    assert 'if(continues(cmd) && !memcmp(&state.rt,&cur.rt,sizeof state.rt)){\n        if(!cur.rec.detached || !uses)return cur.rec.detached;' in dt and 'if(uses || state.rt.n<1 || cls()==NB_UA_CLS_OTHER)return false;' in dt, 'Z3: detach() still starts with the tests detach_peek repeats'
    assert pk.count('return -1;') == 3 and '++' not in pk and 'hist_put' not in pk and 'frame_sync' not in pk, 'Z3: detach_peek changes nothing'
    assert 'frag_read(tile_barrier_on && !compute && desc_frag_only_shaders());' in g and 'x.frag=desc_frag_only_shaders();' in z, 'Z3: the fragment-only test is descriptors()\'s function'
    # the lane's tail is one function for both paths; lane() ends in it
    assert lane.count('bool lane_tail(') == 2 and 'return lane_tail(c,&d,ds,p,first,count,indexed,instances,first_instance,flags,ui,lm,active_colors,tm);}' in lane, 'Z3: lane() ends in the shared tail'
    tail = lane[lane.index('bool lane_tail(Commands &c,Descriptors *dr,const DSet &ds,Pass &p,int first,int count,const p_draw_idx *indexed,uint32_t instances,uint32_t first_instance,unsigned flags,bool ui,int lm,uint32_t active_colors,const Tm &tm){'):lane.index('// The old tail finished a draw lane() left to it')]
    for must in ('vkCmdBindPipeline(', 'vkCmdBindDescriptorSets(c.command,VK_PIPELINE_BIND_POINT_GRAPHICS,ds.layout,0,1,&ds.set,no,ds.off);', 'vkCmdBindVertexBuffers(', 'vkCmdDrawIndexed(', 'snapshot(', 'viewport_of(p,H.vp,H.sc)', 'mark_storage_images();', 'c.finish();',
                 'if(dr && dr->needs_writeback())return fail(NRW_WRITEBACK);', '&& dr && nrsort::take(c,*dr,p,', 'if(dr)dr->defer_writeback();', 'if(dr)drecy::done(*dr);'):
        assert must in tail, 'Z3: the shared tail holds %s' % must
    assert not re.search(r'vkCmd\w+\(', z), 'Z3: no command is recorded outside the shared tail'
    assert 'if(__builtin_expect(nrz3::mode>0,0) && dr && !ui)nrz3::served();' in tail and 'if(nrz3::span_t0)nrz3::span_end();' in tail, 'Z3: the path without the table teaches / is compared at the end of the tail'
    # learning: only what NR-08 answered, and only under a key that names what the path resolved
    assert 'const bool have=nrdesc::z_out==NRZD_HIT || nrdesc::z_out==NRZD_BUILT;' in z and 'nr_dtab_find(&nrdesc::tab,nr_dkey_hash64(K.w,K.ng),K.w,K.ng)!=pl->last' in z, 'Z3: a stored resolution is NR-08\'s own entry of the key'
    for c in ('z_out=NRZD_FELL_GATE;z_rd=0;', '{z_out=NRZD_BUILT;const bool re=e.live;', '{z_out=NRZD_FELL_LIVE;++s.fall[w];', '{z_out=NRZD_FELL_LIVE;++s.fall[F_SET];return false;}', 'z_out=NRZD_HIT;z_rd=nrd;', 'z_out=NRZD_BUILT;id=add_entry('):
        assert c in nd, 'Z3: serve() says how it answered (%s)' % c
    # measurement: the span line in any mode, the 10 s lines, the by-part line apart from the 1-in-64 average
    assert 'if(nrdraw::cur)nrz3::span_t0=(++nrz3::span_calls&63)?0:timing_clock();else nrz3::span_t0=0;' in g and '"[nr] draw span (NR-ZERO,' in lane, 'Z3: the span line'
    assert '"[nr] z3: DM_NR_Z3=%d;' in z and '"[nr] z3 by part (NR-ZERO,' in z and '"[nr] z3 check (DM_NR_Z3=2):' in z and '【红】[nr] z3: %s' in z, 'Z3: the lines'
    assert 'NbState, NbDraw, NrDesc, NrLane, MtEnd, NrZ3, Count };' in (root / 'gfx/vulkan/engine/xbg_cpu_timing.h').read_text(encoding='utf-8') and g.count('"nrlane","mtend","nrz3"};') == 2, 'Z3: its own CPU part'
    # [PRESKIN] nrps::decide at its place (after the answered pass, before the lane); a skinning vertex shader's draw goes through the lane itself;
    # draw() does not decide twice; =2 masks PRESKIN's variant bits; ONCHIP is a gate only while its backend is on (not superseded)
    assert 'const bool psk=nrps::mode==1 && state.shader[0]->psk==1;' in z and z.count('nrps::decide(active_colors,false,prim,count,indexed,instances);ps_called=true;') == 1, 'Z3: PRESKIN decided inside nrz3'
    assert z.index('++pass_fast_hits;') < z.index('nrps::decide(active_colors,false,') < z.index('if(nrdraw::lane(c,d,zp,prim,first,count,indexed,instances,first_instance,pp?unsigned(nrdraw::F_PP):0u,draw_fast)){++s.psk_rec;return 1;}') < z.index('nrdraw::cur=nullptr;'), 'Z3: PRESKIN after the pass marks; a skinned draw takes the lane'
    assert 'if(__builtin_expect(nrps::mode!=0,0)){if(!(z3r==2 && nrz3::ps_called))nrps::decide(' in g, 'Z3: draw() does not run nrps::decide twice'
    assert 'const uint64_t w4=nrps::P.on?H.var.w[4]&((1ull<<40)-1):H.var.w[4];' in z and 'now.pent=nrps::P.on?0:uint64_t(uintptr_t(H.ent));' in z and 'if(psk)now.pent=P.v.pent;' in z, 'Z3: PRESKIN\'s variant bits are not the table\'s'
    assert 'const int fe=nrlf::fe_mode(m);if(nrlf::mode)m=0;' in (root / 'gfx/vulkan/engine/xbg_nr_onchip.inc').read_text(encoding='utf-8'), 'Z3: ONCHIP superseded by LIGHTFUSE has mode 0 (nrz3 gates on nroc::mode>0)'
    print('PASS: NR-ZERO Z3 DM_NR_Z3: default 0 by policy, app silent, safe-mode step 2; hook before the descriptors; key through nrz_key (mutation switch test-only); three stamps; '
          'checks before effects in the path\'s order; =2 predicts before any effect; shared lane tail; detach_peek pure; PRESKIN decided at its place, skinned draws through the lane')
def nrz3e_check():   # [DOS2] NR-ZERO Z3b / Z3c / Z3d (docs/dos2/nr/NR-ZERO.md section 13): the image word, the mesh view table, the ring word
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    z = (root / 'gfx/vulkan/engine/xbg_nr_z3.inc').read_text(encoding='utf-8')
    x = (root / 'gfx/vulkan/engine/xbg_nr_z3e.inc').read_text(encoding='utf-8')
    h = (root / 'gfx/nr/nr_z3e.h').read_text(encoding='utf-8')
    lane = (root / 'gfx/vulkan/engine/xbg_nr_draw.inc').read_text(encoding='utf-8')
    nd = (root / 'gfx/vulkan/engine/xbg_nr_desc.inc').read_text(encoding='utf-8')
    nb = (root / 'gfx/vulkan/engine/xbg_nr_buf.inc').read_text(encoding='utf-8')
    pol = (root / 'gfx/vulkan/engine/xbg_vendor_policy.h').read_text(encoding='utf-8')
    sm = (root / 'gfx/vulkan/engine/xbg_safe_mode.h').read_text(encoding='utf-8')
    for k in ('z3b', 'z3c', 'z3d'):
        assert 'inline int xbg_nr_%s_default(){return 0;}' % k in pol and 'xbg_nr_%s_default()' % k in x, 'Z3b-d: default 0 through the policy (%s)' % k
    assert 'add("DM_NR_Z3B","0");add("DM_NR_Z3C","0");add("DM_NR_Z3D","0");' in sm and sm.index('if(step>=2){') < sm.index('add("DM_NR_Z3B","0")') < sm.index('if(step>=3){'), 'Z3b-d: safe-mode step 2'
    for src in [root / 'android/jni_android.c'] + list((root / 'android/app/src/main/java').rglob('*.java')):
        tx = src.read_text(encoding='utf-8', errors='replace')
        assert 'DM_NR_Z3B' not in tx and 'DM_NR_Z3C' not in tx and 'DM_NR_Z3D' not in tx, 'Z3b-d: the app does not set the switches (%s)' % src.name
    for f in (g, z, x, lane, nd, nb):
        assert 'NRZE_MUTATE' not in f and 'NRZE_MODEL_DROP' not in f, 'Z3b-d: the mutation switches are the test\'s only'
    assert '#define NRZE_MUTATE 0' in h and '=3 does not exist' in x and 'if(v<0 || v>2){' in x, 'Z3b-d: modes 0 / 1 / 2'
    # Z3b: the fields nr_dimg_skip reads are of the types that move the epoch; ~Image moves it; nothing else can end "quiet"
    for decl in ('nrz_leave<VkImageLayout,VK_IMAGE_LAYOUT_GENERAL> layout{VK_IMAGE_LAYOUT_UNDEFINED};', 'nrz_fall uploaded{false};nrz_rise<bool> gpu_written{false};', 'nrz_rise<uint64_t> storage_write{0};',
                 'nrz_checked checked_submission{UINT64_MAX};nrz_rise<uint64_t> last_write{0},opw{0};', '~Image(){++nrz_img_ep;'):
        assert g.count(decl) == 1, 'Z3b: Image field / destructor: %s' % decl
    img = 'const nr_dimg_in x{im.last_write,im.storage_write,im.opw,uint8_t(im.checked_submission==stats.submissions),uint8_t(im.uploaded),uint8_t(im.gpu_written),uint8_t(im.layout==VK_IMAGE_LAYOUT_GENERAL),uint8_t(hook)};'
    assert nd.count(img) == 2 and z.count(img) == 1 and (g + lane + nb + x).count('nr_dimg_in x{') == 0, 'Z3b: the three walks read exactly the seven guarded inputs (and the hook)'
    assert 'uint64_t nrz_sub_now(){return stats.submissions.load(std::memory_order_relaxed);}' in g, 'Z3b: "checked in this submission" against the live submission number'
    for fld, typ in (('layout', 'nrz_leave'), ('uploaded', 'nrz_fall'), ('gpu_written', 'nrz_rise'), ('storage_write', 'nrz_rise'), ('last_write', 'nrz_rise'), ('opw', 'nrz_rise'), ('checked_submission', 'nrz_checked')):
        assert re.search(r'struct %s\b[^;]*\{\s*\n?\s*\w+ v;\s*\n\s*~%s\(\) \{\}' % (typ, typ), h), 'Z3b: %s is not passable through a variadic call (user-provided destructor)' % typ
    for m in re.finditer(r'slot_use=([^;]+);', g + nd + z + (root / 'gfx/vulkan/engine/xbg_nb_hit.inc').read_text(encoding='utf-8')):
        assert m.group(1) in ('slot_serial', '0'), 'Z3b: slot_use is only ever set to the slot serial (%s)' % m.group(0)
    assert nd.count('quiet_ask(e,hook)') == 1 and nd.count('quiet_done(e,hook,zq,nrd)') == 1 and z.count('nrdesc::quiet_ask(e,hook)') == 1 and z.count('nrdesc::quiet_done(e,hook,zq,nrd)') == 1, 'Z3b: both walks ask and report'
    assert 'if(hook || !nrz_quiet_ok(&e.quiet,nrz_img_ep,nrz_sub_now(),slot_serial))return false;' in nd and 'if(!nrd && !hook && !asked_quiet){nrz_quiet_set(&e.quiet,nrz_img_ep,nrz_sub_now(),slot_serial);' in nd, 'Z3b: the three words'
    assert 'if(zq && nrzx::bmode==1){s.img+=e.img.size();s.img_skip+=e.img.size();}else{' in nd and 'if(!(zq && nrzx::bmode==1)){' in z, 'Z3b: only =1 leaves the walk out'
    assert 'e=Ent{};e.plan=&pl;' in nd and 'nrz_quiet quiet{};' in nd, 'Z3b: a remade entry starts without the word'
    # Z3c: every event that can change an answer moves a word of its stamp
    for must in ('c.live=false;++live_ep;', 't.live=true;++live_ep;', 'if(!c.sticky[pg]){c.sticky[pg]=1;++c.st_ver;}++c.wr_ver;', '++trx::hot_adds;++c.wr_ver;}}', '++hits;last_chunk=int(c-table);return true;',
                 'if(nrr==1){snap_how=1;return nrz;}', 'if(zc::view(address,bytes,align,z)){snap_how=2;return z;}'):
        assert g.count(must) == 1, 'Z3c: %s' % must
    assert g.count('.live=false') == 1 and g.count('.live=true') == 1 and g.count('sticky[pg]=1') == 1 and g.count('nrt_wr_add(') == 2, 'Z3c: no other writer of chunk liveness / sticky pages / written ranges'
    wv = g.index('if(!c.sticky[pg]){c.sticky[pg]=1;++c.st_ver;}++c.wr_ver;'); assert wv < g.index('nrt_wr_add(&c.wr,') < wv + 900 and g.count('++trx::hot_adds;++c.wr_ver;}}') == 1, 'Z3c: both written-range sets move the write version of the chunk (mark(): for the chunk it marks; the guard: on its line)'
    for must in ('if(c.dead)return;c.dead=true;++st_ep;', 'k.live=false;++st_ep;', 'e->phase=NRS_DEMOTED;++st_ep;', 'if(!q.empty())++st_ep;', 'since_apply=0;++st_ep;}}', 'if(st_mode<=0 || !tab_ok)return;\n    ++st_ep;',
                 'nr_stab_apply(&tab,gone,nullptr);++st_ep;}}', '++st_ep;chunks.clear();'):
        assert nb.count(must) == 1, 'Z3c: NR-06 static epoch: %s' % must
    assert nb.count('nr_stab_apply(') == 2 and nb.count('nr_stab_add(') == 1 and nb.count('nr_stab_kill(') == 1 and nb.count('nr_stab_drop(') == 1 and nb.count('NRS_DEMOTED;') == 1 and len(re.findall(r'(?:e->|e.)phase=NRS_', nb)) == 5, 'Z3c: no other writer of the static table / an entry\'s phase'
    assert lane.count('nrzx::view(') == 2 and 'b=nrzx::view(r.address,r.size,1,H.stride[i]);' in lane and 'b=nrzx::view(uint64_t(indexed->ibuf),bytes,2,0);' in lane, 'Z3c: the lane\'s two views'
    assert 'else{snap_site=1;nrbuf::stride_hint=H.stride[i];b=snapshot(r.address,r.size);nrbuf::stride_hint=0;snap_site=0;}' in lane and 'else{snap_site=2;b=snapshot(uint64_t(indexed->ibuf),bytes);snap_site=0;}' in lane, 'Z3c: at 0 the statements of before'
    assert 'const uint64_t st[NRZV_STAMPS]={zc::live_ep,zc::table[e->chunk].wr_ver,slot_serial,hit_pend_gen};' in x and 'const uint64_t st[NRZV_STAMPS]={snapshot_epoch,nrbuf::st_ep,0,hit_pend_gen};' in x, 'Z3c: the stamps at the lookup'
    assert 'n.st[0]=zc::live_ep;n.st[1]=zc::table[zc::last_chunk].wr_ver;n.st[2]=slot_serial;n.st[3]=hit_pend_gen;' in x and 'n.st[0]=snapshot_epoch;n.st[1]=nrbuf::st_ep;n.st[2]=0;n.st[3]=hit_pend_gen;' in x, 'Z3c: the same stamps at the store'
    assert 'if(zc::enabled>0 && nrbuf::st_mode<=0 && e->chunk>=0' in x and 'else if(how==2 && nrbuf::st_mode<=0 && zc::last_chunk>=0){' in x, 'Z3c: zero-copy views are kept only while NR-06\'s static copies are off (they come first in snapshot())'
    assert 'if(fresh && cmode==1){' in x and 'snap_how=0;const Buffer b=view_real(address,bytes,site,stride);const int how=snap_how;' in x, 'Z3c: only =1 answers from the table; =2 asks snapshot()'
    for w in re.finditer(r'pending_writebacks\.(?:push_back|emplace_back|erase|clear|pop_back|swap|resize|insert)\([^\n]*', g):
        assert 'hit_pend_gen' in g[g.rfind('\n', 0, w.start()):g.find('\n', w.start())], 'Z3c: a writer of pending_writebacks without ++hit_pend_gen on its line'
    # Z3d: the ring word
    assert 'if(zd.live_ep==zc::live_ep && zd.r.lo==ring_base && zd.size==ring_size && (!zd.c || zd.st_ver==zd.c->st_ver))return zd.r.ok!=0;' in nb, 'Z3d: the words of the ring word'
    assert 'if(&o!=c && o.live && o.lo<zd.r.hi && zd.r.lo<o.lo+o.n)return false;' in nb and 'zd.r.ok=nrz_ring_clean(c->sticky.data(),c->lo,c->n,zd.r.lo,zd.r.hi);' in nb, 'Z3d: one chunk over the ring, no sticky page'
    assert 'if(!zd_valid() || g_ui_moff!=0 || !pending_writebacks.empty())return 0;' in nb and 'if(mode!=1 && mode!=3)return 0;' in nb, 'Z3d: the walk\'s own gates before the word answers'
    assert 'if(g_ui_moff!=0 && address==g_ui_moff_addr)why=W_UI;' in nb and 'else if(!pending_writebacks.empty() && overlaps_pending(address,n))why=W_PEND;' in nb, 'Z3d: the walk still starts with the two tests the word repeats'
    assert nd.count('nrbuf::ubo_fast(u.address,copy,zo,nrzx::dmode==1)') == 1 and 'if(zr<0)zr=nrbuf::ubo(u.address,copy,z);' in nd and 'if(zr!=1 || z.buffer!=rb || z.offset>0xffffffffull)return F_RINGMISS;' in nd, 'Z3d: blocks() asks the word, then the walk; the result is tested as before'
    assert 'else{zr=nrbuf::ubo(u.address,copy,z);++nrzx::s.d_checked;if(zr!=1 || z.buffer!=nrbuf::zd.buf || z.offset!=zo){++nrzx::s.d_bad;' in nd, 'Z3d: =2 runs the walk and compares'
    assert 'nrzx::init(nrdesc::mode,nrdraw::mode,nrdraw::ui_mode);' in z and '"[nr] z3 epochs: DM_NR_Z3B=%d:' in x and '【红】[nr] z3 epochs: %s' in x, 'Z3b-d: read once, their line'
    print('PASS: NR-ZERO Z3b / Z3c / Z3d: defaults 0 by policy, app silent, safe-mode step 2; image fields of the epoch types + ~Image; chunk liveness / write version / sticky version, '
          'NR-06 static epoch and pending-writeback generation at every writer; the lane\'s two views; the ring word behind the walk\'s own gates; =2 runs the walk')
def nrz5_check():   # [DOS2] NR-ZERO Z5 DM_NR_Z5 (docs/dos2/nr/NR-ZERO.md section 14): the packet side and its comparison; the game thread's half is not built
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    z5 = (root / 'gfx/vulkan/engine/xbg_nr_z5.inc').read_text(encoding='utf-8')
    h = (root / 'gfx/nr/nr_z5.h').read_text(encoding='utf-8')
    mt = (root / 'gfx/vulkan/engine/xbg_nb_mt.inc').read_text(encoding='utf-8')
    q = (root / 'gfx/nb/nb_mt.h').read_text(encoding='utf-8')
    lane = (root / 'gfx/vulkan/engine/xbg_nr_draw.inc').read_text(encoding='utf-8')
    assert 'int m=e && *e?atoi(e):xbg_nr_z5_default();' in z5 and 'if(m==1){' in z5 and 'if(m!=0 && m!=2){' in z5 and "the game thread's half is not built" in z5, 'Z5: default through the policy; =1 refused; only =2'
    assert g.index('#include "xbg_nr_z5.inc"') < g.index('#include "xbg_nr_draw.inc"'), 'Z5: before the lane'
    assert 'NRZ5_MUTATE' not in z5 and 'NRZ5_MUTATE' not in mt and 'NRZ5_MUTATE' not in lane and '#define NRZ5_MUTATE 0' in h, 'Z5: the mutation switch is the test\'s only'
    # =2 records nothing: no queue hand-over, no command, no write to the bind cache from nrz5
    assert 'splice(' not in z5 and 'give_back(' not in z5 and not re.search(r'vkCmd\w+\(|nbmt::Cmd\w+\(', z5) and 'const BindCache &bc' in z5 and z5.count('BindCache &bc') == z5.count('const BindCache &bc'), 'Z5: the comparison changes nothing'
    assert 'nbmt::Build b{scratch};nbmt::Z5Sink sink{b};' in z5 and 'nbmt::same_stream(cc->data()+from,cc->used-from,scratch->data(),scratch->used,&at)' in z5, 'Z5: the assembler writes into a chunk of its own; compared with the tail\'s packets'
    assert 'if(cc && cc==nbmt::q.cur && ch0==nbmt::q.st.chunks){' in z5, 'Z5: only packets still in the producer\'s current chunk are read'
    tail = lane[lane.index('bool lane_tail(Commands &c,Descriptors *dr,'):lane.index('// The old tail finished a draw lane() left to it')]
    b0 = tail.index('BindCache &bc=bind_cache;if(bc.cmd!=c.command){bc=BindCache{};bc.cmd=c.command;}'); b1 = tail.index('if(__builtin_expect(nrz5::mode!=0,0))nrz5::draw_begin(c.command,bc,ui);'); b2 = tail.index('vkCmdBindPipeline(')
    e0 = tail.index('if(cond_gpu_draw)condr::gpu_end(c.command);'); e1 = tail.index('if(__builtin_expect(nrz5::mode!=0,0))nrz5::draw_end(bc,H.pipe,H.used,H.vb,H.vbo,H.ib,H.ibo,H.it,H.vp,H.sc,ds.layout,ds.set,ds.no,ds.off,')
    assert b0 < b1 < b2 < e0 < e1 < tail.index('S->cmds+=n;') and tail.count('nrz5::') == 4, 'Z5: draw_begin before the tail\'s first command, draw_end after its last'
    # the assembler is the tail's command section: the same tests in the same order
    for a, b in (('if(bc.pipe!=H.pipe){vkCmdBindPipeline(', 'c->pipe != v->pipe) { if (!s.pipeline(v->pipe)) return 0;'),
                 ('else if(bc.layout!=ds.layout || bc.set!=ds.set || bc.noff!=no || no>32 || (no && memcmp(bc.off,ds.off,no*4))){', 'if (c->layout != v->layout || c->set != v->set || c->noff != no || no > NRZ5_MAX_OFF || (NRZ5_MUTATE != 2 && no && memcmp(c->off, v->off, (size_t)no * 4))) {'),
                 ('if(no<=32){bc.layout=ds.layout;bc.set=ds.set;bc.noff=no;if(no)memcpy(bc.off,ds.off,no*4);}else bc.noff=UINT32_MAX;}', 'else c->noff = 0xffffffffu;'),
                 ('if(!bc.has_vp || memcmp(&bc.vp,&H.vp,sizeof H.vp)){vkCmdSetViewport(', 'if (!c->has_vp || (NRZ5_MUTATE != 4 && memcmp(c->vp, v->vp, NRZ5_VP_BYTES))) {'),
                 ('if(!bc.has_sc || memcmp(&bc.sc,&H.sc,sizeof H.sc)){vkCmdSetScissor(', 'if (!c->has_sc || (NRZ5_MUTATE != 5 && memcmp(c->sc, v->sc, NRZ5_SC_BYTES))) {'),
                 ('if(bc.vb[i]!=H.vb[i] || bc.vbo[i]!=H.vbo[i])changed|=1u<<i;', 'if (c->vb[i] != v->vb[i] || c->vbo[i] != v->vbo[i]) changed |= 1u << i;'),
                 ('const unsigned runs=nr_vb_runs(changed,H.used,f,k);', 'nr_vb_runs(changed, v->used, f, k);'),
                 ('if(bc.ib!=H.ib || bc.ibo!=H.ibo || bc.it!=H.it){vkCmdBindIndexBuffer(', 'if (c->ib != v->ib || c->ibo != v->ibo || (NRZ5_MUTATE != 7 && c->it != v->it)) {')):
        assert a in tail and b in h, 'Z5: the tail\'s test and the assembler\'s: %s' % a
    order = ['s.pipeline(', 's.sets(', 's.viewport(', 's.scissor(', 's.vertex(', 's.index(', 's.draw_indexed(']; at = -1; em = h[h.index('template <class Sink> static inline unsigned nrz5_emit('):h.index('static inline void nrz5_after(')]
    for o in order: assert em.index(o) > at, 'Z5: the assembler\'s command order: %s' % o; at = em.index(o)
    order = ['vkCmdBindPipeline(', 'vkCmdBindDescriptorSets(', 'vkCmdSetViewport(', 'vkCmdSetScissor(', 'vkCmdBindVertexBuffers(', 'vkCmdBindIndexBuffer(', 'vkCmdDrawIndexed(']; at = -1
    for o in order: assert tail.index(o) > at, 'Z5: the tail\'s command order: %s' % o; at = tail.index(o)
    assert tail.count('bc.') == 39, 'Z5: a new use of the bind cache in the tail must be mirrored in nr_z5.h (nrz5_emit / nrz5_after / nrz5_cache_diff): %d' % tail.count('bc.')
    # the packet side: layouts shared by the wrappers and the builder; splice hands over through the one hand-over
    for lay in ('template <class... A> struct PodP { Pkt k; std::tuple<A...> v; };', 'struct PBindSets { Pkt k; VkPipelineBindPoint bp; VkPipelineLayout l; uint32_t first, n, nd; const VkDescriptorSet *sets; const uint32_t *dyn; };',
                'struct PBindVB { Pkt k; uint32_t first, n; const VkBuffer *b; const VkDeviceSize *o; };', 'struct PViewport { Pkt k; uint32_t first, n; const VkViewport *v; };', 'struct PScissor { Pkt k; uint32_t first, n; const VkRect2D *v; };'):
        assert mt.count(lay) == 1, 'Z5: packet layout %s' % lay
    assert mt.count('using P = PodP<A...>;') == 2 and mt.count('using P = PBindSets;') == 2 and mt.count('using P = PBindVB;') == 2 and mt.count('using P = PViewport;') == 2 and mt.count('using P = PScissor;') == 2, 'Z5: wrapper and builder write the same layout'
    sp = q[q.index('    void splice(Chunk *c) {'):q.index('    void give_back(Chunk *c) {')]
    assert re.search(r'if \(!c\) return;\s*flush\(\);\s*c->cb = cb; st\.cmds \+= c->cmds; \+\+st\.spliced; st\.spliced_cmds \+= c->cmds;\s*cur = c; flush\(\);', sp), 'Z5: splice = the producer\'s chunk first, then the chunk, both by flush()'
    assert '"[nr] z5 check (DM_NR_Z5=2):' in z5 and '【红】[nr] z5: %s' in z5 and 'if(__builtin_expect(nrz5::mode!=0,0))nrz5::tick();' in lane, 'Z5: the lines'
    print('PASS: NR-ZERO Z5 DM_NR_Z5: =1 refused (the game thread\'s half is not built), =2 compares and records nothing; draw_begin / draw_end around the tail\'s command section; '
          'the assembler\'s tests are the tail\'s; shared packet layouts; splice through the one hand-over')
def nrmdi_check():   # [DOS2] NR-MDI DM_NR_MDI (docs/dos2/nr/NR-MDI.md): the multi-draw batching count (=2) and the rebind probe (=3)
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_mdi.inc').read_text(encoding='utf-8')
    lane = (root / 'gfx/vulkan/engine/xbg_nr_draw.inc').read_text(encoding='utf-8')
    core = (root / 'gfx/nr/nr_mdi.h').read_text(encoding='utf-8')
    assert g.index('#include "xbg_nr_sort.inc"') < g.index('#include "xbg_nr_mdi.inc"'), 'NR-MDI: after nrsort (its order-free test)'
    assert lane.count('nrmdi::note(') == 1 and 'if(__builtin_expect(nrmdi::mode!=0,0) && dr)nrmdi::note(c,*dr,p,indexed,instances,first_instance);' in lane, 'NR-MDI: one gated note in the lane (dr: a draw with a Descriptors record; nrz3 answers none while DM_NR_MDI is on)'
    n = lane.index('nrmdi::note('); assert lane.rindex('S->cmds+=n;', 0, n) > lane.rindex('vkCmdDraw', 0, n), 'NR-MDI: note after the lane recorded its commands'
    assert 'if(__builtin_expect(nrmdi::mode==3,0) && nrmdi::probe_keep(' in lane and lane.count('nrmdi::probe_keep(') == 1, 'NR-MDI: the probe only at =3'
    assert 'if(m==1){' in inc and 'm=2;}' in inc and 'if(m!=2 && m!=3)m=0;' in inc, 'NR-MDI: =1 not built (counts), default 0'
    c = re.sub(r'//[^\n]*', ' ', core)
    assert 'vulkan' not in c.lower() and 'getenv' not in c, 'NR-MDI: nr_mdi.h engine-free'
    jni = (root / 'android/jni_android.c').read_text(encoding='utf-8')
    assert 'DM_NR_MDI' not in jni, 'NR-MDI: the app does not set it'
    print('PASS: NR-MDI: count after the lane commands, gated; probe only at =3; =1 not built; core engine-free; not set by the app')
def nrposonly_check():   # [DOS2] NR-POSONLY DM_NR_POSONLY (docs/dos2/nr/NR-POSONLY.md): position-only copies of static meshes for depth-only draws
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_posonly.inc').read_text(encoding='utf-8')
    lane = (root / 'gfx/vulkan/engine/xbg_nr_draw.inc').read_text(encoding='utf-8')
    buf = (root / 'gfx/vulkan/engine/xbg_nr_buf.inc').read_text(encoding='utf-8')
    core = (root / 'gfx/nr/nr_posonly.h').read_text(encoding='utf-8')
    walk = (root / 'gfx/vulkan/engine/xbg_spirv_posonly.cpp').read_text(encoding='utf-8')
    assert g.index('#include "xbg_nr_shc.inc"') < g.index('#include "xbg_nr_posonly.inc"') < g.index('void draw(int prim,int first,int count,const p_draw_idx *indexed'), 'NR-POSONLY: before draw()'
    d = g.index('if(__builtin_expect(nrpo::mode!=0,0))nrpo::decide('); l = g.index('nrdraw::lane(c,d,p,prim,first,count', d)
    assert l - d < 900 and 'else nrpo::P.on=false;' in g[d:l], 'NR-POSONLY: the plan is made right before the lane (only the NR-PRESKIN plan between), cleared when off'
    assert '&& !nrpo::P.on && !nrps::P.on){CPU_SCOPE(Pipeline);' in g and "bool memo=use_fast && pipe_memo && !ab_off(\"pipememo\") && !nrpo::P.on && !nrps::P.on;" in g, 'NR-POSONLY: no state-keyed memo / NB-13b for a planned draw (NR-PRESKIN shares the gate)'
    rw = g.index('nrpo::rewrite(attributes,binding_slots,binding_used,zero_binding);'); assert 0 < g.index('bindings.clear();for(uint32_t i=0;i<16;i++)if(binding_used&(1u<<i))bindings.push_back(binding_slots[i]);   // ascending', rw) - rw < 420, 'NR-POSONLY: the vertex input rewritten right before the binding list (the NR-PRESKIN line between)'
    assert 'if(__builtin_expect(nrpo::P.on,0) && b.binding==nrpo::P.k){vertex_buffers.push_back({b.binding,d.keep(nrpo::P.view)});continue;}' in g, 'NR-POSONLY: the old path binds the copy'
    assert 'if(__builtin_expect(nrpo::P.on,0))v.w[4]|=NR_DRAW_VAR_PO;' in lane and 'if(__builtin_expect(nrpo::P.on,0) && i==nrpo::P.k){H.vb[i]=nrpo::P.view.buffer;off[i]=nrpo::P.view.offset;continue;}' in lane, 'NR-POSONLY: the lane keys and binds it'
    assert 'if(h.stage==0 && nrpo_on_at_load())p->po=xbg_spirv_posonly(words.data(),words.size())?1:0;' in g and 'if(vs->po!=1)return;' in inc and 'if(fs && fs->vo_read!=0)return;' in inc, 'NR-POSONLY: VS proved at load, FS reads no varying'
    assert 'if(!nvn_dirty_since(p,size_t(bytes),c.stamp) && nvn_dirty_version_tok(p,size_t(bytes),&g,&inc,&tok))c.tok=tok;else{ok=false;' in inc and 'if(!nvn_dirty_version_tok(p,size_t(bytes),&g,&inc,&tok)){nrpo_free(' in inc, 'NR-POSONLY: the validity rule of tests/nr_posonly_inval_test.c'
    assert 'if(po_write && tab.n)po_write(a,n);}' in buf and 'if(po_gone)po_gone(e);}' in buf and 'tab_ok=st_mode>0 || po_tab;' in buf, 'NR-POSONLY: NR-06 hooks, the table kept on'
    assert 'if(m!=1 && m!=2)m=0;' in inc and 'DM_NR_POSONLY' not in (root / 'android/jni_android.c').read_text(encoding='utf-8'), 'NR-POSONLY: default 0, not set by the app'
    c = re.sub(r'//[^\n]*', ' ', core)
    assert 'vulkan' not in c.lower() and 'getenv' not in c and 'vulkan' not in walk.lower().replace('no vulkan', ''), 'NR-POSONLY: core and walk engine-free'
    print('PASS: NR-POSONLY: plan before the lane, no state-keyed memo for planned draws, vertex input rewritten, copy bound on both paths, VS proved at load, validity rule as tested, NR-06 hooks, default 0')
def nrpreskin_check():   # [DOS2] NR-PRESKIN DM_NR_PRESKIN (docs/dos2/nr/NR-PRESKIN.md): skinning once per mesh instance and submission
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    g = rd('gfx/vulkan/engine/xbg_game.cpp'); inc = rd('gfx/vulkan/engine/xbg_nr_preskin.inc'); lane = rd('gfx/vulkan/engine/xbg_nr_draw.inc')
    core = rd('gfx/nr/nr_preskin.h'); sp = rd('gfx/vulkan/engine/xbg_spirv_preskin.cpp'); pol = rd('gfx/vulkan/engine/xbg_vendor_policy.h')
    assert g.index('#include "xbg_nr_posonly.inc"') < g.index('#include "xbg_nr_preskin.inc"') < g.index('void draw(int prim,int first,int count,const p_draw_idx *indexed'), 'NR-PRESKIN: after NR-POSONLY, before draw()'
    d = g.index('if(__builtin_expect(nrps::mode!=0,0)){if(!(z3r==2 && nrz3::ps_called))nrps::decide('); l = g.index('nrdraw::lane(c,d,p,prim,first,count', d)
    assert g.index('nrpo::decide(') < d and l - d < 700 and 'else nrps::P.on=false;' in g[d:l], 'NR-PRESKIN: the plan right before the lane (after the NR-POSONLY one), cleared when off'
    a = g.index('nrps::apply_old(stages,xlq_vi,state.shader[4],attributes,binding_slots,binding_used,zero_binding);')
    assert g.index('nrpo::rewrite(attributes,binding_slots,binding_used,zero_binding);') < a < g.index('bindings.clear();for(uint32_t i=0;i<16;i++)if(binding_used&(1u<<i))bindings.push_back(binding_slots[i]);   // ascending', a),         'NR-PRESKIN: consumer module + vertex input after every vertex-module pick, before the binding list'
    assert g.index('idvs_point_module(*state.shader[0],xlq_vi)') < a and g.index('vsout_module(*state.shader[0],xlq_vi,vst->module') < a, 'NR-PRESKIN: after the NR-32 / IDVS picks'
    assert 'if(__builtin_expect(nrps::P.on,0) && b.binding==nrps::P.k){vertex_buffers.push_back({b.binding,d.keep(nrps::P.view)});continue;}' in g, 'NR-PRESKIN: the old path binds the record'
    assert 'if(__builtin_expect(nrps::P.on,0))v.w[4]|=nrps::lane_bits();' in lane and 'if(__builtin_expect(nrps::P.on,0) && i==nrps::P.k){H.vb[i]=nrps::P.view.buffer;off[i]=nrps::P.view.offset;continue;}' in lane, 'NR-PRESKIN: the lane keys (layout id + binding) and binds it'
    assert 'inline uint64_t lane_bits(){return P.on?(uint64_t(P.k)<<40 | uint64_t(P.lay_id)<<44):0;}' in inc and 'if(r->id>=(1u<<20))' in inc, 'NR-PRESKIN: lane bits 40-63 (depth format < 40), ids fit 20 bits'
    # the prologue: its slices first, inside the prologue command buffer submitted ahead of the slot's buffer; that buffer starts with the full barrier
    sub = g[g.index('void submit_slots(bool wait){'):g.index('// Pipelines persist across launches')]
    assert 'const bool nrps_pro=nrps::has_jobs(slot_index);' in sub and sub.index('nrps::prologue(slot_index,s.pro);') < sub.index('VkMemoryBarrier before{') and 'cbs[0]=s.pro;cbs[1]=s.cmd;ncb=2;' in sub,         'NR-PRESKIN: slices recorded first in the prologue, submitted ahead of the slot buffer'
    rs = g[g.index('Slot &recording_slot(){'):g.index('// Submit the recording slot.')]
    assert 'vkCmdPipelineBarrier(s.cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,1,&b,0,nullptr,0,nullptr);' in rs, 'NR-PRESKIN: the first ALL -> ALL barrier of the slot buffer orders the records (no barrier of its own)'
    # inputs the prologue may read: host-written only (no pending GPU result), uniform ranges aligned
    dec = inc[inc.index('void decide('):inc.index("// draw()'s old path")]
    assert dec.count('overlaps_pending(') == 2 and 'u.offset%properties.limits.minUniformBufferOffsetAlignment' in dec, 'NR-PRESKIN: vertex / uniform inputs without pending GPU results, aligned'
    assert 'if(code_draw!=P.code || int(P.k)==zero || (used>>P.k&1)){P.on=false;' in inc, 'NR-PRESKIN: checked before anything changes'
    assert 'if(nrps_on_at_load())p->psk=xbg_spirv_preskin_candidate(words.data(),words.size())?1:0;' in g and 'if(vtx_retype_mode() || nr_xlq || p->psk==1)p->words=words;}' in g, 'NR-PRESKIN: candidates at load, their words kept'
    assert 'inline int xbg_nr_preskin_default(XbgGpuFamily f){return xbg_tile_family(f)?1:0;}' in pol and 'DM_NR_PRESKIN' not in rd('android/jni_android.c'), 'NR-PRESKIN: default 0 everywhere, not set by the app'
    assert 'nrps::release();destroy_slots();' in g and 'if(__builtin_expect(nrps::mode>0,0))nrps::tick();' in lane, 'NR-PRESKIN: release at shutdown, the 10 s line'
    assert '${E}/xbg_spirv_preskin.cpp' in rd('gfx/vulkan/CMakeLists.txt'), 'NR-PRESKIN: built'
    c = re.sub(r'//[^\n]*', ' ', core)
    assert re.findall(r'#include <(\w+)\.h>', core) == ['stdint', 'string'] and 'vulkan' not in c.lower() and 'vulkan' not in re.sub(r'//[^\n]*', ' ', sp).lower(), 'NR-PRESKIN: core and SPIR-V pass engine-free'
    for t in ('tests/nr_preskin_core_test.c', 'tests/nr_preskin_test.cpp'): assert (root / 'gfx/vulkan/engine' / t).is_file(), 'NR-PRESKIN: ' + t
    print('PASS: NR-PRESKIN: plan before the lane, consumer + vertex input after every module pick (checked first), record bound on both paths, lane keyed by layout, '
          'slices first in the prologue (the barrier of the slot buffer orders them), host-written inputs only, candidates at load, default 0, core engine-free')
def nrgmem_check():   # NR-GMEM DM_GFX_PASS_GMEM (docs/dos2/nr/NR-GMEM.md): own GMEM / sysmem choice per render pass on Turnip; 0 = untouched
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    h = rd('gfx/nr/nr_gmem.h'); inc = rd('gfx/vulkan/engine/xbg_pass_gmem.inc'); g = rd('gfx/vulkan/engine/xbg_game.cpp'); vd = rd('android/vk_driver.c')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint'] and '#include "' not in h, 'NR-GMEM: nr_gmem.h is pure C'
    i_mt = g.index('#include "xbg_nb_mt.inc"'); i_pg = g.index('#include "xbg_pass_gmem.inc"')
    assert i_mt < i_pg < g.index('#include "xbg_nb_mx.inc"'), 'NR-GMEM: the funnel comes right after nbmt (every later vkCmd*Begin/EndRenderPass / vkCreateRenderPass of the unit)'
    assert inc.rstrip().endswith('#define vkCreateRenderPass pgm::create_rp') and '#define vkCmdBeginRenderPass pgm::begin_rp' in inc and '#define vkCmdEndRenderPass pgm::end_rp' in inc, 'NR-GMEM: the macros'
    assert 'nbmt::CmdBeginRenderPass(c, b, sc);' in inc and 'nbmt::CmdEndRenderPass(c);' in inc and 'const VkResult r = ::vkCreateRenderPass(d, ci, a, out);' in inc, 'NR-GMEM: the wrappers call through'
    eb = inc[inc.index('void end_rp('):inc.index('// NVN PERF window')]
    assert 'else if (apply) { sysmem = true; ++n_barrier; }' in eb and eb.index('if (sysmem) nbmt::CmdPipelineBarrier(c, VK_PIPELINE_STAGE_VERTEX_SHADER_BIT, VK_PIPELINE_STAGE_VERTEX_SHADER_BIT,') < eb.index('nbmt::CmdEndRenderPass(c);'), \
        'NR-GMEM: a sysmem pass gets the VERTEX barrier before its end, only when applied'
    assert "apply = mode == NRGM_APPLY && drv == 1 && driver_id == 18u" in inc, 'NR-GMEM: =1 applies only on Turnip with the driver side ready'
    assert 'if (!mode) return;' in inc and 'if (r != VK_SUCCESS || !mode || !ci) return r;' in inc, 'NR-GMEM: =0 records and counts nothing'
    assert 'pgm::init(gpu_driver_id);' in g and 'pgm::report(f);' in g and g.count('pgm::note_draw(') == 1 and rd('gfx/vulkan/engine/xbg_nr_draw.inc').count('pgm::note_draw(') == 1, 'NR-GMEM: hooks (init, report, both draw paths)'
    assert 'pgm::note_depth_read(open_pass.cmd);return;}' in g and 'pgm::note_storage(open_pass.cmd);' in g and 'if(d.needs_writeback())pgm::note_storage(c.command);' in g, 'NR-GMEM: hazard vetoes'
    assert 'setenv("TU_DEBUG", pgm1 ? "gmem" : "sysmem", 0);' in vd and 'else if (g_pgm && g_custom && !strcmp(n, "vkCreateRenderPass"))' in vd, 'NR-GMEM: driver side (TU_DEBUG, self-dependencies)'
    assert 'if(dm_vk_pass_end_sysmem)dm_vk_pass_end_sysmem(cmd);' in rd('android/vulkan_present.cpp'), 'NR-GMEM: the present pass stays in sysmem'
    assert (root / 'gfx/vulkan/engine/tests/nr_gmem_test.c').is_file(), 'NR-GMEM: the host test exists'
    print('PASS: NR-GMEM: nr_gmem.h pure C; the pgm funnel right after nbmt (create / begin / end of the unit), barrier before the end only when applied (Turnip + driver side), '
          '=0 records nothing; hooks in init / report / both draw paths / storage / depth reads; vk_driver TU_DEBUG gmem + self-dependencies; present pass sysmem')

def nrtcount_check():
    # [DOS2] NR-TCOUNT DM_NR_TCOUNT (docs/dos2/nr/NR-TCOUNT.md): T3 / T4 / T5 counts on pgraph's sampled frames; count only, 0 = nothing
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_tcount.inc').read_text(encoding='utf-8')
    core = (root / 'gfx/nr/nr_tcount.h').read_text(encoding='utf-8')
    assert g.count('#include "../../nr/nr_tcount.h"') == 1, 'NR-TCOUNT: the analysis header is included once'
    pg = g.index('namespace pgraph{' + chr(10) + 'int mode=-1;')
    assert g.count('#include "xbg_nr_tcount.inc"') == 1 and pg < g.index('#include "xbg_nr_tcount.inc"') < g.index('int pass_prof_reserve(VkCommandBuffer cmd)'), 'NR-TCOUNT: the backend comes right after namespace pgraph'
    # the only hooks: pgraph::present (arming / analysing / the 10 s lines) and the forward declaration
    hooks = [ln.strip() for ln in g.split(chr(10)) if 'tcount::' in ln]
    pres = g[g.index('void present(uint64_t){const bool pg=on(),tc=tcount::on();'):g.index('// Per sampled image binding of a fragment shader')]
    assert len(hooks) == 4 and all(h in pres for h in hooks) and g.count('namespace tcount{bool on();bool want();void frame();void tick();}') == 1, 'NR-TCOUNT: hooks only in pgraph::present: ' + repr([h[:80] for h in hooks])
    assert 'void present(uint64_t){const bool pg=on(),tc=tcount::on();if(!pg && !tc)return;' in g, 'NR-TCOUNT: with both switches 0 present() returns at once'
    assert 'if(armed){if(cur>=0)end();if(dump_now)dump(frame-1);if(tc_now)tcount::frame();armed=false;reset();}' in g and 'if(tc)tc_now=tcount::want();' in g and 'if(dump_now || tc_now){reset();armed=true;}' in g, 'NR-TCOUNT: the armed frame is a dump, a count or both'
    assert "int v=e && *e?atoi(e):0;" in inc and 'bool on(){if(__builtin_expect(mode<0,0))init();return mode>0;}' in inc, 'NR-TCOUNT: default 0, read once'
    # count only: the backend records nothing, ends no pass, changes no state
    for bad in ('vkCmd', 'end_open_pass', 'full_barrier', 'state.', 'open_pass', 'begin_open'):
        assert bad not in inc, 'NR-TCOUNT: the backend must not touch the frame: ' + bad
    # the recorder's draw facts are taken only while pgraph is armed
    assert g.count('if(pgraph::armed)pgraph::draw();') == 1, 'NR-TCOUNT: pgraph::draw runs only on armed frames'
    d = g[g.index('void draw(){cx_sh=nullptr;if(cur<0){pend.clear();return;}PassR &r=passes[size_t(cur)];'):g.index('void dispatch(){cx_sh=nullptr;')]
    assert 'const bool vo=vw && (state.rast_discard || (!state.shader[4] && !(state.rt.depth && (state.ds.dw || state.ds.st))));' in d and 'if(r.draws==1){r.first_vsw=vw;r.first_vso=vo;}r.last_vsw=vw;r.last_vso=vo;' in d, 'NR-TCOUNT: VS-only = a pre-raster storage write that reaches no attachment'
    assert "evs.push_back({'E',cur});cur=-1;" in g and "if(ev.k=='E')continue;" in g, 'NR-TCOUNT: pass-end events; the PGRAPH dump skips them'
    code = re.sub(r'//[^' + chr(10) + r']*', '', core)
    assert 'vulkan' not in code.lower() and 'Vk' not in code and 'vk' not in code, 'NR-TCOUNT: the analysis header is pure (no Vulkan)'
    for line in ('[nr] tcount T3 DM_NR_TCOUNT=%d:', '[nr] tcount T4:', '[nr] tcount T5:', '[nr] tcount top:'):
        assert line in core, 'NR-TCOUNT: line ' + line
    assert (root / 'gfx/vulkan/engine/tests/nr_tcount_test.cpp').is_file(), 'NR-TCOUNT: the host test exists'
    print('PASS: NR-TCOUNT: header pure, backend after pgraph, hooks only in pgraph::present, default 0 read once, count only (no pass / state / '
          'command touched), draw facts on armed frames only, pass-end events skipped by the dump, four lines')

def nrlintex_check():
    # [DOS2] NR-TRAFFIC DM_NR_LINTEX (docs/dos2/nr/NR-TRAFFIC.md): pitch-linear textures re-upload the rows the tracker saw written; 0 = the old path
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    inc = (root / 'gfx/vulkan/engine/xbg_nr_lintex.inc').read_text(encoding='utf-8')
    core = (root / 'gfx/nr/nr_lintex.h').read_text(encoding='utf-8')
    assert re.findall(r'#include <(\w+)\.h>', core) == ['stdint', 'string'] and '#include "' not in core and 'Vk' not in re.sub(r'//[^' + chr(10) + r']*', '', core), 'NR-TRAFFIC: nr_lintex.h is pure C'
    assert g.count('#include "../../nr/nr_lintex.h"') == 1 and g.count('#include "xbg_nr_lintex.inc"') == 1, 'NR-TRAFFIC: core + backend included once'
    i_inc = g.index('#include "xbg_nr_lintex.inc"'); i_pe = g.index('bool partial_eligible(const Image &im,const tex_t *t){')
    assert max(g.index('struct Image {'), g.index('struct Commands {')) < i_inc < i_pe < g.index('bool partial_upload(Image &im,const tex_t *t,uint64_t since,uint64_t stamp=0){'), 'NR-TRAFFIC: the backend sits right before partial_eligible (after Image / Commands)'
    assert "const char *e=getenv(\"DM_NR_LINTEX\");mode=e && *e?atoi(e):0;" in inc and 'int mode=-1;' in inc, 'NR-TRAFFIC: default 0, read once at init'
    # every hook in the engine is behind the mode (mode -1 before init, 0 by default: none fires)
    hooks = [ln for ln in g.split(chr(10)) if 'nrlin::' in ln.split('//')[0]]
    for ln in hooks:
        assert ('nrlin::mode' in ln or 'lin_stamp' in ln or 'nrlin::init();' in ln or 'namespace nrlin{' in ln or 'nrlin::protect_stamp(t,whole)' in ln), 'NR-TRAFFIC: hook without a mode gate: ' + ln.strip()[:160]
    assert 'if(nrlin::mode==NRLT_APPLY && (t->d.flags&0x10))return nrlin::eligible(im,t);' in g and 'if(nrlin::mode==NRLT_APPLY && (t->d.flags&0x10))return nrlin::partial(im,t,since);' in g, 'NR-TRAFFIC: partial_eligible / partial_upload take pitch-linear textures only in mode 1'
    assert 'if(lin_stamp && im.lin_hold){im.dirty_stamp=0;im.stable_checks=0;im.lin_hold=false;}' in g and 'else if(lin_stamp){im.dirty_stamp=im.dirty_seen=lin_stamp;im.stable_checks=4;}' in g and 'else if(partial_eligible(im,t) && !ab_off("texdirty")' in g, 'NR-TRAFFIC: the stamp taken before the read replaces the protect-after-read'
    assert 'else if(lin_stamp && !lin_pre && !im.lin_hold){im.cpu_hash=1;' in g, 'NR-TRAFFIC: only pitch-linear textures skip the hash after the upload'
    ps = inc.split('uint64_t protect_stamp(')[1].split('struct Ctx{')[0]
    assert ps.index('if(nvn_dirty_stamp_protect){') < ps.index('const uint64_t stamp=nvn_dirty_now();') < ps.index('nvn_dirty_protect(t->mem,t->L.size);') and 'nvn_dirty_version(t->mem,t->L.size,&g,&inc)' in ps, 'NR-TRAFFIC: protect_stamp: the tracker helper, else stamp first, then protect until all read-only'
    assert 'const uint64_t stamp=protect_stamp(t,whole);' in inc.split('uint64_t full(')[1].split('staging=stream_buffer')[0], 'NR-TRAFFIC: full(): stamp + protect before the rows are read'
    assert 'if(dirty_safe() || nrlin::mode==NRLT_APPLY)stamp=nrlin::protect_stamp(t,whole);' in g and 'else{nvn_dirty_protect(t->mem,t->L.size);stamp=nvn_dirty_now();}++tex_dirty_checks;' in g, 'NR-TRAFFIC: the tracked check: the safe order by default (DM_DIRTY_PROTECT_ORDER) or in mode 1'
    assert 'if(nrlin::mode==NRLT_VERIFY && (t->d.flags&0x10))nrlin::verify(im,t);' in g and 'if(mode!=NRLT_VERIFY ||' in inc, 'NR-TRAFFIC: mode 2 verifies after the old path drew'
    v = inc.split('void verify(')[1].split('void gone(')[0]
    for bad in ('vkCmd', 'Commands', 'stream_buffer', 'pro_images', 'im.uploaded', 'cpu_hash', 'dirty_stamp'):
        assert bad not in v, 'NR-TRAFFIC: verify must not draw or change the image state: ' + bad
    assert 'if(nrlin::mode>0)nrlin::report();' in g and '[nr] lintex (DM_NR_LINTEX=%d' in inc and '[nr] DM_NR_LINTEX=%d (NR-TRAFFIC' in inc, 'NR-TRAFFIC: start line + 10-s line'
    assert (root / 'gfx/vulkan/engine/tests/nr_lintex_test.c').is_file(), 'NR-TRAFFIC: the host test exists'
    print('PASS: NR-TRAFFIC: nr_lintex.h pure C; backend before partial_eligible; DM_NR_LINTEX default 0, every hook mode-gated; mode 1 protect+stamp before the read, '
          'hash skipped only for pitch-linear; mode 2 verify draws nothing; start + 10-s lines')

def nrubwc_check():
    # [DOS2] NR-UBWC DM_NR_UBWC (docs/dos2/nr/NR-UBWC.md): the driver is asked whether attachments are compressed; =1 drops STORAGE only where it alone costs it
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    inc = rd('gfx/vulkan/engine/xbg_nr_ubwc.inc'); g = rd('gfx/vulkan/engine/xbg_game.cpp'); vp = rd('android/vulkan_present.cpp'); pol = rd('gfx/vulkan/engine/xbg_vendor_policy.h')
    h = rd('gfx/nr/nr_ubwc.h')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint'] and '#include "' not in h, 'NR-UBWC: nr_ubwc.h is pure C'
    assert 'inline int xbg_nr_ubwc_default(XbgGpuFamily){return 0;}' in pol, 'NR-UBWC: default 0 on every family'
    # the extension is enabled only from the env value, never by default
    assert 'if(const char *ue=getenv("DM_NR_UBWC");ue && *ue && atoi(ue)!=0){' in vp and vp.count('VK_EXT_IMAGE_COMPRESSION_CONTROL_EXTENSION_NAME') == 2, 'NR-UBWC: extension only with DM_NR_UBWC != 0'
    assert all('VK_STRUCTURE_TYPE_IMAGE_COMPRESSION_CONTROL_EXT' not in x for x in (g, inc, vp)), 'NR-UBWC: no image is created with a compression control'
    # every hook gated
    for hook in ('if(nrubwc::mode==1)ci.usage=nrubwc::lean(ci,nullptr);', 'if(nrubwc::mode==1){ci.usage=nrubwc::lean(ci,&p->nrubwc_def);usage=ci.usage;p->usage=usage;}',
                 'if(nrubwc::mode)nrubwc::att(im);', 'if(im.nrubwc_def && !(im.usage&VK_IMAGE_USAGE_STORAGE_BIT))nrubwc::upgrade(im);', 'nrubwc::init(gpu_policy);'):
        assert g.count(hook) == 1, 'NR-UBWC: hook ' + hook
    assert g.count('nrubwc::') == 8, 'NR-UBWC: no other use of the namespace in xbg_game.cpp (%d)' % g.count('nrubwc::')
    le = inc[inc.index('VkImageUsageFlags lean('):inc.index('void upgrade(')]
    assert "if(mode!=1 || !(ci.usage&VK_IMAGE_USAGE_STORAGE_BIT) || ci.imageType!=VK_IMAGE_TYPE_2D || !(ci.usage&VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT))return ci.usage;" in le, 'NR-UBWC: only 2D colour attachment-capable images at =1'
    assert "would(ci.format,ci.imageType,ci.tiling,ci.usage,ci.flags)==2 && would(ci.format,ci.imageType,ci.tiling,u2,ci.flags)==1" in le, 'NR-UBWC: dropped only when the driver says STORAGE alone costs compression'
    um = g[g.index('void upgrade_mutable(Image &im,VkFormat want,VkImageUsageFlags add_usage){'):g.index('struct DescMemo{')]
    assert 'if(!usage_only)ci.flags|=VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT;ci.usage|=add_usage;' in um and 'else if(!usage_only)im.view_formats.clear();' in um and 'if(!usage_only)im.mutable_format=true;im.usage|=add_usage;' in um, \
        'NR-UBWC: the storage upgrade reuses upgrade_mutable without touching flags / format list'
    assert (root / 'gfx/vulkan/engine/tests/nr_ubwc_test.c').is_file(), 'NR-UBWC: host test exists'
    print('PASS: NR-UBWC: nr_ubwc.h pure C; default 0; extension only with DM_NR_UBWC != 0, no compression control on any image; 5 gated hooks; '
          '=1 drops STORAGE only on 2D colour images when the driver says it alone costs compression; storage upgrade = upgrade_mutable usage-only')

def dirtyorder_check():
    # [DOS2] NR-TRAFFIC round 2 (port-common/dirty-order): stamp -> protect until all read-only -> read on every tracked path; DM_DIRTY_PROTECT_ORDER=0 = old orders
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    c = rd('gfx/nvn/nvn_dirty.c'); h = rd('gfx/nvn/nvn_dirty.h'); g = rd('gfx/vulkan/engine/xbg_game.cpp'); nb = rd('gfx/vulkan/engine/xbg_nr_buf.inc')
    f = c.split('uint64_t nvn_dirty_stamp_protect(')[1].split('void nvn_dirty_order_stats(')[0]
    assert f.index('const uint64_t stamp = atomic_load(&g_now);') < f.index('nvn_dirty_protect(addr, len);') < f.index('all_prot(r, p, q, &sticky)'), 'dirty-order: stamp first, protect, all read-only'
    assert 'v = e && *e ? atoi(e) != 0 : 1;' in c and 'DM_DIRTY_PROTECT_ORDER' in c, 'dirty-order: default 1'
    assert 'uint64_t nvn_dirty_stamp_protect(const void *addr, size_t len, int *whole);' in h and 'int nvn_dirty_safe_order(void);' in h, 'dirty-order: header'
    assert 'inline bool dirty_safe(){static int v=-1;if(v<0)v=nvn_dirty_stamp_protect && nvn_dirty_safe_order && nvn_dirty_safe_order()?1:0;return v!=0;}' in g, 'dirty-order: engine gate (weak symbols)'
    # every nvn_dirty_protect of the engine that precedes a read of tracked bytes is either the old-order branch of a dirty_safe() test or the helper
    for site in ('if(dirty_safe())stamp=nvn_dirty_stamp_protect(p,bytes,&whole);else{stamp=nvn_dirty_now();nvn_dirty_protect(p,bytes);}',   # vcache
                 'if(dirty_safe()){int w=1;stamp=nvn_dirty_stamp_protect(t->mem,t->L.size,&w);if(!w)track=false;}',                       # untracked -> tracked
                 'if(dirty_safe() || nrlin::mode==NRLT_APPLY)stamp=nrlin::protect_stamp(t,whole);',                                       # tracked check
                 'if((dirty_safe() || nrlin::mode==NRLT_APPLY) && !(t->d.flags&0x10) && partial_eligible(im,t)'):                          # upload: protect before the read
        assert site in g, 'dirty-order: site ' + site[:60]
    assert 'if(dirty_safe())stamp=nvn_dirty_stamp_protect(p,size_t(bytes),&whole);' in nb and 'if(tracked && !whole){' in nb, 'dirty-order: NR-06 static copies (demoted when never read-only)'
    assert 'if(!whole)stamp=im.dirty_stamp;' in g and 'if(!whole){f.state=VOLATILE;' in g, 'dirty-order: never wholly read-only -> old stamp kept / not cached'
    assert (root / 'gfx/tests/t_dirty_order.c').is_file(), 'dirty-order: the real-tracker test exists'
    print('PASS: dirty-order: nvn_dirty_stamp_protect stamps first and protects until all read-only; default 1; vcache / untracked->tracked / tracked check / upload / NR-06 use it, '
          'old order only under DM_DIRTY_PROTECT_ORDER=0; not-whole copies keep the old stamp / are not cached / are demoted')


def nrarena_check():
    # [DOS2] NR-TRAFFIC round 2 DM_NR_ARENA (docs/dos2/nr/NR-TRAFFIC.md §10): stream-arena chunks kept per slot; 0 = the old rule
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    g = rd('gfx/vulkan/engine/xbg_game.cpp'); h = rd('gfx/nr/nr_arena.h'); m = rd('gfx/vulkan/engine/xbg_nr_mem.inc')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint'] and '#include "' not in h, 'NR-ARENA: nr_arena.h is pure C'
    assert g.count('#include "../../nr/nr_arena.h"') == 1, 'NR-ARENA: header once'
    assert "const char *e=getenv(\"DM_NR_ARENA\");mode=e && *e?atoi(e):0;" in g and 'if(mode<0)init();if(mode<=0)return 0;' in g, 'NR-ARENA: default 0 = limit 0 = the old rule'
    assert 'const size_t lim=limit?limit:std::max<size_t>(keep_chunks,6);' in g, 'NR-ARENA: trim(0) is the old rule'
    assert g.count('s.stream.trim(narena::keep(s.stream));') == 1 and 'regrown+=rg;if(mode==2)return 0;' in g, 'NR-ARENA: one call site; mode 2 counts only'
    assert 'void reset(){used_chunks_last=used_total?uint32_t(current+1):0;' in g, 'NR-ARENA: the need is taken at reset (chunks touched)'
    assert 'if(narena::mode>0)narena::trim_gen.fetch_add(1);' in m, 'NR-ARENA: NR-29 trims shrink it'
    assert (root / 'gfx/vulkan/engine/tests/nr_arena_test.c').is_file(), 'NR-ARENA: host test'
    print('PASS: NR-ARENA: nr_arena.h pure C; DM_NR_ARENA default 0 (old rule), one call site at the slot retire, mode 2 counts only, NR-29 trim hook')


def nrs2f_check():
    # [DOS2] NR-FRAME S2F (docs/dos2/nr/NR-FRAME.md §10): the Fog tail of NR-ONCHIP's M (Sky -> Light -> Fog), only with DM_NR_ONCHIP > 0
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    h = rd('gfx/nb/nb_onchip.h'); inc = rd('gfx/vulkan/engine/xbg_nr_onchip.inc'); fe = rd('host/hle_dos2_nb.c'); tap = rd('gfx/nvn/nvn_nb_tap.inc')
    pk = (root.parent / 'tools' / 'dos2_nr_sh_pack.py').read_text(encoding='utf-8'); st = (root.parent / 'tools' / 'setup_dos2.py').read_text(encoding='utf-8')
    # planner: the tail only with allow bit 2; the front end asks for it only when the backend published it
    assert "if (allow & 4u) {" in h and "const unsigned allow = r && r->allow ? r->allow : 3u;" in h, 'S2F: tail planned only with allow bit 2 (0 = S2 / S3 as before)'
    assert "__atomic_load_n(&g_nr_oc_fog, __ATOMIC_RELAXED) > 0 ? 7u : 0u" in fe and 'void dm_nr_onchip_publish_fog(int on)' in fe, 'S2F: the front end plans tails only when the backend asks'
    assert 'if(dm_nr_onchip_publish_fog)dm_nr_onchip_publish_fog(fog_on?1:0);' in inc, 'S2F: the backend publishes whether it understands tails'
    fo = inc[inc.index('void init(){'):inc.index('uint32_t bpp(')]
    assert "fog_on=m>0 && !(fge && *fge && atoi(fge)==0) && !lightfuse;" in fo and 'const bool lightfuse=nrlf::mode!=0;' in fo, 'S2F: off with DM_NR_ONCHIP 0, DM_NR_ONCHIP_FOG=0 or DM_NR_LIGHTFUSE (that one wins)'
    # the tap writes c0 into the last attachment slot of a tail Sky header only
    assert "if (nb_oc_tail(np->oc) && nb_oc_role(np->oc) == NB_OCR_SKY && r->natt < NB_REC_ATT) r->att[NB_REC_ATT - 1] = nb_oc_tail_image(f, po, i);" in tap, 'S2F: tap hand-over of c0'
    # backend: a tail that cannot run falls back to plain S2; Fog's NEXT without the tail ends M; input bindings by image; c0 clear in subpass 2
    bg = inc[inc.index('bool begin(Pass &p,Commands &c,const p_nb_pass &hd){'):inc.index('void note_pass(')]
    assert "if(fog_on && nb_oc_tail(hd.oc)){++s.tails;const int tw=tail_ok(p,hd,ci,v[2],f[2]);if(tw)++s.tail_refused[tw];else tl=true;}" in bg, 'S2F: tail begin gated'
    assert "if(!r && tl){++s.refused[R_RP];tl=false;r=get_rp(f[0],f[1],ld[0],ld[1]);}" in bg, 'S2F: no 3-subpass render pass -> plain S2'
    ad = inc[inc.index('bool adjust(Pass &p,Commands &c){'):inc.index('void tick(){')]
    assert "if(r.k==1 && !tail){brk(B_OTHER);return true;}" in ad and "if(input_bad){brk(B_INPUT);return false;}" in ad, 'S2F: Fog without the tail ends M; a wrong input image skips the draw'
    assert "vkCmdClearAttachments(c.command,1,&a,1,&rc);pclears.erase(" in ad and "open_pass.images.push_back(c0);" in ad, 'S2F: the c0 ClearTexture as a subpass-2 clear; c0 joins the open pass'
    iv = inc[inc.index('VkImageView input_view('):inc.index('Rp *get_rp(')]
    assert "if(&im==sp)return sp_view;if(tail && &im==c0)return c0_view;if(tail && &im==df)return df_view;" in iv, 'S2F: input views by image'
    assert "{\"ClusteredLightingWithSSAO\",'5',2,{28,52},{3,6}},{\"DeferredFog\",'5',1,{16,0},{1,0}}" in inc, 'S2F: twin input tables'
    # pack: the S2F variants optional (a failure leaves them out), setup accepts packs with or without them
    assert "OC_OPTIONAL = {'ClusteredLightingWithSSAO': [('5', 0x48)], 'DeferredFog': [('5', 0x02)]}" in pk and "if not optional: raise" in pk, 'S2F: optional pack variants'
    assert "if sorted(k for k in have if k not in optional) != want: raise Fail(" in st, 'S2F: setup accepts the pack with or without the optional variants'
    assert (root / 'gfx/vulkan/engine/tests/nrpack_optional_test.py').is_file(), 'S2F: the setup rule test exists'
    print('PASS: NR-FRAME S2F: tail planned only with allow bit 2 when the backend publishes it (DM_NR_ONCHIP > 0, DM_NR_ONCHIP_FOG, DM_NR_LIGHTFUSE wins); tap hands c0 over; '
          'fallbacks to S2; inputs by image; c0 clear in subpass 2; pack variants optional, setup accepts both')

def nrframe_check():
    # [DOS2] NR-FRAME DM_NR_COVER_FMASK (docs/dos2/nr/NR-FRAME.md): NR-10b's write-mask test knows the format's components; only under DM_NR_COVER
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    h = rd('gfx/nr/nr_frame.h'); inc = rd('gfx/vulkan/engine/xbg_nr_cover.inc'); g = rd('gfx/vulkan/engine/xbg_game.cpp'); vp = rd('gfx/vulkan/engine/xbg_vendor_policy.h')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint'] and '#include "' not in h, 'NR-FRAME: nr_frame.h is pure C'
    assert g.count('#include "../../nr/nr_frame.h"') == 1 and g.index('#include "../../nr/nr_frame.h"') < g.index('#include "xbg_nr_cover.inc"'), 'NR-FRAME: header included once, before the cover backend'
    d = inc[inc.index('Dec decide('):inc.index('bool at_begin(')]
    # the only change of the proof: a mask short of 0xF passes only through nr_fr_mask_full, and only with use_fmask; blend / outputs / 3D target unchanged
    assert "if(!(fs->raster.outputs>>i&1) || (state.color.blend_en>>i&1) || state.rt.color[i]->d.target==2){d.why=W_ATTACH;return d;}" in d, 'NR-FRAME: outputs / blend / 3D target refused as before'
    assert "if(m4!=15){if(!use_fmask || !nr_fr_mask_full(m4,slot_components(p,i))){d.why=W_ATTACH;return d;}fm_used=true;}" in d, 'NR-FRAME: the format rule, gated'
    assert d.count('nr_fr_mask_full') == 1 and inc.count('use_fmask=atoi(m)!=0;') == 1 and 'bool use_fmask=true;' in inc, 'NR-FRAME: DM_NR_COVER_FMASK (default 1 inside DM_NR_COVER)'
    sc = inc[inc.index('unsigned slot_components('):inc.index('void twin_failed()')]
    assert 'return found && c?c:4;' in sc and 'else c=4;' in sc, 'NR-FRAME: unknown attachment format / no render-pass info = 4 components (needs 0xF)'
    # the proof itself runs only under DM_NR_COVER, whose default stays 0 on every family
    assert 'inline int xbg_nr_cover_default(XbgGpuFamily){return 0;}' in vp, 'NR-FRAME: DM_NR_COVER default unchanged (0 everywhere)'
    assert (root / 'gfx/vulkan/engine/tests/nr_frame_test.c').is_file(), 'NR-FRAME: the host test exists'
    # DM_GFX_PASS_GMEM_M: NR-ONCHIP's M (exactly 2 subpasses) may pass NR-GMEM's "other" veto; off unless the env says 1
    gh = rd('gfx/nr/nr_gmem.h'); pg = rd('gfx/vulkan/engine/xbg_pass_gmem.inc')
    assert 'if ((p->subpasses != 1 && !(c->sub2 && (p->subpasses == 2 || p->subpasses == 3))) || p->layers > 1) return NRGM_W_OTHER;' in gh, 'NR-FRAME: the M exception of the GMEM veto (S2 / S2F)'
    assert 'nrgm_cfg c = {1u, 5u, 3u, 600000u, 0, 0}; return c;' in gh and 'cfg.sub2 = env_u("DM_GFX_PASS_GMEM_M", 0) == 1u;' in pg, 'NR-FRAME: DM_GFX_PASS_GMEM_M default 0'
    print('PASS: NR-FRAME: nr_frame.h pure C; NR-10b mask test = 0xF or (DM_NR_COVER_FMASK and every component of the format), unknown = 4; '
          'outputs / blend / 3D target unchanged; DM_NR_COVER default 0 everywhere; DM_GFX_PASS_GMEM_M (M through the GMEM veto) default 0')


def nrhacks_check():   # [DOS2] N6 DM_HACK_* (docs/dos2/nr/NR-HACKS.md): lossy speed settings, every one 0 = today
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    h = rd('gfx/nr/nr_hacks.h'); g = rd('gfx/vulkan/engine/xbg_game.cpp'); inc = rd('gfx/vulkan/engine/xbg_nr_hacks.inc'); sh = rd('gfx/vulkan/engine/xbg_nr_sh.inc')
    q = rd('host/hle_dos2_quality.c'); j = rd('android/app/src/main/java/com/xiaoboluo/d2r/Tl2Gear.java')
    frag = (root.parent / 'tools/dos2_post/PPFXAA_fsr.frag').read_text(encoding='utf-8'); mob = (root.parent / 'tools/dos2_post/PPFXAA_mobile.frag').read_text(encoding='utf-8')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint', 'stdlib', 'string'] and '#include "' not in h, 'N6: nr_hacks.h is pure C'
    # the tier table: C (nr_hacks.h) == Java (Tl2Gear.HACK_TIERS), names in the same order; tier 0 all zero
    ct = re.search(r'nrh_tier_table\[4\]\[NRH_N\] = \{(.*?)\n\};', h, re.S).group(1)
    crow = [list(map(int, re.findall(r'-?\d+', r))) for r in re.findall(r'\{([^{}]*)\}', ct)]
    jt = re.search(r'HACK_TIERS = \{(.*?)\n    \};', j, re.S).group(1)
    jrow = [list(map(int, re.findall(r'-?\d+', r))) for r in re.findall(r'\{([^{}]*)\}', jt)]
    assert crow == jrow and len(crow) == 4 and crow[0] == [0] * len(crow[1]), 'N6: tier tables differ (nr_hacks.h vs Tl2Gear.HACK_TIERS): %s / %s' % (crow, jrow)
    cn = re.findall(r'"(\w+)"', re.search(r'nrh_names\[NRH_N\] = \{([^}]*)\}', h).group(1))
    jn = re.findall(r'"(\w+)"', re.search(r'HACK_NAMES = \{([^}]*)\}', j).group(1))
    assert cn == jn, 'N6: hack names differ: %s / %s' % (cn, jn)
    assert 'if (t <= 0 || t > 4) return;   // off: nothing set' in j, 'N6: the gear sets nothing when the hacks are off'
    # backend hooks: one load each when off
    assert g.count('#include "xbg_nr_hacks.inc"') == 1 and g.index('#include "xbg_nr_shc.inc"') < g.index('#include "xbg_nr_hacks.inc"') < g.index('void draw(int prim,int first,int count,'), 'N6: the include before draw()'
    d0 = g.index('void draw(int prim,int first,int count,'); first = g[d0:g.index('\n', g.index('\n', d0) + 1)]
    assert 'if(__builtin_expect(nrhack::shfar!=0,0) && !nbpost::inside){if(nrhack::shfar<0)nrhack::init();if(nrhack::shfar>0 && nrhack::far_draw()){' in first, 'N6: the far-cascade hook is the first line of draw()'
    assert 'if(__builtin_expect((nrhack::texbias|nrhack::aniso)!=0,0)){const samp_par hp=nrhack::par(input,im);return sampler_game(hp,im,viewed,integer_border);}' in g, 'N6: sampler hook'
    assert 'return shfar==1;}' in inc and 'if(!im.uploaded || im.gpu_written || im.levels<2)return p;' in inc, 'N6: =2 counts only; only uploaded mipmapped textures are biased'
    assert g.count('nrhack::tick();') == 1, 'N6: the 10 s line at present'
    # FSR: the PPFXAA entry only, DM_NR_SH=1 only, the translated head kept, the 1:1 path = PPFXAA_mobile word for word
    assert 'if((fsr || lights) && hacks(i,key,bytes))return true;' in sh and 'if(mode!=1 || !nr_sh_enabled(i))return false;' in sh, 'N6: hack modules only with DM_NR_SH=1'
    assert 'if(fsr && !strcmp(n,"PPFXAA"))' in sh and 'if(lights && !strcmp(n,"ClusteredLightingWithSSAO"))' in sh, 'N6: FSR on PPFXAA, the light cap on the lighting pass only'
    assert 'std::vector<uint8_t> nb(bytes.begin(),bytes.begin()+th);' in sh and 'if(!use)return false;' in sh and 'fsr==1)' in sh, 'N6: hack modules keep the translated head; FSR=2 checks only'
    lf = (root.parent / 'tools/dos2_post/ClusteredLightingWithSSAO_mobile.frag').read_text(encoding='utf-8')
    lc = (root.parent / 'tools/dos2_light_cap.py').read_text(encoding='utf-8')
    assert 'LCAP' not in lf and 'lit < uint(LCAP)' in lc and 'p = p0 + npo;' in lc, 'N6: the light cap is a build-time text patch (the *_mobile.frag sources feed setup stage 8 stamps)'
    assert 'OpDPdx' not in (root.parent / 'tools/spv_interp.py').read_text(encoding='utf-8'), 'N6: derivatives live in tools/dos2_post_fsr.py (spv_interp.py feeds the post-pack stamp)'
    for f in ('ppfxaa_fsrh', 'light_lcap2', 'light_lcap4'):
        assert '0x07230203,' in rd('android/shaders/%s.frag.spv.inc' % f).split(chr(10))[1], 'N6: SPIR-V of ' + f
    q2 = rd('host/hle_dos2_quality.c')
    assert 'if (hv[NRH_LOD] > 0) dq_lod_install(m, hv[NRH_LOD]);' in q2 and 'static int dq_lod_word_ok(const uint8_t *at)' in q2, 'N6: LOD caves only when set, every site word-checked'
    body = lambda s, start, end: s[s.index(start):s.index(end, s.index(start))]
    fb = body(frag, '    float u = TexCoord0.x, v = TexCoord0.y;', '\n}').replace('return vec4(cm, 1.0);', 'outColor = vec4(cm, 1.0); return;').replace('    return vec4(textureLod(tSrc, nanz(vec2(uf, vf)), 0.0).rgb, 1.0);', '    outColor = vec4(textureLod(tSrc, nanz(vec2(uf, vf)), 0.0).rgb, 1.0);')
    mb = body(mob, '    float u = TexCoord0.x, v = TexCoord0.y;', '\n}')
    assert fb == mb, 'N6: the 1:1 path of PPFXAA_fsr.frag is PPFXAA_mobile.frag'
    spv = rd('android/shaders/ppfxaa_fsr.frag.spv.inc')
    assert '0x07230203,' in spv.split('\n')[1], 'N6: SPIR-V of PPFXAA_fsr.frag'
    # HLE half: every hack 0 = nothing; an explicit DM_DOS2_* knob wins
    assert 'if ((!se || !*se) && hv[NRH_SHADOWS] == 1)' in q and 'if ((!ae || !*ae) && hv[NRH_NOAA] == 1)' in q and 'if (hv[NRH_SCALE] > 0) {' in q, 'N6: HLE hacks only when set'
    assert (root / 'gfx/vulkan/engine/tests/nr_hacks_test.c').is_file(), 'N6: the host test exists'
    print('PASS: N6 hacks: nr_hacks.h pure C, tier table and names C == Java, gear sets nothing when off; far-cascade hook first in draw(), sampler hook, '
          '10 s line; FSR (half / fp32) on PPFXAA and the light cap on the lighting pass only, with the translated head, only under DM_NR_SH=1; 1:1 path = PPFXAA_mobile; LCAP-only code; LOD caves word-checked; HLE hacks only when set')

def nrdrift_check():   # [DOS2] NR-DRIFT (docs/dos2/nr/NR-DRIFT.md): the "[nr] growth" line, the GPU clock probe, DM_DOS2_DRS_SETTLE
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    h = rd('gfx/nr/nr_drift.h'); inc = rd('gfx/vulkan/engine/xbg_nr_growth.inc'); g = rd('gfx/vulkan/engine/xbg_game.cpp'); q = rd('host/hle_dos2_quality.c')
    assert re.findall(r'#include <(\w+)\.h>', h) == ['stdint'] and '#include "' not in h, 'NR-DRIFT: nr_drift.h is pure C'
    code = re.sub(r'//[^' + chr(10) + r']*', '', h)
    assert 'Vk' not in code and 'vk' not in code, 'NR-DRIFT: the policy header has no Vulkan'
    # the backend: one forward declaration, the hooks, the include inside the unnamed namespace (after every container it reads)
    assert g.count('namespace nrgrowth{void slot_begin(VkCommandBuffer cmd);void window(double draws_per_frame,uint64_t now);void shutdown();extern uint64_t retire_ns,retire_n;}') == 1, 'NR-DRIFT: forward declaration'
    assert g.count('nrgrowth::slot_begin(s.cmd);') == 1 and g.index('if(nrocc::mode>0)nrocc::slot_begin(s);') < g.index('nrgrowth::slot_begin(s.cmd);') < g.index('Slot &recording_slot(){') + 20000, 'NR-DRIFT: the probe item after the slot-begin ordering barrier'
    rs = g[g.index('Slot &recording_slot(){'):g.index('// Submit the recording slot.')]
    assert rs.index('vkCmdPipelineBarrier(s.cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT') < rs.index('nrgrowth::slot_begin(s.cmd);'), 'NR-DRIFT: after the ordering barrier (outside any render pass)'
    assert g.count('nrgrowth::window(double(perf.draws)/f,now);') == 1 and 'perf_draws.store(double(perf.draws)/f);' in g, 'NR-DRIFT: the perf report feeds the load tracker and the line'
    assert 'extern "C" double xbg_recent_draws(void){return perf_draws.load();}' in g, 'NR-DRIFT: draws a frame for the DRS monitor'
    assert 'nrgrowth::retire_ns+=c5-c0;++nrgrowth::retire_n;' in g, 'NR-DRIFT: the retire cleanup walk is timed'
    assert g.count('nrgrowth::shutdown();') == 1, 'NR-DRIFT: probe objects destroyed at shutdown'
    i_inc = g.index('#include "xbg_nr_growth.inc"'); i_end = g.index('} // namespace', g.index('PerfCounts perf_counts(){'))
    assert g.index('PerfCounts perf_counts(){') < i_inc < i_end, 'NR-DRIFT: the .inc inside the unnamed namespace, after the containers'
    assert g.count('#include "xbg_nr_probe_spv.h"') == 1 and g.count('#include "../../nr/nr_drift.h"') == 1, 'NR-DRIFT: includes'
    # the .inc: off = nothing; the probe only in slot_begin, its own pool / buffers, a barrier after each item
    assert 'if(mode<0)init();if(probe_mode<=0)return;' in inc and 'if(mode<0)init();if(mode<=0)return;' in inc, 'NR-DRIFT: DM_NR_GROWTH=0 / DM_NR_GPUPROBE=0 do nothing'
    assert '#ifdef DM_GAME_DOS2\n    mode=1;\n#else\n    mode=0;\n#endif' in inc, 'NR-DRIFT: default on for DOS2 only'
    sb = inc[inc.index('void slot_begin(VkCommandBuffer cmd){'):inc.index('// ---- sysfs clocks ----')]
    assert sb.count('vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT') == 2 and sb.count('vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,qp,') == 4, 'NR-DRIFT: 4 own stamps, a barrier after each item'
    assert 'next_probe=now+period_ns/2;' in sb and 'if(now<next_probe)return;' in sb, 'NR-DRIFT: at most one item a half period'
    assert 'VK_QUERY_RESULT_WAIT_BIT' not in inc and 'vkDeviceWaitIdle' not in inc and 'vkQueueWaitIdle' not in inc, 'NR-DRIFT: never waits for the GPU'
    assert '[nr] growth (%.0f s, frame %llu, %s, loads %u, level %s): sizes' in inc and '; since load' in inc and '; walks retire cleanup' in inc and '; gpu alu' in inc and '; cost %.0f us' in inc, 'NR-DRIFT: the line'
    # the DRS monitor: default 0, the published target = the held one only while holding, the controller page untouched otherwise
    assert 'const char *se = getenv("DM_DOS2_DRS_SETTLE"); int sm = se && *se ? atoi(se) : 0;' in q, 'NR-DRIFT: DM_DOS2_DRS_SETTLE default 0'
    assert 'static void dq_set_target(float ms) { g_tq[1] = ms * 30.0f / 31.5f; g_tq[0] = ms; dq_publish(); }' in q and 'const float t = g_hold ? 100.0f : g_tq[0], h = g_hold ? 100.0f * 30.0f / 31.5f : g_tq[1];' in q, 'NR-DRIFT: publish = held or normal'
    assert q.count('g_q[0] =') == 0 or 'g_tq[0] = g_q[0] = 31.5f;' in q, 'NR-DRIFT: no direct target writes left'
    assert 'if (hold != g_hold && g_tgt_mode) { g_hold = hold; dq_publish(); }' in q and 'if (g_settle.mode) {' in q, 'NR-DRIFT: the monitor applies the hold only with the switch'
    assert 'int dm_dos2_drs_info(float *pct, int *hold, float *target_ms) {' in q, 'NR-DRIFT: the DRS state for the growth line'
    assert (root / 'gfx/vulkan/engine/tests/nr_drift_test.c').is_file() and (root / 'gfx/vulkan/engine/xbg_nr_probe.comp').is_file(), 'NR-DRIFT: host test and probe source exist'
    # DM_DOS2_DRS_SPIKE: default 0, the site words checked before the jump goes in, the cave from nr_drift.h (Unicorn-tested)
    assert 'const char *sp = getenv("DM_DOS2_DRS_SPIKE"); int sm = sp && *sp ? atoi(sp) : 0;' in q, 'NR-DRIFT: DM_DOS2_DRS_SPIKE default 0'
    si = q[q.index('static int dq_spike_install(module_t *m, uint32_t mode) {'):q.index('void dm_dos2_quality_install(void);   // main.c host_preload')]
    assert si.index('memcmp(m->base + NRD_SPIKE_SITE, nrd_spike_orig, sizeof nrd_spike_orig)') < si.index('dq_poke(m, NRD_SPIKE_SITE, j, 4)'), 'NR-DRIFT: spike site checked word for word first'
    assert 'memcpy(c, nrd_spike_cave, sizeof nrd_spike_cave);' in si and 'nrd_spike_init((uint32_t *)g_q, mode);' in si, 'NR-DRIFT: the cave and its page from nr_drift.h'
    assert (root / 'gfx/vulkan/engine/tests/nr_drift_cave_test.py').is_file(), 'NR-DRIFT: the Unicorn test of the cave exists'
    print('PASS: NR-DRIFT: nr_drift.h pure C; growth .inc inside the unnamed namespace after the containers; probe after the slot-begin barrier, own 4 stamps, '
          'a barrier after each item, one item a half period, never waits; DOS2 default on, 0 = nothing; DM_DOS2_DRS_SETTLE default 0, publish held / normal; DM_DOS2_DRS_SPIKE default 0, site checked, cave from nr_drift.h')


def inputatt_check():   # [DOS2] NR-ONCHIP on the phone 19.11: S2F light.s2 reads Sky through an input attachment (SPIR-V capability 40);
    # the capability validator aborted on it ("Shader stage 4 has unhandled capability 40") - fragment stage only
    g = (root / 'gfx/vulkan/engine/xbg_game.cpp').read_text(encoding='utf-8')
    assert 'case 40:ok=stage==4;break;' in g, 'InputAttachment (40) allowed in the fragment stage'

def ports1119_check():   # [DOS2] NR-DRIFT round 2 omissions audit (NR-DRIFT.md section 9): SH-20 Adreno 8xx policy, PERF-E01 SYNC_XWAIT
    rd = lambda p: (root / p).read_text(encoding='utf-8')
    g = rd('gfx/vulkan/engine/xbg_game.cpp'); ap = rd('gfx/vulkan/engine/xbg_adreno_policy.h'); n = rd('gfx/nvn/hle_nvn.c')
    assert 'inline bool xbg_adreno8_policy(uint32_t vendor_id,const char *device_name,const char *environment){' in ap, 'SH-20: policy in xbg_adreno_policy.h'
    assert 'if(!a8e || !*a8e)a8e="0";' in g and 'return xbg_adreno_rewrite_option(present,c,getenv(env),rewrites_fault || adreno8_on);' in g, 'SH-20: DOS2 opt-in, folded into the rewrite switches'
    sw = n[n.index('NVN(nvnSyncWait, NVNsyncWaitResult, const NVNsync *s, uint64_t timeout) {'):]
    sw = sw[:sw.index('#ifdef __OHOS__')]
    assert 'if (timeout && !x_sub_translated(o->fence)) {' in sw and 'if (sx == 1) {' in sw, 'PERF-E01: the timed-wait block, the wait only in mode 1'
    assert '#define DM_NVN_SYNC_XWAIT_DEFAULT 2' in n and 'static int x_sub_translated(uint64_t sub) { if (g_x_sync) return 1;' in n, 'PERF-E01: DOS2 default 2 (count), the translated check'
    print('PASS: ports 19.11: SH-20 Adreno 8xx policy (DOS2 opt-in), PERF-E01 DM_NVN_SYNC_XWAIT (DOS2 default 2 = count only, 1 = wait)')



nr20_check()
nr27_check()
nr32_check()
nr_idvs_check()
nr23_check()
nr24_check()
nr28_check()
nr13_check()
nr29_check()
nr30_check()
nr31_check()
nr09r_check()
nr09s_check()
nr09s3_check()
nr09u_check()
nrubd_check()
nrcpu_check()
nrtrx_check()
nrheat_check()
nr33b_check()
nr33c_check()
nronchip_check()
nrlightfuse_check()
safemode_check()
nrshc_check()
nrzero_check()
nrz3_check()
nrz3e_check()
nrz5_check()
nrmdi_check()
nrposonly_check()
nrpreskin_check()
nrgmem_check()
nrtcount_check()
nrlintex_check()
dirtyorder_check()
nrarena_check()
nrframe_check()
nrs2f_check()
nrhacks_check()
nrdrift_check()
nrubwc_check()
ports1119_check()
inputatt_check()
_bad=delimiter_gate()
assert not _bad,_bad
