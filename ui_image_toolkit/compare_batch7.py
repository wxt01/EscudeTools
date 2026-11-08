# -*- coding: utf-8 -*-
"""
第 7 批对照图 + 「成品与对照图同源」校验。
对照图只从交付目录读，生成前后各取一次成品 md5，不一致直接 exit 1。
"""
import hashlib
import os
import sys
from PIL import Image, ImageDraw, ImageFont

import config_batch7 as C

BG = (18, 20, 24, 255)
FONT = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 16)
LABEL = (255, 220, 120)


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:12]


def comp(d, n):
    im = Image.open(d / (n + ".png")).convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", im.size, BG), im).convert("RGB")


def stacked(n, scale=1):
    a, b = comp(C.SRC_DIR, n), comp(C.DST_DIR, n)
    W, H = a.size
    can = Image.new("RGB", (W, H * 2 + 26), (50, 50, 55))
    dr = ImageDraw.Draw(can)
    dr.text((6, 3), n + "  原图", font=FONT, fill=LABEL)
    dr.text((6, H + 29), n + "  汉化", font=FONT, fill=(140, 235, 220))
    can.paste(a, (0, 23))
    can.paste(b, (0, H + 49))
    if scale != 1:
        can = can.resize((can.width * scale, can.height * scale), Image.NEAREST)
    return can


def crop_pair(n, box, scale=2):
    a = comp(C.SRC_DIR, n).crop(box)
    b = comp(C.DST_DIR, n).crop(box)
    W, H = a.size
    can = Image.new("RGB", (W * scale, H * scale * 2 + 48), (50, 50, 55))
    dr = ImageDraw.Draw(can)
    dr.text((5, 2), "%s %s 原图" % (n, box), font=FONT, fill=LABEL)
    dr.text((5, H * scale + 26), n + " 汉化", font=FONT, fill=(140, 235, 220))
    can.paste(a.resize((W * scale, H * scale), Image.NEAREST), (0, 22))
    can.paste(b.resize((W * scale, H * scale), Image.NEAREST), (0, H * scale + 46))
    return can


def vstack(parts, tag):
    W = max(p.width for p in parts)
    H = sum(p.height for p in parts) + 26
    can = Image.new("RGB", (W, H), (50, 50, 55))
    ImageDraw.Draw(can).text((6, 3), tag, font=FONT, fill=LABEL)
    y = 26
    for p in parts:
        can.paste(p, (0, y))
        y += p.height
    return can


def main():
    name = C.FILE_PARTS["name"]
    snap = md5(C.DST_DIR / (name + ".png"))
    out = C.DST_DIR
    made = []

    stacked(name).save(out / "对照_第7批_全图.png")
    made.append("对照_第7批_全图.png")

    crop_pair(name, (200, 755, 430, 890), 4).save(out / "对照_第7批_按钮区4x.png")
    made.append("对照_第7批_按钮区4x.png")

    vstack([
        crop_pair(name, (500, 585, 753, 725), 2),   # CHANGE 黄胶带
        crop_pair(name, (495, 720, 753, 845), 2),   # NO. / Day / 数字 / 警示章
        crop_pair(name, (0, 760, 250, 900), 2),     # 小图标 / ◀▶ / 第 4 行数字
        crop_pair(name, (0, 895, 753, 980), 1),     # 底部角色头像条
    ], "第 7 批 · 禁改装饰逐处核对（上原图 / 下汉化，应完全一致）").save(
        out / "对照_第7批_保留项.png")
    made.append("对照_第7批_保留项.png")

    after = md5(C.DST_DIR / (name + ".png"))
    if snap != after:
        print("ERROR 生成对照图期间成品被改动:", snap, "->", after)
        sys.exit(1)
    print("第 7 批对照图 %d 张已生成；成品 md5 前后一致（同源 %s）" % (len(made), snap))
    for f in made:
        print("   %-36s %8d B" % (f, (out / f).stat().st_size))
    files = sorted(f for f in os.listdir(out) if f.lower().endswith(".png"))
    print("交付目录 PNG 共 %d 张（1 成品 + %d 对照）" % (len(files), len(files) - 1))


if __name__ == "__main__":
    main()
