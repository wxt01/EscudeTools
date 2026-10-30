#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_inpaint_patch.py —— 用「干净行复制」擦除图片文字，再写中文

思路：一张界面图里，文字只占少数行。把「没有文字的行」整段复制过去盖住文字行，
      因为按钮/牌子的底色是竖向渐变，同宽复制不会有色差，也不会啃坏水彩描边。

适用与不适用（务必先看 docs/05-界面图汉化.md）：
  适用：底色是纯色或竖向渐变的区域（设置页标签、确认框勾选项）
  不适用：文字背面压着高光/水彩笔触的图（标题画面按钮小字）—— 任何填平都会留下色带

用法：
  python ui_inpaint_patch.py --in <gfx/sys> --out <输出目录> --config ui_misc.json [--preview 图]
"""

import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:/Windows/Fonts/msyh.ttc"


def runs(flags, min_len=2):
    idx = np.where(flags)[0]
    if len(idx) == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for x in idx[1:]:
        if x - p > 1:
            if p - s + 1 >= min_len:
                out.append((int(s), int(p)))
            s = x
        p = x
    if p - s + 1 >= min_len:
        out.append((int(s), int(p)))
    return out


def fill_rows(wa, x0, y0, x1, y1, text_row_flags):
    """把 text_row_flags 为真的行，用同宽干净行覆盖"""
    bands = runs(text_row_flags, 2)
    clean = runs(~text_row_flags, 3)
    for b0, b1 in bands:
        h = b1 - b0 + 1
        cands = [(abs((c0 + c1) // 2 - (b0 + b1) // 2), c0, c1)
                 for c0, c1 in clean if c1 - c0 + 1 >= h]
        if not cands:
            continue
        _, c0, c1 = min(cands)
        src = wa[y0 + c0:y0 + c0 + h, x0:x1 + 1].copy()
        wa[y0 + b0:y0 + b0 + h, x0:x1 + 1] = src
    return wa


def put_text(img, cx, cy, text, size, color, edge):
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, size)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.text((cx + dx, cy + dy), text, font=font, fill=edge, anchor="mm")
    d.text((cx, cy), text, font=font, fill=color, anchor="mm")


# 标题按钮下方小字的默认文案；实际使用 --config 里的 texts（见 ui_misc.example.json）
MENU_SUBS = ["开始游戏", "外传篇章", "后日谈", "读取进度", "更改设定", "附加内容", "退出游戏"]



def do_menu_button(im, subs=None):
    """每列里凡是高度<=16 的白色行带，就是英文下方的日文小字：填平后写中文"""
    a = np.array(im)
    al = a[..., 3] > 128
    lum = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    white = al & (lum > 195)
    H, W = al.shape
    wa = a.copy()
    subs = subs or MENU_SUBS

    cols = runs(al.any(axis=0), 60)[:7]
    tasks = []
    for ci, (cx0, cx1) in enumerate(cols):
        bands = runs(white[:, cx0:cx1 + 1].any(axis=1), 3)
        for (b0, b1) in bands:
            h = b1 - b0 + 1
            if h > 16 or h < 6:
                continue
            # 采样点取小字上方/下方各 3px 处，肯定没有字
            # 逐列重建：用该列上下最近的「无字像素」线性插值，保住渐变与边缘
            y0, y1 = max(0, b0 - 2), min(H - 1, b1 + 2)
            for xx in range(cx0 + 2, cx1 - 1):
                top_c = bot_c = None
                for yy in range(y0 - 1, max(-1, y0 - 26), -1):
                    px = wa[yy, xx]
                    if px[3] > 128 and px[0] * 0.299 + px[1] * 0.587 + px[2] * 0.114 < 185:
                        top_c = px[:3].astype(np.float32)
                        top_y = yy
                        break
                for yy in range(y1 + 1, min(H, y1 + 26)):
                    px = wa[yy, xx]
                    if px[3] > 128 and px[0] * 0.299 + px[1] * 0.587 + px[2] * 0.114 < 185:
                        bot_c = px[:3].astype(np.float32)
                        bot_y = yy
                        break
                if top_c is None and bot_c is None:
                    continue
                if top_c is None:
                    top_c, top_y = bot_c, y0
                if bot_c is None:
                    bot_c, bot_y = top_c, y1
                for yy in range(y0, y1 + 1):
                    t = (yy - top_y) / max(1, (bot_y - top_y))
                    t = min(1.0, max(0.0, t))
                    col = (top_c * (1 - t) + bot_c * t).astype(np.uint8)
                    wa[yy, xx, :3] = col
                    wa[yy, xx, 3] = 255
            tasks.append((cx0, cx1, b0, b1, subs[ci]))

    out = Image.fromarray(wa, "RGBA")
    d = ImageDraw.Draw(out)
    for (cx0, cx1, ty0, ty1, label) in tasks:
        h = ty1 - ty0 + 1
        size = max(9, int(h * 0.95))
        font = ImageFont.truetype(FONT, size)
        cx, cy = (cx0 + cx1) / 2, (ty0 + ty1) / 2
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            d.text((cx + dx, cy + dy), label, font=font, fill=(0, 42, 40, 200), anchor="mm")
        d.text((cx, cy), label, font=font, fill=(212, 242, 238, 255), anchor="mm")
    print("   小字替换", len(tasks), "处")
    return out


def do_title(im, text):
    a = np.array(im)
    al = a[..., 3] > 128
    lum = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    H, W = al.shape
    x0, x1 = int(W * 0.10), int(W * 0.90)
    y0, y1 = int(H * 0.18), int(H * 0.84)
    reg = al[y0:y1 + 1, x0:x1 + 1] & (lum[y0:y1 + 1, x0:x1 + 1] < 120)
    flags = reg.any(axis=1)
    wa = a.copy()
    fill_rows(wa, x0, y0, x1, y1, flags)
    out = Image.fromarray(wa, "RGBA")
    put_text(out, W / 2, (y0 + y1) / 2, text, int(H * 0.5), (86, 40, 20, 255), (255, 238, 205, 110))
    return out


def do_confirm(im, text="下次不再确认"):
    a = np.array(im)
    al = a[..., 3] > 128
    lum = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    white = al & (lum > 200)
    H, W = al.shape

    ytop = int(H * 0.86)
    plate = al[ytop:] & (a[ytop:, :, :3].sum(axis=2) < 300)
    colruns = runs(plate.any(axis=0), 100)[:3]
    wa = a.copy()
    tasks = []
    for (px0, px1) in colruns:
        reg = white[ytop:H, px0 + 35:px1 + 1]
        rows = np.where(reg.any(axis=1))[0]
        if len(rows) == 0:
            continue
        b0, b1 = ytop + int(rows[0]), ytop + int(rows[-1])
        fill_rows(wa, px0 + 35, ytop, px1, H - 1, white[ytop:H, px0 + 35:px1 + 1].any(axis=1))
        tasks.append((px0 + 35, px1, b0, b1))

    out = Image.fromarray(wa, "RGBA")
    d = ImageDraw.Draw(out)
    for (x0, x1, ty0, ty1) in tasks:
        size = max(10, int((ty1 - ty0 + 1) * 1.0))
        font = ImageFont.truetype(FONT, size)
        cx, cy = (x0 + x1) / 2, (ty0 + ty1) / 2
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            d.text((cx + dx, cy + dy), text, font=font, fill=(0, 0, 0, 190), anchor="mm")
        d.text((cx, cy), text, font=font, fill=(255, 255, 255, 255), anchor="mm")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="原版 gfx/sys 目录")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", required=True, help="任务配置 JSON，见 ui_misc.example.json")
    ap.add_argument("--only", default="", help="只处理指定的图，逗号分隔")
    ap.add_argument("--preview", default="")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    jobs = cfg.get("jobs") or []

    only = [x.strip() for x in args.only.split(",") if x.strip()]
    if only:
        jobs = [j for j in jobs if j.get("file") in only]

    os.makedirs(args.out, exist_ok=True)
    done = []
    for job in jobs:
        rel = job.get("file", "")
        typ = job.get("type", "confirm")
        p = os.path.join(args.src, rel)
        if not rel or not os.path.exists(p):
            print("  跳过", rel or "(未指定 file)")
            continue
        im = Image.open(p).convert("RGBA")
        if typ == "menu_button":
            out = do_menu_button(im, job.get("texts"))
        elif typ == "title":
            out = do_title(im, job.get("text", ""))
        elif typ == "confirm":
            out = do_confirm(im, job.get("text", "下次不再确认"))
        else:
            print(f"  ! 未知类型 {typ}，跳过 {rel}")
            continue
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
            canvas.paste(i, (0, y)); y += i.height
        canvas.save(args.preview)
        print("  预览:", args.preview)


if __name__ == "__main__":
    main()
