# -*- coding: utf-8 -*-
"""
追加任务四（13 张）的汉化生成器。运行：在 工具/ 目录执行 python build_batch4.py

六类模型，共用「先量后画」的骨架：
  1. 擦字：实心底板 → 颜色判据 / 同组差分 mask + 同格纹理回填；
           透明底   → 标签窗整块清 alpha=0（辉光也是字的一部分，一起清）。
  2. 重画：宋体 + 逐字字距 + alpha 加实；按原图选左对齐 / 居中；
           发光态用「字形外扩紧光 + 挖空字核心」，不发光的底板字用淡描边。
  3. 落位：真渲染后量墨迹 bbox，再平移到原字左沿 / 中心，不靠字体留白估算。
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config_batch4 as C


def log(*a):
    print(*a, flush=True)


def load(name):
    return np.array(Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")).astype(np.uint8)


def save(arr, name):
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    out.save(C.DST_DIR / (name + ".png"))
    return out


def dilate(mask, k=5):
    return np.array(Image.fromarray((mask * 255).astype(np.uint8), "L")
                    .filter(ImageFilter.MaxFilter(k))) > 0


def box_mask(shape, box, pad=0):
    m = np.zeros(shape[:2], bool)
    x0, y0, x1, y1 = box
    m[max(0, y0-pad):min(shape[0], y1+pad),
      max(0, x0-pad):min(shape[1], x1+pad)] = True
    return m


def font(size):
    if C.SERIF is None:
        raise RuntimeError("找不到宋体，请改 config_batch4.SERIF_CANDIDATES")
    return ImageFont.truetype(C.SERIF, size)


# ---------------------------------------------------------------- 字形渲染
def word_alpha(size, word, f, gap, boost=1.0):
    """逐字绘制纯字形 alpha（从 0,0 起画，落位由 place 负责）。"""
    layer = Image.new("L", size, 0)
    d = ImageDraw.Draw(layer)
    bb = d.textbbox((0, 0), word, font=f)
    # 必须留上边距：直接把 py 设成负值会把字的上半截画到画布外裁掉
    # （首版「存档」被裁成「1寸 1=3」就是这么来的）。落位由 place 统一量 bbox 平移。
    py = 24.0 - (bb[1] + bb[3]) / 2.0
    x = 24.0
    for ch in word:
        d.text((x, py), ch, font=f, fill=255)
        x += d.textlength(ch, font=f) + gap
    a = np.array(layer).astype(np.float32)
    return np.clip(a * boost, 0, 255).astype(np.uint8), (bb[3] - bb[1])


def layer_rgb(size, rgb, alpha):
    im = Image.new("RGBA", size, tuple(int(v) for v in rgb) + (0,))
    im.putalpha(Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), "L"))
    return im


def make_solid_patch(size, word, f, gap, st):
    """实心底板用：淡描边（外扩扣核心）+ 实字。"""
    A, _ = word_alpha(size, word, f, gap, st.get("boost", C.ALPHA_BOOST))
    core = A.astype(np.float32) / 255.0
    outline_a = np.zeros_like(core)
    if st.get("outline"):
        ex = dilate(A > 60, 3).astype(np.float32) * 255
        # 这里已经是 0~outline_a 的 alpha 值，别再乘 255（会把淡描边变成不透明，
        # 中文整字被染成描边色，实测翻车过一次）
        outline_a = np.clip(ex - A.astype(np.float32), 0, 255) * \
                    (st.get("outline_a", 0) / 255.0)
    out = layer_rgb(size, st["outline"] if st.get("outline") else (0, 0, 0),
                    outline_a)
    out = Image.alpha_composite(out, layer_rgb(size, st["fill"], A))
    return out


def make_glow_patch(size, word, f, gap, fill, glow_rgb, glow_gain, boost):
    """透明底用：字形外扩紧光（挖空字核心）+ 实字。"""
    A, _ = word_alpha(size, word, f, gap, boost)
    core = A.astype(np.float32) / 255.0
    ex = dilate(A > 60, 5).astype(np.float32) * 255
    tight = np.array(Image.fromarray(np.clip(ex, 0, 255).astype(np.uint8), "L")
                     .filter(ImageFilter.GaussianBlur(1.8))).astype(np.float32)
    soft = np.array(Image.fromarray(A, "L")
                    .filter(ImageFilter.GaussianBlur(4.5))).astype(np.float32)
    ga = (tight * 0.62 + soft * 0.38) * glow_gain * (1.0 - core * 0.94)
    out = layer_rgb(size, glow_rgb, ga)
    out = Image.alpha_composite(out, layer_rgb(size, fill, A))
    return out


def place(base, patch, left=None, cx=None, cy=None):
    """按真渲染墨迹 bbox 平移贴到目标左沿 / 中心。"""
    a = np.array(patch)
    al = a[:, :, 3]
    ys, xs = np.nonzero(al > 60)
    if not len(xs):
        return base
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    if left is not None:
        # 直接用左沿：目标 left == 平移后墨迹最左列
        dx = int(round(left - x0))
    elif cx is not None:
        dx = int(round(cx - (x0 + x1) / 2.0))
    else:
        dx = 0
    if cy is not None:
        dy = int(round(cy - (y0 + y1) / 2.0))
    else:
        dy = 0
    H, W = base.shape[:2]
    out = np.zeros((H, W, 4), np.float32)
    sx0, sx1 = max(0, -dx), min(W - dx, W)
    sy0, sy1 = max(0, -dy), min(H - dy, H)
    tx0, tx1 = max(0, dx), min(W, W + dx)
    ty0, ty1 = max(0, dy), min(H, H + dy)
    if sx1 <= sx0 or sy1 <= sy0:
        return base
    out[ty0:ty1, tx0:tx1] = a[sy0:sy1, sx0:sx1]
    return Image.alpha_composite(Image.fromarray(base.astype(np.uint8), "RGBA"),
                                 Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA"))


# ---------------------------------------------------------------- 擦字
def diffuse_texture(arr, mask, radius=7, ring_k=7, resid_gain=1.0):
    """
    实心底板擦字后的补底：扩散低频 + 干净环的真实高频残差。

    为什么不用 repair.patch_repair：
      细衬线字（本批木牌/金字/白字笔画只有 1~4px）时，MinFilter(3) 算出的
      core 几乎为空，patch_repair 结尾的「边界 1px 半混合」会把原字保留 50%；
      而它的同格样本里又混着未被 mask 覆盖的字笔画，回填后变成一片黑点
      （见 work/p4/repair_compare.png 的 A/B/G 三行，都翻过车）。
    扩散法不从图里搬样本，只用 mask 外的真实像素插值出局部底色，
    所以字形绝不会被搬回来；高频再从「mask 外的干净环」取真实残差，
    保住木纹/青色笔刷的颗粒，不留下平滑补丁。
    """
    rgb = arr[:, :, :3].astype(np.float32)
    out = rgb.copy()
    known = ~mask
    Hh, Ww = mask.shape
    wf = np.array(Image.fromarray((known * 255).astype(np.uint8), "L")
                  .filter(ImageFilter.GaussianBlur(radius))).astype(np.float32) / 255
    num = np.zeros((Hh, Ww, 3), np.float32)
    num[known] = rgb[known]
    low = np.stack([
        np.array(Image.fromarray(np.clip(num[:, :, c], 0, 255).astype(np.uint8), "L")
                 .filter(ImageFilter.GaussianBlur(radius))).astype(np.float32)
        for c in range(3)], axis=2)
    low = np.clip(low / np.maximum(wf[:, :, None], 1e-3), 0, 255)
    out[mask] = low[mask]

    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.1))).astype(np.float32)
    resid = rgb - blur
    ring = dilate(mask, ring_k) & known & (arr[:, :, 3] > 200)
    samples = resid[ring]
    if len(samples) < 16:
        samples = resid[known]
    yy, xx = np.where(mask)
    idx = (yy * 37 + xx * 101 + 13) % len(samples)
    out[yy, xx] = np.clip(out[yy, xx] + samples[idx] * resid_gain, 0, 255)
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    return res


def column_fill(arr, mask, resid_gain=1.0, ring_k=5):
    """
    暗色/青色水平纹理底板专用：按列取紧邻的上下真实像素线性插值。

    2D 扩散在「有强水平渐变的暗木牌、青色笔刷条」上会偏色 —— 它把周围
    的暗边一起平均进来，擦字区就变成一块深色矩形补丁（率牌实测）。
    按列插值只用同一列上下两行真实像素，颜色和水平渐变都连续；
    再补一点「mask 外干净环」的真实高频残差，保住斑驳颗粒。
    """
    rgb = arr[:, :, :3].astype(np.float32)
    out = rgb.copy()
    H, W = mask.shape
    for x in range(W):
        ys = np.nonzero(mask[:, x])[0]
        if not len(ys):
            continue
        segs, st = [], ys[0]
        for i in range(1, len(ys)):
            if ys[i] != ys[i-1] + 1:
                segs.append((st, ys[i-1]))
                st = ys[i]
        segs.append((st, ys[-1]))
        for ya, yb in segs:
            yt, ybot = ya - 1, yb + 1
            while yt >= 0 and mask[yt, x]:
                yt -= 1
            while ybot < H and mask[ybot, x]:
                ybot += 1
            top = rgb[yt, x] if yt >= 0 else (rgb[ybot, x] if ybot < H else rgb[ya, x])
            bot = rgb[ybot, x] if ybot < H else top
            n = yb - ya + 1
            for j, y in enumerate(range(ya, yb + 1)):
                t = (j + 1) / (n + 1)
                out[y, x] = (1 - t) * top + t * bot
    # 逐列插值会让相邻列的 top/bot 取值不同，留下可见竖条纹；
    # 对小半径模糊后的低频取 mask 内像素，列间断就被抹平。
    smooth = np.array(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)
    out[mask] = smooth[mask]
    known = ~mask
    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.1))).astype(np.float32)
    resid = rgb - blur
    ring = dilate(mask, ring_k) & known
    samples = resid[ring]
    if len(samples) < 16:
        samples = resid[known]
    yy, xx = np.where(mask)
    out[yy, xx] = np.clip(
        out[yy, xx] + samples[(yy * 37 + xx * 101 + 13) % len(samples)] * resid_gain,
        0, 255)
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    return res


def erase_solid(arr, mask, cells=None, radius=7, mode="diffuse"):
    if mode == "column":
        return column_fill(arr, mask)
    return diffuse_texture(arr, mask, radius=radius)


def clear_alpha(arr, boxes):
    for x0, y0, x1, y1 in boxes:
        arr[y0:y1, x0:x1] = 0


def record_mask(name, key, mask, union=False):
    """第 5 批起同一张图会分两步改（标签 + 小格），mask 需要并集而不是覆盖。"""
    p = C.WORK_DIR / ("b4_%s_%s.npy" % (name, key))
    if union and p.exists():
        mask = np.load(str(p)) | mask
    np.save(str(p), mask)


def load_out(name):
    """读上一步已经写进交付目录的中间结果（同一张图分两步改时用）。"""
    return np.array(Image.open(C.DST_DIR / (name + ".png")).convert("RGBA")).astype(np.uint8)


# ---------------------------------------------------------------- 第 5 批：小格工艺
def lines_patch(size, lines, font_size, gap, st, line_gap=1):
    """
    多行中文一次性画进同一张 alpha 层，再统一做描边 + 字身。

    别把「每行各渲染一张 patch 再 alpha 合成」——试过，第二行会出现
    暗色碎笔画（straight-alpha 手工混合把描边层算错了），见 work/p5/patch_alone.png。
    """
    f = font(font_size)
    layer = Image.new("L", size, 0)
    d = ImageDraw.Draw(layer)
    adv = [sum(d.textlength(ch, font=f) + gap for ch in ln) - gap for ln in lines]
    bb = d.textbbox((0, 0), "字", font=f)
    h = bb[3] - bb[1]
    y = 24.0 - bb[1]
    for i, ln in enumerate(lines):
        x = 24.0 + (max(adv) - adv[i]) / 2.0
        for ch in ln:
            d.text((x, y), ch, font=f, fill=255)
            x += d.textlength(ch, font=f) + gap
        y += h + line_gap
    A = np.clip(np.array(layer).astype(np.float32) * st["boost"], 0, 255).astype(np.uint8)
    ex = dilate(A > 60, 3).astype(np.float32) * 255
    oa = np.clip(ex - A.astype(np.float32), 0, 255) * (st["outline_a"] / 255.0)
    out = layer_rgb(size, st["outline"], oa)
    return Image.alpha_composite(out, layer_rgb(size, st["fill"], A))


def text_mask(arr, win, dilate_k=7):
    """
    实心青色小按钮上的白字 + 深色投影：亮判据与暗判据取并集，再外扩。

    只判白色会留下整圈深色描边字影（work/p5/try_vp_cells8x.png 翻过车）；
    膨胀 3 也不够，阴影离笔画有 2~3px。外扩 7 后按钮纹理仍大量保留。
    """
    x0, y0, x1, y1 = win
    q = arr[y0:y1, x0:x1]
    white = ((q[:, :, 0] > 175) & (q[:, :, 1] > 180) &
             (q[:, :, 2] > 175) & (q[:, :, 3] > 150))
    dark = (q[:, :, :3].mean(axis=2) < 70) & (q[:, :, 3] > 150)
    stroke = np.zeros(arr.shape[:2], bool)
    stroke[y0:y1, x0:x1] = white | dark
    return stroke, dilate(stroke, dilate_k) & box_mask(arr.shape, win, 1)


def button_inpaint(arr, mask, gain=0.55, iters=160):
    """
    小按钮擦字后的补底：四邻域调和插值 + 只从「真正的青色像素」取高频。

    试过并否掉的三种：
      column_fill      逐列端点插值，会在小格里留下半边深半边亮的竖条；
      diffuse_texture  known 含单元格暗边，摊出深色矩形（个别格还会全黑）；
      扩散 + 边界羽化  竖条只是变糊，没消失。
    调和插值的每个 mask 像素由四邻反复平均，边界来自四面而不是只有上下两端，
    所以色场连续；初值取全局 teal 中位色，避免从白字/暗描边起算。
    np.pad(edge) 做邻居，别用 np.roll —— 左沿格贴近 x=0，roll 会把最右列
    的深红徽标卷进来。
    """
    rgb = arr[:, :, :3].astype(np.float32)
    teal = ((rgb[:, :, 1] > 105) & (rgb[:, :, 2] > 95) &
            (rgb[:, :, 0] < 155) & (arr[:, :, 3] > 170))
    seed = np.median(rgb[teal & (~mask)], axis=0)
    val = rgb.copy()
    val[mask] = seed
    for _ in range(iters):
        p = np.pad(val, ((1, 1), (1, 1), (0, 0)), mode="edge")
        nb = (p[:-2, 1:-1] + p[2:, 1:-1] +
              p[1:-1, :-2] + p[1:-1, 2:]) / 4.0
        val[mask] = nb[mask]
    out = rgb.copy()
    out[mask] = val[mask]
    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.1))).astype(np.float32)
    resid = rgb - blur
    samples = resid[teal & (~mask)]
    rng = np.random.default_rng(20261108)
    yy, xx = np.where(mask)
    out[yy, xx] = np.clip(out[yy, xx] +
                          samples[rng.integers(0, len(samples), len(yy))] * gain,
                          0, 255)
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    return res


# ---------------------------------------------------------------- 1 木牌
def build_titles():
    for cfg in C.TITLES:
        n = cfg["name"]
        A = load(n)
        win = cfg["win"]
        box = box_mask(A.shape, win)
        # 只擦「比局部背景暗 40 以上的细笔画」，笔画之间的原木纹全部保留。
        # 用同组差分并集（两字形并集）会把整个字区连成一块矩形，扩散补底后
        # 就是明显的浅色补丁；局部背景差是高频量，木牌的大块暗斑不会被选中。
        lum = A[:, :, :3].mean(axis=2)
        bg = np.array(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8), "L")
                      .filter(ImageFilter.GaussianBlur(8))).astype(np.float32)
        stroke = (bg - lum > 40) & (A[:, :, 3] > 200) & box
        mask = dilate(stroke, 5) & box_mask(A.shape, win, 2)
        record_mask(n, "stroke", stroke)
        clean = erase_solid(A, mask, radius=5)
        arr = np.array(clean)
        f = font(C.TITLE_STYLE["font_size"])
        p = make_solid_patch(A.shape[:2][::-1], cfg["word"], f,
                             C.TITLE_STYLE["gap"], C.TITLE_STYLE)
        out = place(arr, p, cx=cfg["center"][0], cy=cfg["center"][1])
        save(np.array(out), n)
        record_mask(n, "erase", mask)
        log("  %-14s %-6s 擦除 %5d px" % (n, cfg["word"], int(mask.sum())))


# ---------------------------------------------------------------- 2 率牌
def build_rates():
    for cfg in C.RATES:
        n = cfg["name"]
        A = load(n)
        win = cfg["win"]
        x0, y0, x1, y1 = win
        q = A[y0:y1, x0:x1].astype(int)
        # 判据放宽到抗锯齿，但只膨胀 3px：金字笔画细，膨胀 7 会让整个词
        # 连成矩形，扩散补底后就是一块深色补丁（实测翻车）。
        lum = q[:, :, :3].mean(axis=2)
        bg = np.array(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8), "L")
                      .filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
        m = ((lum - bg > 18) & (q[:, :, 0] - q[:, :, 2] > 45) &
             (q[:, :, 1] - q[:, :, 2] > 12) & (q[:, :, 3] > 200))
        full = np.zeros(A.shape[:2], bool)
        full[y0:y1, x0:x1] = m
        record_mask(n, "stroke", full)
        mask = dilate(full, 3) & box_mask(A.shape, win, 2)
        clean = erase_solid(A, mask, radius=5, mode="column")
        arr = np.array(clean)
        f = font(C.RATE_STYLE["font_size"])
        p = make_solid_patch(A.shape[:2][::-1], cfg["word"], f,
                             C.RATE_STYLE["gap"], C.RATE_STYLE)
        # 与原金字基线对齐：字底 y=59.5
        out = place(arr, p, left=cfg["left"], cy=C.RATE_STYLE["baseline_y"] - 7)
        save(np.array(out), n)
        record_mask(n, "erase", mask)
        log("  %-14s %-4s 擦除 %5d px" % (n, cfg["word"], int(mask.sum())))


# ---------------------------------------------------------------- 3 stand_back
def build_stand_back():
    cfg = C.STAND_BACK
    A = load(cfg["name"])
    mask = np.zeros(A.shape[:2], bool)
    stroke_all = np.zeros(A.shape[:2], bool)
    cells = []
    for y0, y1 in cfg["rows"]:
        win = (cfg["win_x"][0], y0 + 3, cfg["win_x"][1], y1 - 2)
        x0, yy0, x1, yy1 = win
        q = A[yy0:yy1, x0:x1]
        m = ((q[:, :, 0] > 170) & (q[:, :, 1] > 175) &
             (q[:, :, 2] > 170) & (q[:, :, 3] > 190))
        full = np.zeros(A.shape[:2], bool)
        full[yy0:yy1, x0:x1] = m
        stroke_all |= full
        mask |= dilate(full, 3) & box_mask(A.shape, win, 2)
        cells.append(win)
    record_mask(cfg["name"], "stroke", stroke_all)
    clean = erase_solid(A, mask, cells, radius=5, mode="column")
    arr = np.array(clean)
    f = font(cfg["style"]["font_size"])
    out = Image.fromarray(arr, "RGBA")
    for y0, y1 in cfg["rows"]:
        p = make_solid_patch(A.shape[:2][::-1], cfg["word"], f,
                             cfg["style"]["gap"], cfg["style"])
        out = place(np.array(out), p, cx=cfg["center_x"], cy=(y0 + y1) / 2.0)
    save(np.array(out), cfg["name"])
    record_mask(cfg["name"], "erase", mask)
    log("  %-14s 返回 ×3 擦除 %5d px" % (cfg["name"], int(mask.sum())))


# ---------------------------------------------------------------- 4 extra_mode
def build_extra_mode():
    cfg = C.EXTRA_MODE
    A = load(cfg["name"])
    clear = np.zeros(A.shape[:2], bool)
    for y0, y1 in cfg["rows"]:
        for x0, x1 in cfg["cols"]:
            clear[y0:y1, x0:x1] = True
    arr = A.copy()
    arr[clear] = 0
    record_mask(cfg["name"], "stroke", clear & (A[:, :, 3] > 150))
    f = font(cfg["font_size"])
    out = Image.fromarray(arr, "RGBA")
    for ri, (y0, y1) in enumerate(cfg["rows"]):
        for ci, word in enumerate(cfg["words"]):
            st = cfg["exceptions"].get((ri, ci), cfg["row_styles"][ri])
            p = make_glow_patch(A.shape[:2][::-1], word, f, cfg["gap"],
                                st["fill"], st["glow"], st["glow_gain"],
                                cfg["boost"])
            out = place(np.array(out), p, left=cfg["lefts"][ci], cy=cfg["cy"][ri])
    save(np.array(out), cfg["name"])
    record_mask(cfg["name"], "erase", clear)
    log("  extra_mode    6 词 × 3 行（第 3 行第 4 格单独配色）")


# ---------------------------------------------------------------- 5 stand_parts
def build_stand_parts():
    cfg = C.STAND_PARTS
    A = load(cfg["name"])
    mask = np.zeros(A.shape[:2], bool)
    stroke_all = np.zeros(A.shape[:2], bool)
    cells = []
    for y0, y1 in cfg["rows"]:
        win = (cfg["win_x"][0], y0, cfg["win_x"][1], y1)
        x0, yy0, x1, yy1 = win
        q = A[yy0:yy1, x0:x1]
        m = ((q[:, :, 0] > 165) & (q[:, :, 1] > 170) &
             (q[:, :, 2] > 165) & (q[:, :, 3] > 185))
        full = np.zeros(A.shape[:2], bool)
        full[yy0:yy1, x0:x1] = m
        stroke_all |= full
        mask |= dilate(full, 3) & box_mask(A.shape, win, 2)
        cells.append(win)
    clean = erase_solid(A, mask, cells, radius=5, mode="column")
    f = font(cfg["style"]["font_size"])
    out = Image.fromarray(clean, "RGBA")
    # 用户第 5 批改口：六行一律按格中心落位，不再左对齐到英文墨迹左沿。
    for ri, (y0, y1) in enumerate(cfg["rows"]):
        p = make_solid_patch(A.shape[:2][::-1], cfg["words"][ri], f,
                             cfg["style"]["gap"], cfg["style"])
        out = place(np.array(out), p, cx=cfg["center_x"], cy=(y0 + y1) / 2.0)

    # 徽标上的两个白底小框：只重填框内 1px 以上的区域，外圈与上下箭头不动。
    arr = np.array(out).copy()
    badge_erase = np.zeros(A.shape[:2], bool)
    for bl in C.BADGE_LABELS:
        x0, y0, x1, y1 = bl["box"]
        stroke_all |= _local_dark(A, bl["box"])
        arr[y0 + 1:y1 - 1, x0 + 1:x1 - 1, :3] = C.BADGE_PALE
        arr[y0 + 1:y1 - 1, x0 + 1:x1 - 1, 3] = 255
        badge_erase |= box_mask(A.shape, bl["box"])
    out = Image.fromarray(arr, "RGBA")
    fb = font(C.BADGE_STYLE["font_size"])
    for bl in C.BADGE_LABELS:
        x0, y0, x1, y1 = bl["box"]
        p = make_solid_patch(A.shape[:2][::-1], bl["word"], fb,
                             C.BADGE_STYLE["gap"],
                             dict(fill=C.BADGE_STYLE["fill"], outline=None,
                                  outline_a=0, boost=C.BADGE_STYLE["boost"]))
        out = place(np.array(out), p, cx=(x0 + x1) / 2.0, cy=(y0 + y1) / 2.0)

    save(np.array(out), cfg["name"])
    record_mask(cfg["name"], "stroke", stroke_all)
    # 验收用的允许改动区要把徽标两个白框算进去，但补底 inpaint 绝不能碰它们。
    record_mask(cfg["name"], "erase", mask | badge_erase)
    log("  stand_parts   6 行居中 + 徽标 2 词  擦除 %5d px" % int(mask.sum()))


def _local_dark(arr, box):
    """取小框内的深色原文字像素，作为『旧字已擦除』判据。"""
    x0, y0, x1, y1 = box
    q = arr[y0 + 1:y1 - 1, x0 + 1:x1 - 1]
    m = (q[:, :, 0] < 190) & (q[:, :, 1] < 130) & (q[:, :, 2] < 140)
    full = np.zeros(arr.shape[:2], bool)
    full[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = m
    return full


# ---------------------------------------------------------------- 6 透明辉光标签
def build_glow_labels():
    for cfg in C.GLOW_LABELS:
        A = load(cfg["name"])
        arr = A.copy()
        clear = np.zeros(A.shape[:2], bool)
        for lb in cfg["labels"]:
            x0, y0, x1, y1 = lb["win"]
            arr[y0:y1, x0:x1] = 0
            clear[y0:y1, x0:x1] = True
        record_mask(cfg["name"], "stroke", clear & (A[:, :, 3] > 150))
        f = font(cfg["font_size"])
        out = Image.fromarray(arr, "RGBA")
        for lb in cfg["labels"]:
            p = make_glow_patch(A.shape[:2][::-1], lb["word"], f, cfg["gap"],
                                C.LABEL_STYLE["fill"], cfg["glow"],
                                cfg["glow_gain"], C.LABEL_STYLE["boost"])
            out = place(np.array(out), p, left=lb["left"], cy=lb["cy"])
        save(np.array(out), cfg["name"])
        record_mask(cfg["name"], "erase", clear)
        log("  %-14s %d 个标签" % (cfg["name"], len(cfg["labels"])))


# ---------------------------------------------------------------- 7 第 5 批：补漏与改对齐
def build_now_playing():
    """music_parts 底部黄色 NOW PLAYING → 正在播放。透明底，整窗清 alpha=0 后重画。"""
    cfg = C.NOW_PLAYING
    A = load_out(cfg["name"])          # 已含 CONTROL / VOLUME / MUSIC LIST 的汉化
    src = load(cfg["name"])
    x0, y0, x1, y1 = cfg["win"]
    arr = A.copy()
    arr[y0:y1, x0:x1] = 0
    q = src[y0:y1, x0:x1]
    stroke = np.zeros(A.shape[:2], bool)
    stroke[y0:y1, x0:x1] = ((q[:, :, 0] > 225) & (q[:, :, 1] > 225) &
                            (q[:, :, 2] > 200) & (q[:, :, 3] > 100))
    f = font(cfg["font_size"])
    p = make_glow_patch(A.shape[:2][::-1], cfg["word"], f, cfg["gap"],
                        cfg["fill"], cfg["glow"], cfg["glow_gain"], cfg["boost"])
    out = place(arr, p, cx=cfg["cx"], cy=cfg["cy"])
    save(np.array(out), cfg["name"])
    record_mask(cfg["name"], "stroke", stroke, union=True)
    record_mask(cfg["name"], "erase", box_mask(A.shape, cfg["win"]), union=True)
    log("  music_parts   NOW PLAYING → 正在播放")


def build_voice_cells():
    """voice_parts 顶部 15 个小格：9 处 ALL → 所有，6 处 PLAY LIST → 播放/列表。"""
    name = "voice_parts"
    A = load_out(name)                  # 已含底部 FAVORITE VOICE / PLAY LIST 的汉化
    src = load(name)
    st = C.VOICE_CELL_STYLE
    shape = A.shape[:2][::-1]
    erase = np.zeros(A.shape[:2], bool)
    stroke_all = np.zeros(A.shape[:2], bool)
    for cell in C.VOICE_SMALL_CELLS:
        s, m = text_mask(src, cell["win"], st["dilate"])
        stroke_all |= s
        erase |= m
    clean = button_inpaint(A, erase, st["resid_gain"])
    out = Image.fromarray(clean, "RGBA")
    for cell in C.VOICE_SMALL_CELLS:
        w = cell["win"]
        p = lines_patch(shape, cell["lines"], cell["font_size"], cell["gap"], st)
        out = place(np.array(out), p, cx=(w[0] + w[2]) / 2.0,
                    cy=(w[1] + w[3]) / 2.0)
    save(np.array(out), name)
    record_mask(name, "stroke", stroke_all, union=True)
    record_mask(name, "erase", erase, union=True)
    log("  voice_parts   %d 个小格：ALL/PLAY LIST → 中文" % len(C.VOICE_SMALL_CELLS))


def main():
    log("字体:", C.SERIF)
    log("追加任务四 · 13 张 + 第 5 批口述修订（3 张）")
    build_titles()
    build_rates()
    build_stand_back()
    build_extra_mode()
    build_stand_parts()
    build_glow_labels()
    # 同一张图分两步改：后两步必须读上一步的中间结果，不能从原图重来。
    build_now_playing()
    build_voice_cells()
    log("完成，输出 ->", C.DST_DIR)


if __name__ == "__main__":
    main()
