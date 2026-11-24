package com.xiaoboluo.d2r;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

// [DOOM] On-screen controller, the unified front end's pad (frontend-common, docs/FRONTEND_UNIFIED.md; the same file in DOOM 2016, DOOM Eternal,
// Xenoblade Chronicles 2 and 3; Diablo III draws its own D3PadView with the same skins).
// Two layout presets ("doom_controls" pref "preset"):
//   game   DOOM 2016's pad, unchanged in behaviour:
//          left:  ZL / L in the top corner, "-" toward the middle, the move stick above the d-pad;
//          right: R / ZR in the top corner, "+" toward the middle, A/B/X/Y, and for the right thumb a large FIRE (ZR) button with MELEE
//                 (R3, the right stick click: melee and DOOM's "press R" prompts) next to it.
//   switch nx2android's ergonomic Switch layout (assets/overlay_default.tsv, phone at 1.9:1 and wider, else tablet): both sticks, the d-pad, A B X Y,
//          L R ZL ZR, - +, L3 R3 and the menu button; the layout the theme packs are drawn for (Xenoblade 3's default).
// Looking around works like a mouse: drag on any free spot (not a control, not around the move stick), or drag a held FIRE. Every
// sample of the finger's travel (MotionEvent history included) is measured in dp x the look sensitivity and handed to the native side
// (DmActivity.nativeLookDelta): by default (DM_TOUCH_LOOK=gyro) hle_hid.c adds it to the game's gyro aim channel at the game's next
// input read, so the view turns by exactly that much in the next frame, however slow or fast the finger is, and stops with it.
// DM_TOUCH_LOOK=stick (or a host that cannot use the gyro channel: nativeLookDelta false / missing) keeps the older path: the travel is added to a
// pending turn, played out through the right stick as tilt x time. Both use the same unit (tilt-seconds), so a sensitivity value means the same turn.
// The move stick is linear (DOOM's dead zone is off); the gear dialog can add an offset if the game keeps one anyway. [issue #40] A port can
// offer a floating move stick (six-argument constructor, pref "float_stick"; DOOM 2016: on): it appears under a finger anywhere on the left part
// of the screen, which then no longer turns the view; and a "map mode" (pref "map_key", DOOM 2016: "-") in which touch look drives the right stick.
// It feeds the same native controller channel as a physical gamepad (DmActivity.nativePadKey / nativePadAxes, device PAD_DEVICE)
// with the keycodes front_android.c maps to Switch buttons (Enter=A, Esc=B, R=X, F=Y, Q=L, E=R, Shift=ZL, Ctrl=ZR, Tab=+, M=-,
// BUTTON_THUMBL / THUMBR = L3 / R3, the d-pad keys); the keys sent are the union of every held control's, so FIRE and ZR (both Ctrl) never
// release each other.
// [front] Added from Xenoblade 3's front end: skins (PadSkin: "classic" = the outlines below, or one of nx2android's 26 packs), the controls' opacity
// and size, hiding the pad, and the layout editor (FrontMenu "Edit the layout": drag a control, a second finger resizes it, - / + resize the chosen
// one or all, Reset, Cancel, Save; places per preset in "pos_<game|phone|tablet>_<control>" = x;y;scale, x and y in fractions of the view - the
// same keys as Xenoblade 3's PadView). The gear (menu button) opens the pause menu on a tap (FrontMenu) and moves where it is dragged; its look
// (normal / faded to "gear_alpha" %) stays the gear dialog's.
public class DoomPadView extends View implements FrontMenu.Pad, PadSurface.Painter {
    static final int PAD_DEVICE = 0x7d00;
    static final int SETTINGS = -1;   // not a key: the menu button
    static final String PREFS = "doom_controls", PRESET_GAME = "game", PRESET_SWITCH = "switch";
    static final int OPACITY_DEFAULT = 100, SIZE_DEFAULT = 100;
    // Settings button look (gear dialog, doom_controls "gear_mode", players asked for it to be less in the way): normal, or faded (its
    // alpha scaled to "gear_alpha" % of the usual, a slider in the dialog, full while pressed, same spot). Applies in controllerMode too.
    // An old saved "hidden" (2) is shown as faded.
    static final int GEAR_NORMAL = 0, GEAR_FADED = 1, GEAR_ALPHA_DEFAULT = 10;
    static final int K_BUTTON = 0, K_STICK = 1, K_DPAD = 2, K_MENU = 3, K_CHEAT = 4;   // K_CHEAT: [BL2] action button (writes a cheat.req), no keycode

    // A control. game preset: centre = (fx * W + ox * u, fy * H + oy * u), half extents (hw, hh) * u, u = dp x size; switch preset (win = true):
    // centre = (fx * W + ox * H, fy * H), half extents (hw, hh) * H x the face-button scale. A player's place / size (editor) overrides it.
    static final class Ctl {
        final String name, label; final int kind, key; final float fx, fy, ox, oy, hw, hh; final boolean win;
        boolean look, right; int clickKey; float grab = 1.6f;
        String group;   // the editor moves and resizes a group as one (Diablo III's pad: the A/B/X/Y diamond); null = alone
        int pointer = -1; float kx, ky, travel; long down; boolean onKnob; int dirBits;   // runtime: the finger, a stick's knob (px), a d-pad's held directions
        float bx = Float.NaN, by;                                                         // runtime: a floating stick's base (px) while a finger holds it
        float px = -1, py = -1, ps = 1;                                                   // the player's place (fractions of the view) and size
        boolean removed;                                                                  // the player removed this control in the editor
        int[] combo;                                                                      // extra keycodes sent together with this button (a combo)
        Ctl(String name, String label, int kind, int key, float fx, float fy, float ox, float oy, float hw, float hh, boolean win) {
            this.name = name; this.label = label; this.kind = kind; this.key = key; this.fx = fx; this.fy = fy; this.ox = ox; this.oy = oy; this.hw = hw; this.hh = hh; this.win = win;
        }
    }
    // One finger turning the view: its last position.
    private static final class Look { int pointer = -1; float x, y; }

    // Finger travel (dp) worth one second of full right-stick tilt at sensitivity 1.0, and the time constant over which a pending turn
    // is played out (short, but longer than a game frame so DOOM's per-frame stick sample integrates it evenly).
    private static final float DP_PER_TILT_SECOND = 500, PLAYOUT_S = 0.05f;
    private static final float ABXY_FX = 0.885f, ABXY_FY = 0.36f, DPAD_FX = 0.21f, DPAD_FY = 0.74f, GAP = 50, STICK_R = 64;
    private static final float PHONE_ASPECT = 1.9f, MIN_MM = 10f, REACH_MIN = 0.045f, DRAG_SLOP = 0.02f;
    private final List<Ctl> ctls = new ArrayList<>();
    private final Look look = new Look(), fireLook = new Look(), wheelLook = new Look();
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG), line = new Paint(Paint.ANTI_ALIAS_FLAG), text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float dp, dpi;
    private final PadSkin skin;
    private final String defSkin, defPreset;
    private float deadzone = 0f, lookGain = 1.0f, lookX, lookY, pendX, pendY;
    private float lookDx, lookDy;          // finger travel (dp) not yet handed over (flushLook)
    private static boolean hostLook = true;   // false when the native library lacks nativeLookDelta
    // Weapon wheel (GitHub issue #34): DOOM opens it while R is held (nx_default.cfg: JOY6 "_changeWeapon") and picks the weapon with
    // the right stick, which touch look never moves (it goes through the gyro channel). While the wheel key is held, look-finger travel
    // steers the right stick instead: offset / WHEEL_R_DP, length capped at 1 (so turning back changes direction at once), kept after the
    // finger lifts until the key is released. The finger that holds the key steers too (like a held FIRE turns the view), so one thumb
    // presses R and slides toward the weapon. "wheel_key" (doom_controls): the keycode, 0 = off.
    // [front] Off unless the port opts in: wheelDefault (the constructor's wheelKeyDefault) is the key without a saved "wheel_key"; DOOM 2016
    // passes KEYCODE_E (its R, BUGS_AND_FIXES 2.42), every other port 0 (the old constructors) - their R keeps turning the view as before.
    private static final float WHEEL_R_DP = 40;
    private final int wheelDefault;
    private int wheelKey; private boolean wheelOn; private float wheelX, wheelY;
    // [issue #40] Floating move stick ("as in Diablo III's pad", D3PadView): a finger going down on a free spot of the move stick's side of the
    // screen (the left "float_zone" % of the width, below the top FLOAT_TOP of the height; mirrored when the stick was placed on the right half)
    // or on the stick itself puts the stick's base under the finger, so the tilt is the travel from the touch-down point (no dead circle, no jump
    // to the home centre) and walking starts with the first few dp (shape(): 0.04 of the radius, the move_dz offset). The stick is drawn at its
    // home while no finger holds it. A short tap that went down on the home knob is still L3. Buttons and the d-pad win over the zone; free spots
    // outside it turn the view as before. "float_stick" (doom_controls, boolean): on / off; without a saved value the port's floatDefault (the
    // constructor: DOOM 2016 true; the shorter constructors: not offered = the old fixed stick, no row in the gamepad dialog).
    static final int FLOAT_ZONE_DEFAULT = 45, FLOAT_ZONE_MIN = 25, FLOAT_ZONE_MAX = 60;
    private static final float FLOAT_TOP = 0.18f;
    private final boolean floatOffered, floatDefault;
    private boolean floatOn; private float floatZone = FLOAT_ZONE_DEFAULT / 100f;
    // [issue #40] 3D map (DOOM 2016: "-" = JOY10 opens the dossier / automap, rotated with the right stick). Touch look goes to the gyro channel,
    // which the map does not read (the same cause as the weapon wheel). While "map mode" is on, look-finger travel is played out on the right stick
    // (the pending-turn path of DM_TOUCH_LOOK=stick: finger offset -> rotation) instead of nativeLookDelta. The map key ("map_key", doom_controls;
    // 0 = off) toggles it, B (Esc) ends it. A wrong guess only gives the older stick feel of touch look in game until the next B. The host also
    // declines nativeLookDelta outside gameplay (hle_hid.c, DM_TOUCH_LOOK_GAMEPLAY), so a map that pauses the game turns without this.
    // mapDefault: the constructor's mapKeyDefault (DOOM 2016: KEYCODE_M = "-", every other port 0).
    private final int mapDefault;
    private int mapKey; private boolean mapOn;
    private int lookTakenLog = -1, lookTakenLogs;   // the last path touch look took (1 host gyro, 0 stick), logged on a change
    private long lookNanos;
    private float opacity = 1, sizeK = 1; private boolean shown = true, lookOn = true;
    // "split" (doom_controls, the editor's Grouped / Separate button; GitHub issue #9): every button is placed on its own: the A/B/X/Y
    // diamond is no group and the d-pad becomes four buttons. Off (default) = as before: the diamond and the d-pad move as one.
    private boolean split;
    private String preset = PRESET_GAME; private int builtFor = -2;   // the layout the controls were built for (-1 game, 0 tablet, 1 phone)
    private final Set<Integer> sent = new HashSet<>();   // keys held down in the game
    private Runnable editDone;
    // [front] With a PadSurface (attachSurface, DOOM Eternal's anrfix b1b9a60, docs/port-kb APP-01) the pad is drawn on that surface's own thread,
    // not on the window: the UI thread never waits for HWUI / the GPU (PadSurface.java has the ANR this fixes). Every change of what the pad shows
    // happens under `lock` (UI thread) and the draw thread paints under it; redraw() replaces invalidate(). Touches are still handled here, on the
    // UI thread, exactly as before. Without a surface (a port that never calls attachSurface, or detachSurface: DOOM 2016's DM_PAD_SURFACE=0 /
    // dmPadHwui) it is the old View, drawn on the window, unchanged.
    private final Object lock = new Object();
    private PadSurface surface;
    // The pad's surface, to add to the game's frame right under this view (above the game's SurfaceView); the same one on every call.
    PadSurface attachSurface() {
        if (surface == null) { surface = new PadSurface(getContext(), this); surface.setVisibility(getVisibility()); setWillNotDraw(true); }
        return surface;
    }
    // Back to drawing on the window (UI thread): the surface is taken out of its parent and its thread ends.
    void detachSurface() {
        PadSurface s;
        synchronized (lock) { s = surface; surface = null; }
        if (s == null) return;
        if (s.getParent() instanceof android.view.ViewGroup) ((android.view.ViewGroup) s.getParent()).removeView(s);
        setWillNotDraw(false); invalidate();
        android.util.Log.i("dm", "[java] pad drawn on the window again (HWUI)");
    }
    boolean drawsOnSurface() { return surface != null; }
    private void redraw() { PadSurface s = surface; if (s != null) s.request(); else invalidate(); }
    @Override public void setVisibility(int v) { super.setVisibility(v); PadSurface s = surface; if (s != null) s.setVisibility(v); }

    // defaultPreset: PRESET_GAME (DOOM, Eternal, XC2) or PRESET_SWITCH (XC3); defaultSkin: PadSkin.CLASSIC or a pack; wheelKeyDefault: the weapon
    // wheel key without a saved "wheel_key" (0 = no wheel: the two shorter constructors; DOOM 2016: KeyEvent.KEYCODE_E); mapKeyDefault: the map key
    // without a saved "map_key" (0 = no map mode; DOOM 2016: KeyEvent.KEYCODE_M = "-"); floatStickDefault: the floating move stick without a saved
    // "float_stick" (only the six-argument constructor offers it; the shorter ones keep the fixed stick and show no option for it)
    public DoomPadView(Context c) { this(c, PRESET_GAME, PadSkin.CLASSIC, 0); }
    public DoomPadView(Context c, String defaultPreset, String defaultSkin) { this(c, defaultPreset, defaultSkin, 0); }
    public DoomPadView(Context c, String defaultPreset, String defaultSkin, int wheelKeyDefault) { this(c, defaultPreset, defaultSkin, wheelKeyDefault, 0, false, false); }
    public DoomPadView(Context c, String defaultPreset, String defaultSkin, int wheelKeyDefault, int mapKeyDefault, boolean floatStickDefault) {
        this(c, defaultPreset, defaultSkin, wheelKeyDefault, mapKeyDefault, true, floatStickDefault);
    }
    private DoomPadView(Context c, String defaultPreset, String defaultSkin, int wheelKeyDefault, int mapKeyDefault, boolean offerFloat, boolean floatStickDefault) {
        super(c);
        dp = c.getResources().getDisplayMetrics().density; dpi = c.getResources().getDisplayMetrics().ydpi;
        defPreset = defaultPreset; defSkin = defaultSkin; wheelDefault = wheelKeyDefault;
        mapDefault = mapKeyDefault; floatOffered = offerFloat; floatDefault = offerFloat && floatStickDefault;
        skin = new PadSkin(c);
        line.setStyle(Paint.Style.STROKE); line.setStrokeWidth(2 * dp);
        text.setTextAlign(Paint.Align.CENTER); text.setTextSize(15 * dp);
        reloadSettings();
    }
    String defaultSkin() { return defSkin; }
    // [issue #40] the gamepad dialog (FrontMenu) shows the floating stick's row and zone slider only for a port that offers it
    boolean floatingOffered() { return floatOffered; }
    boolean floatingDefault() { return floatDefault; }

    // ---- the controls of a preset
    private void build(int layout) {
        ctls.clear(); builtFor = layout;
        if (layout < 0) {   // DOOM 2016's pad
            int B = K_BUTTON;
            // right cluster: diamond X top, A right, B bottom, Y left
            ctls.add(new Ctl("x", "X", B, KeyEvent.KEYCODE_R, ABXY_FX, ABXY_FY, 0, -GAP, 26, 26, false)); ctls.add(new Ctl("a", "A", B, KeyEvent.KEYCODE_ENTER, ABXY_FX, ABXY_FY, GAP, 0, 28, 28, false));
            ctls.add(new Ctl("b", "B", B, KeyEvent.KEYCODE_ESCAPE, ABXY_FX, ABXY_FY, 0, GAP, 26, 26, false)); ctls.add(new Ctl("y", "Y", B, KeyEvent.KEYCODE_F, ABXY_FX, ABXY_FY, -GAP, 0, 26, 26, false));
            // right thumb: MELEE (R3) next to where FIRE used to be
            ctls.add(new Ctl("rs", "R3", B, KeyEvent.KEYCODE_BUTTON_THUMBR, 0.86f, 0.79f, -88, 14, 28, 28, false));
            ctls.add(new Ctl("r", "R", B, KeyEvent.KEYCODE_E, 0.84f, 0.09f, 0, 0, 26, 26, false)); ctls.add(new Ctl("zr", "ZR", B, KeyEvent.KEYCODE_CTRL_LEFT, 0.95f, 0.09f, 0, 0, 28, 28, false));
            ctls.add(new Ctl("plus", "+", B, KeyEvent.KEYCODE_TAB, 0.62f, 0.09f, 0, 0, 22, 22, false));
            // left: the d-pad (one control, 8 directions; drawn as DOOM's four buttons), L / ZL, "-", the gear in the middle
            if (split) {   // "split" (editor toggle): the d-pad's four buttons are separate controls, each placed on its own
                ctls.add(new Ctl("dpad_up", "↑", B, KeyEvent.KEYCODE_DPAD_UP, DPAD_FX, DPAD_FY, 0, -GAP, 24, 24, false)); ctls.add(new Ctl("dpad_right", "→", B, KeyEvent.KEYCODE_DPAD_RIGHT, DPAD_FX, DPAD_FY, GAP, 0, 24, 24, false));
                ctls.add(new Ctl("dpad_down", "↓", B, KeyEvent.KEYCODE_DPAD_DOWN, DPAD_FX, DPAD_FY, 0, GAP, 24, 24, false)); ctls.add(new Ctl("dpad_left", "←", B, KeyEvent.KEYCODE_DPAD_LEFT, DPAD_FX, DPAD_FY, -GAP, 0, 24, 24, false));
            } else ctls.add(new Ctl("dpad", "", K_DPAD, 0, DPAD_FX, DPAD_FY, 0, 0, GAP + 24, GAP + 24, false));
            ctls.add(new Ctl("l", "L", B, KeyEvent.KEYCODE_Q, 0.16f, 0.09f, 0, 0, 26, 26, false)); ctls.add(new Ctl("zl", "ZL", B, KeyEvent.KEYCODE_SHIFT_LEFT, 0.05f, 0.09f, 0, 0, 28, 28, false));
            if (DmActivity.BL2) ctls.add(new Ctl("ls", "L3", B, KeyEvent.KEYCODE_BUTTON_THUMBL, 0.09f, 0.84f, 0, 0, 28, 28, false));   // [BL2] L3 按键（替代原 AI 按钮的位置）
            ctls.add(new Ctl("minus", "-", B, KeyEvent.KEYCODE_M, 0.38f, 0.09f, 0, 0, 22, 22, false));
            Ctl st = new Ctl("stick_l", "", K_STICK, 0, 0.12f, 0.42f, 0, 0, STICK_R, STICK_R, false); st.clickKey = KeyEvent.KEYCODE_BUTTON_THUMBL; ctls.add(st);
        } else if (skin.theme != null) {   // nx2android's ergonomic layout
            for (PadTheme.Ctl c : skin.theme.layouts[layout]) {
                int kind = c.kind == PadTheme.STICK_L || c.kind == PadTheme.STICK_R ? K_STICK : c.kind == PadTheme.DPAD ? K_DPAD : c.kind == PadTheme.MENU ? K_MENU : K_BUTTON;
                if (kind == K_DPAD && split) {   // the same four separate buttons in the theme's d-pad box (thirds of it)
                    float t = c.w / 3; String[] n = {"dpad_up", "dpad_right", "dpad_down", "dpad_left"}, lab = {"↑", "→", "↓", "←"};
                    int[] key = {KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_RIGHT, KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_DPAD_LEFT}; float[][] o = {{0, -t}, {t, 0}, {0, t}, {-t, 0}};
                    for (int i = 0; i < 4; i++) ctls.add(new Ctl(n[i], lab[i], K_BUTTON, key[i], c.ax, c.y + o[i][1], c.x + o[i][0], 0, t / 2, t / 2, true));
                    continue;
                }
                Ctl k = new Ctl(c.name, c.kind == PadTheme.MENU ? "⚙" : c.label, kind, kind == K_MENU ? SETTINGS : keyOf(c.btn), c.ax, c.y, c.x, 0, c.w / 2, c.h / 2, true);
                if (kind == K_STICK) { k.right = c.kind == PadTheme.STICK_R; k.clickKey = k.right ? KeyEvent.KEYCODE_BUTTON_THUMBR : KeyEvent.KEYCODE_BUTTON_THUMBL; k.grab = 1.15f; }
                ctls.add(k);
            }
        }
        if (!split) for (Ctl c : ctls) if (c.kind == K_BUTTON && ("a".equals(c.name) || "b".equals(c.name) || "x".equals(c.name) || "y".equals(c.name))) c.group = "abxy";
        loadPlaces();
    }
    static int keyOf(int btn) {   // DM_BTN_* -> the keycode front_android.c maps to it
        switch (btn) {
            case PadTheme.A: return KeyEvent.KEYCODE_ENTER; case PadTheme.B: return KeyEvent.KEYCODE_ESCAPE; case PadTheme.X: return KeyEvent.KEYCODE_R; case PadTheme.Y: return KeyEvent.KEYCODE_F;
            case PadTheme.L: return KeyEvent.KEYCODE_Q; case PadTheme.R: return KeyEvent.KEYCODE_E; case PadTheme.ZL: return KeyEvent.KEYCODE_SHIFT_LEFT; case PadTheme.ZR: return KeyEvent.KEYCODE_CTRL_LEFT;
            case PadTheme.PLUS: return KeyEvent.KEYCODE_TAB; case PadTheme.MINUS: return KeyEvent.KEYCODE_M; case PadTheme.LS: return KeyEvent.KEYCODE_BUTTON_THUMBL; case PadTheme.RS: return KeyEvent.KEYCODE_BUTTON_THUMBR;
            default: return 0;
        }
    }
    private int wantLayout() { return PRESET_SWITCH.equals(preset) && skin.theme != null && getHeight() > 0 ? (getWidth() >= PHONE_ASPECT * getHeight() ? 1 : 0) : -1; }
    private void ensureBuilt() { int l = wantLayout(); if (l != builtFor) { releaseAllLocked(); build(l); } }
    private String placeKey(Ctl c) { return "pos_" + (builtFor < 0 ? "game" : PadTheme.LAYOUT_NAMES[builtFor]) + "_" + c.name; }
    private SharedPreferences prefs() { return getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE); }
    private void loadPlaces() {
        SharedPreferences p = prefs();
        for (Ctl c : ctls) { c.px = c.py = -1; c.ps = 1; String v = p.getString(placeKey(c), null);
            if (v != null) try { String[] f = v.split(";"); c.px = Float.parseFloat(f[0]); c.py = Float.parseFloat(f[1]); c.ps = Float.parseFloat(f[2]); } catch (Exception e) { c.px = c.py = -1; c.ps = 1; }
            c.removed = p.getBoolean("rm_" + placeKey(c), false);
            String cb = p.getString("combo_" + placeKey(c), null); c.combo = null;
            if (cb != null && !cb.isEmpty()) { String[] f = cb.split(","); int[] a = new int[f.length]; int n = 0;
                for (String s : f) try { a[n++] = Integer.parseInt(s.trim()); } catch (Exception ignored) {} if (n > 0) { c.combo = new int[n]; System.arraycopy(a, 0, c.combo, 0, n); } }
        }
    }
    private void savePlaces() {
        SharedPreferences.Editor e = prefs().edit();
        for (Ctl c : ctls) {
            String k = placeKey(c); if (c.px < 0 && c.ps == 1) e.remove(k); else e.putString(k, String.format(Locale.ROOT, "%.5f;%.5f;%.4f", c.px, c.py, c.ps));
            if (c.removed) e.putBoolean("rm_" + k, true); else e.remove("rm_" + k);
            if (c.combo == null || c.combo.length == 0) e.remove("combo_" + k); else { StringBuilder b = new StringBuilder(); for (int kk : c.combo) { if (b.length() > 0) b.append(','); b.append(kk); } e.putString("combo_" + k, b.toString()); }
        }
        e.apply();
    }

    // A real controller is connected (DmActivity.updatePadVisibility): only the settings button stays; everything held is released.
    private boolean controllerMode;
    private int gearMode = GEAR_NORMAL, gearAlpha = GEAR_ALPHA_DEFAULT;
    // Frame counter (gear dialog): fps, mean / max frame time and GPU time of the last 0.5 s, redrawn twice a second.
    private boolean showFps; private final float[] fstats = new float[4];
    private final Runnable fpsTick = new Runnable() { public void run() { if (!showFps) return; synchronized (lock) { try { DmActivity.nativeFrameStats(fstats); } catch (UnsatisfiedLinkError e) { fstats[0] = 0; } } redraw(); postDelayed(this, 500); } };
    // The top-left rounded screen corner and the cutout inset (Android 12+, from WindowInsets), so the FPS counter starts where the top of
    // its glyphs clears the corner arc (Poco F8 Ultra: a bigger radius than the Mi 14 Ultra cut off the start of the line; diablo3-port #1,
    // D3PadView 5941060). Android 10 / 11: 18 dp, as before (also the minimum).
    private float cornerCx, cornerCy, cornerR, safeLeft;
    @Override public android.view.WindowInsets onApplyWindowInsets(android.view.WindowInsets in) {
        cornerR = 0; safeLeft = 0;
        if (android.os.Build.VERSION.SDK_INT >= 31) {
            android.view.RoundedCorner rc = in.getRoundedCorner(android.view.RoundedCorner.POSITION_TOP_LEFT);
            if (rc != null) { cornerR = rc.getRadius(); cornerCx = rc.getCenter().x; cornerCy = rc.getCenter().y; }
            safeLeft = in.getInsets(android.view.WindowInsets.Type.displayCutout()).left;
        }
        redraw();
        return super.onApplyWindowInsets(in);
    }
    private float cornerLeft(float y) {   // x where the corner arc ends at height y (0 below the arc)
        if (cornerR <= 0 || y >= cornerCy) return 0;
        float dy = cornerCy - y; return dy >= cornerR ? cornerCx : cornerCx - (float) Math.sqrt(cornerR * cornerR - dy * dy);
    }
    private void drawFps(Canvas c) {
        if (!showFps || fstats[0] <= 0) return;
        String t = String.format(Locale.ROOT, "%.0f fps  %.1f ms (max %.0f)%s", fstats[0], fstats[1], fstats[2],
            fstats[3] >= 0 ? String.format(Locale.ROOT, "  GPU %.1f", fstats[3]) : "");
        // top left corner, clear of the rounded screen corner; green, half the old size, no background
        text.setTextSize(7.5f * dp); text.setColor(0xff5cff5c); text.setAlpha(255);
        float y = text.getTextSize(), top = y + text.ascent();
        float left = Math.max(18 * dp, Math.max(safeLeft, cornerLeft(top)) + 6 * dp);
        c.drawText(t, left + text.measureText(t) / 2, y, text);   // the paint is centred: shift by half the width
    }
    void setControllerMode(boolean on) {
        synchronized (lock) {
            if (on == controllerMode) return;
            controllerMode = on;
            if (on) releaseAllLocked();
        }
        redraw();
    }
    boolean controllerMode() { return controllerMode; }

    @Override public void reloadSettings() { synchronized (lock) { reloadSettingsLocked(); } redraw(); kickHide(); }
    private void reloadSettingsLocked() {
        SharedPreferences p = prefs();
        deadzone = p.getFloat("move_dz", 0f); showFps = p.getBoolean("fps", true); removeCallbacks(fpsTick); if (showFps) postDelayed(fpsTick, 500); lookGain = p.getFloat("look", 1.0f);
        wheelKey = p.getInt("wheel_key", wheelDefault);
        mapKey = p.getInt("map_key", mapDefault); if (mapKey == 0) mapOn = false;
        floatOn = floatOffered && p.getBoolean("float_stick", floatDefault);
        floatZone = Math.max(FLOAT_ZONE_MIN, Math.min(FLOAT_ZONE_MAX, p.getInt("float_zone", FLOAT_ZONE_DEFAULT))) / 100f;
        gearMode = p.getInt("gear_mode", GEAR_NORMAL) == GEAR_NORMAL ? GEAR_NORMAL : GEAR_FADED; gearAlpha = Math.max(1, Math.min(100, p.getInt("gear_alpha", GEAR_ALPHA_DEFAULT)));
        opacity = Math.max(5, Math.min(100, p.getInt("opacity", OPACITY_DEFAULT))) / 100f; sizeK = Math.max(60, Math.min(160, p.getInt("size", SIZE_DEFAULT))) / 100f;
        shown = p.getBoolean("shown", true); lookOn = p.getBoolean("look_on", true); tick = p.getBoolean("tick", false);
        autoHide = p.getBoolean("pad_autohide", false); autoHideSec = Math.max(2, Math.min(30, p.getInt("pad_autohide_s", 5)));
        if (!autoHide) autoHidden = false;





        boolean sp = p.getBoolean("split", false); if (sp != split) { split = sp; if (builtFor != -2) { releaseAllLocked(); builtFor = -2; } }
        String pr = p.getString("preset", defPreset); if (!pr.equals(preset)) { preset = pr; builtFor = -2; }
        if (builtFor != -2) loadPlaces();
        skinPack = p.getString("skin", defSkin);
        if (surface != null && getHeight() > 0) ensureBuilt();   // [front] the draw thread does not build the controls
    }
    private String skinPack = PadSkin.CLASSIC;
    @Override public String prefsName() { return PREFS; }
    @Override public String[] sliderKeys() { return new String[] {"opacity", "size"}; }
    @Override public int[] sliderDefaults() { return new int[] {OPACITY_DEFAULT, SIZE_DEFAULT}; }
    @Override public String[] presets() { return skin.theme == null ? null : new String[] {PRESET_GAME, PRESET_SWITCH}; }
    @Override public View view() { return this; }

    // ---- geometry
    private float u() { return dp * sizeK; }
    private float faceScale() {   // switch preset: a face button at least MIN_MM wide on a small screen (nx2android's dm_overlay_scale)
        float face = 0.1f; for (Ctl c : ctls) if (c.win && "a".equals(c.name)) face = c.hw * 2;
        float mm = face * getHeight() / dpi * 25.4f, s = mm > 0 ? MIN_MM / mm : 1; return Math.max(1, Math.min(1.45f, s));
    }
    private float[] box(Ctl c) {   // centre x, y, half width, half height in px
        float W = getWidth(), H = getHeight(), hw, hh, x, y;
        if (c.win) { float s = faceScale() * (c.kind == K_MENU ? 1 : sizeK); hw = c.hw * H * s; hh = c.hh * H * s; x = c.fx * W + c.ox * H; y = c.fy * H; }
        else { float k = c.kind == K_MENU ? dp : u(); hw = c.hw * k; hh = c.hh * k; x = c.fx * W + c.ox * u(); y = c.fy * H + c.oy * u(); }
        hw *= c.ps; hh *= c.ps;
        if (c.px >= 0) { x = c.px * W; y = c.py * H; }
        return new float[] {keep(x, hw, W), keep(y, hh, H), hw, hh};
    }
    private static float keep(float p, float half, float extent) { float lo = Math.min(half, extent / 2); return Math.max(lo, Math.min(extent - lo, p)); }
    private static float boxSdf(float dx, float dy, float hw, float hh, float rad) {
        float qx = Math.abs(dx) - hw + rad, qy = Math.abs(dy) - hh + rad, px = Math.max(qx, 0), py = Math.max(qy, 0);
        return (float) Math.sqrt(px * px + py * py) + Math.min(Math.max(qx, qy), 0) - rad;
    }
    // [BL2] 自动隐藏时齿轮跟着一起收起，不再特殊对待；只有接实体手柄时保留齿轮（那时它是触屏上唯一的菜单入口）
    // [BL2] the gear hides with everything else; only with a real controller does it stay (it is then the only touch way to the menu)
    private boolean visible(Ctl c) { return c.kind == K_MENU && controllerMode || (shown && !controllerMode && !autoHidden && !c.removed); }
    // the control a finger going down at (x, y) takes: the nearest button / d-pad / menu whose (enlarged) shape holds it, else a stick whose grab zone
    // holds it (any: every control, for the editor)
    private Ctl hit(float x, float y, boolean any) {
        Ctl best = null; float bd = Float.MAX_VALUE, H = getHeight();
        for (Ctl c : ctls) {
            if (c.kind == K_STICK || (!any && !visible(c))) continue;
            float[] b = box(c); float m = Math.min(b[2], b[3]), rad = b[2] == b[3] ? m : m * 0.35f;
            float d = boxSdf(x - b[0], y - b[1], b[2], b[3], rad), reach = c.win ? Math.max(m * 0.25f, REACH_MIN * H - m) : m * 0.25f;
            if (d < reach && (d + m) / (m + reach) < bd) { bd = (d + m) / (m + reach); best = c; }
        }
        if (best != null) return best;
        for (Ctl c : ctls) {
            if (c.kind != K_STICK || (!any && !visible(c))) continue;
            float[] b = box(c); float dx = x - b[0], dy = y - b[1], r = b[2] * (any ? 1 : c.grab);
            if (dx * dx + dy * dy <= r * r && (best == null || Math.hypot(dx, dy) / b[2] < bd)) { best = c; bd = (float) Math.hypot(dx, dy) / b[2]; }
        }
        return best;
    }
    // a stick's box with its centre at the floating base while a finger holds it there (home otherwise)
    private float[] stickBox(Ctl s) { float[] b = box(s); if (!Float.isNaN(s.bx)) { b[0] = s.bx; b[1] = s.by; } return b; }
    private void moveStick(Ctl s, float x, float y) {
        float[] b = stickBox(s); float R = b[2], dx = x - b[0], dy = y - b[1], d = (float) Math.sqrt(dx * dx + dy * dy);
        if (d > R) { dx *= R / d; dy *= R / d; }
        s.kx = dx; s.ky = dy; s.travel = Math.max(s.travel, d);
    }
    private void grab(Ctl s, int id, float x, float y) { float[] b = box(s); s.onKnob = Math.hypot(x - b[0], y - b[1]) <= b[2]; s.bx = Float.NaN; s.pointer = id; s.down = SystemClock.uptimeMillis(); moveStick(s, x, y); s.travel = 0; }
    // [issue #40] the floating move stick: the base goes under the finger, the knob starts centred on it
    private void grabFloat(Ctl s, int id, float x, float y) {
        float[] b = box(s); s.onKnob = Math.hypot(x - b[0], y - b[1]) <= b[2];
        s.bx = x; s.by = y; s.pointer = id; s.down = SystemClock.uptimeMillis(); s.kx = s.ky = 0; s.travel = 0;
    }
    private boolean floats(Ctl s) { return floatOn && s.kind == K_STICK && !s.right; }
    private Ctl moveCtl() { for (Ctl c : ctls) if (c.kind == K_STICK && !c.right) return c; return null; }
    // a free spot on the move stick's side: the left float_zone of the width (the right one when the stick sits on the right half), below the top strip
    private boolean inFloatZone(Ctl s, float x, float y) {
        float W = getWidth(), H = getHeight(); if (y < FLOAT_TOP * H) return false;
        return box(s)[0] <= W / 2 ? x < floatZone * W : x > (1 - floatZone) * W;
    }
    private void release(Ctl s) {   // a short tap on a stick's knob still presses L3 / R3
        float R = box(s)[2];
        if (s.onKnob && s.travel < 0.5f * R && SystemClock.uptimeMillis() - s.down < 300 && s.clickKey != 0
            && !(l3Locked && s.clickKey == KeyEvent.KEYCODE_BUTTON_THUMBL)) {   // [BL2] L3 锁着时摇杆的短按不发（否则会把锁松开）
            final int k = s.clickKey; key(k, true); postDelayed(() -> key(k, false), 120);
        }
        s.pointer = -1; s.kx = s.ky = 0; s.bx = Float.NaN;
    }
    private void dpadAt(Ctl c, float x, float y) {
        float[] b = box(c); float dx = (x - b[0]) / b[2], dy = (y - b[1]) / b[3], m = (float) Math.sqrt(dx * dx + dy * dy);
        c.dirBits = 0;
        if (m > 0.25f) { int s = Math.round((float) Math.atan2(dy, dx) / ((float) Math.PI / 4)) & 7;   // 8 directions, 0 = right, clockwise
            final int[] dir = {PadTheme.RIGHT, PadTheme.RIGHT | PadTheme.DOWN, PadTheme.DOWN, PadTheme.DOWN | PadTheme.LEFT, PadTheme.LEFT, PadTheme.LEFT | PadTheme.UP, PadTheme.UP, PadTheme.UP | PadTheme.RIGHT};
            c.dirBits = dir[s]; }
    }

    // Radial dead-zone compensation: a small finger deflection maps to just past the game's dead zone, then grows linearly.
    private float[] shape(float x, float y) {
        float m = (float) Math.sqrt(x * x + y * y);
        if (m < 0.04f) return new float[] {0, 0};
        float o = Math.min(1f, deadzone + (1f - deadzone) * Math.min(1f, m));
        return new float[] {x / m * o, y / m * o};
    }

    private void lookStart(Look l, int id, float x, float y) { l.pointer = id; l.x = x; l.y = y; }
    private void lookMove(Look l, float x, float y) {   // finger travel, in dp
        lookDx += (x - l.x) / dp; lookDy += (y - l.y) / dp; l.x = x; l.y = y;
    }
    // Hand the travel over in tilt-seconds (dp x sensitivity / DP_PER_TILT_SECOND): to the gyro aim channel (hle_hid.c dm_touch_look_add,
    // applied whole at the game's next read: no smoothing, no dead zone, nothing left over), or, when the host does not take it, to the
    // pending stick turn below.
    private void flushLook() {
        if (lookDx == 0 && lookDy == 0) return;
        if (wheelOn) {   // the weapon wheel: the travel steers the right stick (see wheelKey)
            wheelX += lookDx / WHEEL_R_DP; wheelY += lookDy / WHEEL_R_DP;
            float m = (float) Math.sqrt(wheelX * wheelX + wheelY * wheelY);
            if (m > 1) { wheelX /= m; wheelY /= m; }
            lookDx = lookDy = 0; return;
        }
        float k = lookGain / DP_PER_TILT_SECOND;
        boolean taken = false;
        // map mode (issue #40): the right stick, not the host's gyro channel; the host itself declines outside gameplay (hle_hid.c)
        if (hostLook && !mapOn) try { taken = DmActivity.nativeLookDelta(lookDx, lookDy, k); } catch (UnsatisfiedLinkError err) { hostLook = false; }
        if (!taken) { pendX += lookDx * k; pendY += lookDy * k; }
        if (hostLook && (taken ? 1 : 0) != lookTakenLog && lookTakenLogs < 60) {
            lookTakenLog = taken ? 1 : 0; lookTakenLogs++;
            android.util.Log.i("dm", "[java] touch look -> " + (taken ? "gyro aim channel (host)" : mapOn ? "right stick (map mode)" : "right stick (host declined: not in gameplay / no gyro reads / DM_TOUCH_LOOK=stick)"));
        }
        lookDx = lookDy = 0;
    }
    // [issue #40] map mode: the map key toggles it, B ends it (sendKeys, on a fresh press of the pad)
    private void mapKeyPressed(int k) {
        if (mapKey == 0) return;
        boolean on = k == mapKey ? !mapOn : k == KeyEvent.KEYCODE_ESCAPE ? false : mapOn;
        if (on == mapOn) return;
        mapOn = on; pendX = pendY = lookDx = lookDy = 0; lookTakenLog = -1;
        android.util.Log.i("dm", "[java] map mode " + (on ? "on (map key): touch look turns the right stick" : "off (" + (k == mapKey ? "map key" : "B") + ")"));
    }
    // Play the pending turn out: tilt = pending / PLAYOUT_S (at most full tilt); what was played since the last tick leaves the pending
    // turn, so the total rotation equals the finger travel. A very fast flick just takes a little longer than its swipe to finish.
    private void updateLook() {
        long now = System.nanoTime();
        float dt = lookNanos == 0 ? 0 : Math.min(0.1f, (now - lookNanos) * 1e-9f); lookNanos = now;
        float px = pendX, py = pendY;
        pendX -= lookX * dt; pendY -= lookY * dt;
        if (pendX * px <= 0) pendX = 0;   // played past zero: done on that axis
        if (pendY * py <= 0) pendY = 0;
        float x = pendX / PLAYOUT_S, y = pendY / PLAYOUT_S, m = (float) Math.sqrt(x * x + y * y);
        if (m > 1) { x /= m; y /= m; }
        if (Math.abs(pendX) < 1e-5f && Math.abs(pendY) < 1e-5f) { pendX = pendY = x = y = 0; lookNanos = 0; }
        lookX = x; lookY = y;
    }

    // ---- output: the union of the held controls' keys (diffed against what the game holds), then the axes
    private static void key(int k, boolean down) { DmActivity.nativePadKey(PAD_DEVICE, k, down); }
    private void sendKeys() {
        Set<Integer> want = new HashSet<>();
        for (Ctl c : ctls) {
            if (c.pointer < 0 || c.removed) continue;
            if (c.kind == K_BUTTON && c.key != 0) want.add(c.key);
            else if (c.kind == K_DPAD) {
                if ((c.dirBits & PadTheme.UP) != 0) want.add(KeyEvent.KEYCODE_DPAD_UP); if ((c.dirBits & PadTheme.DOWN) != 0) want.add(KeyEvent.KEYCODE_DPAD_DOWN);
                if ((c.dirBits & PadTheme.LEFT) != 0) want.add(KeyEvent.KEYCODE_DPAD_LEFT); if ((c.dirBits & PadTheme.RIGHT) != 0) want.add(KeyEvent.KEYCODE_DPAD_RIGHT);
            }
            if (c.combo != null) for (int kk : c.combo) want.add(kk);   // 组合键：和这个按钮的键一起按
        }
        if (l3Locked) want.add(KeyEvent.KEYCODE_BUTTON_THUMBL);   // [BL2] L3 锁定 = 一直按住
        for (Integer k : new ArrayList<>(sent)) if (!want.contains(k)) { key(k, false); sent.remove(k); }
        boolean pressed = false;
        for (Integer k : want) if (sent.add(k)) { key(k, true); pressed = true; mapKeyPressed(k); }
        if (pressed && tick && getContext() instanceof Ticker) ((Ticker) getContext()).padTick();
    }
    // a host that can tick the phone's vibrator on a press (Xenoblade 3: nativeTap); "tick" pref, off unless set
    interface Ticker { void padTick(); }
    private boolean tick;
    private void axes() {
        updateLook();
        float lx = 0, ly = 0, rx = 0, ry = 0;
        for (Ctl c : ctls) if (c.kind == K_STICK) { float R = box(c)[2]; float[] v = shape(c.kx / R, c.ky / R); if (c.right) { rx = v[0]; ry = v[1]; } else { lx = v[0]; ly = v[1]; } }
        if (wheelOn) { rx += wheelX; ry += wheelY; }
        // [BL2] L3 锁定：每次从静止起步补发一次 L3 按下。游戏停步后会清掉冲刺，光靠一直按住 L3 不够。
        // [BL2] L3 latch: re-send one L3 press on every start from standstill (the game drops the sprint when movement stops).
        if (l3Locked) {
            final int L3 = KeyEvent.KEYCODE_BUTTON_THUMBL;
            boolean moving = Math.sqrt(lx * lx + ly * ly) > 0.15f;
            if (moving && !l3Moving) {
                sent.remove(L3); key(L3, false);
                postDelayed(() -> { synchronized (lock) { if (l3Locked && sent.add(L3)) key(L3, true); } }, 50);
            }
            l3Moving = moving;
        } else l3Moving = false;
        DmActivity.nativePadAxes(PAD_DEVICE, lx, ly, Math.max(-1, Math.min(1, rx + lookX)), Math.max(-1, Math.min(1, ry + lookY)), 0, 0, 0, 0);
    }
    // The wheel key held by any control (a button or the d-pad never carries it): look-finger travel then goes to wheelX / wheelY.
    private void updateWheel() {
        boolean on = false;
        if (wheelKey != 0) for (Ctl c : ctls) if (c.pointer >= 0 && c.kind == K_BUTTON && c.key == wheelKey) { on = true; break; }
        if (on != wheelOn) { wheelOn = on; wheelX = wheelY = 0; lookDx = lookDy = 0; pendX = pendY = 0; }
    }
    // Every held key up, sticks centred, look stopped, zero axes (the pause menu, the editor, a controller taking over).
    @Override public void releaseAll() { synchronized (lock) { releaseAllLocked(); } redraw(); }
    private void releaseAllLocked() {
        for (Ctl c : ctls) { c.pointer = -1; c.kx = c.ky = 0; c.dirBits = 0; c.bx = Float.NaN; }
        look.pointer = fireLook.pointer = wheelLook.pointer = -1; pendX = pendY = lookX = lookY = lookDx = lookDy = 0; lookNanos = 0; menuPtr = -1;
        wheelOn = false; wheelX = wheelY = 0;
        for (Integer k : sent) key(k, false);
        sent.clear();
        if (!controllerMode) try { DmActivity.nativePadAxes(PAD_DEVICE, 0, 0, 0, 0, 0, 0, 0, 0); } catch (UnsatisfiedLinkError e) { /* not loaded yet */ }
    }
    private void openMenu() { if (getContext() instanceof FrontMenu.Owner) { FrontMenu m = ((FrontMenu.Owner) getContext()).frontMenu(); if (m != null) m.open(); } }

    // ---- touches
    private int menuPtr = -1; private boolean menuMoved; private float menuX0, menuY0, menuGX, menuGY;
    // [BL2] 触控 UI 自动隐藏（gear "pad_autohide" / "pad_autohide_s"）：超过设定秒数没有触摸就把控件收起来，只留齿轮；
    // 任意一次点按先把它们放回来（那一下只用于唤回，不喂给游戏）。
    // [BL2] Auto-hide of the on-screen controls (gear "pad_autohide" / "pad_autohide_s"): after the chosen idle seconds only the gear stays;
    // any tap brings everything back (that tap only reveals, it is not fed to the game).
    private boolean autoHide; private int autoHideSec = 5; private boolean autoHidden;
    // [BL2] L3 锁定：点一下当长按（一直按住左摇杆键），再点一下松开；每次新开 App 默认不锁
    // [BL2] L3 latch: one tap holds the left-stick button down, the next one releases it; off on every new app run
    private boolean l3Locked;
    private boolean l3Moving;   // [BL2] 左摇杆上一帧是否在移动：锁定时每次起步补发一次 L3 按下（停步后游戏会清掉冲刺）








    private final Runnable hideTask = new Runnable() {
        public void run() {
            boolean hide;
            synchronized (lock) { hide = autoHide && !edit && !autoHidden; if (hide) { releaseAllLocked(); autoHidden = true; } }
            if (hide) redraw();
        }
    };
    private void kickHide() {
        removeCallbacks(hideTask);
        if (autoHide && !edit) postDelayed(hideTask, Math.max(2, autoHideSec) * 1000L);
    }
    @Override protected void onAttachedToWindow() { super.onAttachedToWindow(); kickHide(); }
    // [BL2] 外接手柄时：控件不隐藏、照常可用，只强制 10 秒自动收起；拔掉后恢复玩家自己的自动隐藏设置
    // [BL2] With a real controller: the controls stay usable, only forced to auto-hide after 10 idle seconds; unplugging restores the player's setting
    public void controllerAutoHide(boolean on) {
        if (!DmActivity.BL2) { setControllerMode(on); return; }
        synchronized (lock) {
            if (on) { autoHide = true; autoHideSec = 10; }
            else reloadSettings();
        }
        kickHide(); redraw();
    }
    @Override public boolean onTouchEvent(MotionEvent e) {
        if (autoHidden) {
            if (e.getActionMasked() == MotionEvent.ACTION_DOWN) { synchronized (lock) { autoHidden = false; } redraw(); kickHide(); }
            return true;   // this tap only brings the controls back
        }
        synchronized (lock) { touch(e); kickPlayout(); }
        redraw(); kickHide();
        return true;
    }
    private void touch(MotionEvent e) {
        ensureBuilt();
        if (edit) { editTouch(e); return; }
        int a = e.getActionMasked(), i = e.getActionIndex(), id = e.getPointerId(i);
        float x = e.getX(i), y = e.getY(i);
        switch (a) {
        case MotionEvent.ACTION_DOWN: case MotionEvent.ACTION_POINTER_DOWN: {
            Ctl c = hit(x, y, false), ms;
            if (c != null && c.kind == K_MENU) { c.pointer = id; menuPtr = id; menuMoved = false; menuX0 = x; menuY0 = y; float[] b = box(c); menuGX = b[0] - x; menuGY = b[1] - y; }
            else if (controllerMode) { /* a real controller drives the game: only the menu button, and no axes from this pad (they would make the touch pad
                the active controller in front_android.c) */ }
            else if (c != null && c.kind == K_STICK && c.pointer < 0) { if (floats(c)) grabFloat(c, id, x, y); else grab(c, id, x, y); }
            else if (c != null && c.kind == K_DPAD && c.pointer < 0) { c.pointer = id; dpadAt(c, x, y); }
            else if (c != null && c.kind == K_BUTTON && "ls".equals(c.name)) { l3Locked = !l3Locked; l3Moving = false; }   // [BL2] L3：点一下锁住（长按），再点一下松开
            else if (c != null && c.kind == K_CHEAT && c.pointer < 0) { c.pointer = id; }   // [BL2] AI 按钮：按下高亮，抬起时发命令
            else if (c != null && c.kind == K_BUTTON && c.pointer < 0) { c.pointer = id; if (c.look && fireLook.pointer < 0) lookStart(fireLook, id, x, y);
                if (wheelKey != 0 && c.key == wheelKey && wheelLook.pointer < 0) lookStart(wheelLook, id, x, y); }
            else if (c == null && floatOn && (ms = moveCtl()) != null && ms.pointer < 0 && visible(ms) && inFloatZone(ms, x, y)) grabFloat(ms, id, x, y);   // [issue #40]
            else if (lookOn && look.pointer < 0) lookStart(look, id, x, y);   // any other free spot turns the view
            break;
        }
        case MotionEvent.ACTION_MOVE:
            for (int k = 0; k < e.getPointerCount(); k++) {
                int pid = e.getPointerId(k); float px = e.getX(k), py = e.getY(k);
                for (Ctl c : ctls) if (c.pointer == pid) {
                    if (c.kind == K_STICK) moveStick(c, px, py);
                    else if (c.kind == K_DPAD) dpadAt(c, px, py);
                    else if (c.kind == K_MENU && pid == menuPtr) menuDrag(c, px, py);
                }
                Look l = pid == look.pointer ? look : pid == fireLook.pointer ? fireLook : pid == wheelLook.pointer ? wheelLook : null;
                if (l != null) {   // every batched sample (getHistoricalX/Y), then the current position
                    for (int h = 0, n = e.getHistorySize(); h < n; h++) lookMove(l, e.getHistoricalX(k, h), e.getHistoricalY(k, h));
                    lookMove(l, px, py);
                }
            }
            flushLook();
            break;
        case MotionEvent.ACTION_UP: case MotionEvent.ACTION_POINTER_UP: case MotionEvent.ACTION_CANCEL: {
            boolean all = a == MotionEvent.ACTION_CANCEL || a == MotionEvent.ACTION_UP;
            for (Ctl c : ctls) if (c.pointer >= 0 && (c.pointer == id || all)) {
                if (c.kind == K_STICK) release(c);
                else if (c.kind == K_MENU) { if (menuMoved) savePlaces(); else if (a != MotionEvent.ACTION_CANCEL && c.pointer == id) post(this::openMenu); c.pointer = -1; menuPtr = -1; }
                else if (c.kind == K_CHEAT) { if (a != MotionEvent.ACTION_CANCEL && c.pointer == id) fireAlly(); c.pointer = -1; }
                else { c.pointer = -1; c.dirBits = 0; }
            }
            if (id == look.pointer || all) look.pointer = -1;
            if (id == fireLook.pointer || all) fireLook.pointer = -1;
            if (id == wheelLook.pointer || all) wheelLook.pointer = -1;
            break;
        }
        }
        if (!controllerMode) { updateWheel(); sendKeys(); axes(); }
    }
    // [BL2] AI 按钮：把准星目标变成队友（写一行 cheat.req 的 ally，原生层在出图线程执行）
    private void fireAlly() {
        android.content.Context c = getContext();
        if (c instanceof android.app.Activity) Bl2Cheat.send((android.app.Activity) c, "ally");
    }
    private void menuDrag(Ctl c, float x, float y) {
        if (!menuMoved && Math.hypot(x - menuX0, y - menuY0) < DRAG_SLOP * getHeight()) return;
        menuMoved = true; c.px = Math.max(0, Math.min(1, (x + menuGX) / getWidth())); c.py = Math.max(0, Math.min(1, (y + menuGY) / getHeight()));
    }

    // ---- the layout editor (from Xenoblade 3's front end)
    private boolean edit; private Ctl edSel; private int edPtr = -1, edPtr2 = -1, edBtnDown = -1; private float edGX, edGY, edD0, edS0; private float[][] edSaved; private boolean[] edRmSaved; private int[][] edComboSaved;
    @Override public void startEdit(Runnable done) {
        synchronized (lock) {
        ensureBuilt(); releaseAllLocked(); edit = true; edSel = null; edPtr = edPtr2 = -1; editDone = done;
        edSaved = new float[ctls.size()][]; edRmSaved = new boolean[ctls.size()]; edComboSaved = new int[ctls.size()][];
        for (int i = 0; i < ctls.size(); i++) { Ctl c = ctls.get(i); edSaved[i] = new float[] {c.px, c.py, c.ps}; edRmSaved[i] = c.removed; edComboSaved[i] = c.combo; }
        android.util.Log.i("dm", "[java] layout editor open (" + preset + ")");
        }
        redraw();
    }
    @Override public boolean editing() { return edit; }
    @Override public void endEdit(boolean save) {
        synchronized (lock) {
        if (!edit) return;
        if (save) savePlaces(); else for (int i = 0; i < ctls.size() && i < edSaved.length; i++) { Ctl c = ctls.get(i); c.px = edSaved[i][0]; c.py = edSaved[i][1]; c.ps = edSaved[i][2]; c.removed = edRmSaved[i]; c.combo = edComboSaved[i]; }
        edit = false; edSel = null;
        }
        redraw();
        kickHide();   // [BL2] the auto-hide clock starts again once the editor is closed
        android.util.Log.i("dm", "[java] layout editor " + (save ? "saved" : "cancelled"));
        Runnable d = editDone; editDone = null; if (d != null) d.run();
    }
    @Override public void resetLayout() { synchronized (lock) { ensureBuilt(); for (Ctl c : ctls) { c.px = c.py = -1; c.ps = 1; c.removed = false; c.combo = null; } savePlaces(); } redraw(); }
    private static final int ED_BUTTONS = 9;
    static final float ED_GRID_DIV = 40f;   // 方形网格：格边长 = 屏高 / 40
    private RectF edButton(int k) {   // the toolbar: − + 成组/单独 添加 移除 组合 重置 取消 保存
        float H = getHeight(), bw = H * 0.105f, bh = H * 0.075f, gap = H * 0.012f, total = ED_BUTTONS * bw + (ED_BUTTONS - 1) * gap, x0 = (getWidth() - total) / 2, y0 = H * 0.03f;
        return new RectF(x0 + k * (bw + gap), y0, x0 + k * (bw + gap) + bw, y0 + bh);
    }
    private int edButtonAt(float x, float y) { for (int k = 0; k < ED_BUTTONS; k++) if (edButton(k).contains(x, y)) return k; return -1; }
    // [BL2] 编辑器：添加（把移除过的控件放回来）、组合键（给选中的按钮加同时按的键）
    private void edAddDialog() {
        if (!(getContext() instanceof android.app.Activity)) return;
        final List<Ctl> gone = new ArrayList<>();
        for (Ctl c : ctls) if (c.removed && c.kind != K_MENU) gone.add(c);
        if (gone.isEmpty()) { toast("没有可添加的按键"); return; }
        String[] names = new String[gone.size()];
        for (int i = 0; i < gone.size(); i++) names[i] = gone.get(i).label;
        new android.app.AlertDialog.Builder(getContext()).setTitle("添加按键")
            .setItems(names, (d, which) -> { synchronized (lock) { gone.get(which).removed = false; } redraw(); })
            .setNegativeButton("取消", null).show();
    }
    private static final int[] COMBO_KEYS = {KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_ESCAPE, KeyEvent.KEYCODE_R, KeyEvent.KEYCODE_F,
        KeyEvent.KEYCODE_Q, KeyEvent.KEYCODE_E, KeyEvent.KEYCODE_SHIFT_LEFT, KeyEvent.KEYCODE_CTRL_LEFT,
        KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_DPAD_LEFT, KeyEvent.KEYCODE_DPAD_RIGHT,
        KeyEvent.KEYCODE_BUTTON_THUMBL, KeyEvent.KEYCODE_BUTTON_THUMBR, KeyEvent.KEYCODE_TAB, KeyEvent.KEYCODE_M};
    private static final String[] COMBO_NAMES = {"A", "B", "X", "Y", "L", "R", "ZL", "ZR", "十字上", "十字下", "十字左", "十字右", "L3", "R3", "+", "-"};
    private void edComboDialog() {
        if (edSel == null || edSel.kind != K_BUTTON || !(getContext() instanceof android.app.Activity)) { toast("先选中一个按键"); return; }
        final boolean[] on = new boolean[COMBO_KEYS.length];
        if (edSel.combo != null) for (int kk : edSel.combo) for (int i = 0; i < COMBO_KEYS.length; i++) if (COMBO_KEYS[i] == kk) on[i] = true;
        final Ctl sel = edSel;
        new android.app.AlertDialog.Builder(getContext()).setTitle("组合键（同时按）")
            .setMultiChoiceItems(COMBO_NAMES, on, (d, which, checked) -> on[which] = checked)
            .setPositiveButton("确定", (d, w) -> { synchronized (lock) {
                List<Integer> l = new ArrayList<>(); for (int i = 0; i < on.length; i++) if (on[i]) l.add(COMBO_KEYS[i]);
                if (l.isEmpty()) sel.combo = null; else { sel.combo = new int[l.size()]; for (int i = 0; i < l.size(); i++) sel.combo[i] = l.get(i); }
            } redraw(); })
            .setNegativeButton("取消", null).show();
    }
    private void toast(String s) { android.widget.Toast.makeText(getContext(), s, android.widget.Toast.LENGTH_SHORT).show(); }
    // Grouped / Separate in the editor: the places so far are saved, the controls rebuilt, and Cancel goes back to the new set as it is now
    private void edToggleSplit() {
        savePlaces(); split = !split; prefs().edit().putBoolean("split", split).apply();
        android.util.Log.i("dm", "[java] layout editor: " + (split ? "every button on its own" : "ABXY and d-pad grouped"));
        build(builtFor); edSel = null; edGroup.clear();
        edSaved = new float[ctls.size()][]; edRmSaved = new boolean[ctls.size()]; edComboSaved = new int[ctls.size()][];
        for (int i = 0; i < ctls.size(); i++) { Ctl c = ctls.get(i); edSaved[i] = new float[] {c.px, c.py, c.ps}; edRmSaved[i] = c.removed; edComboSaved[i] = c.combo; }
    }
    private void edResize(Ctl c, float s) { c.ps = Math.max(0.5f, Math.min(2.5f, s)); }
    private void edPlace(Ctl c, float cx, float cy) {   // 吸附到方形网格
        float W = Math.max(1, getWidth()), H = Math.max(1, getHeight()), cell = H / ED_GRID_DIV;
        float x = Math.round(Math.max(0, Math.min(W, cx)) / cell) * cell, y = Math.round(Math.max(0, Math.min(H, cy)) / cell) * cell;
        c.px = Math.max(0, Math.min(1, x / W)); c.py = Math.max(0, Math.min(1, y / H));
    }
    // A group (c.group) is edited as one: the members' centres and sizes when the finger went down, moved by the same offset or scaled about their centre
    private final List<Ctl> edGroup = new ArrayList<>(); private float[][] edStart = new float[0][]; private float edCX, edCY;
    private void edGrab(Ctl sel) {
        edGroup.clear();
        if (sel != null) for (Ctl c : ctls) if (c == sel || (sel.group != null && sel.group.equals(c.group))) edGroup.add(c);
        edStart = new float[edGroup.size()][]; edCX = edCY = 0;
        for (int i = 0; i < edGroup.size(); i++) { Ctl c = edGroup.get(i); float[] b = box(c); edStart[i] = new float[] {b[0], b[1], c.ps}; edCX += b[0]; edCY += b[1]; }
        if (!edGroup.isEmpty()) { edCX /= edGroup.size(); edCY /= edGroup.size(); }
    }
    private void edMoveGroup(float dx, float dy) { for (int i = 0; i < edGroup.size(); i++) edPlace(edGroup.get(i), edStart[i][0] + dx, edStart[i][1] + dy); }
    private void edScaleGroup(float f) {
        for (int i = 0; i < edGroup.size(); i++) { Ctl c = edGroup.get(i); edResize(c, edStart[i][2] * f); float k = c.ps / edStart[i][2];
            if (edGroup.size() > 1) edPlace(c, edCX + (edStart[i][0] - edCX) * k, edCY + (edStart[i][1] - edCY) * k); }
    }
    private void editTouch(MotionEvent e) {
        int a = e.getActionMasked(), ai = e.getActionIndex();
        if (a == MotionEvent.ACTION_DOWN || a == MotionEvent.ACTION_POINTER_DOWN) {
            int id = e.getPointerId(ai); float x = e.getX(ai), y = e.getY(ai);
            int bt = edButtonAt(x, y);
            if (bt >= 0 && edPtr < 0) { edBtnDown = bt; edPtr = id; redraw(); return; }
            if (edPtr >= 0 && edSel != null && edPtr2 < 0 && edBtnDown < 0) {   // a second finger pinches the chosen control
                int k = e.findPointerIndex(edPtr); if (k >= 0) { edD0 = (float) Math.hypot(x - e.getX(k), y - e.getY(k)); edPtr2 = id; edS0 = edSel.ps; edGrab(edSel); }
                return;
            }
            if (edPtr >= 0) return;
            Ctl c = hit(x, y, true); edSel = c; edPtr = c != null ? id : -1; edBtnDown = -1;
            if (c != null) { float[] b = box(c); edGX = b[0] - x; edGY = b[1] - y; edGrab(c); }
            redraw();
        } else if (a == MotionEvent.ACTION_MOVE) {
            if (edPtr < 0 || edBtnDown >= 0 || edSel == null) return;
            int k1 = e.findPointerIndex(edPtr), k2 = edPtr2 >= 0 ? e.findPointerIndex(edPtr2) : -1;
            if (k1 >= 0 && k2 >= 0 && edD0 > 1) edScaleGroup((float) Math.hypot(e.getX(k1) - e.getX(k2), e.getY(k1) - e.getY(k2)) / edD0);
            else if (k1 >= 0) { int s = edGroup.indexOf(edSel); if (s >= 0) edMoveGroup(e.getX(k1) + edGX - edStart[s][0], e.getY(k1) + edGY - edStart[s][1]); }
            redraw();
        } else if (a == MotionEvent.ACTION_UP || a == MotionEvent.ACTION_POINTER_UP || a == MotionEvent.ACTION_CANCEL) {
            int id = e.getPointerId(ai);
            if (id == edPtr2) { edPtr2 = -1; if (edSel != null) { edGrab(edSel); int k = e.findPointerIndex(edPtr); int s = edGroup.indexOf(edSel); if (k >= 0 && s >= 0) { edGX = edStart[s][0] - e.getX(k); edGY = edStart[s][1] - e.getY(k); } } return; }
            if (id != edPtr && a != MotionEvent.ACTION_CANCEL) return;
            int bt = edBtnDown; edPtr = edPtr2 = -1; edBtnDown = -1;
            if (bt >= 0 && a != MotionEvent.ACTION_CANCEL && bt == edButtonAt(e.getX(ai), e.getY(ai))) {
                if (bt == 0 || bt == 1) { float f = bt == 1 ? 1.1f : 1 / 1.1f; if (edSel != null) { edGrab(edSel); edScaleGroup(f); } else for (Ctl c : ctls) edResize(c, c.ps * f); }
                else if (bt == 2) edToggleSplit();
                else if (bt == 3) edAddDialog();
                else if (bt == 4) { if (edSel != null) { edSel.removed = true; edSel = null; } }
                else if (bt == 5) edComboDialog();
                else if (bt == 6) { for (Ctl c : ctls) { c.px = c.py = -1; c.ps = 1; c.removed = false; c.combo = null; } edSel = null; }
                else if (bt == 7) { endEdit(false); return; }
                else { endEdit(true); return; }
            }
            redraw();
        }
    }

    // ---- drawing
    @Override protected void onDraw(Canvas c) {
        super.onDraw(c);
        if (surface != null) return;   // [front] drawn by PadSurface's thread
        ensureBuilt();
        // tick every frame while a pending turn is being played out
        if (pendX != 0 || pendY != 0 || lookX != 0 || lookY != 0) { axes(); postInvalidateOnAnimation(); }
        drawPad(c);
    }
    // [front] With a PadSurface the pending stick turn (DM_TOUCH_LOOK=stick) is played out by a Choreographer callback on the UI thread, which draws nothing.
    private boolean playoutPosted;
    private final Runnable playout = () -> { synchronized (lock) { playoutPosted = false; if (pendX != 0 || pendY != 0 || lookX != 0 || lookY != 0) { axes(); kickPlayout(); } } };
    private void kickPlayout() { if (surface != null && !playoutPosted && (pendX != 0 || pendY != 0 || lookX != 0 || lookY != 0)) { playoutPosted = true; postOnAnimation(playout); } }
    @Override protected void onSizeChanged(int w, int h, int ow, int oh) {
        super.onSizeChanged(w, h, ow, oh);
        if (surface != null) { synchronized (lock) { ensureBuilt(); } redraw(); }
    }
    // ---- [front] PadSurface.Painter: the draw thread, under lock
    @Override public Object paintLock() { return lock; }
    @Override public long paintSignature() {
        int w = getWidth(), ht = getHeight();
        if (w <= 0 || ht <= 0) return PadSurface.NOT_READY;
        if (builtFor != wantLayout()) { post(() -> { synchronized (lock) { ensureBuilt(); } redraw(); }); return PadSurface.NOT_READY; }   // the controls are built on the UI thread
        long s = 17;
        s = s * 31 + w; s = s * 31 + ht; s = s * 31 + builtFor; s = s * 31 + ctls.size();
        s = s * 31 + ((edit ? 1 : 0) | (controllerMode ? 2 : 0) | (shown ? 4 : 0) | (showFps ? 8 : 0) | (split ? 16 : 0) | gearMode << 5 | (autoHidden ? 128 : 0) | (l3Locked ? 256 : 0));
        s = s * 31 + Float.floatToIntBits(opacity); s = s * 31 + Float.floatToIntBits(sizeK); s = s * 31 + gearAlpha;
        s = s * 31 + skinPack.hashCode(); s = s * 31 + preset.hashCode();
        s = s * 31 + (edSel == null ? -1 : ctls.indexOf(edSel)); s = s * 31 + edBtnDown;
        if (showFps && !edit) for (float f : fstats) s = s * 31 + Float.floatToIntBits(f);
        for (Ctl k : ctls) {
            s = s * 31 + (k.pointer >= 0 ? 1 : 0); s = s * 31 + k.dirBits;
            s = s * 31 + Float.floatToIntBits(k.kx); s = s * 31 + Float.floatToIntBits(k.ky);
            s = s * 31 + Float.floatToIntBits(k.bx); s = s * 31 + Float.floatToIntBits(k.by);
            s = s * 31 + Float.floatToIntBits(k.px); s = s * 31 + Float.floatToIntBits(k.py); s = s * 31 + Float.floatToIntBits(k.ps);
        }
        return s == PadSurface.NOT_READY ? s + 1 : s;
    }
    @Override public void paint(Canvas c) { drawPad(c); }
    private void drawPad(Canvas c) {
        if (!edit) drawFps(c);
        skin.select(skinPack, PadSkin.layoutFor(getWidth(), getHeight()));
        if (edit) c.drawColor(0x55000000);
        for (Ctl k : ctls) if (k.kind != K_MENU && (edit || visible(k))) drawCtl(c, k);
        for (Ctl k : ctls) if (k.kind == K_MENU && (edit || visible(k))) drawCtl(c, k);   // [BL2] 齿轮也按同一规则隐藏
        if (edit) drawEditor(c);
    }
    private float alphaOf(Ctl k) {
        if (k.kind == K_MENU) return k.pointer >= 0 ? 1 : gearMode == GEAR_FADED ? gearAlpha / 100f : 1;
        float a = edit ? Math.max(opacity, 0.7f) : opacity;
        return edit && inSel(k) ? 1 : a;
    }
    private boolean inSel(Ctl k) { return edSel != null && (k == edSel || (edSel.group != null && edSel.group.equals(k.group))); }
    private void drawCtl(Canvas c, Ctl k) {
        float[] b = k.kind == K_STICK && !edit ? stickBox(k) : box(k); float al = alphaOf(k);   // a floating stick is drawn where the finger put it
        boolean held = k.pointer >= 0;
        float R = b[2], kx = k.kind == K_STICK ? k.kx / R : 0, ky = k.kind == K_STICK ? k.ky / R : 0;
        float sa = al * (k.kind == K_MENU ? 1 : skin.packAlpha());
        // the game preset's round buttons: a skin's shoulder (wide) sprites get a pill-shaped box of the same height
        float bw = b[2], bh = b[3];
        if (!k.win && (k.name.equals("l") || k.name.equals("r") || k.name.equals("zl") || k.name.equals("zr") || k.kind == K_MENU)) bw = b[2] * 1.6f;
        if (skin.draw(c, k.name, b[0], b[1], bw, bh, held, k.dirBits, kx, ky, sa, getHeight())) {
            if (l3Locked && "ls".equals(k.name)) drawLock(c, b[0], b[1], Math.min(b[2], b[3]), al);
            return;
        }
        drawClassic(c, k, b, al, held);
        if (l3Locked && "ls".equals(k.name)) drawLock(c, b[0], b[1], Math.min(b[2], b[3]), al);
    }
    // [BL2] L3 锁定标记：按钮右上角的小锁
    private void drawLock(Canvas c, float x, float y, float r, float al) {
        float s = Math.max(7 * dp, r * 0.42f), cx = x + r * 0.62f, cy = y - r * 0.62f;
        int col = 0xffe8c040, a = Math.round(0xff * al);
        line.setStrokeWidth(Math.max(1.5f, s * 0.22f)); line.setColor(col); line.setAlpha(a);
        fill.setColor(col); fill.setAlpha(a);
        c.drawArc(cx - s * 0.55f, cy - s * 1.2f, cx + s * 0.55f, cy + s * 0.25f, 180, 180, false, line);
        c.drawRoundRect(new RectF(cx - s * 0.75f, cy - s * 0.1f, cx + s * 0.75f, cy + s * 1.0f), s * 0.22f, s * 0.22f, fill);
    }
    private void drawClassic(Canvas c, Ctl k, float[] b, float al, boolean held) {
        float x = b[0], y = b[1];
        line.setColor(0x90ffffff); line.setAlpha(Math.round(0x90 * al)); text.setColor(0xd0ffffff); text.setAlpha(Math.round(0xd0 * al));
        if (k.kind == K_STICK) {
            float R = b[2];
            fill.setColor(0x20ffffff); fill.setAlpha(Math.round(0x20 * al)); c.drawCircle(x, y, R, fill); c.drawCircle(x, y, R, line);
            fill.setColor(held ? 0x80ffffff : 0x40ffffff); fill.setAlpha(Math.round((held ? 0x80 : 0x40) * al)); c.drawCircle(x + k.kx, y + k.ky, R * 0.42f, fill);
            return;
        }
        if (k.kind == K_DPAD) {   // DOOM's four buttons
            float g = b[2] * GAP / (GAP + 24), r = b[2] - g; text.setTextSize(Math.max(10 * dp, r * 0.62f));
            float[][] d = {{0, -g}, {g, 0}, {0, g}, {-g, 0}}; String[] lab = {"↑", "→", "↓", "←"}; int[] bit = {PadTheme.UP, PadTheme.RIGHT, PadTheme.DOWN, PadTheme.LEFT};
            for (int i = 0; i < 4; i++) { boolean on = held && (k.dirBits & bit[i]) != 0;
                fill.setColor(on ? 0x80ffffff : 0x30ffffff); fill.setAlpha(Math.round((on ? 0x80 : 0x30) * al));
                c.drawCircle(x + d[i][0], y + d[i][1], r, fill); c.drawCircle(x + d[i][0], y + d[i][1], r, line);
                c.drawText(lab[i], x + d[i][0], y + d[i][1] + text.getTextSize() * 0.35f, text); }
            return;
        }
        int base = held ? 0x80ffffff : (k.kind == K_CHEAT ? 0x45ffb347 : (k.look ? 0x40ff6040 : 0x30ffffff));   // [BL2] AI 按钮染成橙色，好认
        fill.setColor(base); fill.setAlpha(Math.round(((base >>> 24) & 0xff) * al));
        text.setTextSize(Math.max(10 * dp, Math.min(15 * dp * sizeK, Math.min(b[2], b[3]) * 0.75f)));
        if (b[2] == b[3]) { c.drawCircle(x, y, b[2], fill); c.drawCircle(x, y, b[2], line); }
        else { RectF r = new RectF(x - b[2], y - b[3], x + b[2], y + b[3]); float rad = Math.min(b[2], b[3]); c.drawRoundRect(r, rad, rad, fill); c.drawRoundRect(r, rad, rad, line); }
        c.drawText(k.label, x, y + text.getTextSize() * 0.35f, text);
    }
    private void drawEditor(Canvas c) {
        String[] names = {"−", "+", split ? "单独" : "成组", "添加", "移除", "组合", "重置", "取消", "保存"};
        // 方形网格：格边长 = 屏高 / 40
        float cell = getHeight() / ED_GRID_DIV;
        line.setStrokeWidth(Math.max(1, 1 * dp));
        line.setColor(0xffffffff); line.setAlpha(0x30);
        for (float x = cell; x < getWidth(); x += cell) c.drawLine(x, 0, x, getHeight(), line);
        for (float y = cell; y < getHeight(); y += cell) c.drawLine(0, y, getWidth(), y, line);
        line.setColor(0xff7fe3f0); line.setAlpha(0x70); line.setStrokeWidth(Math.max(1, 1.5f * dp));
        c.drawRect(0, 0, getWidth(), getHeight(), line);   // 边框，确认网格层在画
        line.setAlpha(255);
        line.setStrokeWidth(1.5f * dp);
        text.setTextSize(getHeight() * 0.038f); text.setColor(0xffffffff); text.setAlpha(255);
        for (int k = 0; k < ED_BUTTONS; k++) {
            RectF r = edButton(k); fill.setColor(k == edBtnDown ? 0xff1fb6c9 : k == ED_BUTTONS - 1 ? 0xe0157c8a : 0xd0202833); line.setColor(0xff7fe3f0); line.setStrokeWidth(1.5f * dp);
            float rad = r.height() / 2; c.drawRoundRect(r, rad, rad, fill); c.drawRoundRect(r, rad, rad, line);
            c.drawText(names[k], r.centerX(), r.centerY() + text.getTextSize() * 0.35f, text);
        }
        if (edSel != null) {   // one frame around the chosen control, or around its whole group
            float l = Float.MAX_VALUE, t = Float.MAX_VALUE, r = -Float.MAX_VALUE, bt = -Float.MAX_VALUE;
            for (Ctl k : ctls) if (inSel(k)) { float[] b = box(k); l = Math.min(l, b[0] - b[2]); t = Math.min(t, b[1] - b[3]); r = Math.max(r, b[0] + b[2]); bt = Math.max(bt, b[1] + b[3]); }
            line.setColor(0xff7fe3f0); line.setStrokeWidth(2 * dp);
            c.drawRoundRect(new RectF(l - 4 * dp, t - 4 * dp, r + 4 * dp, bt + 4 * dp), 12 * dp, 12 * dp, line); }
        line.setStrokeWidth(2 * dp);
        text.setTextSize(getHeight() * 0.032f); text.setAlpha(220);
        c.drawText("拖动控件移动（吸附网格）；第二根手指改大小；−/+ 未选中时改全部；添加/移除按钮；组合键给选中的按钮加同时按的键",
            getWidth() / 2f, getHeight() * 0.18f, text);
    }
}
