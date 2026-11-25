# BL2 cheat / AI-teammate console — how it works

The port exposes the game's own `CheatManager` plus a few BL2-specific AI hooks. The
Android pad writes one-line commands to `dm/cheat.req`; the render hook runs them on the
**game thread** (never on a host thread, so UE3 objects are only touched while the game is
stopped in a frame boundary).

## Files

| Part | File |
| --- | --- |
| Java UI + request writer | `dm/android/app/src/main/java/com/xiaoboluo/d2r/Bl2Cheat.java`, `Bl2CheatBook.java` |
| AI button on the pad | `dm/android/app/src/main/java/com/xiaoboluo/d2r/DoomPadView.java` (`K_CHEAT`, `fireAlly`) |
| Command loop | `dm/host/hle_bl2_probe.c` (`dm_bl2_cheat_tick`, `cheat_run`) |
| Hook call | `dm/gfx/nvn/hle_nvn.c` (weak `dm_bl2_cheat_tick`, called once per frame) |

## Request protocol

`dm/cheat.req` (device: `/sdcard/Download/Borderlands2Mobile/dm/cheat.req`), one command
per line, optional single argument. Results go to `dm/cheat.out` / the log. The file is
polled every 16 frames; if a name table has moved (level change), the port rescans and
re-runs the same command automatically a few seconds later.

## Commands (BL2-specific, in `cheat_run`)

| Command | Effect |
| --- | --- |
| `ally` | Make the object under the crosshair (`DebugGetPlayerTarget`) a player-team pawn via `SetAllegiance` — the "AI teammate" button on the pad sends this |
| `allyall` | Same for every pawn in the level |
| `spawnai <class>` | Spawn a pawn (AI probe) |
| `aiprobe`, `aiinit`, `aipatch [on\|off]`, `aicont add` | Inspect / initialise / patch the AI controller path |
| `aidump`, `aidiff`, `aifix`, `aiprops`, `aiprops2`, `mindfns`, `objs`, `syms` | AI/mind introspection dumps (see the `cheat_log` lines for the format) |
| `travel <map>`, `ctravel <map>`, `ploc`, `fn <name>` | Map travel, player/function lookup |
| `count`, `cycle`, `weather`, `heap`, `console <cmd>`, `say <text>` | Utility: level stats, time-of-day loop, weather, heap stats, UE3 console, HUD text |
| anything else | Forwarded to the game's `CheatManager` (e.g. `god`, `ghost`, `walk`, `give`) |

All commands are case-insensitive. Anything that needs a `CheatManager` instance reports
`没有 CheatManager 实例` until a save is loaded.

## Notes / limits

- Everything runs through `ProcessEvent` on the game thread; there is no host thread
  walking UE3 memory.
- `ally`/`allyall` need a valid target/pawn and `SetAllegiance`; failures are logged with
  the object name so the next attempt can be adjusted.
- AI introspection commands are research tools, not gameplay features; their output
  format is the `cheat_log` text, so expect raw names/addresses.
- These are debug features of a personal port. They mutate game state and are not part
  of the normal play path.
