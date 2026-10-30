#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_dicts.py —— 从「已有译文」里统计词库（纯本地，不花钱）

用途：手上有别的译文（商业汉化、旧版机翻、官方中文都行）时，
      拿它跟日文原文对齐，统计出这个作品实际用的译名、短句对应、拟声词写法，
      再把这些规律喂给模型，产出就会向那份译文的手感靠拢。

对齐语料的格式（TSV，制表符分隔，四列，无表头）：
  脚本名 <TAB> 行号 <TAB> 日文 <TAB> 中文

用法：
  python gen_dicts.py --aligned corpus.tsv --out ./dicts
  python gen_dicts.py --aligned a.tsv b.tsv --out ./dicts --max-len 16

输出（都在 --out 目录）：
  phrase_pairs.tsv   短句对应：日文<TAB>中文<TAB>次数   （可直接当 few-shot 或术语种子）
  moan_pairs.tsv     拟声词对应：全假名的日文 → 中文写法
  style_ref.md       风格样本，附笔法统计，可贴进提示词
"""

import argparse
import collections
import os
import re

TAG = re.compile(r"<[^>]{1,16}>")
KANA_ONLY = re.compile(r"^[ぁ-ゖァ-ヶーっッ、。…！？!?～〜\s]+$")
CN_INTERJ = re.compile(r"^[哈啊嗯呀呜哦噢嘿嘻啧唔诶咿哟呼呵～〜…！!？?、。\s]+$")
CJK = re.compile(r"[\u4e00-\u9fa5]")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")


def read_aligned(paths):
    rows = []
    for p in paths:
        if not os.path.isfile(p):
            print(f"  ! 找不到 {p}，跳过")
            continue
        with open(p, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                name, _idx, jp, zh = parts[0], parts[1], parts[2], parts[3]
                if not jp.strip() or not zh.strip():
                    continue
                rows.append((name, jp, zh))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aligned", nargs="+", required=True, help="对齐语料 TSV（可多个）")
    ap.add_argument("--out", default="dicts")
    ap.add_argument("--max-len", type=int, default=14, help="短句对应的最大日文字数")
    ap.add_argument("--min-count", type=int, default=2, help="短语至少出现几次才收录")
    ap.add_argument("--samples", type=int, default=30, help="风格样本条数")
    args = ap.parse_args()

    rows = read_aligned(args.aligned)
    if not rows:
        raise SystemExit("没有读到有效对齐行，检查 TSV 是否是四列制表符分隔")
    print(f"对齐行 {len(rows)}")

    os.makedirs(args.out, exist_ok=True)

    # ---------- 1. 短句对应 ----------
    pairs = collections.Counter()
    for _name, jp, zh in rows:
        j, z = TAG.sub("", jp).strip(), TAG.sub("", zh).strip()
        if not j or not z or len(j) > args.max_len or len(z) > args.max_len:
            continue
        if j == z:
            continue
        pairs[(j, z)] += 1

    with open(os.path.join(args.out, "phrase_pairs.tsv"), "w", encoding="utf-8") as f:
        f.write("# 日文\t中文\t出现次数\n")
        for (j, z), n in pairs.most_common():
            if n >= args.min_count:
                f.write(f"{j}\t{z}\t{n}\n")
    kept = sum(1 for v in pairs.values() if v >= args.min_count)
    print(f"短句对应 {kept} 条")

    # ---------- 2. 拟声词 ----------
    moans = collections.Counter()
    for _name, jp, zh in rows:
        j, z = TAG.sub("", jp).strip(), TAG.sub("", zh).strip()
        if 1 <= len(j) <= 12 and KANA_ONLY.match(j) and CN_INTERJ.match(z):
            moans[(j, z)] += 1
    with open(os.path.join(args.out, "moan_pairs.tsv"), "w", encoding="utf-8") as f:
        f.write("# 日文拟声\t中文写法\t出现次数\n")
        for (j, z), n in moans.most_common():
            f.write(f"{j}\t{z}\t{n}\n")
    print(f"拟声词对应 {len(moans)} 条")

    # ---------- 3. 风格样本 ----------
    pool = []
    for name, jp, zh in rows:
        j, z = TAG.sub("", jp).strip(), TAG.sub("", zh).strip()
        if not (10 <= len(j) <= 60 and 8 <= len(z) <= 60):
            continue
        if KANA.search(z):
            continue
        score = 0
        if "「" in j:
            score += 2
        if "——" in z or "……" in z:
            score += 1
        if CJK.search(z):
            score += 1
        pool.append((score, name, j, z))
    pool.sort(key=lambda x: -x[0])
    picked = pool[:args.samples]

    with open(os.path.join(args.out, "style_ref.md"), "w", encoding="utf-8") as f:
        f.write("# 风格样本（从已有译文统计）\n\n")
        f.write("以下为日文原文与对应译文的成对样本，可作为 few-shot：让模型照着这个断句与语气写。\n")
        f.write("注意：只学笔法与用词规律，不要把别人的译文直接搬进成品。\n\n")
        for i, (_s, name, j, z) in enumerate(picked, 1):
            f.write(f"## {i}\n")
            f.write(f"- 原文：{j}\n")
            f.write(f"- 参考：{z}\n")
            f.write(f"- 出处：{name}\n\n")
        f.write("---\n\n## 笔法统计（自动计算）\n\n")
        if picked:
            ratio = sum(len(TAG.sub("", z)) for _s, _n, _j, z in picked) / max(
                1, sum(len(TAG.sub("", j)) for _s, _n, j, _z in picked))
            f.write(f"- 中文/日文字数比：约 {ratio:.2f}（低于 1 说明译文比原文紧）\n")
        q = sum(1 for _s, _n, j, _z in picked if "「" in j)
        f.write(f"- 含对话引号的比例：{q}/{len(picked)}\n")
        dash = sum(1 for _s, _n, _j, z in picked if "——" in z)
        f.write(f"- 使用破折号「——」的句子：{dash}/{len(picked)}\n")

    print(f"风格样本 {len(picked)} 条 → {args.out}")
    print("\n怎么用：")
    print("  1) phrase_pairs.tsv 里频率高的词条，挑出来放进 glossary.tsv")
    print("  2) moan_pairs.tsv 直接当拟声词对照表")
    print("  3) style_ref.md 贴进提示词的示例区")


if __name__ == "__main__":
    main()
