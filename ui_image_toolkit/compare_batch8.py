# -*- coding: utf-8 -*-
"""第一组对照图 + 成品 md5 同源校验。"""
import hashlib
import os
import sys
from PIL import Image, ImageDraw, ImageFont

import config_batch8 as C

FONT = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
LABEL = (255, 220, 120)
BG = (24, 26, 30, 255)


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:12]


def comp(d, n):
    im = Image.open(d / (n + ".png")).convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", im.size, BG), im).convert("RGB")


def stacked(n, scale=3):
    a, b = comp(C.SRC_DIR, n), comp(C.DST_DIR, n)
    W, H = a.size[0] * scale, a.size[1] * scale
    can = Image.new("RGB", (W, H * 2 + 30), (50, 50, 55))
    d = ImageDraw.Draw(can)
    d.text((5, 2), "%s  上原图 / 下汉化（%dx）" % (n, scale), font=FONT, fill=LABEL)
    can.paste(a.resize((W, H), Image.NEAREST), (0, 18))
    can.paste(b.resize((W, H), Image.NEAREST), (0, H + 30))
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
    snap = {n: md5(C.DST_DIR / (n + ".png")) for n in C.ALL_NAMES}
    out = C.DST_DIR
    made = []

    vstack([stacked(n, 3) for n in C.TITLES and
            [t["name"] for t in C.TITLES]],
           "第 1 组 · 红底花卉纹金字标题（上原图 / 下汉化）").save(
        out / "对照_戦巫_金字标题.png")
    made.append("对照_戦巫_金字标题.png")

    vstack([stacked(n, 2) for n in ["common_sys_quit", "common_sys_back"]],
           "第 1 组 · 透明底三态发光按钮（上原图 / 下汉化）").save(
        out / "对照_戦巫_系统按钮.png")
    made.append("对照_戦巫_系统按钮.png")

    vstack([stacked(cfg["name"], 3 if cfg["size"][0] < 400 else 1)
            for cfg in C.LABELS],
           "第 2 组 · 浅金胶带 / 金条深字标签（上原图 / 下汉化）").save(
        out / "对照_戦巫_金条标签.png")
    made.append("对照_戦巫_金条标签.png")

    vstack([stacked(cfg["name"], 1 if cfg["size"][0] > 1200 else 2)
            for cfg in C.GRIDS],
           "第 3 组 · 多状态按钮网格（上原图 / 下汉化）").save(
        out / "对照_戦巫_按钮网格.png")
    made.append("对照_戦巫_按钮网格.png")

    # 第四~七组：按结构分组，每组一张纵向对照
    groups = [
        ("标题菜单与帮助",
         ["title_menu_text", "tutorial_help_p", "extra_visual_parts"], 1),
        ("右键菜单与存档页",
         ["common_popup_parts", "file_index", "file_save_parts",
          "file_load_parts", "common_confirm_parts"], 1),
        ("框架图设置项",
         ["config_frame_sound", "config_frame_system",
          "config_frame_manual", "config_frame_text"], 1),
        ("设置项长清单", ["config_check_box"], 2),
        ("鉴赏页与 MUTE",
         ["extra_music_parts", "extra_voice_parts", "config_parts"], 1),
        # 2026-11-16 追加：人名已定稿 / 发光菱形按普通发光字重做
        ("配音人名", ["config_frame_voice"], 1),
        ("发光菱形索引", ["config_index"], 2),
    ]
    for tag, names, scale in groups:
        fn = "对照_戦巫_%s.png" % tag
        vstack([stacked(n, scale) for n in names],
               "第 4~7 组 · %s（上原图 / 下汉化）" % tag).save(out / fn)
        made.append(fn)

    after = {n: md5(C.DST_DIR / (n + ".png")) for n in C.ALL_NAMES}
    bad = [n for n in C.ALL_NAMES if snap[n] != after[n]]
    if bad:
        print("ERROR 生成对照图期间成品被改动:", bad)
        sys.exit(1)
    print("对照图 %d 张；%d 张成品 md5 前后同源" %
          (len(made), len(C.ALL_NAMES)))
    for f in made:
        print("   %-34s %8d B" % (f, (out / f).stat().st_size))
    files = sorted(f for f in os.listdir(out) if f.lower().endswith(".png"))
    print("待交付目录 PNG 共 %d 张（%d 成品 + %d 对照）" %
          (len(files), len(C.ALL_NAMES), len(files) - len(C.ALL_NAMES)))


if __name__ == "__main__":
    main()
