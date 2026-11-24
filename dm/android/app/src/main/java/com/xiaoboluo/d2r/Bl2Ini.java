package com.xiaoboluo.d2r;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Environment;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

// [BL2] 图形设置落到游戏自己的 ini：Switch 版的配置都打包在 WillowGame/CookedSwitch/Coalesced_INT.bin（UE3 FConfigCacheIni：
// 文件数、每个文件一条路径、段数、每段的键值，字符串是 int32 长度 + ASCII 或 UTF-16LE）。这里读汉化覆盖层（patch-cn）里的那份当基底，
// 只改写 Switch-WillowEngine.ini 的 SystemSettings / SystemSettingsMobile 两段里被改过的键，写成一层新的覆盖层 patch-gfx；
// 原文件其余字节原样拷贝，所以汉字文本不受影响。原生端起机时把这层排到 DM_ROMFS_OVERLAY 最前（jni_android.c overlay_extra）。
final class Bl2Ini {
    private Bl2Ini() {}

    static final String REL = "WillowGame/CookedSwitch/Coalesced_INT.bin";
    private static final String ENGINE_INI = "Switch-WillowEngine.ini";
    private static final String[] SECTIONS = {"SystemSettings", "SystemSettingsMobile"};
    private static final String SIG = "gfx_ini_sig";
    private static final String MARKER = "dm/romfs-overlay-extra";

    static File dataDir(Activity a) {
        return new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), DmActivity.DATA_DIR);
    }
    static File layerDir(Activity a) { return new File(dataDir(a), "patch-gfx"); }
    static File outFile(Activity a) { return new File(layerDir(a), REL); }

    // ---- 基底：dm/env 里 DM_ROMFS_OVERLAY 的第一层含 Coalesced 的那个；没有就 patch-cn，再没有就 romfs
    static File baseFile(Activity a) {
        List<File> seen = new ArrayList<>();
        for (File env : new File[] {new File(a.getFilesDir(), "dm/env"), ext(a, "dm/env"), new File(dataDir(a), "dm/env")}) {
            if (env == null || !env.isFile()) continue;
            try (RandomAccessFile f = new RandomAccessFile(env, "r")) {
                String line;
                while ((line = f.readLine()) != null) {
                    int at = line.indexOf("DM_ROMFS_OVERLAY=");
                    if (at < 0) continue;
                    for (String layer : line.substring(at + 17).trim().split(":")) {
                        if (layer.isEmpty()) continue;
                        File c = new File(new File(layer), REL);
                        if (c.isFile()) { if (!seen.contains(c)) seen.add(c); }
                    }
                }
            } catch (IOException | RuntimeException e) { /* 下一处 */ }
        }
        List<File> cands = new ArrayList<>(seen);
        cands.add(new File(new File(dataDir(a), "patch-cn"), REL));
        cands.add(new File(new File(dataDir(a), "romfs"), REL));
        File layer = layerDir(a).getAbsoluteFile();
        for (File c : cands) if (c.isFile() && !c.getParentFile().getParentFile().getParentFile().getAbsoluteFile().equals(layer)) return c;
        return null;
    }
    private static File ext(Activity a, String rel) { File e = a.getExternalFilesDir(null); return e == null ? null : new File(e, rel); }

    // ---- 基底里两段的当前值（缓存到文件身份变化为止）
    private static String cacheKey; private static Map<String, String> cache;
    static Map<String, String> current(Activity a) {
        File b = baseFile(a);
        if (b == null) return new LinkedHashMap<>();
        String key = b.getAbsolutePath() + "|" + b.length() + "|" + b.lastModified();
        if (key.equals(cacheKey) && cache != null) return cache;
        Map<String, String> m = new LinkedHashMap<>();
        try {
            byte[] raw = readAll(b);
            int nf = (raw.length >= 4) ? (raw[0] & 0xff) | (raw[1] & 0xff) << 8 | (raw[2] & 0xff) << 16 | (raw[3] & 0xff) << 24 : -1;
            readValues(raw, m); cacheKey = key; cache = m;
            android.util.Log.i("dm", "图形 ini 基底 " + b + "（" + raw.length + " B, " + nf + " 个文件, " + m.size() + " 键）");
        }
        catch (IOException | RuntimeException e) { android.util.Log.e("dm", "图形 ini 读取失败: " + e, e); }
        return m;
    }

    // ---- 写（或删）覆盖层；ov 为空 = 全部默认，删掉这层
    static void sync(Activity a, Map<String, String> ov) {
        File base = baseFile(a), out = outFile(a);
        SharedPreferences p = a.getSharedPreferences("doom_graphics", Activity.MODE_PRIVATE);
        if (base == null) { android.util.Log.e("dm", "图形 ini：找不到基底 Coalesced_INT.bin"); return; }
        if (ov.isEmpty()) { remove(a); p.edit().putString(SIG, "").apply(); return; }
        String sig = base.getAbsolutePath() + "|" + base.length() + "|" + base.lastModified() + "|" + ov;
        if (sig.equals(p.getString(SIG, "")) && out.isFile()) return;   // 没变：上次写的还在
        try {
            byte[] d = readAll(base), r = rewrite(d, ov);
            File dir = out.getParentFile();
            if (dir != null && !dir.isDirectory() && !dir.mkdirs()) throw new IOException("mkdir " + dir);
            File tmp = new File(out.getAbsolutePath() + ".tmp");
            try (FileOutputStream fo = new FileOutputStream(tmp)) { fo.write(r); }
            if (out.exists() && !out.delete()) throw new IOException("replace " + out);
            if (!tmp.renameTo(out)) throw new IOException("rename " + tmp);
            writeMarker(a);
            p.edit().putString(SIG, sig).apply();
            android.util.Log.i("dm", "图形覆盖层 " + out + "（" + r.length + " B，" + ov.size() + " 项）");
        } catch (IOException | RuntimeException e) {
            android.util.Log.e("dm", "图形覆盖层写入失败: " + e);
        }
    }
    static void remove(Activity a) {
        deleteTree(layerDir(a));
        for (File m : markers(a)) if (m.exists() && !m.delete()) android.util.Log.w("dm", "删除失败 " + m);
        android.util.Log.i("dm", "图形覆盖层已删除：" + layerDir(a) + "（游戏回到 patch-cn / romfs 的原始配置）");
    }
    private static File[] markers(Activity a) { return new File[] {new File(a.getFilesDir(), MARKER), ext(a, MARKER)}; }
    private static void writeMarker(Activity a) throws IOException {
        String path = layerDir(a).getAbsolutePath();
        for (File m : markers(a)) {
            if (m == null) continue;
            File dir = m.getParentFile();
            if (dir != null && !dir.isDirectory() && !dir.mkdirs()) throw new IOException("mkdir " + dir);
            try (FileOutputStream fo = new FileOutputStream(m)) { fo.write((path + "\n").getBytes(StandardCharsets.UTF_8)); }
        }
    }
    private static void deleteTree(File f) {
        File[] list = f.isDirectory() ? f.listFiles() : null;
        if (list != null) for (File c : list) deleteTree(c);
        if (f.exists() && !f.delete()) android.util.Log.w("dm", "delete " + f);
    }

    // ---- 解析 / 改写
    private static byte[] readAll(File f) throws IOException {
        byte[] d = new byte[(int) f.length()];
        int o = 0;
        try (java.io.FileInputStream in = new java.io.FileInputStream(f)) {
            for (int n; o < d.length && (n = in.read(d, o, d.length - o)) > 0; ) o += n;
        }
        if (o != d.length) throw new IOException("短读 " + o + "/" + d.length + "：" + f.getName());   // 没读全就别拿半份文件去解析
        return d;
    }

    static final class Rd {
        final byte[] d; int o;
        Rd(byte[] b) { d = b; }
        int i32() { int v = (d[o] & 0xff) | (d[o + 1] & 0xff) << 8 | (d[o + 2] & 0xff) << 16 | (d[o + 3] & 0xff) << 24; o += 4; return v; }
        String str() {
            int n = i32();
            int size = n < 0 ? -n * 2 : n;
            if (n == Integer.MIN_VALUE || size < 0 || o + (long) size > d.length)
                throw new IllegalStateException("字符串长度 " + n + " 在偏移 " + o + "（共 " + d.length + "）");
            String s;
            if (n < 0) { int u = -n; s = new String(d, o, u * 2, StandardCharsets.UTF_16LE); o += u * 2; }
            else { s = new String(d, o, n, StandardCharsets.ISO_8859_1); o += n; }
            return s.endsWith("\u0000") ? s.substring(0, s.length() - 1) : s;
        }
        void skipStr() { int n = i32(); o += n < 0 ? -n * 2 : n; }
    }
    private static void wInt(ByteArrayOutputStream o, int v) { o.write(v); o.write(v >>> 8); o.write(v >>> 16); o.write(v >>> 24); }
    private static void wStr(ByteArrayOutputStream o, String s) {
        if (s.endsWith("\u0000")) s = s.substring(0, s.length() - 1);
        byte[] b = (s + "\u0000").getBytes(StandardCharsets.UTF_16LE);
        wInt(o, -(b.length / 2)); o.write(b, 0, b.length);
    }

    private static void readValues(byte[] d, Map<String, String> out) {
        Rd r = new Rd(d);
        int nfile = r.i32();
        for (int i = 0; i < nfile; i++) {
            String name;
            try {
                name = r.str();
                int nsec = r.i32();
                if (!name.endsWith(ENGINE_INI)) { skipBody(r, nsec); continue; }   // 本地化文件整段跳过，不解码
                for (int s = 0; s < nsec; s++) {
                    String sname = r.str();
                    boolean want = sname.equals(SECTIONS[0]);   // SystemSettings = 原版那套完整画质（Mobile 段是低配派生）
                    int nk = r.i32();
                    for (int k = 0; k < nk; k++) {
                        String key = r.str(), val = r.str();
                        if (want) out.put(key, val);
                    }
                }
            } catch (RuntimeException e) {
                android.util.Log.e("dm", "图形 ini 第 " + i + "/" + nfile + " 个文件读坏（偏移 " + r.o + "，共 " + d.length + "）", e);
                throw e;
            }
        }
        android.util.Log.i("dm", "图形 ini 解析完成: files=" + nfile + " end=" + r.o + "/" + d.length + " 键=" + out.size());
    }

    static byte[] rewrite(byte[] d, Map<String, String> ov) {
        Rd r = new Rd(d);
        ByteArrayOutputStream out = new ByteArrayOutputStream(d.length + 4096);
        int nfile = r.i32(); wInt(out, nfile);
        for (int i = 0; i < nfile; i++) {
            int start = r.o; String name = r.str(); out.write(d, start, r.o - start);
            int nsec = r.i32(); wInt(out, nsec);
            boolean target = name.endsWith(ENGINE_INI);
            if (!target) {   // 其余文件（本地化文本等）原样拷贝，不解析键值
                int body = r.o; skipBody(r, nsec); out.write(d, body, r.o - body); continue;
            }
            for (int s = 0; s < nsec; s++) {
                int ss = r.o; String sname = r.str(); out.write(d, ss, r.o - ss);
                boolean want = sname.equals(SECTIONS[0]) || sname.equals(SECTIONS[1]);
                int nk = r.i32(); wInt(out, nk);
                for (int k = 0; k < nk; k++) {
                    int ks = r.o; String key = r.str(); out.write(d, ks, r.o - ks);
                    int vs = r.o; String val = r.str();
                    String nv = want ? ov.get(key) : null;
                    if (nv != null && !nv.equals(val)) wStr(out, nv); else out.write(d, vs, r.o - vs);
                }
            }
        }
        return out.toByteArray();
    }
    private static void skipBody(Rd r, int nsec) {
        for (int s = 0; s < nsec; s++) {
            r.skipStr();
            int nk = r.i32();
            for (int k = 0; k < nk; k++) { r.skipStr(); r.skipStr(); }
        }
    }

    // ---- 值的格式（写进 ini 的字符串）
    static String bool(boolean on) { return on ? "True" : "False"; }
    static String percent(int v) { return String.format(Locale.ROOT, "%d.000000", v); }
    static String tenth(int v) { return String.format(Locale.ROOT, "%.1f", v / 10.0); }
}
