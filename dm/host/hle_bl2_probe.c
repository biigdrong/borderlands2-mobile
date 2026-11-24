// [BL2] M0 探针：找 UE3 �?GNames（名字表）锚点，只为“进程内 AI 队友”做可行性验证�?

// M0 probe: locate UE3's GNames (the name table) as the first anchor for in-process AI teammates.

//

// 触发：游戏数据目录（Download/Borderlands2Mobile）里�?probe.on 时启用，结果写到同目�?probe-<�?.txt

// Trigger: a "probe.on" file in the game data directory; the report goes to probe-<seconds>.txt there.

// 只读：不写游戏内存，也不装任何信号处理器；内存用 process_vm_readv 拷出来再扫，

// 坏页/�?unmap 的页只会让那一次读失败（返�?EFAULT），不可能让游戏进程崩溃�?

// Read-only: nothing is written into the game and no signal handler is installed; memory is copied out with

// process_vm_readv, so an unreadable page only fails that one read (EFAULT) instead of killing the process.

#ifdef DM_GAME_BL2

#include "hle.h"

#include <stdio.h>

#include <stdlib.h>

#include <string.h>

#include <stdint.h>

#include <unistd.h>

#include <pthread.h>

#include <errno.h>

#include <sys/mman.h>

#include <stdarg.h>

#include <time.h>

#include <sys/uio.h>

#include <sys/stat.h>
// bionic 在部�?NDK 头里不声明它（API 23 起有实现），这里自己声明
extern ssize_t process_vm_readv(pid_t pid, const struct iovec *local_iov, unsigned long liovcnt,                                const struct iovec *remote_iov, unsigned long riovcnt, unsigned long flags);

#define MAXREG 8192

#define PBUF (256u << 10)
typedef struct {
 uint64_t lo, hi;
 int w, file;
 }
 reg_t;
static reg_t g_reg[MAXREG];
static int g_nreg;
static char g_dir[1024];
static uint8_t g_pbuf[PBUF];
   // 分块拷贝缓冲（只给探针线程用�?| chunk buffer, probe thread only
static int g_einval;
           // process_vm_readv 不可�?| process_vm_readv unusable
static int read_maps(void) {
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[512];
 g_nreg = 0;
    while (fgets(line, sizeof line, f) && g_nreg < MAXREG) {
        unsigned long long lo, hi;
 char perm[8] = {
0}
;
        if (sscanf(line, "%llx-%llx %7s", &lo, &hi, perm) != 3) continue;
        if (perm[0] != 'r') continue;
        if (strstr(line, "[vvar]") || strstr(line, "[vsyscall]")) continue;
        g_reg[g_nreg].lo = lo;
 g_reg[g_nreg].hi = hi;
 g_reg[g_nreg].w = perm[1] == 'w';
        g_reg[g_nreg].file = strchr(line, '/') != NULL;
   // 有路�?= 文件映射（末页可能超出文件长度）        
g_nreg++;
    }
    fclose(f);
    return g_nreg;
}

// 从自己的地址空间安全拷出 n 字节；读不了返回 0，绝不触发信�?

// Copy n bytes out of our own address space; an unreadable page returns 0, never a signal.
static int safe_read(uint64_t src, void *dst, size_t n) {
    if (g_einval) return 0;
    struct iovec l, r;
    l.iov_base = dst;
 l.iov_len = n;
    r.iov_base = (void *)(uintptr_t)src;
 r.iov_len = n;
    ssize_t k = process_vm_readv(getpid(), &l, 1, &r, 1, 0);
    if (k == (ssize_t)n) return 1;
    if (k < 0 && (errno == ENOSYS || errno == EPERM || errno == EINVAL)) g_einval = 1;
    return 0;
}

// 读一段，坏页�?0（按页补救，只有那几页的数据丢失�?
static void read_soft(uint64_t src, uint8_t *dst, size_t n) {
    if (safe_read(src, dst, n)) return;
    for (size_t off = 0;
 off < n;
 off += 4096) {
        size_t m = n - off < 4096 ? n - off : 4096;
        if (!safe_read(src + off, dst + off, m)) memset(dst + off, 0, m);
    }
}
static int clean_text(const char *b, int n) {
    // UE3 的名字只含字�?数字/下划�?�?连字符，且至�?2 个字符；放太宽会把“指向任意短字符串”的指针也算进来    
if (n < 3 || n > 64 || b[n - 1] != 0) return 0;
    for (int i = 0;
 i < n - 1;
 i++) {
        unsigned char c = (unsigned char)b[i];
        int ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-';
        if (!ok) return 0;
    }
    return 1;
}

// GNames 的条目在运行时是 UE3 �?FNameEntry：int32 Index + NUL 结尾文本（指针指�?Index）；

// 包内格式�?int32 长度（含 NUL�? 文本；也接受指针直接指向字符。三种都认�?
static int name_at(uint64_t p, char *out, size_t cap) {
    char b[65];
    int32_t n = 0;
    // (d) UE3 64 �?FNameEntry：Index(4) + 填充(4) + HashNext(8) + 文本（探针实测头大小 = 16�?    
if (safe_read(p, &n, 4) && n >= 0 && n < 4000000 && safe_read(p + 16, b, sizeof b)) {
        size_t L = strnlen(b, sizeof b);
        if (L > 0 && L < sizeof b && clean_text(b, (int)L + 1)) {
 snprintf(out, cap, "%s", b);
 return 1;
 }
    }
    // (b) UE3 32 位：Index(4) + 文本    
if (safe_read(p, &n, 4) && n >= 0 && n < 4000000 && safe_read(p + 4, b, sizeof b)) {
        size_t L = strnlen(b, sizeof b);
        if (L > 0 && L < sizeof b && clean_text(b, (int)L + 1)) {
 snprintf(out, cap, "%s", b);
 return 1;
 }
    }
    // (a) 包格式：int32 长度（含 NUL�? 文本    
if (safe_read(p - 4, &n, 4) && n > 0 && n <= 64 && safe_read(p, b, (size_t)n) && clean_text(b, n)) {
 snprintf(out, cap, "%s", b);
 return 1;
 }
    // (c) 指针直接指向字符    
if (safe_read(p, b, sizeof b)) {
        size_t L = strnlen(b, sizeof b);
        if (L > 0 && L < sizeof b && clean_text(b, (int)L + 1)) {
 snprintf(out, cap, "%s", b);
 return 1;
 }
    }
    return 0;
}
static int is_name_entry(uint64_t p) {
 char b[80];
 return name_at(p, b, sizeof b);
 }

// 一个区域找一个关键字：分块拷贝，块尾留重叠；坏块只丢那几�?
static int hits_region(int r, const char *needle, size_t len, uint64_t *hits, int nh, int max) {
    uint64_t lo = g_reg[r].lo, hi = g_reg[r].hi - (g_reg[r].file ? 4096 : 0);
    if (hi < lo + len) return -1;
    int added = 0;
    for (uint64_t off = 0;
 off + len <= hi - lo && nh + added < max;
 ) {
        size_t n = (hi - lo - off) < PBUF ? (size_t)(hi - lo - off) : PBUF;
        read_soft(lo + off, g_pbuf, n);
        for (size_t i = 0;
 i + len <= n;
 i++)            if (g_pbuf[i] == (uint8_t)needle[0] && !memcmp(g_pbuf + i, needle, len)) {
                hits[nh + added++] = lo + off + i;
                if (nh + added >= max) break;
            }
        if (n <= len) break;
        off += n - (len - 1);
    }
    return added;
}

// 一个可写区域里找“指�?center±tol 的指�?+ 其后连续的名字条目�?
static void slots_region(int r, uint64_t center, uint64_t tol, uint64_t *best_n, uint64_t *best_at, uint64_t *best_v) {
    if (!g_reg[r].w) return;
    uintptr_t own = (uintptr_t)__builtin_frame_address(0);
    if (own >= g_reg[r].lo && own < g_reg[r].hi) return;
   // 跳过探针自己的栈（会匹配�?hits[] 自己�?    
uint64_t lo_v = center > tol ? center - tol : 0, hi_v = center + tol;
    uint64_t lo = (g_reg[r].lo + 7) & ~(uint64_t)7, hi = g_reg[r].hi - (g_reg[r].file ? 4096 : 0);
    if (hi <= lo + 8) return;
    for (uint64_t off = 0;
 off + 8 <= hi - lo;
 ) {
        size_t n = (hi - lo - off) < PBUF ? (size_t)(hi - lo - off) : PBUF;
        n &= ~(size_t)7;
        if (!n) break;
        read_soft(lo + off, g_pbuf, n);
        for (size_t i = 0;
 i + 8 <= n;
 i += 8) {
            uint64_t v;
 memcpy(&v, g_pbuf + i, 8);
            if (v < lo_v || v > hi_v) continue;
            int cnt = 1;
            uint64_t q = lo + off + i + 8, w;
            for (int k = 1;
 k < 64 && q + 8 <= hi && safe_read(q, &w, 8) && is_name_entry(w);
 k++) {
 cnt++;
 q += 8;
 }
            if ((uint64_t)cnt > *best_n) {
 *best_n = cnt;
 *best_at = lo + off + i;
 *best_v = v;
 }
        }
        off += n;
    }
}

// 候选数组前后各 8 个名字（安全读）
static int names_around(uint64_t best_at, char names[16][72]) {
    int nn = 0;
    for (int k = -8;
 k < 8;
 k++) {
        uint64_t q = best_at + (uint64_t)(int64_t)(k * 8), v;
        if (!safe_read(q, &v, 8) || !v) continue;
        char nm[72];
        if (!name_at(v, nm, sizeof nm)) continue;
        if (nn < 16) {
 snprintf(names[nn], sizeof names[0], "[%+d] %s", k, nm);
 ++nn;
 }
    }
    return nn;
}
static int dir_ok(const char *p) {
 return p && *p && access(p, W_OK) == 0;
 }
static int find_dir(void) {
   // <data>/aoc �?<data>/romfs：去掉最后一级得到数据目�?    
const char *c[] = {
getenv("DM_AOC"), getenv("DM_ROMFS"), getenv("DM_SAVE"), getenv("DM_RUNTIME_DIR")}
;
    for (int i = 0;
 i < 4;
 i++) {
        if (!c[i] || !*c[i]) continue;
        snprintf(g_dir, sizeof g_dir, "%s", c[i]);
        char *s = strrchr(g_dir, '/');
        if (s && s != g_dir) *s = 0;
        if (dir_ok(g_dir)) return 1;
    }
    return 0;
}
static int trigger(void) {
    char p[1100];
 snprintf(p, sizeof p, "%s/probe.on", g_dir);
    return access(p, R_OK) == 0;
}
static void dump_maps(FILE *o) {
    fprintf(o, "== maps (%d readable regions)\n", g_nreg);
    for (int i = 0;
 i < g_nreg;
 i++) fprintf(o, "%llx-%llx %s\n", (unsigned long long)g_reg[i].lo, (unsigned long long)g_reg[i].hi, g_reg[i].w ? "rw" : "r-");
}

// ---- 不依赖关键字的找法：GNames 是一个很大的指针数组�? �? 项），每项都指向可读内存里的名字条目�?

// 在可写内存里找“最长的连续指针串”，比按字符串反查可靠得多（条目的头布局�?UE3 版本不同）�?
static int in_region(uint64_t v) {
   // maps 按地址升序，二�?    
int lo = 0, hi = g_nreg - 1;
    while (lo <= hi) {
        int m = (lo + hi) / 2;
        if (v < g_reg[m].lo) hi = m - 1;
        else if (v >= g_reg[m].hi) lo = m + 1;
        else return 1;
    }
    return 0;
}
static int plausible_ptr(uint64_t v) {
 return v && in_region(v);
 }

// ---- 最后一次扫描用：符号表 + GObjObjects 完整转储 ----
static uint64_t g_names_at, g_names_n;
   // find_array 找到�?GNames 指针数组 | GNames array
static uint64_t g_mbase, g_mend;
         // 主模块范�?| main module range
static int reg_of(uint64_t v) {
    int lo = 0, hi = g_nreg - 1;
    while (lo <= hi) {
        int m = (lo + hi) / 2;
        if (v < g_reg[m].lo) hi = m - 1;
        else if (v >= g_reg[m].hi) lo = m + 1;
        else return m;
    }
    return -1;
}
static int vt_ok(uint64_t v) {
   // vtable 在主模块内或任一只读映射�?| vtable in the module or a read-only mapping    if (v >= g_mbase && v < g_mend) 
return 1;
    int r = reg_of(v);
    return r >= 0 && !g_reg[r].w;
}
static int rw_at(uint64_t v) {
 int r = reg_of(v);
 return r >= 0 && g_reg[r].w;
 }
static int names_get(uint64_t idx, char *out, size_t cap) {
    uint64_t e;
    if (idx >= g_names_n || !safe_read(g_names_at + idx * 8, &e, 8) || !e) return 0;
    return name_at(e, out, cap);
}
static uint64_t sym_at(const char *sub, char *name_out, size_t cap) {
    module_t *m = &g_mod[0];
    if (!m->symtab || !m->strtab) return 0;
    for (unsigned i = 0;
 i < m->nsym;
 i++) {
        const char *n = m->strtab + m->symtab[i].st_name;
        if (n && *n && strstr(n, sub)) {
            if (name_out) snprintf(name_out, cap, "%s", n);
            return (uint64_t)m->base + m->symtab[i].st_value;
        }
    }
    return 0;
}
static uint64_t sym_exact(const char *name) {
   // 精确名（GMalloc 这种短名字会被别的符号先匹配到）    
module_t *m = &g_mod[0];
    if (!m->symtab || !m->strtab) return 0;
    for (unsigned i = 0;
 i < m->nsym;
 i++) {
        const char *n = m->strtab + m->symtab[i].st_name;
        if (n && strcmp(n, name) == 0) return (uint64_t)m->base + m->symtab[i].st_value;
    }
    return 0;
}
static uint64_t rd64(uint64_t a) {
 uint64_t v = 0;
 safe_read(a, &v, 8);
 return v;
 }
static int32_t rd32(uint64_t a) {
 int32_t v = -1;
 safe_read(a, &v, 4);
 return v;
 }

// ---- 一次性内存快照：把之后离线分析要用的东西全部落盘，之后不再进游戏 ----

// One-shot snapshot: everything later analysis needs is written to disk, so the game

// never has to be re-entered for another probe round.
static int write_raw(const char *path, uint64_t src, uint64_t bytes) {
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    uint64_t off = 0;
    while (off < bytes) {
        size_t n = (bytes - off) < PBUF ? (size_t)(bytes - off) : PBUF;
        read_soft(src + off, g_pbuf, n);
        if (fwrite(g_pbuf, 1, n, f) != n) {
 fclose(f);
 return 0;
 }
        off += n;
    }
    return fclose(f) == 0;
}
static int copy_file(const char *src, const char *dst) {
    FILE *a = fopen(src, "r");
    if (!a) return 0;
    FILE *b = fopen(dst, "w");
    if (!b) {
 fclose(a);
 return 0;
 }
    char buf[4096];
 size_t n;
    while ((n = fread(buf, 1, sizeof buf, a)) > 0) fwrite(buf, 1, n, b);
    fclose(a);
    return fclose(b) == 0;
}

// find_array 抓到的是“最长的连续指针串”，可能比真实数组短（尾部有条目不像名字时会被截断）�?

// 这里�?run 末尾继续往后走，连�?4096 项都不像名字才停�?
static uint64_t names_extend(uint64_t at, uint64_t n) {
    uint64_t good = n, miss = 0;
    for (uint64_t i = n;
 i < n + 600000;
 i++) {
        uint64_t e = 0;
 char s[80];
        if (safe_read(at + i * 8, &e, 8) && e && plausible_ptr(e) && name_at(e, s, sizeof s)) {
            miss = 0;
 good = i + 1;
        }
 else if (++miss >= 4096) {
            break;
        }
    }
    return good;
}

// names.txt: 一行一�?"idx<TAB>名字"；namehdr.bin: 每项 32 字节条目头（可离线校验条目自带的 Index�?
static void dump_names(const char *dir, uint64_t n) {
    char p[1200];
    snprintf(p, sizeof p, "%s/names.txt", dir);
    FILE *nf = fopen(p, "w");
    snprintf(p, sizeof p, "%s/namehdr.bin", dir);
    FILE *hf = fopen(p, "wb");
    if (!nf || !hf) {
 if (nf) fclose(nf);
 if (hf) fclose(hf);
 return;
 }
    uint8_t hdr[32];
    for (uint64_t i = 0;
 i < n;
 i++) {
        uint64_t e = rd64(g_names_at + i * 8);
        char s[80];
        if (e && name_at(e, s, sizeof s)) fprintf(nf, "%llu\t%s\n", (unsigned long long)i, s);
        else fprintf(nf, "%llu\t\n", (unsigned long long)i);
        memset(hdr, 0, sizeof hdr);
        if (e) safe_read(e, hdr, sizeof hdr);
        fwrite(hdr, 1, sizeof hdr, hf);
    }
    fclose(nf);
    fclose(hf);
}

// gobj.bin: GObjObjects 指针数组原样；objects.bin: 每个对象 512 字节原始内容，偏�?= 下标 * 512
static int dump_objects(const char *dir, FILE *o) {
    char nm[160] = "", p[1200];
    uint64_t go = sym_at("GObjObjects", nm, sizeof nm);
    if (!go) {
 fprintf(o, "gobj: symbol missing\n");
 return 0;
 }
    uint64_t data = rd64(go);
    int32_t num = rd32(go + 8);
    fprintf(o, "gobj_sym %s @ %llx data %llx num %d\n", nm, (unsigned long long)go,            (unsigned long long)data, num);
    if (!data || num <= 0 || num > 2000000) return 0;
    snprintf(p, sizeof p, "%s/gobj.bin", dir);
    write_raw(p, data, (uint64_t)num * 8);
    snprintf(p, sizeof p, "%s/objects.bin", dir);
    FILE *f = fopen(p, "wb");
    if (!f) return 0;
    static uint8_t rec[512];
    for (int32_t i = 0;
 i < num;
 i++) {
        uint64_t q = rd64(data + (uint64_t)i * 8);
        if (q) read_soft(q, rec, sizeof rec);
 else memset(rec, 0, sizeof rec);
        fwrite(rec, 1, sizeof rec, f);
    }
    fclose(f);
    fprintf(o, "objects.bin %d records x 512 = %lld bytes\n", num, (long long)num * 512);
    return 1;
}
static void find_array(FILE *o) {
    uint64_t best_n = 0, best_at = 0;
 int best_r = -1;
    uintptr_t own = (uintptr_t)__builtin_frame_address(0);
    for (int r = 0;
 r < g_nreg;
 r++) {
        if (!g_reg[r].w) continue;
        if (own >= g_reg[r].lo && own < g_reg[r].hi) continue;
        uint64_t lo = (g_reg[r].lo + 7) & ~(uint64_t)7, hi = g_reg[r].hi - (g_reg[r].file ? 4096 : 0);
        if (hi <= lo + 8) continue;
        for (uint64_t off = 0;
 off + 8 <= hi - lo;
 ) {
            size_t n = (hi - lo - off) < PBUF ? (size_t)(hi - lo - off) : PBUF;
            n &= ~(size_t)7;
            if (!n) break;
            read_soft(lo + off, g_pbuf, n);
            for (size_t i = 0;
 i + 8 <= n;
 i += 8) {
                uint64_t v;
 memcpy(&v, g_pbuf + i, 8);
                if (!plausible_ptr(v)) continue;
                if (i >= 8) {
 uint64_t pv;
 memcpy(&pv, g_pbuf + i - 8, 8);
 if (plausible_ptr(pv)) continue;
 }
   // 只从串首开始数                
uint64_t cnt = 1, q = lo + off + i + 8, w;
                while (cnt < 200000 && q + 8 <= hi) {
                    if (q + 8 <= lo + off + n) memcpy(&w, g_pbuf + (size_t)(q - (lo + off)), 8);
                    else if (!safe_read(q, &w, 8)) break;
                    if (!plausible_ptr(w)) break;
                    cnt++;
 q += 8;
                }
                if (cnt >= 256) {
   // 只有很长的串才验证：�?GNames 三万多项，且每一项都是名字条�?                    
uint64_t okc = 0, tot = 0, q2 = lo + off + i, w2;
                    for (uint64_t k = 0;
 k < cnt && tot < 32;
 k++, q2 += 8) {
                        if (!safe_read(q2, &w2, 8)) break;
                        tot++;
 if (is_name_entry(w2)) okc++;
                    }
                    if (tot >= 16 && okc * 4 >= tot * 3 && cnt > best_n) {
 best_n = cnt;
 best_at = lo + off + i;
 best_r = r;
 }
                }
                if (cnt >= 8 && i + cnt * 8 <= n) i += (size_t)(cnt - 1) * 8;
            }
            off += n;
        }
    }
    fprintf(o, "== longest pointer run: %llu entries @ %llx (region %d)%s\n",            (unsigned long long)best_n, (unsigned long long)best_at, best_r,            best_n >= 256 ? "  ** likely GNames **" : "");
    if (best_n >= 256) {
 g_names_at = best_at;
 g_names_n = best_n;
 }
   // 供对象转储解名字    
if (best_n >= 8) {
        char names[16][72];
 int nn = names_around(best_at, names);
        for (int k = 0;
 k < nn;
 k++) fprintf(o, "        %s\n", names[k]);
    }
    fflush(o);
}

// 在全部可读区域里�?needle，然后找“指向这个字符串的指针数组”（GNames 候选）
static void scan(const char *needle, FILE *o) {
    size_t len = strlen(needle) + 1;
    uint64_t hits[32];
 int nh = 0;
    for (int r = 0;
 r < g_nreg && nh < 32;
 r++) {
        int k = hits_region(r, needle, len, hits, nh, 32);
        if (k > 0) nh += k;
    }
    fprintf(o, "-- needle %s: %d hits\n", needle, nh);
    uint64_t mbase = (uint64_t)g_mod[0].base, mend = mbase + g_mod[0].size;
 int tried = 0;
    for (int i = 0;
 i < nh && tried < 8;
 i++) {
        // 可执行文件里的只是字符串常量；运行时名字表在堆上，跳�?main 映像里的命中        
if (hits[i] >= mbase && hits[i] < mend) continue;
        ++tried;
        fprintf(o, "   str @ %llx (main%+lld)\n", (unsigned long long)hits[i], (long long)(hits[i] - mbase));
        // 指针数组里存的是 FNameEntry 入口，头大小随版本不同：�?str±32 范围内任�?        
uint64_t best = 0, best_at = 0, best_v = 0;
        for (int r = 0;
 r < g_nreg && best < 8;
 r++) slots_region(r, hits[i], 32, &best, &best_at, &best_v);
        fprintf(o, "     -> entry %llx slot %llx, %d consecutive name entries%s\n",                (unsigned long long)best_v, (unsigned long long)best_at, best, best >= 8 ? "  ** likely GNames **" : "");
        if (best >= 8) {
            char names[16][72];
 int nn = names_around(best_at, names);
            for (int k = 0;
 k < nn;
 k++) fprintf(o, "        %s\n", names[k]);
        }
        fflush(o);
    }
}
static void snapshot(void) {
    char dir[1100], p[1200];
    snprintf(dir, sizeof dir, "%s/snap", g_dir);
    mkdir(dir, 0777);
    snprintf(p, sizeof p, "%s/info.txt", dir);
    FILE *o = fopen(p, "w");
    if (!o) {
 LOG("BL2 probe: cannot write %s", p);
 return;
 }
    g_names_at = g_names_n = 0;
    g_mbase = (uint64_t)g_mod[0].base;
 g_mend = g_mbase + g_mod[0].size;
    fprintf(o, "main_base %llx size %zu text_end %llx\n", (unsigned long long)g_mbase,            g_mod[0].size, (unsigned long long)g_mod[0].text_end);
    if (!read_maps()) {
 fprintf(o, "no maps\n");
 fclose(o);
 return;
 }
    snprintf(p, sizeof p, "%s/maps.txt", dir);
    copy_file("/proc/self/maps", p);
    find_array(o);
    // 定位 GNames 并写进 info.txt
    if (g_names_at && g_names_n >= 256) {
uint64_t ext = names_extend(g_names_at, g_names_n);
        fprintf(o, "gnames_at %llx run %llu ext %llu\n", (unsigned long long)g_names_at,                (unsigned long long)g_names_n, (unsigned long long)ext);
        snprintf(p, sizeof p, "%s/gnames.bin", dir);
        write_raw(p, g_names_at, ext * 8);
        dump_names(dir, ext);
        fprintf(o, "gnames.bin %llu x 8 = %llu bytes\n", (unsigned long long)ext,                (unsigned long long)ext * 8);
    }
 else {
        fprintf(o, "gnames: not found\n");
    }
    dump_objects(dir, o);
    if (g_einval) fprintf(o, "process_vm_readv unusable\n");
    fclose(o);
    LOG("BL2 probe: snapshot in %s", dir);
}

// 常驻：probe.req 出现一次就导一次快照，避免为了改探针反复重启游戏�?

// Resident: one snapshot per probe.req file, so the probe can change without restarting the game.

// ---- [BL2] 作弊入口：cheat.req 一行命令，由 nvnQueuePresentTexture（客体线程）取走执行 ----
// cheats.txt（离线导出）里的 WillowCheatManager / CheatManager 命令；按名字找 UFunction，再调
// UObject::ProcessEvent。执行放在出图线程，不另开线程碰 UE3 对象。
static volatile int g_cheat_state;   // 0 = 没扫, 1 = 就绪
static int g_cheat_off = 3000;       // FName 索引 -> 名字表槽位
static uint64_t g_cheat_class, g_cheat_class2, g_cheat_inst, g_proc_event;
static uint64_t g_gobj_data; static int32_t g_gobj_num;
static uint64_t g_gobj_sym;          // &GObjObjects（TArray 头）：进图后数组会搬家，必须每次重读
// M2：把敌人变成队友（复用游戏自己的阵营系统）
static uint64_t g_aipawn_class, g_pawn_class, g_alleg_player, g_fn_setalleg, g_fn_gettarget;
static uint64_t g_playerpawn_class;          // WillowPlayerPawn 类（count 用）
// 天气/时间：游戏只有冰原 DLC 的雪天，基础图没有天气；这里做时间循环
static uint64_t g_fn_timeofday;
static int g_cycle_on; static time_t g_cycle_next;
static uint64_t g_fn_travel, g_fn_console;   // PlayerController::LocalTravel / SendToConsole
static uint64_t g_pc_class;                  // PlayerController 类（LocalTravel/ConsoleCommand 挂在父类上）
static uint64_t g_gmalloc, g_mswitch;        // GMalloc（FMallocSwitch*）与 FMallocSwitch::Malloc
static volatile int g_rescan;                // 进图后 GNames 会搬家：置位让常驻线程重扫
static char g_retry[128];                    // 触发重扫时暂存这条命令，重扫完自动执行
static volatile int g_retry_on;
// ---- 游戏线程执行点：hook UObject::ProcessEvent（游戏线程每帧都调它）----
// 最小 ARM64 hook：目标前 16 字节搬到跳板（+ ldr x16/br 回 target+16），再在目标写 ldr x16/br 到 hook
static void (*g_pe_orig)(void *, void *, void *, void *);
static char g_pending[128];                  // 待执行命令（出图线程只入队，游戏线程执行）
static volatile int g_pending_on;
static volatile unsigned long g_pe_hits;     // pe_hook 被调用的次数（诊断）
static uint64_t g_world_sym, g_spawn_fn;     // GWorld 与 UWorld::SpawnActor
static uint64_t g_fn_viewloc;                // GetPawnViewLocation（拿到玩家坐标）
static uint64_t g_aic_class, g_fn_possess;   // AIController 类 + Controller::Possess
static uint64_t g_mind_class, g_fn_initseq, g_seq_deathtrap;   // WillowMind + InitSequence(死神序列)
static uint64_t g_gbaic_class, g_fn_setaidef, g_aidef_psycho;  // GearboxAIController + SetOverrideAIDef
// 手动驱动 AI：Mind 需要引擎每帧 Tick，手动 spawn 的不会自动 tick
static uint64_t g_minds[8]; static int g_nminds;
static uint64_t g_fn_tickai, g_uf_tickai; static int64_t g_ai_next_ms;
static uint64_t g_fn_forcemove, g_ai_player_pawn; static int g_ai_follow;   // 跟随：定时 ForceMoveToActor(玩家)
static uint64_t g_last_mind;   // 最近生成/修复的 Mind（quiet 模式下 aifix 用它）
static void cheat_run(char *line);           // 前向声明
static int64_t now_ms(void);                 // 前向声明
static uint64_t ai_mine(void);               // 前向声明：当前要修的那个 Mind
static uint64_t ai_find_real(uint64_t mine); // 前向声明：场上真实 AI 的 Mind

static void cheat_log(const char *fmt, ...) {
    char b[512]; va_list ap; va_start(ap, fmt); vsnprintf(b, sizeof b, fmt, ap); va_end(ap);
    LOG("BL2 cheat: %s", b);
    if (!g_dir[0]) return;
    char p[1200]; snprintf(p, sizeof p, "%s/cheat.log", g_dir);
    FILE *f = fopen(p, "a");
    if (!f) return;
    time_t t = time(NULL); struct tm tm; localtime_r(&t, &tm);
    fprintf(f, "[%02d:%02d:%02d] %s\n", tm.tm_hour, tm.tm_min, tm.tm_sec, b);
    fclose(f);
}
static int cheat_name_is(uint64_t obj, const char *want) {
    if (!obj) return 0;
    int32_t idx = rd32(obj + 0x48);
    if (idx < g_cheat_off) return 0;
    char b[80];
    if (!names_get((uint64_t)(idx - g_cheat_off), b, sizeof b)) return 0;
    return strcasecmp(b, want) == 0;   // 命令名不分大小写
}
// 类 cls 里名为 want 的成员（UFunction）；flags 取 FunctionFlags（bit 0x200 = exec）
static uint64_t cheat_member(uint64_t cls, const char *want, uint32_t *flags) {
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || rd64(o + 0x40) != cls) continue;
        if (!cheat_name_is(o, want)) continue;
        if (flags) *flags = (uint32_t)rd32(o + 0xc0);
        return o;
    }
    return 0;
}
// 有成员函数的那个才是类（实例没有成员）；God/Ghost/Fly 任一存在就认
static uint64_t cheat_find_class(const char *nm) {
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || !cheat_name_is(o, nm)) continue;
        if (cheat_member(o, "God", NULL) || cheat_member(o, "Ghost", NULL) || cheat_member(o, "Fly", NULL)) return o;
    }
    return 0;
}
// 命令可能在 CheatManager（父类）里
static uint64_t cheat_find(const char *want, uint32_t *flags) {
    uint64_t f = cheat_member(g_cheat_class, want, flags);
    if (!f && g_cheat_class2) f = cheat_member(g_cheat_class2, want, flags);
    return f;
}
// 名字表失效检测：用已知类名验证读到的还是不是真名字
static int cheat_names_ok(void) {
    return g_cheat_class && cheat_name_is(g_cheat_class, "WillowCheatManager");
}
// 进图/切图后 GObjObjects 会扩容搬家、CheatManager 实例也会重建：每条命令前重读一次
static void cheat_refresh(void) {
    if (g_gobj_sym) { g_gobj_data = rd64(g_gobj_sym); g_gobj_num = rd32(g_gobj_sym + 8); }
    if (!g_cheat_class) return;
    if (g_cheat_inst && rd64(g_cheat_inst + 0x50) == g_cheat_class) return;
    g_cheat_inst = 0;
    for (int32_t i = 0; i < g_gobj_num && !g_cheat_inst; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (o && rd64(o + 0x50) == g_cheat_class && cheat_name_is(o, "WillowCheatManager")) g_cheat_inst = o;
    }
}
static int cheat_has_member(uint64_t cls) {
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (o && rd64(o + 0x40) == cls) return 1;
    }
    return 0;
}
static uint64_t cheat_class_with_member(const char *nm, const char *fn) {
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || !cheat_name_is(o, nm)) continue;
        if (cheat_member(o, fn, NULL)) return o;
    }
    return 0;
}
static uint64_t cheat_object_named(const char *want) {
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (o && cheat_name_is(o, want)) return o;
    }
    return 0;
}
static void cheat_pe(void *obj, void *fn, void *par) {
    void (*pe)(void *, void *, void *, void *) = (void (*)(void *, void *, void *, void *))(uintptr_t)g_proc_event;
    pe(obj, fn, par, NULL);
}
// 组一个 UE3 FString 参数：{TCHAR* Data; int Num; int Max}，TCHAR 是 UTF-16。
// 引擎析构时会 free(Data)，所以必须从 GMalloc（FMallocSwitch）分配，不能用静态缓冲。
static void cheat_fstr(uint8_t *par, const char *s) {
    size_t L = strlen(s); if (L > 280) L = 280;
    static uint16_t sbuf[300];
    uint16_t *w = sbuf;
    if (g_gmalloc && g_mswitch) {
        uint64_t g = rd64(g_gmalloc);
        if (g) {
            void *(*m)(void *, unsigned, unsigned) = (void *(*)(void *, unsigned, unsigned))(uintptr_t)g_mswitch;
            void *p = m((void *)(uintptr_t)g, (unsigned)((L + 1) * 2), 8);
            if (p) w = (uint16_t *)p;
        }
    }
    for (size_t i = 0; i < L; i++) w[i] = (uint16_t)(unsigned char)s[i];
    w[L] = 0;
    struct { uint64_t d; int32_t n, m; } f = { (uint64_t)(uintptr_t)w, (int32_t)(L + 1), (int32_t)(L + 1) };
    memset(par, 0, 16); memcpy(par, &f, 16);
}
static uint64_t cheat_pc(void) {   // CheatManager 的 Outer 就是本地 PlayerController
    return g_cheat_inst ? rd64(g_cheat_inst + 0x40) : 0;
}
static void cheat_travel(const char *map) {
    uint64_t pc = cheat_pc();
    if (!pc || !g_fn_travel) { cheat_log("travel：没有 PlayerController/LocalTravel"); return; }
    uint8_t par[16] __attribute__((aligned(16))); cheat_fstr(par, map);
    cheat_log("travel：%s", map);
    cheat_pe((void *)(uintptr_t)pc, (void *)(uintptr_t)g_fn_travel, par);
}
// ClientTravel(URL, TRAVEL_Absolute, bSeamless=false)：引擎在帧末才搬家，不在 ProcessEvent 里拆世界
static void cheat_ctravel(const char *map) {
    uint64_t pc = cheat_pc();
    uint64_t fn = g_pc_class ? cheat_member(g_pc_class, "ClientTravel", NULL) : 0;
    if (!pc || !fn) { cheat_log("ctravel：没有 PlayerController/ClientTravel"); return; }
    uint32_t w = (uint32_t)rd32(fn + 0xc8);
    uint8_t par[64] __attribute__((aligned(16))); memset(par, 0, sizeof par);
    cheat_fstr(par, map);                 // FString URL @0
    par[16] = 0;                          // ETravelType TRAVEL_Absolute
    par[17] = 0;                          // bool bSeamless
    cheat_log("ctravel：%s（参数 %d 个 / %d 字节）", map, (int)((w >> 8) & 0xff), (int)((w >> 16) & 0xffff));
    cheat_pe((void *)(uintptr_t)pc, (void *)(uintptr_t)fn, par);
}
static void cheat_finfo(const char *name) {
    int shown = 0;
    for (int32_t i = 0; i < g_gobj_num && shown < 6; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || !cheat_name_is(o, name)) continue;
        uint64_t owner = rd64(o + 0x40);
        char ob[96] = "?";
        if (owner) { int32_t idx = (int32_t)rd32(owner + 0x48); if (idx >= g_cheat_off) names_get((uint64_t)(idx - g_cheat_off), ob, sizeof ob); }
        uint32_t w = (uint32_t)rd32(o + 0xc8);
        cheat_log("fn %s：owner=%s parms=%d bytes=%d", name, ob, (int)((w >> 8) & 0xff), (int)((w >> 16) & 0xffff));
        for (int32_t j = 0; j < g_gobj_num && j < 400000; j++) {
            uint64_t p = rd64(g_gobj_data + (uint64_t)j * 8);
            if (!p || rd64(p + 0x40) != o) continue;
            char pn[96] = "?";
            int32_t pi = (int32_t)rd32(p + 0x48); if (pi >= g_cheat_off) names_get((uint64_t)(pi - g_cheat_off), pn, sizeof pn);
            cheat_log("  parm %s  +0x70:%d +0x74:%d +0x78:%d +0x7c:%d +0x80:%d +0x84:%d +0x88:%d +0x8c:%d +0x90:%d",
                pn, (int)rd32(p + 0x70), (int)rd32(p + 0x74), (int)rd32(p + 0x78), (int)rd32(p + 0x7c),
                (int)rd32(p + 0x80), (int)rd32(p + 0x84), (int)rd32(p + 0x88), (int)rd32(p + 0x8c), (int)rd32(p + 0x90));
        }
        shown++;
    }
    if (!shown) cheat_log("fn %s：没找到", name);
}
static void cheat_console(const char *cmd) {
    uint64_t pc = cheat_pc();
    if (!pc) { cheat_log("console：没有 PlayerController"); return; }
    // SendToConsole / ClientConsoleCommand 都是 RPC（单机会崩）；ConsoleCommand 是本地执行
    uint64_t fn = g_pc_class ? cheat_member(g_pc_class, "ConsoleCommand", NULL) : 0;
    if (!fn) { cheat_log("console：找不到 PlayerController::ConsoleCommand"); return; }
    // 参数：ReturnValue(FString, 0..16) + bWriteToLog(16) + Command(FString, 24..40)，共 40
    uint8_t par[40] __attribute__((aligned(16))); memset(par, 0, sizeof par);
    cheat_fstr(par + 24, cmd);
    cheat_log("console：%s", cmd);
    cheat_pe((void *)(uintptr_t)pc, (void *)(uintptr_t)fn, par);
}
// say：本地发一句聊天（单字符串参数的对照测试，也方便验证字符串通道）
static void cheat_say(const char *msg) {
    uint64_t pc = cheat_pc();
    uint64_t fn = g_pc_class ? cheat_member(g_pc_class, "Say", NULL) : 0;
    if (!pc || !fn) { cheat_log("say：没有 PlayerController/Say"); return; }
    uint8_t par[16] __attribute__((aligned(16))); cheat_fstr(par, msg);
    cheat_log("say：%s", msg);
    cheat_pe((void *)(uintptr_t)pc, (void *)(uintptr_t)fn, par);
}
// Pawn::SetAllegiance(PawnAllegiance*)：把某个 Pawn 的阵营改成 Allegiance_Player
static int cheat_set_alleg(uint64_t pawn) {
    if (!g_fn_setalleg || !g_alleg_player || !pawn) return 0;
    uint8_t par[16] __attribute__((aligned(16)));
    memset(par, 0, sizeof par);
    memcpy(par, &g_alleg_player, 8);
    cheat_pe((void *)(uintptr_t)pawn, (void *)(uintptr_t)g_fn_setalleg, par);
    return 1;
}
static int is_obj(uint64_t a) {
    for (int32_t i = 0; i < g_gobj_num; i++) if (rd64(g_gobj_data + (uint64_t)i * 8) == a) return 1;
    return 0;
}
// ally：把准星/当前目标变成队友（DebugGetPlayerTarget 返回的对象）
static void cheat_ally_one(void) {
    if (!g_cheat_inst) { cheat_log("ally：没有 CheatManager 实例（先进游戏）"); return; }
    if (!g_fn_gettarget) { cheat_log("ally：没有 DebugGetPlayerTarget"); return; }
    uint8_t par[16] __attribute__((aligned(16)));
    memset(par, 0, sizeof par);
    cheat_pe((void *)(uintptr_t)g_cheat_inst, (void *)(uintptr_t)g_fn_gettarget, par);
    uint64_t t = 0; memcpy(&t, par, 8);
    if (!t || !is_obj(t)) { cheat_log("ally：没拿到目标（对着敌人再试）"); return; }
    char nm[80] = "?";
    if (g_cheat_off >= 0) names_get((uint64_t)(rd32(t + 0x48) - g_cheat_off), nm, sizeof nm);
    // 必须是 Pawn 及其子类才能调 SetAllegiance：DebugGetPlayerTarget 常返回 WorldInfo，乱调会崩
    uint64_t tc = rd64(t + 0x50);
    if (!tc || !cheat_member(tc, "SetAllegiance", NULL)) { cheat_log("ally：%s 不是 Pawn，改用 allyall（全场）", nm); return; }
    if (!cheat_set_alleg(t)) { cheat_log("ally：阵营函数没准备好"); return; }
    cheat_log("ally：%s -> Allegiance_Player", nm);
}
// allyall：场上所有 WillowAIPawn（敌人/NPC）一起改成玩家阵营
static void cheat_ally_all(void) {
    if (!g_aipawn_class || !g_fn_setalleg) { cheat_log("allyall：阵营数据没准备好"); return; }
    int n = 0;
    for (int32_t i = 0; i < g_gobj_num && n < 300; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || rd64(o + 0x50) != g_aipawn_class) continue;
        if (cheat_set_alleg(o)) n++;
    }
    cheat_log("allyall：%d 个 WillowAIPawn -> Allegiance_Player", n);
}
// ploc：直接读玩家 Pawn 内存里的 Location（Actor::Location 偏移 0x98，FVector 3×float，不调任何引擎函数）
#define OFFS_ACTOR_LOC 0x98
static int read_vec3(uint64_t a, float out[3]) {
    return safe_read(a, out, 12);
}
static void cheat_ploc(void) {
    if (!g_playerpawn_class) { cheat_log("ploc：没有玩家 Pawn 类"); return; }
    int n = 0;
    for (int32_t i = 0; i < g_gobj_num && n < 6; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!q || rd64(q + 0x50) != g_playerpawn_class) continue;
        float v[3] = {0, 0, 0};
        char nm[80] = "?";
        if (g_cheat_off >= 0) names_get((uint64_t)(rd32(q + 0x48) - g_cheat_off), nm, sizeof nm);
        read_vec3(q + OFFS_ACTOR_LOC, v);
        cheat_log("ploc：#%d %s @%llx  0x98=[%.0f %.0f %.0f]", i, nm, (unsigned long long)q, v[0], v[1], v[2]);
        n++;
    }
    if (!n) cheat_log("ploc：没有玩家 Pawn");
}
// spawnp <原型名>：直接调 UWorld::SpawnActor 生成（现在跑在游戏线程）
static void cheat_spawnp(const char *arch) {
    if (!g_spawn_fn || !g_world_sym) { cheat_log("spawnp：没有 SpawnActor/GWorld 符号"); return; }
    uint64_t world = rd64(g_world_sym);
    if (!world) { cheat_log("spawnp：GWorld 为空"); return; }
    uint64_t a = cheat_object_named(arch);
    if (!a) { cheat_log("spawnp：找不到原型 %s（包没加载？）", arch); return; }
    uint64_t cls = g_aipawn_class;
    if (strstr(arch, "PlayerPawn") || strstr(arch, "Pawn_Assassin") || strstr(arch, "Pawn_Siren") ||
        strstr(arch, "Pawn_Soldier") || strstr(arch, "Pawn_Mercenary") || strstr(arch, "Pawn_Mechromancer") ||
        strstr(arch, "Pawn_Psycho")) cls = g_playerpawn_class ? g_playerpawn_class : g_aipawn_class;
    if (!cls) { cheat_log("spawnp：没有 Pawn 类"); return; }
    float loc[3] = {0, 0, 0}; int32_t rot[3] = {0, 0, 0};
    // 用玩家 Pawn 的 GetPawnViewLocation 取坐标，生成在脚边（否则会掉在世界原点）
    if (g_playerpawn_class) {   // 直接读玩家 Pawn 的 Location；跳过 CDO（坐标全 0）
        for (int32_t i = 0; i < g_gobj_num; i++) {
            uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
            if (!q || rd64(q + 0x50) != g_playerpawn_class) continue;
            float v[3] = {0, 0, 0};
            if (!read_vec3(q + OFFS_ACTOR_LOC, v)) continue;
            if (v[0] == 0 && v[1] == 0 && v[2] == 0) continue;
            loc[0] = v[0]; loc[1] = v[1]; loc[2] = v[2] + 10.0f;   // Z 只抬 10，避免悬空
            cheat_log("spawnp：玩家坐标 %.0f %.0f %.0f（已抬高 Z）", loc[0], loc[1], loc[2]);
            break;
        }
    }
    typedef void *(*spawn_t)(void *, void *, uint64_t, void *, void *, void *, unsigned, unsigned, void *, void *, unsigned, void *);
    spawn_t f = (spawn_t)(uintptr_t)g_spawn_fn;
    void *r = f((void *)(uintptr_t)world, (void *)(uintptr_t)cls, 0, loc, rot, (void *)(uintptr_t)a, 1, 0, 0, 0, 0, 0);
    cheat_log("spawnp：%s -> %p（类 %llx 原型 %llx 世界 %llx）", arch, r,
              (unsigned long long)cls, (unsigned long long)a, (unsigned long long)world);
    if (r && g_fn_setalleg) cheat_set_alleg((uint64_t)(uintptr_t)r);   // 直接设成玩家阵营
    if (r) cheat_log("spawnp：已设为 Allegiance_Player");
    // 生成 AIController 并 Possess，否则它是死的（不动、没 AI）
    if (r && g_aic_class && g_fn_possess) {
        void *ctl = f((void *)(uintptr_t)world, (void *)(uintptr_t)g_aic_class, 0, loc, rot, 0, 1, 0, 0, 0, 0, 0);
        cheat_log("spawnp：AIController -> %p", ctl);
        if (ctl) {
            uint8_t pp[16] __attribute__((aligned(16))); memset(pp, 0, sizeof pp);
            uint64_t pv = (uint64_t)(uintptr_t)r; memcpy(pp, &pv, 8);
            cheat_pe(ctl, (void *)(uintptr_t)g_fn_possess, pp);
            cheat_log("spawnp：已 Possess");
            if (g_fn_setalleg) cheat_set_alleg((uint64_t)(uintptr_t)r);
        }
    }
    // 生成 WillowMind（AI 大脑），双向绑定，再挂死神的行为序列
    if (r && g_mind_class) {
        void *mind = f((void *)(uintptr_t)world, (void *)(uintptr_t)g_mind_class, 0, loc, rot, 0, 1, 0, 0, 0, 0, 0);
        cheat_log("spawnp：WillowMind -> %p", mind);
        if (mind) {
            uint64_t mv = (uint64_t)(uintptr_t)mind, pv = (uint64_t)(uintptr_t)r;
            *(volatile uint64_t *)(uintptr_t)(pv + 0xe0) = mv;   // Pawn -> Mind
            *(volatile uint64_t *)(uintptr_t)(mv + 0x128) = pv;  // Mind -> Pawn
            cheat_log("spawnp：Mind/Pawn 已互相绑定");
            if (g_fn_initseq && g_seq_deathtrap) {
                uint8_t sp[16] __attribute__((aligned(16))); memset(sp, 0, sizeof sp);
                uint64_t sv = g_seq_deathtrap; memcpy(sp, &sv, 8);
                cheat_pe(mind, (void *)(uintptr_t)g_fn_initseq, sp);
                cheat_log("spawnp：已挂 Action_DeathTrap 行为序列");
            } else cheat_log("spawnp：没有 InitSequence/序列（%llx/%llx）",
                             (unsigned long long)g_fn_initseq, (unsigned long long)g_seq_deathtrap);
        }
    }
}
// 在对象内存里找某个指针，返回偏移（-1 没找到，-2 读失败）
static int scan_ptr(uint64_t obj, uint64_t val, int len) {
    for (int off = 0; off + 8 <= len; off += 8) {
        uint64_t v = 0;
        if (!safe_read(obj + off, &v, 8)) return -2;
        if (v == val) return off;
    }
    return -1;
}
// spawnai <原型名>：生成一个原生 AI 敌人（WillowAIPawn）→ 玩家阵营 → GearboxAIController + Mind + AIDef
static void cheat_spawnai(const char *arch) {
    if (!g_spawn_fn || !g_world_sym) { cheat_log("spawnai：没有 SpawnActor/GWorld"); return; }
    char name[64]; snprintf(name, sizeof name, "%s", arch);
    int hostile = 0, quiet = 0;                      // 第二段：enemy=敌方阵营；quiet=只生成不发条
    char *sp2 = strchr(name, ' ');
    if (sp2) {
        *sp2++ = 0;
        while (*sp2 == ' ') sp2++;
        if (!strcasecmp(sp2, "enemy")) hostile = 1;
        else if (!strcasecmp(sp2, "quiet")) quiet = 1;
    }
    uint64_t world = rd64(g_world_sym);
    if (!world) { cheat_log("spawnai：GWorld 为空"); return; }
    uint64_t a = cheat_object_named(name);
    if (!a) { cheat_log("spawnai：找不到原型 %s", name); return; }
    if (!g_aipawn_class) { cheat_log("spawnai：没有 WillowAIPawn 类"); return; }
    float loc[3] = {0, 0, 0}; int32_t rot[3] = {0, 0, 0};
    if (g_playerpawn_class) {
        for (int32_t i = 0; i < g_gobj_num; i++) {
            uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
            if (!q || rd64(q + 0x50) != g_playerpawn_class) continue;
            float v[3] = {0, 0, 0};
            if (!read_vec3(q + OFFS_ACTOR_LOC, v)) continue;
            if (v[0] == 0 && v[1] == 0 && v[2] == 0) continue;
            loc[0] = v[0] + 120.0f; loc[1] = v[1]; loc[2] = v[2] + 10.0f;
            break;
        }
    }
    typedef void *(*spawn_t)(void *, void *, uint64_t, void *, void *, void *, unsigned, unsigned, void *, void *, unsigned, void *);
    spawn_t f = (spawn_t)(uintptr_t)g_spawn_fn;
    void *r = f((void *)(uintptr_t)world, (void *)(uintptr_t)g_aipawn_class, 0, loc, rot, (void *)(uintptr_t)a, 1, 0, 0, 0, 0, 0);
    cheat_log("spawnai：%s -> %p（AI 类 %llx 原型 %llx）%s", name, r,
              (unsigned long long)g_aipawn_class, (unsigned long long)a, hostile ? " [敌方阵营]" : "");
    if (!r) return;
    if (g_fn_setalleg && !hostile) {
        cheat_set_alleg((uint64_t)(uintptr_t)r);
        cheat_log("spawnai：已设为 Allegiance_Player");
    }
    // AIDef / SetOverrideAIDef 现场解析（进图前这些资源没加载，启动时拿到的是 0）
    if (!g_fn_setaidef && g_mind_class) g_fn_setaidef = cheat_member(g_mind_class, "SetOverrideAIDef", NULL);
    uint64_t aidef = cheat_object_named(strstr(name, "Marauder") ? "AIDef_MarauderGrunt" : "AIDef_Psycho");
    if (!aidef) aidef = cheat_object_named("AIDef_MarauderGrunt");
    if (!aidef) aidef = cheat_object_named("AIDef_Psycho");
    // 快照证实：活体 AI 的 Pawn+0xe0 指向 WillowMind → Mind 本身就是控制器，用它 Possess
    if (g_mind_class && g_fn_possess) {
        void *mind = f((void *)(uintptr_t)world, (void *)(uintptr_t)g_mind_class, 0, loc, rot, 0, 1, 0, 0, 0, 0, 0);
        cheat_log("spawnai：Mind(控制器) -> %p", mind);
        if (mind) {
            uint8_t pp[16] __attribute__((aligned(16))); memset(pp, 0, sizeof pp);
            uint64_t pv = (uint64_t)(uintptr_t)r; memcpy(pp, &pv, 8);
            cheat_pe(mind, (void *)(uintptr_t)g_fn_possess, pp);   // Mind Possess Pawn
            cheat_log("spawnai：Mind 已 Possess Pawn");
            *(volatile uint64_t *)(uintptr_t)((uint64_t)(uintptr_t)mind + 0x128) = (uint64_t)(uintptr_t)r;
            g_last_mind = (uint64_t)(uintptr_t)mind;
            if (g_nminds < 8 && !quiet) g_minds[g_nminds++] = (uint64_t)(uintptr_t)mind;   // 交给 pe_hook 每帧驱动
            if (!quiet) g_ai_next_ms = now_ms() + 2000;   // 等生成流程走完再开始 tick，避免中途驱动半初始化的 Mind
            cheat_log("spawnai：%s（当前 %d 个）", quiet ? "quiet 模式，暂不上发条" : "Mind 已登记给 tick", g_nminds);
            if (g_fn_setaidef && aidef) {
                uint8_t ap[32] __attribute__((aligned(16))); memset(ap, 0, sizeof ap);
                uint64_t av = aidef; memcpy(ap, &av, 8);
                cheat_pe(mind, (void *)(uintptr_t)g_fn_setaidef, ap);
                cheat_log("spawnai：已 SetOverrideAIDef(%llx)", (unsigned long long)aidef);
            } else cheat_log("spawnai：没有 SetOverrideAIDef/AIDef（%llx/%llx）",
                             (unsigned long long)g_fn_setaidef, (unsigned long long)aidef);
        }
    } else cheat_log("spawnai：没有 Mind/Possess（%llx/%llx）",
                     (unsigned long long)g_mind_class, (unsigned long long)g_fn_possess);
}
// objs <关键词>：列出当前内存里名字包含该关键词的对象（上限 25 个）
static void cheat_objs(const char *sub) {
    int n = 0;
    for (int32_t i = 0; i < g_gobj_num && n < 25; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o) continue;
        char nm[80] = "?";
        if (!names_get((uint64_t)(rd32(o + 0x48) - g_cheat_off), nm, sizeof nm)) continue;
        if (!strstr(nm, sub)) continue;
        char cn[80] = "?";
        uint64_t c = rd64(o + 0x50);
        if (c) names_get((uint64_t)(rd32(c + 0x48) - g_cheat_off), cn, sizeof cn);
        cheat_log("objs：#%d %s (%s)", i, nm, cn);
        n++;
    }
    cheat_log("objs：匹配 \"%s\" 共列出 %d 个", sub, n);
}
// count：统计场上 WillowAIPawn / WillowPlayerPawn 数量（验证生成有没有成功）
static void cheat_count(void) {
    int ai = 0, pp = 0;
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o) continue;
        uint64_t c = rd64(o + 0x50);
        if (g_aipawn_class && c == g_aipawn_class) ai++;
        else if (g_playerpawn_class && c == g_playerpawn_class) pp++;
    }
    cheat_log("count：WillowAIPawn %d，WillowPlayerPawn %d（对象总数 %d，pe_hook 命中 %lu）",
              ai, pp, g_gobj_num, (unsigned long)__atomic_load_n(&g_pe_hits, __ATOMIC_RELAXED));
    // 最新创建的 25 个对象（新对象追加在 GObjObjects 末尾），直接看出生成命令造了什么
    int from = g_gobj_num > 25 ? g_gobj_num - 25 : 0;
    for (int32_t i = from; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o) continue;
        char n1[80] = "?", n2[80] = "?";
        names_get((uint64_t)(rd32(o + 0x48) - g_cheat_off), n1, sizeof n1);
        uint64_t c = rd64(o + 0x50);
        if (c) names_get((uint64_t)(rd32(c + 0x48) - g_cheat_off), n2, sizeof n2);
        cheat_log("  +%d %s (%s)", i, n1, n2);
    }
}
// mindfns：列出 WillowMind / GearboxAIController / AIController 的成员函数（找 AI 初始化入口用）
static void cheat_mindfns(void) {
    uint64_t cls[3]; int nc = 0;
    if (g_mind_class) cls[nc++] = g_mind_class;
    if (g_gbaic_class) cls[nc++] = g_gbaic_class;
    if (g_aic_class) cls[nc++] = g_aic_class;
    for (int k = 0; k < nc; k++) {
        char cn[64] = "?";
        names_get((uint64_t)(rd32(cls[k] + 0x48) - g_cheat_off), cn, sizeof cn);
        int n = 0;
        for (int32_t i = 0; i < g_gobj_num; i++) {
            uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
            if (!o || rd64(o + 0x40) != cls[k]) continue;   // Outer == 类 → 成员
            char nm[80] = "?";
            if (!names_get((uint64_t)(rd32(o + 0x48) - g_cheat_off), nm, sizeof nm)) continue;
            cheat_log("fn %s.%s flags=%x ps=%d", cn, nm,
                      (unsigned)rd32(o + 0xc0), (int)(rd32(o + 0xc8) >> 16));
            n++;
        }
        cheat_log("mindfns：%s(%llx) 成员 %d 个", cn, (unsigned long long)cls[k], n);
    }
}
// 属性（UProperty）偏移：+0x7c=Offset，+0x6c=ElementSize
static int prop_off(uint64_t cls, const char *nm, int *esz) {
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || rd64(o + 0x40) != cls) continue;
        if (!cheat_name_is(o, nm)) continue;
        if (esz) *esz = (int)rd32(o + 0x6c);
        return (int)rd32(o + 0x7c);
    }
    return -1;
}
// aiprobe：诊断 AI 为什么不动 —— ①问 CanTickAI 允不允许 tick ②对玩家下 ForceMoveToActor
static void cheat_aiprobe(void) {
    if (!g_nminds) { cheat_log("aiprobe：还没有 AI，先 spawnai"); return; }
    uint64_t m = g_minds[0];
    uint64_t fn = cheat_member(g_mind_class, "CanTickAI", NULL);
    if (fn) {
        uint8_t p[32] __attribute__((aligned(16))); memset(p, 0, sizeof p);
        float dt = 0.033f; memcpy(p, &dt, 4);
        cheat_pe((void *)(uintptr_t)m, (void *)(uintptr_t)fn, p);
        cheat_log("aiprobe：CanTickAI 返回缓冲 %02x %02x %02x %02x（ParmsSize %d）",
                  p[0], p[1], p[2], p[3], (int)(rd32(fn + 0xc8) >> 16));
    } else cheat_log("aiprobe：没找到 CanTickAI");
    // ForceMoveToActor(玩家 Pawn)：能走过去就说明寻路/移动链路是好的
    uint64_t pw = 0;
    for (int32_t i = 0; i < g_gobj_num && !pw; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!q || rd64(q + 0x50) != g_playerpawn_class) continue;
        float v[3]; if (!read_vec3(q + OFFS_ACTOR_LOC, v)) continue;
        if (v[0] == 0 && v[1] == 0 && v[2] == 0) continue;
        pw = q;
    }
    uint64_t fm = cheat_member(g_mind_class, "ForceMoveToActor", NULL);
    if (fm && pw) {
        uint8_t p[16] __attribute__((aligned(16))); memset(p, 0, sizeof p);
        memcpy(p, &pw, 8);
        cheat_pe((void *)(uintptr_t)m, (void *)(uintptr_t)fm, p);
        cheat_log("aiprobe：已 ForceMoveToActor(%llx)", (unsigned long long)pw);
    } else cheat_log("aiprobe：ForceMoveToActor %llx 玩家 %llx", (unsigned long long)fm, (unsigned long long)pw);
    // 用 GetActor 验证「返回值读法」是否可靠：应等于 Mind+0x128 的 Pawn
    uint64_t ga = cheat_member(g_mind_class, "GetActor", NULL);
    if (ga) {
        uint8_t p[16] __attribute__((aligned(16))); memset(p, 0, sizeof p);
        cheat_pe((void *)(uintptr_t)m, (void *)(uintptr_t)ga, p);
        uint64_t v = 0; memcpy(&v, p, 8);
        cheat_log("aiprobe：GetActor = %llx（Mind+0x128 = %llx）",
                  (unsigned long long)v, (unsigned long long)rd64(m + 0x128));
    }
}
// aiinit：补调真实 AI 出生时才会走的初始化，再看 CanTickAI 是否放行
static void ai_call_v(void *m, const char *nm) {
    uint64_t f = cheat_member(g_mind_class, nm, NULL);
    if (!f) { cheat_log("aiinit：没有 %s", nm); return; }
    uint8_t p[16] __attribute__((aligned(16))); memset(p, 0, sizeof p);
    cheat_pe(m, (void *)(uintptr_t)f, p);
    cheat_log("aiinit：已调用 %s", nm);
}
static void cheat_aiinit(void) {
    if (!g_nminds) { cheat_log("aiinit：还没有 AI，先 spawnai"); return; }
    uint64_t m = g_minds[0];
    int esz = 0, off;
    off = prop_off(g_mind_class, "AIDefOverride", &esz);
    if (off >= 0) cheat_log("aiinit：AIDefOverride @+0x%x = %llx（esz %d）", off,
                            (unsigned long long)rd64(m + off), esz);
    else cheat_log("aiinit：找不到 AIDefOverride 属性");
    off = prop_off(g_mind_class, "bCharacterClassInitialized", &esz);
    if (off >= 0) {
        uint32_t w = (uint32_t)rd32(m + off);
        cheat_log("aiinit：bCharacterClassInitialized @+0x%x 字节 %02x %02x %02x %02x", off,
                  w & 0xff, (w >> 8) & 0xff, (w >> 16) & 0xff, (w >> 24) & 0xff);
    } else cheat_log("aiinit：找不到 bCharacterClassInitialized 属性");
    ai_call_v((void *)(uintptr_t)m, "InitializeCharacterClass");
    ai_call_v((void *)(uintptr_t)m, "InitNavigationHandle");
    ai_call_v((void *)(uintptr_t)m, "RecalculateAttributeInitializedState");
    off = prop_off(g_mind_class, "bCharacterClassInitialized", &esz);
    if (off >= 0) cheat_log("aiinit：初始化后 bCharacterClassInitialized = %02x",
                            (unsigned)rd32(m + off) & 0xff);
    uint64_t f = cheat_member(g_mind_class, "CanTickAI", NULL);
    if (f) {
        uint8_t p[32] __attribute__((aligned(16))); memset(p, 0, sizeof p);
        float dt = 0.033f; memcpy(p, &dt, 4);
        cheat_pe((void *)(uintptr_t)m, (void *)(uintptr_t)f, p);
        cheat_log("aiinit：CanTickAI 再问 = %02x %02x %02x %02x", p[0], p[1], p[2], p[3]);
    }
}
// aipatch on|off：把 CanTickAI 原生实现改成 return true，验证它是不是唯一的闸门
static uint32_t g_cantick_save[2]; static int g_cantick_patched;
static void cheat_aipatch(int on) {
    uint64_t a = sym_at("_ZN11AWillowMind9CanTickAIEf", NULL, 0);
    if (!a) a = sym_at("CanTickAI", NULL, 0);
    if (!a) { cheat_log("aipatch：找不到 CanTickAI 原生符号"); return; }
    uint32_t *w = (uint32_t *)(uintptr_t)a;
    uintptr_t pg = (uintptr_t)a & ~(uintptr_t)0x3FFF;
    size_t len = (size_t)((((uintptr_t)a + 8) - pg + 0x3FFF) & ~(uintptr_t)0x3FFF);
    if (mprotect((void *)pg, len, PROT_READ | PROT_WRITE | PROT_EXEC)) { cheat_log("aipatch：mprotect 失败"); return; }
    if (on && !g_cantick_patched) {
        g_cantick_save[0] = w[0]; g_cantick_save[1] = w[1];
        w[0] = 0x52800020;   // mov w0, #1
        w[1] = 0xd65f03c0;   // ret
        g_cantick_patched = 1;
    } else if (!on && g_cantick_patched) {
        w[0] = g_cantick_save[0]; w[1] = g_cantick_save[1];
        g_cantick_patched = 0;
    }
    mprotect((void *)pg, len, PROT_READ | PROT_EXEC);
    __builtin___clear_cache((char *)(uintptr_t)a, (char *)(uintptr_t)a + 8);
    cheat_log("aipatch：%s CanTickAI @%llx（原指令 %08x %08x）", on ? "已改为 return true" : "已还原",
              (unsigned long long)a, g_cantick_save[0], g_cantick_save[1]);
}
// dis <符号子串>：把函数前 64 条指令写到 cheat.dis（拉回 PC 用 llvm-mc 反汇编）
static void cheat_dis(const char *sub) {
    char nm[160] = "?";
    uint64_t a = sym_at(sub, nm, sizeof nm);
    if (!a) { cheat_log("dis：没有符号 %s", sub); return; }
    uint32_t w[64];
    if (!safe_read(a, w, sizeof w)) { cheat_log("dis：读不了 %llx", (unsigned long long)a); return; }
    char p[1200]; snprintf(p, sizeof p, "%s/cheat.dis", g_dir);
    FILE *f = fopen(p, "a");
    if (!f) { cheat_log("dis：打不开 cheat.dis"); return; }
    fprintf(f, "SYM %s %llx\n", nm, (unsigned long long)a);
    for (int i = 0; i < 64; i++) fprintf(f, "%08x\n", w[i]);
    fclose(f);
    cheat_log("dis：%s @%llx 前四条 %08x %08x %08x %08x", nm, (unsigned long long)a, w[0], w[1], w[2], w[3]);
}
// syms <子串>：列出符号表里名字含该子串的符号（找真正的 Tick 入口）
static void cheat_syms(const char *sub) {
    module_t *m = &g_mod[0];
    if (!m->symtab || !m->strtab) { cheat_log("syms：没有符号表"); return; }
    int n = 0;
    for (unsigned i = 0; i < m->nsym; i++) {
        const char *nm = m->strtab + m->symtab[i].st_name;
        if (!nm || !*nm || !strstr(nm, sub)) continue;
        cheat_log("sym %s @+%llx", nm, (unsigned long long)m->symtab[i].st_value);
        if (++n >= 400) break;
    }
    cheat_log("syms：\"%s\" 共 %d 个", sub, n);
}
// aidump：把场上每个 WillowMind（含我们自己生成的）关键字段列出来做对比
static void cheat_aidump(void) {
    int n = 0, mine = 0;
    for (int32_t i = 0; i < g_gobj_num && n < 10; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || rd64(o + 0x50) != g_mind_class) continue;
        int ismine = 0;
        for (int k = 0; k < g_nminds; k++) if (g_minds[k] == o) ismine = 1;
        if (ismine && mine++ >= 1) continue;
        uint64_t pn = rd64(o + 0x128);
        char pcn[64] = "?";
        if (pn) {
            uint64_t pc = rd64(pn + 0x50);
            if (pc) names_get((uint64_t)(rd32(pc + 0x48) - g_cheat_off), pcn, sizeof pcn);
        }
        float v[3] = {0, 0, 0};
        if (pn) read_vec3(pn + OFFS_ACTOR_LOC, v);
        cheat_log("aidump：%s mind=%llx pawn=%llx(%s) +0x348=%d +0x9c8=%llx +0x9d0=%02x loc=[%.0f %.0f %.0f]",
                  ismine ? "我们的" : "真AI", (unsigned long long)o, (unsigned long long)pn, pcn,
                  (int)rd32(o + 0x348), (unsigned long long)rd64(o + 0x9c8),
                  (unsigned)rd32(o + 0x9d0) & 0xff, v[0], v[1], v[2]);
        n++;
    }
    cheat_log("aidump：共列出 %d 个 WillowMind", n);
}
// aidiff：拿一个真实 AI 的 Mind 和我们的 Mind 逐属性对比（只列不同的）
static void cheat_aidiff(void) {
    uint64_t mine = ai_mine(), real = ai_find_real(mine);
    if (!real || !mine) { cheat_log("aidiff：真AI=%llx 我们的=%llx（需要场上有真实 AI 且先生成）",
                                    (unsigned long long)real, (unsigned long long)mine); return; }
    cheat_log("aidiff：真AI %llx(+0x348=%d +0x9d0=%02x) vs 我们 %llx(+0x348=%d +0x9d0=%02x)",
              (unsigned long long)real, (int)rd32(real + 0x348), (unsigned)rd32(real + 0x9d0) & 0xff,
              (unsigned long long)mine, (int)rd32(mine + 0x348), (unsigned)rd32(mine + 0x9d0) & 0xff);
    int n = 0;
    for (int32_t i = 0; i < g_gobj_num && n < 100; i++) {
        uint64_t p = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!p || rd64(p + 0x40) != g_mind_class) continue;   // Outer == WillowMind 类 → 属性
        char nm[80] = "?";
        if (!names_get((uint64_t)(rd32(p + 0x48) - g_cheat_off), nm, sizeof nm)) continue;
        int esz = (int)rd32(p + 0x6c), off = (int)rd32(p + 0x7c);
        if (off <= 0 || off > 0xA00 || (esz != 1 && esz != 4 && esz != 8)) continue;
        uint64_t a, b;
        if (esz == 8) { a = rd64(real + off); b = rd64(mine + off); }
        else if (esz == 4) { a = rd32(real + off); b = rd32(mine + off); }
        else { a = (uint8_t)rd32(real + off); b = (uint8_t)rd32(mine + off); }
        if (a == b) continue;
        cheat_log("aidiff：%s @+0x%x esz=%d 真=%llx 我们=%llx", nm, off, esz,
                  (unsigned long long)a, (unsigned long long)b);
        n++;
    }
    cheat_log("aidiff：差异 %d 项", n);
}
// aifix：从真实 AI 复制缺失的角色定义/AIDef，对齐初始化标志，然后启动 tick + 跟随
static void cheat_aifix(void) {
    uint64_t mine = g_last_mind;
    if (!mine && g_nminds) mine = g_minds[g_nminds - 1];
    if (!mine) { cheat_log("aifix：没有我们的 Mind（先 spawnai <原型> quiet）"); return; }
    uint64_t real = 0;
    for (int32_t i = 0; i < g_gobj_num && !real; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || rd64(o + 0x50) != g_mind_class) continue;
        if (!rd64(o + 0x128)) continue;
        int ismine = 0;
        for (int k = 0; k < g_nminds; k++) if (g_minds[k] == o) ismine = 1;
        if (o != mine && !ismine) real = o;
    }
    if (!real) { cheat_log("aifix：场上没有真实 AI 可参照（找有敌人的地方）"); return; }
    cheat_log("aifix：我们 %llx 参照 %llx（+0x9d0 真=%02x 我们=%02x）",
              (unsigned long long)mine, (unsigned long long)real,
              (unsigned)rd32(real + 0x9d0) & 0xff, (unsigned)rd32(mine + 0x9d0) & 0xff);
    int copied = 0;
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t p = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!p || rd64(p + 0x40) != g_mind_class) continue;
        if ((int)rd32(p + 0x6c) != 8) continue;
        int off = (int)rd32(p + 0x7c);
        if (off <= 0 || off > 0xA00) continue;
        char nm[80] = "?";
        if (!names_get((uint64_t)(rd32(p + 0x48) - g_cheat_off), nm, sizeof nm)) continue;
        if (!strstr(nm, "CharacterClass") && strcmp(nm, "AIDef") && strcmp(nm, "AIClass")) continue;   // 角色定义/行为定义
        uint64_t rv = rd64(real + off), mv = rd64(mine + off);
        if (!rv || rv == mv) continue;
        cheat_log("aifix：%s @+0x%x 我们 %llx -> 真 %llx", nm, off,
                  (unsigned long long)mv, (unsigned long long)rv);
        *(volatile uint64_t *)(uintptr_t)(mine + off) = rv;
        copied++;
    }
    // Possess 只填了通用 Pawn，WillowMind 自己缓存的 MyWillowPawn 还是空 → TickAuthoritative 会空转
    int esz2 = 0, offp = prop_off(g_mind_class, "MyWillowPawn", &esz2);
    uint64_t mypawn = rd64(mine + 0x128);
    if (offp >= 0 && mypawn && !rd64(mine + offp)) {
        *(volatile uint64_t *)(uintptr_t)(mine + offp) = mypawn;
        cheat_log("aifix：MyWillowPawn @+0x%x = %llx", offp, (unsigned long long)mypawn);
        copied++;
    }
    // 父类上声明的 AIDef 才是行为驱动源：都是空属性类（Property），跨类找
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t p = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!p) continue;
        uint64_t pc = rd64(p + 0x50);
        if (!pc) continue;
        char pcn[64] = "?";
        if (!names_get((uint64_t)(rd32(pc + 0x48) - g_cheat_off), pcn, sizeof pcn)) continue;
        if (!strstr(pcn, "Property")) continue;
        char nm[80] = "?";
        if (!names_get((uint64_t)(rd32(p + 0x48) - g_cheat_off), nm, sizeof nm)) continue;
        if (strcmp(nm, "AIDef") && strcmp(nm, "SpawnAIDef")) continue;
        int esz = (int)rd32(p + 0x6c), off = (int)rd32(p + 0x7c);
        if (esz != 8 || off <= 0 || off > 0xA00) continue;
        uint64_t rv = rd64(real + off), mv = rd64(mine + off);
        if (!rv || rv == mv) continue;
        cheat_log("aifix：父类 %s @+0x%x 我们 %llx -> 真 %llx", nm, off,
                  (unsigned long long)mv, (unsigned long long)rv);
        *(volatile uint64_t *)(uintptr_t)(mine + off) = rv;
        copied++;
    }
    // +0x888 是 Mind 缓存的 Actor/Pawn（GetActor/GetAllegiance 都读它），为空则 TickAuthoritative 立刻返回
    uint64_t old888 = rd64(mine + 0x888);
    if (mypawn) {
        *(volatile uint64_t *)(uintptr_t)(mine + 0x888) = mypawn;
        if (old888 != mypawn)
            cheat_log("aifix：+0x888 Pawn 缓存 %llx -> %llx", (unsigned long long)old888,
                      (unsigned long long)mypawn);
    }
    cheat_log("aifix：字段对比 真[888=%llx 878=%llx 998=%llx 870=%02x 890=%02x] 我们[888=%llx 878=%llx 998=%llx 870=%02x 890=%02x]",
              (unsigned long long)rd64(real + 0x888), (unsigned long long)rd64(real + 0x878),
              (unsigned long long)rd64(real + 0x998), (unsigned)rd32(real + 0x870) & 0xff,
              (unsigned)rd32(real + 0x890) & 0xff,
              (unsigned long long)rd64(mine + 0x888), (unsigned long long)rd64(mine + 0x878),
              (unsigned long long)rd64(mine + 0x998), (unsigned)rd32(mine + 0x870) & 0xff,
              (unsigned)rd32(mine + 0x890) & 0xff);
    uint32_t rb = (uint32_t)rd32(real + 0x9d0);
    *(volatile uint32_t *)(uintptr_t)(mine + 0x9d0) = rb;   // 角色定义初始化等标志位
    ai_call_v((void *)(uintptr_t)mine, "InitializeCharacterClass");
    ai_call_v((void *)(uintptr_t)mine, "InitNavigationHandle");
    ai_call_v((void *)(uintptr_t)mine, "RecalculateAttributeInitializedState");
    cheat_log("aifix：复制 %d 项，+0x9d0 现在=%02x", copied, (unsigned)rd32(mine + 0x9d0) & 0xff);
    // 找玩家 Pawn 作为跟随目标
    g_ai_player_pawn = 0;
    for (int32_t i = 0; i < g_gobj_num && !g_ai_player_pawn; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!q || rd64(q + 0x50) != g_playerpawn_class) continue;
        float v[3];
        if (!read_vec3(q + OFFS_ACTOR_LOC, v)) continue;
        if (v[0] == 0 && v[1] == 0 && v[2] == 0) continue;
        g_ai_player_pawn = q;
    }
    if (!g_fn_forcemove) g_fn_forcemove = cheat_member(g_mind_class, "ForceMoveToActor", NULL);
    g_ai_follow = g_ai_player_pawn && g_fn_forcemove;
    int reg = 0;
    for (int k = 0; k < g_nminds; k++) if (g_minds[k] == mine) reg = 1;
    if (!reg && g_nminds < 8) { g_minds[g_nminds++] = mine; reg = 1; }
    g_ai_next_ms = now_ms() + 500;
    cheat_log("aifix：%s，玩家 %llx，ForceMoveToActor %llx，跟随 %s",
              reg ? "已接入 tick" : "没接进 tick", (unsigned long long)g_ai_player_pawn,
              (unsigned long long)g_fn_forcemove, g_ai_follow ? "开" : "关");
}
static uint64_t ai_mine(void) {
    if (g_last_mind) return g_last_mind;
    return g_nminds ? g_minds[g_nminds - 1] : 0;
}
static uint64_t ai_find_real(uint64_t mine) {
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o || rd64(o + 0x50) != g_mind_class) continue;
        if (!rd64(o + 0x128)) continue;
        int ismine = (o == mine);
        for (int k = 0; k < g_nminds && !ismine; k++) if (g_minds[k] == o) ismine = 1;
        if (!ismine) return o;
    }
    return 0;
}
// aiprops：把 Mind 的所有简单属性（1/4/8 字节）真AI vs 我们 全部列出来
static void cheat_aiprops(void) {
    uint64_t mine = ai_mine(), real = ai_find_real(mine);
    if (!mine || !real) { cheat_log("aiprops：我们=%llx 真AI=%llx", (unsigned long long)mine, (unsigned long long)real); return; }
    cheat_log("aiprops：我们 %llx vs 真AI %llx", (unsigned long long)mine, (unsigned long long)real);
    int n = 0;
    for (int32_t i = 0; i < g_gobj_num && n < 140; i++) {
        uint64_t p = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!p || rd64(p + 0x40) != g_mind_class) continue;
        char nm[80] = "?";
        if (!names_get((uint64_t)(rd32(p + 0x48) - g_cheat_off), nm, sizeof nm)) continue;
        int esz = (int)rd32(p + 0x6c), off = (int)rd32(p + 0x7c);
        if (off <= 0 || off > 0xA00 || (esz != 1 && esz != 4 && esz != 8)) continue;
        uint64_t rv, mv;
        if (esz == 8) { rv = rd64(real + off); mv = rd64(mine + off); }
        else if (esz == 4) { rv = rd32(real + off); mv = rd32(mine + off); }
        else { rv = (uint8_t)rd32(real + off); mv = (uint8_t)rd32(mine + off); }
        if (!rv && !mv) continue;
        cheat_log("aiprops：%s @+0x%x esz=%d 真=%llx 我们=%llx%s", nm, off, esz,
                  (unsigned long long)rv, (unsigned long long)mv, rv == mv ? " 同" : "");
        n++;
    }
    cheat_log("aiprops：共 %d 项", n);
}
// aiprops2：跨父类列出所有 AIDef/Sequence/Class 类属性（这些声明在父类上）
static void cheat_aiprops2(void) {
    uint64_t mine = ai_mine(), real = ai_find_real(mine);
    if (!mine || !real) { cheat_log("aiprops2：我们=%llx 真AI=%llx", (unsigned long long)mine, (unsigned long long)real); return; }
    int n = 0;
    for (int32_t i = 0; i < g_gobj_num && n < 80; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o) continue;
        uint64_t oc = rd64(o + 0x50);
        if (!oc) continue;
        char cn[64] = "?";
        if (!names_get((uint64_t)(rd32(oc + 0x48) - g_cheat_off), cn, sizeof cn)) continue;
        if (!strstr(cn, "Property")) continue;            // 只认 UProperty 子类
        char nm[80] = "?";
        if (!names_get((uint64_t)(rd32(o + 0x48) - g_cheat_off), nm, sizeof nm)) continue;
        if (!strstr(nm, "AIDef") && !strstr(nm, "Sequence") && strcmp(nm, "AIClass")) continue;
        int esz = (int)rd32(o + 0x6c), off = (int)rd32(o + 0x7c);
        if (off <= 0 || off > 0xA00) continue;
        uint64_t rv, mv;
        if (esz == 8) { rv = rd64(real + off); mv = rd64(mine + off); }
        else if (esz == 4) { rv = rd32(real + off); mv = rd32(mine + off); }
        else if (esz == 1) { rv = (uint8_t)rd32(real + off); mv = (uint8_t)rd32(mine + off); }
        else continue;
        char on[64] = "?";
        uint64_t outer = rd64(o + 0x40);
        if (outer) names_get((uint64_t)(rd32(outer + 0x48) - g_cheat_off), on, sizeof on);
        cheat_log("aiprops2：%s.%s @+0x%x esz=%d 真=%llx 我们=%llx%s", on, nm, off, esz,
                  (unsigned long long)rv, (unsigned long long)mv, rv == mv ? " 同" : "");
        n++;
    }
    cheat_log("aiprops2：共 %d 项", n);
}
// aicont [add]：定位 WorldInfo 里的控制器数组（TArray<AController*>），可把我们的 Mind 加进去
static void cheat_aicont(int add) {
    uint64_t wi = 0;
    for (int32_t i = 0; i < g_gobj_num && !wi; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o) continue;
        uint64_t c = rd64(o + 0x50);
        if (!c || !cheat_name_is(c, "WorldInfo")) continue;
        float v[3];
        if (!read_vec3(o + OFFS_ACTOR_LOC, v)) continue;
        wi = o;
    }
    if (!wi) { cheat_log("aicont：找不到 WorldInfo 实例"); return; }
    uint64_t mine = ai_mine(), real = ai_find_real(mine);
    cheat_log("aicont：WorldInfo %llx 真AI %llx 我们 %llx", (unsigned long long)wi,
              (unsigned long long)real, (unsigned long long)mine);
    if (!real) { cheat_log("aicont：场上没有真实 AI"); return; }
    // 在 WorldInfo 对象里找指向真 AI 的数组元素
    int hits = 0;
    for (int off = 0; off + 24 <= 0x3000; off += 8) {
        uint64_t data = rd64(wi + off);
        int32_t num = (int32_t)rd32(wi + off + 8), max = (int32_t)rd32(wi + off + 16);
        if (!data || num <= 0 || num > 256 || max < num) continue;
        uint64_t hit = 0;
        for (int k = 0; k < num; k++) {
            uint64_t e = rd64(data + (uint64_t)k * 8);
            if (e == real) { hit = e; break; }
        }
        if (!hit) continue;
        cheat_log("aicont：控制器数组 @WorldInfo+0x%x Data=%llx Num=%d Max=%d", off, (unsigned long long)data, num, max);
        hits++;
        if (!add || !mine) continue;
        int have = 0;
        for (int k = 0; k < num; k++) if (rd64(data + (uint64_t)k * 8) == mine) have = 1;
        if (have) { cheat_log("aicont：已经在数组里"); continue; }
        if (num < max) {
            *(volatile uint64_t *)(uintptr_t)(data + (uint64_t)num * 8) = mine;
            *(volatile int32_t *)(uintptr_t)(wi + off + 8) = num + 1;
            cheat_log("aicont：已追加到数组（%d -> %d）", num, num + 1);
        } else if (g_gmalloc && g_mswitch) {
            uint64_t g = rd64(g_gmalloc);
            void *(*m)(void *, unsigned, unsigned) = (void *(*)(void *, unsigned, unsigned))(uintptr_t)g_mswitch;
            int nmax = max + 8;
            void *nb = g ? m((void *)(uintptr_t)g, (unsigned)(nmax * 8), 16) : NULL;
            if (!nb) { cheat_log("aicont：分配新数组失败"); continue; }
            memcpy(nb, (void *)(uintptr_t)data, (size_t)num * 8);
            ((uint64_t *)nb)[num] = mine;
            *(volatile uint64_t *)(uintptr_t)(wi + off) = (uint64_t)(uintptr_t)nb;
            *(volatile int32_t *)(uintptr_t)(wi + off + 8) = num + 1;
            *(volatile int32_t *)(uintptr_t)(wi + off + 16) = nmax;
            cheat_log("aicont：扩容数组 %d->%d 并追加", max, nmax);
        }
    }
    cheat_log("aicont：命中 %d 个数组", hits);
}
// weather：列出本图已加载的天气模板（基础图没有，只有冰原 DLC 有雪天）
static void cheat_weather(void) {
    int n = 0;
    for (int32_t i = 0; i < g_gobj_num; i++) {
        uint64_t o = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!o) continue;
        uint64_t c = rd64(o + 0x50);
        if (!c) continue;
        char cn[64] = "";
        if (!names_get((uint64_t)(rd32(c + 0x48) - g_cheat_off), cn, sizeof cn)) continue;
        if (strcmp(cn, "WeatherSystemTemplate")) continue;
        char on[80] = "?";
        names_get((uint64_t)(rd32(o + 0x48) - g_cheat_off), on, sizeof on);
        cheat_log("weather：模板 %s", on);
        n++;
    }
    cheat_log("weather：本图天气模板 %d 个（基础图没有天气，只有冰原 DLC 的雪天）", n);
}
static void cheat_cycle_toggle(void) {
    g_cycle_on = !g_cycle_on;
    g_cycle_next = 0;
    cheat_log("cycle：%s（每 5 秒换一次时间）", g_cycle_on ? "开" : "关");
}
// ---- 游戏线程执行点 ----
static void cheat_drain(void) {
    static volatile int busy;
    if (busy) return;
    if (!__atomic_load_n(&g_pending_on, __ATOMIC_ACQUIRE)) return;
    busy = 1;
    __atomic_store_n(&g_pending_on, 0, __ATOMIC_RELEASE);
    char buf[128]; memcpy(buf, g_pending, sizeof buf);
    cheat_run(buf);   // 现在在游戏线程里调 ProcessEvent，生成/改世界才安全
    busy = 0;
}
static int64_t now_ms(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}
// 在游戏线程里给所有手动生成的 Mind 上发条（约每 30ms 一次）
static void cheat_ai_tick(void) {
    static volatile int busy;                     // TickAuthoritative 内部会再调 ProcessEvent，必须防重入
    static int64_t last;
    if (busy) return;
    if ((!g_fn_tickai && !g_uf_tickai) || !g_nminds) return;
    int64_t t = now_ms();
    if (t < g_ai_next_ms) return;
    g_ai_next_ms = t + 33;                        // 约 30Hz
    float dt = last ? (float)(t - last) / 1000.0f : 0.033f;
    last = t;
    if (dt <= 0.0f || dt > 0.2f) dt = 0.033f;
    busy = 1;
    static int tick_n;
    if (tick_n < 3 || tick_n % 30 == 0) {
        uint64_t pn = rd64(g_minds[0] + 0x128);
        float v[3] = {0, 0, 0}; int32_t r3[3] = {0, 0, 0};
        if (pn) { read_vec3(pn + OFFS_ACTOR_LOC, v); safe_read(pn + OFFS_ACTOR_LOC + 12, r3, 12); }
        cheat_log("ai tick #%d mind=%llx pawn=%llx loc=[%.0f %.0f %.0f] yaw=%d dt=%.3f",
                  tick_n, (unsigned long long)g_minds[0], (unsigned long long)pn,
                  v[0], v[1], v[2], r3[1] / 65536, dt);
    }
    tick_n++;
    if (g_ai_follow && g_fn_forcemove && g_ai_player_pawn && tick_n % 60 == 0) {
        uint8_t fp[16] __attribute__((aligned(16))); memset(fp, 0, sizeof fp);
        memcpy(fp, &g_ai_player_pawn, 8);
        cheat_pe((void *)(uintptr_t)g_minds[0], (void *)(uintptr_t)g_fn_forcemove, fp);
    }
    for (int i = 0; i < g_nminds; i++) {
        if (!g_minds[i]) continue;
        if (g_uf_tickai) {                        // 走脚本虚拟机（最稳，能触发原生实现）
            uint8_t p[16] __attribute__((aligned(16))); memset(p, 0, sizeof p);
            memcpy(p, &dt, 4);
            cheat_pe((void *)(uintptr_t)g_minds[i], (void *)(uintptr_t)g_uf_tickai, p);
        } else {                                  // 直接调原生符号 TickAuthoritative(float)
            ((void (*)(void *, float))(uintptr_t)g_fn_tickai)((void *)(uintptr_t)g_minds[i], dt);
        }
    }
    busy = 0;
}
static void pe_hook(void *o, void *f, void *p, void *r) {
    __atomic_fetch_add(&g_pe_hits, 1, __ATOMIC_RELAXED);
    if (__atomic_load_n(&g_pending_on, __ATOMIC_RELAXED)) cheat_drain();
    if (g_nminds) cheat_ai_tick();
    g_pe_orig(o, f, p, r);
}
// 最小 ARM64 hook：目标前 16 字节搬到跳板（+ ldr x16/br 回 target+16），再在目标写 ldr x16/br 到 hook
static int bl2_hook(uint64_t addr, void *hookfn, void **orig) {
    void *t = mmap(NULL, 0x4000, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (t == MAP_FAILED) return 0;
    memcpy(t, (void *)(uintptr_t)addr, 16);
    uint32_t *tw = (uint32_t *)t;
    uint64_t rest = addr + 16;
    tw[4] = 0x58000050; tw[5] = 0xd61f0200;
    tw[6] = (uint32_t)rest; tw[7] = (uint32_t)(rest >> 32);
    if (mprotect(t, 0x4000, PROT_READ | PROT_EXEC)) { munmap(t, 0x4000); return 0; }
    __builtin___clear_cache((char *)t, (char *)(tw + 8));
    uint32_t *at = (uint32_t *)(uintptr_t)addr;
    uint8_t *pg = (uint8_t *)((uintptr_t)at & ~(uintptr_t)0x3FFF);
    size_t len = (size_t)(((uintptr_t)(at + 4) - (uintptr_t)pg + 0x3FFF) & ~(uintptr_t)0x3FFF);
    if (mprotect(pg, len, PROT_READ | PROT_WRITE)) { munmap(t, 0x4000); return 0; }
    uint32_t j[4] = {0x58000050, 0xd61f0200, (uint32_t)(uintptr_t)hookfn, (uint32_t)((uint64_t)(uintptr_t)hookfn >> 32)};
    memcpy(at, j, 16);
    mprotect(pg, len, PROT_READ | PROT_EXEC);
    __builtin___clear_cache((char *)at, (char *)(at + 4));
    *orig = t;
    return 1;
}
// 启动时装（nnMain 之前），此时没有客体线程在执行被改的那 16 字节
static int g_hook_status;   // 0 未试, 1 成功, 2 找不到符号, 3 打补丁失败
static int cheat_install_pe(void) {
    if (g_pe_orig) { g_hook_status = 1; return 1; }
    module_t *m = NULL;
    for (int i = 0; i < g_nmod; i++) if (!strcmp(g_mod[i].name, "main")) m = &g_mod[i];
    if (!m) m = &g_mod[0];
    uint64_t a = sym_at("_ZN7UObject12ProcessEventEP9UFunctionPvS2_", NULL, 0);
    if (!a) { g_hook_status = 2; return 0; }
    void *orig = NULL;
    if (!bl2_hook(a, (void *)pe_hook, &orig)) { g_hook_status = 3; return 0; }
    g_pe_orig = (void (*)(void *, void *, void *, void *))orig;
    g_hook_status = 1;
    LOG("BL2 cheat: ProcessEvent hook in (main+%#llx)", (unsigned long long)(a - (uint64_t)m->base));
    return 1;
}
static int cheat_scan(void) {
    char p[1200];
    g_mbase = (uint64_t)g_mod[0].base; g_mend = g_mbase + g_mod[0].size;
    if (!read_maps()) return 0;
    snprintf(p, sizeof p, "%s/cheat.scan", g_dir);
    FILE *o = fopen(p, "w");
    if (!o) return 0;
    g_names_at = g_names_n = 0;
    cheat_log("扫描名字表…");
    find_array(o);
    fclose(o);
    if (g_names_n < 256) { cheat_log("找不到名字表（%llu 项）", (unsigned long long)g_names_n); return 0; }
    uint64_t go = sym_at("GObjObjects", NULL, 0);
    if (!go) { cheat_log("找不到 GObjObjects"); return 0; }
    g_gobj_sym = go;
    g_gobj_data = rd64(go); g_gobj_num = rd32(go + 8);
    if (!g_gobj_data || g_gobj_num <= 0) { cheat_log("GObjObjects 为空"); return 0; }
    uint64_t cls = 0;
    for (int k = 0; k < 2 && !cls; k++) {   // 名字表槽位偏移随版本可能是 3000 或 0：用成员验证
        g_cheat_off = k ? 0 : 3000;
        cls = cheat_find_class("WillowCheatManager");
    }
    if (!cls) { cheat_log("找不到 WillowCheatManager 类（%d 个对象）", g_gobj_num); return 0; }
    g_cheat_class = cls;
    g_cheat_class2 = cheat_find_class("CheatManager");   // 父类：Ghost/Fly/GiveWeapon 在它身上
    for (int32_t i = 0; i < g_gobj_num && !g_cheat_inst; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (!q || rd64(q + 0x50) != cls) continue;
        if (cheat_name_is(q, "WillowCheatManager")) g_cheat_inst = q;   // Default__WillowCheatManager 名字不同
    }
    char sn[160] = "";
    // M2：阵营锚点（玩家阵营对象 + Pawn::SetAllegiance）
    for (int32_t i = 0; i < g_gobj_num && !g_aipawn_class; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (q && cheat_name_is(q, "WillowAIPawn") && cheat_has_member(q)) g_aipawn_class = q;
    }
    for (int32_t i = 0; i < g_gobj_num && !g_playerpawn_class; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (q && cheat_name_is(q, "WillowPlayerPawn") && cheat_has_member(q)) g_playerpawn_class = q;
    }
    g_pawn_class = cheat_class_with_member("Pawn", "SetAllegiance");
    g_fn_setalleg = g_pawn_class ? cheat_member(g_pawn_class, "SetAllegiance", NULL) : 0;
    g_alleg_player = cheat_object_named("Allegiance_Player");
    g_fn_gettarget = cheat_member(g_cheat_class, "DebugGetPlayerTarget", NULL);
    g_fn_timeofday = cheat_member(g_cheat_class, "SetTimeOfDay", NULL);
    uint64_t pc_cls = cheat_class_with_member("PlayerController", "SendToConsole");
    g_pc_class = pc_cls;
    g_fn_console = pc_cls ? cheat_member(pc_cls, "SendToConsole", NULL) : 0;
    g_fn_travel = pc_cls ? cheat_member(pc_cls, "LocalTravel", NULL) : 0;
    g_gmalloc = sym_exact("GMalloc");
    g_mswitch = sym_at("_ZN13FMallocSwitch6MallocEjj", NULL, 0);
    g_world_sym = sym_exact("GWorld");
    g_spawn_fn = sym_at("_ZN6UWorld10SpawnActorEP6UClass5FName", NULL, 0);
    g_fn_viewloc = g_pawn_class ? cheat_member(g_pawn_class, "GetPawnViewLocation", NULL) : 0;
    if (!g_fn_viewloc) {
        uint64_t wpc = cheat_class_with_member("WillowPawn", "GetPawnViewLocation");
        g_fn_viewloc = wpc ? cheat_member(wpc, "GetPawnViewLocation", NULL) : 0;
    }
    for (int32_t i = 0; i < g_gobj_num && !g_aic_class; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (q && cheat_name_is(q, "AIController") && cheat_has_member(q)) g_aic_class = q;
    }
    uint64_t ctl_cls = cheat_class_with_member("Controller", "Possess");
    g_fn_possess = ctl_cls ? cheat_member(ctl_cls, "Possess", NULL) : 0;
    for (int32_t i = 0; i < g_gobj_num && !g_mind_class; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (q && cheat_name_is(q, "WillowMind") && cheat_has_member(q)) g_mind_class = q;
    }
    g_fn_initseq = g_mind_class ? cheat_member(g_mind_class, "InitSequence", NULL) : 0;
    g_uf_tickai = g_mind_class ? cheat_member(g_mind_class, "TickAuthoritative", NULL) : 0;
    g_fn_tickai = sym_at("_ZN11AWillowMind17TickAuthoritativeEf", NULL, 0);
    cheat_log("AI tick：UFunc %llx 原生 %llx", (unsigned long long)g_uf_tickai, (unsigned long long)g_fn_tickai);
    g_seq_deathtrap = cheat_object_named("Default__Action_DeathTrap");
    for (int32_t i = 0; i < g_gobj_num && !g_gbaic_class; i++) {
        uint64_t q = rd64(g_gobj_data + (uint64_t)i * 8);
        if (q && cheat_name_is(q, "GearboxAIController") && cheat_has_member(q)) g_gbaic_class = q;
    }
    g_fn_setaidef = g_mind_class ? cheat_member(g_mind_class, "SetOverrideAIDef", NULL) : 0;
    g_aidef_psycho = cheat_object_named("AIDef_Psycho");            // 实例就叫 AIDef_Psycho，不是 Default__
    if (!g_aidef_psycho) g_aidef_psycho = cheat_object_named("AIDef_MarauderGrunt");
    cheat_log("spawn 锚点3：GearboxAI %llx SetAIDef %llx AIDef %llx",
              (unsigned long long)g_gbaic_class, (unsigned long long)g_fn_setaidef,
              (unsigned long long)g_aidef_psycho);
    cheat_log("spawn 锚点2：AIController %llx Possess %llx Mind %llx InitSeq %llx 死神序列 %llx",
              (unsigned long long)g_aic_class, (unsigned long long)g_fn_possess,
              (unsigned long long)g_mind_class, (unsigned long long)g_fn_initseq,
              (unsigned long long)g_seq_deathtrap);
    cheat_log("spawn 锚点：GWorld %llx UWorld::SpawnActor %llx",
              (unsigned long long)g_world_sym, (unsigned long long)g_spawn_fn);
    cheat_log("堆：GMalloc %llx FMallocSwitch::Malloc %llx", (unsigned long long)g_gmalloc, (unsigned long long)g_mswitch);
    cheat_log("M2：AIPawn类 %llx Pawn::SetAllegiance %llx Allegiance_Player %llx 取目标 %llx",
              (unsigned long long)g_aipawn_class, (unsigned long long)g_fn_setalleg,
              (unsigned long long)g_alleg_player, (unsigned long long)g_fn_gettarget);
    uint64_t pe = sym_at("ProcessEvent", sn, sizeof sn);
    if (!pe) { pe = g_mbase + 0x601490; snprintf(sn, sizeof sn, "main+0x601490 (fallback)"); }
    g_proc_event = pe;
    cheat_log("就绪：类 %llx 实例 %llx ProcessEvent %s @ %llx，名字表 %llu 项（偏移 %d）",
              (unsigned long long)cls, (unsigned long long)g_cheat_inst, sn,
              (unsigned long long)pe, (unsigned long long)g_names_n, g_cheat_off);
    if (!g_cheat_inst) cheat_log("没有 CheatManager 实例：命令要等进入游戏后才会生效");
    __atomic_store_n(&g_cheat_state, 1, __ATOMIC_RELEASE);
    return 1;
}
// 在出图线程执行一条命令；参数支持单个数字（4 字节）或单个 FString（16 字节）
static void cheat_run(char *line) {
    for (char *s = line; *s; s++) if (*s == '\n' || *s == '\r') *s = 0;
    char full[128]; snprintf(full, sizeof full, "%s", line);   // 重扫后自动重发用（含参数）
    char *sp = line; while (*sp == ' ' || *sp == '\t') sp++;
    char *arg = sp; while (*arg && *arg != ' ' && *arg != '\t') arg++;
    if (*arg) { *arg++ = 0; while (*arg == ' ' || *arg == '\t') arg++; }
    if (!*sp) return;
    cheat_refresh();                                             // 进图后对象数组/实例可能都换了
    if (!cheat_names_ok()) {                                     // 名字表搬家：重扫后自动执行
        snprintf(g_retry, sizeof g_retry, "%s", full);
        __atomic_store_n(&g_retry_on, 1, __ATOMIC_RELEASE);
        __atomic_store_n(&g_rescan, 1, __ATOMIC_RELEASE);
        cheat_log("%s：名字表已搬家，正在重扫，几秒后自动执行", sp);
        return;
    }
    if (!strcasecmp(sp, "ally")) { cheat_ally_one(); return; }
    if (!strcasecmp(sp, "allyall")) { cheat_ally_all(); return; }
    if (!strcasecmp(sp, "weather")) { cheat_weather(); return; }
    if (!strcasecmp(sp, "count")) { cheat_count(); return; }
    if (!strcasecmp(sp, "cycle")) { cheat_cycle_toggle(); return; }
    if (!strcasecmp(sp, "travel")) { cheat_travel(arg); return; }
    if (!strcasecmp(sp, "ctravel")) { cheat_ctravel(arg); return; }
    if (!strcasecmp(sp, "fn")) { cheat_finfo(arg); return; }
    if (!strcasecmp(sp, "heap")) {
        unsigned long long t = 0, f = 0, m = 0;
        int dm_guest_heap_stat(unsigned long long *, unsigned long long *, unsigned long long *);
        if (dm_guest_heap_stat(&t, &f, &m)) cheat_log("heap：总量 %llu MB，余量 %llu MB，最大可分配块 %llu KB", t, f, m);
        else cheat_log("heap：读不到（分配器未初始化）");
        return;
    }
    if (!strcasecmp(sp, "console")) { cheat_console(arg); return; }
    if (!strcasecmp(sp, "say")) { cheat_say(arg); return; }
    if (!strcasecmp(sp, "spawnp")) { cheat_spawnp(arg); return; }
    if (!strcasecmp(sp, "ploc")) { cheat_ploc(); return; }
    if (!strcasecmp(sp, "spawnai")) { cheat_spawnai(arg); return; }
    if (!strcasecmp(sp, "objs")) { cheat_objs(arg); return; }
    if (!strcasecmp(sp, "mindfns")) { cheat_mindfns(); return; }
    if (!strcasecmp(sp, "aiprobe")) { cheat_aiprobe(); return; }
    if (!strcasecmp(sp, "aiinit")) { cheat_aiinit(); return; }
    if (!strcasecmp(sp, "aipatch")) { cheat_aipatch(!arg[0] || !strcasecmp(arg, "1") || !strcasecmp(arg, "on")); return; }
    if (!strcasecmp(sp, "syms")) { cheat_syms(arg); return; }
    if (!strcasecmp(sp, "aidump")) { cheat_aidump(); return; }
    if (!strcasecmp(sp, "aidiff")) { cheat_aidiff(); return; }
    if (!strcasecmp(sp, "aifix")) { cheat_aifix(); return; }
    if (!strcasecmp(sp, "aiprops")) { cheat_aiprops(); return; }
    if (!strcasecmp(sp, "aiprops2")) { cheat_aiprops2(); return; }
    if (!strcasecmp(sp, "aicont")) { cheat_aicont(!strcasecmp(arg, "add")); return; }
    if (!strcasecmp(sp, "dis")) { cheat_dis(arg); return; }
    if (!g_cheat_inst) { cheat_log("%s：没有 CheatManager 实例（先进游戏/读档）", sp); return; }
    uint64_t fn = cheat_find(sp, NULL);
    if (!fn) { cheat_log("%s：没有这个命令", sp); return; }
    uint32_t w = (uint32_t)rd32(fn + 0xc8);           // OperPrecedence(1) NumParms(1) ParmsSize(2)
    int nparms = (int)((w >> 8) & 0xff), psize = (int)((w >> 16) & 0xffff);
    uint8_t par[32] __attribute__((aligned(16))); memset(par, 0, sizeof par);
    if (nparms == 1 && psize == 4) {
        if (!*arg) { cheat_log("%s：需要一个数字参数", sp); return; }
        if (strchr(arg, '.') || strchr(arg, 'e') || strchr(arg, 'E')) { float f = strtof(arg, NULL); memcpy(par, &f, 4); }
        else { int32_t v = (int32_t)strtol(arg, NULL, 0); memcpy(par, &v, 4); }
    } else if (nparms == 1 && psize == 16) {
        if (!*arg) { cheat_log("%s：需要一个文本参数", sp); return; }
        cheat_fstr(par, arg);
    } else if (nparms > 0) {
        cheat_log("%s：需要 %d 个参数（%d 字节），暂不支持", sp, nparms, psize);
        return;
    }
    if (!g_proc_event) { cheat_log("%s：没有 ProcessEvent 地址", sp); return; }
    cheat_log("%s%s%s：执行", sp, *arg ? " " : "", arg);
    cheat_pe((void *)(uintptr_t)g_cheat_inst, (void *)(uintptr_t)fn, nparms ? par : NULL);
}
// 出图钩子每帧调一次（每 16 帧才看文件）；只读文件 + 一次 ProcessEvent
void dm_bl2_cheat_tick(void) {
    if (__atomic_load_n(&g_cheat_state, __ATOMIC_ACQUIRE) != 1 || !g_dir[0]) return;
    // 时间循环：每 5 秒把时间推 3 小时（和帧率无关）
    if (g_cycle_on && g_fn_timeofday) {
        time_t now = time(NULL);
        if (now >= g_cycle_next) {
            g_cycle_next = now + 5;
            cheat_refresh();
            if (g_cheat_inst) {
                static int hour = 6;
                hour = (hour + 3) % 24;
                float v = (float)hour;
                cheat_pe((void *)(uintptr_t)g_cheat_inst, (void *)(uintptr_t)g_fn_timeofday, &v);
            }
        }
    }
    // 重扫完成后自动补执行刚才那条命令
    if (__atomic_load_n(&g_retry_on, __ATOMIC_ACQUIRE) && cheat_names_ok()) {
        char buf[128];
        __atomic_store_n(&g_retry_on, 0, __ATOMIC_RELEASE);
        memcpy(buf, g_retry, sizeof buf);
        cheat_log("重扫完成，自动执行：%s", buf);
        if (g_pe_orig) { snprintf(g_pending, sizeof g_pending, "%s", buf); __atomic_store_n(&g_pending_on, 1, __ATOMIC_RELEASE); }
        else cheat_run(buf);
    }
    static unsigned n;
    if ((n++ & 15) != 0) return;
    char rq[1100]; snprintf(rq, sizeof rq, "%s/cheat.req", g_dir);
    FILE *f = fopen(rq, "r");
    if (!f) return;
    char line[128]; if (!fgets(line, sizeof line, f)) line[0] = 0;
    fclose(f); unlink(rq);   // 先删再执行：命令即使让游戏崩了也不会在下次启动重复
    if (g_pe_orig) {         // hook 在：交给游戏线程执行（生成角色才安全）
        snprintf(g_pending, sizeof g_pending, "%s", line);
        __atomic_store_n(&g_pending_on, 1, __ATOMIC_RELEASE);
    } else cheat_run(line);   // 没装上 hook：退回出图线程直接执行
}
static void *thread_main(void *arg) {
    (void)arg;
    if (!find_dir()) { LOG("BL2 probe: no data dir, resident off"); return NULL; }
    LOG("BL2 probe: resident, %s", g_dir);
    char rq[1100], con[1100];
    snprintf(rq, sizeof rq, "%s/probe.req", g_dir);
    snprintf(con, sizeof con, "%s/cheat.on", g_dir);
    for (int tries = 0; tries < 3; tries++) {   // 启动时模块表可能还没好：最多补装三次
        if (cheat_install_pe()) break;
        sleep(1);
    }
    cheat_log("hook 状态：%d（1=装好，2=找不到 ProcessEvent 符号，3=改代码失败）", g_hook_status);
    for (;;) {
        if (__atomic_load_n(&g_rescan, __ATOMIC_ACQUIRE)) {   // 进图后名字表搬家：重扫一次
            __atomic_store_n(&g_rescan, 0, __ATOMIC_RELEASE);
            cheat_log("重扫名字表…");
            cheat_scan();
        }
        if (__atomic_load_n(&g_cheat_state, __ATOMIC_RELAXED) == 0 && access(con, R_OK) == 0) {
            if (!cheat_scan()) { sleep(5); continue; }
        }
        if (trigger() && access(rq, R_OK) == 0) {
            sleep(1);
            unlink(rq);
            snapshot();
        }
        sleep(1);
    }
    return NULL;
}

// 由 main.c 在 nnMain 前调用；probe.on / cheat.on 出现后常驻
void dm_bl2_probe_start(void) {
    cheat_install_pe();   // 先装游戏线程执行点（此刻还没有客体代码在跑）
    pthread_t th;
    if (!pthread_create(&th, NULL, thread_main, NULL)) pthread_detach(th);
}

#else
void dm_bl2_probe_start(void) {
}

#endif
