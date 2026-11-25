# Divinity Original Sin 2 Mobile

**A native Android port of Divinity: Original Sin 2 – Definitive Edition for Nintendo Switch.** The game's own AArch64
program runs directly on the phone's CPU; a small host provides the Switch system services (HLE of the `nn::` SDK), and
the NVN graphics API is replayed on Vulkan. You bring the game: this repository contains no game content and no keys.

Русский: [ниже](#по-русски).

**Install:** step-by-step guide for players — [docs/INSTALL.md](docs/INSTALL.md) (English) ·
[docs/INSTALL.ru.md](docs/INSTALL.ru.md) (по-русски). In short: dump your own game + update v786432 and `prod.keys`, put
them into `put-game-files-here/`, double-click `setup.bat` (or `bash setup.sh`), copy `work/DivinityOriginalSin2Mobile`
to the phone's `Download` folder and install the APK from the
[Releases page](https://github.com/Desm0nt/divinity-original-sin-2-port/releases/latest) (or build it with `build.bat`,
see *Building*).

> [!WARNING]
> **Tested so far on one device: Snapdragon 8 Gen 3 / Adreno 750 (Xiaomi 14 Ultra) with the bundled Mesa Turnip driver.**
> **Devices with Mali (Exynos, Dimensity, Tensor), PowerVR and Xclipse GPUs have not been tested at all** — the engine has
> fallbacks for them (shared with the DOOM, Diablo III and Torchlight II ports), but expect problems. If something goes
> wrong on your device, please [open an issue](https://github.com/Desm0nt/divinity-original-sin-2-port/issues) and
> **always attach the logs**: the whole folder `Download/DivinityOriginalSin2Mobile/logs/` — `crash.txt` (written at the
> start after a crash), `boot.log` / `boot.prev.log` and `logcat.txt` / `logcat.prev.txt` (written live, so they survive
> even when the system kills the game) — and name your phone model and Android version. Without logs a report usually
> can't be acted on.

## Screenshots

Captured on the phone (Xiaomi 14 Ultra, Adreno 750, Mesa Turnip 27) during development: the game renders at the
screen's 20:9 shape (wider view, nothing stretched). The counter in the top-left corner is the port's own FPS / frame
time / GPU time overlay (it can be turned off). Game text in Russian; the console interface with touch handling, the
button column on the right edge and the on-screen pad.

| | |
|---|---|
| ![Title screen](docs/images/title.jpg) | ![Main menu](docs/images/main_menu.jpg) |
| ![Character creation](docs/images/character_creation.jpg) | ![On the ship: HUD, hot bar and the button column](docs/images/ship_hud.jpg) |
| ![Long press on an item: the Actions menu](docs/images/actions_menu.jpg) | ![Steam clouds on the ship](docs/images/steam_cloud.jpg) |
| ![Game options, by touch](docs/images/options.jpg) | ![Port settings (gear button)](docs/images/settings.jpg) |

## What it is, and what it is not

**It is:**

- The original game code, **executing natively** on the phone — no emulated CPU, no JIT. Switch and Android phones
  share the AArch64 instruction set; an offline rewriter (`dm/tools/patch_nso.py`) changes only the few instructions
  that cannot run unchanged on Linux (x18 use, TLS reads, system calls, counter reads) into calls to the host, and
  `dm/verify/equiv.py` checks every rewritten site against the original instruction before you play.
- An HLE host for the Horizon OS services Divinity: Original Sin 2 uses (SDK **9.3.0**: threads, memory with the virtual
  address memory manager, file system, audio, input, account, save data…), and an NVN → Vulkan recorder and engine tuned
  for Adreno GPUs. The game's 12 329 shaders (Larian's `.bshd` programs and the ones built into the program) are
  translated to SPIR-V offline on your PC.
- A phone port with **touch control on the console interface**, a widescreen picture at the screen's own resolution,
  frame rates above 60, game controllers and the shared settings of the DOOM / Diablo III / Torchlight II ports (see
  *Features*).

**It is not:**

- An emulator, cloud gaming or streaming.
- **A source of game content.** There is no game program, data, shader, text, art or key in this repository, and the
  APK contains none. You dump the game from a Switch you own and convert it on your PC
  ([docs/dos2/GAME_FILES.md](docs/dos2/GAME_FILES.md)). What the repository knows about the game (patch addresses,
  structure offsets, format descriptions…) is listed in [docs/dos2/DERIVED.md](docs/dos2/DERIVED.md).
- Online. Multiplayer and Steam cross-save answer like a console without a connection (answer *No* when the game offers
  cross-save); the game plays single player with local saves.
- Affiliated with Larian Studios or Nintendo.

## Features

**Touch control on the console interface**

The Switch version has a console interface made for a gamepad. The port keeps it and adds touch to it. The interface
movies are patched on your PC by setup (`romfs/Data/TouchUI.pak`); nothing of the game is in the APK.

From the Switch files alone:

- **Menus by tap**: the main menu, character creation, the pause menu, message boxes, save / load, options, mods,
  tutorial boxes and dialogue answers react to taps on their own elements, and the **button hints** at the bottom of a
  screen (e.g. *(B) Back*) are buttons too — a tap on a hint presses that pad button. A tap on the minimap opens the
  map, a tap on a portrait selects that character.
- **Touch as a mouse in the world**: tap = click (walk there, talk, pick up, attack); **long press = right click**, which
  opens the *Actions…* menu of an item or character (or tap the *(X) Actions…* hint over the selected target); drag
  items; **tap places moved items** (in the game's move mode the item goes to the floor where you tap).
- **Camera**: **one-finger swipe on the right 60 % of the screen** turns it, pinch zooms, two fingers left / right turn
  it too.
- **Floating left stick** for walking: invisible until you touch the lower left part of the screen, it appears under your
  thumb and is gone when you let go (it can be turned off: then you walk by tapping the floor). The right stick is hidden
  by default (the gear can show it).
- **On-screen pad** (Joy-Con layout: d-pad, ABXY, L / R / ZL / ZR, − / +) for everything the game does with buttons, with
  the layout editor of the DOOM port (move, resize, hide); game controllers (Bluetooth / USB) and rumble work as well.

The console HUD also gets on-screen buttons (made from the Switch files alone; the button art is this project's own):

- the **button column** on the right edge (character panels, journal, map, options), which can be folded or hidden and
  folds itself while a gamepad is connected;
- the hot bar's page arrows, end turn, sneak and tactical camera buttons, taps on hot bar slots;
- the **panels** (inventory, equipment, character, skills, journal, crafting, trade, rewards) with a button
  row and taps on their tabs, items and skills.

**Picture**

- **Widescreen (Hor+)**: the game renders in the screen's own shape (e.g. 2400×1080 on a 20:9 phone) with a wider view
  of the world, the HUD at the screen edges.
- **Resolution:** the window follows the Switch mode (Docked = the screen's own resolution, Handheld = lighter); the
  **3D resolution** is set per mode: a fixed 100 / 83 / 75 / 67 / 50 % or **dynamic** (the game's own DRS with a target of
  30 / 45 / 60 / 75 / 90 / 120 fps and a lowest size of 85 / 75 / 60 / 50 %; the default in Handheld), with **FSR 1**
  upscaling below 100 %. The interface always stays at full resolution.
- **Graphics quality** page (Off / Light / Medium / Maximum / Custom): bloom, anti-aliasing, shadow maps and filter,
  distant shadows, texture sharpness, angle filtering, model detail distance, lamps per spot.
- **Frame rate limit 30 / 60 (default) / 90 / 120 / no limit** (90 and 120 only where the screen has such a mode; above
  60 is experimental: more heat). The game's speed does not change with the frame rate.

**Front end shared with the DOOM / Diablo III / Torchlight II ports**

- Gear button (⚙) → **pause menu** that really holds the game (as the Switch HOME menu), save export / import.
- Port settings: menu and game language, Switch mode, 3D resolution, dynamic resolution, FSR 1, sharpening, frame rate limit,
  thermal mode, graphics quality, safe mode (Mali / PowerVR), touch as
  mouse, left / right stick, button column, Vulkan driver (with a driver manager), vibration, FPS counter, control
  layout and editor.
- **Textures for phones without BC** (Mali, PowerVR, Xclipse): setup encodes the game's BC textures once to ASTC on your
  PC (`astc/dos2-astc.pack`, ~1.5 GB, every texture kept at ≥ 42 dB against the original); such phones load them directly instead
  of decoding BC at every upload, and whatever the pack lacks is encoded on the phone in the background. Adreno phones
  sample BC natively and do not need the pack.

## Current state

Tested on **Snapdragon 8 Gen 3 / Adreno 750** (Xiaomi 14 Ultra) with Mesa Turnip v27.

- Boot, the main menu, character creation and the start of the campaign (the ship) run at the 60 fps default; with the
  higher limits the frame rate goes above 60 where the GPU allows.
- Touch on the console interface, widescreen, the pause menu and the settings as described above.

### Known limitations

- Only update **v786432** is supported; the patches and addresses are tied to its build id (`main` 4979b200…,
  `sdk` 230994ac…).
- The first time a scene is shown the Vulkan pipelines are built, which can stutter for a moment; later visits are
  smooth (the pipeline cache is kept).
- No online or local multiplayer; Steam cross-save is not available.
- Only one device has been tested; other Snapdragon devices may work, other GPUs (Mali, PowerVR, Xclipse) are untested
  (the engine has fallbacks for them, see *Other GPUs*).
- Touch on the console interface is new: some screens may still need the on-screen pad. Many renderer and host fixes are
  behind switches for A/B testing (`Download/DivinityOriginalSin2Mobile/dm/env`); see
  [docs/dos2/DOS2_PORT.md](docs/dos2/DOS2_PORT.md).

## Building

Requirements: Android SDK with NDK r29 (29.0.14206865), CMake ≥ 3.22 and Ninja, JDK 17+ and Gradle, Python 3. Clone
with submodules:

```sh
git clone --recursive https://github.com/Desm0nt/divinity-original-sin-2-port
# or, in an existing clone:
git submodule update --init --recursive
```

Configure the native host for Divinity: Original Sin 2 (`DM_GAME=dos2`; the default `d2r` builds the original D2R host):

```sh
cmake -S dm/android -B work/build-android -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-31 -DCMAKE_BUILD_TYPE=Release -DDM_GAME=dos2
```

Then build, sign and (optionally) install the APK — `build.bat` on Windows (wraps the PowerShell script), `pwsh`
elsewhere:

```sh
build.bat [-Install <adb serial>] [-Android10]                 # Windows
pwsh tools/build_apk.ps1 [-Install <adb serial>] [-Android10]  # Linux / macOS with PowerShell
```

The script reads every tool path from the environment (`ANDROID_HOME`, `JAVA_HOME`, `GRADLE`, `PYTHON`) and signs with
`DM_KEYSTORE` (default: the Android debug keystore in `~/.android`). Output: `work/DOS2-port-debug.apk`
(`-Android10`: `work/DOS2-port-debug-android10.apk`) and a copy with the release name in `dist/`
(`DOS2-Mobile-v<version>-arm64.apk`, `-arm64-android10.apk`); app id `org.dos2.port` ("Divinity Original Sin 2
Mobile"). The app version comes from `dm/android/dos2/VERSION`. The launcher icon is taken from
`dm/android/dos2/icon.png` when you have one (it is not in this repository); otherwise d2r-mobile's icon is used. The script
downloads the bundled Vulkan driver packages (Turnip; PanVK and RADV-Xclipse as experimental options) with pinned SHA-256s
(`tools/fetch_drivers.py`) the first time. `work/` and `dist/`
are git-ignored; `work/` holds every build output and every game-derived file.

## Installing

Full guide: **[docs/INSTALL.md](docs/INSTALL.md)** (English) / **[docs/INSTALL.ru.md](docs/INSTALL.ru.md)** (Russian).

1. Dump your own copy (base game `010027400CDC6000` + update `010027400CDC6800` **v786432**, as NSP / NSZ / XCI / XCZ)
   and your console's `prod.keys` — e.g. with nxdumptool and Lockpick_RCM on your Switch.
2. Put the files into `put-game-files-here/` (any names) and double-click `setup.bat`, or run `bash setup.sh` on
   Linux / macOS (explicit files in any order work too; `setup check` reports what is missing and changes nothing).
   Setup provides Python, its packages and the .NET 10 SDK in `tools/.runtime` when they are missing (it asks first),
   checks the inputs and the free space (~20 GB while preparing), then extracts the program, patches it, checks the
   patch, extracts the data, translates the shaders, makes the touch interface package and the ASTC texture pack into
   `work/DivinityOriginalSin2Mobile` (~13 GB, of which ~1.5 GB ASTC textures that Adreno phones do not need). Technical
   details: [docs/dos2/GAME_FILES.md](docs/dos2/GAME_FILES.md).
3. Copy `work/DivinityOriginalSin2Mobile` to the phone's `Download` folder (USB cable, *File transfer* mode, or
   `setup push` / the adb commands setup prints) and install the APK.
4. Start *Divinity Original Sin 2 Mobile* and allow *All files access* when asked.

## Vulkan drivers

The APK bundles **Mesa Turnip v27** (an adrenotools build of Mesa main for Adreno 6xx/7xx) and uses it by default; it
falls back to the phone's own driver when Turnip does not load or finds no supported GPU. Your own adrenotools driver
package can be copied into `Download/DivinityOriginalSin2Mobile/drivers/` (the folder or the package zip as released)
and chosen in the gear dialog. Details and known packages: [drivers/README.md](drivers/README.md).

The default is picked per GPU at every start (from the DOOM 2016 port): Adreno 6xx/7xx use the bundled Turnip;
Adreno 710/720/722 and 8xx use their own Turnip package, which the app downloads when the phone is online (the list is
DOOM Mobile's public [drivers/manifest.json](https://github.com/Desm0nt/doom-port/blob/main/drivers/manifest.json),
each zip checked against its SHA-256); Mali, PowerVR, Xclipse and anything without the Adreno kernel driver use the
phone's own driver. If two launches in a row end before the first frame with a custom driver, the system driver is
chosen and saved (crash guard).

## Other GPUs (Mali, PowerVR, Xclipse)

Untested on real hardware. The engine checks the device's features and, instead of aborting, falls back where the
game's Switch shaders need something the GPU lacks (from the DOOM 2016, Diablo III and Torchlight II ports): no geometry
shaders, no D24 depth (D32 is used), no GPU timestamps, no linear filtering of some formats, no depth bounds / depth bias
clamp, no `nullDescriptor`, no sampler anisotropy, driver pipeline failures (skipped instead of fatal), interrupted fence
waits on Mali. BC textures, which Mali and PowerVR cannot sample, come from the **ASTC pack** setup made (see
*Features*); the rest are decoded on the GPU (with a self-test against the CPU decoder) and encoded to ASTC in the
background for the next time. A GPU self-test at start turns off the optimisations a driver gets wrong. One boot.log
line lists what the device needed: `NVN fallbacks on this device: ...`; the texture pack reports itself as
`NVN astc cache: ...`. Reports (device, GPU, driver, logs) are very welcome.

## Android versions and CPUs

- `DOS2-Mobile-v<version>-arm64.apk`: Android 12 or newer (minSdk 31).
  `DOS2-Mobile-v<version>-arm64-android10.apk`: the same app for Android 10 and 11 (minSdk 29; asks for the storage
  permission there instead of *All files access*); it also installs on newer Android. Not yet tested on a real
  Android 10 / 11 device.
- 64-bit ARM only. ARMv8.0 CPUs without LSE atomics (Cortex-A53 / A57 / A72 / A73 phones, e.g. Snapdragon 6xx) are
  supported: the port's own hand-written code picks an ARMv8.0 variant at start (`boot: cpu ...` line in boot.log).
- 8 GB of RAM or more: the game reserves ~3 GB of its own memory, as on the Switch.

## Logs and crash reports

Every start writes a fresh `boot.log` (the previous run is kept as `boot.prev.log`) and a live `logcat.txt` into
`Download/DivinityOriginalSin2Mobile/logs/`: the device, SoC, GPU, Vulkan driver choice, CPU features and the game's
progress. When the game crashes or is killed while playing, the next start writes **`crash.txt`** there (the previous one
is kept as `crash.prev.txt`) and shows a message. A frame stall of more than two seconds writes a report of every thread
into boot.log. Attach the whole `logs` folder to a bug report.

## Repository layout

| Path | What |
|---|---|
| `dm/` | The host (from d2r-mobile, via DOOM Mobile, Diablo III Mobile and Torchlight II Mobile): loader, HLE (`dm/host`, Divinity: Original Sin 2 code in `hle_dos2*.c` and behind `DM_GAME_DOS2`), NVN recorder and Vulkan engine (`dm/gfx`), Android app (`dm/android`; the DOS2 settings in `Tl2Gear.java`, the pad in `D3PadView.java`), offline rewriter (`dm/tools/patch_nso.py`) and its verifiers (`dm/verify`). The tree also carries the DOOM, DOOM Eternal, Xenoblade 2, Diablo III and Torchlight II code paths of the same host family; Divinity: Original Sin 2 builds `DM_GAME_DOOM` + `DM_GAME_D3` + `DM_GAME_TL2` (shared code) + `DM_GAME_DOS2`. |
| `setup.sh`, `setup.bat`, `build.bat` | Game file preparation (`tools/setup_dos2.py`) and APK build entry points |
| `tools/` | Tooling: package / RomFS / ExeFS readers, Larian LSPK reader (`lspk.py`), shader jobs (`dos2_shader_jobs.py`) and translation, touch interface package (`dos2_touchui_pak.py` and the `dos2_*_touch.py` movie patches), ASTC texture pack (`dos2_astc_cache.py`), APK build, device test and analysis scripts (also the Diablo III / Torchlight II ones this port grew from) |
| `third_party/libadrenotools` | git submodule (BSD-2-Clause) |
| `drivers/` | Notes on the bundled and optional Vulkan driver packages (no binaries) |
| `docs/dos2/` | Port documentation: journal, plans and audits, game files, derived information |
| `docs/tl2/`, `docs/d3/` | Documentation of the Torchlight II and Diablo III ports, whose host this port shares |
| `docs/THIRD_PARTY.md`, `docs/DEPENDENCIES.md`, `docs/DERIVED.md`, `docs/upstream/` | Attribution: code ported from other projects, the third-party code and D2R-derived records inherited from d2r-mobile, and d2r-mobile's acknowledgements |

## Credits

Divinity Original Sin 2 Mobile stands on the work of others — thank you:

- **[d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile)** by jhaizhou (MIT) — the base of this port: native
  NSO loader and rewriter, HLE host, NVN → Vulkan engine, shader translation chain and Android app (Java package
  `com.xiaoboluo.d2r`). Its Android app and Vulkan engine came from community contributors; see its
  [acknowledgements](docs/upstream/README-d2r-mobile.md).
- **[DOOM Mobile](https://github.com/Desm0nt/doom-port)** (the DOOM 2016 port) — the lean host core, logs and crash
  reports, driver choice and verification, non-Adreno fallbacks, GPU BC decode, ARMv8.0 thunks, the Android 10 build,
  the layout editor and the unified front end.
- **[Diablo III Mobile](https://github.com/Desm0nt/diablo3-port)** and
  **[Torchlight II Mobile](https://github.com/Desm0nt/torchlight2-port)** — the host this port is a fork of, the setup
  pipeline, the shader translator variant, the GPU self-test, the ASTC texture cache and the menu-by-tap approach.
- **[nxnative](https://github.com/seedds/nxnative)** by seedds (MIT) — threads and SVCs, SDK services (including the
  ones Divinity: Original Sin 2 adds: save data size / extension, error applet, vibration values, profanity filter),
  audio, NVN entry points, the shader program key, patcher and translator pieces.
- **[nx2android](https://github.com/shirai91/nx2android)** (MIT, seedds) — window acquire-sync fix, Android haptics,
  ADPF, gamepad code, the on-screen gamepad theme packs and layout, the save-transfer and pause-hold designs.
- **[BOTWRecompAndroid](https://github.com/mamcjr/BOTWRecompAndroid)** (MIT, Peiikai / mamcjr) — the Turnip / adrenotools
  driver loading approach, the sync-lag idea and NVN 55 object sizes (ideas, re-implemented).
- **[astc-encoder](https://github.com/ARM-software/astc-encoder)** by Arm (Apache-2.0) — the ASTC encoder in the app
  (`dm/third_party/astcenc`) and, through [astc-encoder-py](https://pypi.org/project/astc-encoder-py/) (MIT), in setup.
- **[libadrenotools](https://github.com/bylaws/libadrenotools)** by Billy Laws (BSD-2-Clause).
- **Ryujinx** shader translator (Ryujinx Team and Contributors, MIT), vendored by d2r-mobile in `dm/third_party/ryujinx`.
- **[AMD FidelityFX FSR 1](https://github.com/GPUOpen-Effects/FidelityFX-FSR)** RCAS (MIT).
- **[Granite](https://github.com/Themaister/Granite)** texture decode shaders (MIT, Hans-Kristian Arntzen) — GPU BC
  decoding for GPUs without BC support.
- **[Mesa](https://mesa3d.org) Turnip** (MIT) — the default Vulkan driver on Adreno, bundled in the APK as the adrenotools build
  by **[The412Banner](https://github.com/The412Banner/Banners-Turnip)** (Mesa main); **Mesa PanVK** (Mali) and **RADV** (Samsung Xclipse)
  adrenotools builds by [JimVulkan](https://github.com/JimVulkan) and [zenithblue-oss](https://github.com/zenithblue-oss/panvk-kbase-android)
  as experimental options (MIT). Not stored in this repository: `tools/fetch_drivers.py` downloads them at build time with pinned SHA-256s.
- Khronos **Vulkan validation layers** (Apache-2.0) — used for debugging, not redistributed.

Details per file: [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).

Divinity and Divinity: Original Sin are trademarks of Larian Studios. Nintendo Switch and NVN are trademarks of Nintendo.
This is an unofficial, non-commercial fan project with no affiliation to any of them. **You must own the game and dump
it yourself**: no game files, no keys and no game-derived output are included or distributed here; play it with a copy
you own.

## License

MIT — see [LICENSE](LICENSE). The d2r-mobile copyright notice is kept; third-party components keep their own licenses.

---

## По-русски

> [!WARNING]
> **Проверено только на одном устройстве: Snapdragon 8 Gen 3 / Adreno 750 (Xiaomi 14 Ultra).** Телефоны с GPU **Mali**
> (Exynos, Dimensity, Tensor), **PowerVR** и **Xclipse** не тестировались вообще — обходы в движке есть, но проблемы
> вероятны. Если что-то не работает,
> [откройте issue](https://github.com/Desm0nt/divinity-original-sin-2-port/issues) и **обязательно приложите логи** —
> всю папку `Download/DivinityOriginalSin2Mobile/logs/`: `crash.txt` (появляется при запуске после падения),
> `boot.log` / `boot.prev.log` и `logcat.txt` / `logcat.prev.txt` (пишутся на лету, поэтому сохраняются, даже если
> система убила игру), и укажите модель телефона и версию Android.

**Divinity Original Sin 2 Mobile** — нативный порт Divinity: Original Sin 2 – Definitive Edition для Nintendo Switch на
Android. Оригинальный AArch64-код игры исполняется прямо на процессоре телефона (без эмулятора и JIT); небольшой хост
подменяет системные сервисы Switch (HLE `nn::`, SDK 9.3), а графический API NVN воспроизводится через Vulkan. Основа —
проект [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) (MIT) через порты DOOM Mobile, Diablo III Mobile и
Torchlight II Mobile.

- **Игры в репозитории нет.** Нужна своя копия Divinity: Original Sin 2 для Switch (база + обновление v786432) и свои
  ключи консоли. **Установка по шагам: [docs/INSTALL.ru.md](docs/INSTALL.ru.md).** APK — на странице
  [Releases](https://github.com/Desm0nt/divinity-original-sin-2-port/releases/latest). Технические подробности подготовки
  файлов — [docs/dos2/GAME_FILES.md](docs/dos2/GAME_FILES.md) (англ.), журнал порта —
  [docs/dos2/DOS2_PORT.md](docs/dos2/DOS2_PORT.md).
- **Касание на консольном интерфейсе** (фильмы интерфейса патчит setup на ПК, `romfs/Data/TouchUI.pak`): главное меню,
  создание персонажа, меню паузы, окна сообщений, сохранения, настройки, моды, обучение и ответы в диалогах отвечают на
  тапы по своим элементам; подсказки кнопок внизу экрана — тоже кнопки (тап = нажатие этой кнопки пада); тап по
  мини-карте открывает карту, по портрету — выбирает персонажа. В мире касание
  работает как мышь: тап = клик (идти, говорить, подобрать, атаковать), **долгое нажатие = правый клик** (меню
  «Действия…» предмета или персонажа), перетаскивание предметов, **тап ставит перемещаемый предмет** туда, где коснулись.
  Камера: **свайп одним пальцем по правым 60 % экрана** поворачивает её, щипок — зум. **Плавающий левый стик** ходьбы
  появляется под пальцем в левой нижней части экрана (можно выключить — тогда ходьба тапом по полу); правый стик скрыт по
  умолчанию. Экранный пад (раскладка Joy-Con) с редактором раскладки; геймпады (Bluetooth / USB) и вибрация тоже
  работают.
- HUD получает и экранные кнопки (только из файлов Switch; рисунки кнопок — собственные, проекта): **колонку кнопок** справа (панели персонажа, журнал, карта, параметры; её можно свернуть или скрыть, при
  подключённом геймпаде она сворачивается сама), стрелки страниц панели быстрого доступа, конец хода, скрытность,
  тактическую камеру, тапы по ячейкам, а **панели** (инвентарь, снаряжение, персонаж, навыки, журнал, крафт, торговля,
  награды) — ряд кнопок и тапы по вкладкам, предметам и навыкам.
- **Картинка:** широкий экран по форме телефона (Hor+, например 2400×1080 на 20:9); окно по режиму Switch (в доке — родное
  разрешение экрана, портативный — легче); **разрешение 3D** на каждый режим: фиксированное 100 / 83 / 75 / 67 / 50 % или
  **динамическое** (DRS самой игры, цель 30 / 45 / 60 / 75 / 90 / 120 fps, нижняя граница 85 / 75 / 60 / 50 %; в портативном по
  умолчанию), ниже 100 % — апскейл **FSR 1**; интерфейс всегда в полном разрешении; страница **«Качество графики»**;
  **лимит кадров 30 / 60 (по умолчанию) / 90 / 120 / без ограничения** (выше 60 — эксперимент: больше нагрев; скорость
  игры от частоты кадров не меняется).
- **⚙:** меню паузы, которое по-настоящему держит игру, экспорт / импорт сохранений, язык меню и игры, режим Switch,
  разрешение 3D, динамическое разрешение, FSR 1, резкость, лимит кадров, тепловой режим, качество графики, безопасный режим (Mali / PowerVR), касание как мышь, левый / правый стик, колонка кнопок, драйвер
  Vulkan, вибрация, счётчик FPS, раскладка и её редактор.
- **Текстуры для телефонов без BC** (Mali, PowerVR, Xclipse): setup один раз перекодирует BC-текстуры игры в ASTC на ПК
  (`astc/dos2-astc.pack`, каждая не хуже 42 дБ к оригиналу); такие телефоны грузят их сразу, без распаковки BC, а
  недостающее докодируется на телефоне в фоне. Телефонам с Adreno пак не нужен.
- Проверено на одном устройстве: Snapdragon 8 Gen 3 / Adreno 750 (Xiaomi 14 Ultra) с драйвером Turnip из APK — **60 fps**
  по умолчанию, с лимитом выше 60 — больше, насколько позволяет GPU. Поддерживается только обновление v786432; при первом показе сцены возможны короткие рывки
  (сборка пайплайнов); сетевой игры и Steam cross-save нет (на вопрос о cross-save отвечайте «Нет»).
- Android 12+: `DOS2-Mobile-v<версия>-arm64.apk` (minSdk 31); Android 10 и 11: `DOS2-Mobile-v<версия>-arm64-android10.apk`
  (minSdk 29; на настоящем Android 10 ещё не проверялся). Процессоры ARMv8.0 без LSE (Cortex-A53/A73, Snapdragon 6xx)
  поддерживаются. Нужно 8 ГБ ОЗУ или больше.
- Подготовка файлов: положите базу, обновление, `prod.keys` в
  `put-game-files-here/` и дважды щёлкните `setup.bat` (Linux / macOS: `bash setup.sh`); проверка без изменений —
  `setup check`. Готовую папку `work/DivinityOriginalSin2Mobile` (~13 ГБ, из них ~1.5 ГБ ASTC-текстур, которые на Adreno
  не нужны) скопируйте в `Download` телефона (или `setup push`).
- Сборка: `cmake -S dm/android -B work/build-android … -DDM_GAME=dos2`, затем `build.bat` / `tools/build_apk.ps1`
  (см. «Building»).
