#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_custom_patch.py —— 零散界面图的点对点汉化（逐像素抠色）

⚠️ 实验脚本，实测**未通过**，保留作参考，不建议直接用于产出。
   失败原因：底色是金箔/渐变时，"暗色文字"与"暗色底纹"分不开，
   擦字会把底纹一起抠掉，残留斑块。详见 docs/05-界面图汉化.md。

与 ui_image_patch.py 的区别：那张是「多列栅格标签」，这里是大小不一的小图，
所以按图单独配置：给出擦除方式（擦亮字 / 擦暗字）和文案，自动定位文字包围盒。
文案目前写在脚本内的 PAGES 里，按需修改。

用法：
  python ui_custom_patch.py --in <gfx/sys> --out <输出目录>
"""

import argparse
import os
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\msyh.ttc"

# mode: bright=擦掉亮色字（白字），dark=擦掉暗色字（深色字）
CONFIG = {
    "common/confirm_parts.png": {
        "mode": "bright",
        "band": (0.86, 1.0),        # 只在图片底部找
        "texts": ["下次不再确认"] * 3,
        "size_ratio": 0.62,
    },
    "file/save_title.png": {
        "mode": "dark",
        "inset": (0.16, 0.26, 0.84, 0.78),
        "texts": ["存 档"],
        "size_ratio": 0.62,
    },
    "file/load_title.png": {
        "mode": "dark",
        "inset": (0.16, 0.26, 0.84, 0.78),
        "texts": ["读 档"],
        "size_ratio": 0.62,
    },
}


def runs_of(flags, min_len=20, max_gap=8):
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


def patch_one(im, cfg, text_list):
    a = np.array(im).astype(np.int16)
    lum = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    alpha = a[..., 3]
    H, W = lum.shape

    boxes = []
    if cfg["mode"] == "bright":
        y0 = int(H * cfg["band"][0])
        band = (alpha[y0:] > 128) & (lum[y0:] > 190)
        cols = band.sum(axis=0) > 0
        for x0, x1 in runs_of(cols, min_len=60, max_gap=40):
            sub = band[:, x0:x1 + 1]
            rows = np.where(sub.any(axis=1))[0]
            if len(rows) == 0:
                continue
            boxes.append((x0, y0 + int(rows[0]), x1, y0 + int(rows[-1])))
    else:
        ix0, iy0, ix1, iy1 = cfg["inset"]
        sx0, sy0, sx1, sy1 = int(W * ix0), int(H * iy0), int(W * ix1), int(H * iy1)
        boxes.append((sx0, sy0, sx1, sy1))

    if len(boxes) != len(text_list):
        raise RuntimeError(f"检测到 {len(boxes)} 处，文案 {len(text_list)} 条")

    work = Image.fromarray(a.astype(np.uint8), "RGBA")
    wa = np.array(work).copy()
    for (x0, y0, x1, y1), zh in zip(boxes, text_list):
        pad = 6
        ex0, ey0 = max(0, x0 - pad), max(0, y0 - pad)
        ex1, ey1 = min(W - 1, x1 + pad), min(H - 1, y1 + pad)
        reg = wa[ey0:ey1 + 1, ex0:ex1 + 1]
        if cfg["mode"] == "bright":
            sel = (reg[..., 3] > 128) & (reg[..., 0] * 0.299 + reg[..., 1] * 0.587 + reg[..., 2] * 0.114 > 190)
            color = (255, 255, 255, 255)
            edge = (10, 20, 20, 170)
        else:
            sel = (reg[..., 3] > 128) & (reg[..., 0] * 0.299 + reg[..., 1] * 0.587 + reg[..., 2] * 0.114 < 110)
            px = reg[sel]
            color = tuple(int(v) for v in np.median(px[:, :3], axis=0)) + (255,) if len(px) else (60, 40, 25, 255)
            edge = (255, 240, 200, 90)
        reg[sel, 3] = 0
        wa[ey0:ey1 + 1, ex0:ex1 + 1] = reg
    work = Image.fromarray(wa, "RGBA")

    d = ImageDraw.Draw(work)
    for (x0, y0, x1, y1), zh in zip(boxes, text_list):
        h = y1 - y0 + 1
        size = max(10, int(h * cfg.get("size_ratio", 0.7) * 1.35))
        font = ImageFont.truetype(FONT, size)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            d.text((cx + dx, cy + dy), zh, font=font, fill=edge, anchor="mm")
        d.text((cx, cy), zh, font=font, fill=color, anchor="mm")
    return work


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    done = []
    for rel, cfg in CONFIG.items():
        p = os.path.join(args.src, rel)
        if not os.path.exists(p):
            print(f"  跳过 {rel}")
            continue
        im = Image.open(p).convert("RGBA")
        try:
            out = patch_one(im, cfg, cfg["texts"])
        except Exception as e:
            print(f"  ! {rel}: {e}")
            continue
        dst = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        out.save(dst)
        done.append(rel)
        print(f"  ✓ {rel}  {len(cfg['texts'])} 处")

    if args.preview and done:
        ims = []
        for rel in done:
            im = Image.open(os.path.join(args.out, rel)).convert("RGBA")
            bg = Image.new("RGBA", im.size, (34, 40, 36, 255))
            bg.alpha_composite(im)
            ims.append(bg.convert("RGB"))
        W = max(i.width for i in ims)
        H = sum(i.height for i in ims)
        canvas = Image.new("RGB", (W, H), (34, 40, 36))
        y = 0
        for i in ims:
            canvas.paste(i, (0, y))
            y += i.height
        canvas.save(args.preview)
        print("  预览:", args.preview)


if __name__ == "__main__":
    main()
