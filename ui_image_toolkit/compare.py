# -*- coding: utf-8 -*-
"""
对照图生成器：改字类工作必须同时看「真实 1:1」和「高倍放大」，只看一种会误判。

经验：
  * 8~16 倍放大能看出字形残影、涂抹块、矩形边界、辉光是否糊成板；
  * 但放大会放大「字体太粗/太亮」的错觉，最终验收一定回到 1:1。
  * 有 clean_base.png（清除后的无字底图）时，三栏对照最能定位问题出在
    「清除」还是「重画」：底图脏 = 清除没做好；底图干净但成品怪 = 渲染参数问题。

用法（在「工具」目录下）：
  python compare.py                       # 用 config 的默认路径与格子
  python compare.py --pick 0,2,4 --scale 8
  python compare.py --base _输出/clean_base.png --scale 16
  python compare.py --src 别的原图.png --dst 别的成品.png
"""
import os
import argparse
import numpy as np
from PIL import Image
import config as C


def on_dark(im):
    return Image.alpha_composite(Image.new("RGBA", im.size, C.BG_PREVIEW), im).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=C.SRC)
    ap.add_argument("--dst", default=C.DST)
    ap.add_argument("--base", default=os.path.join(C.WORK, "clean_base.png"),
                    help="清除后的无字底图；不需要三栏时传 none")
    ap.add_argument("--out", default=C.WORK)
    ap.add_argument("--pick", default="0,2,4", help="要放大的格序号，逗号分隔")
    ap.add_argument("--scale", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    src = Image.open(args.src).convert("RGBA")
    dst = Image.open(args.dst).convert("RGBA")
    W, H = src.size
    pick = [int(v) for v in args.pick.split(",") if v.strip() != ""]

    # 1:1 真实尺寸上下对照
    can = Image.new("RGB", (W, H * 2 + 10), C.BG_PREVIEW[:3])
    can.paste(on_dark(src), (0, 0))
    can.paste(on_dark(dst), (0, H + 10))
    p1 = os.path.join(args.out, "对照_1比1.png")
    can.save(p1)
    print("1:1 对照:", p1)

    # 指定格的高倍放大：每个格子一组，竖向上原图 / 下成品（可选中间无字底图）
    base = None
    if args.base.lower() != "none" and os.path.exists(args.base):
        base = Image.open(args.base).convert("RGBA")
    imgs = [src] + ([base] if base else []) + [dst]
    cw = max(C.COLS[i][1] - C.COLS[i][0] for i in pick) + 2 * C.CLEAR_PAD_X
    S = args.scale
    panel_w, panel_h = cw * S, H * S
    canvas = Image.new("RGB", (panel_w * len(pick) + 12 * len(pick),
                               panel_h * len(imgs) + 12 * len(imgs)), (40, 40, 44))
    for k, ci in enumerate(pick):
        xa = C.COLS[ci][0] - C.CLEAR_PAD_X
        xb = xa + cw
        for j, im in enumerate(imgs):
            tile = on_dark(im.crop((xa, 0, xb, H))).resize((panel_w, panel_h), Image.NEAREST)
            canvas.paste(tile, (k * (panel_w + 12), j * (panel_h + 12)))
    p2 = os.path.join(args.out, "对照_重点格放大.png")
    canvas.save(p2)
    print("放大对照:", p2, " 栏顺序:", "原图 / " + ("无字底图 / " if base else "") + "成品")

    # 量化：白色实像素、青光像素、亮像素质心，便于前后比较而不是靠感觉
    A = np.array(dst).astype(int)
    B = np.array(src).astype(int)
    print("\n== 小字带量化（用于对比，不是及格线）==")
    for r in range(C.N_ROWS):
        y0, y1 = r * C.ROW_H + 35, r * C.ROW_H + 54
        for name, arr in (("原图", B), ("成品", A)):
            reg = arr[y0:y1, 60:182]
            white = ((reg[:, :, 0] > 200) & (reg[:, :, 1] > 200) &
                     (reg[:, :, 2] > 200) & (reg[:, :, 3] > 150))
            cyan = ((reg[:, :, 0] < 110) & (reg[:, :, 1] > 130) & (reg[:, :, 3] > 70))
            yy, _ = np.where(white)
            cy = round(float(yy.mean()) + 35, 2) if len(yy) else None
            print(f"  行{r} {name}: 白字 {int(white.sum()):4d}  青光 {int(cyan.sum()):5d}  白字质心y {cy}")


if __name__ == "__main__":
    main()
