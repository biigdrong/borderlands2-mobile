package com.xiaoboluo.d2r;

import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;

// [BL2] 作弊入口：页面上按按钮 = 往游戏数据目录写一行 cheat.req；原生层（hle_bl2_probe.c）在出图线程里取走并执行。
// 命令就是游戏自带的 WillowCheatManager / CheatManager exec 函数名（离线的 cheats.txt 里有全部）。
// 第一次用时原生层要扫一遍内存定位 UE3 的名字表，所以打开这一页会写 cheat.on 让它提前扫完（约几秒，之后都是即时执行）。
final class Bl2Cheat {
    private Bl2Cheat() {}

    static final String ON = "cheat.on", REQ = "cheat.req", LOG = "cheat.log";
    // 无参命令（反复执行就是在开/关之间切）；带参数的下面另有输入框
    static final String[] QUICK = {
        "God", "Ghost", "Fly", "Walk", "AllWeapons", "AllAmmo", "Amphibious",
        "Avatar", "PlayersOnly", "KillAll", "FreezeFrame", "SuspendAI", "Loaded",
    };

    static File dir(android.app.Activity a) { return Bl2Ini.dataDir(a); }

    // 写一个小文件（同目录临时文件 + 改名，原生层不会读到写了一半的内容）
    static boolean put(android.app.Activity a, String name, String text) {
        File d = dir(a);
        if (!d.isDirectory() && !d.mkdirs()) return false;
        File out = new File(d, name), tmp = new File(d, name + ".tmp");
        try (FileOutputStream fo = new FileOutputStream(tmp)) {
            fo.write(text.getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) { return false; }
        if (out.exists() && !out.delete()) return false;
        return tmp.renameTo(out);
    }
    static boolean enable(android.app.Activity a) { return put(a, ON, "1\n"); }
    static boolean send(android.app.Activity a, String cmd) { return put(a, REQ, cmd + "\n"); }

    // cheat.log 的末尾（原生层往里追加每次执行的结果）
    static String tail(android.app.Activity a, int max) {
        File f = new File(dir(a), LOG);
        if (!f.isFile()) return "（还没有执行记录）";
        try (RandomAccessFile r = new RandomAccessFile(f, "r")) {
            long n = r.length(), from = Math.max(0, n - max);
            byte[] b = new byte[(int) (n - from)];
            r.seek(from);
            r.readFully(b);
            String s = new String(b, StandardCharsets.UTF_8);
            return s.trim().isEmpty() ? "（还没有执行记录）" : s.trim();
        } catch (IOException e) { return "读取失败：" + e; }
    }

    static GearSettings.Section page() {
        return new GearSettings.Section() {
            TextView status;

            public void build(final GearSettings g, LinearLayout box) {
                boolean on = enable(g.a);   // 提前触发一次扫描（已在扫/扫过就什么也不做）
                g.note(box, "这些是游戏自带的开发者命令（WillowCheatManager / CheatManager）。按下结果里的命令会写进游戏的请求文件，"
                    + "由原生层在游戏线程里执行；God / Ghost / Fly 这类是开关，再点一次就关。");
                g.note(box, on ? "已请求原生层准备（第一次约几秒扫内存，之后即时）。命令在局内才有效果。"
                    : "写不进数据目录：" + dir(g.a) + "（检查存储权限）。");

                g.heading(box, "搜索命令（中文或英文）");
                final EditText q = new EditText(g.a);
                q.setHint("无敌 / 钱 / 武器 / 传送 / god …");
                q.setSingleLine(true);
                q.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
                box.addView(q);
                final LinearLayout out = new LinearLayout(g.a);
                out.setOrientation(LinearLayout.VERTICAL);
                box.addView(out);
                Button go = g.button(box, "搜索");
                go.setOnClickListener(v -> results(g, out, q.getText().toString()));
                q.setOnEditorActionListener((v, action, e) -> { results(g, out, q.getText().toString()); return true; });
                results(g, out, "");

                g.heading(box, "天气 / 时间");
                g.note(box, "BL2 基础图没有天气系统（雨/沙暴/雷暴都不存在），只有冰原 DLC 的雪天；"
                    + "能循环的是时间（SetTimeOfDay），每 5 秒推 3 小时，部分图天空/雾会跟着变。");
                g.button(box, "列出本图天气模板").setOnClickListener(v -> fire(g, "weather"));
                g.button(box, "时间循环（每 5 秒，开关）").setOnClickListener(v -> fire(g, "cycle"));

                g.heading(box, "AI 队友（M2）");
                g.note(box, "先对着一个敌人（准星/最近目标），再点「把这个敌人变成队友」——它走游戏自己的 AI，会去打其它敌人。"
                    + "「全场敌人变队友」会把当前地图所有 WillowAIPawn 一次改阵营。");
                g.button(box, "把这个敌人变成队友").setOnClickListener(v -> fire(g, "ally"));
                g.button(box, "全场敌人变成队友").setOnClickListener(v -> fire(g, "allyall"));

                g.heading(box, "快捷开关");
                for (final String cmd : QUICK) {
                    Button b = g.button(box, cmd);
                    b.setOnClickListener(v -> fire(g, cmd));
                }

                g.heading(box, "手动输入");
                g.note(box, "带一个数字参数时例如 givecash 99999、slomo 2、setspeed 1.5（整数/小数都行）。");
                final EditText in = new EditText(g.a);
                in.setHint("god / givecash 99999 / slomo 2");
                in.setSingleLine(true);
                in.setImeOptions(EditorInfo.IME_ACTION_DONE);
                box.addView(in);
                Button send = g.button(box, "发送命令");
                send.setOnClickListener(v -> {
                    String c = in.getText().toString().trim();
                    if (c.isEmpty()) { g.toast("先输入命令", false); return; }
                    fire(g, c);
                });

                g.heading(box, "执行记录");
                g.button(box, "刷新执行记录").setOnClickListener(v -> { if (status != null) status.setText(tail(g.a, 2400)); });
                status = g.note(box, tail(g.a, 2400));
            }

            void fire(GearSettings g, String cmd) {
                boolean ok = send(g.a, cmd);
                g.toast(ok ? "已发送：" + cmd : "写入失败", false);
                if (status == null) return;
                status.setText(tail(g.a, 2400));
                // 原生层每 16 帧取一次请求、日志稍后才落盘：1.5s / 4s 各自动刷一次（重扫时也能看到补执行结果）
                for (int ms : new int[] {1500, 4000}) status.postDelayed(() -> status.setText(tail(g.a, 2400)), ms);
            }

            // 中文/英文搜索：先在有说明的条目里找，再用全部命令名补齐；结果限 30 条，每条点一下就发送
            void results(final GearSettings g, LinearLayout out, String query) {
                out.removeAllViews();
                String q = query.trim().toLowerCase(java.util.Locale.ROOT);
                java.util.List<String[]> hits = new java.util.ArrayList<>();
                for (String[] e : Bl2CheatBook.INFO)
                    if (q.isEmpty() || (e[0] + " " + e[1] + " " + e[2] + " " + e[4]).toLowerCase(java.util.Locale.ROOT).contains(q))
                        hits.add(e);
                java.util.Set<String> known = new java.util.HashSet<>();
                for (String[] e : Bl2CheatBook.INFO) known.add(e[0].toLowerCase(java.util.Locale.ROOT));
                for (String n : Bl2CheatBook.NAMES) {
                    if (q.isEmpty() || !n.toLowerCase(java.util.Locale.ROOT).contains(q)) continue;
                    if (known.contains(n.toLowerCase(java.util.Locale.ROOT))) continue;
                    hits.add(new String[] {n, "游戏自带命令（无中文说明）", n, n, ""});
                }
                if (hits.isEmpty()) {
                    TextView t = g.note(out, "没有匹配「" + query.trim() + "」的命令");
                    t.setTextColor(0xFFFF5252);
                    return;
                }
                int n = Math.min(hits.size(), 30);
                for (int i = 0; i < n; i++) {
                    String[] e = hits.get(i);
                    final String cmd = e[3] != null && !e[3].isEmpty() ? e[3] : e[0];
                    Button b = g.button(out, e[0] + " · " + e[1] + "\n用法：" + e[2] + "    示例：" + cmd);
                    b.setOnClickListener(v -> fire(g, cmd));
                }
                if (hits.size() > n) g.note(out, "还有 " + (hits.size() - n) + " 条，输入更具体的关键词再搜");
            }
        };
    }
}
