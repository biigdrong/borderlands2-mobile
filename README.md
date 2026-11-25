# Borderlands 2 (Switch) on Android

A native Android port of **Borderlands 2** for Nintendo Switch, built on the DM NVN HLE
framework. The game's own AArch64 code runs directly on the phone's CPU; the host implements
the Switch system services (`nn::` HLE) and replays the NVN graphics API on Vulkan. You bring
the game: this repository contains no game content, no keys and no APKs built from them.

> **This repository is the Borderlands 2 port.**
> It is **not** the Divinity: Original Sin 2 port. The framework, tools and most of the host
> code are shared with [Divinity: Original Sin 2 Mobile](https://github.com/Desm0nt/divinity-original-sin-2-port)
> (upstream), and that project's original documentation is kept here as
> [README-DOS2.md](README-DOS2.md) for reference.

Status: reference port. Validated on one device — **realme RMX8899 / Snapdragon SM8845 /
Adreno 829 / Android 17**. Other GPUs and drivers are not guaranteed to work.

## Start here

| Document | Contents |
| --- | --- |
| [README-BL2.md](README-BL2.md) | Build and run: data layout on the phone, `dm/env` switches, APK build, shader bundles |
| [docs/BL2-PORT-STATUS.md](docs/BL2-PORT-STATUS.md) | What works, what is still open (HD textures, per-device validation) |
| [docs/BL2-CHEATS.md](docs/BL2-CHEATS.md) | The `cheat.req` console and the AI-teammate hooks |
| [docs/BL2-NPU-AI-TEAMMATE.md](docs/BL2-NPU-AI-TEAMMATE.md) | Design discussion: an NPU-driven AI teammate that does not reuse the game's AI |

## What it is

- The original game code executing **natively** on the phone — no emulated CPU, no JIT.
  Switch and Android phones share the AArch64 instruction set; an offline rewriter
  (`dm/tools/patch_nso.py`) changes only the instructions that cannot run unchanged on Linux
  into calls to the host.
- An HLE host for the Horizon OS services the game uses, and an NVN → Vulkan recorder
  tuned for Adreno. The game's shaders are translated to SPIR-V offline on your PC.
- A phone port with touch control, widescreen presentation at the screen's own aspect, and
  the shared settings of the other DM ports (DOOM, Diablo III, Torchlight II, DOS2).

## What it is not

- An emulator, cloud gaming or streaming.
- **A source of game content.** Dump the game from a Switch you own and convert it on your
  PC. Do not commit or share the dump, the generated `*.xgs` shaders, or APKs built from it.
- Affiliated with Gearbox Software, 2K or Nintendo.

## Upstream

This tree is a fork of [divinity-original-sin-2-port](https://github.com/Desm0nt/divinity-original-sin-2-port)
built with `DM_GAME=bl2`. Framework-level documentation (install flow, driver packaging,
dependency list) still lives in that project and is mirrored under [docs/upstream](docs/upstream)
and [README-DOS2.md](README-DOS2.md).
