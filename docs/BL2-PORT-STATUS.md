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
- Android input: screen L3 latch (re-presses L3 on every start from standstill); ZR (fire)
  sets `Ctl.look`, so the same finger that holds fire also drives touch look — done in
  both the theme layout and the DOOM layout (`DoomPadView.build`).
- Six-axis / gyro aiming: `dm/android/front_android.c` samples the phone gyroscope and
  pushes it through `dm_sixaxis_push` into `hle_hid.c`. BL2 imports
  `IsSixAxisSensorAtRest`, which the HLE did not provide (always false now).
  `DM_GYRO` semantics: unset = on, `DM_GYRO=0` = off (an empty value used to be treated
  as 0, silently disabling the sensor — fixed). XC2/D3 still default to off.
- Pad UI: button and stick-base fills are transparent (pressed highlight kept);
  `debuggable false`; `DM_LOG=0` gates native `boot.log`/logcat and the Java live logcat.
- Build docs: `README-BL2.md` (data layout, `dm/env`, `DM_GEN_DIR`, shader pipeline).

## CI status: building and publishing

`.github/workflows/build-apk.yml` builds on ubuntu-latest and **succeeds**; tag
`v0.2.0-bl2` produced a GitHub Release with `BL2-port.apk`. Things that had to be fixed:

1. `actions/checkout` needs `submodules: recursive` (libadrenotools);
2. the runner's SDK is used directly (the `tools` SDK package no longer exists in
   `android-actions/setup-android@v3`);
3. `DM_GEN_DIR` gets stand-in headers (`dm_hud_exp.h` with `k_exp`, `dm_vault_tab.h` with
   `VT_*`/`vt_row`, `dm_touch_native_art.c` with the `dm_ta_*` no-ops from
   `dm/host/doom_stubs.c`). The real headers are generated from game data;
4. **gradle must pass `-DDM_GAME`** to CMake (it defaulted to `d2r`, so `DM_GAME_BL2` was
   never defined and the BL2 host sources + the `hle_nvn.c` BL2 branch were missing);
5. `hle_nvn.c` now builds its big-stack / trace entry for BL2 too (`nvn_entry.S`
   references `nvn_trace_c` / `nvn_bigstack_top` / `nvn_real_big` / `nvn_lc_tab`).

The CI APK is debug-signed by the runner, so it cannot upgrade a locally built install;
configure a fixed keystore in secrets before using it as the release artifact.

## Open items

- HD textures: only the Switch texture set is shipped. The PC Ultra HD pack is feasible
  but is a resource conversion/re-pack job (pack layout, BC + NVVM swizzle, mip chain,
  streaming pool), not a file swap — see the analysis in the conversation, not yet started.
- Release signing: pin a keystore in secrets and derive `versionCode` from
  `dm/android/bl2/VERSION`.
- Other devices: shader acceptance, thermal headroom and touch layout are unvalidated.

## Key switches

`dm/env` (see `README-BL2.md` §3): `DM_BL2_WIDE_PRESENT`, `DM_LOG`, `DM_3D_SCALE`,
`DM_3D_SCALE_DYN`, `DM_GYRO`, `DM_VK_DRIVER`. Defaults are in the code under `dm/host`
and `dm/gfx/vulkan/engine`.
