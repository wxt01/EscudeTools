#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_mojibake.py —— 处理「原文自己就是乱码」的台词行

背景：个别作品里有少量台词，当年打包时文本按错误编码写入（UTF-8 被当成 SJIS），
      游戏**原版**就在这里显示乱码。字节已丢失，无法还原成原始日文，
      但乱码是按 cp932 解 UTF-8 得到的，反向编码能救回一部分片段，
      再结合上下文就能确定句意，重写成通顺中文。

两步走（人确认，不自动猜）：
  1) export <译文目录> <表.tsv>
     列出所有乱码行：文件 行号 坏原文 还原片段 现译 上文 下文
  2) 把最后一列「改写」填成你要的中文，再跑
     fill <译文目录> <表.tsv>
     回填译文，并在该行写 src_note=mojibake_rewritten（qa_text.py 据此不再报警）

用法：
  python fix_mojibake.py export 3_译文 乱码待改.tsv
  python fix_mojibake.py fill   3_译文 乱码待改.tsv
"""

import argparse
import json
import os
import re
import sys

MOJIBAKE_RE = re.compile(r"[縺繧繝譁隲]|[\uff61-\uff9f]{2,}")
HEADER = ["文件", "行号", "坏原文", "还原片段", "现译", "上文", "下文", "改写"]


def recover(s):
    """cp932 字节 → utf-8 反解，救回能救的片段（坏字节显示为 �）"""
    buf = []
    for ch in s:
        try:
            buf.append(ch.encode("cp932"))
        except UnicodeEncodeError:
            buf.append(ch.encode("utf-8", "replace"))
    return b"".join(buf).decode("utf-8", "replace")


def iter_files(cn_dir):
    for fn in sorted(f for f in os.listdir(cn_dir) if f.endswith(".jsonl")):
        yield fn, os.path.join(cn_dir, fn)


def cmd_export(cn_dir, out_tsv):
    n = 0
    with open(out_tsv, "w", encoding="utf-8") as fo:
        fo.write("\t".join(HEADER) + "\n")
        for fn, path in iter_files(cn_dir):
            rows = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
            idx = {r.get("index"): r for r in rows}
            for i, r in enumerate(rows):
                zh = r.get("zh") or ""
                if not MOJIBAKE_RE.search(zh):
                    continue
                prev = (idx.get((r.get("index") or 0) - 1) or {}).get("zh") or ""
                nxt = (idx.get((r.get("index") or 0) + 1) or {}).get("zh") or ""
                cells = [fn, str(r.get("index")), r.get("jp") or "", recover(r.get("jp") or ""),
                         zh, prev, nxt, ""]
                fo.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in cells) + "\n")
                n += 1
    print(f"导出 {n} 行到 {out_tsv}")
    print("把最后一列「改写」填成中文后执行 fill；填「=」表示保持现译不动。")
    return 0


def cmd_fill(cn_dir, in_tsv):
    table = {}
    with open(in_tsv, encoding="utf-8") as f:
        next(f, None)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 8 and p[7].strip() and p[7].strip() != "=":
                table[(p[0], int(p[1]))] = p[7].strip()
    if not table:
        print("表里没有填写任何「改写」，什么都没改。")
        return 0
    done = 0
    for fn in sorted({k[0] for k in table}):
        path = os.path.join(cn_dir, fn)
        if not os.path.isfile(path):
            print(f"  ! 缺文件 {fn}")
            continue
        rows = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
        changed = False
        for r in rows:
            k = (fn, r.get("index"))
            if k in table:
                r["zh"] = table[k]
                r["src_note"] = "mojibake_rewritten"
                done += 1
                changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"回填 {done} 行；这些行已标 src_note=mojibake_rewritten")
    print("之后跑 build.py --no-gfx 重打脚本即可。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "fill"])
    ap.add_argument("json_dir", help="译文目录（3_译文）")
    ap.add_argument("tsv", help="导出/回填用的 tsv")
    a = ap.parse_args()
    if a.cmd == "export":
        return cmd_export(a.json_dir, a.tsv)
    return cmd_fill(a.json_dir, a.tsv)


if __name__ == "__main__":
    sys.exit(main())
