# BL2 port — current state / handoff

Read `README-BL2.md` first for build and run steps. This file is the short status for
whoever picks the work up next.

## What this repo contains

- The DM NVN-HLE framework (`dm/`) built with `DM_GAME=bl2`;
- BL2-specific host code: `dm/host/hle_bl2_probe.c`, `dm/host/hle_bl2_wide.c`, `dm/host/hle_oodle.c`;
- Shader tooling: `tools/bl2_shader_jobs.py`, `tools/bl2_shader_scan.py`, `tools/bl2_ue3_shaders.py`,
  plus the shared `dm/gfx/tools/dmsh_vk*.py` translators;
- Android UI: `Bl2Cheat*`, `Bl2Gfx`, `Bl2Ini`, the touch pad, the official launcher icon;
- CI: `.github/workflows/build-apk.yml` (artifact + tag release).

**Not in this repo** (by design): game data (`romfs/`, `aoc/`, `patch-cn/`), translated
shaders (`*.xgs`), the four generated `DM_GEN_DIR` headers, APKs, keys, saves.
See §0 of `README-BL2.md` for the legal position.

## Verified on

realme RMX8899 / SM8845 / Adreno 829 / Android 17. Other GPUs and drivers are not
validated: shader modules may be rejected, performance/thermal headroom differs.

## Work already done

- Offline shader pipeline: full-mount job extraction, two-part vertex merge
  (`dmsh_vk.py:vertex_ab`), `spirv-opt -O --preserve-bindings` normalization for modules
  a driver refuses to link, and a per-title clip-space z correction.
  1568 merged bundles were produced and verified on the device.
- Android: screen L3 latch re-presses L3 on every start from standstill; official icon;
  `debuggable false`; `DM_LOG=0` gates native `boot.log`/logcat and the Java live logcat.
- Build docs: `README-BL2.md` (data layout, `dm/env`, `DM_GEN_DIR`, shader pipeline).

## CI status (what to fix next)

The workflow gets through SDK/NDK setup, header stand-ins and compilation; it fails at
**link** with:

1. `dm_ta_current_set` / `dm_ta_skill` / `dm_ta_frame_at`
   These come from `dm_touch_native_art.c`, which `dm/ios/tools/native_art/generate.py`
   generates from game data. A stand-in implementation exists in `dm/host/doom_stubs.c`
   (around line 167) — copy/adapt it into the CI `ci-gen/dm_touch_native_art.c`.
2. `nvn_trace_c` / `nvn_bigstack_top` / `nvn_real_big`
   NVN assembly symbols (`dm/gfx/nvn/`). The CMake source list is parsed from
   `dm/host/Makefile`; the corresponding `.s`/`.inc` sources are not reaching
   `dm/android/CMakeLists.txt`, so they must be added there (or the Makefile parse must
   keep them).

Everything else in the workflow is done: runner SDK packages, submodules, stand-in
`dm_hud_exp.h` / `dm_vault_tab.h`, artifact upload, tag release.

## Key switches

`dm/env` (see `README-BL2.md` §3): `DM_BL2_WIDE_PRESENT`, `DM_LOG`, `DM_3D_SCALE`,
`DM_3D_SCALE_DYN`, `DM_VK_DRIVER`. Defaults are in the code under `dm/host` and
`dm/gfx/vulkan/engine`.
