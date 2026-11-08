# -*- coding: utf-8 -*-
"""
追加任务五 + 任务六（8 张）的汉化生成器。运行：在 工具/ 目录执行 python build_batch6.py

沿用「先量后画」骨架，但本批把落位合成换成 place6：上一批的 place 在
贴片平移量较大时会从边界分支直接返回底图（静默漏字），这里逐像素合成并断言。
"""
import numpy as np
from PIL import Image, ImageFilter

import config_batch6 as C
import build_batch4 as B          # 复用 font / 判据 / 三种补底


def log(*a):
    print(*a, flush=True)


def load(name):
    return np.array(Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")).astype(np.uint8)


def save(arr, name):
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    out.save(C.DST_DIR / (name + ".png"))
    return out


def font(sz):
    if C.SERIF is None:
        raise RuntimeError("找不到宋体，请改 config_batch6.SERIF_CANDIDATES")
    return __import__("PIL.ImageFont", fromlist=["truetype"]).truetype(C.SERIF, sz)


def place6(base, patch, cx, cy, tag=""):
    """逐像素 straight-alpha 合成，带边界裁剪；断言确实画上了字。"""
    a = np.array(patch).copy()
    al = a[:, :, 3]
    ys, xs = np.nonzero(al > 60)
    assert len(xs), tag + " 贴片无墨迹"
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    dx = int(round(cx - (x0 + x1) / 2.0))
    dy = int(round(cy - (y0 + y1) / 2.0))
    H, W = base.shape[:2]
    yy, xx = np.nonzero(al > 0)
    tx, ty = xx + dx, yy + dy
    ok = (tx >= 0) & (tx < W) & (ty >= 0) & (ty < H)
    assert ok.sum() > 30, "%s 落位越界 (%d,%d)" % (tag, dx, dy)
    tx, ty, sy, sx = tx[ok], ty[ok], yy[ok], xx[ok]
    src = a[sy, sx].astype(np.float32)
    sa = src[:, 3:4] / 255.0
    ba = base[ty, tx, 3:4].astype(np.float32) / 255.0
    oa = sa + ba * (1 - sa)
    orgb = (src[:, :3] * sa + base[ty, tx, :3].astype(np.float32) * ba * (1 - sa)) \
           / np.maximum(oa, 1e-6)
    base[ty, tx, :3] = np.clip(orgb, 0, 255).astype(np.uint8)
    base[ty, tx, 3:4] = np.clip(oa * 255, 0, 255).astype(np.uint8)


def solid(shape, word, st):
    return B.make_solid_patch(shape, word, font(st["font_size"]), st["gap"],
                              dict(fill=st["fill"],
                                   outline=st.get("outline"),
                                   outline_a=st.get("outline_a", 0),
                                   boost=st["boost"]))


def record(name, key, mask, union=False):
    p = C.WORK_DIR / ("b6_%s_%s.npy" % (name, key))
    if union and p.exists():
        mask = np.load(str(p)) | mask
    np.save(str(p), mask)


def local_dark(A, win, thr=35, rad=6, min_lum=None):
    """纸片/木牌上的暗字：局部高斯背景减亮度，只取真正的笔画。"""
    x0, y0, x1, y1 = win
    q = A[y0:y1, x0:x1]
    lum = q[:, :, :3].mean(axis=2)
    bg = np.array(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8), "L")
                  .filter(ImageFilter.GaussianBlur(rad))).astype(np.float32)
    m = (bg - lum > thr) & (q[:, :, 3] > 200)
    if min_lum is not None:
        m &= lum > min_lum          # 木牌边缘焦斑比字更黑，用亮度下限排掉
    full = np.zeros(A.shape[:2], bool)
    full[y0:y1, x0:x1] = m
    return full


def white_or_dark(A, win, dilate_k=5):
    """
    青色笔刷上的白字 + 深色描边，取并集后膨胀。

    白判据必须放宽到 130：原衬线字有一圈 r≈150 的抗锯齿，用 170 会漏掉，
    它们留在 known 里被 column_fill 的环残差采样，补出一圈白点
    （dialog BLOCK JUMP 首版就是这个毛病）。
    """
    x0, y0, x1, y1 = win
    q = A[y0:y1, x0:x1]
    white = ((q[:, :, 0] > 130) & (q[:, :, 1] > 135) &
             (q[:, :, 2] > 130) & (q[:, :, 3] > 120))
    # 暗判据只收极黑的描边，别放到 90：笔刷本身的深色噪点会整片入选，
    # 膨胀后 mask 连成一整条，补底就把笔刷纹理磨平了。
    dark = (q[:, :, :3].mean(axis=2) < 45) & (q[:, :, 3] > 150)
    stroke = np.zeros(A.shape[:2], bool)
    stroke[y0:y1, x0:x1] = white | dark
    return stroke, B.dilate(stroke, dilate_k) & B.box_mask(A.shape, win, 1)


def _local_mask(shape, win, local, k=3):
    """把窗口内的二值图膨胀后限制回窗口，不越界污染相邻元素。"""
    x0, y0, x1, y1 = win
    full = np.zeros(shape[:2], bool)
    full[y0:y1, x0:x1] = local
    return B.dilate(full, k) & B.box_mask(shape, win, 1)


def cell_fill(A, win, gain=0.45):
    """
    均匀纸片 / 胶带上的小字：整窗按列重填。

    局部暗差只抓笔画核心，抗锯齿边缘留在 known 里，2D 扩散会把它们的
    亮度一起摊开，中文背后就浮出一圈英文残影（panel 首版 Information /
    SCALING、dialog MARKING 都翻过车）。整窗重填最干净：窗口上下沿都在
    同一张纸片内，按列插值的端点颜色一致，不会留下字影或补丁。
    """
    return B.column_fill(A, B.box_mask(A.shape, win), resid_gain=gain)


def flat_fill(arr, mask, win, gain=0.15, color=None):
    """
    纸片上的字：取窗口内「不是字、也不是暗装饰」的纸色中位 + 高频残差平铺。

    按列插值会取窗口上下两行真实像素，一旦下沿压到黑色表格 / 绿色面板
    就摊出深色矩形（dialog MARKING）；整窗重填又会把纸片横条的两端切出
    色差（panel SCALING）。平铺不依赖端点，窗口外的纸片纹理一律保留。
    """
    x0, y0, x1, y1 = win
    q = arr[y0:y1, x0:x1]
    lum = q[:, :, :3].mean(axis=2)
    sel = (~mask[y0:y1, x0:x1]) & (q[:, :, 3] > 150) & (lum > 140)
    assert sel.sum() > 50, "纸片样本区为空: %s" % (win,)
    rgb = arr[:, :, :3].astype(np.float32)
    if color is None:
        color = np.median(q[:, :, :3][sel], axis=0)
    else:
        color = np.array(color, np.float32)
    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    resid = (rgb - blur)[y0:y1, x0:x1][sel]
    rng = np.random.default_rng(20261108)
    yy, xx = np.where(mask)
    pick = resid[rng.integers(0, len(resid), len(yy))]
    out = rgb.copy()
    out[yy, xx] = np.clip(color + pick * gain, 0, 255)
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    return res


def tape_fill(arr, mask, sample_win, gain=0.60):
    """浅棕胶带上的深红字：取胶带干净区的中位色 + 同区高频残差回填。"""
    rgb = arr[:, :, :3].astype(np.float32)
    x0, y0, x1, y1 = sample_win
    q = arr[y0:y1, x0:x1]
    m = ((q[:, :, 0] > 140) & (q[:, :, 1] > 110) & (q[:, :, 2] < 175) &
         (q[:, :, 0] > q[:, :, 2] + 30) & (q[:, :, 3] > 150))
    assert m.sum() > 30, "胶带样本区为空"
    color = np.median(q[:, :, :3][m], axis=0)
    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    resid = (rgb - blur)[y0:y1, x0:x1][m]
    rng = np.random.default_rng(20261108)
    yy, xx = np.where(mask)
    pick = resid[rng.integers(0, len(resid), len(yy))]
    out = rgb.copy()
    out[yy, xx] = np.clip(color + pick * gain, 0, 255)
    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    return res


# ---------------------------------------------------------------- 1 title
def build_title():
    cfg = C.TITLE
    A = load(cfg["name"])
    stroke = local_dark(A, cfg["win"], 45, 8, min_lum=45)
    mask = B.dilate(stroke, 5) & B.box_mask(A.shape, cfg["win"], 2)
    clean = B.diffuse_texture(A, mask, radius=5)
    arr = np.array(clean).copy()
    p = solid(A.shape[:2][::-1], cfg["word"], cfg["style"])
    place6(arr, p, *cfg["center"], tag="title")
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", stroke)
    record(cfg["name"], "erase", mask)
    log("  title          FLOWCHART → 流程图   擦除 %5d px" % int(mask.sum()))


# ---------------------------------------------------------------- 2 quit
def build_quit():
    cfg = C.QUIT
    A = load(cfg["name"])
    mask = np.zeros(A.shape[:2], bool)
    stroke_all = np.zeros(A.shape[:2], bool)
    cells = []
    for ry in cfg["rows"]:
        for ci, x0 in enumerate(cfg["cols"]):
            win = (x0 + 4, ry + 3, x0 + 106, ry + 35)
            s, m = white_or_dark(A, win, 3)
            stroke_all |= s
            mask |= m
            cells.append((win, cfg["words"][ci], cfg["centers_x"][ci]))
    clean = B.button_inpaint(A, mask, gain=0.45, iters=260)
    arr = np.array(clean).copy()
    shape = A.shape[:2][::-1]
    for i, (win, word, cx) in enumerate(cells):
        p = solid(shape, word, cfg["style"])
        place6(arr, p, cx, (win[1] + win[3]) / 2.0, tag="quit%d" % i)
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", stroke_all)
    record(cfg["name"], "erase", mask)
    log("  quit           3 词 × 3 行          擦除 %5d px" % int(mask.sum()))


# ---------------------------------------------------------------- 3 rate
def build_rate():
    cfg = C.RATE
    A = load(cfg["name"])
    x0, y0, x1, y1 = cfg["win"]
    q = A[y0:y1, x0:x1]
    m = ((q[:, :, 0] < 150) & (q[:, :, 1] < 90) &
         (q[:, :, 2] < 90) & (q[:, :, 3] > 150))
    stroke = np.zeros(A.shape[:2], bool)
    stroke[y0:y1, x0:x1] = m
    mask = _local_mask(A.shape, cfg["win"], m, 3)
    clean = tape_fill(A, mask, cfg["tape_sample"], gain=0.55)
    arr = np.array(clean).copy()
    p = solid(A.shape[:2][::-1], cfg["word"], cfg["style"])
    place6(arr, p, *cfg["center"], tag="rate")
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", stroke)
    record(cfg["name"], "erase", mask)
    log("  rate           Flow → 流程          擦除 %5d px" % int(mask.sum()))


# ---------------------------------------------------------------- 4 chart_parts
def build_chart_parts():
    cfg = C.CHART_PARTS
    A = load(cfg["name"])
    arr = A.copy()
    x0, y0, x1, y1 = cfg["erase_win"]
    stroke = np.zeros(A.shape[:2], bool)
    q = A[y0:y1, x0:x1]
    stroke[y0:y1, x0:x1] = ((q[:, :, 0] > 175) & (q[:, :, 1] > 175) &
                            (q[:, :, 2] > 175) & (q[:, :, 3] > 140))
    arr[y0:y1, x0:x1] = 0
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", stroke)
    record(cfg["name"], "erase", B.box_mask(A.shape, cfg["erase_win"]))
    log("  chart_parts    「日目」→ 只留「日」  擦除 %5d px" % int(stroke.sum()))


# ---------------------------------------------------------------- 5 dialog
def build_dialog():
    cfg = C.DIALOG
    A = load(cfg["name"])
    # 纸片标题：低阈值局部暗差把抗锯齿一起收进 mask，再按列补底。
    # 整窗重填会把窗口下沿的黑色表格卷进来，摊出一块深灰斜纹矩形（首版翻车）。
    sm = local_dark(A, cfg["mark_win"], 12, 5)
    mm = B.dilate(sm, 5) & B.box_mask(A.shape, cfg["mark_win"], 0)
    # 三行笔刷：白字 + 抗锯齿 + 极黑描边，调和补底不出竖条
    sj = np.zeros(A.shape[:2], bool)
    mj = np.zeros(A.shape[:2], bool)
    jump_cells = []
    for ry in cfg["jump_rows"]:
        win = (cfg["jump_win_x"][0], ry + 3, cfg["jump_win_x"][1], ry + 34)
        s, m = white_or_dark(A, win)
        sj |= s
        mj |= m
        jump_cells.append((win, (win[1] + win[3]) / 2.0))
    clean = B.button_inpaint(A, mj, gain=0.45, iters=260)
    clean = flat_fill(np.array(clean), mm, cfg["mark_win"])
    arr = np.array(clean).copy()
    shape = A.shape[:2][::-1]
    p = solid(shape, "标记", cfg["mark_style"])
    place6(arr, p, *cfg["mark_center"], tag="dialog_mark")
    for i, (win, cy) in enumerate(jump_cells):
        p = solid(shape, "方块跳转", cfg["jump_style"])
        place6(arr, p, cfg["jump_center_x"], cy, tag="dialog_jump%d" % i)
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", sm | sj)
    record(cfg["name"], "erase", mm | mj)
    log("  dialog         MARKING + 3 行 JUMP  擦除 %5d px" % int((mm | mj).sum()))


# ---------------------------------------------------------------- 6 panel
def build_panel():
    cfg = C.PANEL
    A = load(cfg["name"])
    stroke = np.zeros(A.shape[:2], bool)
    mask = np.zeros(A.shape[:2], bool)
    clean = A.copy()
    for lb in cfg["labels"]:
        s = local_dark(A, lb["win"], 12, 5)
        m = B.dilate(s, 5) & B.box_mask(A.shape, lb["win"], 1)
        stroke |= s
        mask |= m
        clean = flat_fill(np.array(clean), m, lb["win"],
                          color=lb.get("fill_color"))
    arr = np.array(clean).copy()
    shape = A.shape[:2][::-1]
    for lb in cfg["labels"]:
        st = dict(lb["style"])
        st.update(font_size=lb["font_size"], gap=lb["gap"])
        p = solid(shape, lb["word"], st)
        place6(arr, p, *lb["center"], tag="panel_" + lb["tag"])
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", stroke)
    record(cfg["name"], "erase", mask)
    log("  panel          4 个纸片标签         擦除 %5d px" % int(mask.sum()))


# ---------------------------------------------------------------- 7 confirm_parts
def build_confirm():
    cfg = C.CONFIRM
    A = load(cfg["name"])
    stroke = np.zeros(A.shape[:2], bool)
    mask = np.zeros(A.shape[:2], bool)
    for w in cfg["wins"]:
        x0, y0, x1, y1 = w
        q = A[y0:y1, x0:x1]
        # 中性浅色才算白字，避免把左边的青色小方块选进来
        light = ((q[:, :, 0] > 140) & (q[:, :, 1] > 140) &
                 (q[:, :, 2] > 140) & (q[:, :, 3] > 110) &
                 (q[:, :, :3].max(axis=2) - q[:, :, :3].min(axis=2) < 45))
        stroke[y0:y1, x0:x1] = light
        mask |= _local_mask(A.shape, w, light, 3)
    # 只擦白字，保留原黑色渐变阴影带；按列插值把笔画补回阴影色
    clean = B.column_fill(A, mask, resid_gain=0.30)
    arr = np.array(clean).copy()
    shape = A.shape[:2][::-1]
    for i, center in enumerate(cfg["centers"]):
        p = solid(shape, cfg["word"], cfg["style"])
        place6(arr, p, *center, tag="confirm%d" % i)
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", stroke)
    record(cfg["name"], "erase", mask)
    log("  confirm_parts  日文 ×3 → 下次不再确认")


# ---------------------------------------------------------------- 8 config_parts
def build_config_parts():
    cfg = C.CONFIG_PARTS
    A = load(cfg["name"])
    arr = A.copy()
    stroke = np.zeros(A.shape[:2], bool)
    erase_mute = np.zeros(A.shape[:2], bool)
    mute_cells = []
    for ry in cfg["rows"]:
        for ci, x0 in enumerate(cfg["mute_cols"]):
            w = (x0 + 1, ry, x0 + 40, ry + 12)
            q = A[w[1]:w[3], w[0]:w[2]]
            m = (q[:, :, 3] > 90)
            stroke[w[1]:w[3], w[0]:w[2]] = m
            erase_mute[w[1]:w[3], w[0]:w[2]] = True
            arr[w[1]:w[3], w[0]:w[2]] = 0
            mute_cells.append((w, "light" if ci < 2 else "dark"))
    # ALL：青块上的白字带暗描边，调和补底
    erase_all = np.zeros(A.shape[:2], bool)
    all_cells = []
    for ry in cfg["all_rows"]:
        for x0 in cfg["all_cols"]:
            w = (x0 + 5, ry + 6, x0 + 41, ry + 19)
            s, m = B.text_mask(A, w, cfg["all_dilate"])
            stroke |= s
            erase_all |= m
            # 旧 "ALL" 最右一撇落在 w 右边界之外（实测 x=x0+42..44，
            # 即右列 420~421），旧窗只到 x0+41，每格都留下一个逗号状白点。
            # 单独把这段白字并进擦除 mask；中文落位窗口 w 保持不变，避免移位。
            tail = (x0 + 41, ry + 8, x0 + 45, ry + 19)
            qt = A[tail[1]:tail[3], tail[0]:tail[2]]
            tw = ((qt[:, :, 0] > 165) & (qt[:, :, 1] > 165) &
                  (qt[:, :, 2] > 165) & (qt[:, :, 3] > 110))
            ts = np.zeros(A.shape[:2], bool)
            ts[tail[1]:tail[3], tail[0]:tail[2]] = tw
            stroke |= ts
            erase_all |= B.dilate(ts, 3) & B.box_mask(A.shape, tail, 1)
            all_cells.append(w)
    clean = B.button_inpaint(arr, erase_all, gain=0.55)
    arr = np.array(clean).copy()
    shape = A.shape[:2][::-1]
    for i, (w, style) in enumerate(mute_cells):
        st = cfg["mute_style"][style]
        p = solid(shape, "静音", st)
        place6(arr, p, (w[0] + w[2]) / 2.0, (w[1] + w[3]) / 2.0,
               tag="mute%d" % i)
    for i, w in enumerate(all_cells):
        p = solid(shape, "所有", cfg["all_style"])
        place6(arr, p, (w[0] + w[2]) / 2.0, (w[1] + w[3]) / 2.0,
               tag="all%d" % i)
    save(arr, cfg["name"])
    record(cfg["name"], "stroke", stroke)
    record(cfg["name"], "erase", erase_mute | erase_all)
    log("  config_parts   MUTE ×12 + ALL ×6   擦除 %5d px" %
        int((erase_mute | erase_all).sum()))


def main():
    log("字体:", C.SERIF)
    log("追加任务五 + 六 · 8 张")
    build_title()
    build_quit()
    build_rate()
    build_chart_parts()
    build_dialog()
    build_panel()
    build_confirm()
    build_config_parts()
    log("完成，输出 ->", C.DST_DIR)


if __name__ == "__main__":
    main()
