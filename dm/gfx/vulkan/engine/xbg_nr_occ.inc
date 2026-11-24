// [DOS2] NR-03 DM_NR_OCC: native conditional rendering (docs/dos2/nr/NR-03.md; decision core dm/gfx/nr/nr_occ.h, host test
// tests/nr_occ_test.c). Included by xbg_game.cpp right before draw(); the hooks are declared at the condr forward declarations and are
// single lines (tests/source_structure_test.py block NR-03 keeps them in place).
//
// The game's occlusion test is a pair ReportCounter(SAMPLES_PASSED, a) / ReportCounter(a + 16) around the object's own pre-pass draw and,
// later in the same frame, SetRenderEnableConditional(RENDER_IF_NOT_EQUAL, a) around its real draws (nr_occ.h header). Until now the host
// drew every conditional draw ("SetRenderEnableConditional mode 1: the host draws unconditionally"), and DM_GFX_COND_RENDER emulates the
// whole counter (samples counted from the start, every draw in a query run, reports into guest memory, then judged by guest memory).
// Here the pair is one Vulkan occlusion query (non-precise: only "any sample" matters), nothing is written into the game's memory.
//
//   DM_NR_OCC        0  off (default): no record, no query, no allocation; streams and pictures byte for byte as before
//                    1  on: GPU path = VK_EXT_conditional_rendering on the pair's result, copied into a predicate word at the end of the
//                       pass that closed the pair; PREV path = the host skips the draw when its object was hidden in the last retired
//                       frames (nr_occ.h nro_prev_cull); both: a pair without draws is judged on the CPU (exact). The old samples
//                       reports (timestamps, pending reports, guest writes) are dropped unless DM_NR_OCC_DROP=0.
//                    2  check: queries + decisions of every path, every draw made (old picture); at retire the decisions are compared with
//                       the same-frame truth (= what the Switch culls): one run says how many draws / vertices the Switch culls, how many
//                       the GPU path would cull (and lose to same-pass consumers), how many the prev path would cull right / wrong.
//                    3  poison: as 1 with every decision inverted (GPU: INVERTED predicate; prev / exact: skip what renders): what the
//                       Switch draws disappears - shows on screen that the conditions reach the draws.
//   DM_NR_OCC_PATH   gpu | prev | auto (default auto = xbg_vendor_policy.h xbg_nr_occ_path_default: GPU on Adreno / Xclipse / other,
//                    PREV on the tilers Mali / PowerVR / Maleoon); gpu without the extension falls back to prev.
//   DM_NR_OCC_N      hidden frames a key needs before the prev path culls it (1..60, default 2)
//   DM_NR_OCC_STILL  1 (default): prev culls only when the vertex constants equal the last retired frame's (object + camera still); 0 = any
//   DM_NR_OCC_DROP   with 1 / 3: 1 (default) drop the old samples-report work, 0 keep it (A/B)
// Line "[nr] occ ..." every 10 s while frames come; red lines: prev-path false culls (=1: drawn late on screen; =2: would be), first 16.
// DM_GFX_COND_RENDER != 0 wins (the two would both own occlusion queries): DM_NR_OCC is then off, logged.
#include "../../nr/nr_occ.h"
namespace nrocc{
int mode=-1,path=NRO_PATH_AUTO,still=1;unsigned hold=2;bool drop=true,gpu_ok=false;
nro_slot *ss[MAX_SLOTS]{};nro_hist *hist=nullptr;
VkQueryPool pool[MAX_SLOTS]{};uint32_t reset_n[MAX_SLOTS]{},copied[MAX_SLOTS]{};
VkBuffer pbuf=VK_NULL_HANDLE;VkDeviceMemory pmem=VK_NULL_HANDLE;uint32_t *pmap=nullptr;   // words: slot k at [k * NRO_MAX_Q], then the constants 0 / 1
PFN_vkCmdBeginConditionalRenderingEXT pbegin=nullptr;PFN_vkCmdEndConditionalRenderingEXT pend=nullptr;
// The condition in force (NVN command-buffer state): kind, decision, predicate word, the pair it names.
enum{D_RENDER=0,D_SKIP=1,D_GPU=2};
int kind=CONDR_K_ON,nvn=NRO_NVN_IF_NOT_EQUAL,dec=D_RENDER,cslot=-1;uint32_t poff=0;bool pinv=false;int32_t cpair=-1;uint8_t cflags=0;
uint32_t guard_until=0;
struct Acc{uint64_t frames=0,pairs=0,empty=0,inv[NRO_INV_N]{},full=0,nest=0,queries=0,flushes=0,flushed_q=0,conds=0,unknown=0,cond_inv=0,enables=0,disables=0,
    draws=0,verts=0,cdraws=0,cverts=0,sw_cull=0,sw_verts=0,gpu_cull=0,gpu_same=0,strict_ok=0,strict_false=0,loose_ok=0,loose_false=0,addr_ok=0,addr_false=0,
    exec_gpu=0,exec_skip=0,exec_exact=0,exec_false=0,guard_scene=0,guard_reveal=0,reveals=0,cross=0,conds_lost=0,left_open=0;} acc;
uint64_t red_n=0,red_total=0;std::chrono::steady_clock::time_point last_line{};
const char *path_name(int p){return p==NRO_PATH_GPU?"gpu":p==NRO_PATH_PREV?"prev":"auto";}
int config(){
    if(mode>=0)return mode;
    const char *e=getenv("DM_NR_OCC");mode=nro_clamp_mode(e && *e?atol(e):0);if(!mode)return 0;
    if(const char *c=getenv("DM_GFX_COND_RENDER");c && *c && atoi(c)!=0){xbg_logf("【红】[nr] occ: DM_GFX_COND_RENDER=%s owns the occlusion queries: DM_NR_OCC=%d off",c,mode);mode=0;return 0;}
    if(const char *p=getenv("DM_NR_OCC_PATH");p && *p)path=!strcmp(p,"gpu")?NRO_PATH_GPU:!strcmp(p,"prev")?NRO_PATH_PREV:NRO_PATH_AUTO;
    if(const char *n=getenv("DM_NR_OCC_N");n && *n){long v=atol(n);hold=unsigned(v<1?1:v>60?60:v);}
    if(const char *s=getenv("DM_NR_OCC_STILL");s && *s)still=atoi(s)!=0;
    if(const char *d=getenv("DM_NR_OCC_DROP");d && *d)drop=atoi(d)!=0;
    if(mode==NRO_CHECK)drop=false;
    return mode;}
// xbg_game_initialize (device, family known): the path, the predicate buffer, the decision state.
void init(){
    if(config()<=0 || pbuf)return;
    const int want=path==NRO_PATH_AUTO?xbg_nr_occ_path_default(gpu_policy):path;
    const bool ext=&dm_vk_cond_render && dm_vk_cond_render;
    if(ext){pbegin=(PFN_vkCmdBeginConditionalRenderingEXT)vkGetDeviceProcAddr(cfg.device,"vkCmdBeginConditionalRenderingEXT");pend=(PFN_vkCmdEndConditionalRenderingEXT)vkGetDeviceProcAddr(cfg.device,"vkCmdEndConditionalRenderingEXT");}
    gpu_ok=pbegin && pend;path=want==NRO_PATH_GPU && !gpu_ok?NRO_PATH_PREV:want;
    VkBufferCreateInfo ci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};ci.size=VkDeviceSize(2*NRO_MAX_Q+4)*4;ci.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT|(gpu_ok?VK_BUFFER_USAGE_CONDITIONAL_RENDERING_BIT_EXT:0);ci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
    bool ok=!vkCreateBuffer(cfg.device,&ci,nullptr,&pbuf);
    if(ok){VkMemoryRequirements r;vkGetBufferMemoryRequirements(cfg.device,pbuf,&r);VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ai.allocationSize=r.size;
        ai.memoryTypeIndex=find_memory(r.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,VK_MEMORY_PROPERTY_HOST_CACHED_BIT);void *p=nullptr;
        ok=!vkAllocateMemory(cfg.device,&ai,nullptr,&pmem) && !vkBindBufferMemory(cfg.device,pbuf,pmem,0) && !vkMapMemory(cfg.device,pmem,0,ci.size,0,&p) && p;
        if(ok){pmap=static_cast<uint32_t*>(p);memset(pmap,0,size_t(ci.size));pmap[2*NRO_MAX_Q]=0;pmap[2*NRO_MAX_Q+1]=1;}}
    if(ok){for(auto &s:ss){s=static_cast<nro_slot*>(calloc(1,sizeof(nro_slot)));ok=ok && s;if(s)nro_slot_reset(s);}hist=static_cast<nro_hist*>(calloc(1,sizeof(nro_hist)));ok=ok && hist;}
    if(!ok){xbg_logf("【红】[nr] occ: no predicate buffer / memory: DM_NR_OCC=%d off",mode);mode=0;return;}
    xbg_logf("[nr] occ DM_NR_OCC=%d (%s) path=%s (asked %s, family %s, VK_EXT_conditional_rendering %s) N=%u still=%d drop_old_reports=%d",mode,
        mode==NRO_ON?"on":mode==NRO_CHECK?"check: decisions compared with the same-frame truth, every draw made":"poison: decisions inverted",path_name(path),
        path_name(want),xbg_gpu_family_name(gpu_policy),gpu_ok?"on":"off",hold,still,int(drop && mode!=NRO_CHECK));}
// destroy_slots: the device objects go with the slots (initialize after a device loss makes new ones); decisions start over.
void destroy(){
    for(auto &q:pool)if(q){vkDestroyQueryPool(cfg.device,q,nullptr);q=VK_NULL_HANDLE;}
    if(pbuf){vkDestroyBuffer(cfg.device,pbuf,nullptr);pbuf=VK_NULL_HANDLE;}if(pmem){vkFreeMemory(cfg.device,pmem,nullptr);pmem=VK_NULL_HANDLE;}pmap=nullptr;
    for(auto &n:ss){free(n);n=nullptr;}free(hist);hist=nullptr;for(auto &r:reset_n)r=0;for(auto &c:copied)c=0;
    kind=CONDR_K_ON;dec=D_RENDER;cpair=-1;cflags=0;guard_until=0;}
inline int kof(const Slot &s){return int(&s-slots);}
inline nro_slot *cur(int &k){Slot &s=recording_slot();k=kof(s);return ss[k];}
bool in_pair(){if(mode<=0 || !slots[slot_index].recording)return false;const nro_slot *n=ss[slot_index];return n && n->open>=0;}
// recording_slot(), after the slot's own query pool resets (outside any pass): this submission's pair table and query pool.
void slot_begin(Slot &s){
    if(mode<=0)return;const int k=kof(s);
    if(!pool[k]){VkQueryPoolCreateInfo q{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO};q.queryType=VK_QUERY_TYPE_OCCLUSION;q.queryCount=NRO_MAX_Q;
        if(vkCreateQueryPool(cfg.device,&q,nullptr,&pool[k])){xbg_logf("【红】[nr] occ: no query pool: DM_NR_OCC off");mode=0;return;}reset_n[k]=NRO_MAX_Q;}
    if(reset_n[k])vkCmdResetQueryPool(s.cmd,pool[k],0,reset_n[k]);
    nro_slot_reset(ss[k]);copied[k]=0;
    if(dec==D_GPU && cslot!=k){dec=D_RENDER;cpair=-1;cflags=0;}   // a predicate word of the other submission: render (never straddle the ring)
}
// OP_REPORT_COUNTER, samples passed. true = the old report work is dropped (mode 1 / 3, DM_NR_OCC_DROP=1).
bool report(uint64_t addr){
    int k;nro_slot *n=cur(k);int32_t eq,i;const int r=nro_report(n,addr,&eq,&i);
    if(r&NRO_R_END_QUERY)vkCmdEndQuery(slots[k].cmd,pool[k],uint32_t(eq));
    if(r&NRO_R_FULL)++acc.full;if(r&NRO_R_NEST)++acc.nest;
    if(i>=0 && !n->pair[i].inv){++n->closed_valid;const nro_hent *e=nro_hist_get(hist,n->pair[i].mesh);if(e && e->last==hist->serial)++n->matched;}
    return drop && mode!=NRO_CHECK;}
// draw() entry, before any of the backend's own skips: the draw counts for an open pair and adds to its key.
void draw_enter(int prim,int first,int count,const p_draw_idx *indexed,uint32_t instances){
    nro_slot *n=ss[slot_index];if(!n || !slots[slot_index].recording)return;   // not begun: no pair of this submission is open yet
    const uint32_t inst=indexed?uint32_t(indexed->instances):instances;++n->draws;n->verts+=uint64_t(uint32_t(count))*inst;
    nro_pair *p=nro_draw_enter(n);if(!p || p->inv || (mode!=NRO_CHECK && path!=NRO_PATH_PREV))return;   // the GPU path needs no key
    uint64_t h=nro_mix(p->mesh,uint64_t(uint32_t(prim))|uint64_t(uint32_t(count))<<32);h=nro_mix(h,uint64_t(uint32_t(first))|uint64_t(inst)<<32);
    if(indexed){h=nro_mix(h,indexed->ibuf);h=nro_mix(h,uint64_t(uint32_t(indexed->itype))|uint64_t(uint32_t(indexed->base_vertex))<<32);}
    for(unsigned i=0;i<4;i++)h=nro_mix(h,state.vb[i].address);
    h=nro_mix(h,uint64_t(uintptr_t(state.shader[0])));p->mesh=h;
    uint64_t u=p->ubo;   // the vertex stage's constants (first 256 bytes of the first 4 bound ranges): the object's transform, camera-dependent or not
    for(unsigned i=0,m=0;i<16 && m<4;i++){const NVNbufferRange &r=state.ub[0][i];if(!r.address || !r.size)continue;++m;const size_t b=size_t(r.size<256?r.size:256);
        evguard::EngineRead er(reinterpret_cast<const void*>(uintptr_t(r.address)),b);u=nro_hash_bytes(nro_mix(u,i),reinterpret_cast<const void*>(uintptr_t(r.address)),b);}
    p->ubo=u;}
// condr::set (OP_X_RENDER_COND, OP_X_NB_DRAW flags): the condition in force from now on.
void set(const p_render_cond &c){
    kind=c.kind==CONDR_K_OFF || c.kind==CONDR_K_COND?c.kind:CONDR_K_ON;nvn=c.mode;dec=D_RENDER;cpair=-1;cflags=0;pinv=false;
    if(kind==CONDR_K_ON){++acc.enables;return;}
    if(kind==CONDR_K_OFF){++acc.disables;if(mode!=NRO_CHECK)dec=D_SKIP;return;}   // SetRenderEnable(false): the Switch draws nothing (DOS2 never calls it)
    ++acc.conds;int k;nro_slot *n=cur(k);cslot=k;
    const int32_t i=nro_lookup(n,c.addr);
    if(i<0){++acc.unknown;return;}
    const nro_pair &p=n->pair[i];cpair=i;
    if(p.inv || p.st!=NRO_PS_CLOSED){++acc.cond_inv;cpair=-1;return;}
    if(!(p.flags&NRO_PF_BEGUN)){   // no draw inside: zero samples, the Switch's answer is known now
        const bool render=nro_truth_render(nvn,0)!=0;if(mode!=NRO_CHECK && (render==(mode==NRO_POISON)))dec=D_SKIP;return;}
    const bool gpu_able=mode==NRO_CHECK?nro_copy_ready(n,&p)!=0:(p.flags&NRO_PF_COPIED)!=0;
    const bool guard=nro_guard_scene(n->matched,n->closed_valid) || hist->serial<guard_until;
    const bool strict=!guard && nvn==NRO_NVN_IF_NOT_EQUAL && nro_prev_cull(hist,p.mesh,p.ubo,p.occ,hold,1);
    const bool loose=!guard && nvn==NRO_NVN_IF_NOT_EQUAL && nro_prev_cull(hist,p.mesh,p.ubo,p.occ,hold,0);
    if(guard){if(nro_guard_scene(n->matched,n->closed_valid))++acc.guard_scene;else ++acc.guard_reveal;}
    const bool by_addr=mode==NRO_CHECK && nvn==NRO_NVN_IF_NOT_EQUAL && nro_addr_cull(hist,p.addr);   // what DM_GFX_COND_RENDER=3 would do
    cflags=uint8_t((gpu_able?NRO_CD_GPU_OK:0)|(strict?NRO_CD_PREV_STRICT:0)|(loose?NRO_CD_PREV_LOOSE:0)|(by_addr?NRO_CD_PREV_ADDR:0));
    if(mode==NRO_CHECK)return;
    if(path==NRO_PATH_GPU){if(gpu_able){dec=D_GPU;poff=uint32_t(k*NRO_MAX_Q+p.q)*4;pinv=(nvn==NRO_NVN_IF_EQUAL)!=(mode==NRO_POISON);}return;}
    const bool cull=still?strict:loose;if(cull!=(mode==NRO_POISON))dec=D_SKIP;}
// OP_END of a top-level handle: a condition does not outlive it (as condr::handle_end).
void handle_end(){if(mode>0 && kind!=CONDR_K_ON){kind=CONDR_K_ON;dec=D_RENDER;cpair=-1;cflags=0;++acc.left_open;}}
// draw(), after condr: true = the host skips this draw. Every draw under a condition is noted for the check at retire.
bool skip_draw(int count,const p_draw_idx *indexed,uint32_t instances){
    if(kind==CONDR_K_ON)return false;
    ++acc.cdraws;const uint64_t v=uint64_t(uint32_t(count))*(indexed?uint32_t(indexed->instances):instances);acc.cverts+=v;
    nro_slot *n=ss[slot_index];
    if(kind==CONDR_K_COND && cpair>=0 && n && slots[slot_index].recording){if(cslot!=int(slot_index)){++acc.cross;}
        else if(n->nconds<NRO_MAX_CONDS){nro_cond &c=n->cond[n->nconds++];c.pair=cpair;c.nvn_mode=uint8_t(nvn);c.flags=uint8_t(cflags|(dec==D_SKIP?NRO_CD_EXEC_SKIP:0));c.verts=v;}
        else ++n->conds_lost;}
    if(dec==D_SKIP){if(cpair>=0 && n && !(n->pair[cpair].flags&NRO_PF_BEGUN))++acc.exec_exact;else ++acc.exec_skip;return true;}
    return false;}
// Right before the draw command (inside its pass): begin the open pair's query, begin the GPU predicate. Bits for after_draw.
unsigned before_draw(VkCommandBuffer cmd){
    unsigned bits=0;nro_slot *n=ss[slot_index];if(!n)return 0;
    // (an open run of the old samples counter: never nest - the pair then loses this draw and renders)
    if(n->open>=0 && !open_occlusion.cmd){int32_t q;const int r=nro_draw_query(n,&q);if(r==1){vkCmdBeginQuery(cmd,pool[slot_index],uint32_t(q),0);++acc.queries;}if(r)bits|=1;}
    if(dec==D_GPU && kind==CONDR_K_COND && cslot==int(slot_index)){VkConditionalRenderingBeginInfoEXT bi{VK_STRUCTURE_TYPE_CONDITIONAL_RENDERING_BEGIN_INFO_EXT};bi.buffer=pbuf;bi.offset=poff;
        bi.flags=pinv?VK_CONDITIONAL_RENDERING_INVERTED_BIT_EXT:0;nbmt::PBeginConditionalRendering(pbegin,cmd,&bi);++acc.exec_gpu;bits|=2;}
    return bits;}
void after_draw(VkCommandBuffer cmd,unsigned bits){if(bits&2)nbmt::PEndConditionalRendering(pend,cmd);if(bits&1)nro_draw_done(ss[slot_index]);}
inline int slot_of(VkCommandBuffer cmd){for(int k=0;k<2;k++)if(slots[k].cmd==cmd)return k;return -1;}
// end_open_pass, before vkCmdEndRenderPass: the open pair's query ends with the pass (a later draw of that pair invalidates it).
void pass_end_q(VkCommandBuffer cmd){const int k=slot_of(cmd);if(k<0 || !ss[k])return;const int32_t q=nro_pass_end(ss[k]);if(q>=0)vkCmdEndQuery(cmd,pool[k],uint32_t(q));}
// end_open_pass, after vkCmdEndRenderPass (GPU path, modes 1 / 3): the ended queries into their predicate words, visible to the
// conditional-rendering reads of later passes.
void pass_end_flush(VkCommandBuffer cmd){
    if(mode==NRO_CHECK || path!=NRO_PATH_GPU)return;const int k=slot_of(cmd);if(k<0 || !ss[k])return;uint32_t lo,nq;
    if(!nro_flush_range(ss[k],&lo,&nq))return;
    vkCmdCopyQueryPoolResults(cmd,pool[k],lo,nq,pbuf,VkDeviceSize(k*NRO_MAX_Q+lo)*4,4,VK_QUERY_RESULT_WAIT_BIT);
    VkMemoryBarrier b{VK_STRUCTURE_TYPE_MEMORY_BARRIER};b.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;b.dstAccessMask=VK_ACCESS_CONDITIONAL_RENDERING_READ_BIT_EXT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_CONDITIONAL_RENDERING_BIT_EXT,0,1,&b,0,nullptr,0,nullptr);++acc.flushes;acc.flushed_q+=nq;}
// submit_slots, after the last pass end: the queries no pass-end flush copied, for the host at retire.
void submit(Slot &s){
    if(mode<=0)return;const int k=kof(s);nro_slot *n=ss[k];if(!n)return;
    reset_n[k]=n->qused;copied[k]=n->qused;if(!n->qused)return;const uint32_t lo=n->flush_lo,nq=n->qused-n->flush_lo;n->flush_lo=n->qused;
    if(nq)vkCmdCopyQueryPoolResults(s.cmd,pool[k],lo,nq,pbuf,VkDeviceSize(k*NRO_MAX_Q+lo)*4,4,VK_QUERY_RESULT_WAIT_BIT);
    VkMemoryBarrier b{VK_STRUCTURE_TYPE_MEMORY_BARRIER};b.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;b.dstAccessMask=VK_ACCESS_HOST_READ_BIT;
    vkCmdPipelineBarrier(s.cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&b,0,nullptr,0,nullptr);}
void red(const char *what,const nro_pair &p,const nro_cond &c,uint32_t samples){
    ++red_total;if(red_n>=16)return;++red_n;
    xbg_logf("【红】[nr] occ %s: pair %#llx mesh %016llx occ %u: the prev path culled / would cull it, but %u samples passed this frame (%llu vertices, history serial %u)",
        what,(unsigned long long)p.addr,(unsigned long long)p.mesh,unsigned(p.occ),samples,(unsigned long long)c.verts,hist->serial);}
// retire_slot, after the fence (before the slot is reused): the truth of this submission's pairs -> the check, the history.
void retire(Slot &s){
    if(mode<=0)return;const int k=kof(s);nro_slot *n=ss[k];if(!n)return;
    if(n->draws){++acc.frames;acc.draws+=n->draws;acc.verts+=n->verts;n->draws=n->verts=0;}   // (a slot may retire twice: counted once)
    if(!n->npairs)return;
    const uint32_t *res=pmap+size_t(k)*NRO_MAX_Q;
    if(copied[k]<n->qused){static std::vector<uint32_t> v;v.assign(n->qused,0);   // no submit copy (should not happen): ask the pool; every used query has ended
        if(vkGetQueryPoolResults(cfg.device,pool[k],0,n->qused,v.size()*4,v.data(),4,0)!=VK_SUCCESS)for(auto &x:v)x=1;res=v.data();}
    auto samples=[&](const nro_pair &p)->uint32_t{return (p.flags&NRO_PF_BEGUN) && p.q>=0?res[p.q]:0u;};
    acc.conds_lost+=n->conds_lost;n->conds_lost=0;
    // the check: every conditional draw against the same-frame truth
    for(uint32_t i=0;i<n->nconds;i++){const nro_cond &c=n->cond[i];const nro_pair &p=n->pair[c.pair];const uint32_t sm=samples(p);
        const bool hidden=!nro_truth_render(c.nvn_mode,sm);
        if(hidden){++acc.sw_cull;acc.sw_verts+=c.verts;if(c.flags&NRO_CD_GPU_OK)++acc.gpu_cull;else if(p.flags&NRO_PF_BEGUN)++acc.gpu_same;}
        if(c.flags&NRO_CD_PREV_STRICT){if(hidden)++acc.strict_ok;else{++acc.strict_false;if(mode==NRO_CHECK && still)red("false cull (strict, would be)",p,c,sm);}}
        if(c.flags&NRO_CD_PREV_LOOSE){if(hidden)++acc.loose_ok;else{++acc.loose_false;if(mode==NRO_CHECK && !still)red("false cull (loose, would be)",p,c,sm);}}
        if(c.flags&NRO_CD_PREV_ADDR){if(hidden)++acc.addr_ok;else ++acc.addr_false;}
        if((c.flags&NRO_CD_EXEC_SKIP) && !hidden && mode==NRO_ON){++acc.exec_false;red("FALSE CULL on screen",p,c,sm);}}
    // the history (prev path; the GPU path only counts): mesh keys first, then strict keys of meshes repeated in this submission
    const bool keys=mode==NRO_CHECK || path==NRO_PATH_PREV;
    uint32_t valid=0,reveals=0;if(keys)nro_hist_begin(hist);
    for(uint32_t i=0;i<n->npairs;i++){const nro_pair &p=n->pair[i];if(p.st!=NRO_PS_CLOSED){++acc.inv[NRO_INV_OPEN];continue;}if(p.inv){++acc.inv[p.inv];continue;}
        ++acc.pairs;++valid;const uint32_t sm=samples(p);if(!(p.flags&NRO_PF_BEGUN))++acc.empty;
        if(!keys)continue;const nro_hent *e=nro_hist_get(hist,p.mesh);if(e && e->last+1==hist->serial && e->streak>=hold && sm)++reveals;
        nro_hist_put(hist,p.mesh,p.ubo,sm==0);if(mode==NRO_CHECK)nro_addr_put(hist,p.addr,sm==0);}
    for(uint32_t i=0;keys && i<n->npairs;i++){const nro_pair &p=n->pair[i];if(p.st!=NRO_PS_CLOSED || p.inv)continue;const nro_hent *e=nro_hist_get(hist,p.mesh);
        if(e && e->count>1)nro_hist_put(hist,nro_strict_key(p.mesh,p.ubo),p.ubo,samples(p)==0);}
    acc.reveals+=reveals;if(nro_guard_reveals(reveals,valid))guard_until=hist->serial+2;
    n->npairs=0;n->nconds=0;n->open=n->qactive=-1;}
// NVN PERF cadence: the summary every 10 s.
void perf_report(){
    if(mode<=0 || !acc.frames)return;const auto now=std::chrono::steady_clock::now();
    if(last_line.time_since_epoch().count() && now-last_line<std::chrono::seconds(10))return;last_line=now;
    const double f=double(acc.frames),dr=acc.draws?100.0/double(acc.draws):0,vr=acc.verts?100.0/double(acc.verts):0;
    xbg_logf("[nr] occ DM_NR_OCC=%d path=%s: %llu submissions; pairs %.1f/f (empty %.1f; unusable: pool %.2f split %.2f skipped-by-host %.2f nested %.2f open %.2f; full %.2f), "
        "conditions %.1f/f (no pair %.2f, unusable pair %.2f, other submission %.2f, left open %llu), SetRenderEnable on %.1f off %.1f; draws %.1f/f, conditional %.1f/f (%.1f %%)",
        mode,path_name(path),(unsigned long long)acc.frames,acc.pairs/f,acc.empty/f,acc.inv[NRO_INV_POOL]/f,acc.inv[NRO_INV_SPLIT]/f,acc.inv[NRO_INV_SKIPPED]/f,acc.inv[NRO_INV_NEST]/f,
        acc.inv[NRO_INV_OPEN]/f,acc.full/f,acc.conds/f,acc.unknown/f,acc.cond_inv/f,acc.cross/f,(unsigned long long)acc.left_open,acc.enables/f,acc.disables/f,acc.draws/f,acc.cdraws/f,double(acc.cdraws)*dr);
    xbg_logf("[nr] occ the Switch culls %.1f draws/f = %.2f %% of draws, %.2f %% of vertices; GPU path culls %.1f/f (same-pass consumers it must draw: %.1f/f); "
        "prev strict (N=%u) culls %.1f/f right, %.2f/f WRONG; prev loose %.1f/f right, %.2f/f WRONG; by address (as DM_GFX_COND_RENDER=3) %.1f/f right, %.2f/f WRONG; conditions under a guard: scene %.1f/f reveal %.1f/f (reveals %.2f/f); "
        "executed: gpu predicate %.1f/f, host skip %.1f/f (exact %.1f/f), false culls on screen %llu; queries %.1f/f, flushes %.1f/f (%.1f queries), history %u keys / %u rebuilds / %u lost%s",
        acc.sw_cull/f,double(acc.sw_cull)*dr,double(acc.sw_verts)*vr,acc.gpu_cull/f,acc.gpu_same/f,hold,acc.strict_ok/f,acc.strict_false/f,acc.loose_ok/f,acc.loose_false/f,acc.addr_ok/f,acc.addr_false/f,
        acc.guard_scene/f,acc.guard_reveal/f,acc.reveals/f,acc.exec_gpu/f,acc.exec_skip/f,acc.exec_exact/f,(unsigned long long)acc.exec_false,acc.queries/f,acc.flushes/f,acc.flushed_q/f,
        hist->n,hist->rebuilds,hist->lost,acc.conds_lost?" (conditional draws lost: table full)":"");
    if(red_total)xbg_logf("%s[nr] occ prev-path false culls so far: %llu (%s)",red_total?"【红】":"",(unsigned long long)red_total,mode==NRO_ON?"drawn a frame or two late on screen":"would be");
    acc=Acc{};}
}
