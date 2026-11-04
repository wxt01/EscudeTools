# -*- coding: utf-8 -*-
"""
雪碧图结构诊断：接手「多状态按钮雪碧图改字」任务时的第一步。

它专门回答一个最容易看错、也最致命的问题：
    小字背后到底有没有「底板」？
  - 若格间列 / 空白格在文字带高度上 alpha≈0
      → 没有底板，字（白字+描边+外发光）直接悬在透明背景上。
        此时必须「整块清除再重画」，绝不能把旧字笔画涂成背景色。
  - 若这些位置 alpha 明显 > 0 且横向连续成带
      → 确实有底板，只需在底板范围内替换文字，改动可以小得多。

用法（在「工具」目录下）：
  python inspect_sprite.py
  python inspect_sprite.py --cols 65:176,345:415 --band 31:60 --rows 4
  python inspect_sprite.py 别的图.png --rows 3 --out _输出/诊断

不给 --cols 时只做全图剖面（适合刚拿到图、还没定位格子）。
输出：控制台 + 一个报告 txt + alpha / 深底 / 白底 / 逐行放大 PNG。
"""
import os
import argparse
import numpy as np
from PIL import Image

try:
    import config as C
except ImportError:
    C = None


def parse_cols(s):
    if not s:
        return None
    out = []
    for part in s.split(","):
        a, b = part.strip().split(":")
        out.append((int(a), int(b)))
    return out


def composite(im, bg):
    return Image.alpha_composite(Image.new("RGBA", im.size, bg), im).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", default=C.SRC if C else None)
    ap.add_argument("--rows", type=int, default=C.N_ROWS if C else 4)
    ap.add_argument("--cols", default=None, help="格 x 范围，形如 65:176,345:415")
    ap.add_argument("--band", default="31:60", help="行内小字带 y 范围，形如 31:60")
    ap.add_argument("--out", default=C.WORK if C else "_输出")
    args = ap.parse_args()

    if not args.image:
        ap.error("请给出图片路径")
    src = Image.open(args.image).convert("RGBA")
    a = np.array(src).astype(int)
    W, H = src.size
    rh = H // args.rows
    cols = parse_cols(args.cols)
    bt, bb = (int(v) for v in args.band.split(":"))
    os.makedirs(args.out, exist_ok=True)
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    say("== 基本信息 ==")
    say(f"文件: {os.path.abspath(args.image)}")
    say(f"尺寸 {W}x{H}  模式 {src.mode}  状态行数 {args.rows}  推定行高 {rh}")

    # ---- 可视化
    Image.fromarray(a[:, :, 3].astype(np.uint8), "L").save(
        os.path.join(args.out, "诊断_alpha通道.png"))
    composite(src, (18, 22, 26, 255)).save(os.path.join(args.out, "诊断_深底.png"))
    composite(src, (245, 245, 245, 255)).save(os.path.join(args.out, "诊断_白底.png"))
    row_canvas = Image.new("RGB", (W * 2, rh * 2 * args.rows), (40, 40, 44))
    for r in range(args.rows):
        row_canvas.paste(composite(src.crop((0, r * rh, W, (r + 1) * rh)),
                                   (18, 22, 26, 255)).resize((W * 2, rh * 2), Image.LANCZOS),
                         (0, r * rh * 2))
    row_canvas.save(os.path.join(args.out, "诊断_逐行放大.png"))

    say("")
    say("== 每行整体 ==")
    for r in range(args.rows):
        sub = a[r * rh:(r + 1) * rh]
        nz = sub[:, :, 3] > 0
        white = ((sub[:, :, 0] > 230) & (sub[:, :, 1] > 230) &
                 (sub[:, :, 2] > 230) & (sub[:, :, 3] > 200)).sum()
        say(f"行{r}: 非透明 {nz.sum():6d}  alpha中位(非透明) "
            f"{int(np.median(sub[:, :, 3][nz])) if nz.any() else 0:3d}  白色实像素 {white:5d}")

    say("")
    say("== y 方向 alpha 剖面（每行 rel y，取全图中位数）==")
    say("  用来找文字带：小字会让这一段 alpha 明显抬高；大字下缘辉光会缓慢衰减。")
    for rel in range(max(0, bt - 8), min(rh, bb + 4), 2):
        vals = [int(np.median(a[r * rh + rel, :, 3])) for r in range(args.rows)]
        say(f"  rel {rel:3d}: {vals}")

    if not cols:
        say("")
        say("未给 --cols，跳过逐格统计。可用列投影找连续段：")
        band = a[bt:bb] if args.rows == 1 else a[rh + bt:rh + bb]
        proj = (band[:, :, 3] > 0).sum(axis=0)
        segs, start = [], None
        for x in range(W):
            if proj[x] > 0 and start is None:
                start = x
            elif proj[x] == 0 and start is not None:
                if x - start > 4:
                    segs.append((start, x - 1))
                start = None
        say("  非透明连续段: " + str(segs[:40]))
    else:
        say("")
        say("== 逐格（每格在文字带内的统计）==")
        zone = np.zeros(W, bool)
        for x0, x1 in cols:
            zone[max(0, x0 - C.CLEAR_PAD_X if C else 14):min(W, x1 + 15)] = True
        gap_x = np.where(~zone)[0]
        for r in range(args.rows):
            say(f"-- 行{r}")
            for ci, (x0, x1) in enumerate(cols):
                reg = a[r * rh + bt:r * rh + bb, x0:x1]
                nz = (reg[:, :, 3] > 0).sum()
                wh = ((reg[:, :, 0] > 230) & (reg[:, :, 1] > 230) &
                      (reg[:, :, 2] > 230) & (reg[:, :, 3] > 200)).sum()
                cy = ((reg[:, :, 0] < 110) & (reg[:, :, 1] > 130) &
                      (reg[:, :, 2] > 110) & (reg[:, :, 3] > 70)).sum()
                tag = "  <== 疑似空白格" if nz < 30 else ""
                say(f"   格{ci:2d} x{x0:4d}-{x1:4d}: 非透明 {nz:5d} 白字 {wh:4d} 青光 {cy:5d}{tag}")

        say("")
        say("== 底板判据（最重要）==")
        for r in range(args.rows):
            if len(gap_x):
                g = a[r * rh + bt:r * rh + min(bb, rh), gap_x]
                say(f"  行{r} 格间列 alpha: 中位 {np.median(g[:, :, 3]):.0f} "
                    f"最大 {g[:, :, 3].max()} 均值 {g[:, :, 3].mean():.1f}")
            for ci, (x0, x1) in enumerate(cols):
                reg = a[r * rh + bt:r * rh + min(bb, rh), x0:x1]
                if (reg[:, :, 3] > 0).sum() < 30:
                    say(f"  行{r} 空白格{ci} alpha: 最大 {reg[:, :, 3].max()}")
        say("  解读：格间列 alpha≈0 且空白格 alpha=0 → 没有底板，字和它的辉光直接悬空；")
        say("        此时把旧字笔画涂成某个不透明颜色，等于凭空造一块亮牌，笔画越密越刺眼。")
        say("        正确做法是整块清除（含辉光）→ 用真实背景重建 → 重新渲染文字。")

    report = os.path.join(args.out, "诊断报告.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n报告:", report)


if __name__ == "__main__":
    main()
