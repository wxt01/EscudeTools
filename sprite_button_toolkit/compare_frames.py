# -*- coding: utf-8 -*-
"""四张框架图的 1:1 上下对照 + 单条 3 倍放大"""
from PIL import Image, ImageDraw
import config_frames as C

BG = (20, 22, 26, 255)
OUT = C.WORK_DIR
OUT.mkdir(exist_ok=True)


def on_bg(im):
    return Image.alpha_composite(Image.new("RGBA", im.size, BG), im.convert("RGBA")).convert("RGB")


def pair(name, scale=1):
    s = Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")
    d = Image.open(C.DST_DIR / (name + ".png")).convert("RGBA")
    a, b = on_bg(s), on_bg(d)
    w, h = a.size
    if scale != 1:
        a = a.resize((w * scale, h * scale), Image.LANCZOS)
        b = b.resize((w * scale, h * scale), Image.LANCZOS)
        w, h = a.size
    can = Image.new("RGB", (w, h * 2 + 8), (60, 60, 64))
    can.paste(a, (0, 0))
    can.paste(b, (0, h + 8))
    p = OUT / ("对照_%s.png" % name)
    can.save(p)
    print(" ->", p)


def zoom_rows(name, rows, scale=3):
    """若干条 (x0,x1,y0,y1) 区域，上原图 / 下成品"""
    s = Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")
    d = Image.open(C.DST_DIR / (name + ".png")).convert("RGBA")
    A, B = on_bg(s), on_bg(d)
    cw = max(x1 - x0 for x0, x1, y0, y1 in rows)
    ch = max(y1 - y0 for x0, x1, y0, y1 in rows)
    can = Image.new("RGB", (cw * scale * len(rows) + 8 * len(rows), ch * scale * 2 + 8),
                    (60, 60, 64))
    for i, (x0, x1, y0, y1) in enumerate(rows):
        a = A.crop((x0, y0, x0 + cw, y0 + ch)).resize((cw * scale, ch * scale), Image.NEAREST)
        b = B.crop((x0, y0, x0 + cw, y0 + ch)).resize((cw * scale, ch * scale), Image.NEAREST)
        px = i * (cw * scale + 8)
        can.paste(a, (px, 0))
        can.paste(b, (px, ch * scale + 8))
    p = OUT / ("对照_%s_局部3x.png" % name)
    can.save(p)
    print(" ->", p)


if __name__ == "__main__":
    for n in C.FRAMES:
        pair(n)
    zoom_rows("frame_system", [(20, 410, 0, 52), (440, 830, 0, 52), (870, 1250, 0, 52)])
    zoom_rows("frame_text", [(20, 410, 128, 178), (440, 830, 128, 178), (870, 1250, 128, 178)])
    zoom_rows("frame_manual", [(20, 420, 0, 105), (440, 840, 130, 245)])
