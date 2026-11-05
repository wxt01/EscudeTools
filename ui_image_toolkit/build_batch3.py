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
                        整层一次性旋转复现原图「整体斜过来」（不用逐字抬高）
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


def rotate_whole(im, angle, pad=14):
    """【已弃用】整层 RGBA 旋转：会串色，改用 rotate_alpha 分层旋转（11.11）。

    整层一次性旋转 —— 所有字作为一个整体斜过来，字内横竖笔画也跟着斜。

    和「逐字抬高 / 逐行平移斜切」的区别：后者每个字本身仍是正立的，
    只是排成阶梯，用户一眼就能看出「假斜」。旋转是在带留白的大画布上做，
    再裁回原 patch，字角和柔光都不会被硬裁。
    """
    # ⚠️ PIL 的 rotate 对 RGBA 是逐通道独立插值、不做预乘：透明区 RGB=0
    #    会混进边缘，合成到深底后每个词后面出现一块暗矩形、柔光发灰。
    #    所以先预乘 alpha（透明区 RGB 归零）→ 旋转 → 反预乘还原颜色。
    a = np.array(im).astype(np.float32)
    al = a[:, :, 3:4] / 255.0
    a[:, :, :3] *= al
    w, h = im.size
    big = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.float32)
    big[pad:pad + h, pad:pad + w] = a
    r = np.array(Image.fromarray(np.clip(big, 0, 255).astype(np.uint8), "RGBA")
                 .rotate(angle, resample=Image.BICUBIC, expand=False)).astype(np.float32)
    out = r[pad:pad + h, pad:pad + w]
    al2 = out[:, :, 3:4] / 255.0
    out[:, :, :3] = np.clip(
        np.where(al2 > 0.002, out[:, :, :3] / np.maximum(al2, 0.002), 0), 0, 255)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def rotate_alpha(layer, angle, pad=14):
    """只旋转 alpha 灰度层，颜色完全不参与插值。

    ⚠️ 整层 RGBA 旋转（哪怕预乘/反预乘）仍有两处硬伤：
      1. BICUBIC 对各通道独立插值，透明区与半透明区交界会串色，暖白字身
         被深褐描边/透明黑染成灰褐色，1:1 下像「字被一层灰板盖住」；
      2. 反预乘在低 alpha 处放大插值噪声，笔画周围出现红/绿杂点。
    正解是把三层（柔光/字身/描边）各自的 alpha 单独旋转，再用**纯色**
    重建并合成 —— 颜色永远干净，几何仍是整层一次旋转，字本身照样斜。
    """
    w, h = layer.size
    big = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    big.paste(layer, (pad, pad))
    r = big.rotate(angle, resample=Image.BICUBIC, expand=False)
    return r.crop((pad, pad, pad + w, pad + h))


def compose_layers(alphas, colors, size):
    """用纯色 + 各自 alpha 重建三层，从外到内合成。"""
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for a, rgb in zip(alphas, colors):
        if a is None or rgb is None:
            continue
        lay = Image.new("RGBA", size, tuple(rgb) + (0,))
        lay.putalpha(a)
        out = Image.alpha_composite(out, lay)
    return out


def align_patch(im, target_x, target_cy=None):
    """旋转后补正墨迹左沿（九行严格对齐原图 +52）和垂直重心（防整行下移被裁底）。"""
    arr0 = np.array(im)
    a = arr0[:, :, 3]
    cols = np.nonzero((a > 50).any(axis=0))[0]
    dx = int(round(target_x - cols.min())) if len(cols) else 0
    dy = 0
    if target_cy is not None:
        wy = a.astype(np.float32).sum(axis=1)
        cy = float((np.arange(len(wy)) * wy).sum() / max(wy.sum(), 1))
        dy = int(round(target_cy - cy))
    if dx == 0 and dy == 0:
        return im
    h, w = arr0.shape[:2]
    out = np.zeros_like(arr0)
    xd0, xd1 = max(0, dx), min(w, w + dx)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    yd0, yd1 = max(0, dy), min(h, h + dy)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    out[yd0:yd1, xd0:xd1] = arr0[ys0:ys1, xs0:xs1]
    return Image.fromarray(out, "RGBA")


def make_white_patch(pw, ph, word, font, cy, fill, gap, weight=1.0):
    ca = text_alpha((pw, ph), word, font, 0, cy, gap, weight)
    p = Image.new("RGBA", (pw, ph), tuple(fill) + (0,))
    p.putalpha(ca)
    return p


def feather_edges(im, f=3, fx=0):
    """边界羽化：柔光被 patch 边界硬裁出的直线，在 1:1 下就是矩形光板。

    fx 专门处理**左右**边界 —— 整层旋转后第一个字左侧的光晕会顶到 patch
    左界，被裁成一条垂直硬边，看起来就像首字被一块板挡住了一部分。
    fx 必须小于墨迹左沿到 patch 左界的距离，否则会削到首字笔画。
    """
    a = np.array(im)
    h, w = a.shape[:2]
    if f > 0:
        win = np.ones(h, np.float32)
        r = np.linspace(0, 1, f, endpoint=False, dtype=np.float32)
        win[:f] = r
        win[-f:] = r[::-1]
        a[:, :, 3] = np.clip(a[:, :, 3].astype(np.float32) * win[:, None],
                             0, 255).astype(np.uint8)
    if fx > 0:
        win = np.ones(w, np.float32)
        r = np.linspace(0, 1, fx, endpoint=False, dtype=np.float32)
        win[:fx] = r
        win[-fx:] = r[::-1]
        a[:, :, 3] = np.clip(a[:, :, 3].astype(np.float32) * win[None, :],
                             0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def make_styled_patch(pw, ph, word, font, cy, st, cfg, pad=0, dim=1.0,
                      gap=None):
    """popup 用三层，从外到内：暖白柔光 -> 半透明字身 -> 1px 细色描边。

    层序是从原图实测 alpha 反推出来的，别凭「字应该是实心的」直觉画：
      描边   alpha>200   n=289  最实，颜色随状态变（深褐 / 红 / 橙红）
      字身   120~200     n=428  半透明暖白，不是纯白实心块
      柔光   30~120      n=675  暖白，占面积最大
    旧版把字身画成 255 实心（核心 901 像素）、柔光几乎没有，于是又粗又硬、
    红色被挤成一条边，红白观感整个反过来。最后整层斜切做斜体感。
    """
    # 文字先在 patch 内右移 render_margin 再整体旋转；旋转完由 align_patch
    # 把墨迹左沿补正回 pad（绝对 +52）。这样首字左下角的旋转插值与柔光尾巴
    # 都有落脚空间，不会被 patch 左界垂直削掉。
    A = np.array(text_alpha((pw, ph), word, font,
                            pad + cfg.get("render_margin", 0), cy,
                            cfg["char_gap"] if gap is None else gap,
                            1.0, cfg["rise"])).astype(np.float32)
    core = A / 255.0

    # 柔光：字形小半径模糊后挖掉字核心，只留贴笔画的一圈。
    # 半径必须 < 行高余量：36px 行高里字高 23px，上下各只有 6.5px，
    # 5px 光晕 + 旋转增量会被上下边界硬裁成直线，1:1 下就是一块矩形光板。
    # 也别用「外扩环 * gain」凑面积：环会饱和成不透明片，比光板更糟。
    near = np.array(Image.fromarray(A.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(cfg["glow_blur"]))).astype(np.float32)
    # 幂次压缩：模糊后的中低值（字间空隙 / 外接矩形内部）被压暗，
    # 只有贴着笔画的高值留下来 —— 这是「光」和「矩形光板」的分界线。
    near = 255.0 * np.clip(near / 255.0, 0, 1) ** cfg.get("glow_gamma", 1.0)
    # 外雾：大半径但强度低，只提供原图那种「白色发亮」的氛围；
    # alpha 低，即使被 patch 边界裁掉也不会形成可见的矩形硬边。
    fog = np.array(Image.fromarray(A.astype(np.uint8))
                   .filter(ImageFilter.GaussianBlur(cfg["glow_fog_blur"]))).astype(np.float32)
    ga = (near * cfg["glow_gain"] + fog * cfg["glow_fog_gain"]) * \
         st["glow"] * st["alpha"] * (1.0 - core * 0.92)
    ga = np.clip(ga, 0, cfg.get("glow_cap", 255))

    # 字身：半透明。禁用态由 st["alpha"] 再压一档；常态可单列提亮
    ba = A * st.get("body", cfg["body_gain"]) * st["alpha"]

    # 描边：只在字形外 1px，细而实；字内减掉，抗锯齿边缘留自然过渡
    if st["edge"]:
        ex = dilate(A > 60, 3).astype(np.float32) * 255
        ea = np.clip(ex - A * 1.6, 0, 255) * st["alpha"] * cfg["edge_alpha"]
    else:
        ea = np.zeros_like(A)

    def L(alpha):
        return Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), "L")

    alphas = [L(ga), L(ba), L(ea) if st["edge"] else None]
    colors = [cfg["glow_rgb"], st["fill"], st["edge"]]

    # ★ 整层旋转，而不是逐字抬高（rise 必须为 0）+ 斜切。
    #   只旋各层 alpha、再用纯色重建：颜色不被透明黑/深褐描边串色污染，
    #   几何仍是「整个词一次性斜过来」，字内横竖笔画跟着斜。
    out0 = compose_layers(alphas, colors, (pw, ph))
    pre = np.array(out0)[:, :, 3].astype(np.float32).sum(axis=1)
    target_cy = float((np.arange(len(pre)) * pre).sum() / max(pre.sum(), 1))
    if cfg.get("rotate"):
        rot = [rotate_alpha(a, cfg["rotate"], cfg.get("rotate_pad", 14))
               if a is not None else None for a in alphas]
        out = compose_layers(rot, colors, (pw, ph))
    else:
        out = out0

    # 左右羽化宽度必须小于墨迹左沿到 patch 左界的距离，否则会削到首字笔画。
    # 列0 的 pad 只有 1px（禁用态、本身无辉光），索性不做左右羽化。
    fx = min(cfg.get("feather_x", 0), max(0, pad - 1))
    out = feather_edges(out, cfg.get("glow_feather", 0), fx)
    out = align_patch(out, pad, target_cy)
    if dim != 1.0:
        a = np.array(out).astype(np.float32)
        a[:, :, 3] *= dim
        out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
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
def patch_right(p):
    """patch 内 alpha>60 墨迹的最右列（含柔光），用于红线验收。"""
    a = np.array(p)[:, :, 3]
    cols = np.nonzero((a > 60).any(axis=0))[0]
    return int(cols.max()) if len(cols) else 0


def fit_sizes(cfg):
    """逐行按红线下调字号，四列共用同一字号（状态切换时字不能忽大忽小）。

    用列 1（常态、柔光最宽）试渲染：墨迹右沿若超过「红线 - 2px」，
    字号降 1 再试。这样「最后一个字被引擎裁掉」由代码保证不会发生；
    换词、换字号、换红线都不用手算。红线本身来自原图每行英文的实际右沿。
    """
    ci = 1
    col = cfg["cols"][ci]
    x0 = cfg["clear_x0"][ci]
    pad = cfg["text_x"][ci] - x0
    pw = col + cfg["col_w"] - x0
    st = cfg["styles"][ci]
    sizes = []
    for ri, ((y0, y1), word) in enumerate(zip(cfg["rows"], cfg["words"])):
        ph, cy = y1 - y0, (y1 - y0) / 2.0
        sz = cfg["font_sizes"][ri]
        limit = cfg["redline"][ri] - 2
        for _ in range(6):
            font = ImageFont.truetype(cfg["font"], sz)
            p = make_styled_patch(pw, ph, word, font, cy, st, cfg, pad,
                                  cfg["row_dim"].get(ri, 1.0),
                                  cfg["char_gaps"][ri])
            if x0 + patch_right(p) - col <= limit or sz <= 12:
                break
            sz -= 1
        sizes.append(sz)
    return sizes


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
    sizes = fit_sizes(cfg)
    log("popup 逐行字号(按红线校准): %s" % sizes)
    fonts = [ImageFont.truetype(cfg["font"], sz) for sz in sizes]
    for ci, col in enumerate(cfg["cols"]):
        st = cfg["styles"][ci]
        for ri, ((y0, y1), word) in enumerate(zip(cfg["rows"], cfg["words"])):
            # patch 左界严格等于清除区左界：旋转/柔光怎么扩散都不会漏到区外；
            # 旋转后由 align_left 把墨迹左沿补正到 text_x - clear_x0。
            x0 = cfg["clear_x0"][ci]
            pad = cfg["text_x"][ci] - x0
            pw = col + cfg["col_w"] - x0
            ph = y1 - y0
            cy = (y0 + y1) / 2.0 - y0
            p = make_styled_patch(pw, ph, word, fonts[ri], cy, st, cfg, pad,
                                  cfg["row_dim"].get(ri, 1.0),
                                  cfg["char_gaps"][ri])
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
