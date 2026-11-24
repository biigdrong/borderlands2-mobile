#include <sys/system_properties.h>
#include <unordered_map>
#include <cmath>
// 安卓Vulkan呈现与窗口生命周期；依据原WSI桥及PR9/10的可回退呈现/钉核实验。
// Android Vulkan presentation and window lifetimes, based on the original WSI bridge and reversible PR9/10 overlap/affinity experiments.
#define VK_USE_PLATFORM_ANDROID_KHR
#include "vulkan_present.h"
#ifdef DM_GAME_DOOM
extern "C" void dm_aperf_present(ANativeWindow*,float);
#endif
#include "../gfx/vulkan/nvn_vk.h"
#include "../gfx/xtrace.h"
#include "../host/cpu_topo.h"   // [cpu-place] the translator's pin comes from the placement plan unless a marker sets it
#include <android/log.h>
#include <android/native_window.h>
#include <dlfcn.h>
#include <algorithm>
#include <vector>
#include <string>
#include <mutex>
#include <atomic>
#include <condition_variable>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstddef>
#include <cerrno>
#include <sched.h>
#include <unistd.h>
#include <time.h>
extern "C" { int dm_vk_compr_ctl=0; PFN_vkGetPhysicalDeviceImageFormatProperties2 dm_vk_ifp2=nullptr; }   // [DOS2] NR-UBWC (DM_NR_UBWC != 0): bit 0 VK_EXT_image_compression_control enabled (the driver tells per image whether UBWC / AFBC is on), bit 1 also its _swapchain feature
static void nrubwc_swapchain_report(VkDevice device,const std::vector<VkImage> &images,VkFormat fmt);
// [nonadreno] (from the DOOM 2016 port, 7c0da0e) Mali: vkWaitForFences returns VK_ERROR_INITIALIZATION_FAILED when its ppoll() is
// interrupted by a signal (Skyline fence_cycle.h cbc896c8f8, idea only); retried. Other results unchanged, so Adreno sees the same calls.
static VkResult dm_present_wait_fences(VkDevice d,uint32_t n,const VkFence *f,VkBool32 all,uint64_t timeout){
    VkResult r=vkWaitForFences(d,n,f,all,timeout);
    for(unsigned tries=0;r==VK_ERROR_INITIALIZATION_FAILED && tries<1000;++tries)r=vkWaitForFences(d,n,f,all,timeout);
    return r;}
#define vkWaitForFences dm_present_wait_fences
// [present-thread] PERF-D07 DM_GFX_PRESENT_THREAD (port-common/modules/present-thread): with the present thread on, two threads use the
// one VkQueue, so every queue call of this file takes queue_mutex (the engine's take it through dm_present_queue_lock); the blit's
// submission and the queue present of the job the present thread runs are reported to the hand-off (present_thread.h). Mode 0: no lock.
#include "present_thread.h"
#include "../gfx/nr/nr_present.h"   // [DOS2] NR-11 DM_NR_PRESENT: reasons and dm_nrp_img (the engine's side: engine/xbg_nr_present.inc)
#include "../gfx/nr/nr_rotate.h"    // [DOS2] NR-20 DM_NR_ROTATE: decisions and geometry of the pre-rotation (namespace nrr)
#include <cstdarg>
static std::atomic<int> pt_cfg{0};static std::mutex pt_queue_mutex;static thread_local bool pt_on_thread=false;
static void pt_mark_submitted(void);static void pt_stamp_present(void);
struct PtQLock{bool on;PtQLock():on(pt_cfg.load(std::memory_order_relaxed)!=0){if(on)pt_queue_mutex.lock();}~PtQLock(){if(on)pt_queue_mutex.unlock();}};
static VkResult pt_queue_submit(VkQueue q,uint32_t n,const VkSubmitInfo *s,VkFence f){VkResult r;{PtQLock l;r=vkQueueSubmit(q,n,s,f);}if(r==VK_SUCCESS && pt_on_thread)pt_mark_submitted();return r;}
static VkResult pt_queue_present(VkQueue q,const VkPresentInfoKHR *p){VkResult r;{PtQLock l;r=vkQueuePresentKHR(q,p);}if(pt_on_thread)pt_stamp_present();return r;}
static VkResult pt_queue_wait_idle(VkQueue q){PtQLock l;return vkQueueWaitIdle(q);}
#define vkQueueSubmit pt_queue_submit
#define vkQueuePresentKHR pt_queue_present
#define vkQueueWaitIdle pt_queue_wait_idle
extern "C" double dm_present_period(void);
#ifdef DM_GAME_DOS2
extern "C" float dm_dos2_fps_vote(float marker);   // gfx/vulkan/nvn_vk.c: the window vote for DM_DOS2_FPS
#endif
// 错过上屏节拍的帧数（晚于「上次期望时刻 + 周期」2 ms 以上）；自适应出图档按它降档 / 试升
// Frames that missed their display slot (more than 2 ms later than "previous desired time + period"); the adaptive present tier steps down / probes up by it
static std::atomic<uint64_t> dm_present_late{0};
extern "C" uint64_t dm_present_late_count(void){return dm_present_late.load(std::memory_order_relaxed);}
namespace {
std::mutex window_mutex;std::condition_variable window_cv;
// Vulkan状态仅宿主线程使用；UI锁只保护窗口快照，不跨GPU等待。
// Serialize Vulkan callers separately; never hold the UI window lock across GPU waits.
std::mutex render_mutex;
ANativeWindow *desired=nullptr,*active=nullptr;uint64_t generation=0,active_generation=0;
VkInstance instance;VkPhysicalDevice physical;VkDevice device;VkQueue queue;uint32_t family;
VkSurfaceKHR surface;VkSwapchainKHR swapchain;VkFormat swap_format;VkExtent2D extent;
VkSurfaceTransformFlagBitsKHR created_transform;VkExtent2D created_surface_extent;
// 无旋转 blit 由系统合成器旋转；记录属性以免 SUBOPTIMAL 触发逐帧重建。
// The compositor rotates our unrotated blit; cache properties to avoid rebuilding every SUBOPTIMAL frame.
bool surface_properties_changed(){
    VkSurfaceCapabilitiesKHR c{};
    if(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&c)!=VK_SUCCESS)return true;
    return c.currentTransform!=created_transform || c.currentExtent.width!=created_surface_extent.width || c.currentExtent.height!=created_surface_extent.height;
}
std::vector<VkImage> images;VkCommandPool command_pool;VkCommandBuffer command;
VkSemaphore acquired;std::vector<VkSemaphore> finished;VkFence fence;bool ready=false,swap_dirty=false;std::string shader_path;
// [DOS2] NR-11 DM_NR_PRESENT (docs/dos2/nr/NR-11.md; the rules: gfx/nr/nr_present.h). 1 / 3: the swapchain images are also colour
// attachments (and copy sources), each gets a view, and the engine renders the frame's last passes straight into an acquired image, so the
// present of such a frame is only vkQueuePresentKHR. With the present thread on, that thread acquires the next image right after each job
// ("parks" it, off the translation thread) and the engine takes it; inline, the engine acquires with timeout 0. A frame the engine does not
// take, or takes and then presents by the old blit (pre_index), is presented as before. 2: nothing changes here (the engine counts only;
// the snapshot answers its questions). 0 / unset: no change at all (usage, views, parking, snapshot: none).
namespace nrp {
int mode=0;
std::vector<VkImageView> views;bool usage_ok=false;uint64_t gen=0;
std::mutex mu;   // park, taken, snap: the translation thread reads them without render_mutex
struct Park{bool have=false;uint32_t index=0;VkSemaphore sem=VK_NULL_HANDLE;uint64_t gen=0;bool sub=false;} park;bool taken=false;
// Acquire semaphores of parked / taken images: a ring, one per acquire. A semaphore comes round again 6 acquires later; by then the batch
// that waited on it has retired (the engine reuses a slot only after its fence: two slots), and so has the blit that waited on one.
VkSemaphore ring[6]{};unsigned ring_next=0;
struct Snap{uint64_t gen=0;VkFormat fmt=VK_FORMAT_UNDEFINED;uint32_t w=0,h=0;bool usage_ok=false,identity=true;std::vector<VkImage> images;std::vector<VkImageView> views;std::vector<VkSemaphore> finished;} snap;
std::atomic<uint64_t> parks{0},park_fails{0},takes{0},direct{0},blits{0},lost{0};
inline bool on(){return mode==1 || mode==3;}
VkSemaphore next_sem(){VkSemaphore &s=ring[ring_next++%6];if(!s){VkSemaphoreCreateInfo sc{VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};if(vkCreateSemaphore(device,&sc,nullptr,&s))s=VK_NULL_HANDLE;}return s;}
// The swapchain goes (queue idle): views, the parked image (its semaphore may hold the signal of an acquire nobody waits for: replaced).
void drop(){for(auto v:views)if(v)vkDestroyImageView(device,v,nullptr);views.clear();
    std::lock_guard<std::mutex> l(mu);if(park.have){for(auto &s:ring)if(s==park.sem){vkDestroySemaphore(device,s,nullptr);s=VK_NULL_HANDLE;}}park=Park{};taken=false;snap=Snap{};}
int check(VkFormat fmt,uint32_t w,uint32_t h,bool need_views){   // under mu
    if(!snap.gen)return NRP_P_NO_SWAPCHAIN;if(!snap.identity)return NRP_P_ROTATED;if(!snap.usage_ok || (need_views && snap.views.empty()))return NRP_P_USAGE;
    if(snap.fmt!=fmt)return NRP_P_FORMAT;if(snap.w!=w || snap.h!=h)return NRP_P_EXTENT;return NRP_P_OK;}
}
// [DOS2] NR-20 DM_NR_ROTATE (docs/dos2/nr/NR-20.md; the rules and the geometry: gfx/nr/nr_rotate.h). 1 / 3: when the surface is turned
// (currentTransform ROTATE_90 / 180 / 270; the phone: 2 / 8) the swapchain takes preTransform = currentTransform and the panel's orientation,
// and present_body draws the window texture turned into the image (one draw, shaders/nr_rotate.*) instead of the blit, so the compositor
// shows the image as it is. NR-11 refuses such a swapchain (snap.identity). 2: the identity swapchain and the blit as before; the decision
// is logged, the objects are made, and every NRR_PROBE_EVERY presents the turned draw goes into an image of its own and NRR_PROBES of its
// pixels are compared with the window texture's (red lines). 3: as 1, the image is cleared magenta first (what the draw misses shows).
// 0 / unset: nothing (one compare per swapchain and per present). Everything here runs under render_mutex.
// RCAS (DM_GFX_SHARPEN; docs/dos2/nr/NR-20-rcas.md): the turned draw sharpens itself (shaders/nr_rotate_rcas.frag, pipe[2]), one pass in
// place of RCAS + blit; mode 2 probes it against RCAS's own image of the old path (pipe[3]). No pipeline: identity + RCAS + blit as before.
namespace nrr {
const uint32_t vs_code[]={
#include "shaders/nr_rotate.vert.spv.inc"
};
const uint32_t fs_code[]={
#include "shaders/nr_rotate.frag.spv.inc"
};
const uint32_t fs_rcas_code[]={
#include "shaders/nr_rotate_rcas.frag.spv.inc"
};
// the sharpening draw's push constants: nr_rotate.vert's 6 floats, then (from NRR_RCAS_PC_OFFSET) nr_rotate_rcas.frag's block
struct RcasPush{float vm[6];float pad[2];nrr_rcas_pc r;};
static_assert(offsetof(RcasPush,r)==NRR_RCAS_PC_OFFSET && sizeof(RcasPush)==92,"nr_rotate_rcas.frag push-constant layout");
int mode=0;
inline bool on(){return mode==NRR_MODE_ON || mode==NRR_MODE_POISON;}
VkSurfaceTransformFlagBitsKHR pre=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;   // this swapchain's preTransform (IDENTITY: the old blit)
VkExtent2D img{};int reason=NRR_R_OFF;uint32_t turn=0,last_transform=0;bool failed=false;unsigned polls=0;
// per device: set layout, pipeline layout, samplers ([0] nearest, [1] linear), pool, a set per flight; per format: render passes and the
// pipelines (rp [0] load DONT_CARE = the draw covers the image, [1] CLEAR = letterbox bars / poison: compatible, pipe[0]; [2] mode 2's probe
// image, ends in TRANSFER_SRC, other dependencies: pipe[1], made only with =2; with RCAS on also the sharpening draw: pipe[2] on rp[0] / [1],
// pipe[3] on rp[2] (=2), layout_rcas); per swapchain: views and framebuffers; per flight: the window texture's view
VkDescriptorSetLayout dsl{};VkPipelineLayout layout{},layout_rcas{};VkDescriptorPool pool{};VkDescriptorSet sets[2]{};VkSampler samp[2]{};
VkFormat pfmt=VK_FORMAT_UNDEFINED;VkRenderPass rp[3]{};VkPipeline pipe[4]{};bool rcas_want=false;
std::vector<VkImageView> views;std::vector<VkFramebuffer> fbs;VkImageView src_view[2]{};
struct Probe{VkImage img{};VkDeviceMemory mem{};VkImageView view{};VkFramebuffer fb{};uint32_t w=0,h=0;VkFormat fmt=VK_FORMAT_UNDEFINED;
    VkBuffer buf{};VkDeviceMemory bmem{};void *map=nullptr;bool coherent=false,pend[2]{},sharp[2]{};int fi[2]{},fs[2]{};int32_t px[2][NRR_PROBES],py[2][NRR_PROBES],sx[2][NRR_PROBES],sy[2][NRR_PROBES];} probe;
uint64_t presents=0,drawn=0,blits=0,swaps=0,rotated_swaps=0,turns=0,probes_ok=0,probes_bad=0,probes_skipped=0,probe_frames=0;unsigned red_lines=0;double next_line=0;
uint64_t sharp_draws=0,sharp_plain=0,probes_rcas=0;   // turned draws that sharpened / that should have but could not (linear filter, no pipeline); RCAS probes
void red(const char *fmt,...){if(red_lines>=16)return;++red_lines;char t[512];va_list a;va_start(a,fmt);vsnprintf(t,sizeof t,fmt,a);va_end(a);__android_log_print(ANDROID_LOG_WARN,"dm-vulkan","【红】[nr] rotate: %s",t);}
uint32_t mem_type(uint32_t bits,VkMemoryPropertyFlags want){VkPhysicalDeviceMemoryProperties mp;vkGetPhysicalDeviceMemoryProperties(physical,&mp);for(uint32_t i=0;i<mp.memoryTypeCount;i++)if((bits&(1u<<i)) && (mp.memoryTypes[i].propertyFlags&want)==want)return i;return UINT32_MAX;}
// The objects for swapchain format f (and, want_rcas, the sharpening draw's). NRR_R_OK, NRR_R_PIPELINE (the plain draw's failed: the swapchain
// stays identity) or NRR_R_SHARPEN (only the sharpening draw's failed: identity, the old RCAS + blit).
int setup(VkFormat f,bool want_rcas){
    if(!dsl){
        VkDescriptorSetLayoutBinding b{};b.binding=0;b.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;b.descriptorCount=1;b.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT;
        VkDescriptorSetLayoutCreateInfo dl{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};dl.bindingCount=1;dl.pBindings=&b;if(vkCreateDescriptorSetLayout(device,&dl,nullptr,&dsl)){dsl=VK_NULL_HANDLE;return NRR_R_PIPELINE;}
        VkPushConstantRange pc{VK_SHADER_STAGE_VERTEX_BIT,0,6*sizeof(float)};VkPipelineLayoutCreateInfo pl{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};pl.setLayoutCount=1;pl.pSetLayouts=&dsl;pl.pushConstantRangeCount=1;pl.pPushConstantRanges=&pc;
        if(vkCreatePipelineLayout(device,&pl,nullptr,&layout)){layout=VK_NULL_HANDLE;return NRR_R_PIPELINE;}
        VkDescriptorPoolSize ps{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,2};VkDescriptorPoolCreateInfo dp{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};dp.maxSets=2;dp.poolSizeCount=1;dp.pPoolSizes=&ps;
        if(vkCreateDescriptorPool(device,&dp,nullptr,&pool)){pool=VK_NULL_HANDLE;return NRR_R_PIPELINE;}
        VkDescriptorSetLayout ls[2]={dsl,dsl};VkDescriptorSetAllocateInfo ai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};ai.descriptorPool=pool;ai.descriptorSetCount=2;ai.pSetLayouts=ls;if(vkAllocateDescriptorSets(device,&ai,sets))return NRR_R_PIPELINE;
        for(int i=0;i<2;i++){VkSamplerCreateInfo si{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};si.magFilter=si.minFilter=i?VK_FILTER_LINEAR:VK_FILTER_NEAREST;si.mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST;
            si.addressModeU=si.addressModeV=si.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;si.maxLod=0;if(vkCreateSampler(device,&si,nullptr,&samp[i])){samp[i]=VK_NULL_HANDLE;return NRR_R_PIPELINE;}}
    }
    if(pfmt==f && pipe[0] && (mode!=NRR_MODE_CHECK || pipe[1]) && (!want_rcas || (pipe[2] && (mode!=NRR_MODE_CHECK || pipe[3]))))return NRR_R_OK;
    for(auto &q:pipe)if(q){vkDestroyPipeline(device,q,nullptr);q=VK_NULL_HANDLE;}for(auto &p:rp)if(p){vkDestroyRenderPass(device,p,nullptr);p=VK_NULL_HANDLE;}pfmt=VK_FORMAT_UNDEFINED;
    for(int k=0;k<3;k++){
        VkAttachmentDescription at{};at.format=f;at.samples=VK_SAMPLE_COUNT_1_BIT;at.loadOp=k?VK_ATTACHMENT_LOAD_OP_CLEAR:VK_ATTACHMENT_LOAD_OP_DONT_CARE;at.storeOp=VK_ATTACHMENT_STORE_OP_STORE;
        at.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE;at.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE;at.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;at.finalLayout=k==2?VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL:VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        VkAttachmentReference ar{0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};VkSubpassDescription sp{};sp.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS;sp.colorAttachmentCount=1;sp.pColorAttachments=&ar;
        // in: the acquire semaphore waits at COLOR_ATTACHMENT_OUTPUT (the submit below), so the layout transition comes after the presentation
        // engine let go of the image; the probe image: after the last probe's copy. out: to the present (semaphore) / to the probe's copy
        VkSubpassDependency dep[2]{};dep[0].srcSubpass=VK_SUBPASS_EXTERNAL;dep[0].dstSubpass=0;dep[0].srcStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT|(k==2?VK_PIPELINE_STAGE_TRANSFER_BIT:0);
        dep[0].dstStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;dep[0].srcAccessMask=0;dep[0].dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        dep[1].srcSubpass=0;dep[1].dstSubpass=VK_SUBPASS_EXTERNAL;dep[1].srcStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;dep[1].srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        dep[1].dstStageMask=k==2?VK_PIPELINE_STAGE_TRANSFER_BIT:VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT;dep[1].dstAccessMask=k==2?VK_ACCESS_TRANSFER_READ_BIT:0;
        VkRenderPassCreateInfo rc{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};rc.attachmentCount=1;rc.pAttachments=&at;rc.subpassCount=1;rc.pSubpasses=&sp;rc.dependencyCount=2;rc.pDependencies=dep;
        if(vkCreateRenderPass(device,&rc,nullptr,&rp[k])){rp[k]=VK_NULL_HANDLE;return NRR_R_PIPELINE;}
    }
    VkShaderModule vm{},fm{};VkShaderModuleCreateInfo mi{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};mi.codeSize=sizeof vs_code;mi.pCode=vs_code;VkResult r=vkCreateShaderModule(device,&mi,nullptr,&vm);
    mi.codeSize=sizeof fs_code;mi.pCode=fs_code;if(!r)r=vkCreateShaderModule(device,&mi,nullptr,&fm);
    VkPipelineShaderStageCreateInfo ss[2]{};for(auto &s:ss){s.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;s.pName="main";}ss[0].stage=VK_SHADER_STAGE_VERTEX_BIT;ss[0].module=vm;ss[1].stage=VK_SHADER_STAGE_FRAGMENT_BIT;ss[1].module=fm;
    VkPipelineVertexInputStateCreateInfo vi{VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};VkPipelineInputAssemblyStateCreateInfo ia{VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};ia.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    VkPipelineViewportStateCreateInfo vs{VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};vs.viewportCount=1;vs.scissorCount=1;
    VkPipelineRasterizationStateCreateInfo rs{VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};rs.polygonMode=VK_POLYGON_MODE_FILL;rs.cullMode=VK_CULL_MODE_NONE;rs.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE;rs.lineWidth=1;
    VkPipelineMultisampleStateCreateInfo ms{VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};ms.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT;
    VkPipelineColorBlendAttachmentState ba{};ba.colorWriteMask=0xf;VkPipelineColorBlendStateCreateInfo cb{VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};cb.attachmentCount=1;cb.pAttachments=&ba;
    VkDynamicState dyn[]={VK_DYNAMIC_STATE_VIEWPORT,VK_DYNAMIC_STATE_SCISSOR};VkPipelineDynamicStateCreateInfo dy{VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO};dy.dynamicStateCount=2;dy.pDynamicStates=dyn;
    VkGraphicsPipelineCreateInfo gp{VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};gp.stageCount=2;gp.pStages=ss;gp.pVertexInputState=&vi;gp.pInputAssemblyState=&ia;gp.pViewportState=&vs;gp.pRasterizationState=&rs;
    gp.pMultisampleState=&ms;gp.pColorBlendState=&cb;gp.pDynamicState=&dy;gp.layout=layout;gp.renderPass=rp[0];gp.subpass=0;
    if(!r)r=vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&gp,nullptr,&pipe[0]);
    if(!r && mode==NRR_MODE_CHECK){gp.renderPass=rp[2];r=vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&gp,nullptr,&pipe[1]);}
    if(fm)vkDestroyShaderModule(device,fm,nullptr);
    if(r){if(vm)vkDestroyShaderModule(device,vm,nullptr);for(auto &q:pipe)if(q){vkDestroyPipeline(device,q,nullptr);q=VK_NULL_HANDLE;}return NRR_R_PIPELINE;}
    pfmt=f;if(!want_rcas){vkDestroyShaderModule(device,vm,nullptr);return NRR_R_OK;}
    // the sharpening draw: the same state (vm kept for it), nr_rotate_rcas.frag, a layout whose one push range covers both stages' blocks
    if(!layout_rcas){VkPushConstantRange pc{VK_SHADER_STAGE_VERTEX_BIT|VK_SHADER_STAGE_FRAGMENT_BIT,0,uint32_t(sizeof(RcasPush))};VkPipelineLayoutCreateInfo pl{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
        pl.setLayoutCount=1;pl.pSetLayouts=&dsl;pl.pushConstantRangeCount=1;pl.pPushConstantRanges=&pc;if(vkCreatePipelineLayout(device,&pl,nullptr,&layout_rcas))layout_rcas=VK_NULL_HANDLE;}
    VkShaderModule rm{};mi.codeSize=sizeof fs_rcas_code;mi.pCode=fs_rcas_code;r=layout_rcas?vkCreateShaderModule(device,&mi,nullptr,&rm):VK_ERROR_INITIALIZATION_FAILED;
    ss[1].module=rm;gp.layout=layout_rcas;gp.renderPass=rp[0];
    if(!r)r=vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&gp,nullptr,&pipe[2]);
    if(!r && mode==NRR_MODE_CHECK){gp.renderPass=rp[2];r=vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&gp,nullptr,&pipe[3]);}
    vkDestroyShaderModule(device,vm,nullptr);if(rm)vkDestroyShaderModule(device,rm,nullptr);
    if(r){for(int i=2;i<4;i++)if(pipe[i]){vkDestroyPipeline(device,pipe[i],nullptr);pipe[i]=VK_NULL_HANDLE;}red("the sharpening turned draw's pipeline failed (VkResult %d): RCAS stays on the old identity swapchain + blit",int(r));return NRR_R_SHARPEN;}
    return NRR_R_OK;
}
void drop_probe(){if(probe.fb)vkDestroyFramebuffer(device,probe.fb,nullptr);if(probe.view)vkDestroyImageView(device,probe.view,nullptr);if(probe.img)vkDestroyImage(device,probe.img,nullptr);if(probe.mem)vkFreeMemory(device,probe.mem,nullptr);
    probe.fb=VK_NULL_HANDLE;probe.view=VK_NULL_HANDLE;probe.img=VK_NULL_HANDLE;probe.mem=VK_NULL_HANDLE;probe.w=probe.h=0;probe.pend[0]=probe.pend[1]=false;}
// The swapchain goes (queue idle): its views and framebuffers, the flights' views of the window texture, mode 2's probe image.
void drop(){for(auto b:fbs)if(b)vkDestroyFramebuffer(device,b,nullptr);fbs.clear();for(auto v:views)if(v)vkDestroyImageView(device,v,nullptr);views.clear();
    for(auto &v:src_view)if(v){vkDestroyImageView(device,v,nullptr);v=VK_NULL_HANDLE;}drop_probe();pre=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;img=VkExtent2D{};}
// The device goes (cleanup_initialization, queue idle).
void destroy_all(){drop();if(probe.buf)vkDestroyBuffer(device,probe.buf,nullptr);if(probe.bmem)vkFreeMemory(device,probe.bmem,nullptr);probe=Probe{};
    for(auto q:pipe)if(q)vkDestroyPipeline(device,q,nullptr);for(auto &p:rp)if(p)vkDestroyRenderPass(device,p,nullptr);for(auto &s:samp)if(s)vkDestroySampler(device,s,nullptr);
    if(pool)vkDestroyDescriptorPool(device,pool,nullptr);if(layout)vkDestroyPipelineLayout(device,layout,nullptr);if(layout_rcas)vkDestroyPipelineLayout(device,layout_rcas,nullptr);if(dsl)vkDestroyDescriptorSetLayout(device,dsl,nullptr);
    for(auto &q:pipe)q=VK_NULL_HANDLE;for(auto &p:rp)p=VK_NULL_HANDLE;for(auto &s:samp)s=VK_NULL_HANDLE;pool=VK_NULL_HANDLE;layout=VK_NULL_HANDLE;layout_rcas=VK_NULL_HANDLE;dsl=VK_NULL_HANDLE;sets[0]=sets[1]=VK_NULL_HANDLE;pfmt=VK_FORMAT_UNDEFINED;}
// Views + framebuffers of the rotated swapchain's images (false: drop() them, the caller makes an identity swapchain).
bool make_targets(const std::vector<VkImage> &imgs,VkFormat f){
    views.assign(imgs.size(),VK_NULL_HANDLE);fbs.assign(imgs.size(),VK_NULL_HANDLE);
    for(size_t i=0;i<imgs.size();i++){VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=imgs[i];vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=f;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
        if(vkCreateImageView(device,&vi,nullptr,&views[i])){views[i]=VK_NULL_HANDLE;return false;}
        VkFramebufferCreateInfo fc{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};fc.renderPass=rp[0];fc.attachmentCount=1;fc.pAttachments=&views[i];fc.width=img.width;fc.height=img.height;fc.layers=1;
        if(vkCreateFramebuffer(device,&fc,nullptr,&fbs[i])){fbs[i]=VK_NULL_HANDLE;return false;}}
    return true;
}
// A new swapchain: decide (cap = the surface now, usage_ok = COLOR_ATTACHMENT allowed, sharpen = RCAS on: the sharpening draw is made too).
// Returns the transform to use.
VkSurfaceTransformFlagBitsKHR decide(const VkSurfaceCapabilitiesKHR &cap,VkFormat f,bool usage_ok,bool sharpen){
    const uint32_t cur=uint32_t(cap.currentTransform);
    if(last_transform && cur!=last_transform && (cur|last_transform)==(NRR_T_ROT90|NRR_T_ROT270))++turns;   // the phone turned over (2 <-> 8)
    last_transform=cur;rcas_want=sharpen;
    int made=NRR_R_PIPELINE;if(nrr_decide(mode,cur,uint32_t(cap.supportedTransforms),usage_ok,0,1,failed,&turn)==NRR_R_OK)made=setup(f,sharpen);
    reason=nrr_decide(mode,cur,uint32_t(cap.supportedTransforms),usage_ok,made==NRR_R_SHARPEN,made!=NRR_R_PIPELINE,failed,&turn);
    return on() && reason==NRR_R_OK?VkSurfaceTransformFlagBitsKHR(turn):VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
}
// A rotated swapchain could not be completed: rotation off for this run (the caller makes an identity swapchain at once).
void fail(const char *what,int r){failed=true;red("%s failed (VkResult %d): an identity swapchain instead, the compositor turns the picture; pre-rotation off until restart",what,r);}
void source_barrier(VkCommandBuffer cmd,VkImage src,bool to_read){
    VkImageMemoryBarrier b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};b.srcQueueFamilyIndex=b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;b.image=src;b.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    // the engine hands the window texture over in TRANSFER_SRC_OPTIMAL (written by earlier submissions) and keeps tracking it so: sampled
    // here, then back, with later writes of any stage after this read (the WAR the blit path's source_read barrier gives)
    if(to_read){b.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b.newLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;b.srcAccessMask=VK_ACCESS_MEMORY_WRITE_BIT;b.dstAccessMask=VK_ACCESS_SHADER_READ_BIT;
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,0,0,nullptr,0,nullptr,1,&b);}
    else{b.oldLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;b.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b.srcAccessMask=0;b.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,0,nullptr,0,nullptr,1,&b);}
}
// The flight's view of the window texture and its set (the flight's previous frame has retired: its fence was waited).
bool bind_source(unsigned f,VkImage src,VkFormat fmt,bool linear){
    if(src_view[f]){vkDestroyImageView(device,src_view[f],nullptr);src_view[f]=VK_NULL_HANDLE;}
    VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=src;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=fmt;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    VkImageViewUsageCreateInfo vu{VK_STRUCTURE_TYPE_IMAGE_VIEW_USAGE_CREATE_INFO};vu.usage=VK_IMAGE_USAGE_SAMPLED_BIT;vi.pNext=&vu;   // the engine's image may carry STORAGE etc. its format lacks
    if(vkCreateImageView(device,&vi,nullptr,&src_view[f])){src_view[f]=VK_NULL_HANDLE;return false;}
    VkDescriptorImageInfo ii{samp[linear?1:0],src_view[f],VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};VkWriteDescriptorSet w{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};w.dstSet=sets[f];w.descriptorCount=1;w.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;w.pImageInfo=&ii;
    vkUpdateDescriptorSets(device,1,&w,0,nullptr);return true;
}
extern "C" __attribute__((weak)) void dm_vk_pass_end_sysmem(VkCommandBuffer cmd);   // [DOS2] NR-GMEM (vk_driver.c)
// One turned draw of the bound source into framebuffer fb (fbw x fbh) through render pass p; vp = the destination rectangle in the image.
// rc: the sharpening draw (pipe[2] / [3]) with these RCAS push constants; null: the plain one (pipe[0] / [1]).
void draw_pass(VkCommandBuffer cmd,unsigned f,VkRenderPass p,VkFramebuffer fb,uint32_t fbw,uint32_t fbh,nrr_rect vp,const float m[4],const float t[2],const VkClearColorValue &clear,bool draw,const nrr_rcas_pc *rc=nullptr){
    VkClearValue cv{};cv.color=clear;VkRenderPassBeginInfo rb{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};rb.renderPass=p;rb.framebuffer=fb;rb.renderArea={{0,0},{fbw,fbh}};rb.clearValueCount=p==rp[0]?0:1;rb.pClearValues=&cv;
    vkCmdBeginRenderPass(cmd,&rb,VK_SUBPASS_CONTENTS_INLINE);
    if(draw){const VkPipelineLayout lay=rc?layout_rcas:layout;vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pipe[(p==rp[2]?1:0)+(rc?2:0)]);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,lay,0,1,&sets[f],0,nullptr);
        VkViewport v{float(vp.x),float(vp.y),float(vp.w),float(vp.h),0,1};VkRect2D sc{{vp.x,vp.y},{uint32_t(vp.w),uint32_t(vp.h)}};vkCmdSetViewport(cmd,0,1,&v);vkCmdSetScissor(cmd,0,1,&sc);
        if(rc){const RcasPush pc{{m[0],m[1],m[2],m[3],t[0],t[1]},{0,0},*rc};vkCmdPushConstants(cmd,lay,VK_SHADER_STAGE_VERTEX_BIT|VK_SHADER_STAGE_FRAGMENT_BIT,0,sizeof pc,&pc);}
        else{float pc[6]={m[0],m[1],m[2],m[3],t[0],t[1]};vkCmdPushConstants(cmd,lay,VK_SHADER_STAGE_VERTEX_BIT,0,sizeof pc,pc);}
        vkCmdDraw(cmd,3,1,0,0);}
    if(dm_vk_pass_end_sysmem)dm_vk_pass_end_sysmem(cmd);   // [DOS2] NR-GMEM: under DM_GFX_PASS_GMEM=1 (TU_DEBUG=gmem) the present pass stays in sysmem as before
    vkCmdEndRenderPass(cmd);
}
// The present of a rotated swapchain: the window texture (sw x sh; its rectangle sx, sy, sbw, sbh) into image `index`, shown at the old
// blit's window rectangle (dx, dy, dw, dh) of the window extent ew x eh. false: no view of the source (the image is cleared black this
// frame; the caller makes an identity swapchain next). sharpen: RCAS is on and the source is a format it takes (the old path would
// sharpen this frame): the sharpening draw, unless the frame is filtered linearly (TL2 pillarbox: then unsharpened, counted).
bool draw(VkCommandBuffer cmd,unsigned f,uint32_t index,VkImage src,VkFormat fmt,uint32_t sw,uint32_t sh,int32_t sx,int32_t sy,int32_t sbw,int32_t sbh,nrr_rect d,uint32_t ew,uint32_t eh,bool linear,bool sharpen,float sharpness,bool *sharpened){
    const nrr_rect vp=nrr_map_rect(turn,ew,eh,d);const bool covers=vp.x==0 && vp.y==0 && vp.w==int32_t(img.width) && vp.h==int32_t(img.height);
    VkClearColorValue clear{};if(mode==NRR_MODE_POISON){clear.float32[0]=1;clear.float32[2]=1;clear.float32[3]=1;}
    if(index>=fbs.size())return false;   // not reached: a rotated swapchain has a framebuffer per image (make_targets) or is replaced at once
    const bool ok=bind_source(f,src,fmt,linear);
    float m[4],t[2];nrr_uv_affine(turn,sw,sh,sx,sy,sbw,sbh,m,t);
    nrr_rcas_pc rc;const bool rcas=sharpen && !linear && pipe[2];*sharpened=rcas && ok;if(rcas)nrr_rcas_map(turn,ew,eh,d,sw,sh,sx,sy,sbw,sbh,sharpness,&rc);else if(sharpen)++sharp_plain;
    if(ok)source_barrier(cmd,src,true);
    draw_pass(cmd,f,covers && ok && mode!=NRR_MODE_POISON?rp[0]:rp[1],fbs[index],img.width,img.height,vp,m,t,clear,ok,rcas?&rc:nullptr);
    if(ok)source_barrier(cmd,src,false);
    return ok;
}
// Mode 2: every NRR_PROBE_EVERY presents the turned draw into an image of the rotated extent, then NRR_PROBES of its pixels and the window
// texture's texels they should show into a host buffer; probe_collect compares them after the flight's fence.
bool probe_target(uint32_t w,uint32_t h,VkFormat f){
    if(probe.img && probe.w==w && probe.h==h && probe.fmt==f)return true;
    drop_probe();
    VkImageCreateInfo ic{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};ic.imageType=VK_IMAGE_TYPE_2D;ic.format=f;ic.extent={w,h,1};ic.mipLevels=ic.arrayLayers=1;ic.samples=VK_SAMPLE_COUNT_1_BIT;ic.tiling=VK_IMAGE_TILING_OPTIMAL;
    ic.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT;if(vkCreateImage(device,&ic,nullptr,&probe.img)){probe.img=VK_NULL_HANDLE;return false;}
    VkMemoryRequirements mr;vkGetImageMemoryRequirements(device,probe.img,&mr);VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=mr.size;ma.memoryTypeIndex=mem_type(mr.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    if(ma.memoryTypeIndex==UINT32_MAX || vkAllocateMemory(device,&ma,nullptr,&probe.mem) || vkBindImageMemory(device,probe.img,probe.mem,0)){probe.mem=VK_NULL_HANDLE;drop_probe();return false;}
    VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=probe.img;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=f;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    if(vkCreateImageView(device,&vi,nullptr,&probe.view)){probe.view=VK_NULL_HANDLE;drop_probe();return false;}
    VkFramebufferCreateInfo fc{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};fc.renderPass=rp[2];fc.attachmentCount=1;fc.pAttachments=&probe.view;fc.width=w;fc.height=h;fc.layers=1;
    if(vkCreateFramebuffer(device,&fc,nullptr,&probe.fb)){probe.fb=VK_NULL_HANDLE;drop_probe();return false;}
    if(!probe.buf){VkBufferCreateInfo bc{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bc.size=VkDeviceSize(2*2*NRR_PROBES*4);bc.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT;if(vkCreateBuffer(device,&bc,nullptr,&probe.buf)){probe.buf=VK_NULL_HANDLE;drop_probe();return false;}
        VkMemoryRequirements br;vkGetBufferMemoryRequirements(device,probe.buf,&br);uint32_t t=mem_type(br.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);probe.coherent=t!=UINT32_MAX;
        if(t==UINT32_MAX)t=mem_type(br.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT);VkMemoryAllocateInfo ba{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ba.allocationSize=br.size;ba.memoryTypeIndex=t;
        if(t==UINT32_MAX || vkAllocateMemory(device,&ba,nullptr,&probe.bmem) || vkBindBufferMemory(device,probe.buf,probe.bmem,0) || vkMapMemory(device,probe.bmem,0,VK_WHOLE_SIZE,0,&probe.map)){
            vkDestroyBuffer(device,probe.buf,nullptr);probe.buf=VK_NULL_HANDLE;if(probe.bmem)vkFreeMemory(device,probe.bmem,nullptr);probe.bmem=VK_NULL_HANDLE;probe.map=nullptr;drop_probe();return false;}}
    probe.w=w;probe.h=h;probe.fmt=f;return true;
}
void probe_collect(unsigned f){
    if(!probe.pend[f])return;probe.pend[f]=false;
    if(!probe.coherent){VkMappedMemoryRange mr{VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE};mr.memory=probe.bmem;mr.size=VK_WHOLE_SIZE;vkInvalidateMappedMemoryRanges(device,1,&mr);}
    const uint8_t *b=static_cast<const uint8_t*>(probe.map)+size_t(f)*2*NRR_PROBES*4;unsigned bad=0;
    for(int i=0;i<NRR_PROBES;i++){const uint8_t *d=b+i*4,*s=b+(NRR_PROBES+i)*4;
        if(nrr_probe_equal_tol(d,probe.fi[f],s,probe.fs[f],probe.sharp[f]?1:0)){++probes_ok;continue;}++probes_bad;
        if(bad++<2)red("probe (DM_NR_ROTATE=2, %s%s): image pixel (%d,%d) = %02x%02x%02x%02x, the %s (%d,%d) it shows = %02x%02x%02x%02x",nrr_transform_name(turn),probe.sharp[f]?", RCAS":"",probe.px[f][i],probe.py[f][i],d[0],d[1],d[2],d[3],
            probe.sharp[f]?"texel of RCAS's own image":"window texel",probe.sx[f][i],probe.sy[f][i],s[0],s[1],s[2],s[3]);}
}
// rcas_img: the old path sharpened this frame into RCAS's own image (sw x sh, R8G8B8A8_UNORM, TRANSFER_SRC_OPTIMAL after its blit): the
// sharpening draw is probed against that image's texels (the unturned output) instead of the window texture's.
void probe_record(VkCommandBuffer cmd,unsigned f,VkImage src,VkFormat fmt,uint32_t sw,uint32_t sh,int32_t sx,int32_t sy,int32_t sbw,int32_t sbh,nrr_rect d,uint32_t ew,uint32_t eh,bool linear,VkFormat sfmt,VkImage rcas_img,float sharpness){
    if(mode!=NRR_MODE_CHECK || reason!=NRR_R_OK || ++probe_frames%NRR_PROBE_EVERY || probe.pend[f])return;
    const bool sharp=rcas_img!=VK_NULL_HANDLE;if(sharp && !pipe[3]){++probes_skipped;return;}
    const int fi=nrr_probe_format(uint32_t(sfmt)),fs=nrr_probe_format(uint32_t(sharp?VK_FORMAT_R8G8B8A8_UNORM:fmt));
    if(linear || sbw!=d.w || sbh!=d.h || !fi || !fs || (fi&2)!=(fs&2)){++probes_skipped;return;}   // compared only 1:1 (nearest) between 8-bit RGBA-class formats of one sRGB-ness
    uint32_t iw,ih;nrr_image_extent(turn,ew,eh,&iw,&ih);if(!probe_target(iw,ih,sfmt) || !bind_source(f,src,fmt,false)){++probes_skipped;red("probe: no image / view (mode 2 check skipped)");return;}
    const nrr_rect vp=nrr_map_rect(turn,ew,eh,d);float m[4],t[2];nrr_uv_affine(turn,sw,sh,sx,sy,sbw,sbh,m,t);VkClearColorValue clear{};
    nrr_rcas_pc rc;if(sharp)nrr_rcas_map(turn,ew,eh,d,sw,sh,sx,sy,sbw,sbh,sharpness,&rc);
    source_barrier(cmd,src,true);draw_pass(cmd,f,rp[2],probe.fb,iw,ih,vp,m,t,clear,true,sharp?&rc:nullptr);source_barrier(cmd,src,false);
    nrr_probe_points(vp,uint32_t(probe_frames/NRR_PROBE_EVERY),probe.px[f],probe.py[f]);
    VkBufferImageCopy c[2][NRR_PROBES]{};const VkDeviceSize base=VkDeviceSize(f)*2*NRR_PROBES*4;
    for(int i=0;i<NRR_PROBES;i++){if(sharp)nrr_rcas_src_texel(&rc,probe.px[f][i],probe.py[f][i],&probe.sx[f][i],&probe.sy[f][i]);else nrr_src_texel(m,t,vp,sw,sh,probe.px[f][i],probe.py[f][i],&probe.sx[f][i],&probe.sy[f][i]);
        for(int k=0;k<2;k++){c[k][i].bufferOffset=base+VkDeviceSize(k*NRR_PROBES+i)*4;c[k][i].imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};c[k][i].imageExtent={1,1,1};}
        c[0][i].imageOffset={probe.px[f][i],probe.py[f][i],0};c[1][i].imageOffset={probe.sx[f][i],probe.sy[f][i],0};}
    vkCmdCopyImageToBuffer(cmd,probe.img,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,probe.buf,NRR_PROBES,c[0]);
    vkCmdCopyImageToBuffer(cmd,sharp?rcas_img:src,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,probe.buf,NRR_PROBES,c[1]);
    VkBufferMemoryBarrier hb{VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER};hb.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;hb.dstAccessMask=VK_ACCESS_HOST_READ_BIT;hb.srcQueueFamilyIndex=hb.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;hb.buffer=probe.buf;hb.size=VK_WHOLE_SIZE;
    VkMemoryBarrier rb{VK_STRUCTURE_TYPE_MEMORY_BARRIER};rb.srcAccessMask=VK_ACCESS_TRANSFER_READ_BIT;rb.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;   // later writes of the window texture after the copy read it
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT|VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,1,&rb,1,&hb,0,nullptr);
    probe.fi[f]=fi;probe.fs[f]=fs;probe.sharp[f]=sharp;probe.pend[f]=true;if(sharp)++probes_rcas;
}
// After each successful present: counters and, every 10 s, one line.
void frame(bool turned,bool sharpened){
    ++presents;if(turned)++drawn;else ++blits;if(sharpened)++sharp_draws;
    timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);const double now=double(ts.tv_sec)+double(ts.tv_nsec)*1e-9;if(!next_line){next_line=now+10;return;}if(now<next_line)return;next_line=now+10;
    __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] rotate (DM_NR_ROTATE=%d, last 10 s): %llu presents, turned draw %llu, blit %llu; RCAS %s: sharpened in the turned draw %llu, unsharpened %llu; swapchain %s (surface %s, %s), image %ux%u; swapchains %llu (pre-rotated %llu, phone turned %llu)%s; probes ok %llu bad %llu skipped %llu (RCAS %llu); red %u",
        mode,(unsigned long long)presents,(unsigned long long)drawn,(unsigned long long)blits,rcas_want?(pipe[2]?"on":"on, no turned pipeline"):"off",(unsigned long long)sharp_draws,(unsigned long long)sharp_plain,
        nrr_transform_name(uint32_t(pre)),nrr_transform_name(last_transform),nrr_reason_name(reason),img.width,img.height,(unsigned long long)swaps,(unsigned long long)rotated_swaps,(unsigned long long)turns,failed?", FAILED (off)":"",
        (unsigned long long)probes_ok,(unsigned long long)probes_bad,(unsigned long long)probes_skipped,(unsigned long long)probes_rcas,red_lines);
    presents=drawn=blits=sharp_draws=sharp_plain=0;
}
}
// 缺省开启（标记文件 gfx-present-overlap 为 '0' 时关）：最多两次呈现 blit 在途，不在每帧后清空队列，游戏可在 GPU 收尾本帧时翻译下一帧。
// On by default (marker file gfx-present-overlap = '0' turns it off): keep up to two present blits in flight instead of draining the queue
// after every frame, so the game translates the next frame while the GPU finishes this one. Each in-flight frame has
// its own pool, acquire semaphore and fence; slot 0 is the original set. Later engine barriers on the source image are
// ALL_COMMANDS and its release retires with a later submission, which covers this blit in queue order.
bool overlap=false;VkCommandPool overlap_pool;VkCommandBuffer overlap_command;VkSemaphore overlap_acquired;VkFence overlap_fence;
bool in_flight[2];unsigned flight=0;
// Diagnostic (marker gfx-present-timing; overlap mode): GPU time of each present's clear and blit, from two timestamps per
// in-flight frame, read once that frame's fence has signalled; averaged over 300 presents.
bool present_timing=false;VkQueryPool present_queries=VK_NULL_HANDLE;bool present_stamped[2];double present_tick_ns=1,present_gpu_ns=0;unsigned present_timed=0;
// 游戏线程（调用呈现的线程；同步翻译时也是翻译线程）钉在最高频的核上。Redmi K50 Ultra 上调度器一直把它放在 A710
// （cpu4–6，MIUI 封顶 2.57 GHz），从不用空着的 X2（cpu7，封顶 2.25 GHz）；钉到 X2 后营地在 3D 比例 0.6 下从 40.2 升到
// 44.3 fps（同进程 A/B，CPU 17.1 → 14.3 ms）。MIUI 会改线程的可用核掩码，所以每 120 次呈现核对一次。
// 标记 gfx-no-pin 关闭，gfx-pin-cpu = 十六进制掩码 指定核；gfx-ab-toggle = N 加 gfx-ab-target = pin 时每 N 秒钉 / 放开交替。
// The game thread (the caller of present, which also translates in sync mode) runs on the cores with the highest maximum
// frequency. On the Redmi K50 Ultra the scheduler kept it on the A710 cores (cpu4-6, capped at 2.57 GHz by MIUI) and never
// used the idle X2 (cpu7, capped at 2.25 GHz); pinned to the X2 the camp went from 40.2 to 44.3 fps at 3D scale 0.6
// (in-process A/B, CPU 17.1 -> 14.3 ms). MIUI rewrites thread affinity masks, so the pin is checked every 120 presents.
// Marker gfx-no-pin turns it off and gfx-pin-cpu = hex mask picks the cores; gfx-ab-toggle = N with gfx-ab-target = pin
// alternates pinned and released every N seconds, in phase with the engine's A/B (its PERF lines carry ab=).
// [cpu-place] Without any of these markers the pin is no longer made here: hle_cpu_place.c places this thread (and the guest threads) by
// the capacity plan and the gear's "CPU cores" mode, checks the masks every 2 s and again after onResume; pin_update only tells it
// which thread presents. With a marker this code pins as before and the module leaves the presenting thread alone.
unsigned pin_mask=0;int pin_ab=0;int pin_state=-1;unsigned pin_presents=0,pin_drifts=0,pin_failures=0;cpu_set_t pin_original;bool pin_have_original=false;bool pin_markers=false;
unsigned fastest_cores(){
    unsigned best=0,mask=0,present=0;
    for(int c=0;c<32;c++){char path[96];snprintf(path,sizeof path,"/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq",c);FILE *f=fopen(path,"rb");if(!f)continue;
        unsigned v=0;if(fscanf(f,"%u",&v)==1 && v){present|=1u<<c;if(v>best){best=v;mask=0;}if(v==best)mask|=1u<<c;}fclose(f);}
    return mask==present?0:mask;   // one core class: nothing to pick
}
void pin_update(){
    dm_cpu_place_translator(int(gettid()));if(!pin_markers)return;   // [cpu-place]
    if(!pin_mask)return;bool want=true;
    if(pin_ab>0){timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);want=((ts.tv_sec/pin_ab)&1)==0;}
    bool changed=int(want)!=pin_state;if(!changed && ++pin_presents%120)return;
    if(!pin_have_original){CPU_ZERO(&pin_original);if(sched_getaffinity(0,sizeof pin_original,&pin_original))for(int c=0;c<32;c++)CPU_SET(c,&pin_original);pin_have_original=true;}
    cpu_set_t set;CPU_ZERO(&set);if(want){for(int c=0;c<32;c++)if(pin_mask>>c&1)CPU_SET(c,&set);}else set=pin_original;
    if(!changed){cpu_set_t cur;CPU_ZERO(&cur);if(!sched_getaffinity(0,sizeof cur,&cur) && CPU_EQUAL(&cur,&set))return;++pin_drifts;}
    int r=sched_setaffinity(0,sizeof set,&set),err=r?errno:0;pin_state=want;if(r)++pin_failures;
    // Refused while the app's cpuset lacks the cores (Android moves the app between cpusets, at start for one): the kernel
    // keeps the request and applies it again when the cpuset allows, and the next check retries.
    if(changed || pin_drifts<=4 || (r && pin_failures<=4))__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","NVN pin tid=%d %s mask=%x result=%d errno=%d drifts=%u failures=%u",int(gettid()),want?"pinned":"released",want?pin_mask:0u,r,err,pin_drifts,pin_failures);
}
void log_message(void*,const char *text){__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","%s",text);}
[[noreturn]] void fatal(void*,const char *text){__android_log_print(ANDROID_LOG_FATAL,"dm-vulkan","%s",text);abort();}
void destroy_present_semaphores(){for(auto s:finished)if(s)vkDestroySemaphore(device,s,nullptr);finished.clear();}
// 调用者先等队列空闲；基础WSI销毁仍沿用WaitIdle惯例，不声称提供呈现栅栏保证。
// Call only after queue idle. Base WSI teardown follows the WaitIdle convention,
// which is not the explicit presentation-fence guarantee of swapchain_maintenance1.
void destroy_swap(){destroy_present_semaphores();if(nrp::mode)nrp::drop();if(nrr::mode)nrr::drop();if(swapchain)vkDestroySwapchainKHR(device,swapchain,nullptr);swapchain=VK_NULL_HANDLE;images.clear();if(surface)vkDestroySurfaceKHR(instance,surface,nullptr);surface=VK_NULL_HANDLE;if(active)ANativeWindow_release(active);active=nullptr;}
void cleanup_initialization(){
    if(queue)vkQueueWaitIdle(queue);
    if(device){if(fence)vkDestroyFence(device,fence,nullptr);if(acquired)vkDestroySemaphore(device,acquired,nullptr);if(command_pool)vkDestroyCommandPool(device,command_pool,nullptr);}
    fence=VK_NULL_HANDLE;acquired=VK_NULL_HANDLE;command_pool=VK_NULL_HANDLE;command=VK_NULL_HANDLE;
    if(device){if(overlap_fence)vkDestroyFence(device,overlap_fence,nullptr);if(overlap_acquired)vkDestroySemaphore(device,overlap_acquired,nullptr);if(overlap_pool)vkDestroyCommandPool(device,overlap_pool,nullptr);}
    overlap_fence=VK_NULL_HANDLE;overlap_acquired=VK_NULL_HANDLE;overlap_pool=VK_NULL_HANDLE;overlap_command=VK_NULL_HANDLE;overlap=false;in_flight[0]=in_flight[1]=false;flight=0;
    destroy_swap();if(device)for(auto &s:nrp::ring)if(s){vkDestroySemaphore(device,s,nullptr);s=VK_NULL_HANDLE;}   // [DOS2] NR-11
    if(device)nrr::destroy_all();   // [DOS2] NR-20 (nothing made unless DM_NR_ROTATE was set)
    if(device)vkDestroyDevice(device,nullptr);device=VK_NULL_HANDLE;queue=VK_NULL_HANDLE;
    if(instance)vkDestroyInstance(instance,nullptr);instance=VK_NULL_HANDLE;physical=VK_NULL_HANDLE;
}
// 刷新率投票：App 不投票时，安卓（MIUI）让这个表面跑 60 Hz，尽管屏和系统设置都允许 120。投 120 Hz 不改 60 帧的出图节奏（nvn_pace_hz），
// 但赶不上 16.7 ms 的那一帧在屏上停 25 ms 而不是 33.3 ms。标记 gfx-frame-rate = N（Hz；0 = 不投票）。
// Frame-rate vote: without a vote from the app, Android (MIUI) runs this surface at 60 Hz although the panel and the system
// setting allow 120. A 120 Hz vote keeps the 60 fps present pacing (nvn_pace_hz), but a frame that misses 16.7 ms stays on
// screen for 25 ms instead of 33.3. Marker gfx-frame-rate = N (Hz; 0 = no vote).
float frame_rate_vote=120;
// 按游戏输出尺寸出图：窗口缓冲设成游戏输出的尺寸（2000×900），由显示硬件放大到屏幕，呈现端只做 1:1 拷贝，不再每帧清屏、
// 用 GPU 按最近邻放大到 2712×1220。分辨率不变，最后一步放大从 GPU 移到显示控制器（滤波也更平滑）。标记 gfx-present-native = 0 关。
// Present at the game's output size: the window's buffers take the game's output size (2000x900) and the display hardware
// scales them to the screen, so the presenter copies 1:1 instead of clearing and nearest-scaling to 2712x1220 on the GPU
// every frame. Same resolution; the final upscale moves from the GPU to the display controller (with smoother filtering).
// Marker gfx-present-native = 0 turns it off.
#ifdef __OHOS__
bool present_native=false;   // 鸿蒙：缓冲尺寸与合成缩放未在真机核过，先关；标记 gfx-present-native = 1 打开 | HarmonyOS: buffer geometry vs compositor scaling not yet checked on device; off, marker gfx-present-native = 1 enables
#else
bool present_native=true;
#endif
int native_w=0,native_h=0;
namespace rcas{bool enabled();}   // [DOS2] NR-20: create_swap asks (RCAS on: the turned draw that sharpens is made too, NR-20-rcas.md)
int create_surface(){
    destroy_swap();native_w=native_h=0;
    {std::lock_guard<std::mutex> lock(window_mutex);if(!desired)return VK_NOT_READY;active=desired;ANativeWindow_acquire(active);active_generation=generation;}
    if(frame_rate_vote>0){
        // 运行时查询API，系统拒绝投票不会中止Vulkan初始化。 | Resolve the API at runtime; a refused vote does not abort Vulkan initialization.
        static auto set_rate=[]{void *lib=dlopen("libnativewindow.so",RTLD_NOW);return reinterpret_cast<int32_t(*)(ANativeWindow*,float,int8_t)>(lib?dlsym(lib,"ANativeWindow_setFrameRate"):nullptr);}();
        int fr=set_rate?set_rate(active,frame_rate_vote,ANATIVEWINDOW_FRAME_RATE_COMPATIBILITY_DEFAULT):-1;
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Frame rate vote %.0f Hz result=%d (marker gfx-frame-rate; display request, not FPS)",double(frame_rate_vote),fr);
    }
    VkAndroidSurfaceCreateInfoKHR ci{VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR};ci.window=active;
    VkResult r=vkCreateAndroidSurfaceKHR(instance,&ci,nullptr,&surface);if(r)return r;
    if(!device)return 0;VkBool32 supported=VK_FALSE;r=vkGetPhysicalDeviceSurfaceSupportKHR(physical,family,surface,&supported);if(r||!supported)return r?r:VK_ERROR_FEATURE_NOT_PRESENT;return 0;
}
int create_swap(){
    VkSurfaceCapabilitiesKHR cap;VkResult r=vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&cap);if(r)return r;
    if(!(cap.supportedUsageFlags&VK_IMAGE_USAGE_TRANSFER_DST_BIT))return VK_ERROR_FORMAT_NOT_SUPPORTED;
    if(!(cap.supportedTransforms&VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR))return VK_ERROR_FEATURE_NOT_PRESENT;
    uint32_t n=0;r=vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&n,nullptr);if(r||!n)return r?r:VK_ERROR_FORMAT_NOT_SUPPORTED;
    std::vector<VkSurfaceFormatKHR> formats(n);r=vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&n,formats.data());if(r)return r;
    VkSurfaceFormatKHR sf=formats[0];if(sf.format==VK_FORMAT_UNDEFINED)sf.format=VK_FORMAT_R8G8B8A8_UNORM;
    for(auto f:formats)if(f.format==VK_FORMAT_R8G8B8A8_UNORM||f.format==VK_FORMAT_B8G8R8A8_UNORM){sf=f;break;}
    extent=cap.currentExtent;if(extent.width==UINT32_MAX){extent.width=std::clamp(uint32_t(std::max(1,ANativeWindow_getWidth(active))),cap.minImageExtent.width,cap.maxImageExtent.width);extent.height=std::clamp(uint32_t(std::max(1,ANativeWindow_getHeight(active))),cap.minImageExtent.height,cap.maxImageExtent.height);}if(!extent.width||!extent.height)return VK_NOT_READY;
    VkSwapchainCreateInfoKHR ci{VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};ci.surface=surface;
#ifdef __OHOS__
    {unsigned want=4;if(const char *e=getenv("DM_SWAP_IMAGES"))want=unsigned(std::max(2,atoi(e)));ci.minImageCount=std::max(want,cap.minImageCount);}   // 马良最佳实践：重负载 3–4 张；按期望上屏时刻排帧时合成器手里多压一张，取 4 张免得翻译线程等交换链、反压到游戏帧节奏 | Maleoon best practice: 3–4 under heavy load; with desired display times the compositor holds one more buffer, so take 4 to keep the translation thread from waiting on the swapchain and back-pressuring the game cadence
#else
    ci.minImageCount=std::max(2u,cap.minImageCount);
#endif
    if(cap.maxImageCount)ci.minImageCount=std::min(ci.minImageCount,cap.maxImageCount);ci.imageFormat=sf.format;ci.imageColorSpace=sf.colorSpace;ci.imageExtent=extent;ci.imageArrayLayers=1;ci.imageUsage=VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    // [DOS2] NR-11: colour attachment (the engine's last passes) and copy source (an aborted frame copies the image back into the window texture)
    const VkImageUsageFlags nrp_usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT;nrp::usage_ok=(cap.supportedUsageFlags&nrp_usage)==nrp_usage;
    if(nrp::on() && nrp::usage_ok)ci.imageUsage|=nrp_usage;ci.imageSharingMode=VK_SHARING_MODE_EXCLUSIVE;ci.preTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;ci.compositeAlpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    // [DOS2] NR-20 DM_NR_ROTATE 1 / 3: preTransform = the surface's turn, the images in the panel's orientation (90 / 270: the extent swapped,
    // Google's pre-rotation guide; `extent` stays the window's), colour attachments for the turned draw. 2 decides and logs only.
    VkSurfaceTransformFlagBitsKHR nrr_pre=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
    if(nrr::mode){nrr_pre=nrr::decide(cap,sf.format,(cap.supportedUsageFlags&VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT)!=0,rcas::enabled());
        if(nrr_pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR){ci.preTransform=nrr_pre;ci.imageUsage|=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;nrr_image_extent(uint32_t(nrr_pre),extent.width,extent.height,&ci.imageExtent.width,&ci.imageExtent.height);}}
    if(!(cap.supportedCompositeAlpha&ci.compositeAlpha))for(uint32_t b=1;b<=8;b<<=1)if(cap.supportedCompositeAlpha&b){ci.compositeAlpha=VkCompositeAlphaFlagBitsKHR(b);break;}
    // [BL2] DM_VK_PRESENT=mailbox|immediate|fifo: the swapchain present mode. FIFO (the default) makes the queue wait for the display, so
    // the GPU idles between frames while the CPU records the next one; MAILBOX does not block (and does not tear) and lets the GPU run back
    // to back. The mode is tried as asked; if the surface rejects it the next create_swap() uses FIFO (the loader stub here has no
    // vkGetPhysicalDeviceSurfacePresentModesKHR, so the support list cannot be queried up front).
    static bool pm_fallback=false;   // this process: the requested mode was rejected once
    VkPresentModeKHR pm=VK_PRESENT_MODE_FIFO_KHR;
    if(!pm_fallback){ const char *e=getenv("DM_VK_PRESENT");
      if(e&&*e){ if(!strcmp(e,"mailbox"))pm=VK_PRESENT_MODE_MAILBOX_KHR; else if(!strcmp(e,"immediate"))pm=VK_PRESENT_MODE_IMMEDIATE_KHR; } }
    ci.presentMode=pm;ci.clipped=VK_TRUE;ci.oldSwapchain=swapchain;VkSwapchainKHR replacement=VK_NULL_HANDLE;r=vkCreateSwapchainKHR(device,&ci,nullptr,&replacement);
    // 创建失败也会退休oldSwapchain；重试不得继续传入退休句柄。
    // Even failed creation retires oldSwapchain; never pass that retired handle on retry.
    destroy_present_semaphores();if(nrp::mode)nrp::drop();if(nrr::mode)nrr::drop();if(swapchain)vkDestroySwapchainKHR(device,swapchain,nullptr);swapchain=r?VK_NULL_HANDLE:replacement;images.clear();
    if(r && nrr_pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR){nrr::fail("vkCreateSwapchainKHR (pre-rotated)",r);return create_swap();}   // [DOS2] NR-20: the old one is retired and gone: an identity one now
    if(r && pm!=VK_PRESENT_MODE_FIFO_KHR){static bool told;if(!told){told=true;__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","present mode %d rejected (%d): FIFO",int(pm),int(r));}pm_fallback=true;return create_swap();}   // [BL2] no MAILBOX here: FIFO
    if(r)return r;swap_format=sf.format;
    if(nrr::mode){nrr::pre=nrr_pre;nrr::img=ci.imageExtent;++nrr::swaps;if(nrr_pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR)++nrr::rotated_swaps;}   // [DOS2] NR-20
    created_transform=cap.currentTransform;created_surface_extent=cap.currentExtent;
    __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Swapchain: window=%dx%d extent=%ux%u currentTransform=%u supported=%u selected=%u",ANativeWindow_getWidth(active),ANativeWindow_getHeight(active),extent.width,extent.height,unsigned(cap.currentTransform),unsigned(cap.supportedTransforms),unsigned(ci.preTransform));
    r=vkGetSwapchainImagesKHR(device,swapchain,&n,nullptr);if(r)return r;images.resize(n);r=vkGetSwapchainImagesKHR(device,swapchain,&n,images.data());if(r)return r;images.resize(n);
    if(dm_vk_compr_ctl&2)nrubwc_swapchain_report(device,images,swap_format);   // [DOS2] NR-UBWC: is the window buffer compressed (gralloc decides)?
    // 呈现完成信号量按交换链图像分配；重新获取该图像后才能再次发信号。
    // Index present-wait semaphores by acquired image, not by CPU frame/fence.
    finished.resize(n,VK_NULL_HANDLE);VkSemaphoreCreateInfo sc{VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};
    for(auto &s:finished){r=vkCreateSemaphore(device,&sc,nullptr,&s);if(r)return r;}
    if(nrr::mode){   // [DOS2] NR-20: the rotated images' views and framebuffers (a failure: an identity swapchain at once, retiring this one)
        if(nrr::pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR && !nrr::make_targets(images,swap_format)){nrr::fail("swapchain image views / framebuffers",VK_ERROR_OUT_OF_HOST_MEMORY);return create_swap();}
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] rotate (DM_NR_ROTATE=%d): surface %s (supported %#x) -> %s: swapchain %s, image %ux%u, window extent %ux%u%s%s",nrr::mode,nrr_transform_name(uint32_t(cap.currentTransform)),unsigned(cap.supportedTransforms),
            nrr_reason_name(nrr::reason),nrr_transform_name(uint32_t(nrr::pre)),nrr::img.width,nrr::img.height,extent.width,extent.height,nrr::mode==NRR_MODE_CHECK && nrr::reason==NRR_R_OK?" (=2: would pre-rotate; the identity swapchain and the blit are kept, the turned draw is probed)":"",
            nrr::rcas_want && nrr::reason==NRR_R_OK?(nrr::mode==NRR_MODE_CHECK?"; RCAS: the sharpening turned draw is probed against RCAS's own image":"; RCAS sharpens in the turned draw (one pass)"):"");}
    if(nrp::mode){   // [DOS2] NR-11: colour-attachment views (1 / 3) and the snapshot the engine asks (every mode but 0)
        if(nrp::on() && (ci.imageUsage&VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT)){nrp::views.assign(images.size(),VK_NULL_HANDLE);
            for(size_t i=0;i<images.size();i++){VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=images[i];vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=swap_format;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
                if(vkCreateImageView(device,&vi,nullptr,&nrp::views[i])){nrp::views[i]=VK_NULL_HANDLE;for(auto &v:nrp::views)if(v)vkDestroyImageView(device,v,nullptr);nrp::views.clear();break;}}}
        std::lock_guard<std::mutex> l(nrp::mu);nrp::snap.gen=++nrp::gen;nrp::snap.fmt=swap_format;nrp::snap.w=extent.width;nrp::snap.h=extent.height;nrp::snap.usage_ok=nrp::usage_ok;nrp::snap.identity=ci.preTransform==VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
        nrp::snap.images=images;nrp::snap.views=nrp::views;nrp::snap.finished=finished;nrp::park=nrp::Park{};nrp::taken=false;
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] present (DM_NR_PRESENT=%d): swapchain gen %llu, %zu images %ux%u format %d, colour attachment %s, views %zu",nrp::mode,(unsigned long long)nrp::gen,images.size(),extent.width,extent.height,int(swap_format),
            nrp::usage_ok?(nrp::on()?"on":"allowed (not asked: =2)"):"NOT allowed by the surface",nrp::views.size());}
    return VK_SUCCESS;
}
// 诊断（标记 gfx-membench）：每种主机可见内存类型的 CPU 写、CPU 读，以及 GPU 填充后的 CPU 读速度，启动时测一次。
// Diagnostic (marker gfx-membench): CPU write, CPU read, and CPU read after a GPU fill, for each host-visible memory type; run once at start.
void membench(){
    VkPhysicalDeviceMemoryProperties mp;vkGetPhysicalDeviceMemoryProperties(physical,&mp);
    const VkDeviceSize n=4u<<20;std::vector<uint8_t> host(n,1),back(n);
    VkCommandPoolCreateInfo cp{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};cp.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;cp.queueFamilyIndex=family;VkCommandPool pool;if(vkCreateCommandPool(device,&cp,nullptr,&pool))return;
    VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=pool;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ca.commandBufferCount=1;VkCommandBuffer cmd;if(vkAllocateCommandBuffers(device,&ca,&cmd)){vkDestroyCommandPool(device,pool,nullptr);return;}
    auto now=[]{timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return double(ts.tv_sec)*1e9+double(ts.tv_nsec);};
    for(uint32_t t=0;t<mp.memoryTypeCount;t++){
        VkMemoryPropertyFlags f=mp.memoryTypes[t].propertyFlags;if(!(f&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT))continue;
        VkBufferCreateInfo bi{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bi.size=n;bi.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;bi.sharingMode=VK_SHARING_MODE_EXCLUSIVE;VkBuffer b;if(vkCreateBuffer(device,&bi,nullptr,&b))continue;
        VkMemoryRequirements r;vkGetBufferMemoryRequirements(device,b,&r);if(!(r.memoryTypeBits&(1u<<t))){vkDestroyBuffer(device,b,nullptr);continue;}
        VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ai.allocationSize=r.size;ai.memoryTypeIndex=t;VkDeviceMemory m;if(vkAllocateMemory(device,&ai,nullptr,&m)){vkDestroyBuffer(device,b,nullptr);continue;}
        void *p=nullptr;if(vkBindBufferMemory(device,b,m,0)||vkMapMemory(device,m,0,VK_WHOLE_SIZE,0,&p)){vkFreeMemory(device,m,nullptr);vkDestroyBuffer(device,b,nullptr);continue;}
        bool coherent=(f&VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)!=0;VkMappedMemoryRange mr{VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE};mr.memory=m;mr.size=VK_WHOLE_SIZE;
        double w=1e30,rc=1e30,rd=1e30,flush=0,inv=0;bool ok=true;
        for(int k=0;k<4;k++){double t0=now();memcpy(p,host.data(),n);double t1=now();if(!coherent)vkFlushMappedMemoryRanges(device,1,&mr);double t2=now();w=std::min(w,t1-t0);flush=std::max(flush,t2-t1);}
        for(int k=0;k<4;k++){double t0=now();memcpy(back.data(),p,n);rc=std::min(rc,now()-t0);}
        for(int k=0;k<4;k++){
            vkResetCommandBuffer(cmd,0);VkCommandBufferBeginInfo cb{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};vkBeginCommandBuffer(cmd,&cb);
            uint32_t value=0x01020304u+uint32_t(k);vkCmdFillBuffer(cmd,b,0,n,value);
            VkMemoryBarrier mb{VK_STRUCTURE_TYPE_MEMORY_BARRIER};mb.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;mb.dstAccessMask=VK_ACCESS_HOST_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&mb,0,nullptr,0,nullptr);
            vkEndCommandBuffer(cmd);VkSubmitInfo si{VK_STRUCTURE_TYPE_SUBMIT_INFO};si.commandBufferCount=1;si.pCommandBuffers=&cmd;if(vkQueueSubmit(queue,1,&si,VK_NULL_HANDLE)||vkQueueWaitIdle(queue)){ok=false;break;}
            double t0=now();if(!coherent)vkInvalidateMappedMemoryRanges(device,1,&mr);double t1=now();memcpy(back.data(),p,n);double t2=now();
            rd=std::min(rd,t2-t1);inv=std::max(inv,t1-t0);uint32_t got;memcpy(&got,back.data()+n-4,4);ok=ok&&got==value;
        }
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","NVN membench type=%u flags=%#x write=%.2f GB/s (flush %.0f us) read=%.2f GB/s read_after_gpu=%.2f GB/s (invalidate %.0f us) ok=%d",
            t,unsigned(f),double(n)/w,flush/1e3,double(n)/rc,double(n)/rd,inv/1e3,int(ok));
        vkUnmapMemory(device,m);vkFreeMemory(device,m,nullptr);vkDestroyBuffer(device,b,nullptr);
    }
    vkDestroyCommandPool(device,pool,nullptr);
}
int has_window(void*){std::lock_guard<std::mutex> l(window_mutex);return desired!=nullptr;}
void wait_window(){std::unique_lock<std::mutex> lock(window_mutex);window_cv.wait(lock,[]{return desired!=nullptr;});}
bool window_changed(){std::lock_guard<std::mutex> lock(window_mutex);return !desired||generation!=active_generation;}
void wait_window_change(uint64_t bad){std::unique_lock<std::mutex> lock(window_mutex);window_cv.wait(lock,[bad]{return generation!=bad;});}
void wait_resize(){std::unique_lock<std::mutex> lock(window_mutex);window_cv.wait_for(lock,std::chrono::milliseconds(16),[]{return generation!=active_generation;});}
// [DOOM] Optional sharpening of the game's frame at present: RCAS, the sharpening pass of AMD FSR 1 (shaders/rcas.comp, offline
// compiled). DM_GFX_SHARPEN=<stops> turns it on (0 = strongest, 0.2 typical, 1 mild); used with DM_DOOM_RES (the game renders
// 3D at a fraction and upscales it itself). Only for 8-bit UNORM RGBA/BGRA frames; anything else is presented unsharpened.
extern "C" { int dm_vk_cond_render=0; }   // [DOS2] VK_EXT_conditional_rendering enabled (only when DM_GFX_COND_RENDER=1; read by the Vulkan engine, namespace condr)
extern "C" { int dm_vk_format_list=0; int dm_vk_custom_border=0; }   // [XC2] custom_border: VK_EXT_custom_border_color enabled (customBorderColorWithoutFormat)   // VK_KHR_image_format_list enabled on the device (read by the Vulkan engine)
extern "C" { int dm_vk_descriptor_indexing=0; }   // [ETERNAL] VK_EXT_descriptor_indexing enabled: partially bound + sampled-image update-after-bind (bindless pools)
namespace rcas {
const uint32_t code[]={
#include "shaders/rcas.spv.inc"
};
int on=-1;float sharpness=1;VkImage image{};VkDeviceMemory memory{};VkImageView view{};uint32_t w=0,h=0;
VkDescriptorSetLayout set_layout{};VkPipelineLayout layout{};VkPipeline pipeline{};VkDescriptorPool pool{};VkDescriptorSet sets[2]{};VkSampler sampler{};VkImageView source_views[2]{};
bool enabled(){if(on<0){const char *e=getenv("DM_GFX_SHARPEN");on=e && *e && atof(e)>=0;if(on){sharpness=std::exp2(-float(atof(e)));__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","RCAS sharpening at present: stops=%s (DM_GFX_SHARPEN)",e);}}return on>0;}
uint32_t memory_type(uint32_t bits,VkMemoryPropertyFlags want){VkPhysicalDeviceMemoryProperties mp;vkGetPhysicalDeviceMemoryProperties(physical,&mp);for(uint32_t i=0;i<mp.memoryTypeCount;i++)if((bits&(1u<<i)) && (mp.memoryTypes[i].propertyFlags&want)==want)return i;return 0;}
bool setup(){
    if(pipeline)return true;
    VkDescriptorSetLayoutBinding b[2]{};b[0].binding=0;b[0].descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;b[0].descriptorCount=1;b[0].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    b[1].binding=1;b[1].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;b[1].descriptorCount=1;b[1].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    VkDescriptorSetLayoutCreateInfo dl{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};dl.bindingCount=2;dl.pBindings=b;if(vkCreateDescriptorSetLayout(device,&dl,nullptr,&set_layout))return false;
    VkPushConstantRange pc{VK_SHADER_STAGE_COMPUTE_BIT,0,12};VkPipelineLayoutCreateInfo pl{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};pl.setLayoutCount=1;pl.pSetLayouts=&set_layout;pl.pushConstantRangeCount=1;pl.pPushConstantRanges=&pc;
    if(vkCreatePipelineLayout(device,&pl,nullptr,&layout))return false;
    VkShaderModuleCreateInfo mi{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};mi.codeSize=sizeof code;mi.pCode=code;VkShaderModule module{};if(vkCreateShaderModule(device,&mi,nullptr,&module))return false;
    VkComputePipelineCreateInfo ci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};ci.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;ci.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;ci.stage.module=module;ci.stage.pName="main";ci.layout=layout;
    VkResult r=vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&ci,nullptr,&pipeline);vkDestroyShaderModule(device,module,nullptr);if(r)return false;
    VkDescriptorPoolSize ps[2]{{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,2},{VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,2}};VkDescriptorPoolCreateInfo dp{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};dp.maxSets=2;dp.poolSizeCount=2;dp.pPoolSizes=ps;
    if(vkCreateDescriptorPool(device,&dp,nullptr,&pool))return false;
    VkDescriptorSetLayout ls[2]={set_layout,set_layout};VkDescriptorSetAllocateInfo ai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};ai.descriptorPool=pool;ai.descriptorSetCount=2;ai.pSetLayouts=ls;if(vkAllocateDescriptorSets(device,&ai,sets))return false;
    VkSamplerCreateInfo si{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};si.magFilter=si.minFilter=VK_FILTER_NEAREST;si.addressModeU=si.addressModeV=si.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;if(vkCreateSampler(device,&si,nullptr,&sampler))return false;
    return true;
}
bool target(uint32_t width,uint32_t height){
    if(image && w==width && h==height)return true;
    if(view)vkDestroyImageView(device,view,nullptr);if(image)vkDestroyImage(device,image,nullptr);if(memory)vkFreeMemory(device,memory,nullptr);view={};image={};memory={};
    VkImageCreateInfo ic{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};ic.imageType=VK_IMAGE_TYPE_2D;ic.format=VK_FORMAT_R8G8B8A8_UNORM;ic.extent={width,height,1};ic.mipLevels=ic.arrayLayers=1;ic.samples=VK_SAMPLE_COUNT_1_BIT;
    ic.tiling=VK_IMAGE_TILING_OPTIMAL;ic.usage=VK_IMAGE_USAGE_STORAGE_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT;if(vkCreateImage(device,&ic,nullptr,&image))return false;
    VkMemoryRequirements mr;vkGetImageMemoryRequirements(device,image,&mr);VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=mr.size;ma.memoryTypeIndex=memory_type(mr.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    if(vkAllocateMemory(device,&ma,nullptr,&memory) || vkBindImageMemory(device,image,memory,0))return false;
    VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=image;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=ic.format;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};if(vkCreateImageView(device,&vi,nullptr,&view))return false;
    w=width;h=height;return true;
}
// Records the pass; on success the caller blits from rcas::image (TRANSFER_SRC_OPTIMAL) instead of the source.
bool record(VkCommandBuffer cmd,unsigned f,VkImage source,VkFormat format,uint32_t width,uint32_t height){
    if(!enabled() || (format!=VK_FORMAT_R8G8B8A8_UNORM && format!=VK_FORMAT_B8G8R8A8_UNORM))return false;
    if(!setup() || !target(width,height)){on=0;__android_log_print(ANDROID_LOG_WARN,"dm-vulkan","RCAS setup failed: sharpening off");return false;}
    if(source_views[f])vkDestroyImageView(device,source_views[f],nullptr);   // this flight's previous frame has retired (its fence was waited)
    VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=source;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=format;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    if(vkCreateImageView(device,&vi,nullptr,&source_views[f])){source_views[f]={};return false;}
    VkDescriptorImageInfo si{sampler,source_views[f],VK_IMAGE_LAYOUT_GENERAL},di{VK_NULL_HANDLE,view,VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet wr[2]{};for(auto &x:wr){x.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;x.dstSet=sets[f];x.descriptorCount=1;}
    wr[0].dstBinding=0;wr[0].descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;wr[0].pImageInfo=&si;
    wr[1].dstBinding=1;wr[1].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;wr[1].pImageInfo=&di;vkUpdateDescriptorSets(device,2,wr,0,nullptr);
    VkImageMemoryBarrier b[2]{};
    for(auto &x:b){x.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;x.srcQueueFamilyIndex=x.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;x.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};}
    b[0].image=source;b[0].oldLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b[0].newLayout=VK_IMAGE_LAYOUT_GENERAL;b[0].srcAccessMask=VK_ACCESS_MEMORY_WRITE_BIT;b[0].dstAccessMask=VK_ACCESS_SHADER_READ_BIT;
    b[1].image=image;b[1].oldLayout=VK_IMAGE_LAYOUT_UNDEFINED;b[1].newLayout=VK_IMAGE_LAYOUT_GENERAL;b[1].srcAccessMask=VK_ACCESS_TRANSFER_READ_BIT;b[1].dstAccessMask=VK_ACCESS_SHADER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,0,nullptr,2,b);
    vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&sets[f],0,nullptr);
    struct{int32_t w,h;float s;}push{int32_t(width),int32_t(height),sharpness};vkCmdPushConstants(cmd,layout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof push,&push);
    vkCmdDispatch(cmd,(width+7)/8,(height+7)/8,1);
    b[0].oldLayout=VK_IMAGE_LAYOUT_GENERAL;b[0].newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b[0].srcAccessMask=VK_ACCESS_SHADER_READ_BIT;b[0].dstAccessMask=0;   // back to the layout the engine tracks
    b[1].oldLayout=VK_IMAGE_LAYOUT_GENERAL;b[1].newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b[1].srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;b[1].dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,2,b);
    return true;
}
}
// [BL2] FSR 1 EASU at the present: the game's frame (e.g. 1280x720) upscaled to the window with edge-adaptive spatial upsampling
// (shaders/fsr1_easu.comp, offline compiled, MIT FsrEasuF). DM_GFX_FSR=1 turns it on; the window buffer then takes the screen's size and
// this compute pass replaces the display controller's scaling. RCAS sharpens its output when the gear's sharpening is on (FSR 1's second
// pass). Only 8-bit RGBA/BGRA frames, like RCAS.
namespace easu {
const uint32_t code[]={
#include "shaders/fsr1_easu.spv.inc"
};
int on=-1; VkImage image{}; VkDeviceMemory memory{}; VkImageView view{}; uint32_t w=0,h=0;
VkDescriptorSetLayout set_layout{}; VkPipelineLayout layout{}; VkPipeline pipeline{}; VkDescriptorPool pool{}; VkDescriptorSet sets[2]{};
VkSampler sampler{}; VkImageView source_views[2]{};
bool enabled(){
    if(on<0){ const char *e=getenv("DM_GFX_FSR"); on = e && *e && atoi(e)>0;
        if(on) __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","FSR 1 EASU at present (DM_GFX_FSR): the frame is upscaled to the window on the GPU"); }
    return on>0;
}
uint32_t memory_type(uint32_t bits,VkMemoryPropertyFlags want){
    VkPhysicalDeviceMemoryProperties mp;vkGetPhysicalDeviceMemoryProperties(physical,&mp);
    for(uint32_t i=0;i<mp.memoryTypeCount;i++)if((bits&(1u<<i)) && (mp.memoryTypes[i].propertyFlags&want)==want)return i;
    return 0;
}
bool setup(){
    if(pipeline)return true;
    VkDescriptorSetLayoutBinding b[2]{};b[0].binding=0;b[0].descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;b[0].descriptorCount=1;b[0].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    b[1].binding=1;b[1].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;b[1].descriptorCount=1;b[1].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    VkDescriptorSetLayoutCreateInfo dl{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};dl.bindingCount=2;dl.pBindings=b;if(vkCreateDescriptorSetLayout(device,&dl,nullptr,&set_layout))return false;
    VkPushConstantRange pc{VK_SHADER_STAGE_COMPUTE_BIT,0,16};VkPipelineLayoutCreateInfo pl{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};pl.setLayoutCount=1;pl.pSetLayouts=&set_layout;pl.pushConstantRangeCount=1;pl.pPushConstantRanges=&pc;
    if(vkCreatePipelineLayout(device,&pl,nullptr,&layout))return false;
    VkShaderModuleCreateInfo mi{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};mi.codeSize=sizeof code;mi.pCode=code;VkShaderModule module{};if(vkCreateShaderModule(device,&mi,nullptr,&module))return false;
    VkComputePipelineCreateInfo ci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};ci.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;ci.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;ci.stage.module=module;ci.stage.pName="main";ci.layout=layout;
    VkResult r=vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&ci,nullptr,&pipeline);vkDestroyShaderModule(device,module,nullptr);if(r)return false;
    VkDescriptorPoolSize ps[2]{{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,2},{VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,2}};VkDescriptorPoolCreateInfo dp{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};dp.maxSets=2;dp.poolSizeCount=2;dp.pPoolSizes=ps;
    if(vkCreateDescriptorPool(device,&dp,nullptr,&pool))return false;
    VkDescriptorSetLayout ls[2]={set_layout,set_layout};VkDescriptorSetAllocateInfo ai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};ai.descriptorPool=pool;ai.descriptorSetCount=2;ai.pSetLayouts=ls;if(vkAllocateDescriptorSets(device,&ai,sets))return false;
    VkSamplerCreateInfo si{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};si.magFilter=si.minFilter=VK_FILTER_NEAREST;si.addressModeU=si.addressModeV=si.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;if(vkCreateSampler(device,&si,nullptr,&sampler))return false;
    return true;
}
bool target(uint32_t width,uint32_t height){
    if(image && w==width && h==height)return true;
    if(view)vkDestroyImageView(device,view,nullptr);if(image)vkDestroyImage(device,image,nullptr);if(memory)vkFreeMemory(device,memory,nullptr);view={};image={};memory={};
    VkImageCreateInfo ic{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};ic.imageType=VK_IMAGE_TYPE_2D;ic.format=VK_FORMAT_R8G8B8A8_UNORM;ic.extent={width,height,1};ic.mipLevels=ic.arrayLayers=1;ic.samples=VK_SAMPLE_COUNT_1_BIT;
    ic.tiling=VK_IMAGE_TILING_OPTIMAL;ic.usage=VK_IMAGE_USAGE_STORAGE_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT;if(vkCreateImage(device,&ic,nullptr,&image))return false;
    VkMemoryRequirements mr;vkGetImageMemoryRequirements(device,image,&mr);VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=mr.size;ma.memoryTypeIndex=memory_type(mr.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    if(vkAllocateMemory(device,&ma,nullptr,&memory) || vkBindImageMemory(device,image,memory,0))return false;
    VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=image;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=ic.format;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};if(vkCreateImageView(device,&vi,nullptr,&view))return false;
    w=width;h=height;return true;
}
// records the pass; on success the caller blits from easu::image (TRANSFER_SRC_OPTIMAL) 1:1 instead of the source
bool record(VkCommandBuffer cmd,unsigned f,VkImage source,VkFormat format,uint32_t sw,uint32_t sh,uint32_t dw,uint32_t dh){
    if(!enabled() || (format!=VK_FORMAT_R8G8B8A8_UNORM && format!=VK_FORMAT_B8G8R8A8_UNORM))return false;
    if(!dw || !dh || !sw || !sh)return false;
    if(!setup() || !target(dw,dh)){on=0;__android_log_print(ANDROID_LOG_WARN,"dm-vulkan","FSR EASU setup failed: upscaling off");return false;}
    if(source_views[f])vkDestroyImageView(device,source_views[f],nullptr);   // this flight's previous frame has retired (its fence was waited)
    VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=source;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=format;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    if(vkCreateImageView(device,&vi,nullptr,&source_views[f])){source_views[f]={};return false;}
    VkDescriptorImageInfo si{sampler,source_views[f],VK_IMAGE_LAYOUT_GENERAL},di{VK_NULL_HANDLE,view,VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet wr[2]{};for(auto &x:wr){x.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;x.dstSet=sets[f];x.descriptorCount=1;}
    wr[0].dstBinding=0;wr[0].descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;wr[0].pImageInfo=&si;
    wr[1].dstBinding=1;wr[1].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;wr[1].pImageInfo=&di;vkUpdateDescriptorSets(device,2,wr,0,nullptr);
    VkImageMemoryBarrier b[2]{};
    for(auto &x:b){x.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;x.srcQueueFamilyIndex=x.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;x.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};}
    b[0].image=source;b[0].oldLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b[0].newLayout=VK_IMAGE_LAYOUT_GENERAL;b[0].srcAccessMask=VK_ACCESS_MEMORY_WRITE_BIT;b[0].dstAccessMask=VK_ACCESS_SHADER_READ_BIT;
    b[1].image=image;b[1].oldLayout=VK_IMAGE_LAYOUT_UNDEFINED;b[1].newLayout=VK_IMAGE_LAYOUT_GENERAL;b[1].srcAccessMask=VK_ACCESS_TRANSFER_READ_BIT;b[1].dstAccessMask=VK_ACCESS_SHADER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,0,nullptr,2,b);
    vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&sets[f],0,nullptr);
    struct{float sw,sh,dw,dh;}push{float(sw),float(sh),float(dw),float(dh)};vkCmdPushConstants(cmd,layout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof push,&push);
    vkCmdDispatch(cmd,(dw+7)/8,(dh+7)/8,1);
    b[0].oldLayout=VK_IMAGE_LAYOUT_GENERAL;b[0].newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b[0].srcAccessMask=VK_ACCESS_SHADER_READ_BIT;b[0].dstAccessMask=0;   // back to the layout the engine tracks
    b[1].oldLayout=VK_IMAGE_LAYOUT_GENERAL;b[1].newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b[1].srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;b[1].dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,2,b);
    return true;
}
}
#ifdef DM_TL2_MAIN   // [DOS2] Torchlight II main addresses: tl2 build only
extern "C" int (*dm_present_pillarbox)(void);   // [TL2] hle_tl2_wide.c registers it (translation thread, at the present): 0 none, 1 squeeze, 2 band 16:9, 3 band stretched
// [TL2] hle_tl2_icons.c: the HUD action bar's icon rectangles (source pixels) to copy out of this frame, and the copied pixels after the
// frame's fence. A host-visible buffer per flight; the copy is recorded into the present's own command buffer (the source is already in
// TRANSFER_SRC_OPTIMAL for the blit), so it adds no wait; nothing is recorded unless a batch is due (at most 4 a second).
extern "C" int (*dm_present_icon_want)(int32_t,int32_t,int32_t,int32_t,int32_t(*)[4],int);
extern "C" void (*dm_present_icon_done)(int,const int32_t(*)[4],const uint8_t*,int);
namespace icons {
enum{MAXN=8,MAXPX=160};
VkBuffer buf[2]{};VkDeviceMemory mem[2]{};void *map[2]{};bool coherent[2]{},pend[2]{};int n[2]{},bgra[2]{};int32_t rect[2][MAXN][4];
bool ensure(unsigned f){
    if(buf[f])return true;
    VkBufferCreateInfo bc{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bc.size=VkDeviceSize(MAXN)*MAXPX*MAXPX*4;bc.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT;if(vkCreateBuffer(device,&bc,nullptr,&buf[f]))return buf[f]=VK_NULL_HANDLE,false;
    VkMemoryRequirements mr;vkGetBufferMemoryRequirements(device,buf[f],&mr);VkPhysicalDeviceMemoryProperties mp;vkGetPhysicalDeviceMemoryProperties(physical,&mp);
    int pick=-1;for(int pass=0;pass<2 && pick<0;pass++)for(uint32_t i=0;i<mp.memoryTypeCount;i++){VkMemoryPropertyFlags fl=mp.memoryTypes[i].propertyFlags;
        VkMemoryPropertyFlags want=pass?VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT:VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_CACHED_BIT;
        if((mr.memoryTypeBits&(1u<<i)) && (fl&want)==want){pick=int(i);coherent[f]=(fl&VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)!=0;break;}}
    VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=mr.size;ma.memoryTypeIndex=uint32_t(pick<0?0:pick);
    if(pick<0||vkAllocateMemory(device,&ma,nullptr,&mem[f])||vkBindBufferMemory(device,buf[f],mem[f],0)||vkMapMemory(device,mem[f],0,VK_WHOLE_SIZE,0,&map[f])){
        __android_log_print(ANDROID_LOG_WARN,"dm-vulkan","TL2 HUD icon readback buffer failed: no button icons");vkDestroyBuffer(device,buf[f],nullptr);buf[f]=VK_NULL_HANDLE;return false;}
    return true;
}
void collect(unsigned f){
    if(!pend[f])return;pend[f]=false;
    if(!coherent[f]){VkMappedMemoryRange mr{VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE};mr.memory=mem[f];mr.size=VK_WHOLE_SIZE;vkInvalidateMappedMemoryRanges(device,1,&mr);}
    if(dm_present_icon_done)dm_present_icon_done(n[f],rect[f],static_cast<const uint8_t*>(map[f]),bgra[f]);
}
void record(VkCommandBuffer cmd,unsigned f,bool fence_idle,VkImage source,VkFormat format,int32_t x,int32_t y,int32_t w,int32_t h){
    if(!dm_present_icon_want || (format!=VK_FORMAT_R8G8B8A8_UNORM && format!=VK_FORMAT_B8G8R8A8_UNORM && format!=VK_FORMAT_R8G8B8A8_SRGB && format!=VK_FORMAT_B8G8R8A8_SRGB))return;
    if(pend[f] && fence_idle)collect(f);   // a batch whose fence was retired another way (swapchain rebuild drains the queue)
    if(pend[f])return;
    int32_t r[MAXN][4];int k=dm_present_icon_want(x,y,w,h,r,MAXN);if(k<=0 || !ensure(f))return;
    VkBufferImageCopy c[MAXN]{};VkDeviceSize off=0;
    for(int i=0;i<k;i++){c[i].bufferOffset=off;c[i].imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};c[i].imageOffset={r[i][0],r[i][1],0};c[i].imageExtent={uint32_t(r[i][2]),uint32_t(r[i][3]),1};
        off+=VkDeviceSize(r[i][2])*r[i][3]*4;memcpy(rect[f][i],r[i],sizeof r[i]);}
    vkCmdCopyImageToBuffer(cmd,source,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,buf[f],uint32_t(k),c);
    VkBufferMemoryBarrier b{VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER};b.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;b.dstAccessMask=VK_ACCESS_HOST_READ_BIT;b.srcQueueFamilyIndex=b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;b.buffer=buf[f];b.size=VK_WHOLE_SIZE;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,0,nullptr,1,&b,0,nullptr);
    n[f]=k;bgra[f]=format==VK_FORMAT_B8G8R8A8_UNORM||format==VK_FORMAT_B8G8R8A8_SRGB;pend[f]=true;
}
}
#endif
int present_body(VkImage source,VkFormat source_format,uint32_t width,uint32_t height,const int32_t crop[4],int pre_index=-1,uint64_t pre_gen=0);
int present(void*,void*,VkImage source,VkFormat source_format,uint32_t width,uint32_t height,const int32_t crop[4],int32_t){
    std::lock_guard<std::mutex> render_lock(render_mutex);
    pin_update();
    return present_body(source,source_format,width,height,crop);
}
// [present-thread] The present itself; the caller holds render_mutex (present(), the present thread, or DM_GFX_PRESENT_THREAD=2 inline).
// [DOS2] NR-11: pre_index >= 0 = the swapchain image the engine took for this frame (its acquire already waited on by the engine's tail
// batch, the image in GENERAL): no acquire, no semaphore wait, the blit as before. Dropped when the swapchain is recreated first.
int present_body(VkImage source,VkFormat source_format,uint32_t width,uint32_t height,const int32_t crop[4],int pre_index,uint64_t pre_gen){
    VkFormatProperties sp;vkGetPhysicalDeviceFormatProperties(physical,source_format,&sp);if(!(sp.optimalTilingFeatures&VK_FORMAT_FEATURE_BLIT_SRC_BIT))return VK_ERROR_FORMAT_NOT_SUPPORTED;
    int x=0,y=0,w=int(width),h=int(height);if(crop&&crop[2]>0&&crop[3]>0){x=std::clamp(crop[0],0,w);y=std::clamp(crop[1],0,h);w=std::min(crop[2],int(width)-x);h=std::min(crop[3],int(height)-y);}if(w<=0||h<=0)return VK_ERROR_INITIALIZATION_FAILED;
    if(easu::enabled() && present_native){   // [BL2] FSR: the window buffer must be the screen's size, so the GPU upscales instead of the display controller
        present_native=false;native_w=native_h=0;swap_dirty=true;
        if(active) ANativeWindow_setBuffersGeometry(active,0,0,0);   // back to the window's own size
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","FSR: window buffer = the screen's size (display scaling off, EASU at present)");
    }
    for(;;){
    if(present_native && surface && active && (native_w!=w || native_h!=h)){   // the next swapchain takes this size (currentExtent follows the buffer geometry)
        int g=ANativeWindow_setBuffersGeometry(active,w,h,0);native_w=w;native_h=h;swap_dirty=true;
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Present at the game's output size %dx%d result=%d (marker gfx-present-native)",w,h,g);}
    // 后台等待释放UI锁；保留同一源帧，恢复并真正呈现后才返回成功。
    // Suspend without the UI lock; keep this source frame until it is presented.
    wait_window();
    VkResult r;
    if(!surface||window_changed()){
        if((r=vkQueueWaitIdle(queue)))return r;
        r=VkResult(create_surface());
        if(r==VK_NOT_READY)continue;
        if(r==VK_ERROR_SURFACE_LOST_KHR){uint64_t bad=active_generation;destroy_swap();wait_window_change(bad);continue;}
        if(r)return r;swap_dirty=true;pre_index=-1;
    }
    if(swap_dirty){pre_index=-1;
        if((r=vkQueueWaitIdle(queue)))return r;
        r=VkResult(create_swap());
        if(r==VK_NOT_READY||r==VK_ERROR_OUT_OF_DATE_KHR){wait_resize();continue;}
        if(r==VK_ERROR_SURFACE_LOST_KHR){uint64_t bad=active_generation;destroy_swap();wait_window_change(bad);continue;}
        if(r)return r;swap_dirty=false;
    }
    VkFormatProperties dp;vkGetPhysicalDeviceFormatProperties(physical,swap_format,&dp);if(!(dp.optimalTilingFeatures&VK_FORMAT_FEATURE_BLIT_DST_BIT))return VK_ERROR_FORMAT_NOT_SUPPORTED;
    // 有限获取超时让渲染线程重新检查Surface代数，UI从不等待驱动。
    // A bounded acquire lets rendering observe lifecycle changes; UI never waits on the driver.
    unsigned f=overlap?flight:0;VkCommandPool pool=f?overlap_pool:command_pool;VkCommandBuffer cmd=f?overlap_command:command;VkSemaphore acq=f?overlap_acquired:acquired;VkFence done=f?overlap_fence:fence;
    if(in_flight[f]){XTRACE_BEGIN("dm-present-fence");r=vkWaitForFences(device,1,&done,VK_TRUE,10000000000ull);XTRACE_END();if(r)return r;if((r=vkResetFences(device,1,&done)))return r;in_flight[f]=false;
#ifdef DM_TL2_MAIN   // [DOS2] Torchlight II main addresses: tl2 build only
        icons::collect(f);
#endif
        if(nrr::mode==NRR_MODE_CHECK)nrr::probe_collect(f);   // [DOS2] NR-20 =2
        if(present_stamped[f]){uint64_t t[2]{};if(vkGetQueryPoolResults(device,present_queries,f*2,2,sizeof t,t,8,VK_QUERY_RESULT_64_BIT)==VK_SUCCESS && t[1]>=t[0]){present_gpu_ns+=double(t[1]-t[0])*present_tick_ns;
            if(++present_timed==300){__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","NVN PERF present_gpu_us=%.0f extent=%ux%u (marker gfx-present-timing)",present_gpu_ns/present_timed/1e3,extent.width,extent.height);present_gpu_ns=0;present_timed=0;}}present_stamped[f]=false;}}
    uint32_t index=0;bool waited=false;   // [DOS2] NR-11: waited = the engine's image (pre_index); a parked image is waited on like an own acquire
    bool parked=false;
    if(pre_index>=0 && pre_gen==nrp::gen && uint32_t(pre_index)<images.size()){index=uint32_t(pre_index);waited=true;r=VK_SUCCESS;++nrp::blits;}
    else if(nrp::on()){std::lock_guard<std::mutex> l(nrp::mu);if(nrp::park.have && nrp::park.gen==nrp::gen){index=nrp::park.index;acq=nrp::park.sem;r=nrp::park.sub?VK_SUBOPTIMAL_KHR:VK_SUCCESS;parked=true;}nrp::park=nrp::Park{};}
    pre_index=-1;
    if(!waited && !parked){XTRACE_BEGIN("dm-acquire");r=vkAcquireNextImageKHR(device,swapchain,50000000ull,acq,VK_NULL_HANDLE,&index);XTRACE_END();}
    if(r==VK_TIMEOUT||r==VK_NOT_READY)continue;
    if(r==VK_ERROR_OUT_OF_DATE_KHR){swap_dirty=true;wait_resize();continue;}
    if(r==VK_ERROR_SURFACE_LOST_KHR){if((r=vkQueueWaitIdle(queue)))return r;uint64_t bad=active_generation;destroy_swap();wait_window_change(bad);continue;}
    bool rebuild=r==VK_SUBOPTIMAL_KHR;if(r!=VK_SUCCESS&&!rebuild)return r;
    r=vkResetCommandPool(device,pool,0);if(r)return r;VkCommandBufferBeginInfo bi{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};bi.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;if((r=vkBeginCommandBuffer(cmd,&bi)))return r;
    bool stamp=present_timing && overlap;if(stamp && !present_queries){VkQueryPoolCreateInfo q{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO};q.queryType=VK_QUERY_TYPE_TIMESTAMP;q.queryCount=4;if(vkCreateQueryPool(device,&q,nullptr,&present_queries))stamp=false;
        VkPhysicalDeviceProperties pp;vkGetPhysicalDeviceProperties(physical,&pp);present_tick_ns=pp.limits.timestampPeriod;}
    if(stamp){vkCmdResetQueryPool(cmd,present_queries,f*2,2);vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,present_queries,f*2);}
    // [DOS2] NR-20 DM_NR_ROTATE: a pre-rotated swapchain gets the turned draw (nrr::draw: its render pass makes the layouts) instead of the
    // barrier, clear and blit below; the window rectangle math is the same
    const bool turned=nrr::pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
    VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};barrier.srcQueueFamilyIndex=barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;barrier.image=images[index];barrier.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};barrier.oldLayout=waited?VK_IMAGE_LAYOUT_GENERAL:VK_IMAGE_LAYOUT_UNDEFINED;barrier.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;barrier.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
    if(waited)barrier.srcAccessMask=VK_ACCESS_MEMORY_WRITE_BIT|VK_ACCESS_MEMORY_READ_BIT;   // [DOS2] NR-11: the engine's passes / copy-back wrote it after their batch waited for the acquire
    // 换布局须在获取信号量的等待阶段（下面提交的 TRANSFER）之后：源阶段写 TOP_OF_PIPE 时，换布局不等信号量，可能在呈现引擎
    // 读完这张图之前就发生（验证层同步检查：SYNC-HAZARD-WRITE-AFTER-READ）。
    // The layout transition must come after the acquire semaphore's wait stage (TRANSFER, in the submit below). With
    // TOP_OF_PIPE as the source stage it does not wait for the semaphore and can happen before the presentation engine has
    // finished reading the image (synchronization validation: SYNC-HAZARD-WRITE-AFTER-READ).
    if(!turned)vkCmdPipelineBarrier(cmd,waited?VK_PIPELINE_STAGE_ALL_COMMANDS_BIT:VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&barrier);
    else if(waited){VkMemoryBarrier mb{VK_STRUCTURE_TYPE_MEMORY_BARRIER};mb.srcAccessMask=VK_ACCESS_MEMORY_WRITE_BIT;mb.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;   // not reached: NR-11 takes no image of a rotated swapchain
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,0,1,&mb,0,nullptr,0,nullptr);}
    barrier.srcAccessMask=0;
    double aw=w,ah=h;   // the shape the picture is shown at (normally the source's)
    int bx=x,bw=w;      // the source columns shown (normally all of them)
#ifdef DM_TL2_MAIN   // [DOS2] Torchlight II main addresses: tl2 build only
    // [TL2] hle_tl2_wide.c, while a loading screen is up in widescreen: 1 = the whole W x 1080 window (its 1920 canvas stretched to W)
    // squeezed to 16:9, 2 = only its centred 16:9 band (where the hybrid UI drew the loading art) at 16:9, 3 = that band stretched to the
    // screen. Black side bars from the letterbox clear below; a squeeze / stretch samples linearly when the format allows it
    int pmode=dm_present_pillarbox && w*9>h*16 ? dm_present_pillarbox() : 0;
    bool pillar=pmode==1;
    if(pmode==1)aw=h*16.0/9.0;
    else if(pmode==2 || pmode==3){int band=std::min(w,int(std::lround(h*16.0/9.0)));bx=x+(w-band)/2;bw=band;if(pmode==2)aw=band;else pillar=true;}
#endif
    double scale=std::min(double(extent.width)/aw,double(extent.height)/ah);int dw=std::max(1,int(aw*scale)),dh=std::max(1,int(ah*scale)),dx=(int(extent.width)-dw)/2,dy=(int(extent.height)-dh)/2;
    if(!turned && (dx || dy || dw!=int(extent.width) || dh!=int(extent.height))){   // letterbox bars only where the blit leaves part of the image (turned: the draw's render pass clears)
        VkClearColorValue black{};vkCmdClearColorImage(cmd,images[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&black,1,&barrier.subresourceRange);
        barrier.oldLayout=barrier.newLayout;barrier.srcAccessMask=barrier.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&barrier);}
    VkImageBlit blit{};blit.srcSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};blit.dstSubresource=blit.srcSubresource;blit.srcOffsets[0]={bx,y,0};blit.srcOffsets[1]={bx+bw,y+h,1};blit.dstOffsets[0]={dx,dy,0};blit.dstOffsets[1]={dx+dw,dy+dh,1};
    // 最近邻不要求额外线性过滤能力。鸿蒙：游戏出图比屏幕小、要放大，格式支持时用线性，不然像素发硬、斜边锯齿。
    // Nearest needs no extra linear-filter support. HarmonyOS: the game image is smaller than the screen and gets upscaled; use linear when the format supports it, otherwise pixels look blocky and diagonals jagged.
    VkFilter filter=VK_FILTER_NEAREST;
#ifdef __OHOS__
    if(sp.optimalTilingFeatures&VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT)filter=VK_FILTER_LINEAR;
#endif
#ifdef DM_TL2_MAIN   // [DOS2] Torchlight II main addresses: tl2 build only
    if(pillar && (sp.optimalTilingFeatures&VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT))filter=VK_FILTER_LINEAR;
#endif
#ifdef DM_TL2_MAIN   // [DOS2] Torchlight II main addresses: tl2 build only
    icons::record(cmd,f,!in_flight[f],source,source_format,x,y,w,h);
#endif
    bool sharpened=false;
    if(turned){   // [DOS2] NR-20: the window texture turned into the image, at the blit's rectangle mapped into it (RCAS on: the draw sharpens, NR-20-rcas.md)
        const bool sharpen=rcas::enabled() && (source_format==VK_FORMAT_R8G8B8A8_UNORM || source_format==VK_FORMAT_B8G8R8A8_UNORM);   // = rcas::record's own test
        if(!nrr::draw(cmd,f,index,source,source_format,width,height,bx,y,bw,h,nrr_rect{dx,dy,dw,dh},extent.width,extent.height,filter==VK_FILTER_LINEAR,sharpen,rcas::sharpness,&sharpened)){
            nrr::fail("the window texture's view",VK_ERROR_OUT_OF_HOST_MEMORY);swap_dirty=true;}}   // this frame black, the next present makes an identity swapchain
    else{
    bool fsr=false;
    int bsx=bx, bsy=y, bsw=bw, bsh=h;   // the source rect the blit reads
    if(!turned && easu::enabled() && x==0 && y==0 && w==int(width) && h==int(height)){   // [BL2] FSR 1 EASU: whole frame, no crop
        if(easu::record(cmd,f,source,source_format,width,height,dw,dh)){ bsx=0; bsy=0; bsw=int(dw); bsh=int(dh); fsr=true; }
    }
    sharpened=rcas::record(cmd,f,fsr?easu::image:source,fsr?VK_FORMAT_R8G8B8A8_UNORM:source_format,fsr?dw:w,fsr?dh:h);
    VkImageBlit src=blit;   // FSR: 1:1 from the upscaled image; otherwise the source rect as before
    if(fsr){src.srcOffsets[0]={bsx,bsy,0};src.srcOffsets[1]={bsx+bsw,bsy+bsh,1};}
    vkCmdBlitImage(cmd,sharpened?rcas::image:(fsr?easu::image:source),VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,images[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&src,filter);
    // 同队列后续写入必须等源图读取完成；即使下一次图像布局未改变也建立 WAR 执行依赖。
    // Order subsequent same-queue writes after the source read, including reuse without a layout change.
    VkMemoryBarrier source_read{VK_STRUCTURE_TYPE_MEMORY_BARRIER};source_read.srcAccessMask=VK_ACCESS_TRANSFER_READ_BIT;source_read.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,1,&source_read,0,nullptr,0,nullptr);
    barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;barrier.newLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;barrier.dstAccessMask=0;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,0,0,nullptr,0,nullptr,1,&barrier);
    }
    if(stamp){vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,present_queries,f*2+1);present_stamped[f]=true;}
    if(nrr::mode==NRR_MODE_CHECK)nrr::probe_record(cmd,f,source,source_format,width,height,bx,y,bw,h,nrr_rect{dx,dy,dw,dh},extent.width,extent.height,filter==VK_FILTER_LINEAR,swap_format,!turned && sharpened?rcas::image:VK_NULL_HANDLE,rcas::sharpness);   // [DOS2] NR-20 =2: after the timing stamp (RCAS: against its own image)
    if((r=vkEndCommandBuffer(cmd)))return r;VkPipelineStageFlags stage=turned?VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT:VK_PIPELINE_STAGE_TRANSFER_BIT;VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.waitSemaphoreCount=waited?0:1;submit.pWaitSemaphores=&acq;submit.pWaitDstStageMask=&stage;submit.commandBufferCount=1;submit.pCommandBuffers=&cmd;submit.signalSemaphoreCount=1;submit.pSignalSemaphores=&finished[index];
    if((r=vkQueueSubmit(queue,1,&submit,done)))return r;in_flight[f]=true;VkPresentInfoKHR pi{VK_STRUCTURE_TYPE_PRESENT_INFO_KHR};pi.waitSemaphoreCount=1;pi.pWaitSemaphores=&finished[index];pi.swapchainCount=1;pi.pSwapchains=&swapchain;pi.pImageIndices=&index;
#ifdef __OHOS__
    // 期望上屏时刻（鸿蒙 SET_DESIRED_PRESENT_TIMESTAMP）：上屏节奏 = 上次期望时刻 + 一个出图档周期；早到的帧由合成器按时放出，翻译线程不等；
    // 落后时从当前时刻重新起拍。翻译完成时刻的抖动（±5 ms）不再让一帧在屏上停 3 或 5 个刷新。DM_PRESENT_TS=0 关。
    // Desired display time (HarmonyOS SET_DESIRED_PRESENT_TIMESTAMP): cadence = previous desired time + one present-tier period; an early frame is released on time by the compositor
    // without the translation thread waiting; when late, restart the cadence from now. Jitter in translation completion (±5 ms) no longer leaves a frame on screen for 3 or 5 refreshes.
    {static int on=-1;if(on<0){const char *e=getenv("DM_PRESENT_TS");on=!(e&&*e=='0');}static int64_t tgt;double per=dm_present_period();
     if(on&&per>0&&active){timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);int64_t now=int64_t(ts.tv_sec)*1000000000+ts.tv_nsec,p=int64_t(per*1e9),next=tgt?tgt+p:now;
      if(tgt&&now>tgt+p+2000000)dm_present_late.fetch_add(1,std::memory_order_relaxed);if(next<now)next=now;if(next>now+2*p)next=now+p;tgt=next;OH_NativeWindow_NativeWindowHandleOpt(active,SET_DESIRED_PRESENT_TIMESTAMP,next);}}
#endif
#ifdef DM_GAME_DOOM
    dm_aperf_present(active,frame_rate_vote);   // ADPF work report + display rate vote (perf_android.c)
#endif
    XTRACE_BEGIN("dm-queue-present");VkResult pr=vkQueuePresentKHR(queue,&pi);XTRACE_END();
    // 呈现失败时先排空，拆除路径要求队列空闲。
    // Drain a failed present before teardown, which requires an idle queue.
    if(overlap){flight^=1;if(pr!=VK_SUCCESS && pr!=VK_SUBOPTIMAL_KHR && (r=vkQueueWaitIdle(queue)))return r;}
    else{if((r=vkWaitForFences(device,1,&done,VK_TRUE,10000000000ull)))return r;if((r=vkResetFences(device,1,&done)))return r;in_flight[0]=false;if((r=vkQueueWaitIdle(queue)))return r;
        if(nrr::mode==NRR_MODE_CHECK)nrr::probe_collect(0);   // [DOS2] NR-20 =2
#ifdef DM_TL2_MAIN   // [DOS2] Torchlight II main addresses: tl2 build only
        icons::collect(0);
#endif
    }
    if(pr==VK_ERROR_SURFACE_LOST_KHR){uint64_t bad=active_generation;destroy_swap();wait_window_change(bad);continue;}
    if(pr==VK_ERROR_OUT_OF_DATE_KHR){swap_dirty=true;wait_resize();continue;}
    if(pr!=VK_SUCCESS&&pr!=VK_SUBOPTIMAL_KHR)return pr;
    // 已成功呈现的帧不因尺寸瞬变报错；下帧再重建或等待可用尺寸。
    // Defer suboptimal recreation to the next frame, which can wait for a usable extent.
    if((rebuild||pr==VK_SUBOPTIMAL_KHR)&&surface_properties_changed())swap_dirty=true;
    // [DOS2] NR-20: while pre-rotated, the surface's transform is also polled (a turn of the phone the WSI does not report as SUBOPTIMAL)
    if(nrr::mode){if(turned && !swap_dirty && ++nrr::polls%NRR_POLL==0 && surface_properties_changed())swap_dirty=true;nrr::frame(turned,turned && sharpened);}
    return 0;
    }
}
// [DOS2] NR-11: the present of a frame the engine rendered into swapchain image `index` (its last batch signals finished[index]); the caller
// holds render_mutex. A swapchain recreated since the take: the frame is lost (counted), the next present goes the old way and recreates.
int nrp_direct_present(uint32_t index,uint64_t g){
    if(g!=nrp::gen || !swapchain || index>=images.size()){++nrp::lost;return 0;}
    VkPresentInfoKHR pi{VK_STRUCTURE_TYPE_PRESENT_INFO_KHR};pi.waitSemaphoreCount=1;pi.pWaitSemaphores=&finished[index];pi.swapchainCount=1;pi.pSwapchains=&swapchain;pi.pImageIndices=&index;
    XTRACE_BEGIN("dm-queue-present");const VkResult pr=vkQueuePresentKHR(queue,&pi);XTRACE_END();
    if(pr==VK_SUCCESS || pr==VK_SUBOPTIMAL_KHR){++nrp::direct;if(pr==VK_SUBOPTIMAL_KHR && surface_properties_changed())swap_dirty=true;return 0;}
    VkResult r=vkQueueWaitIdle(queue);if(r)return r;   // as present_body: a failed present drains before any teardown
    if(pr==VK_ERROR_OUT_OF_DATE_KHR){swap_dirty=true;++nrp::lost;return 0;}
    if(pr==VK_ERROR_SURFACE_LOST_KHR){destroy_swap();++nrp::lost;return 0;}   // the next present_body makes a surface (and waits for a window)
    return pr;
}
// [DOS2] NR-11, the present thread after each job (render_mutex held): acquire the next image now, off the translation thread, so the engine
// can take it for the next frame. Nothing while the engine holds one (the surface lets only one image be acquired at a time with the usual
// image count) or one is parked; a timeout / failure leaves nothing parked and the next job acquires as before.
void nrp_park_next(){
    if(!nrp::on() || nrp::views.empty() || !swapchain || !surface || swap_dirty || window_changed())return;
    if(nrr::pre!=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR)return;   // [DOS2] NR-20: pre-rotated, the engine takes no image (NRP_P_ROTATED)
    {std::lock_guard<std::mutex> l(nrp::mu);if(nrp::park.have || nrp::taken)return;}
    VkSemaphore s=nrp::next_sem();if(!s)return;uint32_t index=0;
    XTRACE_BEGIN("dm-nrp-park");const VkResult r=vkAcquireNextImageKHR(device,swapchain,50000000ull,s,VK_NULL_HANDLE,&index);XTRACE_END();
    if(r!=VK_SUCCESS && r!=VK_SUBOPTIMAL_KHR){++nrp::park_fails;if(r==VK_ERROR_OUT_OF_DATE_KHR)swap_dirty=true;return;}
    std::lock_guard<std::mutex> l(nrp::mu);nrp::park=nrp::Park{true,index,s,nrp::gen,r==VK_SUBOPTIMAL_KHR};++nrp::parks;
}
}
// [present-thread] PERF-D07 DM_GFX_PRESENT_THREAD (DOOM 2016 vulkan_present.cpp pt::loop; port-common/modules/present-thread). The engine
// reads the switch and calls dm_present_thread_set. 1: the engine hands each present (source image, format, size, crop) to the present
// thread, which runs the same present_body as before: wait for the flight's fence, acquire, letterbox clear, RCAS, blit, submit, queue
// present, swapchain / surface recreation, the window waits while the app is in the background, the ADPF report and frame-rate vote
// (dm_aperf_present). Order on the one VkQueue: the engine waits until every handed present has its blit submitted before it submits
// anything (dm_present_wait_submitted), and every queue call of both threads takes the queue lock, so the queue sees the same sequence as
// presenting inline. The translation thread keeps its pin (pin_update at the hand-off). 2: the same protocol (queue lock) run inline on
// the caller, no thread. 0 / unset: none of this runs and the queue lock is a no-op.
// The present thread is the ADPF session's first thread (it calls dm_aperf_present; perf_android.c makes the caller a member); the
// translation thread joins it by load like the game's other busy threads. Its cores: every core but the translation thread's, re-checked
// every 128 presents (it is created by the pinned translation thread and inherits that pin: DOOM 2016's DM_GFX_PRESENT_UNPIN lesson).
#if __has_include("../host/cpu_topo.h")
#include "../host/cpu_topo.h"   // [cpu-place] where the module is in: its plan's present mask
extern "C" const dm_cpu_plan_t *dm_cpu_plan(void) __attribute__((weak));
#define PT_HAVE_PLAN 1
#endif
#include <pthread.h>
#include <sys/resource.h>
#include <thread>
namespace pt {
struct Job{VkImage src;VkFormat fmt;uint32_t w,h;int32_t crop[4];bool has_crop;int nrp=0;uint32_t idx=0;uint64_t gen=0;};   // nrp: [DOS2] NR-11 1 = direct present of image idx, 2 = blit into the taken image idx
dmpt::Handoff<Job,4> &q=*new dmpt::Handoff<Job,4>();   // never destroyed: no exit-time destructor under a thread that waits on it
thread_local uint64_t last_ticket=0;   // the producer's latest hand-off (nvn_vk.c maps its present number to it)
std::atomic<int> translator_tid{0};std::atomic<uint64_t> inline_jobs{0};
unsigned cpus_of(int tid){cpu_set_t s;CPU_ZERO(&s);if(sched_getaffinity(tid,sizeof s,&s))return 0;unsigned m=0;for(int c=0;c<32;c++)if(CPU_ISSET(c,&s))m|=1u<<c;return m;}
// Every 128 presents: the wanted mask from DM_GFX_PRESENT_CPUS (hex), the cpu-place plan, or every core but the translation thread's.
void place(){
    static int ncpu=0;static unsigned all=0,khz[32];static unsigned placed=0,changes=0;
    if(!ncpu){long n=sysconf(_SC_NPROCESSORS_CONF);ncpu=int(n<1?8:n>32?32:n);all=ncpu>=32?~0u:(1u<<ncpu)-1;
        for(int c=0;c<ncpu;c++){char path[96];snprintf(path,sizeof path,"/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq",c);khz[c]=0;if(FILE *f=fopen(path,"rb")){if(fscanf(f,"%u",&khz[c])!=1)khz[c]=0;fclose(f);}}}
    const char *u=getenv("DM_GFX_PRESENT_UNPIN");if(u && *u=='0')return;   // DOOM 2016's switch: =0 keeps the inherited mask
    unsigned want=0,avoid=0;const char *why="";
    if(const char *e=getenv("DM_GFX_PRESENT_CPUS");e && *e){want=unsigned(strtoul(e,nullptr,16))&all;why="DM_GFX_PRESENT_CPUS";}
#ifdef PT_HAVE_PLAN
    if(!want && dm_cpu_plan){const dm_cpu_plan_t *p=dm_cpu_plan();if(p && p->present){want=p->present&all;why="cpu plan";}}
#endif
    if(!want){const int t=translator_tid.load(std::memory_order_relaxed);avoid=pin_mask?pin_mask:t?cpus_of(t):0;want=dmpt::place_mask(all,avoid,khz,ncpu);why=pin_mask?"all but the pin":"all but the translation thread's cores";}
    if(!want)return;
    const unsigned now=cpus_of(0);if(now==want && placed==want)return;
    cpu_set_t s;CPU_ZERO(&s);for(int c=0;c<32;c++)if(want>>c&1)CPU_SET(c,&s);const int r=sched_setaffinity(0,sizeof s,&s),err=r?errno:0;
    if(placed!=want || ++changes<=4)__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","NVN present thread tid=%d cpus %x -> %x (%s; translation thread %d on %x) result=%d errno=%d",
        int(gettid()),now,want,why,translator_tid.load(std::memory_order_relaxed),avoid,r,err);
    placed=want;
}
void loop(){
    pt_on_thread=true;pthread_setname_np(pthread_self(),"dm-present");
    int pr=setpriority(PRIO_PROCESS,0,-8);if(pr)pr=setpriority(PRIO_PROCESS,0,-4);
    __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","NVN present thread started tid=%d nice=%d (setpriority %d) inherited cpus=%x",int(gettid()),getpriority(PRIO_PROCESS,0),pr,cpus_of(0));
    place();
    for(unsigned n=1;;n++){Job j;uint64_t tk;if(!q.take(j,tk))return;
        const int64_t t0=dmpt::now_ns();int r;{std::lock_guard<std::mutex> rl(render_mutex);
            if(j.nrp==1){q.mark_submitted();r=nrp_direct_present(j.idx,j.gen);}   // [DOS2] NR-11: nothing to submit, the engine's batch signals the present
            else r=present_body(j.src,j.fmt,j.w,j.h,j.has_crop?j.crop:nullptr,j.nrp==2?int(j.idx):-1,j.gen);
            if(j.nrp){std::lock_guard<std::mutex> l(nrp::mu);nrp::taken=false;}}
        q.finish(tk,r,uint64_t(dmpt::now_ns()-t0));
        if(nrp::on()){std::lock_guard<std::mutex> rl(render_mutex);nrp_park_next();}   // [DOS2] NR-11: after finish, so drains and the hand-off do not wait for it
        if(r){static int told=0;if(told++<4)__android_log_print(ANDROID_LOG_ERROR,"dm-vulkan","NVN present thread: present %llu failed: VkResult %d",(unsigned long long)tk,r);}
        if(n%128==0)place();}
}
}
static void pt_mark_submitted(void){pt::q.mark_submitted();}
static void pt_stamp_present(void){pt::q.stamp(dmpt::now_ns());}
extern "C" void pc_note(const char *id,int applied,const char *fmt,...);   // [pc]
extern "C" void dm_present_thread_set(int mode){pt_cfg.store(mode>0 && mode<=2?mode:0);if(mode>0)__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","NVN present thread mode=%d (DM_GFX_PRESENT_THREAD: 1 own thread, 2 same protocol inline)",pt_cfg.load());
    pc_note("present-thread",pt_cfg.load()==1,"%s",pt_cfg.load()==1?"DM_GFX_PRESENT_THREAD=1: fence / acquire / blit / queue present on dm-present; PERF-D07":pt_cfg.load()==2?"DM_GFX_PRESENT_THREAD=2: the protocol inline, no thread":"DM_GFX_PRESENT_THREAD=0: presents inline");   // [pc]
}
// Returns 0, or the VkResult of an earlier failed present on the thread (the engine stops with it, as it did for an inline failure).
extern "C" int dm_present_async(VkImage source,VkFormat format,uint32_t width,uint32_t height,const int32_t crop[4],int32_t){
    if(pt_cfg.load(std::memory_order_relaxed)!=1){std::lock_guard<std::mutex> render_lock(render_mutex);pin_update();++pt::inline_jobs;pt::last_ticket=0;return present_body(source,format,width,height,crop);}
    pin_update();   // the translation thread (the caller) keeps its pin, as present() pinned it
    {const int t=int(gettid());if(pt::translator_tid.load(std::memory_order_relaxed)!=t)pt::translator_tid.store(t,std::memory_order_relaxed);}
    pt::Job j{source,format,width,height,{0,0,0,0},crop!=nullptr};if(crop)memcpy(j.crop,crop,sizeof j.crop);
    uint64_t tk=0;XTRACE_BEGIN("dm-present-handoff");const int e=pt::q.push(j,[]{std::thread(pt::loop).detach();},&tk);XTRACE_END();
    pt::last_ticket=e?0:tk;return e;
}
// [DOS2] NR-11 DM_NR_PRESENT (engine/xbg_nr_present.inc). query: would an image of this format / size be handed out (no side effects; =2).
extern "C" int dm_present_nrp_query(VkFormat fmt,uint32_t w,uint32_t h){
    if(!nrp::mode)return NRP_P_OFF;if(rcas::enabled())return NRP_P_SHARPEN;std::lock_guard<std::mutex> l(nrp::mu);return nrp::check(fmt,w,h,false);}
static void nrp_fill(dm_nrp_img *o,uint32_t index,VkSemaphore sem,uint64_t g){   // under nrp::mu
    o->index=index;o->image=nrp::snap.images[index];o->view=nrp::snap.views[index];o->acquired=sem;o->finished=nrp::snap.finished[index];o->gen=g;o->format=nrp::snap.fmt;o->width=nrp::snap.w;o->height=nrp::snap.h;}
// take: an acquired swapchain image for this frame (0), or the reason none is handed out. With the present thread: only the image it parked,
// and only while it has no job left (that job might need it). Inline: an acquire with timeout 0 on this thread (no image free: none).
extern "C" int dm_present_nrp_take(VkFormat fmt,uint32_t w,uint32_t h,dm_nrp_img *out){
    if(!nrp::on())return NRP_P_OFF;if(rcas::enabled())return NRP_P_SHARPEN;
    if(pt_cfg.load(std::memory_order_relaxed)==1){
        {std::lock_guard<std::mutex> ql(pt::q.mu);if(pt::q.done<pt::q.enq)return NRP_P_JOB_PENDING;}
        std::lock_guard<std::mutex> l(nrp::mu);if(int c=nrp::check(fmt,w,h,true))return c;if(nrp::taken)return NRP_P_NO_IMAGE;
        if(!nrp::park.have || nrp::park.gen!=nrp::snap.gen || nrp::park.index>=nrp::snap.images.size())return NRP_P_NO_IMAGE;
        if(nrp::park.sub)return NRP_P_REBUILD;   // suboptimal: leave it to the blit job, which rebuilds after presenting it
        nrp_fill(out,nrp::park.index,nrp::park.sem,nrp::park.gen);nrp::park=nrp::Park{};nrp::taken=true;++nrp::takes;return NRP_P_OK;}
    std::lock_guard<std::mutex> rl(render_mutex);
    if(!swapchain || !surface || window_changed())return NRP_P_NO_SWAPCHAIN;if(swap_dirty)return NRP_P_REBUILD;
    {std::lock_guard<std::mutex> l(nrp::mu);if(int c=nrp::check(fmt,w,h,true))return c;if(nrp::taken)return NRP_P_NO_IMAGE;}
    VkSemaphore sem=nrp::next_sem();if(!sem)return NRP_P_ERROR;uint32_t index=0;
    XTRACE_BEGIN("dm-nrp-acquire");const VkResult r=vkAcquireNextImageKHR(device,swapchain,0,sem,VK_NULL_HANDLE,&index);XTRACE_END();
    if(r==VK_TIMEOUT || r==VK_NOT_READY)return NRP_P_NO_IMAGE;if(r==VK_ERROR_OUT_OF_DATE_KHR){swap_dirty=true;return NRP_P_REBUILD;}if(r!=VK_SUCCESS && r!=VK_SUBOPTIMAL_KHR)return NRP_P_ERROR;
    if(r==VK_SUBOPTIMAL_KHR && surface_properties_changed())swap_dirty=true;   // this frame is still presented; the next present rebuilds
    std::lock_guard<std::mutex> l(nrp::mu);if(index>=nrp::snap.images.size())return NRP_P_ERROR;nrp_fill(out,index,sem,nrp::gen);nrp::taken=true;++nrp::takes;return NRP_P_OK;
}
// give: the frame's present with its taken image. how 1 = direct (the engine's batch signalled img->finished), 2 = the old blit of `source`
// into it. With the present thread: a job like dm_present_async (ticket included); else inline here.
extern "C" int dm_present_async_nrp(VkImage source,VkFormat format,uint32_t width,uint32_t height,const int32_t crop[4],int32_t interval,int how,const dm_nrp_img *img){
    if(pt_cfg.load(std::memory_order_relaxed)!=1){std::lock_guard<std::mutex> render_lock(render_mutex);pin_update();++pt::inline_jobs;pt::last_ticket=0;
        const int r=how==1?nrp_direct_present(img->index,img->gen):present_body(source,format,width,height,crop,int(img->index),img->gen);
        std::lock_guard<std::mutex> l(nrp::mu);nrp::taken=false;return r;}
    pin_update();
    {const int t=int(gettid());if(pt::translator_tid.load(std::memory_order_relaxed)!=t)pt::translator_tid.store(t,std::memory_order_relaxed);}
    pt::Job j{source,format,width,height,{0,0,0,0},crop!=nullptr,how,img->index,img->gen};if(crop)memcpy(j.crop,crop,sizeof j.crop);(void)interval;
    uint64_t tk=0;XTRACE_BEGIN("dm-present-handoff");const int e=pt::q.push(j,[]{std::thread(pt::loop).detach();},&tk);XTRACE_END();
    pt::last_ticket=e?0:tk;return e;
}
// Totals since start: images parked by the present thread, parks that failed, images taken by the engine, direct presents, blits into a taken
// image, frames lost to a swapchain change between take and present.
extern "C" void dm_present_nrp_stats(uint64_t out[6]){out[0]=nrp::parks.load();out[1]=nrp::park_fails.load();out[2]=nrp::takes.load();out[3]=nrp::direct.load();out[4]=nrp::blits.load();out[5]=nrp::lost.load();}
// Nanoseconds waited until every handed present has its blit submitted / has finished (0 = nothing pending).
extern "C" uint64_t dm_present_wait_submitted(void){return pt::q.wait_submitted();}
extern "C" uint64_t dm_present_drain(void){return pt::q.drain();}
extern "C" int dm_present_last_error(void){return pt::q.err.load();}
extern "C" void dm_present_queue_lock(void){if(pt_cfg.load(std::memory_order_relaxed))pt_queue_mutex.lock();}
extern "C" void dm_present_queue_unlock(void){if(pt_cfg.load(std::memory_order_relaxed))pt_queue_mutex.unlock();}
// Totals since start: presents run by the thread (or inline with =2), the thread's time in them, the engine's waits on a full hand-off ring
// (ns), and on a not yet submitted blit (ns, dm_present_wait_submitted).
extern "C" void dm_present_thread_stats(uint64_t out[4]){out[0]=pt::q.jobs.load()+pt::inline_jobs.load();out[1]=pt::q.busy_ns.load();out[2]=pt::q.full_ns.load();out[3]=pt::q.wait_ns.load();}
// For nvn_vk.c (mtl_present / mtl_present_wait / mtl_presented_time): the ticket of the present this thread just handed over (0 = presented
// inline), a wait until that present's blit is on the queue (the contract of mtl_present_wait), and when its vkQueuePresentKHR returned
// (CLOCK_MONOTONIC seconds; 0 = not yet).
extern "C" uint64_t dm_present_last_ticket(void){return pt_cfg.load(std::memory_order_relaxed)==1?pt::last_ticket:0;}
extern "C" uint64_t dm_present_wait_ticket(uint64_t tk){return tk && pt_cfg.load(std::memory_order_relaxed)==1?pt::q.wait_ticket(tk):0;}
extern "C" double dm_present_time(uint64_t tk){const int64_t ns=pt::q.presented_ns(tk);return ns?double(ns)*1e-9:0;}
extern "C" void dm_android_vk_set_window(ANativeWindow *window){if(window)ANativeWindow_acquire(window);{std::lock_guard<std::mutex> l(window_mutex);if(desired)ANativeWindow_release(desired);desired=window;++generation;}window_cv.notify_all();}
extern "C" int dm_android_vk_has_window(){return has_window(nullptr);}
// [DOOM] BUGS_AND_FIXES 2.56 (DOOM issue #33, KB DRV-07; [DOS2] from D3 deab687): the in-process fallback to the system driver (jni_android.c
// host_thread). A failed initialization destroys what it made (fail -> cleanup_initialization), so it may run again with another driver, as
// long as the engine was not initialized yet (dm_vk_initialize below keeps state of its own): dm_android_vk_retry_safe. DM_VK_FAKE_INIT_FAIL
// (test switch, dm/env): 1 = the initialization fails right after the swapchain was made, only while a custom driver is active (the same
// VkResult as PanVK on the Mali-G57 of DOOM issue #33), so the fallback can be checked on a phone where every driver works; 2 = it fails with
// any driver (the system driver too: the start error must be shown, no loop).
extern "C" int dm_vk_driver_custom(void);
static bool engine_touched=false;
extern "C" int dm_android_vk_retry_safe(void){return !engine_touched && !ready;}
static bool fake_init_fail(){const char *e=getenv("DM_VK_FAKE_INIT_FAIL");if(!e||!*e)return false;const int v=atoi(e);return v>=2 || (v==1 && dm_vk_driver_custom());}
extern "C" __attribute__((weak)) void xbg_safe_mode_boot(uint32_t vendor,const char *name);   // [safe-mode] xbg_game.cpp (xbg_safe_mode.inc)
extern "C" int dm_android_vk_initialize(const char *path,char *error,size_t bytes){
    if(path){std::string dir=path;size_t cut=dir.find_last_of('/');if(FILE *m=fopen(((cut==std::string::npos?dir:dir.substr(0,cut))+"/gfx-present-native").c_str(),"rb")){present_native=fgetc(m)!='0';fclose(m);}
        if(FILE *m=fopen(((cut==std::string::npos?dir:dir.substr(0,cut))+"/gfx-present-timing").c_str(),"rb")){present_timing=true;fclose(m);}}
    std::lock_guard<std::mutex> render_lock(render_mutex);
    auto fail=[&](const char *what,VkResult r)->int{if(error&&bytes)snprintf(error,bytes,"%s: VkResult %d",what,int(r));if(!ready)cleanup_initialization();return int(r?r:VK_ERROR_INITIALIZATION_FAILED);};
    if(ready||!path||!*path)return fail("Initialization requires an external shader directory and an uninitialized renderer",VK_ERROR_INITIALIZATION_FAILED);
    // 每次初始化从缺省的 120 Hz 重新读标记。 | Each initialization starts again from the 120 Hz default before the marker.
    frame_rate_vote=120;
    {const char *e=getenv("DM_NR_PRESENT");nrp::mode=e && *e?nrp_clamp_mode(atol(e)):0;   // [DOS2] NR-11 (the engine reads the same switch)
     if(nrp::mode)__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] DM_NR_PRESENT=%d: %s",nrp::mode,nrp::on()?"swapchain images are colour attachments; the engine may render the last passes into them":"count only (the presenter answers questions, changes nothing)");}
    dm_vk_format_list=0;dm_vk_custom_border=0;dm_vk_descriptor_indexing=0;dm_vk_cond_render=0;dm_vk_compr_ctl=0;dm_vk_ifp2=nullptr;   // [DOOM] 2.56: a repeated initialization (driver fallback) starts over
    {std::string dir=path;size_t cut=dir.find_last_of('/');if(FILE *m=fopen(((cut==std::string::npos?dir:dir.substr(0,cut))+"/gfx-frame-rate").c_str(),"rb")){float v=0;frame_rate_vote=fscanf(m,"%f",&v)==1 && v>=0 && v<=240?v:0;fclose(m);}
#ifdef DM_GAME_DOS2
     // [DOS2] no marker: the vote follows DM_DOS2_FPS (nvn_pace.h nvn_fps_vote_hz: 90 votes 90, everything else the 120 default)
     else frame_rate_vote=dm_dos2_fps_vote(frame_rate_vote);
#endif
    }

    VkApplicationInfo ai{VK_STRUCTURE_TYPE_APPLICATION_INFO};ai.pApplicationName="dm-android";ai.apiVersion=VK_API_VERSION_1_1;
#ifdef DM_GAME_ETERNAL
    ai.apiVersion=VK_API_VERSION_1_2;   // [ETERNAL] descriptor indexing as core 1.2 where the device lacks the EXT name (LDPlayer)
#endif

    const char *ext[]={VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_ANDROID_SURFACE_EXTENSION_NAME,VK_EXT_DEBUG_UTILS_EXTENSION_NAME};VkInstanceCreateInfo ic{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};ic.pApplicationInfo=&ai;ic.enabledExtensionCount=2;ic.ppEnabledExtensionNames=ext;
    // DM_VK_VALIDATION=1 (diagnostics): the Khronos validation layer packaged in the APK (tools/build_apk.ps1 -Validation; a
    // debuggable app's own layers), with synchronization validation and best practices; messages go to logcat "dm-vvl", each
    // message id at most 20 times. =2: core validation only (faster).
    const char *vvl_env=getenv("DM_VK_VALIDATION");int vvl=vvl_env?atoi(vvl_env):0;const char *layer="VK_LAYER_KHRONOS_validation";
    VkValidationFeatureEnableEXT vf_on[]={VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT,VK_VALIDATION_FEATURE_ENABLE_BEST_PRACTICES_EXT};
    VkValidationFeaturesEXT vf{VK_STRUCTURE_TYPE_VALIDATION_FEATURES_EXT};vf.enabledValidationFeatureCount=2;vf.pEnabledValidationFeatures=vf_on;
    if(vvl){auto enum_layers=(PFN_vkEnumerateInstanceLayerProperties)vkGetInstanceProcAddr(nullptr,"vkEnumerateInstanceLayerProperties");
        uint32_t ln=0;bool have=false;if(enum_layers){enum_layers(&ln,nullptr);std::vector<VkLayerProperties> lp(ln);enum_layers(&ln,lp.data());for(auto &l:lp)if(!strcmp(l.layerName,layer))have=true;}
        __android_log_print(ANDROID_LOG_INFO,"dm-vvl","validation layer %s (%u layers)",have?"found":"NOT FOUND",ln);
        if(have){ic.enabledLayerCount=1;ic.ppEnabledLayerNames=&layer;ic.enabledExtensionCount=3;if(vvl==1)ic.pNext=&vf;}else vvl=0;}
    VkResult r=vkCreateInstance(&ic,nullptr,&instance);if(r)return fail("vkCreateInstance",r);
    if(vvl){static std::mutex vm;static std::unordered_map<int32_t,unsigned> seen;
        VkDebugUtilsMessengerCreateInfoEXT mi{VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT};
        mi.messageSeverity=VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT;
        mi.messageType=VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT;
        mi.pfnUserCallback=[](VkDebugUtilsMessageSeverityFlagBitsEXT sev,VkDebugUtilsMessageTypeFlagsEXT,const VkDebugUtilsMessengerCallbackDataEXT *d,void*)->VkBool32{
            unsigned c;{std::lock_guard<std::mutex> g(vm);c=++seen[d->messageIdNumber];}
            if(c<=20 || (c&(c-1))==0)__android_log_print(sev>=VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT?ANDROID_LOG_ERROR:ANDROID_LOG_WARN,"dm-vvl","#%u %s %s",c,d->pMessageIdName?d->pMessageIdName:"?",d->pMessage?d->pMessage:"");
            return VK_FALSE;};
        auto mk=(PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance,"vkCreateDebugUtilsMessengerEXT");VkDebugUtilsMessengerEXT m;
        if(mk)mk(instance,&mi,nullptr,&m);}
    uint32_t n=0;vkEnumeratePhysicalDevices(instance,&n,nullptr);std::vector<VkPhysicalDevice> devices(n);vkEnumeratePhysicalDevices(instance,&n,devices.data());if(!n)return fail("No Vulkan device",VK_ERROR_INITIALIZATION_FAILED);
    physical=devices[0];
    // [DOS2][safe-mode] docs/dos2/nr/SAFE-MODE.md (xbg_game.cpp xbg_safe_mode.inc): this boot's GPU safe-mode step on Mali / PowerVR (real or
    // DM_GFX_SIM_GPU), decided from the physical device before anything reads the switches it may set: the device extensions below, DM_NR_ROTATE
    // (read right after, it was read at the top before), the engine's initialize, the NB / NR installs in dm_main. Weak: once per process.
    {VkPhysicalDeviceProperties sp{};vkGetPhysicalDeviceProperties(physical,&sp);if(xbg_safe_mode_boot)xbg_safe_mode_boot(sp.vendorID,sp.deviceName);}
    {const char *e=getenv("DM_NR_ROTATE");nrr::mode=e && *e?nrr_clamp_mode(atol(e)):nrr_default_mode();nrr::failed=false;nrr::last_transform=0;   // [DOS2] NR-20
     if(nrr::mode){char man[PROP_VALUE_MAX]={0},model[PROP_VALUE_MAX]={0},board[PROP_VALUE_MAX]={0};__system_property_get("ro.soc.manufacturer",man);__system_property_get("ro.soc.model",model);__system_property_get("ro.board.platform",board);
      __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] DM_NR_ROTATE=%d: %s; SoC %s %s (board %s): whether this device's compositor turns the window for free (DEVICE) or on the GPU (CLIENT): adb shell dumpsys SurfaceFlinger",nrr::mode,
        nrr::on()?"pre-rotated swapchain, the frame drawn turned (no blit); DM_NR_PRESENT then idles":"count + probe only (identity swapchain, the blit as before)",man[0]?man:"?",model[0]?model:"?",board[0]?board:"?");}}
    // 启动期间也可能旋转/切后台；等待新窗口，不把瞬时撤回误报为启动失败。
    // Rotation/backgrounding can race startup too; wait for a live window instead of failing boot.
    for(;;){wait_window();r=VkResult(create_surface());if(r==VK_NOT_READY)continue;if(r==VK_ERROR_SURFACE_LOST_KHR){uint64_t bad=active_generation;destroy_swap();wait_window_change(bad);continue;}if(r)return fail("Android surface",r);break;}
    vkGetPhysicalDeviceQueueFamilyProperties(physical,&n,nullptr);std::vector<VkQueueFamilyProperties> q(n);vkGetPhysicalDeviceQueueFamilyProperties(physical,&n,q.data());bool found=false;
    for(uint32_t i=0;i<n;i++){VkBool32 p=0;vkGetPhysicalDeviceSurfaceSupportKHR(physical,i,surface,&p);if(p&&(q[i].queueFlags&(VK_QUEUE_GRAPHICS_BIT|VK_QUEUE_COMPUTE_BIT))==(VK_QUEUE_GRAPHICS_BIT|VK_QUEUE_COMPUTE_BIT)){family=i;found=true;break;}}if(!found)return fail("No graphics/compute/present family",VK_ERROR_FEATURE_NOT_PRESENT);
    VkPhysicalDeviceShaderDrawParametersFeatures draw{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_DRAW_PARAMETERS_FEATURES};VkPhysicalDeviceFeatures2 features{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};features.pNext=&draw;vkGetPhysicalDeviceFeatures2(physical,&features);
    vkEnumerateDeviceExtensionProperties(physical,nullptr,&n,nullptr);std::vector<VkExtensionProperties> available(n);vkEnumerateDeviceExtensionProperties(physical,nullptr,&n,available.data());bool mirror=false,minmax=false,indirect_count=false,ahb=false,foreign=false,format_list=false;for(auto e:available){if(std::string(e.extensionName)==VK_KHR_IMAGE_FORMAT_LIST_EXTENSION_NAME)format_list=true;if(std::string(e.extensionName)==VK_ANDROID_EXTERNAL_MEMORY_ANDROID_HARDWARE_BUFFER_EXTENSION_NAME)ahb=true;if(std::string(e.extensionName)==VK_EXT_QUEUE_FAMILY_FOREIGN_EXTENSION_NAME)foreign=true;if(std::string(e.extensionName)==VK_KHR_DRAW_INDIRECT_COUNT_EXTENSION_NAME)indirect_count=true;if(std::string(e.extensionName)==VK_KHR_SAMPLER_MIRROR_CLAMP_TO_EDGE_EXTENSION_NAME)mirror=true;if(std::string(e.extensionName)==VK_EXT_SAMPLER_FILTER_MINMAX_EXTENSION_NAME)minmax=true;}
    {std::string all;for(auto &e:available){all+=e.extensionName;all+=' ';}   // 诊断：设备扩展全表（每次启动一行）| Diagnostics: the full device extension list (one line per launch)
     for(size_t at=0;at<all.size();at+=900)__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Device extensions [%zu]: %s",at/900,all.substr(at,900).c_str());
     VkPhysicalDeviceExternalMemoryHostPropertiesEXT host{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT};VkPhysicalDeviceProperties2 pr{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};pr.pNext=&host;vkGetPhysicalDeviceProperties2(physical,&pr);
     __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Device %s api=%u.%u.%u driver=%#x minImportedHostPointerAlignment=%llu",pr.properties.deviceName,VK_VERSION_MAJOR(pr.properties.apiVersion),VK_VERSION_MINOR(pr.properties.apiVersion),VK_VERSION_PATCH(pr.properties.apiVersion),pr.properties.driverVersion,(unsigned long long)host.minImportedHostPointerAlignment);
#if defined(DM_GAME_XC2) || defined(DM_GAME_D3)
     {   // [XC2] one line per boot that answers the driver questions of docs/ADRENO750.md (driver, XFB, clip/cull, VS stores, SSBO range)
      VkPhysicalDeviceDriverProperties dp{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};VkPhysicalDeviceSubgroupProperties sg{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_PROPERTIES};sg.pNext=&dp;
      VkPhysicalDeviceProperties2 p2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};p2.pNext=&sg;vkGetPhysicalDeviceProperties2(physical,&p2);const VkPhysicalDeviceLimits &L=p2.properties.limits;
      VkPhysicalDeviceTransformFeedbackFeaturesEXT xf{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_TRANSFORM_FEEDBACK_FEATURES_EXT};VkPhysicalDeviceFeatures2 f2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};f2.pNext=&xf;vkGetPhysicalDeviceFeatures2(physical,&f2);
      char nb[128]={0};__system_property_get("ro.dalvik.vm.native.bridge",nb);
      __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Device caps: driverID=%d name=\"%s\" info=\"%s\" id=%#x subgroup=%u stages=%#x ops=%#x xfb=%u streams=%u vsStores=%u clipCull=%u ssboRange=%u uboRange=%u nativeBridge=%s",
        int(dp.driverID),dp.driverName,dp.driverInfo,p2.properties.deviceID,sg.subgroupSize,unsigned(sg.supportedStages),unsigned(sg.supportedOperations),unsigned(xf.transformFeedback),unsigned(xf.geometryStreams),
        unsigned(f2.features.vertexPipelineStoresAndAtomics),L.maxCombinedClipAndCullDistances,L.maxStorageBufferRange,L.maxUniformBufferRange,nb[0]?nb:"none");}
#endif
    }
    std::vector<const char*> dext={VK_KHR_SWAPCHAIN_EXTENSION_NAME};if(mirror)dext.push_back(VK_KHR_SAMPLER_MIRROR_CLAMP_TO_EDGE_EXTENSION_NAME);
    // NVN min/max reduction samplers (depth pyramids): extension only (the instance is Vulkan 1.1); without it reductions sample as average.
    if(minmax)dext.push_back(VK_EXT_SAMPLER_FILTER_MINMAX_EXTENSION_NAME);
    // [DOOM] GPU-driven culling writes DrawElementsIndirect arguments and counts on the GPU; replayed as vkCmdDraw*IndirectCount.
    if(indirect_count)dext.push_back(VK_KHR_DRAW_INDIRECT_COUNT_EXTENSION_NAME);
    // [DOOM] format lists keep UBWC compression on images that need a second view format (xbg_game.cpp upgrade_mutable)
    if(format_list){dext.push_back(VK_KHR_IMAGE_FORMAT_LIST_EXTENSION_NAME);dm_vk_format_list=1;}
    // [DOOM] zero-copy guest memory imports AHardwareBuffer pages as buffer memory (xbg_game.cpp zc)
    if(ahb && foreign){dext.push_back(VK_ANDROID_EXTERNAL_MEMORY_ANDROID_HARDWARE_BUFFER_EXTENSION_NAME);dext.push_back(VK_EXT_QUEUE_FAMILY_FOREIGN_EXTENSION_NAME);}
    // Diagnostic (marker gfx-pipe-stats): the driver's per-pipeline statistics (VK_KHR_pipeline_executable_properties).
    VkPhysicalDevicePipelineExecutablePropertiesFeaturesKHR pef{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PIPELINE_EXECUTABLE_PROPERTIES_FEATURES_KHR};
    if(FILE *ps=[&]{std::string dir=path;size_t cut=dir.find_last_of('/');return fopen(((cut==std::string::npos?dir:dir.substr(0,cut))+"/gfx-pipe-stats").c_str(),"rb");}()){fclose(ps);dext.push_back(VK_KHR_PIPELINE_EXECUTABLE_PROPERTIES_EXTENSION_NAME);pef.pipelineExecutableInfo=VK_TRUE;pef.pNext=draw.pNext;draw.pNext=&pef;}
#ifdef DM_GAME_ETERNAL
    // [ETERNAL] id Tech 7 shaders index the whole texture / sampler pools: the engine mirrors them in update-after-bind descriptor
    // arrays (xbg_game.cpp namespace bindless). Only the features it uses are enabled; it logs and skips such shaders without them.
    VkPhysicalDeviceDescriptorIndexingFeaturesEXT di_on{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DESCRIPTOR_INDEXING_FEATURES_EXT};
    {bool di_ext=false;for(auto &e:available)if(std::string(e.extensionName)==VK_EXT_DESCRIPTOR_INDEXING_EXTENSION_NAME)di_ext=true;
     // core in Vulkan 1.2: a device can report 1.2+ without listing the EXT (LDPlayer); the same feature struct then needs no extension
     uint32_t dev_api=0;{VkPhysicalDeviceProperties pp;vkGetPhysicalDeviceProperties(physical,&pp);dev_api=pp.apiVersion;}
     const bool di_core=dev_api>=VK_API_VERSION_1_2;
     VkPhysicalDeviceDescriptorIndexingFeaturesEXT di{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DESCRIPTOR_INDEXING_FEATURES_EXT};
     if(di_ext || di_core){VkPhysicalDeviceFeatures2 f2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};f2.pNext=&di;vkGetPhysicalDeviceFeatures2(physical,&f2);}
     const bool ok=(di_ext || di_core) && di.descriptorBindingPartiallyBound && di.descriptorBindingSampledImageUpdateAfterBind;
     if(ok){if(di_ext)dext.push_back(VK_EXT_DESCRIPTOR_INDEXING_EXTENSION_NAME);di_on.descriptorBindingPartiallyBound=VK_TRUE;di_on.descriptorBindingSampledImageUpdateAfterBind=VK_TRUE;di_on.pNext=draw.pNext;draw.pNext=&di_on;dm_vk_descriptor_indexing=1;}
     __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Descriptor indexing ext=%d core=%d partiallyBound=%u sampledImageUpdateAfterBind=%u runtimeArray=%u nonUniformSampled=%u dynamicIndexing=%u -> %s",
        int(di_ext),int(di_core),unsigned(di.descriptorBindingPartiallyBound),unsigned(di.descriptorBindingSampledImageUpdateAfterBind),unsigned(di.runtimeDescriptorArray),unsigned(di.shaderSampledImageArrayNonUniformIndexing),
        unsigned(features.features.shaderSampledImageArrayDynamicIndexing),ok?"enabled":"off (bindless shaders are skipped)");}
#endif
#if defined(DM_GAME_XC2) || defined(DM_GAME_D3)
    // [XC2] NVN samplers with arbitrary border colours (Adreno 750: Qualcomm / Turnip list it); without it the engine uses the nearest canonical colour
    VkPhysicalDeviceCustomBorderColorFeaturesEXT cbc{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_CUSTOM_BORDER_COLOR_FEATURES_EXT};
    {bool has=false;for(auto &e:available)if(std::string(e.extensionName)==VK_EXT_CUSTOM_BORDER_COLOR_EXTENSION_NAME)has=true;
     if(has && !getenv("DM_GFX_NO_CUSTOM_BORDER")){VkPhysicalDeviceFeatures2 f2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};f2.pNext=&cbc;vkGetPhysicalDeviceFeatures2(physical,&f2);
      if(cbc.customBorderColors && cbc.customBorderColorWithoutFormat){dext.push_back(VK_EXT_CUSTOM_BORDER_COLOR_EXTENSION_NAME);cbc.pNext=draw.pNext;draw.pNext=&cbc;dm_vk_custom_border=1;}}
     __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Custom border colour ext=%d colors=%u withoutFormat=%u -> %s",int(has),unsigned(cbc.customBorderColors),unsigned(cbc.customBorderColorWithoutFormat),dm_vk_custom_border?"enabled":"off (nearest canonical colour)");}
#endif
    // [DOS2] DM_GFX_COND_RENDER=1: VK_EXT_conditional_rendering for NVN SetRenderEnableConditional (xbg_game.cpp condr; ETR PERF-E05). Off unless asked for.
    VkPhysicalDeviceConditionalRenderingFeaturesEXT crf{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_CONDITIONAL_RENDERING_FEATURES_EXT};
    // NR-03 DM_NR_OCC 1 / 3 (xbg_nr_occ.inc, GPU path) asks for it too; unset / 0 / 2 = as before.
    const char *nro=getenv("DM_NR_OCC");const bool nro_ext=nro && (atoi(nro)==1 || atoi(nro)==3);
    if(const char *ce=getenv("DM_GFX_COND_RENDER");(ce && atoi(ce)==1) || nro_ext){
        bool has=false;for(auto &x:available)if(!strcmp(x.extensionName,VK_EXT_CONDITIONAL_RENDERING_EXTENSION_NAME))has=true;
        VkPhysicalDeviceConditionalRenderingFeaturesEXT have{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_CONDITIONAL_RENDERING_FEATURES_EXT};
        if(has){VkPhysicalDeviceFeatures2 f2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};f2.pNext=&have;vkGetPhysicalDeviceFeatures2(physical,&f2);}
        if(has && have.conditionalRendering){dext.push_back(VK_EXT_CONDITIONAL_RENDERING_EXTENSION_NAME);crf.conditionalRendering=VK_TRUE;crf.pNext=draw.pNext;draw.pNext=&crf;dm_vk_cond_render=1;}
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","VK_EXT_conditional_rendering: listed=%d feature=%u -> %s",int(has),unsigned(have.conditionalRendering),dm_vk_cond_render?"enabled":"off");}
    // [DOS2] NR-UBWC DM_NR_UBWC 1 / 2 (docs/dos2/nr/NR-UBWC.md): VK_EXT_image_compression_control only to ASK the driver whether an image is
    // compressed (vkGetImageSubresourceLayout2EXT + VkImageCompressionPropertiesEXT; the engine passes no VkImageCompressionControlEXT, so no
    // image is created differently by enabling it). Unset / 0: not enabled, as before.
    VkPhysicalDeviceImageCompressionControlFeaturesEXT icc{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_COMPRESSION_CONTROL_FEATURES_EXT};
    VkPhysicalDeviceImageCompressionControlSwapchainFeaturesEXT iccs{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_COMPRESSION_CONTROL_SWAPCHAIN_FEATURES_EXT};
    if(const char *ue=getenv("DM_NR_UBWC");ue && *ue && atoi(ue)!=0){
        bool has=false,hass=false;for(auto &x:available){if(!strcmp(x.extensionName,VK_EXT_IMAGE_COMPRESSION_CONTROL_EXTENSION_NAME))has=true;if(!strcmp(x.extensionName,VK_EXT_IMAGE_COMPRESSION_CONTROL_SWAPCHAIN_EXTENSION_NAME))hass=true;}
        VkPhysicalDeviceImageCompressionControlFeaturesEXT h{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_COMPRESSION_CONTROL_FEATURES_EXT};VkPhysicalDeviceImageCompressionControlSwapchainFeaturesEXT hs{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_COMPRESSION_CONTROL_SWAPCHAIN_FEATURES_EXT};
        if(has){VkPhysicalDeviceFeatures2 f2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};f2.pNext=&h;if(hass)h.pNext=&hs;vkGetPhysicalDeviceFeatures2(physical,&f2);}
        if(has && h.imageCompressionControl){dext.push_back(VK_EXT_IMAGE_COMPRESSION_CONTROL_EXTENSION_NAME);icc.imageCompressionControl=VK_TRUE;icc.pNext=draw.pNext;draw.pNext=&icc;dm_vk_compr_ctl=1;
            dm_vk_ifp2=reinterpret_cast<PFN_vkGetPhysicalDeviceImageFormatProperties2>(vkGetInstanceProcAddr(instance,"vkGetPhysicalDeviceImageFormatProperties2"));   // what a create info would get (DM_NR_UBWC=1 decisions)
            if(hass && hs.imageCompressionControlSwapchain){dext.push_back(VK_EXT_IMAGE_COMPRESSION_CONTROL_SWAPCHAIN_EXTENSION_NAME);iccs.imageCompressionControlSwapchain=VK_TRUE;iccs.pNext=draw.pNext;draw.pNext=&iccs;dm_vk_compr_ctl|=2;}}
        __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] ubwc DM_NR_UBWC=%s: VK_EXT_image_compression_control listed=%d feature=%u, _swapchain listed=%d feature=%u -> %s",ue,int(has),unsigned(h.imageCompressionControl),int(hass),unsigned(hs.imageCompressionControlSwapchain),
            dm_vk_compr_ctl?(dm_vk_compr_ctl&2?"enabled (images + swapchain are asked)":"enabled (images are asked; swapchain not)"):"not available: the engine cannot ask this driver (counts stay empty)");}
    float priority=1;VkDeviceQueueCreateInfo qc{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};qc.queueFamilyIndex=family;qc.queueCount=1;qc.pQueuePriorities=&priority;VkDeviceCreateInfo dc{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};dc.pNext=&draw;dc.pEnabledFeatures=&features.features;dc.queueCreateInfoCount=1;dc.pQueueCreateInfos=&qc;dc.enabledExtensionCount=uint32_t(dext.size());dc.ppEnabledExtensionNames=dext.data();__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[init] vkCreateDevice: %u extensions (issue #3: init steps on disk)",unsigned(dext.size()));if((r=vkCreateDevice(physical,&dc,nullptr,&device)))return fail("vkCreateDevice",r);vkGetDeviceQueue(device,family,0,&queue);__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[init] device created; surface and swapchain next");
    for(;;){
        wait_window();
        if(!surface||window_changed()){
            r=VkResult(create_surface());if(r==VK_NOT_READY)continue;
            if(r==VK_ERROR_SURFACE_LOST_KHR){uint64_t bad=active_generation;destroy_swap();wait_window_change(bad);continue;}
            if(r)return fail("Android surface",r);
        }
        r=VkResult(create_swap());
        if(r==VK_NOT_READY||r==VK_ERROR_OUT_OF_DATE_KHR){wait_resize();continue;}
        if(r==VK_ERROR_SURFACE_LOST_KHR){uint64_t bad=active_generation;destroy_swap();wait_window_change(bad);continue;}
        if(r)return fail("Swapchain",r);__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[init] swapchain created");break;
    }
    if(fake_init_fail()){__android_log_print(ANDROID_LOG_WARN,"dm-vulkan","DM_VK_FAKE_INIT_FAIL=%s: failing the initialization after the swapchain (test of the driver fallback)",getenv("DM_VK_FAKE_INIT_FAIL"));
        return fail("Swapchain (faked by DM_VK_FAKE_INIT_FAIL)",VK_ERROR_INVALID_EXTERNAL_HANDLE);}
    VkCommandPoolCreateInfo cp{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};cp.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;cp.queueFamilyIndex=family;if((r=vkCreateCommandPool(device,&cp,nullptr,&command_pool)))return fail("Present command pool",r);
    VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=command_pool;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ca.commandBufferCount=1;if((r=vkAllocateCommandBuffers(device,&ca,&command)))return fail("Present command",r);
    VkSemaphoreCreateInfo sc{VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};if((r=vkCreateSemaphore(device,&sc,nullptr,&acquired)))return fail("Acquire semaphore",r);VkFenceCreateInfo fc{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};if((r=vkCreateFence(device,&fc,nullptr,&fence)))return fail("Present fence",r);
    {std::string dir=path;size_t cut=dir.find_last_of('/');FILE *m=fopen(((cut==std::string::npos?dir:dir.substr(0,cut))+"/gfx-present-overlap").c_str(),"rb");overlap=true;if(m){overlap=fgetc(m)!='0';fclose(m);}
     auto open_marker=[&](const char *name){return fopen(((cut==std::string::npos?dir:dir.substr(0,cut))+name).c_str(),"rb");};
     pin_mask=fastest_cores();pin_ab=0;pin_state=-1;pin_have_original=false;pin_presents=pin_drifts=0;pin_markers=false;
     if(FILE *p=open_marker("/gfx-pin-cpu")){if(fscanf(p,"%x",&pin_mask)!=1)pin_mask=0;fclose(p);pin_markers=true;}
     if(FILE *n=open_marker("/gfx-no-pin")){pin_mask=0;fclose(n);pin_markers=true;}
     if(FILE *t=open_marker("/gfx-ab-target")){char target[16]={0};if(fscanf(t,"%15s",target)==1 && !strcmp(target,"pin"))if(FILE *a=open_marker("/gfx-ab-toggle")){if(fscanf(a,"%d",&pin_ab)!=1)pin_ab=0;fclose(a);pin_markers=true;}fclose(t);}
     if(!pin_markers)pin_mask=0;dm_cpu_place_markers(pin_markers);   // [cpu-place] no marker: the module pins
     __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","NVN pin mask=%x ab=%d (markers gfx-no-pin, gfx-pin-cpu, gfx-ab-target=pin%s)",pin_mask,pin_ab,pin_markers?"":"; none set: the [cpu] plan places this thread");
     if(FILE *b=open_marker("/gfx-membench")){fclose(b);membench();}}
    if(overlap){if((r=vkCreateCommandPool(device,&cp,nullptr,&overlap_pool)))return fail("Present command pool",r);ca.commandPool=overlap_pool;if((r=vkAllocateCommandBuffers(device,&ca,&overlap_command)))return fail("Present command",r);
        if((r=vkCreateSemaphore(device,&sc,nullptr,&overlap_acquired)))return fail("Acquire semaphore",r);if((r=vkCreateFence(device,&fc,nullptr,&overlap_fence)))return fail("Present fence",r);}
    __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","Present overlap=%d (marker gfx-present-overlap)",int(overlap));
    shader_path=path;dm_vk_config config{};config.size=sizeof(config);config.game.size=sizeof(config.game);config.game.physical=physical;config.game.device=device;config.game.queue=queue;config.game.queue_family=family;config.game.enabled_core=features.features;config.game.enabled_shader_draw_parameters=draw.shaderDrawParameters;config.game.fence_timeout_ns=10000000000ull;config.game.shader_directory=shader_path.c_str();config.game.present=present;config.game.log=log_message;config.game.fatal=fatal;config.sampler_mirror_clamp_to_edge=mirror;config.sampler_filter_minmax=minmax;config.has_window=has_window;config.display_hz=0; // Query actual display refresh in frontend; do not guess 60 Hz.
    engine_touched=true;int status=dm_vk_initialize(&config,error,bytes);if(!status)ready=true;else cleanup_initialization();return status;
}
// [DOS2] NR-UBWC: one line per swapchain (re)creation - which swapchain images the driver reports compressed (UBWC on Adreno: gralloc's
// flag of the window buffer; AFBC on Mali). Only with DM_NR_UBWC != 0 and the _swapchain feature.
static void nrubwc_swapchain_report(VkDevice device,const std::vector<VkImage> &images,VkFormat fmt){
    auto q=reinterpret_cast<PFN_vkGetImageSubresourceLayout2EXT>(vkGetDeviceProcAddr(device,"vkGetImageSubresourceLayout2EXT"));
    if(!q)q=reinterpret_cast<PFN_vkGetImageSubresourceLayout2EXT>(vkGetDeviceProcAddr(device,"vkGetImageSubresourceLayout2KHR"));
    if(!q){__android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] ubwc swapchain: vkGetImageSubresourceLayout2 missing");return;}
    unsigned on=0;for(VkImage im:images){VkImageSubresource2KHR sub{VK_STRUCTURE_TYPE_IMAGE_SUBRESOURCE_2_EXT};sub.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0};
        VkImageCompressionPropertiesEXT cp{VK_STRUCTURE_TYPE_IMAGE_COMPRESSION_PROPERTIES_EXT};VkSubresourceLayout2KHR lay{VK_STRUCTURE_TYPE_SUBRESOURCE_LAYOUT_2_EXT};lay.pNext=&cp;
        q(device,im,&sub,&lay);if(cp.imageCompressionFlags!=VK_IMAGE_COMPRESSION_DISABLED_EXT)++on;}
    __android_log_print(ANDROID_LOG_INFO,"dm-vulkan","[nr] ubwc swapchain: %u of %zu images compressed (format %d)",on,images.size(),int(fmt));
}
