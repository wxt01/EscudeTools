#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_font.py —— 生成「码表」：中文 → SJIS 占位字符

原理：
  引擎按 Shift-JIS 解码文本。中文里的很多字（以及 ——、· 这类标点）在
  Shift-JIS 里根本不存在，直接写进去会变成 ?。
  办法是：找一个 SJIS 里合法、但正文用不到的「冷门汉字」码位当作占位符，
  注入时把中文换成它；随后 gen_fontpages.py 再把那个格子画成中文字形。
  引擎以为在显示日文，画出来的却是中文。

  同理，若某个作品确认使用系统字体（而不是位图字库），这份码表也能配合
  映射 TTF 使用（--ttf 可另存一份），但本流水线默认走位图路线。

用法：
  python gen_font.py --text <项目>/3_json_cn --out <项目>/5_build/cmap --exclude-text <项目>/2_json_jp

产物：
  cmap.json           {"中": "凜", ...} 注入前替换用（本流水线唯一必需产物）
  report.txt          覆盖率与冲突报告
  MSGothic_cnjp.ttf   仅在加 --ttf 时生成，供系统字体路线使用
"""

import argparse
import json
import os
import sys

from fontTools.ttLib import TTFont

# SJIS 双字节合法范围
LEADS = list(range(0x81, 0xA0)) + list(range(0xE0, 0xF0))
TRAILS = list(range(0x40, 0x7F)) + list(range(0x80, 0xFD))

# 这些码位对应的字符太常用，正文里可能真的会用到，尽量不要占用
COMMON = set("、。，．・：；？！゛゜´｀¨＾￣＿ヽヾゝゞ〃仝々〆〇ー―‐／＼～∥｜…‥‘’“”（）〔〕［］｛｝〈〉《》「」『』【】＋－±×÷＝≠＜＞≦≧∞∴♂♀°′″℃￥＄￠￡％＃＆＊＠§☆★○●◎◇")


def collect_chars(path, exts=(".json", ".jsonl")):
    """从导出的文本里收集需要的中文字符"""
    need = set()
    if os.path.isfile(path):
        files = [path]
    else:
        files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(exts)]
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            if fp.endswith(".jsonl"):
                for line in f:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    for v in (o.get("zh"), o.get("jp")):
                        if isinstance(v, str):
                            need.update(v)
            else:
                try:
                    data = json.load(f)
                except Exception:
                    continue
                for it in data if isinstance(data, list) else []:
                    for v in (it.get("zh"), it.get("jp")):
                        if isinstance(v, str):
                            need.update(v)
    # 只保留非 ASCII（ASCII 全部原样保留）
    return {c for c in need if ord(c) > 0x7F}


def sjis_page(lead, trail):
    c0 = lead - (0x40 if lead >= 0xE0 else 0)
    c1 = trail - (1 if trail >= 0x80 else 0)
    page = (c0 - 0x80) * 2
    if c1 < 0x9E:
        page -= 1
    return page


def build_slot_pool(exclude=None, max_page=83):
    """枚举 SJIS 空闲码位，返回 [(byte_pair, decoded_char)]，优先冷门汉字

    exclude: 正文里真实出现过的字符集合。这些字绝不能当占位格——否则一旦
    有没翻到的日文残留，显示的会是别人的字形（我们覆盖了那个格子）。
    """
    exclude = exclude or set()
    pool = []
    for lead in LEADS:
        for trail in TRAILS:
            b = bytes([lead, trail])
            try:
                ch = b.decode("cp932")
            except UnicodeDecodeError:
                continue
            if len(ch) != 1:
                continue
            o = ord(ch)
            # 只要汉字区（含少见汉字），跳过假名/符号/常用符号
            if not (0x4E00 <= o <= 0x9FFF):
                continue
            if ch in COMMON or ch in exclude:
                continue
            # 只用游戏真正会渲染的页（正文用到的最大页），高页引擎不画
            if max_page and sjis_page(lead, trail) > max_page:
                continue
            pool.append((b, ch))
    # 冷门优先：按 Unicode 从大到小（越靠后的汉字越生僻）
    pool.sort(key=lambda x: -ord(x[1]))
    return pool


def load_standin_table(path):
    """加载替身字优选表：目标字(不在SJIS) -> SJIS 合法替身字

    表中替身字与目标字语义/字形相关（多为繁体或日文写法），按表选占位字
    让码表可追溯、替换出错时兜底字形也可读。
    """
    if not path or not os.path.isfile(path):
        return {}
    table = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2 and len(parts[0]) == 1 and len(parts[1]) == 1:
                table.setdefault(parts[0], parts[1])
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="json_cn 目录或文件")
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--base", default=r"C:\Windows\Fonts\simhei.ttf")
    ap.add_argument("--family", default="ＭＳ ゴシック")
    ap.add_argument("--exclude-text", default="", help="日文原文目录：其中出现过的字不作为占位格")
    ap.add_argument("--max-page", type=int, default=83, help="占位格最高页号（引擎只渲染正文用到的页）")
    ap.add_argument("--ttf", action="store_true", help="额外导出映射 TTF（系统字体路线才需要）")
    ap.add_argument("--standin-table", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "standin.tsv"),
                    help="替身字优选表（默认自动加载脚本同目录 standin.tsv，可传空字符串禁用）")
    args = ap.parse_args()

    need = collect_chars(args.text)
    jp_chars = collect_chars(args.exclude_text) if args.exclude_text else set()
    def _encodable(ch):
        try:
            ch.encode("cp932")
            return True
        except UnicodeEncodeError:
            return False

    cjk = {c for c in need if 0x3400 <= ord(c) <= 0x9FFF or 0xF900 <= ord(c) <= 0xFAFF}
    # 标点里 SJIS 编码不了的那些（——、·、♪ 等）也必须走映射，
    # 否则落盘时会被替换成 ?，游戏里就是一片问号
    cjk |= {c for c in need if ord(c) > 0x7F and not _encodable(c)}
    cjk = sorted(cjk)
    other = sorted(need - set(cjk))
    print(f"需要字符 {len(need)} 个（汉字 {len(cjk)}，其他 {len(other)}）")

    font = TTFont(args.base, fontNumber=0)
    cmap_table = font.getBestCmap()
    have = set(cmap_table.keys())
    missing = [c for c in need if ord(c) not in have]
    if missing:
        print(f"! 基础字体缺 {len(missing)} 个字形，将跳过：{''.join(missing[:20])}")

    pool = build_slot_pool(jp_chars | set(need), args.max_page)
    print(f"日文正文用字 {len(jp_chars)} 个已排除；可用码位 {len(pool)} 个（页号<= {args.max_page}）")

    # 替身字优选表：能查到表的字直接用表内替身（语义/字形相关、经过验证），
    # 查不到的回落到冷门码位池
    standin = load_standin_table(args.standin_table)
    if standin:
        print(f"替身字优选表：{len(standin)} 条")
    slot_by_ch = {ch: (b, ch) for b, ch in pool}

    # 建立映射：中文字符 → 用于占位的日文汉字
    mapping = {}
    used = set()
    used_pref = 0
    for c in cjk:
        if ord(c) not in have:
            continue
        slot_ch = None
        pref = standin.get(c)
        if pref and pref != c and pref not in used and pref in slot_by_ch:
            slot_ch = pref
            used_pref += 1
        else:
            for b, ch in pool:
                if ch in used or ch == c:
                    continue
                slot_ch = ch
                break
        if slot_ch:
            used.add(slot_ch)
            mapping[c] = slot_ch
    if standin:
        print(f"按优选表映射 {used_pref} 个，冷门池兜底 {len(mapping) - used_pref} 个")

    if len(mapping) < len(cjk):
        print(f"! 码位不足，{len(cjk) - len(mapping)} 个字符未能映射")

    # 重写 cmap：占位字符 → 中文字形
    for table in font["cmap"].tables:
        if table.isUnicode():
            for c, slot_ch in mapping.items():
                table.cmap[ord(slot_ch)] = cmap_table[ord(c)]

    # 改家族名，让 configure.exe 的字体列表里能看到（并尽量排在最后）
    for rec in font["name"].names:
        try:
            s = rec.toUnicode()
        except Exception:
            continue
        if rec.nameID in (1, 4, 16):
            rec.string = args.family
        elif rec.nameID == 6:
            rec.string = "MSGothicCNJP"
        elif rec.nameID == 3:
            rec.string = "MSGothicCNJP-Regular"

    os.makedirs(args.out, exist_ok=True)
    font_path = os.path.join(args.out, "MSGothic_cnjp.ttf")
    if args.ttf:
        font.save(font_path)

    with open(os.path.join(args.out, "cmap.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=0)

    with open(os.path.join(args.out, "report.txt"), "w", encoding="utf-8") as f:
        f.write(f"需要字符 {len(need)}，汉字 {len(cjk)}，已映射 {len(mapping)}\n")
        f.write(f"缺字形 {len(missing)}：{''.join(missing)}\n")
        f.write("映射样例：\n")
        for c, s in list(mapping.items())[:50]:
            f.write(f"  {c} -> {s} (U+{ord(s):04X})\n")

    if args.ttf:
        print(f"映射字体已生成：{font_path}")
    print(f"码表已生成：{os.path.join(args.out, 'cmap.json')}")


if __name__ == "__main__":
    main()
