# -*- coding: utf-8 -*-
"""
追加任务三生成脚本：radio_button / check_box / popup_parts / sys_quit / sys_back

这批图统一是「透明背景 + 文字(+图标/辉光)」，所以工艺比有底板的图简单：
  1. 把每格文字带整块清成 alpha=0（背景本来就透明，不需要补纹理）
  2. 在同样的位置重画中文，样式从原图逐列/逐行实测
  3. 图标、箭头、下方所有 UI 元素不进入清除区，逐像素保留

三种渲染模型：
  * 纯白衬线字      —— radio/check（三列复用同一字形）
  * 细斜体三层字    —— popup：暖白柔光 / 半透明暖白字身 / 1px 细色描边，
                        逐字基线递升 + 整层斜切复现原图倾斜
  * 白字+青色外发光 —— sys（三行 alpha 相同，只换辉光色，中心按原图墨迹对齐）
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config_batch3 as C


def log(*a):
    print(*a, flush=True)


def dilate(mask, size):
    return np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.MaxFilter(size))) > 0


def shear(arr, k, cy):
    """整体倾斜：顶部向右、底部向左（模拟原图拉丁斜体）。arr 为 RGBA uint8。"""
    out = np.zeros_like(arr)
    H, W = arr.shape[:2]
    for y in range(H):
        s = int(round(-k * (y - cy)))
        if s > 0:
            out[y, s:] = arr[y, :W - s]
        elif s < 0:
            out[y, :W + s] = arr[y, -s:]
        else:
            out[y] = arr[y]
    return out


def clear(arr, boxes):
    """把文字矩形清成透明。背景本来就是 alpha=0，所以不用补底。"""
    n = 0
    for x0, y0, x1, y1 in boxes:
        reg = arr[y0:y1, x0:x1]
        n += int((reg[:, :, 3] > 0).sum())
        reg[:] = 0
    return n


def baseline(font, chars):
    """统一基线：用全部字符的 bbox 并集算一次，避免逐词 bbox 差异造成上下浮动。"""
    d = ImageDraw.Draw(Image.new("L", (8, 8), 0))
    bb = d.textbbox((0, 0), chars, font=font)
    return -(bb[1] + bb[3]) / 2.0, bb


def text_alpha(size, word, font, x, cy, gap, weight=1.0, rise=0.0):
    """渲染纯字形 alpha，逐字排布（可加字距、逐字基线递升）。

    rise>0 时后面的字逐个抬高，用来复现原图「整行左下→右上」的倾斜排列；
    它和整层斜切是两件事：前者是行基线，后者是字形本身斜体。
    """
    layer = Image.new("L", size, 0)
    d = ImageDraw.Draw(layer)
    py, _ = None, None
    by, _bb = baseline(font, word)
    py = cy + by
    for i, ch in enumerate(word):
        d.text((x, py - rise * i), ch, font=font, fill=255)
        x += d.textlength(ch, font=font) + gap
    a = np.array(layer).astype(np.float32)
    if weight != 1.0:
        a = np.clip(a * weight, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "L")


def composite(base, patch, box):
    base.alpha_composite(patch, box)


def make_white_patch(pw, ph, word, font, cy, fill, gap, weight=1.0):
    ca = text_alpha((pw, ph), word, font, 0, cy, gap, weight)
    p = Image.new("RGBA", (pw, ph), tuple(fill) + (0,))
    p.putalpha(ca)
    return p


def make_styled_patch(pw, ph, word, font, cy, st, cfg, pad):
    """popup 用三层，从外到内：暖白柔光 -> 半透明字身 -> 1px 细色描边。

    层序是从原图实测 alpha 反推出来的，别凭「字应该是实心的」直觉画：
      描边   alpha>200   n=289  最实，颜色随状态变（深褐 / 红 / 橙红）
      字身   120~200     n=428  半透明暖白，不是纯白实心块
      柔光   30~120      n=675  暖白，占面积最大
    旧版把字身画成 255 实心（核心 901 像素）、柔光几乎没有，于是又粗又硬、
    红色被挤成一条边，红白观感整个反过来。最后整层斜切做斜体感。
    """
    A = np.array(text_alpha((pw, ph), word, font, pad, cy,
                            cfg["char_gap"], 1.0, cfg["rise"])).astype(np.float32)
    core = A / 255.0

    # 柔光：字形模糊后挖掉字核心，只留贴着笔画的一圈
    blur = np.array(Image.fromarray(A.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(cfg["glow_blur"]))).astype(np.float32)
    ga = blur * st["glow"] * cfg["glow_gain"] * st["alpha"] * (1.0 - core * 0.88)

    # 字身：半透明。禁用态由 st["alpha"] 再压一档；常态可单列提亮
    ba = A * st.get("body", cfg["body_gain"]) * st["alpha"]

    # 描边：只在字形外 1px，细而实；字内减掉，抗锯齿边缘留自然过渡
    if st["edge"]:
        ex = dilate(A > 60, 3).astype(np.float32) * 255
        ea = np.clip(ex - A * 1.6, 0, 255) * st["alpha"] * cfg["edge_alpha"]
    else:
        ea = np.zeros_like(A)

    def layer(rgb, alpha):
        im = Image.new("RGBA", (pw, ph), tuple(rgb) + (0,))
        im.putalpha(Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), "L"))
        return im

    out = layer(cfg["glow_rgb"], ga)
    out = Image.alpha_composite(out, layer(st["fill"], ba))
    if st["edge"]:
        out = Image.alpha_composite(out, layer(st["edge"], ea))

    k = cfg["shear"]
    if k:
        out = Image.fromarray(shear(np.array(out), k, cy), "RGBA")
    return out


def make_glow_patch(pw, ph, word, font, cy, glow_rgb, cfg, gap, tx=0,
                    weight=None):
    """sys 用：青色外发光 + 纯白字核心。三行只换 glow_rgb。"""
    if weight is None:
        weight = cfg["core_weight"]
    ca = np.array(text_alpha((pw, ph), word, font, tx, cy, gap, weight)).astype(np.float32)
    # 直接对字形做小半径模糊；不做 MaxFilter 外扩，否则汉字之间会被填满成青板
    ga = np.array(Image.fromarray(np.clip(ca, 0, 255).astype(np.uint8))
                  .filter(ImageFilter.GaussianBlur(cfg["glow_blur"]))).astype(np.float32)
    ga = ga * cfg["glow_gain"] * (1.0 - np.clip(ca / 255.0, 0, 1) * 0.85)

    g = Image.new("RGBA", (pw, ph), tuple(glow_rgb) + (0,))
    g.putalpha(Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8), "L"))
    t = Image.new("RGBA", (pw, ph), tuple(cfg["white"]) + (0,))
    t.putalpha(Image.fromarray(np.clip(ca, 0, 255).astype(np.uint8), "L"))
    return Image.alpha_composite(g, t)


def save(name, arr):
    p = os.path.join(C.DST_DIR, name + ".png")
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(p)
    log("  ->", p)


# ================================================================ radio / check
def build_simple(cfg):
    name = cfg["name"]
    W, H = cfg["size"]
    src = np.array(Image.open(os.path.join(C.SRC_DIR, name + ".png")).convert("RGBA"))
    assert src.shape[:2] == (H, W), (name, src.shape)
    out = src.copy()

    boxes = []
    for col in cfg["cols"]:
        for y0, y1 in cfg["rows"]:
            boxes.append((col + cfg["clear_x0"], y0, col + cfg["col_w"], y1))
    n = clear(out, boxes)
    log("%s: 清除 %d 个旧字像素" % (name, n))

    canvas = Image.fromarray(out, "RGBA")
    font = ImageFont.truetype(cfg["font"], cfg["font_size"])
    for col in cfg["cols"]:
        for (y0, y1), word in zip(cfg["rows"], cfg["words"]):
            cy = (y0 + y1) / 2.0
            pw = cfg["col_w"] - cfg["text_x"]   # 贴到 text_x，右沿正好落在列边界，不溢出到下一列图标
            ph = y1 - y0
            p = make_white_patch(pw, ph, word, font, cy - y0,
                                 cfg["text_rgb"], cfg["char_gap"], cfg["weight"])
            composite(canvas, p, (col + cfg["text_x"], y0))
    res = np.array(canvas)
    np.save(os.path.join(C.WORK_DIR, name + "_cleared.npy"), out)
    save(name, res)
    return res


# ================================================================ popup_parts
def build_popup():
    cfg = C.POPUP
    W, H = cfg["size"]
    src = np.array(Image.open(os.path.join(C.SRC_DIR, "popup_parts.png")).convert("RGBA"))
    assert src.shape[:2] == (H, W)
    out = src.copy()

    boxes = []
    for ci, col in enumerate(cfg["cols"]):
        for y0, y1 in cfg["rows"]:
            boxes.append((cfg["clear_x0"][ci], y0, col + cfg["col_w"], y1))
    n = clear(out, boxes)
    log("popup_parts: 清除 %d 个旧字像素（箭头不在清除区内）" % n)

    canvas = Image.fromarray(out, "RGBA")
    font = ImageFont.truetype(cfg["font"], cfg["font_size"])
    for ci, col in enumerate(cfg["cols"]):
        st = cfg["styles"][ci]
        for (y0, y1), word in zip(cfg["rows"], cfg["words"]):
            # patch 左界严格等于清除区左界：柔光/斜切怎么扩散都不会漏到区外，
            # 文字起点用 text_x-clear_x0 保证绝对位置不变。
            x0 = cfg["clear_x0"][ci]
            pad = cfg["text_x"][ci] - x0
            pw = col + cfg["col_w"] - x0
            ph = y1 - y0
            cy = (y0 + y1) / 2.0 - y0
            p = make_styled_patch(pw, ph, word, font, cy, st, cfg, pad)
            composite(canvas, p, (x0, y0))
    res = np.array(canvas)
    save("popup_parts", res)
    return res


# ================================================================ sys_quit / sys_back
def build_sys(cfg):
    name = cfg["name"]
    W, H = cfg["size"]
    src = np.array(Image.open(os.path.join(C.SRC_DIR, name + ".png")).convert("RGBA"))
    assert src.shape[:2] == (H, W)
    out = src.copy()
    s = C.SYS

    boxes = []
    for y0, y1 in s["rows"]:
        for x0, x1 in cfg["spans"]:
            boxes.append((x0, y0, x1, y1))
    n = clear(out, boxes)
    log("%s: 清除 %d 个旧字/辉光像素" % (name, n))

    canvas = Image.fromarray(out, "RGBA")
    font = ImageFont.truetype(s["font"], s["font_size"])
    for r, (y0, y1) in enumerate(s["rows"]):
        ph = y1 - y0
        # ★ 整行一个图层：辉光按整行生成，光可以自然跨过词间空隙。
        # 按词格分别裁剪会把光切断在格边界，三行会退化成纯白字。
        row = Image.new("L", (W, ph), 0)
        rd = ImageDraw.Draw(row)
        by, _ = baseline(font, "".join(cfg["words"]))
        py = ph / 2.0 + by
        # ★ 对齐基准是原图逐格量出来的「墨迹中心」，不是词格几何中心。
        #   按格居中会让中文整体偏左 3~5px（用户明确指出）。
        for word, center in zip(cfg["words"], cfg["centers"]):
            tw = sum(rd.textlength(c, font=font) for c in word) + \
                 s["char_gap"] * (len(word) - 1)
            x = center - tw / 2.0
            for ch in word:
                rd.text((x, py), ch, font=font, fill=255)
                x += rd.textlength(ch, font=font) + s["char_gap"]
        ca = np.clip(np.array(row).astype(np.float32) * s["core_weight"], 0, 255)
        ga = np.array(Image.fromarray(ca.astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(s["glow_blur"]))).astype(np.float32)
        ga = ga * s["glow_gain"] * (1.0 - np.clip(ca / 255.0, 0, 1) * 0.85)

        g = Image.new("RGBA", (W, ph), tuple(s["glow_rgb"][r]) + (0,))
        g.putalpha(Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8), "L"))
        t = Image.new("RGBA", (W, ph), tuple(s["white"]) + (0,))
        t.putalpha(Image.fromarray(ca.astype(np.uint8), "L"))
        composite(canvas, Image.alpha_composite(g, t), (0, y0))
    res = np.array(canvas)
    save(name, res)
    return res


if __name__ == "__main__":
    log("字体: 衬线=%s  黑体=%s" % (C.SERIF, C.SANS))
    build_simple(C.RADIO)
    build_simple(C.CHECK)
    build_popup()
    build_sys(C.SYS_QUIT)
    build_sys(C.SYS_BACK)
    log("五张成品生成完毕")
