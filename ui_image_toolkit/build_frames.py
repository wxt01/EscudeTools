# -*- coding: utf-8 -*-
"""
四张 frame_*.png 的汉化生成器。

与设置页三张图的最大区别：这些是**透明叠加层**，深色背景是游戏另画的，
图里那片深色其实是 alpha=0。所以擦字只需把文字带清成透明，
不需要补任何背景纹理 —— 也不该补，补了反而会在游戏里露出一块补丁。

三条硬规则：
  1. 青色水彩笔触是装饰，必须逐像素保留。文字带与笔触带在 y 上不重叠，
     清除窗口止于文字底 +3px，且新图层被 allow 掩码裁在清除窗口附近。
  2. 白色日文带青色柔光，中文照做（字形外扩 + 模糊，别用 1px 描边）。
  3. 键名（Space / Back Space / Enter / Esc / Ctrl）原样写回，
     BGM / BGV 两格连清除都不做，保持原图像素。

运行：在 工具/ 目录执行 python build_frames.py
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config_frames as C


def log(*a):
    print(*a, flush=True)


def build(name, cfg):
    src = Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")
    assert src.size == cfg["size"], (name, src.size, cfg["size"])
    arr = np.array(src).astype(np.uint8)
    H, W = arr.shape[:2]
    log("%-14s %s  清除窗口 %d  文字 %d" %
        (name, src.size, len(cfg["clears"]), len(cfg["texts"])))

    # ---- 1. 逐窗口清成透明（RGB 保留，透明区逐像素无变化）
    clean = arr.copy()
    for x0, x1, y0, y1 in cfg["clears"]:
        clean[y0:y1, x0:x1, 3] = 0
    out = Image.fromarray(clean, "RGBA")

    # ---- 2. 允许区域：只在左右和下方略微外扩。
    # 上方绝不外扩 —— frame_manual 的键位行紧跟在青色笔触下面，
    # 向上扩 4px 会把笔触尾部一起改掉（自检抓到过）。
    allow = np.zeros((H, W), dtype=np.uint8)
    for x0, x1, y0, y1 in cfg["clears"]:
        allow[y0:min(H, y1 + 2), max(0, x0 - 8):min(W, x1 + 8)] = 255

    # ---- 3. 渲染：白字(带青光) + 彩色/小字
    fonts = {}
    for key, st in C.STYLES.items():
        fonts[key] = ImageFont.truetype(C.FONT, st["size"])
    core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    plain = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd, pd = ImageDraw.Draw(core), ImageDraw.Draw(plain)

    # 统一基线：每种字号算一次，避免逐条 bbox 差异造成上下浮动
    base_py = {}
    for key, f in fonts.items():
        words = "".join(t["text"] for t in cfg["texts"] if t["style"] == key)
        if words:
            bb = cd.textbbox((0, 0), words, font=f)
            base_py[key] = -(bb[1] + bb[3]) / 2.0

    for item in cfg["texts"]:
        st, f = C.STYLES[item["style"]], fonts[item["style"]]
        d = cd if item["style"] == "white" else pd
        text = item["text"]
        ws = [d.textlength(ch, font=f) for ch in text]
        tw = sum(ws) + st["gap"] * (len(text) - 1)
        sx = item["x"] - tw / 2.0 if item["align"] == "center" else item["x"]
        py = item["cy"] + base_py.get(item["style"], 0)
        for ch, cw in zip(text, ws):
            d.text((sx, py), ch, font=f, fill=st["rgb"] + (255,))
            sx += cw + st["gap"]

    # 白字实笔画加实（宋体/雅黑细笔画在 20px 下抗锯齿偏虚）
    ca_raw = np.array(core.getchannel("A")).astype(np.float32)
    ca = np.clip(ca_raw * 1.25, 0, 255).astype(np.uint8)
    core.putalpha(Image.fromarray(ca, "L"))

    # 青色外发光：字形外扩(紧光) + 大半径柔光，字核心挖空
    g = C.GLOW
    ca_f = ca.astype(np.float32) / 255.0
    ca_u8 = Image.fromarray(ca, "L")
    tight = np.array(ca_u8.filter(ImageFilter.MaxFilter(g["expand"]))
                     .filter(ImageFilter.GaussianBlur(g["tight_blur"]))).astype(np.float32) / 255.0
    soft = np.array(ca_u8.filter(ImageFilter.GaussianBlur(g["soft_blur"]))
                    ).astype(np.float32) / 255.0
    ga = (tight * g["tight_w"] + soft * g["soft_w"]) * 255.0
    ga *= (1.0 - ca_f * (1.0 - g["core_keep"]))
    glow = Image.new("RGBA", (W, H), C.GLOW_RGB + (0,))
    glow.putalpha(Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8), "L"))

    layer = Image.alpha_composite(glow, core)
    layer = Image.alpha_composite(layer, plain)
    la = np.array(layer.getchannel("A"))
    layer.putalpha(Image.fromarray(np.minimum(la, allow), "L"))
    out = Image.alpha_composite(out, layer)

    dst = C.DST_DIR / (name + ".png")
    out.save(dst)
    log("   ->", dst)
    return out


def main():
    C.WORK_DIR.mkdir(exist_ok=True)
    log("字体:", C.FONT)
    log("=" * 64)
    results = {n: build(n, c) for n, c in C.FRAMES.items()}
    log("=" * 64)
    log("四张框架图已写入", C.DST_DIR)
    return results


if __name__ == "__main__":
    main()
