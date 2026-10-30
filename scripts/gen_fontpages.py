#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_fontpages.py —— 把中文字形画进游戏的位图字库（gfx/font/ja_jp/<字号>/<页>.png）

映射公式来自引擎源码 misc/text.c: put_char()，LANG_JP 分支：

    c0 = lead;  c1 = trail
    if c0 >= 0xE0: c0 -= 0x40
    if c1 >= 0x80: c1 -= 1
    page = (c0 - 0x80) * 2
    if c1 < 0x9E: page -= 1; cell = c1 - 0x3F
    else:                       cell = c1 - 0x9D

    格内坐标：col = cell % 16, row = cell // 16, 格宽 = 字号

  注意：必须用这个公式，不能用"第几个合法 SJIS 字符"计数——后者会整体错位。
  第 00 页是 ASCII（cell = 字符 - 0x20），第 95 页是半角片假名。

用法：
  python gen_fontpages.py --cmap cmap.json --fontdir <output/gfx/font/ja_jp> \
                          --out <新目录> --font C:/Windows/Fonts/msyh.ttc
"""

import argparse
import json
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

COLS = 16
SS = 4  # 超采样倍数：先按 4 倍字号绘制再缩回，避免小字号直绘的笔画不均
       # （24px 直绘时青类密横部件糊死显重、亘类小部件发虚缺笔画）


def engine_pos(lead, trail):
    """SJIS 双字节 -> (页号, 格号)，完全复刻 put_char()"""
    c0 = lead - (0x40 if lead >= 0xE0 else 0)
    c1 = trail - (1 if trail >= 0x80 else 0)
    page = (c0 - 0x80) * 2
    if c1 < 0x9E:
        page -= 1
        cell = c1 - 0x3F
    else:
        cell = c1 - 0x9D
    return page, cell


def pos_of(placeholder):
    b = placeholder.encode("cp932")
    if len(b) == 1:
        if 0x21 <= b[0] <= 0x7E:
            return 0, b[0] - 0x20
        return None
    if len(b) != 2:
        return None
    page, cell = engine_pos(b[0], b[1])
    if page < 1 or page > 94 or cell < 0 or cell > 95:
        return None
    return page, cell


def gray_palette():
    pal = []
    for i in range(256):
        pal += [i, i, i]
    return pal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmap", required=True, help="中文→占位字符 的 json")
    ap.add_argument("--fontdir", required=True, help="原字库目录（含 12/ 14/ …）")
    ap.add_argument("--out", required=True, help="输出目录（复制原目录后修改）")
    ap.add_argument("--font", default=r"C:\Windows\Fonts\msyh.ttc")
    ap.add_argument("--index", type=int, default=0, help="ttc 内的字体序号")
    ap.add_argument("--sizes", default="", help="留空则自动扫描 fontdir 下所有字号目录")
    ap.add_argument("--scale", type=float, default=1.0, help="字号缩放")
    ap.add_argument("--dx", type=float, default=0.0, help="水平微调（按字号比例）")
    ap.add_argument("--dy", type=float, default=0.0, help="垂直微调（按字号比例）")
    args = ap.parse_args()

    with open(args.cmap, encoding="utf-8") as f:
        cmap = json.load(f)

    placed, missed = {}, []
    for zh, ph in cmap.items():
        pos = pos_of(ph)
        if pos is None:
            missed.append((zh, ph))
            continue
        placed[zh] = pos

    used = {}
    for zh, (p, c) in placed.items():
        used.setdefault((p, c), []).append(zh)
    clash = {k: v for k, v in used.items() if len(v) > 1}
    print(f"待画字符 {len(cmap)}，可定位 {len(placed)}，失败 {len(missed)}，撞格 {len(clash)}")
    if missed[:5]:
        print("  失败样例:", missed[:5])
    if clash:
        k = list(clash)[0]
        print(f"  撞格样例: 页{k[0]} 格{k[1]} <- {clash[k]}")

    if os.path.exists(args.out):
        shutil.rmtree(args.out)
    shutil.copytree(args.fontdir, args.out)

    if args.sizes.strip():
        sizes = [x.strip() for x in args.sizes.split(",") if x.strip()]
    else:
        sizes = sorted([d for d in os.listdir(args.fontdir)
                        if d.isdigit() and os.path.isdir(os.path.join(args.fontdir, d))], key=int)
        print("自动识别字号:", ",".join(sizes))
    total = 0
    for size in sizes:
        d = os.path.join(args.out, size)
        if not os.path.isdir(d):
            continue
        cellsz = int(size)
        try:
            fnt = ImageFont.truetype(args.font, size=max(6, int(cellsz * args.scale * SS)), index=args.index)
        except TypeError:
            fnt = ImageFont.truetype(args.font, size=max(6, int(cellsz * args.scale * SS)))
        pages = {}
        for zh, (page, cell) in placed.items():
            fn = os.path.join(d, f"{page:02d}.png")
            if not os.path.exists(fn):
                continue
            if page not in pages:
                pages[page] = Image.open(fn).convert("L")
            img = pages[page]
            col, row = cell % COLS, cell // COLS
            # 超采样：按 SS 倍字号在大画布上画，缩回后再按墨迹居中贴进格子。
            # 直接小字号直绘会笔画不均（密横糊死、小部件发虚）；
            # 不做墨迹居中则雅黑 CJK 墨迹比 em box 高，底横被裁（"姐"变"姉"样）。
            scratch = Image.new("L", (cellsz * SS * 3, cellsz * SS * 3), 0)
            ds = ImageDraw.Draw(scratch)
            ds.text((cellsz * SS * 1.5, cellsz * SS * 1.5), zh, font=fnt, fill=255, anchor="mm")
            bb = scratch.getbbox()
            tile = Image.new("L", (cellsz, cellsz), 0)
            if bb:
                ink = scratch.crop(bb)
                ink = ink.resize((max(1, round(ink.width / SS)),
                                  max(1, round(ink.height / SS))), Image.LANCZOS)
                if ink.width > cellsz or ink.height > cellsz:
                    r = min(cellsz / ink.width, cellsz / ink.height)
                    ink = ink.resize((max(1, round(ink.width * r)),
                                      max(1, round(ink.height * r))), Image.LANCZOS)
                px = round(cellsz / 2 - ink.width / 2 + cellsz * args.dx)
                py = round(cellsz / 2 - ink.height / 2 + cellsz * args.dy)
                tile.paste(ink, (px, py))
            img.paste(tile, (col * cellsz, row * cellsz))
            total += 1
        for page, img in pages.items():
            out = img.convert("P")
            out.putpalette(gray_palette())
            out.save(os.path.join(d, f"{page:02d}.png"))
    print(f"完成：写入 {total} 个字形，输出到 {args.out}")


if __name__ == "__main__":
    main()
