// [BL2] Widescreen (DM_BL2_WIDE): Borderlands 2 gets its NVN window size from two immediates next to nn::oe::GetOperationMode —
// docked 1920x1080, handheld 1280x720 — in main (v131072):
//   0x1297738  mov w20,w0 (GetOperationMode) / cmp w20,#1 / mov w9,#1280 / orr w10,wzr,#1920 / csel w9,w10,w9,eq / str w9,[x19,#0x18]
//              / str w9,[global width] / mov w8,#720 / mov w9,#1080 / csel w8,w9,w8,eq  (the window setup at boot)
//   0x1297888  the same block (the operation-mode change / window rebuild path)
// The width is replaced with 1080 (docked) or 720 (handheld) at the screen's aspect, heights unchanged: the frame is wider, nothing is
// cropped, the extra pixels are new area on both sides (Hor+ if the engine keeps the vertical FOV, which the screenshot check decides).
//   DM_BL2_WIDE=1        the screen's aspect (1080p docked: about 2352x1080 on a 20:9 phone)
//   DM_BL2_WIDE=<width>  explicit docked width (1921..4096, rounded to 16); handheld = 2/3 of it
//   unset / 0            the Switch's 1920x1080 / 1280x720
// Both sites are checked word for word against this build; another build changes nothing.
#ifdef DM_GAME_BL2
#include <sys/mman.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "hle.h"
#include "front.h"

uint64_t front_screen_px(void);   // front_android.c: the screen's landscape size, height << 32 | width (0 = unknown yet)

enum { BW_SITE = 0x1297738, BW_SITE2 = 0x1297888, BW_W1 = 0x129773c, BW_D1 = 0x1297740, BW_W2 = 0x129788c, BW_D2 = 0x1297890 };
static const uint32_t k_bw_fp[7] = {0x7100069f /* cmp w20,#1 */, 0x5280a009 /* mov w9,#1280 */, 0x32190fea /* orr w10,wzr,#1920 */,
                                    0xb0012d0b, 0x1a890149 /* csel */, 0xb9001a69 /* str w9,[x19,#0x18] */, 0x52805a08 /* mov w8,#720 */};

static int bw_poke(module_t *m, uint32_t off, unsigned imm, int rd) {
    uint32_t *at = (uint32_t *)(m->base + off);
    uint8_t *pg = (uint8_t *)((uintptr_t)at & ~(uintptr_t)0x3FFF);   // 16 KB = the loader's sealing granule
    if (mprotect(pg, 0x4000, PROT_READ | PROT_WRITE)) return -1;
    *at = 0x52800000u | ((imm & 0xffff) << 5) | ((unsigned)rd & 31);   // movz w<rd>,#imm
    if (mprotect(pg, 0x4000, PROT_READ | PROT_EXEC)) die("[wide] mprotect RX");
    __builtin___clear_cache((char *)at, (char *)(at + 1));
    return 0;
}

void dm_bl2_wide_install(void);   // main.c host_preload, right after load_modules (before any guest code runs)
void dm_bl2_wide_install(void) {
    const char *e = getenv("DM_BL2_WIDE");
    if (!e || !*e || (*e == '0' && !e[1])) return;
    long want = atol(e);
    unsigned dk, hh;
    if (want >= 1280) {   // an explicit docked width
        dk = (unsigned)((want + 8) / 16 * 16);
        hh = dk * 2 / 3 / 16 * 16;
    } else {
        uint64_t sc = front_screen_px();
        unsigned sw = (uint32_t)sc, sh = (uint32_t)(sc >> 32);
        if (!sw || !sh) { LOG("【红】[wide] DM_BL2_WIDE: screen size unknown: the window stays 16:9"); return; }
        if (sh > sw) { unsigned t = sw; sw = sh; sh = t; }   // landscape: long side first
        dk = (unsigned)(((uint64_t)1080 * sw / sh + 8) / 16 * 16);
        hh = (unsigned)(((uint64_t)720 * sw / sh + 8) / 16 * 16);
    }
    if (dk > 4096) dk = 4096;
    if (hh > 2560) hh = 2560;
    if (dk <= 1920) { LOG("[wide] DM_BL2_WIDE=%s: the screen is not wider than 16:9: the window stays 1920x1080 / 1280x720", e); return; }
    module_t *m = NULL;
    for (int i = 0; i < g_nmod; i++) if (!strcmp(g_mod[i].name, "main")) m = &g_mod[i];
    if (!m || !m->base || m->text_end < BW_D2 + 4 ||
        memcmp(m->base + BW_SITE, k_bw_fp, sizeof k_bw_fp) || memcmp(m->base + BW_SITE2, k_bw_fp, sizeof k_bw_fp) ||
        *(const uint32_t *)(m->base + BW_W1 - 12) != 0x2a0003f4 || *(const uint32_t *)(m->base + BW_W2 - 12) != 0x2a0003f4) {
        LOG("【红】[wide] main is not Borderlands 2 v131072 (0x1297730 layout): the window stays 16:9"); return;
    }
    if (bw_poke(m, BW_W1, hh, 9) || bw_poke(m, BW_D1, dk, 10) || bw_poke(m, BW_W2, hh, 9) || bw_poke(m, BW_D2, dk, 10)) {
        LOG("【红】[wide] mprotect failed: the window stays 16:9"); return;
    }
    // The SDK's display-resolution table: every docked entry is "mov w8,#1080; orr w10,wzr,#1920". Left at 1920 the game still
    // presents a 1920 frame and its last pass crops the right of the wide render; widened here the swapchain follows.
    {
        module_t *s = NULL;
        for (int i = 0; i < g_nmod; i++) if (!strcmp(g_mod[i].name, "sdk")) s = &g_mod[i];
        static const uint32_t site[8] = {0x53820, 0x5384c, 0x53ab0, 0x53ad0, 0x53b78, 0x53b88, 0x53b9c, 0x53bb8};
        int ok = s && s->base && s->text_end > site[7] + 4;
        for (int i = 0; ok && i < 8; i++)
            ok = *(const uint32_t *)(s->base + site[i] - 4) == 0x52808708u && *(const uint32_t *)(s->base + site[i]) == 0x32190feau;
        if (ok) for (int i = 0; i < 8; i++) bw_poke(s, site[i], dk, 10);
        LOG("[wide] BL2 sdk resolution table %s (docked width %u)", ok ? "widened" : "is not this build, left at 1920", dk);
    }
    LOG("[wide] BL2 window %ux1080 docked / %ux720 handheld (screen %u:%u, Hor+, nothing cropped)", dk, hh,
        (unsigned)(front_screen_px() & 0xffffffff), (unsigned)(front_screen_px() >> 32));
}
#endif
