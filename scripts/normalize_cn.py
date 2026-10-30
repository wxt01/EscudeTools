#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_cn.py —— 译文清理（在注入前跑）

做三件事：
  1. 去掉 <ruby text='かな'>汉字</ruby> 的注音，只留汉字（中文不需要假名注音）
  2. 把残留的日文假名拟声词规范成中文写法（ぁ→啊、ん→嗯、ッ/ー/゛→去掉）
  3. 报告仍然残留假名的行，供人工复查

用法：
  python normalize_cn.py [--dry]
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import paths

CN_DIR = paths.dirs()["json_cn"]

RUBY = re.compile(r"<ruby[^>]*>(.*?)</ruby>", re.I)
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")

# 假名 → 中文（只保留有意义的，其余删除）
MAP = {
    "ぁ": "啊", "ァ": "啊", "あ": "啊", "ア": "啊",
    "ぃ": "一", "ィ": "一", "い": "一", "イ": "一",
    "ぅ": "呜", "ゥ": "呜", "う": "呜", "ウ": "呜",
    "ぇ": "诶", "ェ": "诶", "え": "诶", "エ": "诶",
    "ぉ": "哦", "ォ": "哦", "お": "哦", "オ": "哦",
    "ん": "嗯", "ン": "嗯",
    "っ": "", "ッ": "", "ー": "", "゛": "", "゜": "", "・": "·",
    "ゃ": "呀", "ャ": "呀", "ゅ": "悠", "ュ": "悠", "ょ": "哟", "ョ": "哟",
    "は": "哈", "ハ": "哈", "ひ": "咿", "ヒ": "咿", "ふ": "呼", "フ": "呼",
    "へ": "嘿", "ヘ": "嘿", "ほ": "呵", "ホ": "呵",
}


def norm(zh):
    if not zh:
        return zh
    zh = RUBY.sub(lambda m: m.group(1), zh)
    zh = re.sub(r"</?ruby[^>]*>", "", zh, flags=re.I)   # 处理残缺/孤立标签
    # 术语/换行占位符如果模型没还原，会在游戏里显示成 ?T0? 之类的乱码，直接去掉
    zh = re.sub(r"[\u3016\u3010]\s*[A-Za-z]?\d*[nN]?\s*[\u3017\u3011]", "", zh)
    out = []
    for ch in zh:
        if ch in MAP:
            out.append(MAP[ch])
        elif KANA.match(ch):
            out.append("")          # 其余假名一律去掉
        else:
            out.append(ch)
    s = "".join(out)
    s = re.sub(r"([啊嗯呜哦诶呀哟哈呼嘿呵咿])\1{4,}", lambda m: m.group(1) * 3, s)  # 压缩过长拖音
    return s


def main():
    global CN_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只统计不写入")
    ap.add_argument("--project", default="", help="项目目录（含 project.json）")
    args = ap.parse_args()
    if args.project:
        CN_DIR = paths.dirs(cli=args.project)["json_cn"]
    print(f"译文目录：{CN_DIR}")

    files = sorted(glob.glob(os.path.join(CN_DIR, "*.jsonl")))
    if not args.dry:
        bak = os.path.join(BASE, "备份", time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(bak, exist_ok=True)
        for p in files:
            shutil.copy2(p, bak)
        print(f"已备份到 {bak}")

    changed = left = 0
    samples = []
    for p in files:
        seen = {}
        order = []
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            k = o.get("index")
            if k not in seen:
                order.append(k)
            # 后者覆盖前者，但空译文不覆盖已有译文
            if k in seen and not o.get("zh") and seen[k].get("zh"):
                continue
            seen[k] = o
        rows = []
        for k in order:
            o = seen[k]
            zh = o.get("zh") or ""
            nz = norm(zh)
            if nz != zh:
                changed += 1
            o["zh"] = nz
            if KANA.search(nz):
                left += 1
                if len(samples) < 15:
                    samples.append((os.path.basename(p), o.get("index"), nz))
            rows.append(o)
        if not args.dry:
            with open(p, "w", encoding="utf-8") as f:
                for o in rows:
                    f.write(json.dumps(o, ensure_ascii=False) + "\n")

    print(f"清理 {changed} 行；仍残留假名 {left} 行")
    for s in samples:
        print("  ", s[0], s[1], s[2][:70])


if __name__ == "__main__":
    main()
