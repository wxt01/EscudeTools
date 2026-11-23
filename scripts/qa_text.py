#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa_text.py —— 打包前文本质检（汉化补丁出厂检查）

目标：**不亲自通玩，也能在制作阶段把翻译问题揪出来**。
分两档：拦截项（不为 0 就不许出包）、警告项（人工判断）。

  一、逐行硬伤（拦截）
     空译 / 译文是乱码 / 残留假名 / 半角片假名 / 残留占位符 / 残留 ruby 标签 /
     与原文相同(未译) / 繁体日文写法 / 首尾空白与换行符

  二、字库风险（拦截）
     占位冲突（两字共用一格）/ 占位越界（> font.max_page 或格>93）/ 画了但没墨迹

  三、一致性（拦截 + 警告）
     项目自定义名词异体表（拦截）/ 术语命中率 / 专名在译文中缺失 /
     同一角色自称混用 / 同一角色「你/您」混用 / 同一日文原文多种译法

  四、语气与可读性（警告）
     感叹问号强度下降 / 长段无标点 / 英文单词残留 / 句末标点缺失 /
     过短(疑似漏译) / 过长(疑似冗余) / 非拟声复读 / 引号括号不配对 / 数字丢失

  五、人工抽检
     --sample N 导出随机抽检表（tsv），按「风险分」排序，方便快速过目

用法：
  python qa_text.py [--project <项目>] [--strict] [--sizes 12,24]
                    [--max-samples 500] [--sample 60] [--sample-out 抽检表.tsv]

退出码：0 通过；2 有拦截项；3 只有警告且加了 --strict
"""

import argparse
import collections
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths

# ---------- 判定用的字符集/正则 ----------

TAG_RE = re.compile(r"<[^>]{1,60}>")
KANA_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
HANKAKU_RE = re.compile(r"[\uff61-\uff9f]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
MOJIBAKE_RE = re.compile(r"[縺繧繝譁隲]|[\uff61-\uff9f]{2,}")
PLACEHOLDER_RE = re.compile(r"[\u3010\u3016]\s*[A-Za-z]?\d{1,3}[nN]?\s*[\u3011\u3017]")
JP_ENDING_RE = re.compile(r"(です|ます|ました|ません|ください|でしょう|だな|だよ|かよ|ねえ|よな|ている|でした)")
SENT_END = "。！？…！?♪」』）】”—～’"
ASCII_WORD_RE = re.compile(r"[A-Za-z]{3,}")
ASCII_OK = {"ON", "OFF", "CONFIG", "SAVE", "LOAD", "BGM", "BGV", "SE", "CV",
            "HP", "MP", "END", "NG", "OK", "ADV", "SLG", "OP", "ED", "CG", "QSAVE",
            "QLOAD", "BACKLOG", "AUTO", "SKIP", "FAST", "NORMAL", "KEEP", "CANCEL",
            # 引擎脚本/技术标识（手册类文本里属正常）
            "RGB", "RGBA", "ALPHA", "SKEW", "RND", "MAX", "SPD", "BLUR", "COL", "LSF",
            "MOT", "CLR", "FLT", "PTCL", "FILL", "MUL", "OVL", "XOR", "MONO", "BOX",
            "CX", "CY", "IME", "GPU", "CPU", "URL", "HTTP", "JSON", "SQL", "README"}
# 同一角色不该混用的自称
SELF_FORMS = ["我", "俺", "咱", "咱们", "人家", "本大爷", "老子", "妾", "吾", "余", "小女子", "在下"]
POLITE = ["您", "你"]

# 日语新字体 / 繁体：出现在简体译文里就是漏改（可按需扩充）
TRAD_CHARS = set(
    "姫華裡態讓來卻這熱邊個們時會說當發醫體點實彈藥處聽見給麼樣對從無為與殺傷殘騎墮鬱"
    "門儀劔劍戰齡歲廣應惡據舉拝抜択拡絵図団囲気鉄銀銃龍竜稲髪圧変弁隣獣沢様達戦屆屬歸"
    "優傳僅價億儀儘償兒黨內兩冊寫準劃剛創劇勸辦務動勵勞勢勳匯區協單賣廬廳歷厲壓參雙發變"
)
PAIRS = (("「", "」"), ("『", "』"), ("“", "”"), ("（", "）"), ("【", "】"))


def engine_page_cell(placeholder):
    """占位字 → (页号, 格号)。口径 = JIS 区/点（misc/text.c: put_char）。"""
    try:
        b = placeholder.encode("cp932")
    except UnicodeEncodeError:
        return None
    if len(b) != 2:
        return None
    lead, trail = b
    if lead <= 0x9F:
        ku = (lead - 0x81) * 2 + 0x21
    else:
        ku = (lead - 0xC1) * 2 + 0x21
    if trail >= 0x9F:
        ten = trail - 0x7E
        ku += 1
    else:
        ten = trail - (0x1F if trail < 0x7F else 0x20)
    return ku - 0x21, ten - 0x21


def load_rows(cn_dir):
    rows = []
    for fn in sorted(f for f in os.listdir(cn_dir) if f.endswith(".jsonl")):
        with open(os.path.join(cn_dir, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                rows.append({
                    "file": fn,
                    "index": o.get("index"),
                    "char": o.get("char"),
                    "jp": o.get("jp") or "",
                    "zh": o.get("zh") or "",
                    "note": o.get("src_note") or "",
                })
    return rows


def load_tsv(path):
    out = []
    if not path or not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            p = line.split("\t")
            if len(p) >= 2 and p[0] and p[1]:
                out.append(tuple(p[:3]))
    return out


# ---------- 一、逐行硬伤 ----------

def check_lines(rows):
    blocks, warns = [], []
    for r in rows:
        fn, idx, jp, zh = r["file"], r["index"], r["jp"], r["zh"]
        jb, zb = TAG_RE.sub("", jp), TAG_RE.sub("", zh)

        if not zh.strip():
            if CJK_RE.search(jb) or KANA_RE.search(jb):
                blocks.append(("空译", fn, idx, jp[:40]))
            continue

        if MOJIBAKE_RE.search(zh) and r["note"] != "mojibake_rewritten":
            blocks.append(("译文是乱码", fn, idx, zh[:40]))
        if KANA_RE.search(zb):
            blocks.append(("残留假名", fn, idx, zh[:40]))
        if HANKAKU_RE.search(zh):
            blocks.append(("半角片假名", fn, idx, zh[:40]))
        if PLACEHOLDER_RE.search(zh):
            blocks.append(("残留占位符", fn, idx, zh[:40]))
        if re.search(r"</?ruby", zh, re.I):
            blocks.append(("残留ruby标签", fn, idx, zh[:40]))
        if zh != zh.strip():
            blocks.append(("首尾空白", fn, idx, repr(zh[:20])))
        if "\n" in zh:
            blocks.append(("含裸换行符", fn, idx, repr(zh[:20])))
        if jb.strip() == zb.strip() and len(CJK_RE.findall(zb)) > 3:
            # 整行就是个专名（去 ruby 后没假名、汉字也不多）时，中日写法相同属正常
            if KANA_RE.search(jb) or len(CJK_RE.findall(zb)) >= 12:
                blocks.append(("与原文相同(未译)", fn, idx, jp[:44]))

        bad = sorted({c for c in zb if c in TRAD_CHARS})
        if bad:
            blocks.append(("繁体/日文写法", fn, idx, "".join(bad) + "｜" + zh[:36]))

        jl, zl = len(jb), len(zb)
        if r["note"] == "mojibake_rewritten":
            jl = 0          # 原文是乱码，长度不可比
        if jl >= 8 and zl < jl * 0.35:
            warns.append(("疑似漏译(过短)", fn, idx, f"{jl}→{zl}｜{jp[:36]}", 3))
        if jl >= 6 and zl > jl * 2.2 and zl > 40:
            warns.append(("疑似冗余(过长)", fn, idx, f"{jl}→{zl}｜{jp[:36]}", 2))

        for a, b in PAIRS:
            if zh.count(a) != zh.count(b):
                warns.append(("引号/括号不配对", fn, idx, zh[:40], 1))
                break

        jn, zn = re.findall(r"\d+", jb), re.findall(r"\d+", zb)
        if jn and len(jn) > len(zn):
            warns.append(("数字疑似丢失", fn, idx, zh[:40], 1))

        m = re.search(r"(.{2,6})\1{2,}", zb)
        if m and not set(m.group(1)) <= set("啊嗯呜唔哈呀哦诶噢呃呼咿嘿嚕、。——…"):
            warns.append(("疑似复读", fn, idx, zh[:40], 1))

        # 感叹/问号强度
        j_em = jb.count("！") + jb.count("？") + jb.count("!")
        z_em = zb.count("！") + zb.count("？") + zb.count("!")
        if j_em >= 2 and z_em == 0 and zb.rstrip()[-1:] not in "—…":
            warns.append(("语气强度下降(感叹/问号全丢)", fn, idx, f"{j_em}→0｜{zh[:34]}", 2))

        # 长段无标点（一行里连续 40+ 字没有断句符号）
        for seg in ([] if ("@" in zb or "=" in zb) else zb.split("<r>")):
            for run in re.split(r"[。，！？…～；：”’）】—　、]", seg):
                if len(run) >= 40:
                    warns.append(("长段无标点", fn, idx, run[:44], 2))
                    break

        # 英文单词残留：夹在中文句子中间的多半是模型把词漏译成英文 → 拦截；
        # 其它位置（专名、代码、括号内）只警告。
        words, inline = [], []
        for m in ASCII_WORD_RE.finditer(zb):
            w = m.group(0)
            if w.upper() in ASCII_OK:
                continue
            words.append(w)
            i = m.start() - 1
            while i >= 0 and zb[i] in " \u3000":
                i -= 1
            j = m.end()
            while j < len(zb) and zb[j] in " \u3000":
                j += 1
            pre = zb[i] if i >= 0 else ""
            post = zb[j] if j < len(zb) else ""
            if pre and post and CJK_RE.match(pre) and CJK_RE.match(post):
                inline.append(w)
        if inline:
            blocks.append(("英文夹在句中", fn, idx, ",".join(inline[:4]) + "｜" + zh[:30]))
        elif words:
            warns.append(("英文单词残留", fn, idx, ",".join(words[:4]) + "｜" + zh[:30], 2))

        # 句末标点缺失
        if jb.rstrip() and jb.rstrip()[-1] in SENT_END and zb.rstrip() and zb.rstrip()[-1] not in SENT_END:
            warns.append(("句末标点缺失", fn, idx, zh[-24:], 1))
    return blocks, warns


# ---------- 三、一致性 ----------

def check_consistency(rows, glossary, variant_pairs):
    blocks, warns = [], []

    # 术语命中率
    for jp_t, zh_t, _ in glossary:
        hit = [r for r in rows if jp_t in r["jp"]]
        if len(hit) < 3:
            continue
        ok = sum(1 for r in hit if zh_t in r["zh"])
        if ok / len(hit) < 0.85:
            warns.append(("术语未按表统一", "-", f"{jp_t}→{zh_t}", f"{ok}/{len(hit)} ({ok/len(hit):.0%})", 3))

    # 专名在译文中缺失（只查长度≥3 的词，且原文出现即要求译名出现）
    miss = collections.Counter()
    for jp_t, zh_t, _ in glossary:
        if len(jp_t) < 3:
            continue
        for r in rows:
            if jp_t in r["jp"] and zh_t not in r["zh"] and r["zh"]:
                miss[(jp_t, zh_t)] += 1
    for (jp_t, zh_t), n in miss.most_common(20):
        if n >= 2:
            warns.append(("专名缺失(原文有译名无)", "-", f"{jp_t}→{zh_t}", f"{n} 行", min(3, 1 + n // 10)))

    # 同一角色自称 / 你您 混用
    by_char = collections.defaultdict(list)
    for r in rows:
        # 只统计“像对白”的行：旁白也会带角色 id，混进来必然误报
        z = (r["zh"] or "").lstrip()
        if r["char"] is not None and z[:1] in "“「‘":
            by_char[str(r["char"])].append(r["zh"])
    for cid, zhs in by_char.items():
        if len(zhs) < 20:
            continue
        texts = "\n".join(zhs)
        forms = {f: texts.count(f) for f in SELF_FORMS}
        forms = {k: v for k, v in forms.items() if v >= 3}
        if len(forms) >= 2:
            warns.append(("角色自称混用", f"char={cid}", "", str(forms), 2))
        p = {k: texts.count(k) for k in POLITE}
        if p["您"] >= 10 and p["你"] >= 10:
            warns.append(("你/您混用", f"char={cid}", "", str(p), 1))

    # 同一日文 → 多种译法（长句才查，避免短句正常差异）
    grp = collections.defaultdict(set)
    for r in rows:
        if len(TAG_RE.sub("", r["jp"])) >= 12 and r["zh"]:
            grp[r["jp"]].add(r["zh"])
    multi = [(jp, zs) for jp, zs in grp.items() if len(zs) >= 2]
    for jp, zs in multi[:15]:
        warns.append(("同一原文多种译法", "-", jp[:28], f"{len(zs)} 种：{list(zs)[0][:20]}…", 1))

    # 项目自定义异体表（拦截）
    for std, variant, _ in variant_pairs:
        n = sum(1 for r in rows if variant in r["zh"])
        if n:
            blocks.append(("名词异体写法", "-", f"{std}/{variant}", f"{n} 处"))
    return blocks, warns


# ---------- 三·补、人名错位 ----------

RUBY_TAG = re.compile(r"<ruby[^>]*>|</ruby>", re.I)


def strip_ruby(s):
    """去掉 ruby 标签本体，但保留其外层汉字（<ruby text='エル'>死体</ruby> → 死体）"""
    return RUBY_TAG.sub("", s)


def build_name_pairs(glossary, names_map):
    """名字对照只认项目里的 3_译文\词典\names_map.tsv（日文<TAB>中文）。

    不从术语表自动推导：术语表里混着 攻撃/冷静/気力 这类词，当成名字会大面积误报。
    没提供这张表就跳过人名错位检查，并在控制台提示。
    """
    pairs = []
    for row in names_map:
        a, b = row[0], row[1]
        if len(b) >= 2 and a:
            pairs.append((a, b))
    return pairs


def check_names(rows, pairs):
    """原文出现 A 的名字、译文却没写 A、反而写了另一个 B → 人名错位（真错误）"""
    blocks = []
    if len(pairs) < 2:
        return blocks
    for r in rows:
        jp, zh = strip_ruby(r["jp"]), r["zh"]
        if not jp or not zh:
            continue
        for jp_a, zh_a in pairs:
            if jp_a not in jp or zh_a in zh:
                continue
            # 只有「原文根本没出现的名字」被写进来才算错位；
            # 同一行同时提到多个人（原文也有）属正常。
            wrong = [zh_b for jp_b, zh_b in pairs
                     if jp_b != jp_a and zh_b != zh_a and len(zh_b) >= 2
                     and zh_b in zh and jp_b not in jp]
            if wrong:
                blocks.append(("人名错位", r["file"], r["index"],
                               f"原文有「{jp_a}」应为「{zh_a}」，译文却是「{wrong[0]}」｜{zh[:30]}"))
                break
    return blocks


# ---------- 三·补2、用字覆盖 ----------

def check_coverage(rows, cmap):
    """译文里的每个非 ASCII 字符，要么在码表里有占位字，要么能被 cp932 直接编码。
    两者都不满足 → 注入时变 ?，游戏里就是问号。"""
    blocks = []
    miss = collections.Counter()
    first = {}
    for r in rows:
        for ch in TAG_RE.sub("", r["zh"]):
            if ord(ch) <= 0x7F or ch in cmap:
                continue
            try:
                ch.encode("cp932")
                continue
            except UnicodeEncodeError:
                pass
            miss[ch] += 1
            first.setdefault(ch, (r["file"], r["index"]))
    for ch, n in miss.most_common(30):
        fn_, idx = first[ch]
        blocks.append(("用字无占位(会显示问号)", fn_, idx, f"「{ch}」U+{ord(ch):04X} 共 {n} 处"))
    return blocks


# ---------- 二、字库 ----------

def check_font(cmap, max_page, sizes, pages_dir):
    blocks, warns = [], []
    dup = collections.defaultdict(list)
    for zh, ph in cmap.items():
        dup[ph].append(zh)
    for ph, zhs in dup.items():
        if len(zhs) > 1:
            blocks.append(("占位冲突(同格多字)", "-", ph, "".join(zhs)))

    for zh, ph in cmap.items():
        pos = engine_page_cell(ph)
        if not pos:
            blocks.append(("占位无法定位", "-", zh, ph))
            continue
        page, cell = pos
        if page > max_page or cell > 93:
            blocks.append(("占位越界", "-", zh, f"页{page} 格{cell}（上限 {max_page}）"))

    try:
        from PIL import Image
    except ImportError:
        warns.append(("字库墨迹未检查", "-", "-", "未安装 Pillow", 1))
        return blocks, warns

    cache, blank = {}, []
    for zh, ph in cmap.items():
        pos = engine_page_cell(ph)
        if not pos:
            continue
        page, cell = pos
        for size in sizes:
            key = (size, page)
            if key not in cache:
                fp = os.path.join(pages_dir, size, "%02d.png" % page) if pages_dir else ""
                cache[key] = Image.open(fp).convert("L") if fp and os.path.isfile(fp) else None
            img = cache[key]
            if img is None:
                continue
            cs = img.width // 16
            box = ((cell % 16) * cs, (cell // 16) * cs,
                   (cell % 16) * cs + cs, (cell // 16) * cs + cs)
            if img.crop(box).getextrema()[1] < 8:
                blank.append((zh, size, page, cell))
                break
    for zh, size, page, cell in blank[:50]:
        blocks.append(("字库无墨迹", "-", zh, f"{size}px 页{page} 格{cell}"))
    if len(blank) > 50:
        blocks.append(("字库无墨迹", "-", "…", f"另有 {len(blank)-50} 字"))
    return blocks, warns


# ---------- 抽检表 ----------

def export_sample(rows, warns, n, out_path, seed=20261121):
    """把「风险分」最高的行 + 随机行混在一起导出，方便人工过目"""
    score = collections.Counter()
    for it in warns:
        fn, idx = it[1], it[2]
        if fn not in ("-", "") and isinstance(idx, (int, str)):
            score[(fn, idx)] += 1
    pool = [(r["file"], r["index"]) for r in rows]
    ranked = sorted(pool, key=lambda k: -score[k])
    pick = ranked[:n // 2]
    rest = [k for k in pool if k not in set(pick)]
    random.seed(seed)
    pick += random.sample(rest, min(n - len(pick), len(rest)))
    idx = {(r["file"], r["index"]): r for r in rows}
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("文件\t行号\t日文\t译文\t风险分\n")
        for k in pick:
            r = idx.get(k)
            if not r:
                continue
            jp = (r["jp"] or "").replace("\t", " ").replace("\n", " ")
            zh = (r["zh"] or "").replace("\t", " ").replace("\n", " ")
            f.write(f"{k[0]}\t{k[1]}\t{jp}\t{zh}\t{score[k]}\n")
    return len(pick)


# ---------- 六·专名多译 / 生僻字形 ----------

TERM_BR = re.compile(r"『([^』]{1,16})』|《([^》]{1,16})》")
RARE_OK = set("咲呣啰嗞嗐嗶窸窣欸瘆唷呐喏诶袴屌")          # 人名用字与拟声词
RARE_OK_TERMS = ("艶鬼", "廻鬼", "瞭望")                 # 项目内明确保留的日式写法


def extract_terms(s):
    out = []
    for m in TERM_BR.finditer(s or ""):
        out.append((m.group(1) or m.group(2)).strip())
    return out


def check_term_variants(rows):
    """同一日文专名译成多个写法 → 3 种以上拦截、2 种警告"""
    blocks, warns = [], []
    seen = collections.defaultdict(set)
    count = collections.Counter()
    for r in rows:
        jts, zts = extract_terms(r.get("jp")), extract_terms(r.get("zh"))
        # 只在「一行里原文一个括号词、译文也一个」时才配对，避免错位误报
        if len(jts) != 1 or len(zts) != 1:
            continue
        j, z = jts[0], zts[0]
        if not j or not z or len(j) > 10:
            continue
        count[j] += 1
        seen[j].add(z)
    for j, zs in sorted(seen.items(), key=lambda kv: -count[kv[0]]):
        if count[j] >= 3 and len(zs) >= 3:
            blocks.append(("专名多译", "-", j[:22], "／".join(sorted(zs))[:60]))
        elif count[j] >= 3 and len(zs) == 2:
            warns.append(("专名两种写法", "-", j[:22], "／".join(sorted(zs))[:60], 2))
    return blocks, warns


def gb2312_ok(ch):
    try:
        ch.encode("gb2312")
        return True
    except UnicodeEncodeError:
        return False


def check_rare_chars(rows, allow_chars=(), allow_terms=()):
    """非 GB2312 汉字：小字号下容易糊，或本身就是日文/繁体写法"""
    warns = []
    cnt = collections.Counter()
    first = {}
    allow = set(allow_chars) | RARE_OK
    for r in rows:
        if "z_script_sample" in str(r.get("file", "")):
            continue
        z = r.get("zh") or ""
        for t in set(allow_terms) | set(RARE_OK_TERMS):
            z = z.replace(t, "")
        for ch in z:
            if "\u4e00" <= ch <= "\u9fff" and not gb2312_ok(ch) and ch not in allow:
                cnt[ch] += 1
                first.setdefault(ch, f"{r.get('file','')}#{r.get('index','')}")
    for ch, n in cnt.most_common(30):
        warns.append(("生僻/日文字形残留", first[ch], ch, f"{n} 处", 1))
    return warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--sizes", default="12,16,24,32", help="字库墨迹抽查的字号")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--max-samples", type=int, default=500)
    ap.add_argument("--sample", type=int, default=0, help="额外导出 N 行人工抽检表")
    ap.add_argument("--sample-out", default="")
    args = ap.parse_args()

    d = paths.dirs(cli=args.project or None)
    root, cfg = d["root"], d["cfg"]
    if not os.path.isdir(d["json_cn"]):
        sys.exit(f"没有译文目录：{d['json_cn']}")

    rows = load_rows(d["json_cn"])
    glossary = load_tsv(os.path.join(d["json_cn"], "词典", cfg.get("glossary", "glossary.tsv")))
    variants = load_tsv(os.path.join(d["json_cn"], "词典", "names_variants.tsv"))

    cmap_path = os.path.join(d["build"], "cmap", "cmap.json")
    cmap = {}
    if os.path.isfile(cmap_path):
        with open(cmap_path, encoding="utf-8") as f:
            cmap = json.load(f)
    max_page = int((cfg.get("font") or {}).get("max_page", 83))

    print(f"项目：{root}")
    print(f"译文 {len(rows)} 行｜术语 {len(glossary)} 条｜码表 {len(cmap)} 字｜页号上限 {max_page}")

    names_map = load_tsv(os.path.join(d["json_cn"], "词典", "names_map.tsv"))
    name_pairs = build_name_pairs(glossary, names_map)
    if not name_pairs:
        print("提示：没有 3_译文\\词典\\names_map.tsv，跳过「人名错位」检查"
              "（格式：日文名<TAB>中文名）")

    blocks, warns = check_lines(rows)
    blocks += check_names(rows, name_pairs)
    b2, w2 = check_consistency(rows, glossary, variants)
    blocks += b2
    warns += w2
    b4, w4 = check_term_variants(rows)
    blocks += b4
    warns += w4
    name_chars = set()
    try:
        for v in json.load(open(os.path.join(d["root"], "names_zh.json"), encoding="utf-8")).values():
            if isinstance(v, str):
                name_chars |= set(v)
    except Exception:
        pass
    warns += check_rare_chars(rows, allow_chars=name_chars)
    if cmap:
        dz_path = os.path.join(d["root"], "data_zh.json")
        if os.path.isfile(dz_path):
            extra = [{"file": "data_zh.json", "index": k, "jp": "", "zh": v, "note": ""}
                     for k, v in json.load(open(dz_path, encoding="utf-8")).items()
                     if isinstance(v, str)]
            blocks += check_coverage(extra, cmap)
        blocks += check_coverage(rows, cmap)
        b3, w3 = check_font(cmap, max_page, [s.strip() for s in args.sizes.split(",") if s.strip()],
                            os.path.join(d["build"], "pages"))
        blocks += b3
        warns += w3
    else:
        print("提示：没有 5_构建\\cmap\\cmap.json，跳过字库检查（先跑一次全量构建再查）")

    cnt_b = collections.Counter(c for c, *_ in blocks)
    cnt_w = collections.Counter(c for c, *_ in warns)
    print("\n拦截项：", dict(cnt_b) if cnt_b else "无")
    print("警告项：", dict(cnt_w) if cnt_w else "无")

    # 按文件统计问题密度，指导人工复看
    per_file = collections.Counter()
    for cat, fn, idx, *_ in blocks + warns:
        if fn not in ("-",):
            per_file[fn] += 1
    if per_file:
        print("\n问题最集中的文件（前 10）：")
        for fn, n in per_file.most_common(10):
            print(f"   {fn}: {n}")

    rep = args.report or os.path.join(root, "审校报告.txt")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("文本质检报告\n" + "=" * 60 + "\n")
        f.write(f"项目：{root}\n行数：{len(rows)}｜术语 {len(glossary)}｜码表 {len(cmap)}\n\n")
        f.write("【拦截项】" + (f"共 {len(blocks)} 条\n" if blocks else "无\n"))
        for it in blocks[:args.max_samples]:
            f.write("  " + " | ".join(str(x) for x in it) + "\n")
        if len(blocks) > args.max_samples:
            f.write(f"  …（另有 {len(blocks)-args.max_samples} 条）\n")
        f.write("\n【警告项】" + (f"共 {len(warns)} 条\n" if warns else "无\n"))
        for it in warns[:args.max_samples]:
            f.write("  " + " | ".join(str(x) for x in it) + "\n")
        if len(warns) > args.max_samples:
            f.write(f"  …（另有 {len(warns)-args.max_samples} 条）\n")
        if per_file:
            f.write("\n【问题最集中的文件】\n")
            for fn, n in per_file.most_common(30):
                f.write(f"  {fn}\t{n}\n")
    print(f"报告：{rep}")

    if args.sample:
        sp = args.sample_out or os.path.join(root, "人工抽检表.tsv")
        n = export_sample(rows, warns, args.sample, sp)
        print(f"抽检表：{sp}（{n} 行，风险高的在前，后接随机）")

    if blocks:
        print("\n结论：不通过（拦截项必须清零才能出包）")
        return 2
    if warns and args.strict:
        print("\n结论：--strict 下警告视为失败")
        return 3
    print("\n结论：通过" + ("（有警告，可人工判断）" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
