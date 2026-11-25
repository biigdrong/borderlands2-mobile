# Installing Divinity Original Sin 2 Mobile — step by step

Русская версия: [INSTALL.ru.md](INSTALL.ru.md).

Divinity Original Sin 2 Mobile runs **your own copy** of Divinity: Original Sin 2 – Definitive Edition for Nintendo
Switch on an Android phone. This project contains no game files and never shares game files or console keys: you dump
them from a Switch you own. A setup program on your PC turns your dump into a game folder (~13 GB), you copy that folder
to the phone and install the app.

The whole thing takes about 30–60 minutes, most of it copying and waiting for setup.

## What you need

**From your Switch** (see step 1):

| What | Details |
|---|---|
| Divinity: Original Sin 2 – Definitive Edition base game | title id `010027400CDC6000`, from your cartridge or eShop copy |
| Update **v786432** | title id `010027400CDC6800` (the latest). Only this exact update works (the port is made for its code). Dump tools usually put it in the file name, e.g. `...[010027400CDC6800][v786432].nsp` |
| `prod.keys` | the keys of **your own** console |

No language pack and no DLC is needed: the game's languages and its *Gift Bag* content are in the base game.

The game and the update can be **NSP, NSZ, XCI or XCZ**, in any combination. Split dumps from a FAT32 SD card work too
(a folder with parts `00`, `01`, … or `name.xc0`, `name.xc1`, …). File names do not matter: setup recognises the files
by their content.

The touch interface (menus, the HUD's on-screen buttons, the button column on the right edge, the panels' button rows) is
made from these Switch files alone; its button art is this project's own. No other edition of the game is needed.

**A PC** with Windows 10/11 (64-bit), Linux or macOS:

- about **20 GB of free disk space** while preparing (up to ~32 GB with NSZ / XCZ input);
- internet on the first run: setup downloads a few helper tools (Python packages ~60 MB, Microsoft .NET ~300 MB, the
  SPIR-V tools of Google's Android NDK ~7 MB, and Python itself ~15 MB on Windows if you have none). It asks before
  each download and puts them only inside its own folder. Later runs work offline.

**A phone:**

- Android 12 or newer, 64-bit (Android 10 and 11: the separate `-android10` APK, Step 6);
- **Snapdragon with an Adreno GPU recommended** (tested on Snapdragon 8 Gen 3; Mali / PowerVR / Xclipse phones use their
  own driver with engine fallbacks and are untested);
- 8 GB of RAM or more;
- about **13 GB free** in internal storage (about **15 GB** with the `astc` folder that phones without BC need, see
  Step 5);
- a USB cable (or another way to copy the folder to the phone).

## Step 1. Get the game files and keys from your Switch

**Dumping them yourself.** This needs a Switch that can run homebrew (how to get there is not covered here).
1. Install the game and the latest update (v786432) on the Switch.
2. Dump them with [nxdumptool](https://github.com/DarkMatterCore/nxdumptool): installed or eShop copy → *NSP*;
   cartridge → *XCI* (the installed update is dumped separately as NSP). For NSP dumps turn on
   **"remove console specific data"** — otherwise the update cannot be read on a PC.
3. Dump the console keys with [Lockpick_RCM](https://github.com/shchmue/Lockpick_RCM). You get `prod.keys` on the SD card
   in `switch/`.
4. Copy the files to your PC.

Do not download game files or keys from the internet, and do not share yours.

## Step 2. Get Divinity Original Sin 2 Mobile setup

Download this repository as a ZIP (green **Code** button → **Download ZIP**) or clone it, and extract it to a disk with
enough free space, into a short path such as `D:\DOS2-setup`. You get a folder with `setup.bat`, `setup.sh` and a folder
`put-game-files-here`.

## Step 3. Put your files into `put-game-files-here`

```
<setup folder>/
├── setup.bat
├── setup.sh
└── put-game-files-here/
    ├── Divinity Original Sin 2 ... [010027400CDC6000][v0].nsp         (or .nsz / .xci / .xcz — the base game)
    ├── Divinity Original Sin 2 ... [010027400CDC6800][v786432].nsp    (the update)
    └── prod.keys
```

You may also put the folder from your dump tool inside it as it is (setup looks two folders deep).

## Step 4. Run setup

### Windows

1. **Double-click `setup.bat`.** If Windows warns about a file from the internet, choose **Run** (or **More info → Run anyway**).
2. Answer the questions with **Y** and Enter (Enter alone also means yes): *Download a private Python?* (only when your PC
   has no Python 3.10+), *Install the Python packages?*, *Download and install the .NET 10 SDK?*, *Download them there
   now?* (the SPIR-V tools, stage 8). Everything goes into `tools\.runtime` inside the setup folder. Nothing is installed
   system-wide, no admin rights are needed.
3. **Wait.** Setup shows ten numbered stages with progress:

   | Stage | Usually takes |
   |---|---|
   | 1. Finding and checking your game files | seconds |
   | 2. Checking the tools and the free space | seconds (first time: the .NET download) |
   | 3. Extracting the game program | seconds |
   | 4. Patching the program for Android | 1–2 min |
   | 5. Checking the patch | 1–10 min |
   | 6. Extracting the game data (~11.4 GB) | 1–15 min |
   | 7. Translating the shaders (12 329 of them) | 2–20 min |
   | 8. Fusing the post-processing shaders (`native-post.xgspack`, `native-nr.xgspack`, `native-nr33b.xgspack`, `native-nr33c.xgspack`) | 3–5 min (first time: the ~7 MB SPIR-V tools download) |
   | 9. Making the touch interface package | under a minute |
   | 10. Preparing textures for phones without BC (ASTC) | 5–20 min |

   It checks the free space before it starts and stops early with a clear message when something is wrong. If you
   close the window or the PC turns off, just run setup again: finished stages are skipped (stage 10 resumes where it
   stopped). If your phone has an Adreno GPU (Snapdragon) you can skip stage 10: `setup.bat --skip-astc`. Stage 8 is
   optional: if it cannot be done (no internet for its tools, say), setup says so and goes on; the game then draws its
   post-processing passes one by one (a little slower), and the next setup run tries again.
4. At the end it shows where the finished folder is, the adb commands to copy it, and what to do next.

Instead of using `put-game-files-here` you can also drag the files onto `setup.bat`.

### Linux / macOS

1. You need Python 3.10 or newer with its `venv` module (Debian / Ubuntu: `sudo apt install python3 python3-venv python3-pip`;
   Fedora: `sudo dnf install python3 python3-pip`; Arch: `sudo pacman -S python python-pip`; macOS: `brew install python@3.12`).
2. Open a terminal in the setup folder and run `bash setup.sh`. Answer the questions with **Y** and wait (same stages
   as on Windows). Python packages go into `tools/.runtime/venv`, .NET into `tools/.runtime/dotnet`.

You can also give the files directly, in any order: `bash setup.sh ~/dumps/dos2-base.nsp ~/dumps/dos2-update.nsp ~/prod.keys`.

### Not sure what is missing?

Run `setup.bat check` (Windows, in a terminal in the setup folder) or `bash setup.sh check`. It lists the tools, the
game files it finds, what is already prepared and the next step, and changes nothing.

## Step 5. Copy the game folder to the phone

The finished folder is **`work/DivinityOriginalSin2Mobile`** inside the setup folder.

- **USB file transfer:** connect the phone, choose **File transfer**, open the phone's **internal storage** →
  **Download** and copy the whole **`DivinityOriginalSin2Mobile`** folder there. It must end up exactly like this:

  ```
  Internal storage/Download/DivinityOriginalSin2Mobile/romfs/...
  Internal storage/Download/DivinityOriginalSin2Mobile/dm/out/...
  Internal storage/Download/DivinityOriginalSin2Mobile/dm/shaders/shaders.xgspack
  Internal storage/Download/DivinityOriginalSin2Mobile/dm/shaders/native-post.xgspack
  Internal storage/Download/DivinityOriginalSin2Mobile/dm/shaders/native-nr.xgspack     (and native-nr33b / native-nr33c)
  Internal storage/Download/DivinityOriginalSin2Mobile/astc/...       (only needed without BC: Mali, PowerVR, Xclipse)
  Internal storage/Download/DivinityOriginalSin2Mobile/drivers/       (your own Vulkan drivers, optional)
  ```

  The `astc` folder (~1.5 GB) is used only by phones whose GPU cannot sample BC textures (Mali, PowerVR, Xclipse); on a
  Snapdragon / Adreno phone you can leave it out.
- **adb (USB debugging):** `setup.bat push` / `bash setup.sh push` copies only what is missing and resumes after an
  interruption; setup also prints the plain `adb push` commands.

## Step 6. Install the app

Install the APK from the [latest release](https://github.com/Desm0nt/divinity-original-sin-2-port/releases/latest), or
build it yourself (`build.bat`, see *Building* in the [README-DOS2](../README-DOS2.md)). Android asks you to allow installing apps
from your browser or file manager the first time.

- Android 12 or newer: `DOS2-Mobile-v<version>-arm64.apk`.
- Android 10 or 11: `DOS2-Mobile-v<version>-arm64-android10.apk` (the same game built for older Android; it asks for the
  storage permission instead of *All files access*; not yet tested on a real Android 10 device).

## Step 7. First launch

1. Start **Divinity Original Sin 2 Mobile**.
2. It asks for **All files access** (it needs it to read `Download/DivinityOriginalSin2Mobile`). Turn it on and go back.
3. The first start and the first visit of every scene take longer than later ones (the Vulkan pipelines are built and
   cached). When the game offers *Steam cross-save*, answer **No** (there is no network play).
4. The gear button (⚙) opens the pause menu and the port's settings: language, render resolution (default: the screen's
   own height), dynamic resolution (off), frame rate limit (60), touch as mouse, left / right stick, button column,
   Vulkan driver, FPS counter, control layout.

**Playing by touch:** menus react to taps on their items, and the button hints at the bottom of the screen are buttons.
In the world a tap is a click (walk, talk, pick up, attack); a **long press** opens the *Actions…* menu of what is under
your finger; drag items to move them. Swipe with one finger on the right part of the screen to turn the camera, pinch
to zoom. The move stick appears under your left thumb anywhere in the lower left (the gear can hide it: then tap the
floor to walk). Everything else is on the on-screen pad (d-pad, ABXY, shoulder buttons, − / +); *Edit the layout* in
the gear dialog moves, resizes and hides its buttons. The HUD also has a button column on the right edge (character panels,
journal, map) and buttons for options, tactical camera, cancel, end turn, sneak and weapon.

Saves and settings stay in the app's own storage. Installing a newer APK over the old one keeps them; the pause menu can
export and import saves.

## Troubleshooting / FAQ

**"your Divinity Original Sin 2 update is v… ; only v786432 is supported"** — dump update v786432.

**"the Divinity Original Sin 2 base game / the update … is not among the files"** — setup lists every file it found with
its title id and version; check that you copied the right files into `put-game-files-here`.

**"prod.keys not found" / "your prod.keys has no …" / "does not decrypt with this prod.keys"** — use the keys of the
console you dumped from, made with an up-to-date Lockpick_RCM. `title.keys` is a different file.

**"personalized ticket" / "no ticket for rights id"** — dump the NSP again with nxdumptool's *remove console specific
data* option turned on (and keep the ticket).

**"not enough free space"** — free some space, or put the work folder on another disk: `setup.bat --work D:\dos2-work`
(Windows) or `bash setup.sh --work /mnt/big/dos2-work`.

**I already set up an older version (0.1.x)** — run setup again in the same folder after downloading the new version: it
skips everything that is still current and makes only what changed (for 0.2.0: the touch interface package and three new
shader packs, a few minutes). Then copy `romfs/Data/TouchUI.pak` and the whole `dm/shaders` folder to the phone again
(or the whole `DivinityOriginalSin2Mobile` folder; overwriting the files that did not change is fine).

**I set up an older release with an `.ipa`** — it is not needed any more (setup ignores it). Run setup again after
updating: it remakes only the touch interface package (stage 9); copy `romfs/Data/TouchUI.pak` to the phone again.

**Where is the language setting?** — gear button → *Game settings…* → *Game language*; restart the game afterwards.
The languages are built in.

**Black screen or the app closes** — open the gear dialog → *Vulkan driver* → try *System*, restart the app. Then open an
issue on this repository with the phone model, Android version and what happened, and attach the whole
`Download/DivinityOriginalSin2Mobile/logs/` folder: after a crash the next start writes `crash.txt` there (with the log
of the crashed run) and says so on screen; `boot.log` and `logcat.txt` of the current run and `boot.prev.log` /
`logcat.prev.txt` of the one before are written line by line while the game runs (so they are there even when Android
kills the game). Every setup run is logged to `work/setup.log`: attach it for setup problems.

Technical details of the preparation (what each step does, running the tools by hand): [dos2/GAME_FILES.md](dos2/GAME_FILES.md).
