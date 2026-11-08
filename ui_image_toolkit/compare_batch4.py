# -*- coding: utf-8 -*-
"""
生成本批分组对照图，并做「成品与对照图同源」校验。

★ 上一批踩过：对照图从完整成品生成，之后交付文件被旧稿覆盖，
  出现「对照图正常、成品没汉化」。所以这里生成前后各取一次 md5，
  不一致直接报错；对照图只从交付目录读，绝不另存一份成品当样本。
运行：工具/ 目录执行 python compare_batch4.py
"""
import hashlib
import os
import sys
from PIL import Image, ImageDraw, ImageFont

import config_batch4 as C

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
        # 居中放进格子，不拉伸
        can.paste(p.crop((0, 0, min(p.width, cw), min(p.height, ch))), (x, y))
    return can


def crop_pair(n, box, scale=2):
    a = comp(C.SRC_DIR, n).crop(box)
    b = comp(C.DST_DIR, n).crop(box)
    W, H = a.size
    can = Image.new("RGB", (W * scale, H * scale * 2 + 48), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((5, 2), n + " 原图", font=FONT, fill=LABEL_FG)
    d.text((5, H * scale + 26), n + " 汉化", font=FONT, fill=(140, 235, 220))
    can.paste(a.resize((W * scale, H * scale), Image.NEAREST), (0, 22))
    can.paste(b.resize((W * scale, H * scale), Image.NEAREST), (0, H * scale + 46))
    return can


def main():
    snap = before()
    out = C.DST_DIR

    # 1 四块木牌
    grid(C.TITLES and [d["name"] for d in C.TITLES], 411, 226, 2,
         "四块木牌标题 · 上原图 / 下汉化").save(out / "对照_木牌标题.png")

    # 2 三张率牌 + stand_back
    names = [d["name"] for d in C.RATES] + ["stand_back"]
    grid(names, 260, 270, 2, "鉴赏率牌与返回按钮 · 上原图 / 下汉化").save(
        out / "对照_率牌与返回.png")

    # 3 extra_mode 完整三行（2x）
    stacked("extra_mode", 2).save(out / "对照_分页按钮.png")

    # 4 四张部件图的标签区（stand_parts 裁到 710 让红色徽标一起入镜）
    parts = [
        crop_pair("stand_parts", (455, 115, 710, 310), 2),
        crop_pair("music_parts", (60, 45, 400, 195), 2),
        crop_pair("voice_parts", (0, 340, 920, 410), 1),
        crop_pair("visual_parts", (1000, 95, 1280, 141), 2),
    ]
    W = max(p.width for p in parts)
    H = sum(p.height for p in parts) + 26
    can = Image.new("RGB", (W, H), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((6, 3), "部件图标签 · 上原图 / 下汉化", font=FONT, fill=LABEL_FG)
    y = 26
    for p in parts:
        can.paste(p, (0, y))
        y += p.height
    can.save(out / "对照_部件图.png")

    # 5 第 5 批口述修订：五处改动的原图/成品放大对照
    rev = [
        crop_pair("music_parts", (300, 540, 586, 600), 3),   # NOW PLAYING
        crop_pair("stand_parts", (455, 120, 710, 310), 2),   # 六行居中
        crop_pair("stand_parts", (645, 140, 705, 182), 6),   # 徽标放大
        crop_pair("voice_parts", (0, 0, 665, 145), 2),        # 顶部左侧小格
        crop_pair("voice_parts", (880, 0, 1020, 120), 3),     # 顶部右侧小格
    ]
    W = max(p.width for p in rev)
    H = sum(p.height for p in rev) + 26
    can = Image.new("RGB", (W, H), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((6, 3), "第 5 批修订 · NOW PLAYING / 六行居中 / 徽标 / 小格 ALL·PLAY LIST",
           font=FONT, fill=LABEL_FG)
    y = 26
    for p in rev:
        can.paste(p, (0, y))
        y += p.height
    can.save(out / "对照_本次修订.png")

    # 同源校验
    after = {n: md5(C.DST_DIR / (n + ".png")) for n in C.ALL_NAMES}
    bad = [n for n in C.ALL_NAMES if snap[n] != after[n]]
    if bad:
        print("ERROR 生成对照图期间成品被改动:", bad)
        sys.exit(1)
    print("对照图 5 张已生成，13 张成品 md5 生成前后一致（同源）")
    files = sorted(f for f in os.listdir(out) if f.lower().endswith(".png"))
    print("交付目录 PNG 共 %d 张" % len(files))
    for f in files:
        print("   ", f)


if __name__ == "__main__":
    main()
