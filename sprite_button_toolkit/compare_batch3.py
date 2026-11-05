# -*- coding: utf-8 -*-
"""追加任务三：五张图的 1:1 / 放大上下对照，以及关键格特写。"""
import os
from PIL import Image, ImageDraw

import config_batch3 as C

BG = (20, 24, 28, 255)


def od(im):
    return Image.alpha_composite(Image.new("RGBA", im.size, BG), im.convert("RGBA")).convert("RGB")


def pair(name, scale, crop=None, out=None):
    s = Image.open(os.path.join(C.SRC_DIR, name + ".png")).convert("RGBA")
    d = Image.open(os.path.join(C.DST_DIR, name + ".png")).convert("RGBA")
    if crop:
        s, d = s.crop(crop), d.crop(crop)
    w, h = s.size
    S = scale
    can = Image.new("RGB", (w * S, h * S * 2 + 10), (40, 40, 44))
    can.paste(od(s).resize((w * S, h * S), Image.NEAREST), (0, 0))
    can.paste(od(d).resize((w * S, h * S), Image.NEAREST), (0, h * S + 10))
    p = os.path.join(C.WORK_DIR, out or ("对照3_" + name + ".png"))
    can.save(p)
    print(p)


if __name__ == "__main__":
    pair("radio_button", 2)
    pair("check_box", 2)
    pair("popup_parts", 2, crop=(0, 0, 864, 400))
    pair("sys_quit", 4)
    pair("sys_back", 4)
    # 全图 1:1（不放大，用于确认下方 UI 元素没被动过）
    pair("popup_parts", 1, out="对照3_popup_parts_全图1x.png")
