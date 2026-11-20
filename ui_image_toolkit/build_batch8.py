# -*- coding: utf-8 -*-
"""
戦巫 UI 第一批 · 第一组生成器（5 张）
运行：在 <游戏>\\7_图片 目录下执行
      python <工具>\\ui_image_toolkit\\build_batch8.py
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import config_batch8 as C
import build_batch4 as B
import build_batch6 as B6
from glyph_unit import (
    glyph_fill, glow_glyph, tight_clip, soft_patch_shape,
)


def log(*a):
    print(*a, flush=True)


def load(name):
    return np.array(Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")).astype(np.uint8)


def save(arr, name):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA").save(
        C.DST_DIR / (name + ".png"))


def font(sz):
    from PIL import ImageFont
    return ImageFont.truetype(C.SERIF, sz)


def place8(base, patch, cx, cy, tag="", clip=None, feather=2, fade_bottom=0,
           shape=None):
    """逐像素 straight-alpha 合成；断言贴片有墨迹且落位不越界。

    clip=(x0,y0,x1,y1)：**矩形**事前框定，边缘 feather 像素线性羽化。
    shape=全图尺寸 float32(0~1)：**按原图 alpha 轮廓**事前框定（菱形 / 圆形 /
    文字墨迹 bbox），贴片超出原图形状的棱角一律淡出。矩形 clip 会把圆形按钮
    与菱形切出方形边界，这时必须用 shape 而不是 clip。
    fade_bottom：clip 下边界前 N 像素把光晕线性压到 0。
    """
    a = np.array(patch).copy()
    al = a[:, :, 3]
    ys, xs = np.nonzero(al > 60)
    assert len(xs), tag + " 贴片无墨迹"
    dx = int(round(cx - (xs.min() + xs.max()) / 2.0))
    dy = int(round(cy - (ys.min() + ys.max()) / 2.0))
    H, W = base.shape[:2]
    yy, xx = np.nonzero(al > 0)
    tx, ty = xx + dx, yy + dy
    ok = (tx >= 0) & (tx < W) & (ty >= 0) & (ty < H)
    w = np.ones(len(ty), np.float32)
    if clip is not None:
        bx0, by0, bx1, by1 = clip
        ok &= (tx >= bx0) & (tx < bx1) & (ty >= by0) & (ty < by1)
        if feather > 0:
            wx = np.minimum(tx - bx0, bx1 - 1 - tx).astype(np.float32)
            wy = np.minimum(ty - by0, by1 - 1 - ty).astype(np.float32)
            w *= np.clip(np.minimum(wx, wy) / float(feather), 0.0, 1.0)
        if fade_bottom > 0:
            from_bottom = (by1 - 1 - ty).astype(np.float32)
            w *= np.clip(from_bottom / float(fade_bottom), 0.0, 1.0)
    if shape is not None:
        safe = (tx >= 0) & (tx < W) & (ty >= 0) & (ty < H)
        sw = np.zeros(len(ty), np.float32)
        sw[safe] = shape[ty[safe], tx[safe]]
        w *= np.clip(sw, 0.0, 1.0)
    al2 = a[:, :, 3].astype(np.float32)
    al2[yy, xx] *= w
    a[:, :, 3] = np.clip(al2, 0, 255).astype(np.uint8)
    assert ok.sum() > 20, "%s 落位越界 (%d,%d)" % (tag, dx, dy)
    tx, ty, sy, sx = tx[ok], ty[ok], yy[ok], xx[ok]
    src = a[sy, sx].astype(np.float32)
    sa = src[:, 3:4] / 255.0
    ba = base[ty, tx, 3:4].astype(np.float32) / 255.0
    oa = sa + ba * (1.0 - sa)
    orgb = (src[:, :3] * sa + base[ty, tx, :3].astype(np.float32) * ba * (1.0 - sa)) \
           / np.maximum(oa, 1e-6)
    base[ty, tx, :3] = np.clip(orgb, 0, 255).astype(np.uint8)
    base[ty, tx, 3:4] = np.clip(oa * 255, 0, 255).astype(np.uint8)


def solid8(shape, word, f, gap, fill, boost=1.0):
    """纯色实心字贴片（框内无描边）。"""
    A, _ = B.word_alpha(shape, word, f, gap, boost)
    return B.layer_rgb(shape, fill, A)


def outline8(shape, word, f, gap, color, boost=1.0, k=3):
    """空心描边字：原图第 0 行是金色细线勾边、字身暗，不能画成实心。"""
    A, _ = B.word_alpha(shape, word, f, gap, boost)
    ex = B.dilate(A > 60, k).astype(np.float32) * 255
    ring = np.clip(ex - A.astype(np.float32), 0, 255)
    return B.layer_rgb(shape, color, ring)


def gold_mask(A, win):
    """红底花卉纹上的金字：靠 G 通道区分（金字 g≈208，红底 g≈20）。"""
    x0, y0, x1, y1 = win
    q = A[y0:y1, x0:x1]
    m = ((q[:, :, 0] > 170) & (q[:, :, 1] > 120) &
         (q[:, :, 2] < 175) & (q[:, :, 3] > 140))
    full = np.zeros(A.shape[:2], bool)
    full[y0:y1, x0:x1] = m
    return full, B.dilate(full, 3) & B.box_mask(A.shape, win, 1)


def build_titles():
    f = font(C.TITLE_STYLE["font_size"])
    for cfg in C.TITLES:
        A = load(cfg["name"])
        stroke, mask = gold_mask(A, cfg["win"])
        clean = B.diffuse_texture(A, mask, radius=5, resid_gain=0.85)
        arr = np.array(clean).copy()
        p = solid8(A.shape[:2][::-1], cfg["word"], f,
                   C.TITLE_STYLE["gap"], C.TITLE_STYLE["fill"],
                   C.TITLE_STYLE["boost"])
        place8(arr, p, *cfg["center"], tag=cfg["name"])
        # 日文副标题与花纹：窗口外一律还原
        x0, y0, x1, y1 = cfg["win"]
        allow = np.zeros(A.shape[:2], bool)
        allow[y0:y1, x0:x1] = True
        arr[~allow] = A[~allow]
        save(arr, cfg["name"])
        np.save(str(C.WORK_DIR / ("b8_%s_stroke.npy" % cfg["name"])), stroke)
        np.save(str(C.WORK_DIR / ("b8_%s_erase.npy" % cfg["name"])), mask)
        log("  %-22s → %-6s  金字擦除 %d px" %
            (cfg["name"], cfg["word"], int(mask.sum())))


def build_sys(cfg):
    A = load(cfg["name"])
    arr = A.copy()
    stroke = np.zeros(A.shape[:2], bool)
    clear = np.zeros(A.shape[:2], bool)
    x0, x1 = cfg["clear_x"]
    for row in cfg["rows"]:
        y0, y1 = row["y0"], row["y1"]
        stroke[y0:y1, x0:x1] = A[y0:y1, x0:x1, 3] > 100
        arr[y0:y1, x0:x1] = 0
        clear[y0:y1, x0:x1] = True

    f = font(cfg["font_size"])
    shape = A.shape[:2][::-1]
    for row in cfg["rows"]:
        for key, word, cx in cfg["words"]:
            if row["gain"] <= 0.6:      # 行 0：金色空心描边字，无光晕
                p = outline8(shape, word, f, cfg["gap"], row["fill"], row["boost"])
            else:
                p = B.make_glow_patch(shape, word, f, cfg["gap"],
                                      row["fill"], row["glow"],
                                      row["gain"], row["boost"])
            place8(arr, p, cx, row["cy"], tag="%s_%s" % (key, row["y0"]))

    arr[~clear] = A[~clear]            # 边界收敛：窗口外 0 改动
    save(arr, cfg["name"])
    np.save(str(C.WORK_DIR / ("b8_%s_stroke.npy" % cfg["name"])), stroke)
    np.save(str(C.WORK_DIR / ("b8_%s_erase.npy" % cfg["name"])), clear)
    log("  %-22s → %d 行 × %d 词  清除 %d px" %
        (cfg["name"], len(cfg["rows"]), len(cfg["words"]), int(clear.sum())))


def build_labels():
    """第二组：浅金胶带/金条上的深字。局部暗差找笔画 + 干净纸色中位回填。"""
    for cfg in C.LABELS:
        A = load(cfg["name"])
        arr = A.copy()
        stroke = np.zeros(A.shape[:2], bool)
        mask = np.zeros(A.shape[:2], bool)
        f = font(cfg["font_size"])
        for lb in cfg["labels"]:
            w = lb["win"]
            s = B6.local_dark(A, w, thr=28, rad=5)
            m = B.dilate(s, 3) & B.box_mask(A.shape, w, 1)
            arr = np.array(B6.flat_fill(arr, m, w, gain=0.12)).copy()
            stroke |= s
            mask |= m
        for lb in cfg["labels"]:
            p = solid8(A.shape[:2][::-1], lb["word"], f,
                       C.LABEL_STYLE["gap"], C.LABEL_STYLE["fill"],
                       C.LABEL_STYLE["boost"])
            place8(arr, p, *lb["center"], tag=cfg["name"] + "_" + lb["word"])
        allow = np.zeros(A.shape[:2], bool)
        for lb in cfg["labels"]:
            x0, y0, x1, y1 = lb["win"]
            allow[y0:y1, x0:x1] = True
        arr[~allow] = A[~allow]
        save(arr, cfg["name"])
        np.save(str(C.WORK_DIR / ("b8_%s_stroke.npy" % cfg["name"])), stroke)
        np.save(str(C.WORK_DIR / ("b8_%s_erase.npy" % cfg["name"])), mask)
        log("  %-22s → %-10s 擦除 %d px" %
            (cfg["name"], "/".join(l["word"] for l in cfg["labels"]), int(mask.sum())))


def fill_median(arr, mask, win, gain=0.12):
    """深底/纯色按钮：取窗口内未遮挡像素的 RGB 中位 + 极轻高频残差。

    与 B6.flat_fill 的区别是不要求 lum>140，深蓝/红色菱形底也能用。
    """
    x0, y0, x1, y1 = win
    rgb = arr[:, :, :3].astype(np.float32)
    q = arr[y0:y1, x0:x1]
    sel = (~mask[y0:y1, x0:x1]) & (q[:, :, 3] > 140)
    assert sel.sum() > 40, "按钮样本区为空: %s" % (win,)
    color = np.median(q[:, :, :3][sel], axis=0)
    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    resid = (rgb - blur)[y0:y1, x0:x1][sel]
    rng = np.random.default_rng(20261115)
    yy, xx = np.where(mask)
    pick = resid[rng.integers(0, len(resid), len(yy))]
    out = rgb.copy()
    out[yy, xx] = np.clip(color + pick * gain, 0, 255)
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    return res


def tape_rebuild(arr, win):
    """橙色横条上的立体字（白核 + 同色橙投影）专用：逐行中位色重建。

    字影与横条是同一色系，按颜色分不开；按列插值又会把字影当端点。
    但横条是**水平**结构：同一行里字影只占少数像素，行中位就是干净横条色。
    逐行取中位 → 纵向小半径平滑保住横条渐变 → 加极轻真实高频残差保颗粒。
    """
    x0, y0, x1, y1 = win
    rgb = arr[:, :, :3].astype(np.float32)
    q = rgb[y0:y1, x0:x1]
    # 每行中位（排除纯白字核，避免把字色拉进背景）
    rowmed = []
    for row in q:
        sel = (row.min(axis=1) < 225)
        rowmed.append(np.median(row[sel], axis=0) if sel.sum() > 8
                      else np.median(row, axis=0))
    rowmed = np.array(rowmed, np.float32)
    # 纵向 3 点滑动平均，消除逐行跳变
    k = np.ones(3) / 3.0
    smooth = np.stack([np.convolve(rowmed[:, c], k, mode="same")
                       for c in range(3)], axis=1)
    bg = np.repeat(smooth[:, None, :], x1 - x0, axis=1)
    out = rgb.copy()
    out[y0:y1, x0:x1] = np.clip(bg, 0, 255)
    # 不加任何来自原图的高频残差：原图残差里就含旧字笔画，
    # 叠回去等于把字影搬回来（方法论 B 组的「平移借用残差」坑）。
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)

    # ★ alpha 同样要重建：立体字影在 alpha 上就是一片高不透明区，
    # 只把 RGB 抹匀、留着字形 alpha，合成到深底上旧字照样显形。
    # 逐行取 alpha 中位 + 纵向平滑，保留横条上下的光晕渐变。
    aa = arr[y0:y1, x0:x1, 3].astype(np.float32)
    amed = np.median(aa, axis=1)
    asmo = np.convolve(amed, k, mode="same")
    res[y0:y1, x0:x1, 3] = np.clip(
        np.repeat(asmo[:, None], x1 - x0, axis=1), 0, 255).astype(np.uint8)
    return res


def dark_fill(arr, mask, win, gain=0.06):
    """深色/半透明底板上的亮字：只擦笔画，取窗内干净深色像素中位回填。

    与 flat_fill 的区别：不要求 lum>140、alpha>140（半透明深底两样都不满足）；
    保留原 alpha 通道，绝不整窗清 alpha（左侧紫框/红勾选框会被一起抹掉）。
    """
    x0, y0, x1, y1 = win
    q = arr[y0:y1, x0:x1]
    sel = (~mask[y0:y1, x0:x1]) & (q[:, :, 3] > 40)
    assert sel.sum() > 30, "深底样本区为空: %s" % (win,)
    color = np.median(q[:, :, :3][sel], axis=0)
    rgb = arr[:, :, :3].astype(np.float32)
    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    resid = (rgb - blur)[y0:y1, x0:x1][sel]
    rng = np.random.default_rng(20261115)
    yy, xx = np.where(mask)
    pick = resid[rng.integers(0, len(resid), len(yy))]
    out = rgb.copy()
    out[yy, xx] = np.clip(color + pick * gain, 0, 255)
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    return res


def dark_fill2(arr, mask, win, thresh=100, fill_all=False):
    """发光字专用：只填 mask 覆盖的像素，底板色从「非 mask 且暗」的像素取。

    与 dark_fill 的区别：dark_fill 的样本区不筛亮度，窗口里若有头像亮部、
    黄/粉光晕横带，中位会被拉亮，填出浅色补丁或发光横带。这里只取暗像素
    （即真正的底板），且**不整窗铺**，mask 外的菱形渐变 / 花卉纹 / 头像
    与金边逐像素保留。
    """
    x0, y0, x1, y1 = win
    q = arr[y0:y1, x0:x1]
    mm = mask[y0:y1, x0:x1]
    lum = q[:, :, :3].mean(axis=2)
    H = mm.shape[0]
    # 逐行取「非 mask 且暗」的底板中位：菱形是纵向渐变、花卉纹有层次，
    # 全窗口一个中位色会填出边界清晰的补丁框。
    cols, alphas = [], []
    for i in range(H):
        if fill_all:
            # 字与光晕都在窗口中央，左右两端是干净的菱形底色。
            # 从两端取每行底色，铺满后与菱形同色，不会出现偏亮的横条。
            sample = np.concatenate([q[i, :10], q[i, -10:]], axis=0)
            sel = (sample[:, 3] > 60) & (sample[:, :3].mean(axis=1) < thresh)
        else:
            sample = q[i]
            sel = (~mm[i]) & (q[i, :, 3] > 60) & (lum[i] < thresh)
        if sel.sum() >= 4:
            cols.append(np.median(sample[sel, :3], axis=0))
            alphas.append(float(np.median(sample[sel, 3])))
        else:
            cols.append(None)      # 整行被发光横带占满，用最近有效行插值
            alphas.append(None)
    valid = [i for i, c in enumerate(cols) if c is not None]
    assert valid, "暗底样本区为空: %s" % (win,)
    for i in range(H):
        if cols[i] is None:
            j = min(valid, key=lambda k: abs(k - i))
            cols[i], alphas[i] = cols[j], alphas[j]
    C = np.array(cols, np.float32)
    A = np.array(alphas, np.float32)
    # 纵向 3 点平滑，消除逐行跳变
    C = np.stack([np.convolve(C[:, c], np.ones(3) / 3.0, mode="same")
                  for c in range(3)], axis=1)
    A = np.convolve(A, np.ones(3) / 3.0, mode="same")
    out = arr.copy()
    sub = out[y0:y1, x0:x1]
    for i in range(H):
        if fill_all:
            # 整格铺满，颜色来自左右两端的真实底板；不与原图像素做羽化
            # 混合——混合会把旧字笔画/光晕又带回来。
            sub[i, :, :3] = np.clip(C[i], 0, 255).astype(np.uint8)
            sub[i, :, 3] = int(np.clip(A[i], 0, 255))
        else:
            sub[i, mm[i], :3] = np.clip(C[i], 0, 255).astype(np.uint8)
            sub[i, mm[i], 3] = int(np.clip(A[i], 0, 255))
    return out


def btn_fill(arr, mask, win):
    """圆形按钮补底：逐行取「非字笔画」像素 RGB 中位，只填 mask 内像素。

    按钮是径向渐变，整窗铺一个中位色会出色板；diffuse_texture 的低频
    外推又会mask 一大就把圆心亮色摊成浅色斑块。逐行中位既跟随渐变，
    又只改笔画覆盖的像素，圆周金边 / 勾号 / 方框图标逐点不动。
    """
    x0, y0, x1, y1 = win
    q = arr[y0:y1, x0:x1]
    mm = mask[y0:y1, x0:x1]
    Hh = mm.shape[0]
    cols = []
    for i in range(Hh):
        sel = (~mm[i]) & (q[i, :, 3] > 60)
        cols.append(np.median(q[i, sel, :3], axis=0) if sel.sum() >= 3
                    else None)
    valid = [i for i, c in enumerate(cols) if c is not None]
    if not valid:
        # 极窄窗口（方形按钮只有 15px 高、字几乎占满）：从窗口上下方
        # 各 5px 的真实底板像素取中位，绝不硬失败、也绝不铺出平板。
        ring = np.concatenate([
            arr[max(0, y0 - 5):y0, x0:x1].reshape(-1, 4),
            arr[y1:min(arr.shape[0], y1 + 5), x0:x1].reshape(-1, 4)], axis=0)
        ok = ring[:, 3] > 60
        fallback = (np.median(ring[ok, :3], axis=0) if ok.sum() >= 3
                    else np.median(q[:, :, :3].reshape(-1, 3), axis=0))
        cols = [fallback] * Hh
    else:
        for i in range(Hh):
            if cols[i] is None:
                j = min(valid, key=lambda k: abs(k - i))
                cols[i] = cols[j]
    C = np.stack([np.convolve(
        np.array([cols[i][c] for i in range(Hh)], np.float32),
        np.ones(5) / 5.0, mode="same") for c in range(3)], axis=1)
    # 两行 PLAY/LIST 窗口共用一个圆形按钮，各自逐行中位会在交界处
    # 取到不同底色，留下一条水平接缝（实测成品 y30~32 亮度从 86 骤降到
    # 32，原图没有）。补底色改为「该按钮整体」的中位：从窗口上下各
    # 扩 8px 取真实底板，两窗口取到同一批像素 → 底色一致，接缝消失。
    ring = np.concatenate([
        arr[max(0, y0 - 8):y1, x0:x1].reshape(-1, 4),
        arr[y0:min(arr.shape[0], y1 + 8), x0:x1].reshape(-1, 4)], axis=0)
    ok = ring[:, 3] > 60
    if ok.sum() >= 30:
        C[:] = np.median(ring[ok, :3], axis=0)
    out = arr.copy()
    sub = out[y0:y1, x0:x1]
    for i in range(Hh):
        sub[i, mm[i], :3] = np.clip(C[i], 0, 255).astype(np.uint8)
        # alpha 保持原图，不在圆形边缘造出不透明方块
    return out


# 紧框口径通用实现已抽到 glyph_unit.py（方法文档 1.3.1）。


def vert_flat(arr, win, orig=None, pad=8, thresh=100):
    """发光字整格重建：从窗口**上下方**（光晕之外）取菱形真实底色，纵向插值。

    orig=原图 RGBA 时，铺色严格限于**原图不透明的菱形轮廓内**：窗口是矩形，
    四个角本该透明，整窗铺满会把矩形棱角填成实色、超出菱形斜边（用户反馈
    「文字作为一块长方形放进去，棱角超出了菱形」）。菱形外的像素一律保持原图。
    """
    x0, y0, x1, y1 = win
    H = y1 - y0

    def med(s):
        ok = (s[:, 3] > 60) & (s[:, :3].mean(axis=1) < thresh)
        if ok.sum() < 10:
            ok = s[:, 3] > 60
        return np.median(s[ok, :3], axis=0), float(np.median(s[ok, 3]))

    top = arr[max(0, y0 - pad):y0, x0:x1].reshape(-1, 4)
    bot = arr[y1:min(arr.shape[0], y1 + pad), x0:x1].reshape(-1, 4)
    ct, at = med(top)
    cb, ab = med(bot)
    out = arr.copy()
    sub = out[y0:y1, x0:x1]
    # 只覆盖**完全不透明**的菱形内部。alpha 1..200 是菱形斜边的抗锯齿
    # 过渡，把它们也铺成实色会在尖角留下小方块（实测 488 px）。
    inside = (np.ones((H, x1 - x0), bool) if orig is None
              else orig[y0:y1, x0:x1, 3] > 200)
    for i in range(H):
        t = i / max(H - 1, 1)
        row = inside[i]
        sub[i, row, :3] = np.clip(ct * (1 - t) + cb * t, 0, 255).astype(np.uint8)
        sub[i, row, 3] = int(np.clip(at * (1 - t) + ab * t, 0, 255))
    return out


def grid_cells(cfg):
    """把行列网格展开成逐字单元；row=每行同组词，col=每列同组词。"""
    cells = []
    for ri, (y0, y1, cy) in enumerate(cfg["rows"]):
        for ci, (x0, x1) in enumerate(cfg["cols"]):
            word = cfg["words"][ci if cfg["axis"] == "row" else ri]
            fill = cfg["row_fills"][ri]
            cells.append(dict(win=(x0, y0, x1, y1),
                              center=((x0 + x1) / 2.0, cy),
                              word=word, fill=fill))
    return cells


def build_grids():
    """第三组：多状态按钮网格，逐格独立擦字/补底/落位。"""
    for cfg in C.GRIDS:
        A = load(cfg["name"])
        arr = A.copy()
        stroke = np.zeros(A.shape[:2], bool)
        mask = np.zeros(A.shape[:2], bool)
        cells = grid_cells(cfg)
        for cell in cells:
            w = cell["win"]
            x0, y0, x1, y1 = w
            q = A[y0:y1, x0:x1]
            lum = q[:, :, :3].mean(axis=2)
            # 只判「亮核」会漏掉整圈黄光/粉光，中文背后留下完整英文发光字影。
            # 改为相对该格底板亮度差：字核、抗锯齿、光晕一并纳入 mask。
            base_lum = float(np.median(lum))
            s = (lum > base_lum + 18) & (q[:, :, 3] > 60)
            full = np.zeros(A.shape[:2], bool)
            full[y0:y1, x0:x1] = s
            m = B.dilate(full, 5) & B.box_mask(A.shape, w, 1)
            if cfg.get("mode") == "transparent":
                # 透明底白字：整窗清 alpha，不补底（补底反而会造出一块色板）
                arr[y0:y1, x0:x1] = 0
            else:
                # 菱形/胶囊是渐变底：单色中位会填出一圈可见补丁框，
                # 用扩散低频跟住局部渐变（第一组红底花卉纹已验证）。
                arr = np.array(B.diffuse_texture(arr, m, radius=5,
                                                 resid_gain=0.60)).copy()
            stroke |= full
            mask |= m
        f = font(cfg["font_size"])
        for cell in cells:
            p = solid8(A.shape[:2][::-1], cell["word"], f, cfg["gap"],
                       cell["fill"], cfg["boost"])
            place8(arr, p, *cell["center"],
                   tag=cfg["name"] + "_" + cell["word"])
        allow = np.zeros(A.shape[:2], bool)
        for cell in cells:
            x0, y0, x1, y1 = cell["win"]
            allow[y0:y1, x0:x1] = True
        arr[~allow] = A[~allow]
        save(arr, cfg["name"])
        np.save(str(C.WORK_DIR / ("b8_%s_stroke.npy" % cfg["name"])), stroke)
        np.save(str(C.WORK_DIR / ("b8_%s_erase.npy" % cfg["name"])), mask)
        log("  %-22s → %d 格  擦除 %d px" %
            (cfg["name"], len(cells), int(mask.sum())))


# ============================================================================
# 第四~七组：通用「独立文字单元」处理器
# 每个单元按各自原 bbox 独立擦字、独立补底、独立落位；不跨单元串联。
# ============================================================================

def ink_mask(A, win, ink):
    """按文字颜色判型生成旧字笔画 mask（整图尺寸 bool）。

    ink 决定「什么是旧字」，与补底路线（flat/diffuse/clear）正交：
      dark         浅金/纸底上的深棕、深灰字
      light        深色横条上的浅字（绝对亮度阈值，不依赖中位）
      bright       深底亮字（相对中位亮度差）
      colored      红/粉字 ∪ 白描边（popup 第 3/4 列）
      white_orange 白字 ∪ 橙色描边（CHANGE 胶带）
    """
    x0, y0, x1, y1 = win
    q = A[y0:y1, x0:x1]
    r, g, b, al = q[:, :, 0], q[:, :, 1], q[:, :, 2], q[:, :, 3]
    lum = (r.astype(np.float32) + g + b) / 3.0
    if ink == "flat" or ink == "dark":
        base = float(np.median(lum[(al > 140)])) if (al > 140).any() else 200.0
        s = (lum < base - 32) & (al > 100)
    elif ink == "light":
        s = (lum > 150) & (al > 100)
    elif ink == "colored":
        # 红/粉字本身。白描边不单独判（纸底本身就是米白，会把整片纸卷进来），
        # 靠逐单元 dilate 把紧贴的描边一起纳入 mask。
        s = (r > 140) & (g < 140) & (b < 175) & (al > 90) & (r > g + 45)
    elif ink == "colored_rim":
        # 红/粉字 + 紧贴的白描边：先在整图算红字核，取其 7px 邻域环，
        # 环内的纯白像素才算描边。这样既擦掉整圈白边，又不会把整片米白纸
        # 卷进 mask（否则扩散补底会把纸当样本，摊出白色圆角亮块）。
        core = (r > 140) & (g < 140) & (b < 175) & (al > 90) & (r > g + 45)
        cf = np.zeros(A.shape[:2], bool)
        cf[y0:y1, x0:x1] = core
        near = B.dilate(cf, 7)[y0:y1, x0:x1]
        white = (r > 195) & (g > 190) & (b > 180) & (al > 120)
        s = core | (near & white)
    elif ink.startswith("dist"):
        # 相对「该格底板中位色」的颜色距离：字核、光晕、抗锯齿一起纳入，
        # 与底板是深蓝紫 / 深红 / 深色花卉纹无关。固定亮度阈值（light）
        # 会漏掉暖黄 / 粉色光晕，留下整条发光英文字影。
        # 阈值可写在 ink 名里（dist55），渐变菱形用高一点的值，避免把
        # 偏离中位的渐变底色误判成字、又被整格填回同色造成「假未擦除」。
        th = float(ink[4:]) if ink[4:].isdigit() else 40.0
        opaque = al > 150
        base = (np.median(q[:, :, :3][opaque], axis=0) if opaque.sum() > 30
                else np.median(q[:, :, :3], axis=0))
        dist = np.abs(q[:, :, :3].astype(np.float32) - base).mean(axis=2)
        s = (dist > th) & (al > 60)
    elif ink == "btn":
        # 实心圆/方按钮上的金/白字 + 紧贴的暗描边。
        # 「亮金字」用 gold 判据；「暗描边」是字形邻域内显著暗于该行
        # 局部低频背景的像素。只在亮字 5px 邻域内取，避免把圆的径向
        # 渐变 / 圆周金边 / 下方勾与方框图标卷进 mask（dilate 7 的教训）。
        bright = (g > 105) & (r > 120) & (al > 120)
        f = np.zeros(A.shape[:2], bool)
        f[y0:y1, x0:x1] = bright
        near = B.dilate(f, 5)[y0:y1, x0:x1]
        lm = (r.astype(np.float32) + g + b) / 3.0
        bgm = np.array(Image.fromarray(np.clip(lm, 0, 255)
                                       .astype(np.uint8), "L")
                       .filter(ImageFilter.GaussianBlur(4))).astype(np.float32)
        rim = near & (lm < bgm - 18) & (al > 100)
        s = bright | rim
    elif ink == "btngold":
        # 圆/方按钮两种状态字体不同：暗态是金字 [176,149,92]，亮态（红底）
        # 是近白字 [255,235,235]，后者 b 很高，纯金字判据 g>b+8 会漏掉，
        # 成品会留下一条白色 PLAY/LIST。用「绝对亮度 ∪ 金色」联合判据。
        # 试过自适应底板阈值想连暗金投影一起擦，结果把方格金框也卷进
        # mask 擦出缺口、又带出抗锯齿噪点，反而差于用户已认可的基线。
        lumi = (r.astype(np.float32) + g + b) / 3.0
        s = ((lumi > 155) | ((r > 120) & (g > 100) & (g > b + 8))) & (al > 120)
    elif ink == "labelgold":
        # 透明底标签金字；band 已避开 y331/y360 两条贯穿金线。
        s = (r > 120) & (g > 100) & (al > 120) & (g > b + 8)
    elif ink == "glowband":
        # 发光菱形：逐行取「该行暗底板中位」，与底色差异 >26 的像素即
        # 旧字 + 光晕 + 抗锯齿。band 放大到字 bbox±10 才能把整片英文光晕
        # 擦净；此时菱形内框金线会落进 band，用「局部亮像素密度」把它们
        # 摘出来保护 —— 金线是 2px 细线（7×7 邻域亮像素占比 <0.32），
        # 字/光晕是成片亮区（占比高），两者不会混淆。
        s = np.zeros(r.shape, bool)
        allop = q[:, :, 3] > 150
        fallback = (np.median(q[:, :, :3][allop], axis=0)
                    if allop.sum() > 20 else np.array([40, 30, 70]))
        for i in range(r.shape[0]):
            row = q[i]
            lumi = row[:, :3].mean(axis=1)
            dark = (row[:, 3] > 150) & (lumi < 110)
            bg = (np.median(row[dark, :3], axis=0) if dark.sum() >= 4
                  else fallback)
            d = np.abs(row[:, :3].astype(np.float32) - bg).mean(axis=1)
            s[i] = (d > 26) & (row[:, 3] > 50)
        dens = np.array(
            Image.fromarray((s * 255).astype(np.uint8), "L")
            .filter(ImageFilter.BoxBlur(3)), dtype=np.float32) / 255.0
        goldline = ((r > 140) & (g > 110) & (b < 180) & (al > 200))
        s &= ~(goldline & (dens < 0.32))
    elif ink == "gold":
        # 实心圆/方按钮上的金/白字：g 通道显著高于深蓝紫底与红底。
        # 不削边：窗口已严格贴住原文字墨迹 bbox，圆周金边与下方图标都在
        # 窗口之外；再削边反而会把窗口边缘的旧字母笔画留下来。
        s = (g > 105) & (r > 120) & (al > 120)
    elif ink == "white":
        # CHANGE 白字：橙横条 g≈106，用 g/b 下限把它排除，只留纯白笔画
        s = (r > 175) & (g > 155) & (b > 145) & (al > 110)
    elif ink == "band_all":
        # 文字带整块重建：白字、橙色立体投影、橙色横条同色系，无法靠颜色
        # 区分。直接把整窗纳入 mask，交给 column_fill 按列从上下沿真实像素
        # 插值——横条是水平渐变，能保住层次，且字影绝不会残留。
        s = np.ones(r.shape, bool) & (al > 0)
    elif ink == "white_orange":
        white = (r > 175) & (g > 155) & (b > 145) & (al > 110)
        orange = (r > 130) & (g < 135) & (b < 90) & (al > 110)
        s = white | orange
    else:  # bright / clear / diffuse
        base = float(np.median(lum)) if lum.size else 40.0
        s = (lum > base + 22) & (al > 60)
    full = np.zeros(A.shape[:2], bool)
    full[y0:y1, x0:x1] = s
    return full


def build_cells():
    for cfg in C.CELLS:
        A = load(cfg["name"])
        assert A.shape[1::-1] == cfg["size"], \
            "%s 尺寸不符 %s" % (cfg["name"], A.shape)
        arr = A.copy()
        stroke = np.zeros(A.shape[:2], bool)
        mask = np.zeros(A.shape[:2], bool)
        kind = cfg["kind"]
        f = font(cfg["font_size"])
        # 原图 alpha 轮廓（菱形 / 圆形按钮）：贴片落位前按它软裁，
        # 中文与光晕的方形棱角就不会超出原图形状。边缘 1.2px 羽化。
        if any(u.get("shape") for u in cfg["units"]):
            sil = (A[:, :, 3] > 20).astype(np.uint8) * 255
            shape = np.array(Image.fromarray(sil, "L")
                             .filter(ImageFilter.GaussianBlur(1.2)),
                             dtype=np.float32) / 255.0
        else:
            shape = None

        for u in cfg["units"]:
            w = u["win"]
            band = u.get("band", w)
            x0, y0, x1, y1 = w
            k = u.get("kind", kind)
            ink = u.get("ink", k)
            if ink == "glowband":
                # 发光菱形走专用 glow_glyph（上下干净行取底色），
                # 不能用逐行左右取样的 ink_mask。
                full = np.zeros(A.shape[:2], bool)
                m = np.zeros(A.shape[:2], bool)
            else:
                full = ink_mask(A, band, ink)
                m = B.dilate(full, u.get("dilate", 3)) & \
                    B.box_mask(A.shape, band, u.get("pad", 1))
            if k == "flat":
                arr = np.array(B6.flat_fill(arr, m, w, gain=0.10)).copy()
            elif k == "clear":
                # 整窗清 alpha，不补底（深底/透明底补底会造出一块色板）
                arr[y0:y1, x0:x1] = 0
                # clear 路线的「旧字」= 窗内原不透明像素；mask 记整窗，
                # 否则 stroke 恒为空，自检「旧字擦除率」分母为 0 假失败
                full = np.zeros(A.shape[:2], bool)
                full[y0:y1, x0:x1] = A[y0:y1, x0:x1, 3] > 60
                m = B.box_mask(A.shape, w, 0)
            elif k == "band":
                # 橙色横条 + 同色立体字影：整条文字带按行中位色重建，
                # 字影（少数像素）被中位滤掉，横条渐变由纵向平滑保留。
                arr = tape_rebuild(arr, w)
            elif k == "darkfill":
                # 深色底板亮字：只擦笔画，用窗内真实深色像素中位回填，
                # 保留深色底板与相邻红/紫勾选框（整窗清 alpha 会毁掉它们）
                arr = dark_fill(arr, m, w, gain=0.06)
            elif k == "darkfill_dark":
                # 发光字（光晕横带 / 头像亮部会污染中位）：只取暗底板样本
                arr = dark_fill2(arr, m, w)
            elif k == "stroke":
                # 【只擦笔画，不铺平整格】人名牌是深色花卉纹 + 角色头像，
                # 中文比原名短时，被铺平的区域就会空出一块突兀的平板。
                # 正解：mask 只覆盖亮字笔画，扩散从笔画外围真实纹理插值回填，
                # 未被 mask 覆盖的像素逐点保持原图（花卉纹、头像、金边全在）。
                # resid_gain 由单元指定：花卉纹需要一点颗粒（0.75），
                # 圆形按钮必须 0 —— 原图残差里含旧字母笔画，叠回去就是
                # 用户反馈的「英文没擦干净」（方法文档 B 组记过这个坑）。
                arr = np.array(B.diffuse_texture(
                    arr, m, radius=4,
                    resid_gain=u.get("resid", 0.75))).copy()
            elif k == "btnfill":
                # 圆形按钮：逐行中位、只填笔画像素，不低频外推、不铺整窗
                arr = btn_fill(arr, m, w)
            elif k == "glyph":
                # 【只重绘字形像素，不铺矩形】band 内按颜色判据找旧字/光晕，
                # 逐像素从邻近真实底板取色回填；band 外（菱形内框线、圆周
                # 金边、方形金框、标签金线、勾选/方框图标）一律不动。
                if ink == "glowband":
                    arr, em = glow_glyph(arr, A, band, u["center"],
                                         u.get("frame"), u.get("dilate", 3))
                else:
                    em = B.dilate(full, u.get("dilate", 3)) & \
                        B.box_mask(A.shape, band, 0)
                if u.get("protect_border"):
                    bx0, by0, bx1, by1 = band
                    qb = A[by0:by1, bx0:bx1]
                    goldline = ((qb[:, :, 0] > 135) & (qb[:, :, 1] > 105) &
                                (qb[:, :, 2] < 180) & (qb[:, :, 3] > 200))
                    n = int(u["protect_border"])
                    edge = np.zeros(goldline.shape, bool)
                    edge[:n, :] = edge[-n:, :] = True
                    edge[:, :n] = edge[:, -n:] = True
                    prot = np.zeros(A.shape[:2], bool)
                    prot[by0:by1, bx0:bx1] = goldline & edge
                    em &= ~prot
                if ink != "glowband":
                    arr = glyph_fill(arr, A, em, band,
                                     transparent=u.get("transparent", False))
                full = em.copy()          # stroke 记实际擦掉的字形像素
                m = B.box_mask(A.shape, w, 0)   # erase 记允许区（自检用）
            elif k == "rowflat":
                # 菱形发光字：从窗口上下方干净底板取色，纵向插值整格铺满。
                # stroke 仍记 dist mask（旧字 + 光晕），这些像素会被整格
                # 重建改掉；erase 记整窗。不能把 stroke 也记成整窗——
                # 整窗里大量像素本来就是菱形底色，填回同色不算改动，
                # 会把「旧字擦除率」稀释到 0.72 造成假失败。
                arr = vert_flat(arr, w, orig=A)   # 只填原图菱形轮廓内
                m = B.box_mask(A.shape, w, 0)
            else:
                arr = np.array(B.diffuse_texture(arr, m, radius=4,
                                                 resid_gain=0.55)).copy()
            stroke |= full
            mask |= m

        # 逐单元独立落位（每格自己的 center，不合并、不串联）
        for u in cfg["units"]:
            uf = font(u["font_size"]) if "font_size" in u else f
            fill = u.get("fill", cfg["fill"])
            if u.get("glow"):
                # 发光字：逐单元自带光晕色与强度（config_index 三态、人名牌粉光）
                p = B.make_glow_patch(A.shape[:2][::-1], u["word"], uf,
                                      cfg["gap"], fill, u["glow"],
                                      u.get("gain", 1.0),
                                      u.get("boost", cfg["boost"]))
            else:
                p = solid8(A.shape[:2][::-1], u["word"], uf, cfg["gap"],
                           fill, u.get("boost", cfg["boost"]))
            clip = None
            shape_arg = shape if u.get("shape") else None
            if u.get("soft_shape"):
                # 发光态：按中文字形软掩膜淡出光晕，不用矩形 clip 硬裁。
                shape_arg = soft_patch_shape(
                    p, u["center"][0], u["center"][1],
                    (A.shape[1], A.shape[0]))
            elif u.get("clip_pad") is not None:
                # 事前框 = 渲染后中文墨迹 bbox + pad，方块完全贴合中文字形，
                # 不再沿用「原英文窗口」这种远大于字的矩形。
                clip = tight_clip(p, u["center"][0], u["center"][1],
                                  u["clip_pad"])
                w = u["win"]
                assert (clip[0] >= w[0] and clip[1] >= w[1] and
                        clip[2] <= w[2] and clip[3] <= w[3]), \
                    "%s/%s 中文贴片框越出允许窗口: clip=%s win=%s" % (
                        cfg["name"], u["word"], clip, w)
            elif u.get("clip"):
                clip = u["win"]
            place8(arr, p, *u["center"],
                   tag=cfg["name"] + "_" + u["word"],
                   clip=clip, shape=shape_arg)

        allow = np.zeros(A.shape[:2], bool)
        H, W = A.shape[:2]
        for u in cfg["units"]:
            x0, y0, x1, y1 = u["win"]
            # 夹紧坐标：负 y 会被 numpy 当成「从末尾数」的反向切片，
            # 把 allow 写空、成品上沿被还原成英文（本轮实测坑）。
            allow[max(0, y0):min(H, y1), max(0, x0):min(W, x1)] = True
        # 注意：不要用「按原图还原窗口边缘金色像素」来保金边。金边与旧英文
        # 笔画同色，那样会把已擦掉的字母一起放回来（用户反馈「英文没擦干净
        # 就贴上中文」）。正确做法是窗口本身严格贴住文字墨迹 bbox、避开圆周
        # 金边与下方图标，一次擦净，不做任何事后还原。
        arr[~allow] = A[~allow]          # 窗口外 0 改动
        save(arr, cfg["name"])
        np.save(str(C.WORK_DIR / ("b8_%s_stroke.npy" % cfg["name"])), stroke)
        np.save(str(C.WORK_DIR / ("b8_%s_erase.npy" % cfg["name"])), mask)
        log("  %-24s → %-2d 单元 擦除 %d px  [%s]" %
            (cfg["name"], len(cfg["units"]), int(mask.sum()), kind))


def build_glow_groups():
    """透明底多状态发光字：整行清 alpha，逐行配色重画，逐词独立归位。"""
    for cfg in C.GLOW_GROUPS:
        A = load(cfg["name"])
        arr = A.copy()
        stroke = np.zeros(A.shape[:2], bool)
        clear = np.zeros(A.shape[:2], bool)
        x0, x1 = cfg["clear_x"]
        for row in cfg["rows"]:
            y0, y1 = row["y0"], row["y1"]
            stroke[y0:y1, x0:x1] = A[y0:y1, x0:x1, 3] > 100
            arr[y0:y1, x0:x1] = 0
            clear[y0:y1, x0:x1] = True
            # 【方法文档 3.2 第 2 步：仅下沿 N 行按「逐行中位」补回光晕】
            # 大字带整块清 0 会连下沿的大字辉光尾巴一起抹掉，形成一段
            # 透明黑带。但只补这几行、且用「逐行排除字形亮部后的中位」：
            # 这几行是纯光晕（无字形笔画），中位就是真实光晕色，不会
            # 搬回英文字形，也不会像整行铺满那样变成实心色带。
            # 权重自上而下线性升到 1，与 keep 区原图光晕无缝衔接。
            N = cfg.get("glow_tail", 0)
            if N:
                band = A[y1 - N:y1, x0:x1].astype(np.float32)
                lum = band[:, :, :3].mean(axis=2)
                for k in range(N):
                    ok = band[k, :, 3] > 40
                    med = np.median(lum[k][ok]) if ok.any() else 0.0
                    sel = ok & (lum[k] < med + 32)
                    c = (np.median(band[k][sel], axis=0) if sel.sum() > 30
                         else np.median(band[k][ok], axis=0) if ok.any()
                         else 0.0)
                    w = (k + 1) / float(N + 1)
                    arr[y1 - N + k, x0:x1] = np.clip(
                        c * w, 0, 255).astype(np.uint8)

        f = font(cfg["font_size"])
        shape = A.shape[:2][::-1]
        wf = cfg.get("word_fills")
        wg = cfg.get("word_glows")
        # 【严格框定文字界限】逐词 bbox：以相邻词中心的中点分界，
        # 每个中文只落在自己那个词的格子里，横向不串到邻词、纵向不越到
        # 下方日文小字带。整行矩形 clip 的 x 方向等于没框（0..全宽）。
        cxs = [w[2] for w in cfg["words"]]
        bounds = [x0] + [(cxs[i] + cxs[i + 1]) / 2.0
                         for i in range(len(cxs) - 1)] + [x1]
        for row in cfg["rows"]:
            for wi, (key, word, cx) in enumerate(cfg["words"]):
                clip = ((int(bounds[wi]), row["y0"], int(bounds[wi + 1]),
                         row["y1"]) if cfg.get("clip_rows") else None)
                fill = wf[wi] if wf else row["fill"]
                glow = (wg[wi] if wg else (wf[wi] if wf else row["glow"]))
                if row["gain"] <= 0.6 and not wf:
                    p = outline8(shape, word, f, cfg["gap"], fill, row["boost"])
                else:
                    p = B.make_glow_patch(shape, word, f, cfg["gap"],
                                          fill, glow, row["gain"], row["boost"])
                place8(arr, p, cx, row["cy"], tag="%s_%s" % (key, row["y0"]),
                       clip=clip, fade_bottom=cfg.get("fade_bottom", 0))

        arr[~clear] = A[~clear]
        # HELP 木牌金字（仅 tutorial_help_p）：红底花卉纹走扩散补底
        if cfg["name"] == "tutorial_help_p":
            t = C.HELP_TITLE
            x0, y0, x1, y1 = t["win"]
            q = A[y0:y1, x0:x1]
            # 红底花卉纹 g≈20，金字与其暗金衬线描边 g>90。
            # 用 G 通道把整圈描边一起纳入 mask（只判纯亮金会留虚线轮廓）。
            gm = ((q[:, :, 1] > 88) & (q[:, :, 0] > 110) &
                  (q[:, :, 2] < 190) & (q[:, :, 3] > 100))
            # 衬线大字外圈还有一层深色描边/阴影，只判金色会留下细虚线。
            # 在「字形 9px 邻域内」把显著暗于局部背景的像素一并纳入，
            # 远处花卉纹的深色花瓣不受影响。
            lum = q[:, :, :3].mean(axis=2)
            bg = np.array(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8), "L")
                          .filter(ImageFilter.GaussianBlur(3))).astype(np.float32)
            core = np.zeros(A.shape[:2], bool)
            core[y0:y1, x0:x1] = gm
            near = B.dilate(core, 9)[y0:y1, x0:x1]
            dark_rim = (lum < bg - 26) & (q[:, :, 3] > 100) & near
            ha = np.zeros(A.shape[:2], bool)
            ha[y0:y1, x0:x1] = gm | dark_rim
            ha = B.dilate(ha, 3) & B.box_mask(A.shape, t["win"], 1)
            # 与第一组木牌同工艺：只擦笔画，扩散从窗外真实红底纹理插值，
            # 绝不整块矩形清零（那样扩散补不回中心，出现深色矩形补丁）。
            patch = np.array(B.diffuse_texture(A, ha, radius=7,
                                               resid_gain=0.85)).copy()
            hf = font(t["font_size"])
            hp = solid8(shape, t["word"], hf, C.TITLE_STYLE["gap"],
                        C.TITLE_STYLE["fill"], C.TITLE_STYLE["boost"])
            place8(patch, hp, *t["center"], tag="HELP")
            allow = B.box_mask(A.shape, t["win"], 0)
            arr = np.where(allow[:, :, None], patch, arr).astype(np.uint8)
            stroke |= ha
            clear |= allow
            arr[~clear] = A[~clear]

        # 日文假名副标题带硬禁区：即使上面任何一步溢出，这里也逐像素还原。
        # 必须放在 HELP 特例之后，否则会把 tutorial_help_p 的木牌中文一起擦掉。
        if cfg.get("strict_keep"):
            for kx0, ky0, kx1, ky1 in cfg["keep"]:
                arr[ky0:ky1, kx0:kx1] = A[ky0:ky1, kx0:kx1]

        save(arr, cfg["name"])
        np.save(str(C.WORK_DIR / ("b8_%s_stroke.npy" % cfg["name"])), stroke)
        np.save(str(C.WORK_DIR / ("b8_%s_erase.npy" % cfg["name"])), clear)
        log("  %-24s → %d 行 × %d 词  清除 %d px" %
            (cfg["name"], len(cfg["rows"]), len(cfg["words"]), int(clear.sum())))


def main():
    log("字体:", C.SERIF)
    log("戦巫 UI 第一批 · 累计 %d 张（前三组 %d + 通用单元 %d + 发光组 %d）" %
        (len(C.ALL_NAMES), 5 + len(C.LABELS) + len(C.GRIDS),
         len(C.CELLS), len(C.GLOW_GROUPS)))
    build_titles()
    build_sys(C.SYS_QUIT)
    build_sys(C.SYS_BACK)
    build_labels()
    build_grids()
    build_cells()
    build_glow_groups()
    log("完成，输出 ->", C.DST_DIR)


if __name__ == "__main__":
    main()
