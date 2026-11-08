# -*- coding: utf-8 -*-
"""
第 6 批（8 张）分组对照图 + 「成品与对照图同源」校验。

沿用 compare_batch4.py 的教训：对照图只从交付目录读，生成前后各取一次
成品 md5，不一致直接报错，杜绝「对照图正常、成品是旧稿」。
运行：工具/ 目录执行 python compare_batch6.py
"""
import hashlib
import os
import sys
from PIL import Image, ImageDraw, ImageFont

import config_batch6 as C

BG = (18, 20, 24, 255)
FONT = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 16)
LABEL_FG = (255, 220, 120)


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:12]


def comp(d, n):
    im = Image.open(d / (n + ".png")).convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", im.size, BG), im).convert("RGB")


def before():
    return {n: md5(C.DST_DIR / (n + ".png")) for n in C.ALL_NAMES}


def stacked(n, scale=1):
    """单张：原图在上、汉化在下。"""
    a, b = comp(C.SRC_DIR, n), comp(C.DST_DIR, n)
    W, H = a.size
    can = Image.new("RGB", (W, H * 2 + 26), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((6, 3), n + "  原图", font=FONT, fill=LABEL_FG)
    d.text((6, H + 29), n + "  汉化", font=FONT, fill=(140, 235, 220))
    can.paste(a, (0, 23))
    can.paste(b, (0, H + 49))
    if scale != 1:
        can = can.resize((can.width * scale, can.height * scale), Image.NEAREST)
    return can


def grid(names, cw, ch, cols=2, tag=""):
    rows = (len(names) + cols - 1) // cols
    can = Image.new("RGB", (cw * cols, ch * rows + 26), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((6, 3), tag, font=FONT, fill=LABEL_FG)
    for i, n in enumerate(names):
        p = stacked(n)
        x, y = (i % cols) * cw, (i // cols) * ch + 26
        can.paste(p.crop((0, 0, min(p.width, cw), min(p.height, ch))), (x, y))
    return can


def crop_pair(n, box, scale=2):
    """局部放大：上原图 / 下汉化，NEAREST 不做插值糊字。"""
    a = comp(C.SRC_DIR, n).crop(box)
    b = comp(C.DST_DIR, n).crop(box)
    W, H = a.size
    can = Image.new("RGB", (W * scale, H * scale * 2 + 48), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((5, 2), "%s %s 原图" % (n, box), font=FONT, fill=LABEL_FG)
    d.text((5, H * scale + 26), n + " 汉化", font=FONT, fill=(140, 235, 220))
    can.paste(a.resize((W * scale, H * scale), Image.NEAREST), (0, 22))
    can.paste(b.resize((W * scale, H * scale), Image.NEAREST), (0, H * scale + 46))
    return can


def vstack(parts, tag):
    W = max(p.width for p in parts)
    H = sum(p.height for p in parts) + 26
    can = Image.new("RGB", (W, H), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((6, 3), tag, font=FONT, fill=LABEL_FG)
    y = 26
    for p in parts:
        can.paste(p, (0, y))
        y += p.height
    return can


def main():
    snap = before()
    out = C.DST_DIR
    made = []

    # 1 木牌标题 / 退出按钮 / 鉴赏率牌（小图，整张上下对照）
    g = grid(["title", "quit", "rate"], 430, 370, 2,
             "第 6 批 · 木牌标题 / 退出按钮 / 鉴赏率牌   上原图 / 下汉化")
    g.save(out / "对照_第6批_标题与按钮.png")
    made.append("对照_第6批_标题与按钮.png")

    # 2 两张长图（面板 / 对话框），整张 1x 上下对照
    g = grid(["panel", "dialog"], 380, 1490, 2,
             "第 6 批 · 设置面板 / 确认对话框   上原图 / 下汉化")
    g.save(out / "对照_第6批_面板与对话框.png")
    made.append("对照_第6批_面板与对话框.png")

    # 3 两张部件图整张 + 确认框整张
    stacked("confirm_parts").save(out / "对照_第6批_确认框.png")
    made.append("对照_第6批_确认框.png")
    grid(["chart_parts", "config_parts"], 440, 620, 2,
         "第 6 批 · 流程图部件 / 设置页部件   上原图 / 下汉化").save(
        out / "对照_第6批_部件图.png")
    made.append("对照_第6批_部件图.png")

    # 4 小字放大：肉眼验收最容易看不清的地方
    zoom = [
        crop_pair("title", (20, 14, 340, 74), 3),
        crop_pair("rate", (45, 60, 110, 92), 8),
        crop_pair("chart_parts", (210, 255, 265, 287), 8),
        crop_pair("dialog", (0, 136, 190, 176), 4),
        crop_pair("dialog", (20, 266, 195, 386), 3),
        crop_pair("panel", (90, 0, 300, 32), 4),
        crop_pair("panel", (175, 108, 300, 142), 5),
        crop_pair("panel", (172, 314, 300, 352), 5),
        crop_pair("panel", (85, 544, 295, 578), 4),
        crop_pair("confirm_parts", (55, 588, 290, 634), 4),
        crop_pair("config_parts", (160, 0, 430, 130), 4),
    ]
    vstack(zoom, "第 6 批 · 小字逐处放大验收（上原图 / 下汉化）").save(
        out / "对照_第6批_小字放大.png")
    made.append("对照_第6批_小字放大.png")

    # 同源校验：对照图生成期间成品不得被改动
    after = {n: md5(C.DST_DIR / (n + ".png")) for n in C.ALL_NAMES}
    bad = [n for n in C.ALL_NAMES if snap[n] != after[n]]
    if bad:
        print("ERROR 生成对照图期间成品被改动:", bad)
        sys.exit(1)
    print("第 6 批对照图 %d 张已生成；8 张成品 md5 生成前后一致（同源）" % len(made))
    for f in made:
        p = out / f
        print("   %-36s %8d B" % (f, p.stat().st_size))
    files = sorted(f for f in os.listdir(out) if f.lower().endswith(".png"))
    print("交付目录 PNG 共 %d 张（8 成品 + %d 对照）" % (len(files), len(files) - 8))


if __name__ == "__main__":
    main()
