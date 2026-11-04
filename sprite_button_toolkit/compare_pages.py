# -*- coding: utf-8 -*-
"""三张新图的验收对照：1:1 真实尺寸 + 逐格放大（上原图 / 下成品）"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
import config_pages as C

BG = (24, 28, 32, 255)
OUT = C.WORK_DIR
OUT.mkdir(exist_ok=True)


def on_bg(im):
    return Image.alpha_composite(Image.new("RGBA", im.size, BG), im.convert("RGBA")).convert("RGB")


def pair(name, scale=1, crop=None):
    s = Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")
    d = Image.open(C.DST_DIR / (name + ".png")).convert("RGBA")
    a, b = on_bg(s), on_bg(d)
    if crop:
        a, b = a.crop(crop), b.crop(crop)
    w, h = a.size
    if scale != 1:
        a = a.resize((w * scale, h * scale), Image.NEAREST)
        b = b.resize((w * scale, h * scale), Image.NEAREST)
    w, h = a.size
    can = Image.new("RGB", (w, h * 2 + 10), (45, 45, 48))
    can.paste(a, (0, 0))
    can.paste(b, (0, h + 10))
    p = OUT / ("对照_%s_%dx.png" % (name, scale))
    can.save(p)
    print(" ->", p)
    return can


def grid(name, spans, row_bounds, scale, tag):
    """横向若干格 × 纵向三行状态，每格上原图下成品拼在一张图里"""
    s = Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")
    d = Image.open(C.DST_DIR / (name + ".png")).convert("RGBA")
    A, B = on_bg(s), on_bg(d)
    # 按行状态竖排，每行内部上原图 / 下成品
    strips = []
    for (ya, yb) in [(r[0], r[1]) for r in row_bounds]:
        strips.append((ya, yb))
    cw = max(b - a for a, b in spans)
    rh = max(b - a for a, b in strips)
    can = Image.new("RGB", (cw * scale * len(spans) + 8 * len(spans),
                            rh * scale * 2 * len(strips) + 10 * len(strips)), (45, 45, 48))
    dr = ImageDraw.Draw(can)
    for j, (ya, yb) in enumerate(strips):
        for i, (xa, xb) in enumerate(spans):
            ca = A.crop((xa, ya, xa + cw, ya + rh)).resize((cw * scale, rh * scale), Image.NEAREST)
            cb = B.crop((xa, ya, xa + cw, ya + rh)).resize((cw * scale, rh * scale), Image.NEAREST)
            px = i * (cw * scale + 8)
            py = j * (rh * scale * 2 + 10)
            can.paste(ca, (px, py))
            can.paste(cb, (px, py + rh * scale))
        dr.text((4, j * (rh * scale * 2 + 10) + 2), "row%d" % j, fill=(220, 220, 220))
    p = OUT / ("对照_%s_%s.png" % (name, tag))
    can.save(p)
    print(" ->", p)


if __name__ == "__main__":
    pair("title", 3)
    pair("index", 2)
    pair("button", 1)
    pair("button", 2, crop=(0, 0, 600, 126))
    # 用户最关心的三行状态，逐格放大
    grid("button", [(11, 132), (156, 279), (303, 426), (450, 573), (597, 720)],
         C.BUTTON_ROWS, 3, "前五格3x")
    grid("button", [(744, 867), (891, 1014), (1038, 1161), (1185, 1308), (1351, 1509)],
         C.BUTTON_ROWS, 3, "后五格3x")
    grid("index", C.INDEX_SPANS, C.INDEX_ROWS, 3, "逐格3x")
