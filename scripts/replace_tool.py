#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
替换工具 —— 双击「替换工具.bat」运行

流程：
  1. 输入要查找的词（比如：那里）
  2. 屏幕显示找到多少处、前几条例句
  3. 输入你想换成什么（比如：那处）
  4. 确认一下，就替换完了
  5. 可以接着换下一个词，输入空行退出

每次运行都会自动备份，改坏了可以还原。
"""

import json
import os
import shutil
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import paths

_D = paths.dirs(cli=(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None))
CN_DIR = _D["json_cn"]
BK_ROOT = os.path.join(_D["root"], "备份")
LOG = os.path.join(_D["root"], "替换记录.txt")


def load_all():
    """读取所有译文：[(文件名, 行号, 日文, 中文)]"""
    rows = []
    if not os.path.isdir(CN_DIR):
        return rows
    for fn in sorted(f for f in os.listdir(CN_DIR) if f.endswith(".jsonl")):
        path = os.path.join(CN_DIR, fn)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                rows.append([fn, o.get("index", 0), o.get("jp", ""), o.get("zh", "")])
    return rows


def backup():
    if not os.path.isdir(CN_DIR):
        return None
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BK_ROOT, stamp)
    os.makedirs(dst, exist_ok=True)
    for fn in os.listdir(CN_DIR):
        if fn.endswith(".jsonl"):
            shutil.copy2(os.path.join(CN_DIR, fn), os.path.join(dst, fn))
    return dst


def apply_change(rows, old, new):
    """把中文里的 old 换成 new，写回文件；返回改动条数"""
    changed = {}
    hits = 0
    for r in rows:
        if old and old in r[3]:
            r[3] = r[3].replace(old, new)
            changed.setdefault(r[0], []).append([r[1], r[3]])
            hits += 1
    for fn, items in changed.items():
        path = os.path.join(CN_DIR, fn)
        data = {}
        order = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                data[o.get("index")] = o
                order.append(o.get("index"))
        for idx, zh in items:
            if idx in data:
                data[idx]["zh"] = zh
        with open(path, "w", encoding="utf-8") as f:
            for idx in order:
                f.write(json.dumps(data[idx], ensure_ascii=False) + "\n")
    return hits


def show_hits(rows, word, limit=6):
    hits = [r for r in rows if word in r[3]]
    print(f"\n找到 {len(hits)} 处，涉及 {len(set(r[0] for r in hits))} 个文件")
    for r in hits[:limit]:
        print(f"  [{r[0]} 第{r[1]}行]")
        print(f"     现在：{r[3][:70]}")
    if len(hits) > limit:
        print(f"  …… 还有 {len(hits) - limit} 处")
    return len(hits)


def main():
    print("=" * 56)
    print("           译文一键替换工具")
    print("=" * 56)
    rows = load_all()
    if not rows:
        print(f"\n没有找到译文。请确认这个文件夹里有 json_cn 目录：\n  {CN_DIR}")
        return
    print(f"\n已载入 {len(rows)} 行译文。")
    print("用法：输入一个词 → 看它出现在哪 → 输入要换成的词 → 确认。")

    did_backup = False
    round_no = 0
    while True:
        round_no += 1
        print("\n" + "-" * 56)
        word = input("① 要查找的词（直接回车退出）：").strip()
        if not word:
            break
        n = show_hits(rows, word)
        if n == 0:
            print("  没有找到，换一个词试试（可能是全角/半角或标点不同）")
            continue
        new = input("② 替换成（直接回车 = 只看不改）：")
        if new == "":
            print("  未修改。")
            continue
        if new == word:
            print("  和原来一样，跳过。")
            continue
        confirm = input(f"③ 确认把这 {n} 处的「{word}」换成「{new}」？(y/n)：").strip().lower()
        if confirm not in ("y", "yes", "是"):
            print("  已取消。")
            continue
        if not did_backup:
            dst = backup()
            did_backup = True
            print(f"  已备份原译文到：{dst}")
        hits = apply_change(rows, word, new)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{word}\t{new}\t{hits}处\n")
        print(f"  完成，共替换 {hits} 处。")
        print("  （接着可以换下一个词；改了之后要重新注入+回封才进游戏）")

    print("\n结束。改动已保存，替换记录见：替换记录.txt")
    if did_backup:
        print("如需还原，把 备份 文件夹里最新那批文件复制回 json_cn 即可。")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n已中断，未保存的改动不会生效。")
