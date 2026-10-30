#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_cover_patch.py —— 「整块覆盖」式界面图汉化

⚠️ 实验脚本，**仅在纯色底上可用**。渐变底/带纹理的底会出现色块接缝，
   比不翻更难看，因此未采用。保留作参考。详见 docs/05-界面图汉化.md。

思路：直接在文字区域盖一块同色底板再写字，不做逐像素抠色，
所以不会咬坏描边，代价是盖住的地方失去纹理。
底板颜色从附近像素采样，并加轻微噪点，尽量和周围融合。

用法：
  python ui_cover_patch.py --in <gfx/sys> --out <输出目录> [--preview 文件]
"""

import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:/Windows/Fonts/msyhbd.ttc"


def sample_color(a, x, y, r=6):
    h, w = a.shape[:2]
    x0, x1 = max(0, x - r), min(w, x + r)
    y0, y1 = max(0, y - r), min(h, y + r)
    reg = a[y0:y1, x0:x1]
    reg = reg[reg[..., 3] > 128]
    if len(reg) == 0:
        return (0, 0, 0, 255)
    return tuple(int(v) for v in np.median(reg[:, :3], axis=0)) + (255,)


def cover_with_color(img, box, color, noise=6):
    x0, y0, x1, y1 = box
    arr = np.array(img)
    h, w = y1 - y0, x1 - x0
    if h <= 0 or w <= 0:
        return img
    patch = np.zeros((h, w, 4), dtype=np.uint8)
    patch[..., :3] = color[:3]
    patch[..., 3] = 255
    if noise:
        n = np.random.randint(-noise, noise + 1, size=(h, w, 1))
        patch[..., :3] = np.clip(patch[..., :3].astype(np.int16) + n, 0, 255)
    arr[y0:y1, x0:x1] = patch
    return Image.fromarray(arr, "RGBA")


def draw_text(img, box, text, size, color, edge):
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, size)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.text((cx + dx, cy + dy), text, font=font, fill=edge, anchor="mm")
    d.text((cx, cy), text, font=font, fill=color, anchor="mm")
    return img


def bands(flags, min_len=8, max_gap=6):
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


def do_menu_button(im):
    labels = ["继续游戏", "外传故事", "后日谈", "读取存档", "设置", "特典", "退出游戏"]
    a = np.array(im)
    al = a[..., 3] > 128
    yrow = np.where(al.any(axis=1))[0]
    top, bot = int(yrow[0]), int(yrow[-1])
    step = (bot - top + 1) / 4.0
    rows = [(int(top + i * step), int(top + (i + 1) * step) - 1) for i in range(4)]
    cols = bands(al.any(axis=0), min_len=40, max_gap=6)[:7]
    out = im
    for (y0, y1) in rows:
        for ci, (x0, x1) in enumerate(cols):
            color = sample_color(a, x0 + 12, (y0 + y1) // 2, 4)
            box = (x0 + 8, y0 + 7, x1 - 6, y1 - 6)
            out = cover_with_color(out, box, color)
            draw_text(out, box, labels[ci], max(14, int((y1 - y0) * 0.42)),
                      (255, 255, 255, 255), (0, 40, 38, 255))
    return out


def do_title(im, text):
    a = np.array(im)
    color = sample_color(a, 40, 20, 8)
    box = (int(im.width * 0.13), int(im.height * 0.24),
           int(im.width * 0.87), int(im.height * 0.78))
    out = cover_with_color(im, box, color, noise=4)
    draw_text(out, box, text, int(im.height * 0.5), (70, 30, 18, 255), (255, 235, 200, 90))
    return out


def do_confirm(im):
    a = np.array(im)
    al = a[..., 3] > 128
    H, W = al.shape
    y0band = int(H * 0.86)
    dark = al[y0band:] & (a[y0band:, :, 0] + a[y0band:, :, 1] + a[y0band:, :, 2] < 260)
    cols = bands(dark.any(axis=0), min_len=120, max_gap=20)
    out = im
    for (x0, x1) in cols[:3]:
        color = sample_color(a, x0 + 8, y0band + (H - y0band) // 2, 4)
        box = (x0 + 40, y0band + 8, x1 - 8, H - 10)
        out = cover_with_color(out, box, color, noise=4)
        draw_text(out, box, "下次不再确认", max(12, int((H - y0band) * 0.30)),
                  (255, 255, 255, 255), (0, 0, 0, 180))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    jobs = [
        ("title/menu_button.png", lambda im: do_menu_button(im)),
        ("file/save_title.png", lambda im: do_title(im, "存 档")),
        ("file/load_title.png", lambda im: do_title(im, "读 档")),
        ("common/confirm_parts.png", lambda im: do_confirm(im)),
    ]
    os.makedirs(args.out, exist_ok=True)
    done = []
    for rel, fn in jobs:
        p = os.path.join(args.src, rel)
        if not os.path.exists(p):
            print("  跳过", rel)
            continue
        im = Image.open(p).convert("RGBA")
        out = fn(im)
        dst = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        out.save(dst)
        done.append(rel)
        print("  ✓", rel)
    if args.preview and done:
        ims = []
        for rel in done:
            im = Image.open(os.path.join(args.out, rel)).convert("RGBA")
            bg = Image.new("RGBA", im.size, (20, 26, 24, 255))
            bg.alpha_composite(im)
            ims.append(bg.convert("RGB"))
        W = max(i.width for i in ims)
        Hh = sum(i.height for i in ims)
        canvas = Image.new("RGB", (W, Hh), (20, 26, 24))
        y = 0
        for i in ims:
            canvas.paste(i, (0, y))
            y += i.height
        canvas.save(args.preview)
        print("  预览:", args.preview)


if __name__ == "__main__":
    main()
