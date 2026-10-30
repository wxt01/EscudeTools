#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_image_patch.py —— 把烧在界面图里的日文换成中文

适用：gfx/sys/config/frame_*.png（设置界面的 5 个页签底图）这类
      「透明背景 + 水彩笔触 + 烧死的日文」的图。

做法：
  1. 按行分离「文字带」与下面的水彩笔触（笔触那几行像素数会突然翻倍）
  2. 在文字带里按列聚类，得到每个标签的矩形
  3. 只把矩形内的不透明像素抹掉（笔触保留），再用原文字颜色写中文

用法：
  python ui_image_patch.py --in <gfx/sys 原目录> --out <输出目录> [--preview 名字]
"""

import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

# 文案不写死在代码里：由 --labels 指定的 JSON 提供，格式见 ui_labels.example.json
# {
#   "font": "C:\\Windows\\Fonts\\msyh.ttc",
#   "pages": {
#     "config/frame_text.png": {"rows": [3, 3, 3], "texts": ["第一行左", "第一行中", ...]}
#   }
# }
# rows 是「每一行有几个标签」，必须与实际图一致；数量对不上脚本会跳过并提示。


def load_labels(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    pages = cfg.get("pages") or {k: v for k, v in cfg.items()
                                 if isinstance(v, dict) and "texts" in v}
    return cfg.get("font") or FONT_PATH, pages


def text_boxes(im, gap=60, min_w=40):
    a = np.array(im)
    al = a[..., 3] > 0
    rows = np.where(al.any(axis=1))[0]
    if len(rows) == 0:
        return []
    bands, start, prev = [], rows[0], rows[0]
    for y in rows[1:]:
        if y - prev > 4:
            bands.append((start, prev))
            start = y
        prev = y
    bands.append((start, prev))

    out = []
    for y0, y1 in bands:
        cnt = al[y0:y1 + 1].sum(axis=1)
        if len(cnt) < 8:
            continue
        plateau = np.median(cnt[:max(3, int(len(cnt) * 0.5))])
        cut = next((i for i, c in enumerate(cnt) if c > plateau * 1.15 and i > 3), len(cnt) - 1)
        te = y0 + cut - 1
        sub = al[y0:te + 1]
        cols = np.where(sub.any(axis=0))[0]
        if len(cols) == 0:
            continue
        cs, cp = cols[0], cols[0]
        for x in cols[1:]:
            if x - cp > gap:
                if cp - cs >= min_w:
                    out.append((int(cs), int(y0), int(cp), int(te)))
                cs = x
            cp = x
        if cp - cs >= min_w:
            out.append((int(cs), int(y0), int(cp), int(te)))
    return sorted(out, key=lambda b: (b[1] // 80, b[0]))


def split_row(al, y0, y1, k, width=None):
    """3 列栅格布局：把行宽按 k 等分，再在每个等分内收紧到实际墨迹"""
    if width is None:
        width = al.shape[1]
    if k <= 0:
        return []
    prof = al[y0:y1 + 1].any(axis=0)
    boxes = []
    for i in range(k):
        a = int(width * i / k)
        b = int(width * (i + 1) / k)
        sub = al[y0:y1 + 1, a:b].sum(axis=0)
        cols = np.where(sub > 0)[0]
        if len(cols) == 0:
            continue
        # 取最长的连续墨迹段（间隔 <=8px 视为连续），丢掉笔触飞溅的零散点
        runs, cs, cp = [], cols[0], cols[0]
        for x in cols[1:]:
            if x - cp > 8:
                runs.append((cs, cp))
                cs = x
            cp = x
        runs.append((cs, cp))
        r0, r1 = max(runs, key=lambda r: int(sub[r[0]:r[1] + 1].sum()))
        # 擦除用整列，保证不残留日文；居中用实际墨迹
        boxes.append((a, int(y0), b - 1, int(y1), a + int(r0), a + int(r1)))
    return boxes


def detect(im, rows):
    """按给定的每行标签数切出文字块"""
    al = (np.array(im)[..., 3] > 0)
    yrows = np.where(al.any(axis=1))[0]
    if len(yrows) == 0:
        return []
    bands, start, prev = [], yrows[0], yrows[0]
    for y in yrows[1:]:
        if y - prev > 4:
            bands.append((start, prev))
            start = y
        prev = y
    bands.append((start, prev))

    text_bands = []
    for y0, y1 in bands:
        if (y1 - y0 + 1) > 200:         # 整块照片/边框
            continue
        cnt = al[y0:y1 + 1].sum(axis=1)
        plateau = np.median(cnt[:max(3, int(len(cnt) * 0.5))])
        cut = next((i for i, c in enumerate(cnt) if c > plateau * 1.15 and i > 3), len(cnt) - 1)
        te = int(y0 + cut - 1)
        if (te - y0 + 1) > 45:          # 切出来仍偏高，说明不是单行标签
            continue
        text_bands.append((int(y0), te))
    boxes = []
    for (y0, y1), k in zip(text_bands, rows):
        boxes.extend(split_row(al, y0, y1, k))
    return boxes


def patch(im, boxes, texts):
    a = np.array(im)
    wa = np.array(im).copy()
    colors = []
    for (x0, y0, x1, y1, _tx0, _tx1) in boxes:
        region = a[y0:y1 + 1, _tx0:_tx1 + 1]
        px = region[region[..., 3] > 128]
        if len(px) == 0:
            colors.append((255, 255, 255, 255))
            continue
        lum = px[:, :3].sum(axis=1)
        top = px[lum >= np.median(lum)]
        colors.append(tuple(int(v) for v in np.median(top[:, :3], axis=0)) + (255,))
        # 真正的擦除：写回像素数组
        sub = wa[y0:y1 + 1, x0:x1 + 1]
        sub[sub[..., 3] > 0, 3] = 0
        wa[y0:y1 + 1, x0:x1 + 1] = sub

    work = Image.fromarray(wa, "RGBA")
    d = ImageDraw.Draw(work)
    for (x0, y0, x1, y1, tx0, tx1), zh, color in zip(boxes, texts, colors):
        h = y1 - y0 + 1
        size = max(10, int(h * 0.95))
        font = ImageFont.truetype(FONT_PATH, size)
        cx, cy = (tx0 + tx1) / 2, (y0 + y1) / 2 + 1
        edge = (16, 24, 26, 150)      # 细描边，避免黑框太重
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            d.text((cx + dx, cy + dy), zh, font=font, fill=edge, anchor="mm")
        d.text((cx, cy), zh, font=font, fill=color, anchor="mm")
    return work


def main():
    global FONT_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="原版 gfx/sys 目录")
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", required=True, help="文案配置 JSON，见 ui_labels.example.json")
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    FONT_PATH, pages = load_labels(args.labels)

    if os.path.exists(args.out):
        import shutil
        shutil.rmtree(args.out)
    os.makedirs(args.out)

    done = []
    for rel, cfg in pages.items():
        texts, rows = cfg["texts"], cfg["rows"]
        p = os.path.join(args.src, rel)
        if not os.path.exists(p):
            print(f"  跳过（不存在）{rel}")
            continue
        im = Image.open(p).convert("RGBA")
        boxes = detect(im, rows)
        if len(boxes) != len(texts):
            print(f"  ! {rel} 检测 {len(boxes)} 块，文案 {len(texts)} 条，跳过")
            continue
        out = patch(im, boxes, texts)
        dst = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        out.save(dst)
        done.append((rel, len(boxes)))

    for rel, n in done:
        print(f"  ✓ {rel}  {n} 条")

    if args.preview:
        ims = [Image.open(os.path.join(args.out, r)) for r, _ in done]
        W = max(i.width for i in ims)
        H = sum(i.height for i in ims)
        canvas = Image.new("RGBA", (W, H), (30, 34, 32, 255))
        y = 0
        for i in ims:
            canvas.alpha_composite(i, (0, y))
            y += i.height
        canvas.convert("RGB").save(args.preview)
        print("  预览:", args.preview)


if __name__ == "__main__":
    main()
