#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_button_patch.py —— 标题画面按钮图汉化（4 状态 × N 按钮）

⚠️ 实验脚本，**未采用**。英文主标能保住，但按钮下方那行日文小字压在一条高光上，
   任何填平都会留下亮带或描边残影（试过 6 种办法）。保留作参考。
   详见 docs/05-界面图汉化.md 的「做不了的怎么办」。

思路：切格 → 找白色文字范围 → 用邻近条带覆盖擦除 → 在英文行下方居中写中文。
"""

import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:/Windows/Fonts/msyhbd.ttc"
RELPATH = "menu_button.png"
LABELS = ["继续游戏", "外传故事", "后日谈", "读取存档", "设置", "特典", "退出游戏"]


def bands(flags, min_len=2, max_gap=4):
    idx = np.where(flags)[0]
    if len(idx) == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for x in idx[1:]:
        if x - p > max_gap:
            if p - s >= min_len:
                out.append((int(s), int(p)))
            s = x
        p = x
    if p - s >= min_len:
        out.append((int(s), int(p)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    im = Image.open(os.path.join(args.src, RELPATH)).convert("RGBA")
    a = np.array(im)
    al = a[..., 3] > 128
    H, W = al.shape

    yrow = np.where(al.any(axis=1))[0]
    top, bot = int(yrow[0]), int(yrow[-1])
    step = (bot - top + 1) / 4.0
    rows = [(int(top + i * step), int(top + (i + 1) * step) - 1) for i in range(4)]
    cols = bands(al.any(axis=0), min_len=40, max_gap=6)
    print(f"行 {len(rows)}，列 {len(cols)}")

    wa = a.copy()
    lum_all = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    white_all = (a[..., 3] > 128) & (lum_all > 210)

    # 全文按「白色文字行带」切分：4 行 × 2 行字 = 8 条
    text_bands = bands(white_all.any(axis=1), min_len=6, max_gap=2)
    print("文字行带", len(text_bands), text_bands)

    tasks = []
    for (ty0, ty1) in text_bands:
        h = ty1 - ty0 + 1
        is_title = h >= 18          # 大号英文行
        seg = white_all[ty0:ty1 + 1]
        for (cx0, cx1) in bands(seg.any(axis=0), min_len=30, max_gap=12):
            edge = cx0 - 6 if cx0 - 6 > 0 else cx0 + 6
            col = wa[ty0:ty1 + 1, edge:edge + 1].copy()
            wa[ty0:ty1 + 1, cx0 - 6:cx1 + 7] = col
            if is_title:
                # 归属第几列（按按钮列中心）
                mid = (cx0 + cx1) / 2
                idx = min(range(len(cols)), key=lambda i: abs((cols[i][0] + cols[i][1]) / 2 - mid))
                tasks.append((cx0, cx1, ty0, ty1, LABELS[idx]))

    out = Image.fromarray(wa, "RGBA")
    d = ImageDraw.Draw(out)
    for (x0, x1, ey0, ey1, label) in tasks:
        h = ey1 - ey0 + 1
        size = max(12, int(h * 0.98))
        font = ImageFont.truetype(FONT, size)
        cx, cy = (x0 + x1) / 2, (ey0 + ey1) / 2
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            d.text((cx + dx, cy + dy), label, font=font, fill=(0, 30, 28, 255), anchor="mm")
        d.text((cx, cy), label, font=font, fill=(255, 255, 255, 255), anchor="mm")

    os.makedirs(args.out, exist_ok=True)
    dst = os.path.join(args.out, RELPATH)
    out.save(dst)
    print("已输出", dst, "共", len(tasks), "个按钮")

    if args.preview:
        bg = Image.new("RGBA", out.size, (18, 24, 22, 255))
        bg.alpha_composite(out)
        bg.convert("RGB").save(args.preview)


if __name__ == "__main__":
    main()
