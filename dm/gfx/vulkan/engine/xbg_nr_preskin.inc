// [DOS2] NR-PRESKIN DM_NR_PRESKIN (docs/dos2/nr/NR-PRESKIN.md): skinned meshes are skinned once per submission, not in every pass.
// Included by xbg_game.cpp right after xbg_nr_posonly.inc (before draw()). SPIR-V in xbg_spirv_preskin.{h,cpp} (plan = minimum cut of the
// skinning vertex shader; SLICE = the cut values' computation storing raw words; CONSUMER = the shader reading them as uint inputs), the
// record table in dm/gfx/nr/nr_preskin.h.
//   DM_NR_PRESKIN  0  default everywhere (xbg_vendor_policy.h xbg_nr_preskin_default): draw() pays one load and a not-taken branch; no
//                     analysis at load.
//                  2  count: every skinned draw is classified (depth-only / colour; why not), its record looked up / made in a table per
//                     submission exactly as =1 would (reuse: own record, another shader's wider record), the work a frame before / after in
//                     the plan's instruction counts and the malioc G57 cycle model; nothing is drawn differently.
//                  1  apply: per mesh instance (bone block + vertex streams) and value set, the slice runs ONCE per submission in the
//                     submission's prologue command buffer: one vertex-only draw of the mesh's vertices (rasterizer discard, POINT_LIST, the
//                     draw's own vertex buffers and formats: the same fixed-function fetch) storing the cut values into a per-slot arena;
//                     every skinned draw of the submission whose values are in a record binds it as one more vertex stream (binding P.k,
//                     stride 4 x record words, R32..R32G32B32A32_UINT groups) with its consumer module. No extra barrier: the prologue is
//                     submitted ahead of the slot's command buffer, whose first command is the full ALL -> ALL barrier every submission
//                     already starts with (recording_slot). Fallback = the draw as before.
//                  3  poison: as 1, but the slices are not run (records hold stale / zero words): skinned characters break on screen.
//   DM_NR_PRESKIN_MAXM 16   records of at most this many words a vertex are used (3 = the depth passes' position only; 12 = G-buffer)
//   DM_NR_PRESKIN_MAXV 65536 vertices a record may cover (a mesh's vertex stream range; larger: not pre-skinned)
//   DM_NR_PRESKIN_MB   8    arena per slot (two slots), capped by NR-29's static-buffer share
// Needs vertexPipelineStoresAndAtomics (modes 1 / 3; without it: counted only). Line "[nr] preskin (...)" every 10 s, start line
// "[nr] DM_NR_PRESKIN=...", red lines "【红】[nr] preskin: ...".
#include "../../nr/nr_preskin.h"
// xbg_spirv_preskin.h: included at the top of xbg_game.cpp (before the NB-20b context defines)
namespace nrps{
int mode=-1;uint32_t maxm=16,maxv=65536;uint64_t asize=0;
enum Why{W_STAGES,W_SPECIAL,W_TOPO,W_CONV,W_PLAN,W_WIDE,W_ATTR,W_INST,W_UNBOUND,W_PENDING,W_STRIDE,W_BIG,W_ALIGN,W_ARENA,W_POOL,W_PIPE,W_CONS,W_BIND,W_N};
const char *const why_name[W_N]={"tess/geometry","special draw","points","converted format","no plan","record too wide","attribute","instanced input",
    "unbound","pending GPU result","stride / format","mesh too big","uniform alignment","arena full","descriptor pool","slice pipeline","consumer module","no free binding"};
struct Cons{VkShaderModule mod{};XbgPreskinLayout lay{};uint32_t id=0;std::vector<uint32_t> words;std::map<std::tuple<uint64_t,uint64_t,int>,VkShaderModule> trim;};
struct Plan{
    std::string key;bool ok=false;std::string why;XbgPreskinPlan p;std::vector<uint32_t> words;
    std::vector<uint32_t> slot,bytes;uint32_t bone_slot=0;nrps_val want[NRPS_MAXV]{};uint32_t nwant=0;
    VkShaderModule slice{};VkDescriptorSetLayout dsl{};VkPipelineLayout pl{};
    std::unordered_map<uint64_t,VkPipeline> pipes;std::unordered_map<uint64_t,std::unique_ptr<Cons>> cons;
    uint32_t cls=0;   // 0: record <= 4 words (depth passes' position), 1: wider (G-buffer / FX)
};
struct PK{const Shader *s;uint64_t code;bool operator==(const PK &o)const{return s==o.s && code==o.code;}};
struct PKH{size_t operator()(const PK &k)const{return size_t(uint64_t(uintptr_t(k.s))*0x9E3779B97F4A7C15ull^k.code);}};
std::unordered_map<PK,std::unique_ptr<Plan>,PKH> plans;uint32_t next_cons=1;
struct Job{VkPipeline pipe{};VkPipelineLayout pl{};VkDescriptorSet set{};uint32_t nverts=0,nb=0;uint32_t bind[17]{};VkBuffer vb[17]{};VkDeviceSize off[17]{};};
// descriptor sets: allocated once per (slot, plan) and rewritten in later submissions of the slot (its previous one retired): vk_tramp has
// no vkResetDescriptorPool (as xbg_game.cpp's pass probes)
struct Sets{std::vector<VkDescriptorSet> v;size_t used=0;};
struct SlotSt{uint64_t serial=~0ull;VkBuffer buf{};VkDeviceMemory mem{};uint8_t *map=nullptr;bool coh=true;nrps_bump bump{};VkDescriptorPool pool{};
    std::vector<Job> jobs;std::vector<nrps_rec> recs;std::unordered_multimap<uint64_t,uint32_t> by_bucket;std::unordered_map<const void*,Sets> sets;};
SlotSt S[MAX_SLOTS];VkRenderPass rp{};VkFramebuffer fb{};
struct Plan_t{bool on=false;uint32_t k=0,stride=0,lay_id=0;uint64_t code=0;Buffer view{};Plan *pl=nullptr;Cons *c=nullptr;} P;   // the draw in hand
struct Stats{uint64_t draws,sk[2],sk_idx[2],why[W_N],why_idx[W_N],elig[2],elig_idx[2],applied[2],applied_idx[2],recs[2],rec_verts[2],rec_bytes,own[2],sup[2],
    jobs,code_mismatch,ops_saved,ops_slice,cyc_saved,cyc_slice;} s{};
uint64_t next_ns=0,frames0=0,peak=0;unsigned reds=0;
void red(const char *fmt,...) __attribute__((format(printf,1,2)));
void red(const char *fmt,...){if(reds++>=16)return;char b[400];va_list a;va_start(a,fmt);vsnprintf(b,sizeof b,fmt,a);va_end(a);xbg_logf("【红】[nr] preskin: %s",b);}
// malioc 2026.5 Mali-G57 (the player's pack, the Mali load chain + retype; docs/dos2/nr/NR-PRESKIN.md section 4), cycles a vertex, bound
// (load/store): saved by the consumer in the position + varying variants, and the slice per pre-skinned vertex. A model, not a measure.
const double cyc_saved_k[2]={14.0+14.0,12.0+13.5},cyc_slice_k[2]={18.0,21.0};
// 19.11 W_m1b: the family default (1 on Mali / PowerVR) must count here too - gpu_policy is set in xbg_game_initialize, before any module loads
bool on_at_load(){static int v=-1;if(v<0){const char *e=getenv("DM_NR_PRESKIN");v=e && *e?atoi(e)!=0:xbg_nr_preskin_default(gpu_policy)!=0;}return v!=0;}
uint32_t env_u(const char *n,uint32_t d,uint32_t lo,uint32_t hi){const char *e=getenv(n);return e && *e?std::clamp<uint32_t>(uint32_t(atoi(e)),lo,hi):d;}
void init(){
    const char *e=getenv("DM_NR_PRESKIN");int m=e && *e?atoi(e):xbg_nr_preskin_default(gpu_policy);if(m<0 || m>3)m=0;
    maxm=env_u("DM_NR_PRESKIN_MAXM",16,1,16);maxv=env_u("DM_NR_PRESKIN_MAXV",65536,256,1u<<22);
    if(m && !on_at_load()){xbg_logf("【红】[nr] DM_NR_PRESKIN=%d from the family default: the shaders were not analysed at load (needs DM_NR_PRESKIN in dm/env): off",m);m=0;}
    if((m==1 || m==3) && !cfg.enabled_core.vertexPipelineStoresAndAtomics){red("vertexPipelineStoresAndAtomics is off on this device: counting only (=2)");m=2;}
    if(m==1 || m==3){asize=uint64_t(env_u("DM_NR_PRESKIN_MB",8,1,256))<<20;if(dm_nr_mem_cap)asize=std::min<uint64_t>(asize,dm_nr_mem_cap(NRM_BUFSTATIC,asize));
        bool ok=true;
        for(auto &st:S){if(!nrbuf::make(VkDeviceSize(asize),st.buf,st.mem,st.map,st.coh)){ok=false;break;}memset(st.map,0,64);if(!st.coh)nrbuf::flush(st.mem,0,64);   // words 0..15: the zero stream of constant inputs
            VkDescriptorPoolSize ps[2]={{VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,8192},{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,2048}};VkDescriptorPoolCreateInfo pc{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
            pc.maxSets=2048;pc.poolSizeCount=2;pc.pPoolSizes=ps;if(vkCreateDescriptorPool(cfg.device,&pc,nullptr,&st.pool)!=VK_SUCCESS){ok=false;break;}
            st.bump.size=asize;}
        if(ok){VkSubpassDescription sp{};sp.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS;VkRenderPassCreateInfo rc{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};rc.subpassCount=1;rc.pSubpasses=&sp;
            ok=vkCreateRenderPass(cfg.device,&rc,nullptr,&rp)==VK_SUCCESS;
            if(ok){VkFramebufferCreateInfo fc{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};fc.renderPass=rp;fc.width=fc.height=fc.layers=1;ok=vkCreateFramebuffer(cfg.device,&fc,nullptr,&fb)==VK_SUCCESS;}}
        if(!ok){red("no memory / pool / render pass for %llu MB arenas: counting only (=2)",(unsigned long long)(asize>>20));m=2;}}
    xbg_logf("[nr] DM_NR_PRESKIN=%d (NR-PRESKIN: %s; family default %d): skinning vertex shaders cut at load, the slice once per mesh instance and submission, "
             "consumers read the record; records up to %u words, meshes up to %u vertices, arena %llu MB a slot",m,m==1?"on":m==2?"count only":m==3?"POISON (slices not run)":"off",
             xbg_nr_preskin_default(gpu_policy),maxm,maxv,(unsigned long long)(asize>>20));
    mode=m;}
// the plan of a vertex shader for one retype code (the words the pipeline's module is made of)
Plan *plan_for(const Shader *vs,uint64_t code){
    auto f=plans.find(PK{vs,code});if(f!=plans.end() && f->second->key==vs->key)return f->second.get();
    auto pl=std::make_unique<Plan>();pl->key=vs->key;Plan *r=pl.get();plans[PK{vs,code}]=std::move(pl);
    if(vs->words.empty()){r->why="the module's words were not kept";return r;}
    std::string why;if(code){if(!vtx_retype_words(*vs,code,vs->words,r->words,&why)){r->why="retype: "+why;return r;}}else r->words=vs->words;
    std::vector<XbgPreskinBind> binds;for(auto &b:vs->bindings)if(b.type==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER)binds.push_back({b.binding,b.source<<16|b.slot});
    if(!xbg_spirv_preskin_plan(r->words.data(),r->words.size(),binds.data(),binds.size(),r->p)){r->why=r->p.why;return r;}
    for(uint32_t b:r->p.slice_ubos){const xbg_shader_binding *sb=nullptr;for(auto &x:vs->bindings)if(x.binding==b && x.type==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER)sb=&x;
        if(!sb || sb->source!=XBG_SOURCE_UNIFORM || sb->slot>=NRPS_SLOTS || sb->count!=1){r->why="a slice uniform block is not one NVN uniform slot";return r;}
        r->slot.push_back(sb->slot);r->bytes.push_back(sb->bytes);if(b==r->p.bone_binding)r->bone_slot=sb->slot;}
    r->nwant=uint32_t(r->p.vals.size());if(r->nwant>NRPS_MAXV){r->why="too many values";return r;}
    for(uint32_t i=0;i<r->nwant;i++){const XbgPreskinVal &v=r->p.vals[i];uint32_t sm=0;for(size_t k=0;k<r->slot.size();k++)if(v.ubo_mask>>k&1)sm|=1u<<r->slot[k];
        r->want[i]={v.hash,v.first,v.comps,v.loc_mask,sm};}
    r->cls=r->p.m<=4?0:1;
    if(mode==1 || mode==3){   // the slice module and its layout (set 0: the uniform blocks it reads + the record buffer)
        std::vector<uint32_t> sw;const char *w="";
        if(!xbg_spirv_preskin_slice(r->words.data(),r->words.size(),r->p,sw,&w)){r->why=std::string("slice: ")+w;return r;}
        VkShaderModuleCreateInfo mc{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};mc.codeSize=sw.size()*4;mc.pCode=sw.data();
        {gpguard::ModuleLock serial;if(vkCreateShaderModule(cfg.device,&mc,nullptr,&r->slice)!=VK_SUCCESS){r->slice={};r->why="slice module";return r;}}
        std::vector<VkDescriptorSetLayoutBinding> lb;for(uint32_t b:r->p.slice_ubos)lb.push_back({b,VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,1,VK_SHADER_STAGE_VERTEX_BIT,nullptr});
        lb.push_back({r->p.ssbo_binding,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_VERTEX_BIT,nullptr});
        VkDescriptorSetLayoutCreateInfo dc{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};dc.bindingCount=uint32_t(lb.size());dc.pBindings=lb.data();
        if(vkCreateDescriptorSetLayout(cfg.device,&dc,nullptr,&r->dsl)!=VK_SUCCESS){r->dsl={};r->why="slice set layout";return r;}
        VkPipelineLayoutCreateInfo pc{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};pc.setLayoutCount=1;pc.pSetLayouts=&r->dsl;
        if(vkCreatePipelineLayout(cfg.device,&pc,nullptr,&r->pl)!=VK_SUCCESS){r->pl={};r->why="slice pipeline layout";return r;}}
    r->ok=true;
    static unsigned told=0;if(told++<8 || mode==2)xbg_logf("[nr] preskin plan vs=%s code=%llx: record %u words (%u values, %u on another uniform block), bone loads %u, body ops %u -> consumer %u + slice %u, "
        "Locations orig %04x slice %04x consumer %04x",vs->key.c_str(),(unsigned long long)code,r->p.m,r->nwant,r->p.kdep,r->p.bone_loads,r->p.ops_orig,r->p.ops_cons,r->p.ops_slice,r->p.orig_locs,r->p.slice_locs,r->p.cons_locs);
    return r;}
Cons *cons_for(Plan *pl,const uint32_t *pos,uint64_t ph){
    auto f=pl->cons.find(ph);if(f!=pl->cons.end())return f->second->mod || mode==2?f->second.get():nullptr;
    auto c=std::make_unique<Cons>();Cons *r=c.get();pl->cons[ph]=std::move(c);const char *w="";
    if(!xbg_spirv_preskin_consumer(pl->words.data(),pl->words.size(),pl->p,pos,r->words,&r->lay,&w)){red("consumer of %s: %s",pl->key.c_str(),w);r->words.clear();return nullptr;}
    r->id=next_cons++;if(r->id>=(1u<<20)){red("consumer ids exhausted");return nullptr;}
    if(mode==2){r->words.clear();r->words.shrink_to_fit();return r;}
    VkShaderModuleCreateInfo mc{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};mc.codeSize=r->words.size()*4;mc.pCode=r->words.data();
    {gpguard::ModuleLock serial;if(vkCreateShaderModule(cfg.device,&mc,nullptr,&r->mod)!=VK_SUCCESS){r->mod={};red("consumer module of %s failed",pl->key.c_str());return nullptr;}}
    return r;}
// the slice pipeline for these vertex inputs (location, stream, format, offset, stride; zero = constant input on binding zb)
struct In{uint32_t loc,stream,off,stride,cls;VkFormat f;bool zero;};
VkPipeline slice_pipe(Plan *pl,const In *ins,uint32_t nin,uint32_t zb){
    uint64_t h=nrps_mix(0x51CEull,zb);for(uint32_t i=0;i<nin;i++){h=nrps_mix(h,ins[i].loc|ins[i].stream<<8|uint64_t(ins[i].zero)<<16|uint64_t(ins[i].cls)<<20);h=nrps_mix(h,uint64_t(ins[i].f)<<32|ins[i].off);h=nrps_mix(h,ins[i].stride);}
    auto f=pl->pipes.find(h);if(f!=pl->pipes.end())return f->second;
    std::vector<VkVertexInputBindingDescription> vb;std::vector<VkVertexInputAttributeDescription> va;uint32_t used=0;
    for(uint32_t i=0;i<nin;i++){const In &x=ins[i];
        if(x.zero){const VkFormat zf=x.cls==0?VK_FORMAT_R32G32B32A32_SFLOAT:x.cls==1?VK_FORMAT_R32G32B32A32_SINT:VK_FORMAT_R32G32B32A32_UINT;va.push_back({x.loc,zb,zf,0});
            if(!(used>>zb&1)){used|=1u<<zb;vb.push_back({zb,0,VK_VERTEX_INPUT_RATE_VERTEX});}continue;}
        va.push_back({x.loc,x.stream,x.f,x.off});if(!(used>>x.stream&1)){used|=1u<<x.stream;vb.push_back({x.stream,x.stride,VK_VERTEX_INPUT_RATE_VERTEX});}}
    VkPipelineShaderStageCreateInfo st{VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};st.stage=VK_SHADER_STAGE_VERTEX_BIT;st.module=pl->slice;st.pName="main";
    VkPipelineVertexInputStateCreateInfo vi{VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};vi.vertexBindingDescriptionCount=uint32_t(vb.size());vi.pVertexBindingDescriptions=vb.data();
    vi.vertexAttributeDescriptionCount=uint32_t(va.size());vi.pVertexAttributeDescriptions=va.data();
    VkPipelineInputAssemblyStateCreateInfo ia{VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};ia.topology=VK_PRIMITIVE_TOPOLOGY_POINT_LIST;
    VkPipelineRasterizationStateCreateInfo rs{VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};rs.rasterizerDiscardEnable=VK_TRUE;rs.polygonMode=VK_POLYGON_MODE_FILL;rs.lineWidth=1;
    VkGraphicsPipelineCreateInfo ci{VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};ci.stageCount=1;ci.pStages=&st;ci.pVertexInputState=&vi;ci.pInputAssemblyState=&ia;ci.pRasterizationState=&rs;
    ci.layout=pl->pl;ci.renderPass=rp;ci.subpass=0;
    VkPipeline p=VK_NULL_HANDLE;const uint64_t t0=timing_clock();
    if(vkCreateGraphicsPipelines(cfg.device,pipeline_cache,1,&ci,nullptr,&p)!=VK_SUCCESS){p=VK_NULL_HANDLE;red("slice pipeline of %s failed",pl->key.c_str());}
    else{static unsigned told=0;if(told++<16)xbg_logf("[nr] preskin slice pipeline vs=%s inputs %u: %.1f ms",pl->key.c_str(),nin,double(timing_clock()-t0)/1e6);}
    pl->pipes[h]=p;return p;}
SlotSt &slot_now(){SlotSt &st=S[slot_index];
    if(st.serial!=slot_serial){st.serial=slot_serial;st.recs.clear();st.by_bucket.clear();st.jobs.clear();st.bump.used=64;   // the slot's previous submission retired (recording_slot)
        for(auto &x:st.sets)x.second.used=0;}
    return st;}
// draw(), right before the NR-09 lane (after nrpo::decide): the plan of this draw (P).
void decide(uint32_t colors,bool special,int prim,int count,const p_draw_idx *indexed,uint32_t instances){
    P.on=false;if(mode<0)init();if(mode<=0)return;
    ++s.draws;const Shader *vs=state.shader[0];if(!vs || vs->psk!=1)return;
    const int cls_d=(!colors && state.rt.depth)?0:1;const uint64_t n=uint64_t(uint32_t(count))*(indexed?uint64_t(indexed->instances):instances);
    ++s.sk[cls_d];s.sk_idx[cls_d]+=n;
    auto fail=[&](int w){++s.why[w];s.why_idx[w]+=n;};
    if(state.shader[1] || state.shader[2] || state.shader[3]){fail(W_STAGES);return;}
    if(special){fail(W_SPECIAL);return;}
    if(topology(prim)==VK_PRIMITIVE_TOPOLOGY_POINT_LIST || (state.poly.mode!=2 && state.poly.mode!=1 && cfg.enabled_core.fillModeNonSolid)){fail(W_TOPO);return;}
    // the retype code draw() will compute (DM_GFX_VTX_RETYPE), and the streams the shader's inputs use
    uint64_t code=0;uint32_t vstreams=0;bool has_zero=false;
    for(size_t i=0;i<vs->inputs.size();i++){const uint32_t loc=vs->inputs[i];if(loc>=16){fail(W_ATTR);return;}va_st a;memcpy(&a,&state.attrib[loc],4);
        if(!a.fmt){has_zero=true;continue;}if(a.stream>=16){fail(W_ATTR);return;}vstreams|=1u<<a.stream;
        const VkFormat f=format(a.fmt);if(!(format_properties(f).bufferFeatures&VK_FORMAT_FEATURE_VERTEX_BUFFER_BIT)){fail(W_CONV);return;}
        if(vtx_retype_mode() && !vs->words.empty()){const uint32_t want=xbg_vertex_format_class(int(f));if(want!=vs->input_classes[i])code|=uint64_t(want+1)<<(2*loc);}}
    Plan *pl=plan_for(vs,code);if(!pl->ok){fail(W_PLAN);static unsigned told=0;if(told++<8)xbg_logf("[nr] preskin vs=%s code=%llx not planned: %s",vs->key.c_str(),(unsigned long long)code,pl->why.c_str());return;}
    if(pl->p.m>maxm){fail(W_WIDE);return;}
    const int zb=has_zero?xbg_vertex_zero_binding(state.attrib,vs->inputs.data(),vs->inputs.size()):-1;
    // the slice's inputs as the draw binds them
    uint64_t cur_loc[16]={},cur_slot[NRPS_SLOTS]={};uint32_t nverts=UINT32_MAX,streams=0,nin=0;In ins[16];Buffer vbuf[16];
    for(uint32_t l=0;l<16;l++)if(pl->p.slice_locs>>l&1){
        va_st a;memcpy(&a,&state.attrib[l],4);uint32_t icls=0;for(size_t i=0;i<vs->inputs.size();i++)if(vs->inputs[i]==l)icls=vs->input_classes[i];
        if(!a.fmt){if(zb<0){fail(W_ATTR);return;}ins[nin++]={l,0,0,0,icls,VK_FORMAT_UNDEFINED,true};cur_loc[l]=0x2E40ull;continue;}
        const uint32_t k=a.stream,stride=state.stream[k].stride;if(state.stream[k].divisor){fail(W_INST);return;}
        const VkFormat f=format(a.fmt);const uint32_t fsz=nrpo_fmt_size(uint32_t(f));if(!fsz || !stride){fail(W_STRIDE);return;}
        const NVNbufferRange r=state.vb[k];if(!(r.address && r.size)){fail(W_UNBOUND);return;}
        if(!pending_writebacks.empty() && overlaps_pending(r.address,r.size)){fail(W_PENDING);return;}
        nverts=std::min(nverts,nrps_nverts(r.size,stride,a.offset,fsz));
        if(mode!=2 && !(streams>>k&1)){snap_site=1;nrbuf::stride_hint=stride;vbuf[k]=snapshot(r.address,r.size);nrbuf::stride_hint=0;snap_site=0;}   // the draw's own call (a cache hit for it)
        streams|=1u<<k;
        cur_loc[l]=mode==2?nrps_id_attr(uint32_t(f),a.offset,stride,r.address,r.size,snapshot_epoch,0):nrps_id_attr(uint32_t(f),a.offset,stride,r.address,r.size,uint64_t(vbuf[k].buffer),vbuf[k].offset);
        ins[nin++]={l,k,a.offset,stride,icls,f,false};}
    if(nverts==UINT32_MAX || !nverts){fail(W_STRIDE);return;}
    if(nverts>maxv){fail(W_BIG);return;}
    VkDescriptorBufferInfo ubi[8]{};if(pl->slot.size()>8){fail(W_PLAN);return;}
    for(size_t i=0;i<pl->slot.size();i++){const uint32_t sl=pl->slot[i];const NVNbufferRange r=state.ub[0][sl];if(!(r.address && r.size)){fail(W_UNBOUND);return;}
        const size_t copy=std::min<size_t>(r.size,pl->bytes[i]?pl->bytes[i]:65536),nb=uniform_range(copy);
        if(!pending_writebacks.empty() && overlaps_pending(r.address,nb)){fail(W_PENDING);return;}
        if(mode==2){cur_slot[sl]=nrps_id_ubo(r.address,copy,snapshot_epoch,0);continue;}
        const Buffer u=uniform_snapshot(r.address,copy);   // the draw's descriptors took the same (address, copy): a cache hit
        if(u.offset%properties.limits.minUniformBufferOffsetAlignment){fail(W_ALIGN);return;}
        cur_slot[sl]=nrps_id_ubo(r.address,copy,uint64_t(u.buffer),u.offset);ubi[i]={u.buffer,u.offset,VkDeviceSize(nb)};}
    // the binding of the record: the highest the draw's inputs leave free (the zero stream takes the lowest)
    int pk=-1;for(int b=15;b>=0;b--)if(!(vstreams>>b&1) && b!=zb){pk=b;break;}if(pk<0){fail(W_BIND);return;}
    const int pc=cls_d;++s.elig[pc];s.elig_idx[pc]+=n;
    SlotSt &st=slot_now();
    const uint64_t bucket=nrps_mix(cur_slot[pl->bone_slot],0xB0E5ull);uint32_t pos[16];nrps_rec *hit=nullptr;
    {auto rg=st.by_bucket.equal_range(bucket);for(auto it=rg.first;it!=rg.second;++it){nrps_rec &r=st.recs[it->second];if(nrps_match(&r,pl->want,pl->nwant,cur_loc,cur_slot,nverts,pos)){hit=&r;break;}}}
    const uint32_t m=pl->p.m;
    if(hit){++hit->uses;if(hit->m==m && nrps_pos_identity(pos,m))++s.own[pl->cls];else ++s.sup[pl->cls];}
    else{nrps_rec r{};r.bucket=bucket;r.m=m;r.nverts=nverts;r.nvals=pl->nwant;memcpy(r.v,pl->want,sizeof(nrps_val)*pl->nwant);r.uses=1;
        for(uint32_t l=0;l<16;l++)if(pl->p.slice_locs>>l&1)r.loc_id[l]=cur_loc[l];for(uint32_t sl:pl->slot)r.slot_id[sl]=cur_slot[sl];
        const uint64_t bytes=uint64_t(nverts)*m*4;
        if(mode!=2){
            const uint64_t off=nrps_take(&st.bump,bytes+64,std::max<VkDeviceSize>(64,properties.limits.minStorageBufferOffsetAlignment));if(off==~0ull){fail(W_ARENA);return;}
            r.off=off;
            const VkPipeline pipe=slice_pipe(pl,ins,nin,zb<0?0u:uint32_t(zb));if(!pipe){fail(W_PIPE);return;}
            Job j;j.pipe=pipe;j.pl=pl->pl;j.nverts=nverts;
            Sets &ss=st.sets[pl];
            if(ss.used==ss.v.size()){VkDescriptorSetAllocateInfo ai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};ai.descriptorPool=st.pool;ai.descriptorSetCount=1;ai.pSetLayouts=&pl->dsl;
                VkDescriptorSet ns{};if(vkAllocateDescriptorSets(cfg.device,&ai,&ns)!=VK_SUCCESS){fail(W_POOL);st.bump.used=off;return;}ss.v.push_back(ns);}
            j.set=ss.v[ss.used++];
            VkWriteDescriptorSet wr[9]{};VkDescriptorBufferInfo sb{st.buf,off,VkDeviceSize(bytes)};uint32_t nw=0;
            for(size_t i=0;i<pl->slot.size();i++){VkWriteDescriptorSet &x=wr[nw++];x.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;x.dstSet=j.set;x.dstBinding=pl->p.slice_ubos[i];x.descriptorCount=1;x.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;x.pBufferInfo=&ubi[i];}
            {VkWriteDescriptorSet &x=wr[nw++];x.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;x.dstSet=j.set;x.dstBinding=pl->p.ssbo_binding;x.descriptorCount=1;x.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;x.pBufferInfo=&sb;}
            vkUpdateDescriptorSets(cfg.device,nw,wr,0,nullptr);
            for(uint32_t k=0;k<16;k++)if(streams>>k&1){j.bind[j.nb]=k;j.vb[j.nb]=vbuf[k].buffer;j.off[j.nb]=vbuf[k].offset;j.nb++;}
            if(zb>=0){bool z=false;for(uint32_t i=0;i<nin;i++)z|=ins[i].zero;if(z){j.bind[j.nb]=uint32_t(zb);j.vb[j.nb]=st.buf;j.off[j.nb]=0;j.nb++;}}
            if(mode==1)st.jobs.push_back(j);++s.jobs;}
        ++s.recs[pl->cls];s.rec_verts[pl->cls]+=nverts;s.rec_bytes+=bytes;
        const uint32_t ix=uint32_t(st.recs.size());st.recs.push_back(r);st.by_bucket.emplace(bucket,ix);hit=&st.recs.back();
        for(uint32_t j2=0;j2<m;j2++)pos[j2]=j2;
        s.ops_slice+=uint64_t(nverts)*pl->p.ops_slice;s.cyc_slice+=uint64_t(nverts*cyc_slice_k[pl->cls]);}
    Cons *c=cons_for(pl,pos,nrps_pos_hash(pos,m,hit->m));if(!c){fail(W_CONS);return;}
    s.ops_saved+=n*(pl->p.ops_orig-pl->p.ops_cons);s.cyc_saved+=uint64_t(double(n)*cyc_saved_k[pl->cls]);
    ++s.applied[pc];s.applied_idx[pc]+=n;
    if(mode==2)return;
    P.on=true;P.k=uint32_t(pk);P.stride=hit->m*4;P.pl=pl;P.c=c;P.code=code;P.lay_id=c->id;
    P.view=Buffer{};P.view.buffer=st.buf;P.view.memory=st.mem;P.view.offset=hit->off;P.view.size=size_t(uint64_t(hit->nverts)*hit->m*4);P.view.mapped=st.map+hit->off;P.view.coherent=st.coh;}
// draw()'s old path, after the vertex-stage module picks (retype, NR-32, IDVS) and NR-POSONLY's rewrite: the consumer module (NR-32-trimmed
// like the module it replaces when the pipeline's fragment shader reads fewer varyings) and the vertex input: attributes the consumer no
// longer reads go, the record's groups come on binding P.k (stride P.stride). Checked first, changed only when both can be: a retype code
// other than the plan's (code_draw: draw()'s xlq_vi) or a taken binding drops the plan for this draw (nothing changed).
void apply_old(std::vector<VkPipelineShaderStageCreateInfo> &stages,uint64_t code_draw,const Shader *fs,std::vector<VkVertexInputAttributeDescription> &attrs,
               VkVertexInputBindingDescription slots[16],uint32_t &used,int zero){
    if(code_draw!=P.code || int(P.k)==zero || (used>>P.k&1)){P.on=false;++s.code_mismatch;return;}
    VkShaderModule m=P.c->mod;
    if((nr_xlq || xlq_twin) && fs){const int xm=fs->nm_is_twin && xlq_twin?1:nr_xlq;
        if((xm==1 || xm==3) && fs->vo_read!=XBG_VSOUT_ALL){const auto key=std::make_tuple(fs->vo_read,fs->vo_decl,xm);auto f=P.c->trim.find(key);
            if(f!=P.c->trim.end())m=f->second;
            else{std::vector<uint32_t> out;const uint64_t keep=xlq_keep(fs->vo_read,xm);VkShaderModule t=m;
                if(xbg_spirv_vsout_trim(P.c->words.data(),P.c->words.size(),keep,out,nullptr,fs->vo_decl) && !*xbg_spirv_vsout_check(P.c->words.data(),P.c->words.size(),out.data(),out.size(),keep)){
                    VkShaderModuleCreateInfo mc{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};mc.codeSize=out.size()*4;mc.pCode=out.data();gpguard::ModuleLock serial;
                    if(vkCreateShaderModule(cfg.device,&mc,nullptr,&t)!=VK_SUCCESS)t=m;}
                P.c->trim[key]=t;m=t;}}}
    for(auto &x:stages)if(x.stage==VK_SHADER_STAGE_VERTEX_BIT)x.module=m;
    const uint32_t keep=P.pl->p.cons_locs;size_t o=0;for(size_t i=0;i<attrs.size();i++)if(keep>>attrs[i].location&1)attrs[o++]=attrs[i];attrs.resize(o);
    static const VkFormat uf[5]={VK_FORMAT_UNDEFINED,VK_FORMAT_R32_UINT,VK_FORMAT_R32G32_UINT,VK_FORMAT_R32G32B32_UINT,VK_FORMAT_R32G32B32A32_UINT};
    for(uint32_t g=0;g<P.c->lay.groups;g++)attrs.push_back({P.c->lay.loc[g],P.k,uf[P.c->lay.width[g]],4*P.c->lay.first[g]});
    slots[P.k]={P.k,P.stride,VK_VERTEX_INPUT_RATE_VERTEX};used|=1u<<P.k;}
// the NR-09 lane's variant word 4 (bits 40-43 the record binding, 44-63 the consumer layout id; 0 = not planned)
inline uint64_t lane_bits(){return P.on?(uint64_t(P.k)<<40 | uint64_t(P.lay_id)<<44):0;}
// submit_slots(): this slot's slices, recorded into its prologue command buffer (ahead of the slot's buffer in the same submission)
bool has_jobs(unsigned si){return mode==1 && S[si].serial==slot_serial && !S[si].jobs.empty();}
void prologue(unsigned si,VkCommandBuffer cb){
    SlotSt &st=S[si];if(st.jobs.empty())return;
    if(!st.coh)nrbuf::flush(st.mem,0,64);
    VkRenderPassBeginInfo b{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};b.renderPass=rp;b.framebuffer=fb;b.renderArea={{0,0},{1,1}};
    vkCmdBeginRenderPass(cb,&b,VK_SUBPASS_CONTENTS_INLINE);VkPipeline cur{};
    for(const Job &j:st.jobs){if(j.pipe!=cur){vkCmdBindPipeline(cb,VK_PIPELINE_BIND_POINT_GRAPHICS,j.pipe);cur=j.pipe;}
        vkCmdBindDescriptorSets(cb,VK_PIPELINE_BIND_POINT_GRAPHICS,j.pl,0,1,&j.set,0,nullptr);
        for(uint32_t i=0;i<j.nb;i++)vkCmdBindVertexBuffers(cb,j.bind[i],1,&j.vb[i],&j.off[i]);
        vkCmdDraw(cb,j.nverts,1,0,0);}
    vkCmdEndRenderPass(cb);peak=std::max<uint64_t>(peak,st.bump.used);st.jobs.clear();}
void tick(){if(mode<=0)return;const uint64_t now=timing_clock();if(!next_ns){next_ns=now+10000000000ull;frames0=stats.presents.load();return;}if(now<next_ns)return;next_ns=now+10000000000ull;
    const uint64_t f1=stats.presents.load();const double fr=f1>frames0?double(f1-frames0):1.;frames0=f1;
    std::string w;for(int i=0;i<W_N;i++)if(s.why[i]){char b[96];snprintf(b,sizeof b,"%s%s %.1f (%.2f M idx)",w.empty()?"":", ",why_name[i],s.why[i]/fr,s.why_idx[i]/fr/1e6);w+=b;}
    size_t np=0,nr=0,nc=0,nsp=0;for(auto &p:plans){if(p.second->ok)np++;else nr++;nc+=p.second->cons.size();nsp+=p.second->pipes.size();}
    const double net=double(s.cyc_saved)-double(s.cyc_slice);
    xbg_logf("[nr] preskin (DM_NR_PRESKIN=%d, NR-PRESKIN, last 10 s, %.0f frames): draws %.1f a frame; skinned depth-only %.1f (%.3f M indices) / colour %.1f (%.3f M); "
        "eligible %.1f / %.1f; %s depth-only %.1f (%.3f M idx) / colour %.1f (%.3f M); records a frame: position-class %.1f (%.1f k vertices) / wider %.1f (%.1f k), %.2f MB; "
        "reuse: own %.1f / %.1f, another shader's record %.1f / %.1f draws (draws per record %.2f / %.2f); model (SPIR-V body ops) saved %.2f M - slice %.2f M; "
        "malioc G57 model [m, every index shaded]: saved %.2f M cycles - slice %.2f M = %.2f M (%.2f ms at 1.9 Gcycle/s, G57 MC2); slices recorded %.1f a frame, arena peak %.2f MB of %llu; "
        "plans %zu (refused %zu), consumers %zu, slice pipelines %zu; code mismatch %llu; not: %s",
        mode,fr,s.draws/fr,s.sk[0]/fr,s.sk_idx[0]/fr/1e6,s.sk[1]/fr,s.sk_idx[1]/fr/1e6,s.elig[0]/fr,s.elig[1]/fr,mode==2?"would apply":"applied",
        s.applied[0]/fr,s.applied_idx[0]/fr/1e6,s.applied[1]/fr,s.applied_idx[1]/fr/1e6,s.recs[0]/fr,s.rec_verts[0]/fr/1e3,s.recs[1]/fr,s.rec_verts[1]/fr/1e3,s.rec_bytes/fr/1048576.,
        s.own[0]/fr,s.own[1]/fr,s.sup[0]/fr,s.sup[1]/fr,s.recs[0]?double(s.own[0]+s.sup[0]+s.recs[0])/double(s.recs[0]):0.,s.recs[1]?double(s.own[1]+s.sup[1]+s.recs[1])/double(s.recs[1]):0.,
        s.ops_saved/fr/1e6,s.ops_slice/fr/1e6,s.cyc_saved/fr/1e6,s.cyc_slice/fr/1e6,net/fr/1e6,net/fr/1.9e6,s.jobs/fr,peak/1048576.,(unsigned long long)(asize>>20),
        np,nr,nc,nsp,(unsigned long long)s.code_mismatch,w.empty()?"-":w.c_str());
    s=Stats{};peak=0;}
// shutdown (the queue idle)
void release(){
    for(auto &p:plans){Plan &x=*p.second;for(auto &q:x.pipes)if(q.second)vkDestroyPipeline(cfg.device,q.second,nullptr);
        for(auto &c:x.cons){if(c.second->mod)vkDestroyShaderModule(cfg.device,c.second->mod,nullptr);for(auto &t:c.second->trim)if(t.second && t.second!=c.second->mod)vkDestroyShaderModule(cfg.device,t.second,nullptr);}
        if(x.pl)vkDestroyPipelineLayout(cfg.device,x.pl,nullptr);if(x.dsl)vkDestroyDescriptorSetLayout(cfg.device,x.dsl,nullptr);if(x.slice)vkDestroyShaderModule(cfg.device,x.slice,nullptr);}
    plans.clear();
    for(auto &st:S){if(st.pool)vkDestroyDescriptorPool(cfg.device,st.pool,nullptr);if(st.buf){vkDestroyBuffer(cfg.device,st.buf,nullptr);vkFreeMemory(cfg.device,st.mem,nullptr);}st=SlotSt{};}
    if(fb)vkDestroyFramebuffer(cfg.device,fb,nullptr);if(rp)vkDestroyRenderPass(cfg.device,rp,nullptr);fb={};rp={};P=Plan_t{};if(mode>0)mode=-1;}
}
