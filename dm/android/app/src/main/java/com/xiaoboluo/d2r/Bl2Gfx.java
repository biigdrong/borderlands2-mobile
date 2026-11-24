package com.xiaoboluo.d2r;

import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.system.ErrnoException;
import android.system.Os;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

// [BL2] 设置/图形：Switch 版 Coalesced_INT.bin 里能找到的画质键都摆出来（SystemSettings / SystemSettingsMobile），
// 布尔量做开关、有档位的做横向滑条；保存时改成新的一层 romfs 覆盖层（Bl2Ini），下次启动生效。
// 放大/锐化：渲染比例（ScreenPercentage）+ 引擎的 FSR RCAS 锐化（DM_GFX_SHARPEN，主页面那行是同一个开关）。
// 帧生成：本移植的引擎没有运动矢量，也没有可插入的插帧通道，做不了，页内说明这一点。
final class Bl2Gfx {
    private Bl2Gfx() {}

    static final String P = "gfx_";
    private static final String GROUP = "图形";

    // ---- 布尔开关：ini 键、中文名、基底里没有时当作的值、1 = 后处理（页面里标红）
    static final String[][] BOOLS = {
        {"Bloom", "泛光", "True", "1"},
        {"DepthOfField", "景深", "True", "1"},
        {"AmbientOcclusion", "环境光遮蔽", "True", "1"},
        {"bAllowLightShafts", "光束（体积光）", "True", "1"},
        {"Distortion", "扭曲", "True", "1"},
        {"FilteredDistortion", "过滤扭曲", "True", "1"},
        {"MotionBlur", "运动模糊", "False", "1"},
        {"LensFlares", "镜头光晕", "True", "1"},
        {"FogVolumes", "雾体积", "False", "0"},
        {"AllowRadialBlur", "径向模糊", "True", "1"},
        {"AllowSubsurfaceScattering", "次表面散射", "True", "1"},
        {"AllowImageReflections", "图像反射", "False", "0"},
        {"DynamicLights", "动态光照", "True", "0"},
        {"DynamicShadows", "动态阴影", "True", "0"},
        {"LightEnvironmentShadows", "光环境阴影", "True", "0"},
        {"SHSecondaryLighting", "SH 次级光照", "True", "0"},
        {"DirectionalLightmaps", "方向光贴图", "True", "0"},
        {"StaticDecals", "静态贴花", "True", "0"},
        {"DynamicDecals", "动态贴花", "True", "0"},
        {"UnbatchedDecals", "未批处理贴花", "True", "0"},
        {"bEnableForegroundShadowsOnWorld", "前景阴影", "True", "0"},
        {"bAllowHardwareShadowFiltering", "硬件阴影过滤", "True", "0"},
        {"bEnableVSMShadows", "VSM 阴影", "False", "0"},
        {"bAllowWholeSceneDominantShadows", "整场景主阴影", "True", "0"},
        {"FXAA", "FXAA 抗锯齿", "True", "1"},
        {"HighPrecisionGBuffers", "高精度 G-Buffer", "False", "0"},
        {"UseVsync", "垂直同步", "False", "0"},
    };

    // ---- 档位滑条：ini 键、中文名、档位值、每档的名字（null = 直接显示数值）、写入格式、基底里没有时的默认值
    static final Object[][] STOPS = {
        {"ScreenPercentage", "渲染比例", range(50, 200, 5), null, "pct", 100},
        {"DetailMode", "细节模式", new int[] {0, 1, 2}, new String[] {"低", "中", "高"}, "int", 2},
        {"TextureQuality", "纹理质量", new int[] {0, 1, 2}, new String[] {"低", "中", "高"}, "int", 0},
        {"ViewDistance", "视距", new int[] {0, 1, 2, 3}, new String[] {"低", "中", "高", "极高"}, "int", 2},
        {"MaxAnisotropy", "各向异性过滤", new int[] {1, 2, 4, 8, 16}, new String[] {"1x", "2x", "4x", "8x", "16x"}, "int", 8},
        {"ShadowCascades", "阴影级联", new int[] {1, 2, 3, 4}, new String[] {"1", "2", "3", "4"}, "int", 3},
        {"MaxShadowResolution", "最大阴影分辨率", new int[] {512, 768, 1024, 1536, 2048}, null, "int", 1024},
        {"ShadowDistanceMultiplier", "阴影距离", new int[] {5, 7, 10, 13, 15, 20}, new String[] {"0.5x", "0.7x", "1.0x", "1.3x", "1.5x", "2.0x"}, "tenth", 10},
        {"NumberOfDecals", "贴花数量", new int[] {0, 1, 2}, new String[] {"少", "中", "多"}, "int", 1},
        {"DecalCullDistanceScale", "贴花距离", new int[] {2, 4, 6, 8, 10}, new String[] {"0.2x", "0.4x", "0.6x", "0.8x", "1.0x"}, "tenth", 10},
        {"MaxDrawDistanceScale", "绘制距离", new int[] {5, 7, 10, 13, 15, 20}, new String[] {"0.5x", "0.7x", "1.0x", "1.3x", "1.5x", "2.0x"}, "tenth", 10},
        {"SkeletalMeshLODBias", "骨骼网格 LOD", new int[] {-2, -1, 0, 1, 2}, new String[] {"-2", "-1", "0", "+1", "+2"}, "int", 0},
        {"ParticleLODBias", "粒子 LOD", new int[] {-2, -1, 0, 1, 2}, new String[] {"-2", "-1", "0", "+1", "+2"}, "int", 0},
    };

    static int[] range(int from, int to, int step) {
        int n = (to - from) / step + 1; int[] v = new int[n];
        for (int i = 0; i < n; i++) v[i] = from + i * step;
        return v;
    }
    static String text(String kind, int v) {
        if ("pct".equals(kind)) return Bl2Ini.percent(v);
        if ("tenth".equals(kind)) return Bl2Ini.tenth(v);
        return Integer.toString(v);
    }
    static String label(Object[] spec, int at) {
        int[] stops = (int[]) spec[2]; String[] names = (String[]) spec[3];
        String v = names != null ? names[at] : "pct".equals(spec[4]) ? stops[at] + "%" : Integer.toString(stops[at]);
        return spec[1] + "：" + v;
    }

    // 界面上显示的是 SystemSettings（原版那套完整画质）；保存时把看到的值显式写进两段，
    // 所以「看到什么就生效什么」，不受游戏实际用哪一段的影响。
    static String base(Map<String, String> cur, String key, String dflt) {
        String v = cur.get(key); return v != null ? v : dflt;
    }
    static int baseInt(Map<String, String> cur, String key, int dflt, String kind) {
        String v = cur.get(key);
        if (v == null) return dflt;
        try { double d = Double.parseDouble(v.trim()); return "tenth".equals(kind) ? (int) Math.round(d * 10) : (int) Math.round(d); }
        catch (NumberFormatException e) { return dflt; }
    }
    static int nearest(int[] stops, int v) {
        int b = 0;
        for (int i = 1; i < stops.length; i++) if (Math.abs(stops[i] - v) < Math.abs(stops[b] - v)) b = i;
        return b;
    }

    // ---- 从 prefs 组出要写进 ini 的覆盖表（只含玩家真正改过的键）
    // 和基底相同的值不算改动：旧版「全量保存」在 prefs 里留下的键会被这里过滤掉，不会再把 Mobile 段的值灌进 SystemSettings
    static Map<String, String> overrides(android.app.Activity a, SharedPreferences p) {
        Map<String, String> cur = Bl2Ini.current(a), ov = new LinkedHashMap<>();
        for (String[] b : BOOLS) {
            if (!p.contains(P + b[0])) continue;
            String v = Bl2Ini.bool(p.getBoolean(P + b[0], false));
            if (!v.equalsIgnoreCase(base(cur, b[0], b[2]).trim())) ov.put(b[0], v);
        }
        for (Object[] s : STOPS) {
            String key = (String) s[0];
            if (!p.contains(P + key)) continue;
            int[] stops = (int[]) s[2];
            String v = text((String) s[4], stops[nearest(stops, p.getInt(P + key, stops[0]))]);
            if (!sameNum(v, base(cur, key, text((String) s[4], (Integer) s[5])))) ov.put(key, v);
        }
        return ov;
    }
    static boolean sameNum(String x, String y) {
        try { return Math.abs(Double.parseDouble(x.trim()) - Double.parseDouble(y.trim())) < 1e-6; }
        catch (NumberFormatException e) { return false; }
    }

    // ---- 页
    static GearSettings.Section page() {
        return new GearSettings.Section() {
            final List<Tog> togs = new ArrayList<>();
            final List<Num> nums = new ArrayList<>();
            Map<String, String> cur = new LinkedHashMap<>();
            CheckBox fsr;

            public void build(GearSettings g, LinearLayout box) {
                togs.clear(); nums.clear();   // 页面可以反复打开：不清就会累积上一轮的旧控件
                cur = Bl2Ini.current(g.a);
                SharedPreferences p = g.gamePrefs();

                g.note(box, "这些是游戏自己的画质配置（Coalesced_INT.bin 的 SystemSettings 两段），保存后下次启动生效。"
                    + "汉化文本会保留：改出来的是一层新的覆盖层。");
                Button reset = g.button(box, "一键恢复默认画质");
                reset.setOnClickListener(v -> new AlertDialog.Builder(g.a)
                    .setTitle("恢复默认画质")
                    .setMessage("会删除画质覆盖层，回到游戏原始配置（保留汉化）。确定恢复？")
                    .setNegativeButton("取消", null)
                    .setPositiveButton("恢复", (d, w) -> {
                        // 直接把覆盖层删掉：游戏回到 patch-cn / romfs 里的原始配置，不重新生成一份「等值」文件
                        SharedPreferences.Editor e = p.edit();
                        for (String k : p.getAll().keySet()) if (k.startsWith(P) || "sharpen".equals(k)) e.remove(k);
                        e.apply();
                        Bl2Ini.remove(g.a);
                        // 覆盖层已删，基底换回干净的那份：按它重新算一遍所有开关/滑条，别把旧值当默认
                        cur = Bl2Ini.current(g.a);
                        for (Tog t : togs) {
                            t.base = "True".equalsIgnoreCase(base(cur, t.key, t.dflt));
                            t.c.setChecked(t.base);
                        }
                        for (Num n : nums) {
                            n.base = nearest(n.stops, baseInt(cur, (String) n.spec[0], (Integer) n.spec[5], n.kind));
                            n.at = n.base;   // base 是档位下标，不是档位值
                            n.bar.setProgress(n.at);
                            n.label.setText(label(n.spec, n.at));
                        }
                        if (fsr != null) fsr.setChecked(false);
                        if (sharpenBar != null) { sharpenAt = 0; sharpenBar.setProgress(0); sharpenLabel.setText("锐化（FSR RCAS）：关"); }
                        g.toast("已删除画质覆盖层，恢复原始配置（下次启动生效）", true);
                    })
                    .show());

                g.heading(box, "渲染与放大（下次启动生效）");
                Num scale = null;
                for (Object[] s : STOPS) if ("ScreenPercentage".equals(s[0])) scale = number(g, box, p, s);
                g.note(box, "低于 100% = 3D 降分辨率，配下面的「锐化（FSR RCAS）」补细节；高于 100% = 超采样（DSR 风格），"
                    + "降采样回 720p，画面更干净但更吃 GPU。");
                fsr = g.check(box, "FSR 1 放大（EASU）", p.getBoolean("gfx_fsr", false));
                g.note(box, "开：窗口按屏幕分辨率走，每个像素的帧用 FSR 1 的 EASU 放上去（和 Citron 的 FSR 同一个阶段），"
                    + "再叠下面的 RCAS 锐化。关：保持现状，由显示控制器放大。仅 8 位 RGBA 画面；带少量 GPU 开销。");
                sharpen(g, box, p);
                if (scale != null) nums.add(scale);

                g.heading(box, "效果开关（红字 = 后处理，关掉最省 GPU；都需重启）");
                for (String[] b : BOOLS) {
                    boolean dflt = "True".equalsIgnoreCase(base(cur, b[0], b[2]));
                    boolean on = p.contains(P + b[0]) ? p.getBoolean(P + b[0], dflt) : dflt;
                    CheckBox c = g.check(box, b[1], on);
                    if ("1".equals(b[3])) c.setTextColor(0xFFFF5252);
                    togs.add(new Tog(b[0], c, dflt, b[2]));
                }

                g.heading(box, "画质档位（下次启动生效）");
                for (Object[] s : STOPS) if (!"ScreenPercentage".equals(s[0])) nums.add(number(g, box, p, s));

                g.heading(box, "其它");
                g.note(box, "帧生成：本移植没有时域上采样/运动矢量，也没有可以插帧的呈现通道，物理上做不了，所以没有这一项。");
            }

            // 渲染比例之外的那条：引擎的 RCAS 锐化（pref "sharpen"，和主页面同一项；拖动只改界面，保存时才写）
            TextView sharpenLabel; SeekBar sharpenBar; int sharpenAt;
            void sharpen(GearSettings g, LinearLayout box, SharedPreferences p) {
                String[] names = {"关", "低", "中", "高"};
                sharpenAt = Math.max(0, Math.min(3, p.getInt("sharpen", 0)));
                sharpenLabel = g.text(box, "锐化（FSR RCAS）：" + names[sharpenAt]);
                sharpenBar = new SeekBar(g.a); sharpenBar.setMax(3); sharpenBar.setProgress(sharpenAt); box.addView(sharpenBar);
                sharpenBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                    public void onProgressChanged(SeekBar sb, int v, boolean user) {
                        sharpenAt = v; sharpenLabel.setText("锐化（FSR RCAS）：" + names[v]);
                    }
                    public void onStartTrackingTouch(SeekBar sb) {}
                    public void onStopTrackingTouch(SeekBar sb) {}
                });
            }

            Num number(GearSettings g, LinearLayout box, SharedPreferences p, Object[] spec) {
                String key = (String) spec[0]; int[] stops = (int[]) spec[2]; String kind = (String) spec[4];
                int b = nearest(stops, baseInt(cur, key, (Integer) spec[5], kind));
                int at = p.contains(P + key) ? nearest(stops, p.getInt(P + key, stops[b])) : b;
                Num n = new Num(spec, stops, kind, b, at);
                n.label = g.text(box, label(spec, at));
                n.bar = new SeekBar(g.a); n.bar.setMax(stops.length - 1); n.bar.setProgress(at); box.addView(n.bar);
                n.bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                    public void onProgressChanged(SeekBar sb, int v, boolean user) {
                        n.at = v; n.label.setText(label(spec, v));
                    }
                    public void onStartTrackingTouch(SeekBar sb) {}
                    public void onStopTrackingTouch(SeekBar sb) {}
                });
                return n;
            }

            public void save(GearSettings g, SharedPreferences.Editor game, SharedPreferences.Editor pad) {
                if (fsr != null) game.putBoolean("gfx_fsr", fsr.isChecked());
                game.remove(P + "wide");   // 旧版「真宽屏」勾选已并入「画面形状」，清掉残留
                if (sharpenBar != null) game.putInt("sharpen", sharpenAt);
                // 只写玩家真正改过的键：和界面初始值相同的就不碰，避免把 Mobile 段整套覆盖成 SystemSettings 的值
                for (Tog t : togs) {
                    if (t.c.isChecked() != t.base) game.putBoolean(P + t.key, t.c.isChecked()); else game.remove(P + t.key);
                }
                for (Num n : nums) {
                    String key = (String) n.spec[0];
                    if (n.at != n.base) game.putInt(P + key, n.stops[n.at]); else game.remove(P + key);
                }
            }

            public void after(GearSettings g) {
                Bl2Ini.sync(g.a, overrides(g.a, g.gamePrefs()));
                g.toast("图形设置已保存，下次启动生效", true);
            }

            public void env(GearSettings g) throws ErrnoException {
                boolean on = g.gamePrefs().getBoolean("gfx_fsr", false);
                Os.setenv("DM_GFX_FSR", on ? "1" : "0", true);
                // 锐化：和 GearPages.sharpen 同一组值（BL2 没有那一行，这一行必须自己导出，否则滑条无效）
                int sh = g.gamePrefs().getInt("sharpen", 0);
                if (sh > 0 && sh < GearPages.SHARPEN_STOPS.length) Os.setenv("DM_GFX_SHARPEN", GearPages.SHARPEN_STOPS[sh], true);
                else Os.unsetenv("DM_GFX_SHARPEN");
                Os.setenv("DM_BL2_WIDE", g.gamePrefs().getInt("aspect", 0) == 2 ? "1" : "0", true);   // [BL2] 宽屏只认「画面形状」
                Bl2Ini.sync(g.a, overrides(g.a, g.gamePrefs()));
            }
        };
    }

    static final class Tog {
        final String key; final CheckBox c; final String dflt; boolean base;   // dflt = 键不存在时的原始值
        Tog(String k, CheckBox c, boolean b, String d) { key = k; this.c = c; base = b; dflt = d; }
    }
    static final class Num {
        final Object[] spec; final int[] stops; final String kind; int base;
        TextView label; SeekBar bar; int at;
        Num(Object[] s, int[] st, String k, int b, int a) { spec = s; stops = st; kind = k; base = b; at = a; }
    }
}
