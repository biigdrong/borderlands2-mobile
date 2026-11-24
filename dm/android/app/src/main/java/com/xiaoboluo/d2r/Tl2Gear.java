package com.xiaoboluo.d2r;

import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.system.ErrnoException;
import android.system.Os;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;

// [TL2] Torchlight II's own gear sections and their order, on the shared gear (frontend-common GearSettings / GearPages, docs/FRONTEND_UNIFIED.md
// "Gear"). This file belongs to the TL2 port (dm/android/app/src/main/java/com/xiaoboluo/d2r/Tl2Gear.java; a reference copy sits in
// frontend-common/migration/tl2/), not to frontend-common's java/: the sync never touches it. DmActivity.gearSections returns sections(this, g).
// The dialog has the rows DmActivity.showD3Settings had before the move (parity table frontend-common/migration/tl2-parity.md: same prefs,
// environment, defaults; the generic rows are GearPages' with GearText's 13 languages, the TL2 rows keep their string resources d3_* / tl2_*
// in the menu language). TL2 rows here:
//   mode            Switch mode = render size (pref handheld, DM_OPMODE 1 / 0; labels show the size for the picked picture shape)   next launch
//   picture shape   GearPages.pictureShape: 16:9 bars / stretched / widescreen (pref aspect, default 2; DM_TL2_WIDE=<W> from the display)
//   loading stretch widescreen loading screens stretched (pref tl2_stretch_loading, default off; DM_TL2_WIDE_LOADSTRETCH)            next launch
//   mods            Tl2Mods: the .MOD list, its own dialog with its own Save (pref tl2_mods; converted at the next start)
//   layout          D3PadView / Tl2Touch layouts tl2 / tl2_side / gamepad (pad d3_layout, applies when picked) + skill icons (tl2_icons);
//                   [DOS2] gamepad (the Switch pad, default) first, then tl2 / tl2_side
//   touch           Tl2Touch: diagonal correction, second-set modifier, the optional extras (pad tl2_iso / tl2_mod / tl2_tap / tl2_hold_walk /
//                   tl2_hero_y / tl2_aim)
//   safe mode       [DOS2] GearPages.safeMode: GPU safe mode off / auto / on (pref safe_mode, DM_SAFE_MODE; Mali / PowerVR only; docs/dos2/nr/SAFE-MODE.md)
//   start env       no row: DM_TL2_POINTER=1 (always on), the DOOM cvars unset, the non-Adreno text diagnostics
// A Diablo III build of this tree (DM_GAME=d3) gets D3's rows instead of the TL2 ones where they differ (touch / gamepad, D3 skill icons,
// hide sticks, walking to the finger, menu swipes).
// [DOS2] Divinity: Original Sin 2 has its own list (dos2Sections, owner 19.11): groups under headings (language / screen and resolution /
// frame rate / graphics quality / driver and safety / controls / other); the window is always the screen's own height and the 3D
// resolution is one row per Switch mode (Res3d: a fixed % or dynamic resolution).
final class Tl2Gear {
    private Tl2Gear() {}
    static final boolean TL2 = DmActivity.TL2;
    static final int[] FPS_LIMITS = {30, 60};   // above 60 is not offered: the game runs its frames at 60 like on the Switch (present interval 1)

    // The dialog, top to bottom (and the start environment in the same order)
    static List<GearSettings.Section> sections(DmActivity a, GearSettings g) {
        if (DmActivity.DOS2) return dos2Sections(a, g);
        Mode mode = new Mode(a);
        List<GearSettings.Section> l = new ArrayList<>();
        l.add(startEnv(a));
        if (DmActivity.BL2) l.add(GearSettings.page("图形（重启生效）", Bl2Gfx.page()));   // [BL2] 设置/图形：游戏自己的画质键（Bl2Gfx / Bl2Ini）
        if (DmActivity.BL2) l.add(GearSettings.page("作弊", Bl2Cheat.page()));   // [BL2] 作弊：游戏自带的 WillowCheatManager 命令（Bl2Cheat + hle_bl2_probe.c）
        l.add(GearPages.gameLanguage(DmActivity.D3_LANG_CODES, DmActivity.D3_LANG_LABELS, true));
        l.add(note(R.string.d3_game_lang_note));
        l.add(mode);
        l.add(GearPages.pictureShape(new String[] {g.str(R.string.d3_aspect_bars), g.str(R.string.d3_aspect_stretch), g.str(R.string.d3_aspect_wide)},
            DmActivity.D3_ASPECT_DEFAULT, g.str(R.string.d3_aspect_wide_note), a::applyAspectLayout, (s, v) -> aspectEnv(a, v), mode::relabel));
        if (!DmActivity.BL2) l.add(stretchLoading());   // [BL2] 加载画面拉伸是 DOS2/TL2 的，BL2 无效，不再显示
        // TL2 mods: their own row in the pause menu (DmActivity.portRows -> Tl2Gear.showMods), not a gear section
        if (!DmActivity.BL2) l.add(GearPages.sharpen());   // [BL2] 锐化已经放进「图形」页，这里不再重复
        l.add(GearPages.fpsLimit(FPS_LIMITS, 60)); l.add(note(R.string.d3_fps_note));
        if (a.drivers() != null) { l.add(GearPages.driver(a.drivers())); l.add(note(R.string.d3_driver_note)); }   // [BL2] 系统驱动 / 开源驱动（自己选 ZIP）
        l.add(GearPages.rumble());
        l.add(localPlay());
        l.add(GearPages.fpsCounter());
        l.add(new Layout());
        l.add(GearPages.padControls());
        if (DmActivity.BL2) l.add(GearPages.padAutoHide());   // [BL2] 触控 UI 自动隐藏 + 秒数
        l.add(GearPages.deadzone());
        l.add(TL2 ? new TouchRows() : new D3Touch());
        l.add(GearPages.gearButton());
        if (a.updateNotice() != null) l.add(GearPages.updates(a.updateNotice()));
        return l;
    }
    // [DOS2] the Divinity: Original Sin 2 dialog (owner 19.11: grouped by topic). Not here: TL2's loading-screen stretch (DOS2's widescreen has
    // no pillarboxed loading art, hle_dos2_wide.c), LAN play (TL2's Pia over ldn is not wired / tested for DOS2), the layout list (one layout:
    // the Switch pad, edited in its own editor), TL2 / D3 touch rows. The start env runs in this order too: dos2Window (DM_DOS2_RES,
    // DmActivity.dos2Base) before the picture shape (aspectEnv reads dos2Base).
    static List<GearSettings.Section> dos2Sections(DmActivity a, GearSettings g) {
        Mode mode = new Mode(a); Res3d res = new Res3d(a, mode);
        List<GearSettings.Section> l = new ArrayList<>();
        l.add(startEnv(a));
        l.add(group(R.string.dos2_group_lang));
        l.add(GearPages.gameLanguage(DmActivity.D3_LANG_CODES, DmActivity.D3_LANG_LABELS, true));
        l.add(note(R.string.d3_game_lang_note));
        l.add(group(R.string.dos2_group_screen));
        l.add(dos2Window());   // no row: the window height = the screen's own (before the rows that show the window size)
        l.add(mode);
        l.add(GearPages.pictureShape(new String[] {g.str(R.string.d3_aspect_bars), g.str(R.string.d3_aspect_stretch), g.str(R.string.d3_aspect_wide)},
            DmActivity.D3_ASPECT_DEFAULT, g.str(R.string.d3_aspect_wide_note), a::applyAspectLayout, (s, v) -> aspectEnv(a, v), v -> { mode.relabel(v); res.relabel(v); }));
        l.add(res);   // 3D resolution per Switch mode: a fixed % (DM_HACK_SCALE) or dynamic (DM_DOS2_DRS + its target / floor rows)
        l.add(GearPages.sharpen());
        l.add(dos2Fsr());   // FSR 1 upscaling of a 3D below 100 % (DM_HACK_FSR; on the hacks page until 19.11)
        l.add(group(R.string.dos2_group_fps));
        l.add(dos2Fps()); l.add(note(R.string.dos2_fps_note));   // 30 / 60 / 90 / 120 / uncapped (DM_DOS2_FPS)
        l.add(dos2Thermal());   // hle_dos2_quality.c thermal ladder
        l.add(group(R.string.dos2_group_quality));
        l.add(GearSettings.page(g.str(R.string.dos2_hacks), dos2Hacks()));   // N6 simplifications page (DM_HACK_*, docs/dos2/nr/NR-HACKS.md)
        SafeMode sm = a.safeMode();
        if (a.drivers() != null || (sm != null && sm.eligible())) l.add(group(R.string.dos2_group_driver));
        if (a.drivers() != null) { l.add(GearPages.driver(a.drivers())); l.add(note(R.string.d3_driver_note)); }
        l.add(GearPages.safeMode(a));   // [DOS2][safe-mode] off / auto / on, shown on Mali / PowerVR only (SafeMode.eligible); DM_SAFE_MODE
        l.add(group(R.string.dos2_group_controls));
        l.add(dos2Touch()); l.add(dos2Column()); l.add(dos2LStick()); l.add(dos2RStick());
        l.add(GearPages.padControls());
        l.add(GearPages.deadzone());
        l.add(GearPages.rumble());
        l.add(GearPages.gearButton());
        l.add(group(R.string.dos2_group_other));
        l.add(GearPages.fpsCounter());
        if (a.updateNotice() != null) l.add(GearPages.updates(a.updateNotice()));   // as in TL2 v0.1.7: the app version + "Check for new versions at start"
        return l;
    }
    // ---- [DOS2] a group heading (no row): bold, larger, a thin line above it
    static GearSettings.Section group(int res) {
        return new GearSettings.Section() {
            public void build(GearSettings g, LinearLayout box) {
                android.view.View line = new android.view.View(g.a); line.setBackgroundColor(0x40808080);
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, 2); lp.topMargin = 40; box.addView(line, lp);
                TextView t = g.heading(box, g.str(res)); t.setPadding(0, 16, 0, 4);
                t.setTypeface(android.graphics.Typeface.DEFAULT_BOLD); t.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 18);
            }
        };
    }

    // ---- [mp] local wireless play over the LAN (hle_ldn.c; pref "mp_lan", on by default -> DM_LDN): the game's own local multiplayer (Pia over
    // nn::ldn) between phones on one Wi-Fi / hotspot. No couch co-op row: TL2 on the Switch supports {Handheld, No1} only (main 0x13e9fc).
    // (frontend-common GearPages.localPlay is the same section with the shared texts; this one uses the port's resources until the gear texts sync.)
    static GearSettings.Section localPlay() {
        return new GearSettings.Section() {
            CheckBox lan;
            public void build(GearSettings g, LinearLayout box) {
                lan = g.check(box, g.when(g.str(R.string.d3_mp_lan), false), g.gamePrefs().getBoolean("mp_lan", true));
                g.note(box, g.str(R.string.tl2_mp_lan_note));
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { game.putBoolean("mp_lan", lan.isChecked()); }
            public void env(GearSettings g) throws ErrnoException { Os.setenv("DM_LDN", g.gamePrefs().getBoolean("mp_lan", true) ? "1" : "0", true); }
        };
    }

    // ---- a row-less note under the section before it
    static GearSettings.Section note(int res) {
        return new GearSettings.Section() { public void build(GearSettings g, LinearLayout box) { g.note(box, g.str(res)); } };
    }

    // ---- no row: the start environment that has no option
    static GearSettings.Section startEnv(DmActivity a) {
        return new GearSettings.Section() {
            public void build(GearSettings g, LinearLayout box) {}
            public void env(GearSettings g) throws ErrnoException {
                Os.unsetenv("DM_DOOM_DRS"); Os.unsetenv("DM_DOOM_RES");   // the DOOM cvars (rs_enable / rs_forceFraction*) do not apply
                if (TL2) Os.setenv("DM_TL2_POINTER", "1", true);   // hle_tl2_ui.c menu taps: always on (owner), no gear option; DM_TL2_UIDUMP only from dm/env
                // GPUs we could not test (no Adreno kernel driver: Mali, PowerVR, Xclipse): the existing text diagnostics, so one report shows what
                // the renderer did - the NVN calls of the first 120 frames, a per-pass GPU profile every 600 frames for the first ~2 minutes. Text
                // only; dm/env still overrides each value. Not DM_NVN_TRACE (its wrapper crashed the host's slot calls at boot, Mali 0.2.1).
                if (!VkDrivers.kgsl()) {
                    Os.setenv("DM_NVN_FRAMES", "120", false);
                    Os.setenv("DM_GFX_PASS_PROF", "60 600 7200", false);
                    a.crumb("diagnostics on (not an Adreno GPU: " + VkDrivers.hardwareSummary() + "): NVN calls of 120 frames, pass profile for ~2 min");
                }
            }
        };
    }

    // ---- the Switch operation mode = the game's render size (hle_oe.c GetOperationMode / GetPerformanceMode): docked 1920x1080 (D3 1600x900),
    // handheld 1280x720; the labels show the size the next launch renders at for the picked picture shape (widescreen: the screen's aspect).
    // Next launch here (DM_OPMODE); the pause menu's mode row switches it live (DmActivity.setDocked, the same pref).
    // [DOS2] the labels show the window (the interface is drawn at it); each mode has its own 3D resolution row (Res3d follows the pick).
    static final class Mode implements GearSettings.Section {
        final DmActivity a; RadioGroup r; GearSettings g; Runnable changed;   // changed: the DRS row's refresh when the pick changes
        Mode(DmActivity a) { this.a = a; }
        boolean pickedHandheld() { return r != null ? GearSettings.picked(r) == 1 : g != null && g.gamePrefs().getBoolean("handheld", false); }
        public void build(GearSettings g, LinearLayout box) {
            this.g = g; SharedPreferences p = g.gamePrefs();
            g.heading(box, g.when(g.str(DmActivity.DOS2 ? R.string.dos2_mode : R.string.d3_mode), false));
            r = g.radios(box, new String[] {"", ""}, p.getBoolean("handheld", false) ? 1 : 0, false);
            r.setOnCheckedChangeListener((grp, id) -> { if (changed != null) changed.run(); });
            relabel(p.getInt("aspect", DmActivity.D3_ASPECT_DEFAULT));
            g.note(box, g.str(DmActivity.DOS2 ? R.string.dos2_mode_note : R.string.d3_mode_note));
        }
        void relabel(int aspect) {
            if (r == null || g == null) return;
            int[] sc = a.screenSize(), dk = DmActivity.d3RenderSize(aspect == 2, false, sc[0], sc[1]), hh = DmActivity.d3RenderSize(aspect == 2, true, sc[0], sc[1]);
            ((RadioButton) r.getChildAt(0)).setText(g.str(R.string.d3_mode_docked, dk[0] + "×" + dk[1]));
            ((RadioButton) r.getChildAt(1)).setText(g.str(DmActivity.DOS2 ? R.string.dos2_mode_handheld : R.string.d3_mode_handheld, hh[0] + "×" + hh[1]));
        }
        public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { game.putBoolean("handheld", GearSettings.picked(r) == 1); }
        public void env(GearSettings g) throws ErrnoException {
            a.startedHandheld = g.gamePrefs().getBoolean("handheld", false);
            Os.setenv("DM_OPMODE", a.startedHandheld ? "0" : "1", true);   // dm/env still wins (it is applied after this)
        }
    }
    // ---- picture shape 2 = widescreen (next launch): DOS2 hle_dos2_wide.c DM_DOS2_WIDE=<W>x<H> (Hor+; narrower screens 1600 x H, letterboxed
    // by the game itself); TL2 hle_tl2_wide.c W x 1080 Hor+, the width from the display, not the SurfaceView (the view
    // may still be laid out 16:9 before startedAspect is known, or portrait when started with the screen off); D3 hle_d3.c DM_D3_WIDE
    static void aspectEnv(DmActivity a, int v) throws ErrnoException {
        a.startedAspect = v;
        if (DmActivity.DOS2) {   // [DOS2] hle_dos2_wide.c: the docked window in the screen's shape (WxH, from the display: long side first), 0 = the Switch's 1600x900
            int[] sc = a.screenSize(), d = v == 2 ? DmActivity.dos2WideSize(sc[0], sc[1]) : DmActivity.dos2Base == 900 ? null : new int[] {1280, 720};
            Os.setenv("DM_DOS2_WIDE", d != null ? d[0] + "x" + d[1] : "0", true);
        } else if (TL2) {
            int[] sc = a.screenSize(); long ww = sc[1] > 0 ? Math.round(1080.0 * sc[0] / sc[1] / 16) * 16 : 0;
            Os.setenv("DM_TL2_WIDE", v != 2 ? "0" : ww > 1920 ? Long.toString(ww) : "1", true);
        } else if (v == 2) Os.setenv("DM_D3_WIDE", "1", true); else Os.unsetenv("DM_D3_WIDE");
        if (DmActivity.BL2) Os.setenv("DM_BL2_WIDE", v == 2 ? "1" : "0", true);   // [BL2] 画面形状=宽屏就是真宽屏（原生补丁），其余形状关闭
    }
    // ---- widescreen loading screens: TL2 pillarboxed 16:9 by default, stretched when asked (hle_tl2_wide.c); D3 the other way round (ls_present_crop)
    // ---- [DOS2] the window height (no row since 19.11): always the screen's own (dos2NativeRes) -> DM_DOS2_RES and DmActivity.dos2Base (the
    // mode labels, DM_DOS2_WIDE in aspectEnv). Until 19.11 a row 720 / 900 / 1080 (pref "dos2_res", the older checkbox "dos2_res_900") set
    // the whole window, interface included; now the interface stays at the screen's resolution and Res3d scales only the 3D. The old pref is
    // still read by Res3d to carry a player's lower window over as a 3D %.
    static int dos2NativeRes(android.content.Context c) {   // the largest of 720 / 900 / 1080 that the screen's short side holds (current display mode)
        try {
            android.util.DisplayMetrics m = new android.util.DisplayMetrics();
            ((android.view.WindowManager) c.getSystemService(android.content.Context.WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(m);
            int s = Math.min(m.widthPixels, m.heightPixels);
            return s >= 1080 ? 1080 : s >= 900 ? 900 : 720;
        } catch (RuntimeException e) { return 720; }
    }
    static int dos2OldRes(android.content.Context c, SharedPreferences p) {   // the pre-19.11 window height: "dos2_res", else "dos2_res_900", else native
        int r = p.getInt("dos2_res", p.getBoolean("dos2_res_900", false) ? 900 : dos2NativeRes(c));
        return r == 900 || r == 1080 ? r : 720;
    }
    static GearSettings.Section dos2Window() {
        return new GearSettings.Section() {
            public void build(GearSettings g, LinearLayout box) { DmActivity.dos2Base = dos2NativeRes(g.a); }
            public void env(GearSettings g) throws ErrnoException { DmActivity.dos2Base = dos2NativeRes(g.a); Os.setenv("DM_DOS2_RES", Integer.toString(DmActivity.dos2Base), true); }
        };
    }
    // ---- [DOS2] frame rate limit (next launch; docs/dos2/DOS2_PORT.md "Лимит кадров 90 / 120 / без ограничения"). Pref "fps_limit" as the
    // shared GearPages.fpsLimit row it replaces for DOS2 (a saved 30 / 60 stays), plus 90 / 120 / 0 = uncapped. 30 / 60 set DM_PRESENT_MAX_HZ
    // exactly as before (default 60: unchanged); 90 / 120 / uncapped set DM_DOS2_FPS (hle_nvn.c present_auto_hz -> nvn_pace.h
    // nvn_pace_target_hz). 90 / 120 are offered only when the display has a mode at a multiple of them (GearDisplay.modeFor); uncapped always
    // (no host pacing; the FIFO swapchain holds it to the refresh). dm/env DM_DOS2_FPS wins over the row (the env file is read later).
    static final int[] DOS2_FPS = {30, 60, 90, 120, 0};
    static boolean dos2FpsOffered(android.app.Activity a, int f) { return f == 0 || GearDisplay.fpsLimitAvailable(a, f); }
    // The saved choice, lowered to the highest offered one at or under it when its display mode is gone (another screen / refresh setting)
    static int dos2FpsPref(android.app.Activity a, SharedPreferences p) {
        int want = p.getInt("fps_limit", 60);
        if (want == 0) return 0;
        if (want <= 60) return want == 30 ? 30 : 60;
        int got = 60; for (int f : DOS2_FPS) if (f > got && f <= want && dos2FpsOffered(a, f)) got = f;
        return got;
    }
    static GearSettings.Section dos2Fps() {
        return new GearSettings.Section() {
            final ArrayList<Integer> fps = new ArrayList<>(); RadioGroup r;
            public void build(GearSettings g, LinearLayout box) {
                fps.clear(); for (int f : DOS2_FPS) if (dos2FpsOffered(g.a, f)) fps.add(f);
                String[] labels = new String[fps.size()]; int cur = dos2FpsPref(g.a, g.gamePrefs()), at = 1;
                for (int i = 0; i < labels.length; i++) { int f = fps.get(i); labels[i] = f == 0 ? g.str(R.string.dos2_fps_uncapped) : String.valueOf(f); if (f == cur) at = i; }
                g.heading(box, g.whenKey("gear_fps_limit", false));
                r = g.radios(box, labels, at, true);
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { if (!fps.isEmpty()) game.putInt("fps_limit", fps.get(GearSettings.picked(r))); }
            public void env(GearSettings g) throws ErrnoException {
                int f = dos2FpsPref(g.a, g.gamePrefs());
                if (f == 30 || f == 60) { Os.setenv("DM_PRESENT_MAX_HZ", String.valueOf(f), true); Os.unsetenv("DM_DOS2_FPS"); }
                else { Os.unsetenv("DM_PRESENT_MAX_HZ"); Os.setenv("DM_DOS2_FPS", String.valueOf(f), true); }
            }
        };
    }
    // After nativeStart (dm/env is in the environment by then): the effective target, one boot.log line with it and the display modes the phone
    // offers, and for 90 / 120 / uncapped the window's display mode (the lowest mode at a multiple of the target, the same resolution first;
    // uncapped: the fastest mode at the current resolution). 30 / 60 request nothing (as before: the surface's 120 Hz vote and the system decide).
    // [DOS2] owner 18.11: memory-bound passes slow ~1.5x within ~30 s of play (DDR / bus clock drop suspected). DM_SUSTAINED=1 asks Android for
    // sustained performance mode (Window.setSustainedPerformanceMode: a clock level the device can hold, no bursts); off by default until a phone
    // run shows it helps. The boot line says whether the device supports it (HyperOS may ignore it).
    static void dos2SustainedApply(DmActivity a) {
        String e = Os.getenv("DM_SUSTAINED"); if (e == null || !e.trim().equals("1")) return;
        android.os.PowerManager pm = (android.os.PowerManager) a.getSystemService(android.content.Context.POWER_SERVICE);
        boolean sup = pm != null && pm.isSustainedPerformanceModeSupported();
        if (sup) a.getWindow().setSustainedPerformanceMode(true);
        a.crumb("sustained performance mode (DM_SUSTAINED=1): " + (sup ? "requested" : "not supported by this device"));
    }
    static void dos2FpsApply(DmActivity a) {
        String e = Os.getenv("DM_DOS2_FPS"), cap = Os.getenv("DM_PRESENT_MAX_HZ");
        int t = -1; if (e != null) for (int f : DOS2_FPS) if (e.trim().equals(String.valueOf(f))) t = f;
        String from = t >= 0 ? "DM_DOS2_FPS" : "DM_PRESENT_MAX_HZ " + (cap == null ? "unset" : cap);
        if (t < 0) t = "30".equals(cap) ? 30 : 60;
        android.view.Display d = GearDisplay.display(a);
        StringBuilder modes = new StringBuilder(); android.view.Display.Mode cur = d == null ? null : d.getMode(), pick = null;
        if (d != null) for (android.view.Display.Mode m : d.getSupportedModes()) {
            modes.append(' ').append(m.getModeId()).append('@').append(String.format(java.util.Locale.ROOT, "%.2f", m.getRefreshRate())).append('/').append(m.getPhysicalWidth()).append('x').append(m.getPhysicalHeight());
            if (t == 0 && cur != null && m.getPhysicalWidth() == cur.getPhysicalWidth() && m.getPhysicalHeight() == cur.getPhysicalHeight()
                && (pick == null || m.getRefreshRate() > pick.getRefreshRate())) pick = m;
        }
        if (t > 60) pick = GearDisplay.modeFor(a, t);
        // [DOS2] owner 18.11: with a 30 / 45 / 60 limit also ask for the FASTEST mode at a multiple of the limit (120 Hz on the Mi 14, not the
        // 60 Hz HyperOS falls to for a 60 fps window): a frame that misses its slot is then shown on the next 8.3 ms vsync (25 ms = 40 fps)
        // instead of the next 16.7 ms one (33 ms = 30 fps). Pacing stays at the limit. DM_DOS2_HIGHHZ=0 turns it off (request nothing, as before).
        String hh = Os.getenv("DM_DOS2_HIGHHZ"); boolean high = hh == null || !hh.trim().equals("0");
        if (high && t > 0 && t <= 60 && d != null && cur != null) for (android.view.Display.Mode m : d.getSupportedModes()) {
            if (m.getPhysicalWidth() != cur.getPhysicalWidth() || m.getPhysicalHeight() != cur.getPhysicalHeight()) continue;
            double k = m.getRefreshRate() / t; if (Math.abs(k - Math.rint(k)) > 0.02 || Math.rint(k) < 1) continue;
            if (pick == null || m.getRefreshRate() > pick.getRefreshRate()) pick = m;
        }
        boolean asks = t > 60 || t == 0 || (high && t > 0 && t <= 60);
        String req = asks ? (pick == null ? "none (no mode at a multiple: paced as is)" : pick.getModeId() + " @ " + pick.getRefreshRate() + " Hz") : "none (30 / 60, DM_DOS2_HIGHHZ=0)";
        if (pick != null && asks) {
            WindowManager.LayoutParams lp = a.getWindow().getAttributes(); lp.preferredDisplayModeId = pick.getModeId(); a.getWindow().setAttributes(lp);
        }
        a.crumb("fps target " + (t == 0 ? "uncapped" : String.valueOf(t)) + " (" + from + "): display modes" + (d == null ? " unknown" : modes.toString())
            + ", current " + (cur == null ? "?" : cur.getModeId() + " @ " + cur.getRefreshRate() + " Hz") + ", requested " + req);
    }
    // ---- [DOS2] 3D resolution per Switch mode (owner 19.11; docs/dos2/nr/DRS-MODE.md, docs/dos2/nr/NR-HACKS.md; hle_dos2_quality.c). One
    // row per mode: "Dynamic" or a fixed 100 / 83 / 75 / 67 / 50 % of the window per side; the labels show the lines of that mode's window.
    // Only the 3D is scaled (the game's DRS object); the interface stays at the window = the screen's resolution (dos2Window).
    //   fixed p : DM_DOS2_DRS=off + DM_HACK_SCALE=<p> (100 = the full window; native: min = max = p, 100 ms target)    next launch
    //   dynamic : DM_DOS2_DRS=<floor>:100 + DM_DOS2_DRS_TARGET_MS (1000 / fps x 0.95) + DM_HACK_SCALE=100 (so a hack tier never adds a
    //             scale); target fps {30, 45, 60, 75, 90, 120} live (dos2DrsLive -> nativeSetDos2Drs), floor {85, 75, 60, 50} % next launch
    // Prefs: dos2_res3d_dk / _hh = 0 dynamic, else the %; dos2_drs_fps_dk / _hh (0 = the default target: the frame-rate limit when it is a
    // target, else 60), dos2_drs_min_dk / _hh (default 75). dos2_drs_dk / _hh are still written (1 dynamic / 0 fixed) for older builds.
    // No dos2_res3d_* yet (saved before 19.11): the mode's old DRS pick (dos2_drs_dk / _hh -1 = the mode's default: Handheld on, Docked off;
    // the pre-17.11 dos2_drs "on" = on in both) -> dynamic; else the % whose window lines are closest to the old window (dos2OldRes: 720 on a
    // 1080 screen -> 67 %, 900 -> 83 %, 1080 or no pref = the screen's own -> 100 %). An old hack tier's SCALE is not carried over.
    // When it applies: the start env for the mode the game starts in; on Save and on the pause menu's live mode switch (DmActivity.setDocked
    // -> dos2DrsLive) the running game gets the mode's target (dynamic) or the 100 ms target (fixed: steps up to its ceiling). dm/env still wins.
    static final int[] RES3D = {0, 100, 83, 75, 67, 50};           // 0 = dynamic; else % of the window per side
    static final int[] DOS2_DRS_FPS = {30, 45, 60, 75, 90, 120};   // owner 19.11: targets
    static final int[] DOS2_DRS_MINS = {85, 75, 60, 50};           // owner 19.11: the lowest 3D size allowed, % of the window per side
    static final int DOS2_DRS_FLOOR = 75;   // % of the window: the game's own minimum (SetSize fmov #0.75)
    static int dos2RunFps = -1;             // the frame-rate limit the running game started with (0 = no limit); -1 before the start env
    static int dos2DrsDefaultFps(int limit) { for (int f : DOS2_DRS_FPS) if (f == limit) return limit; return 60; }   // the limit when it is a target, else 60
    static String dos2DrsMinKey(boolean hh) { return hh ? "dos2_drs_min_hh" : "dos2_drs_min_dk"; }
    static int dos2DrsMin(SharedPreferences p, boolean hh) { int v = p.getInt(dos2DrsMinKey(hh), DOS2_DRS_FLOOR); return v >= 50 && v < 100 ? v : DOS2_DRS_FLOOR; }
    static String dos2DrsKey(boolean hh) { return hh ? "dos2_drs_hh" : "dos2_drs_dk"; }
    static String dos2DrsFpsKey(boolean hh) { return hh ? "dos2_drs_fps_hh" : "dos2_drs_fps_dk"; }
    static String res3dKey(boolean hh) { return hh ? "dos2_res3d_hh" : "dos2_res3d_dk"; }
    // The window height of one mode for a base height and a picture shape (DmActivity.dos2Size: what hle_dos2_wide.c builds)
    static int dos2WindowH(android.app.Activity a, int base, int aspect, boolean hh) {
        int[] sc = GearDisplay.screenSize(a); return DmActivity.dos2Size(base, aspect == 2, hh, sc[0], sc[1])[1];
    }
    // The 3D resolution of one mode: 0 = dynamic, else the % (from the pre-19.11 prefs while the player has not saved this row)
    static int dos2Res3d(android.app.Activity a, SharedPreferences p, boolean hh) {
        if (p.contains(res3dKey(hh))) { int v = p.getInt(res3dKey(hh), -1); if (GearSettings.indexOf(RES3D, v, -1) >= 0) return v; }
        boolean oldOn = p.getBoolean("dos2_drs", false);   // the single row before 17.11
        int o = p.contains(dos2DrsKey(hh)) ? p.getInt(dos2DrsKey(hh), -1) : oldOn ? 1 : -1;
        if (o < 0 ? hh : o == 1) return 0;
        int aspect = p.getInt("aspect", DmActivity.D3_ASPECT_DEFAULT);
        double was = dos2WindowH(a, dos2OldRes(a, p), aspect, hh), now = dos2WindowH(a, dos2NativeRes(a), aspect, hh);
        int best = 1; for (int i = 2; i < RES3D.length; i++) if (Math.abs(RES3D[i] * now - 100 * was) < Math.abs(RES3D[best] * now - 100 * was)) best = i;
        return RES3D[best];
    }
    // The effective {dynamic 0/1, target fps, floor %} of one mode for a frame-rate limit
    static int[] dos2DrsFor(android.app.Activity a, SharedPreferences p, boolean hh, int limit) {
        boolean oldOn = p.getBoolean("dos2_drs", false);
        int f = p.contains(dos2DrsFpsKey(hh)) ? p.getInt(dos2DrsFpsKey(hh), 0) : oldOn ? p.getInt("dos2_drs_fps", 60) : 0;
        return new int[] {dos2Res3d(a, p, hh) == 0 ? 1 : 0, f > 0 ? f : dos2DrsDefaultFps(limit), dos2DrsMin(p, hh)};
    }
    static String dos2DrsText(int[] d, int res, boolean hh) {
        return (hh ? "handheld" : "docked") + ": 3D " + (d[0] == 1 ? "dynamic, floor " + d[2] + " %, target " + d[1] + " fps" : "fixed " + res + " % of the window");
    }
    // Live: the DRS of mode hh for the running game (its start limit); false = not applied (no library / no target copy: next launch then)
    static boolean dos2DrsLive(DmActivity a, boolean hh, String why) {
        SharedPreferences p = a.gamePrefs();
        int[] d = dos2DrsFor(a, p, hh, dos2RunFps >= 0 ? dos2RunFps : dos2FpsPref(a, p));
        boolean ok = false;
        try { ok = DmActivity.nativeSetDos2Drs(d[0] == 1, d[1]); } catch (Throwable t) { /* no library yet */ }
        a.crumb("3D resolution " + dos2DrsText(d, dos2Res3d(a, p, hh), hh) + " (" + why + ")"
            + (ok ? ", target live (a new fixed % / floor, fixed <-> dynamic: next launch)" : ", not live: next launch"));
        return ok;
    }
    static final class Res3d implements GearSettings.Section {
        final DmActivity a; final Mode mode; GearSettings g; int lim, aspect; boolean quiet, shownHh;
        TextView head; RadioGroup res, rfps, rmin; LinearLayout drs; int[] opts;
        final int[] pick = new int[2], fps = new int[2], mins = new int[2];   // [0] docked, [1] handheld: what the rows hold now
        Res3d(DmActivity a, Mode mode) { this.a = a; this.mode = mode; }
        public void build(GearSettings g, LinearLayout box) {
            this.g = g; SharedPreferences p = g.gamePrefs(); lim = dos2FpsPref(g.a, p); aspect = p.getInt("aspect", DmActivity.D3_ASPECT_DEFAULT);
            java.util.TreeSet<Integer> o = new java.util.TreeSet<>(); for (int f : DOS2_DRS_FPS) o.add(f);
            for (int m = 0; m < 2; m++) {
                int[] d = dos2DrsFor(g.a, p, m == 1, lim); pick[m] = dos2Res3d(g.a, p, m == 1); fps[m] = d[1]; mins[m] = d[2]; o.add(d[1]);
            }
            opts = new int[o.size()]; String[] labels = new String[opts.length]; int i = 0;
            for (int f : o) { opts[i] = f; labels[i++] = String.valueOf(f); }
            head = g.heading(box, "");
            String[] blank = new String[RES3D.length]; java.util.Arrays.fill(blank, "");
            res = g.radios(box, blank, 0, false);
            drs = g.vbox(box);   // the dynamic resolution's own rows: shown only while "Dynamic" is picked
            g.note(drs, g.when(g.str(R.string.dos2_drs_target), true));
            rfps = g.radios(drs, labels, 0, true);
            g.note(drs, g.when(g.str(R.string.dos2_drs_min), false));   // the floor is patched into the game at start
            String[] ml = new String[DOS2_DRS_MINS.length]; java.util.Arrays.fill(ml, "");
            rmin = g.radios(drs, ml, 0, true);
            g.note(box, g.str(R.string.dos2_res3d_note));
            show(mode.pickedHandheld());
            res.setOnCheckedChangeListener((grp, id) -> {
                if (quiet) return;
                int m = shownHh ? 1 : 0, v = RES3D[GearSettings.picked(res)]; boolean was = pick[m] == 0; pick[m] = v;
                drs.setVisibility(v == 0 ? android.view.View.VISIBLE : android.view.View.GONE);
                if (v == 0 && !was) explainDynamic(mins[m]);   // a tap on "Dynamic" (not the dialog's first show, not a mode switch)
            });
            rfps.setOnCheckedChangeListener((grp, id) -> { if (!quiet) fps[shownHh ? 1 : 0] = opts[GearSettings.picked(rfps)]; });
            rmin.setOnCheckedChangeListener((grp, id) -> { if (!quiet) mins[shownHh ? 1 : 0] = DOS2_DRS_MINS[GearSettings.picked(rmin)]; });
            mode.changed = () -> show(mode.pickedHandheld());
        }
        void explainDynamic(int floor) {
            new AlertDialog.Builder(g.a).setTitle(g.str(R.string.dos2_res3d_drs_title)).setMessage(g.str(R.string.dos2_res3d_drs_text, floor))
                .setPositiveButton(g.str(R.string.dos2_res3d_drs_ok), null).show();
        }
        void relabel(int aspect) { this.aspect = aspect; if (res != null) labels(); }   // the picture shape picked in the open dialog
        void labels() {   // "100 % (1080p)": the lines of the shown mode's window at each %
            int h = dos2WindowH(g.a, dos2NativeRes(g.a), aspect, shownHh);
            for (int i = 0; i < RES3D.length; i++)
                ((RadioButton) res.getChildAt(i)).setText(i == 0 ? g.str(R.string.dos2_res3d_drs) : g.str(R.string.dos2_res3d_fixed, RES3D[i], Math.round(h * RES3D[i] / 100f)));
            for (int k = 0; k < DOS2_DRS_MINS.length; k++)
                ((RadioButton) rmin.getChildAt(k)).setText(g.str(R.string.dos2_res3d_fixed, DOS2_DRS_MINS[k], Math.round(h * DOS2_DRS_MINS[k] / 100f)));
        }
        void show(boolean hh) {   // the rows for one mode (quiet: the listeners keep the other mode's values)
            quiet = true; shownHh = hh; int m = hh ? 1 : 0;
            head.setText(g.when(g.str(hh ? R.string.dos2_res3d_for_handheld : R.string.dos2_res3d_for_docked), false));
            labels();
            res.check(res.getChildAt(GearSettings.indexOf(RES3D, pick[m], 1)).getId());
            int at = 0; for (int i = 0; i < opts.length; i++) if (opts[i] == fps[m]) at = i;
            rfps.check(rfps.getChildAt(at).getId());
            rmin.check(rmin.getChildAt(GearSettings.indexOf(DOS2_DRS_MINS, mins[m], 1)).getId());
            drs.setVisibility(pick[m] == 0 ? android.view.View.VISIBLE : android.view.View.GONE);
            quiet = false;
        }
        public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) {
            for (int m = 0; m < 2; m++) {   // a target equal to the default is kept as the default (it follows the frame-rate limit)
                boolean hh = m == 1;
                game.putInt(res3dKey(hh), pick[m]);
                game.putInt(dos2DrsKey(hh), pick[m] == 0 ? 1 : 0);
                game.putInt(dos2DrsFpsKey(hh), fps[m] == dos2DrsDefaultFps(lim) ? 0 : fps[m]);
                game.putInt(dos2DrsMinKey(hh), mins[m]);
            }
        }
        // live, no restart (the running game's DRS target is our copy), for the mode it runs in; a failed live call applies at the next launch
        public void after(GearSettings g) { dos2DrsLive(a, a.startedHandheld, "gear"); }
        public void env(GearSettings g) throws ErrnoException {
            SharedPreferences p = g.gamePrefs(); boolean hh = p.getBoolean("handheld", false);
            dos2RunFps = dos2FpsPref(g.a, p);
            int v = dos2Res3d(g.a, p, hh); int[] d = dos2DrsFor(g.a, p, hh, dos2RunFps);
            if (v != 0) {
                Os.setenv("DM_DOS2_DRS", "off", true); Os.unsetenv("DM_DOS2_DRS_TARGET_MS");
                Os.setenv("DM_HACK_SCALE", Integer.toString(v), true);   // 100 = off (nr_hacks.h: >= 100 -> 0)
            } else {
                Os.setenv("DM_DOS2_DRS", d[2] + ":100", true);
                Os.setenv("DM_DOS2_DRS_TARGET_MS", String.format(java.util.Locale.ROOT, "%.2f", 1000.0 / d[1] * 0.95), true);
                Os.setenv("DM_HACK_SCALE", "100", true);   // explicit: a hack tier's SCALE never lowers the DRS ceiling
            }
            a.crumb("3D resolution at start, " + dos2DrsText(d, v, hh));
        }
    }
    // ---- [DOS2] FSR 1 EASU upscaling in the stretch pass instead of the console's bilinear stretch (DM_HACK_FSR, nr_hacks.h; next launch).
    // Only does something while the 3D is below 100 % (a fixed % or dynamic). Pref "dos2_fsr"; before 19.11 the hacks page's FSR row: tiers
    // 1-3 had it on, Custom its own "hack_fsr". Always exported explicitly (1 / 0), so a hack tier never decides it.
    static boolean dos2FsrPref(SharedPreferences p) {
        if (p.contains("dos2_fsr")) return p.getBoolean("dos2_fsr", false);
        int t = p.getInt("hack_tier", 0);
        return (t >= 1 && t <= 3) || (t == 4 && p.getInt("hack_fsr", HACK_TIERS[2][1]) == 1);
    }
    static GearSettings.Section dos2Fsr() {
        return new GearSettings.Section() {
            CheckBox c;
            public void build(GearSettings g, LinearLayout box) { c = g.check(box, g.when(g.str(R.string.dos2_fsr), false), dos2FsrPref(g.gamePrefs())); }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { game.putBoolean("dos2_fsr", c.isChecked()); }
            public void env(GearSettings g) throws ErrnoException { Os.setenv("DM_HACK_FSR", dos2FsrPref(g.gamePrefs()) ? "1" : "0", true); }
        };
    }
    // ---- [DOS2] N6 speed hacks (next launch; dm/gfx/nr/nr_hacks.h, docs/dos2/nr/NR-HACKS.md). Pref "hack_tier": 0 off (nothing is set, so an
    // env-file DM_HACK_TIER / DM_HACK_* still works), 1 light / 2 medium / 3 max (the table below = nrh_tier_table, source_structure_test.py
    // compares them), 4 custom (prefs hack_<name>). A tier sets DM_HACK_TIER only (the native takes the table and its per-GPU rule,
    // xbg_hack_fsr_tier_default); custom sets its DM_HACK_* explicitly (explicit values win in the native). Round 2: LOD distances, light cap.
    // Rows: NOBLOOM, NOAA, SHADOWS, SHPCF, SHFAR, TEXBIAS (1/100 mip), ANISO, LOD, LIGHTS. [DOS2] 19.11: the SCALE and FSR columns stay in the
    // table (= nrh_tier_table) but the page neither shows nor exports them: the main page's Res3d / dos2Fsr always set DM_HACK_SCALE and
    // DM_HACK_FSR explicitly, which win over the tier.
    static final String[] HACK_NAMES = {"SCALE", "FSR", "NOBLOOM", "NOAA", "SHADOWS", "SHPCF", "SHFAR", "TEXBIAS", "ANISO", "LOD", "LIGHTS"};
    static final int[][] HACK_TIERS = {
        {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
        {85, 1, 0, 0, 0, 2, 0, 0, 0, 90, 0},
        {85, 1, 0, 0, 1, 2, 0, 50, 4, 80, 4},
        {75, 1, 1, 0, 1, 2, 1, 100, 2, 70, 2},
    };
    static final int HACK_FIRST = 2;   // the first column the page shows (0 SCALE, 1 FSR: the main page's rows)
    static final int[] HACK_PCF = {0, 2, 3}, HACK_BIAS = {0, 50, 100}, HACK_ANISO = {0, 4, 2, 1}, HACK_LOD = {0, 90, 80, 70}, HACK_LIGHTS = {0, 4, 2};
    static boolean dos2HackSame(int[] a, int[] b) { for (int i = HACK_FIRST; i < a.length; i++) if (a[i] != b[i]) return false; return true; }
    static int[] dos2HackValues(SharedPreferences p) {
        int t = p.getInt("hack_tier", 0);
        if (t >= 0 && t <= 3) return HACK_TIERS[t].clone();
        int[] v = new int[HACK_NAMES.length];
        for (int i = 0; i < v.length; i++) v[i] = p.getInt("hack_" + HACK_NAMES[i].toLowerCase(java.util.Locale.ROOT), HACK_TIERS[2][i]);
        return v;
    }
    static GearSettings.Section dos2Hacks() {
        return new GearSettings.Section() {
            RadioGroup tier, pcf, bias, aniso, lod, lights; CheckBox nobloom, noaa, shadows, shfar; boolean applying;
            void pick(RadioGroup r, int i) { r.check((Integer) r.getTag() + i); }
            void show(int[] v) {
                applying = true;
                nobloom.setChecked(v[2] == 1); noaa.setChecked(v[3] == 1);
                shadows.setChecked(v[4] == 1); pick(pcf, GearSettings.indexOf(HACK_PCF, v[5], 0)); shfar.setChecked(v[6] == 1);
                pick(bias, GearSettings.indexOf(HACK_BIAS, v[7], 0)); pick(aniso, GearSettings.indexOf(HACK_ANISO, v[8], 0));
                pick(lod, GearSettings.indexOf(HACK_LOD, v[9], 0)); pick(lights, GearSettings.indexOf(HACK_LIGHTS, v[10], 0));
                applying = false;
            }
            int[] read() {
                return new int[] {0, 0, nobloom.isChecked() ? 1 : 0, noaa.isChecked() ? 1 : 0,
                    shadows.isChecked() ? 1 : 0, HACK_PCF[GearSettings.picked(pcf)], shfar.isChecked() ? 1 : 0, HACK_BIAS[GearSettings.picked(bias)],
                    HACK_ANISO[GearSettings.picked(aniso)], HACK_LOD[GearSettings.picked(lod)], HACK_LIGHTS[GearSettings.picked(lights)]};
            }
            void custom() { if (!applying) { applying = true; pick(tier, 4); applying = false; } }
            public void build(GearSettings g, LinearLayout box) {
                SharedPreferences p = g.gamePrefs();
                g.note(box, g.str(R.string.dos2_hacks_intro));
                g.heading(box, g.when(g.str(R.string.dos2_hacks_tier), false));
                tier = g.radios(box, new String[] {g.str(R.string.dos2_hacks_off), g.str(R.string.dos2_hacks_light), g.str(R.string.dos2_hacks_medium),
                    g.str(R.string.dos2_hacks_max), g.str(R.string.dos2_hacks_custom)}, Math.max(0, Math.min(4, p.getInt("hack_tier", 0))), true);
                g.note(box, g.str(R.string.dos2_hacks_tier_note));
                nobloom = g.check(box, g.when(g.str(R.string.dos2_hack_nobloom), false), false);
                noaa = g.check(box, g.when(g.str(R.string.dos2_hack_noaa), false), false);
                shadows = g.check(box, g.when(g.str(R.string.dos2_hack_shadows), false), false);
                g.heading(box, g.when(g.str(R.string.dos2_hack_shpcf), false));
                pcf = g.radios(box, new String[] {g.str(R.string.dos2_hack_shpcf_game), g.str(R.string.dos2_hack_shpcf_mobile), g.str(R.string.dos2_hack_shpcf_dref)}, 0, true);
                shfar = g.check(box, g.when(g.str(R.string.dos2_hack_shfar), false), false);
                g.heading(box, g.when(g.str(R.string.dos2_hack_texbias), false));
                bias = g.radios(box, new String[] {g.str(R.string.dos2_hack_texbias_0), g.str(R.string.dos2_hack_texbias_1), g.str(R.string.dos2_hack_texbias_2)}, 0, true);
                g.heading(box, g.when(g.str(R.string.dos2_hack_aniso), false));
                aniso = g.radios(box, new String[] {g.str(R.string.dos2_hack_aniso_game), "4x", "2x", "1x"}, 0, true);
                g.heading(box, g.when(g.str(R.string.dos2_hack_lod), false));
                lod = g.radios(box, new String[] {g.str(R.string.dos2_hack_aniso_game), "90 %", "80 %", "70 %"}, 0, true);
                g.heading(box, g.when(g.str(R.string.dos2_hack_lights), false));
                lights = g.radios(box, new String[] {g.str(R.string.dos2_hack_lights_all), "4", "2"}, 0, true);
                show(dos2HackValues(p));
                tier.setOnCheckedChangeListener((r, id) -> { if (applying) return; int t = GearSettings.picked(tier); if (t <= 3) show(HACK_TIERS[t]); });
                for (RadioGroup r : new RadioGroup[] {pcf, bias, aniso, lod, lights}) r.setOnCheckedChangeListener((rr, id) -> custom());
                for (CheckBox c : new CheckBox[] {nobloom, noaa, shadows, shfar}) c.setOnCheckedChangeListener((cc, on) -> custom());
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) {
                int t = GearSettings.picked(tier); int[] v = read();
                for (int k = 0; k <= 3; k++) if (t == 4 && dos2HackSame(v, HACK_TIERS[k])) t = k;   // a custom pick equal to a tier is that tier
                game.putInt("hack_tier", t);
                if (t == 4) for (int i = HACK_FIRST; i < v.length; i++) game.putInt("hack_" + HACK_NAMES[i].toLowerCase(java.util.Locale.ROOT), v[i]);
            }
            public void env(GearSettings g) throws ErrnoException {
                SharedPreferences p = g.gamePrefs(); int t = p.getInt("hack_tier", 0);
                if (t <= 0 || t > 4) return;   // off: nothing set (dm/env may still set DM_HACK_*)
                Os.setenv("DM_HACK_TIER", t == 4 ? "custom" : String.valueOf(t), true);
                if (t != 4) return;
                int[] v = dos2HackValues(p);
                for (int i = HACK_FIRST; i < v.length; i++)   // not SCALE / FSR: the main page sets those
                    Os.setenv("DM_HACK_" + HACK_NAMES[i], i == 7 ? String.format(java.util.Locale.ROOT, "%.2f", v[i] / 100.0) : String.valueOf(v[i]), true);
            }
        };
    }

    // ---- [DOS2] thermal mode (next launch): hle_dos2_quality.c DM_DOS2_THERMAL=1, the ladder on the AThermal headroom (DRS ceiling, then the
    // shadow quality, then bloom). Off by default; when off nothing is set, so an env-file DM_DOS2_THERMAL still works
    static GearSettings.Section dos2Thermal() {
        return new GearSettings.Section() {
            CheckBox c;
            public void build(GearSettings g, LinearLayout box) {
                c = g.check(box, g.when(g.str(R.string.dos2_thermal), false), g.gamePrefs().getBoolean("dos2_thermal", false));
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { game.putBoolean("dos2_thermal", c.isChecked()); }
            public void env(GearSettings g) throws ErrnoException { if (g.gamePrefs().getBoolean("dos2_thermal", false)) Os.setenv("DM_DOS2_THERMAL", "1", true); }
        };
    }
    // ---- [DOS2] touch as mouse (next launch; experiment): hle_dos2_touch.c DM_DOS2_TOUCH=1, touches off the pad's buttons and stick homes
    // become mouse records in the engine's own InjectInput (tap = left click, drag = left drag, hold = right click, pinch = zoom, two-finger
    // drag = wheel), the iPad way. On by default (owner 15.11, Mi 13); when off nothing is set, so an env-file DM_DOS2_TOUCH still works for the hook (the pad
    // then still keeps the touches)
    static GearSettings.Section dos2Touch() {
        return new GearSettings.Section() {
            CheckBox c;
            public void build(GearSettings g, LinearLayout box) {
                c = g.check(box, g.when(g.str(R.string.dos2_touch), false), g.gamePrefs().getBoolean("dos2_touch", true));
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { game.putBoolean("dos2_touch", c.isChecked()); }
            public void env(GearSettings g) throws ErrnoException {
                DmActivity.dos2Touch = g.gamePrefs().getBoolean("dos2_touch", true);
                if (DmActivity.dos2Touch) Os.setenv("DM_DOS2_TOUCH", "1", true);
            }
        };
    }
    // ---- [DOS2] the iPad button column of the console HUD (bottomBar_d, tools/dos2_hud_touch.py; owner 15.11): shown / folded (a small arrow at the
    // right edge unfolds it) / hidden, and what a connected gamepad does to it: hide / fold (default) / leave as is. Live (DmActivity.dos2ColumnApply ->
    // nativeSetDos2Column -> hle_dos2_touchui_vis.c; the movie asks twice a second); the start state also goes into DM_DOS2_COLUMN
    // [DOS2] owner 15.11: the left stick can be switched off - then a tap anywhere on the floor walks; zoom = pinch, camera = two fingers
    // left / right (hle_dos2_touch.c). The hint is the note under the switch. Live (D3PadView reads DmActivity.dos2LStickOff).
    static GearSettings.Section dos2LStick() {
        return new GearSettings.Section() {
            android.widget.RadioGroup r;
            public void build(GearSettings g, LinearLayout box) {
                g.note(box, g.str(R.string.dos2_lstick));
                r = g.radios(box, new String[] {g.str(R.string.dos2_lstick_on), g.str(R.string.dos2_lstick_off)}, g.gamePrefs().getBoolean("dos2_lstick_hide", false) ? 1 : 0, true);
                g.note(box, g.str(R.string.dos2_lstick_hint));
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pd) {
                DmActivity.dos2LStickOff = GearSettings.picked(r) == 1; game.putBoolean("dos2_lstick_hide", DmActivity.dos2LStickOff);
            }
            public void env(GearSettings g) throws ErrnoException { DmActivity.dos2LStickOff = g.gamePrefs().getBoolean("dos2_lstick_hide", false); }
        };
    }
    // [DOS2] owner 16.11: the right stick hidden by default (one-finger swipe / two fingers turn the camera, pinch zooms); can be shown here. Live.
    static GearSettings.Section dos2RStick() {
        return new GearSettings.Section() {
            android.widget.RadioGroup r;
            public void build(GearSettings g, LinearLayout box) {
                g.note(box, g.str(R.string.dos2_rstick));
                r = g.radios(box, new String[] {g.str(R.string.dos2_lstick_on), g.str(R.string.dos2_rstick_off)}, g.gamePrefs().getBoolean("dos2_rstick_hide", true) ? 1 : 0, true);
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pd) {
                DmActivity.dos2RStickOff = GearSettings.picked(r) == 1; game.putBoolean("dos2_rstick_hide", DmActivity.dos2RStickOff);
            }
            public void env(GearSettings g) throws ErrnoException { DmActivity.dos2RStickOff = g.gamePrefs().getBoolean("dos2_rstick_hide", true); }
        };
    }
    static GearSettings.Section dos2Column() {
        return new GearSettings.Section() {
            android.widget.RadioGroup base, pad;
            public void build(GearSettings g, LinearLayout box) {
                SharedPreferences p = g.gamePrefs();
                g.note(box, g.str(R.string.dos2_column));
                base = g.radios(box, new String[] {g.str(R.string.dos2_column_shown), g.str(R.string.dos2_column_folded), g.str(R.string.dos2_column_hidden)}, p.getInt("dos2_col", 0), true);
                g.note(box, g.str(R.string.dos2_column_pad));
                pad = g.radios(box, new String[] {g.str(R.string.dos2_column_pad_hide), g.str(R.string.dos2_column_pad_fold), g.str(R.string.dos2_column_pad_keep)}, p.getInt("dos2_col_pad", 1), true);
            }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pd) {
                DmActivity.dos2ColBase = GearSettings.picked(base); DmActivity.dos2ColPad = GearSettings.picked(pad);
                game.putInt("dos2_col", DmActivity.dos2ColBase); game.putInt("dos2_col_pad", DmActivity.dos2ColPad);
                DmActivity.dos2ColumnApply();   // live
            }
            public void env(GearSettings g) throws ErrnoException {
                SharedPreferences p = g.gamePrefs();
                DmActivity.dos2ColBase = Math.max(0, Math.min(2, p.getInt("dos2_col", 0))); DmActivity.dos2ColPad = Math.max(0, Math.min(2, p.getInt("dos2_col_pad", 1)));
                Os.setenv("DM_DOS2_COLUMN", Integer.toString(DmActivity.dos2ColumnState()), true);
            }
        };
    }
    static GearSettings.Section stretchLoading() {
        return new GearSettings.Section() {
            CheckBox c;
            public void build(GearSettings g, LinearLayout box) { c = g.check(box, g.when(g.str(R.string.d3_stretch_loading), false), g.gamePrefs().getBoolean(DmActivity.STRETCH_LOADING_KEY, DmActivity.STRETCH_LOADING_DEFAULT)); }
            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { game.putBoolean(DmActivity.STRETCH_LOADING_KEY, c.isChecked()); }
            public void env(GearSettings g) throws ErrnoException {
                String on = g.gamePrefs().getBoolean(DmActivity.STRETCH_LOADING_KEY, DmActivity.STRETCH_LOADING_DEFAULT) ? "1" : "0";
                Os.setenv(TL2 ? "DM_TL2_WIDE_LOADSTRETCH" : "DM_D3_WIDE_STRETCH_LOADING", on, true);
            }
        };
    }

    // ---- the mod manager (Tl2Mods): every .MOD in Download/Torchlight2Mobile/mods with title, author, version from its header, a tick to enable
    // it and up / down for the load order (lower = loaded later, wins). Its own dialog, saved with its own "Save"; the next start converts and
    // loads them (DmActivity.prepareTl2Mods).
    static GearSettings.Section mods(DmActivity a) {
        return new GearSettings.Section() {
            public void build(GearSettings g, LinearLayout box) {
                g.heading(box, g.str(R.string.tl2_mods_title));
                Button b = g.button(box, g.str(R.string.tl2_mods_button, Tl2Mods.enabledCount(g.gamePrefs())));
                b.setOnClickListener(v -> showMods(g, b));
                g.note(box, g.str(R.string.tl2_mods_restart));
            }
        };
    }
    static void showMods(GearSettings g, Button from) {
        SharedPreferences p = g.gamePrefs(); final List<Tl2Mods.Mod> mods = Tl2Mods.list(p);
        LinearLayout box = g.vbox(null); box.setPadding(48, 24, 48, 0);
        g.note(box, g.str(R.string.tl2_mods_folder, Tl2Mods.modsDir().getAbsolutePath()));
        final LinearLayout rows = g.vbox(box);
        final Runnable[] fill = new Runnable[1];
        fill[0] = () -> {
            rows.removeAllViews();
            if (mods.isEmpty()) { TextView t = g.text(rows, g.str(R.string.tl2_mods_none)); t.setPadding(0, 24, 0, 24); }
            for (int i = 0; i < mods.size(); i++) {
                final int at = i; final Tl2Mods.Mod m = mods.get(i);
                LinearLayout row = new LinearLayout(g.a); row.setOrientation(LinearLayout.HORIZONTAL); row.setPadding(0, 12, 0, 12);
                CheckBox c = new CheckBox(g.a);
                String sub = m.info == null ? g.str(R.string.tl2_mods_bad, m.error)
                    : g.str(R.string.tl2_mods_line, (m.info.author.isEmpty() ? "" : m.info.author + " · ") + m.file.getName(), m.info.modver);
                c.setText(Tl2Mods.describe(m) + "\n" + sub); c.setEnabled(m.info != null); c.setChecked(m.on && m.info != null);
                c.setOnCheckedChangeListener((b, on) -> m.on = on);
                row.addView(c, new LinearLayout.LayoutParams(0, -2, 1f));
                Button up = new Button(g.a), down = new Button(g.a);
                up.setText("▲"); down.setText("▼"); up.setEnabled(i > 0); down.setEnabled(i < mods.size() - 1);
                up.setOnClickListener(v -> { java.util.Collections.swap(mods, at, at - 1); fill[0].run(); });
                down.setOnClickListener(v -> { java.util.Collections.swap(mods, at, at + 1); fill[0].run(); });
                row.addView(up, new LinearLayout.LayoutParams(-2, -2)); row.addView(down, new LinearLayout.LayoutParams(-2, -2));
                rows.addView(row);
            }
        };
        fill[0].run();
        g.note(box, g.str(R.string.tl2_mods_restart));
        android.widget.ScrollView scroll = new android.widget.ScrollView(g.a); scroll.addView(box);
        new AlertDialog.Builder(g.a).setTitle(g.str(R.string.tl2_mods_title)).setView(scroll)
            .setPositiveButton(g.s("gear_save"), (d, w) -> {
                String before = enabledList(p); Tl2Mods.save(p, mods); if (from != null) from.setText(g.str(R.string.tl2_mods_button, Tl2Mods.enabledCount(p)));
                if (!before.equals(enabledList(p))) askRestart(g, Tl2Mods.enabledCount(p) > 0);   // the enabled set or its order changed
            })
            .setNegativeButton(g.s("gear_cancel"), null).show();
    }

    // the enabled mods in load order (what the next start converts and loads)
    static String enabledList(SharedPreferences p) {
        StringBuilder b = new StringBuilder();
        for (String l : p.getString(Tl2Mods.PREF, "").split("\n")) if (l.endsWith("\t1")) b.append(l).append('\n');
        return b.toString();
    }
    // mods load only at the start: offer the graceful quit + reopen right away (DmActivity.restartGame)
    static void askRestart(GearSettings g, boolean anyOn) {
        new AlertDialog.Builder(g.a).setTitle(g.str(R.string.tl2_mods_restart_q))
            .setMessage(g.str(anyOn ? R.string.tl2_mods_restart_on : R.string.tl2_mods_restart_off))
            .setPositiveButton(g.str(R.string.tl2_mods_restart_now), (d, w) -> { if (g.a instanceof DmActivity) ((DmActivity) g.a).restartGame(); })
            .setNegativeButton(g.str(R.string.tl2_mods_restart_later), null).show();
    }

    // ---- the on-screen control layout (D3PadView "d3_layout"; applies when picked: the pad is visible behind the dialog). TL2: the D2R Mobile-style
    // layouts (Tl2Touch) "tl2" sticks + skill fan (default), "tl2_side" quick-access cells on the sides, or the gamepad; D3: touch / gamepad.
    // Below it the skill icons on the buttons (TL2: Tl2Touch "tl2_icons", hle_tl2_icons.c; D3: D3SkillIcons "d3_icons" + "d3_hide_sticks").
    static final class Layout implements GearSettings.Section {
        CheckBox icons, hide;
        public void build(GearSettings g, LinearLayout box) {
            SharedPreferences cp = g.padPrefs();
            g.heading(box, g.when(g.str(R.string.d3_layout), true));
            // [DOS2] the Switch pad first (its default, D3PadView.LAYOUT_DEFAULT), TL2's two touch layouts as alternatives
            final String[] ids = DmActivity.DOS2 ? new String[] {D3PadView.LAYOUT_GAMEPAD, D3PadView.LAYOUT_TL2, D3PadView.LAYOUT_TL2_SIDE}
                : TL2 ? new String[] {D3PadView.LAYOUT_TL2, D3PadView.LAYOUT_TL2_SIDE, D3PadView.LAYOUT_GAMEPAD} : new String[] {D3PadView.LAYOUT_TOUCH, D3PadView.LAYOUT_GAMEPAD};
            String now = cp.getString("d3_layout", D3PadView.LAYOUT_DEFAULT);
            int at = TL2 ? 0 : ids.length - 1;   // an unknown value: what D3PadView falls back to (DOS2 gamepad, TL2 tl2, D3 gamepad)
            for (int i = 0; i < ids.length; i++) if (ids[i].equals(now)) at = i;
            String[] labels = DmActivity.DOS2 ? new String[] {g.str(R.string.dos2_layout_switch), g.str(R.string.tl2_layout_touch), g.str(R.string.tl2_layout_side)}
                : TL2 ? new String[] {g.str(R.string.tl2_layout_touch), g.str(R.string.tl2_layout_side), g.str(R.string.d3_layout_gamepad)}
                      : new String[] {g.str(R.string.d3_layout_touch), g.str(R.string.d3_layout_gamepad)};
            RadioGroup r = g.radios(box, labels, at, false);
            r.setOnCheckedChangeListener((rg, id) -> { cp.edit().putString("d3_layout", ids[GearSettings.picked(rg)]).apply(); g.reloadPad(); });
            g.note(box, g.str(DmActivity.DOS2 ? R.string.dos2_layout_note : TL2 ? R.string.tl2_layout_note : R.string.d3_layout_note));
            if (TL2) icons = g.check(box, g.when(g.str(R.string.d3_skill_icons), true), cp.getBoolean("tl2_icons", true));
            else {
                icons = g.check(box, g.when(g.str(R.string.d3_skill_icons), true), cp.getBoolean("d3_icons", true));
                hide = g.check(box, g.when(g.str(R.string.d3_hide_sticks), true), cp.getBoolean("d3_hide_sticks", true));
                g.note(box, g.str(R.string.d3_skill_icons_note));
            }
        }
        public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) {
            pad.putBoolean(TL2 ? "tl2_icons" : "d3_icons", icons.isChecked());
            if (hide != null) pad.putBoolean("d3_hide_sticks", hide.isChecked());
        }
    }

    // ---- [TL2] the D2R-style touch layout (Tl2Touch, pad prefs tl2_*): sliders live, the rest on Save; the extras are off by default
    static final class TouchRows implements GearSettings.Section {
        RadioGroup mod, tap, aim; CheckBox walk;
        public void build(GearSettings g, LinearLayout box) {
            SharedPreferences cp = g.padPrefs();
            g.heading(box, g.when(g.str(R.string.tl2_touch), true));
            g.slider(box, cp, g.str(R.string.tl2_iso), "tl2_iso", Tl2Touch.ISO_MIN, Tl2Touch.ISO_MAX, Tl2Touch.ISO_DEFAULT, g::reloadPad);
            g.note(box, g.str(R.string.tl2_iso_note));
            g.heading(box, g.str(R.string.tl2_mod));
            mod = g.radios(box, Tl2Touch.MOD_NAMES, cp.getInt("tl2_mod", 0), true);
            g.note(box, g.str(R.string.tl2_mod_note));
            g.heading(box, g.str(R.string.tl2_extras));
            g.heading(box, g.str(R.string.tl2_tap));
            tap = g.radios(box, new String[] {g.str(R.string.d3_off), g.str(R.string.tl2_tap_a), g.str(R.string.tl2_tap_face)}, cp.getInt("tl2_tap", Tl2Touch.TAP_OFF), false);
            walk = g.check(box, g.str(R.string.tl2_hold_walk), cp.getBoolean("tl2_hold_walk", false));
            g.slider(box, cp, g.str(R.string.d3_hero_y), "tl2_hero_y", Tl2Touch.HERO_Y_MIN, Tl2Touch.HERO_Y_MAX, Tl2Touch.HERO_Y_DEFAULT, g::reloadPad);
            g.heading(box, g.str(R.string.tl2_aim));
            aim = g.radios(box, new String[] {g.str(R.string.d3_off), g.str(R.string.tl2_aim_right), g.str(R.string.tl2_aim_left)}, cp.getInt("tl2_aim", Tl2Touch.AIM_OFF), false);
        }
        public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) {
            pad.putInt("tl2_tap", GearSettings.picked(tap)).putBoolean("tl2_hold_walk", walk.isChecked()).putInt("tl2_aim", GearSettings.picked(aim))
               .putInt("tl2_mod", GearSettings.picked(mod));
        }
    }
    // ---- [D3] its touch layout: walking toward a held finger (D3PadView.HERO_* / DEPTH_*, live sliders) and what menu-mode swipes press
    static final class D3Touch implements GearSettings.Section {
        RadioGroup swipe;
        public void build(GearSettings g, LinearLayout box) {
            SharedPreferences cp = g.padPrefs();
            g.heading(box, g.when(g.str(R.string.d3_touch_walk), true));
            g.slider(box, cp, g.str(R.string.d3_hero_y), "d3_hero_y", D3PadView.HERO_Y_MIN, D3PadView.HERO_Y_MAX, D3PadView.HERO_Y_DEFAULT, g::reloadPad);
            g.slider(box, cp, g.str(R.string.d3_depth), "d3_depth", D3PadView.DEPTH_MIN, D3PadView.DEPTH_MAX, D3PadView.DEPTH_DEFAULT, g::reloadPad);
            g.note(box, g.str(R.string.d3_touch_walk_note));
            g.heading(box, g.when(g.str(R.string.d3_menu_swipe), true));
            swipe = g.radios(box, new String[] {g.str(R.string.d3_menu_swipe_stick), g.str(R.string.d3_menu_swipe_dpad)}, cp.getInt("d3_menu_swipe", D3PadView.MENU_SWIPE_STICK), true);
        }
        public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) { pad.putInt("d3_menu_swipe", GearSettings.picked(swipe)); }
    }
}
