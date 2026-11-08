# -*- coding: utf-8 -*-
"""
追加任务七：file_parts.png 的 SAVE / LOAD 汉化生成器。

三行 alpha 完全相同、只换光晕色 → 一套中文 alpha 层贴三次。
运行：工具/ 目录执行 python build_batch7.py
      python build_batch7.py calibrate   # 只跑光晕参数网格校准
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config_batch7 as C


def log(*a):
    print(*a, flush=True)


def load(name):
    return np.array(Image.open(C.SRC_DIR / (name + ".png")).convert("RGBA")).astype(np.uint8)


def save(arr, name):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA").save(
        C.DST_DIR / (name + ".png"))


def font(sz):
    if C.SERIF is None:
        raise RuntimeError("找不到宋体，请改 config_batch7.SERIF_CANDIDATES")
    return ImageFont.truetype(C.SERIF, sz)


def dilate(mask, k):
    assert k % 2 == 1, "MaxFilter 只接受奇数核"
    return np.array(Image.fromarray((mask * 255).astype(np.uint8), "L")
                    .filter(ImageFilter.MaxFilter(k))) > 0


def word_alpha(size, word, f, gap, boost=1.0):
    """逐字绘制纯字形 alpha；起点留 24px 上边距，落位由 place7 统一量 bbox 平移。"""
    layer = Image.new("L", size, 0)
    d = ImageDraw.Draw(layer)
    bb = d.textbbox((0, 0), word, font=f)
    py = 24.0 - (bb[1] + bb[3]) / 2.0
    x = 24.0
    for ch in word:
        d.text((x, py), ch, font=f, fill=255)
        x += d.textlength(ch, font=f) + gap
    a = np.array(layer).astype(np.float32)
    return np.clip(a * boost, 0, 255).astype(np.uint8)


def glow_patch(size, word, f, st, glow_rgb):
    """透明底白字 + 青色柔光；光晕层挖空字核心，避免白字被染成光色。"""
    A = word_alpha(size, word, f, st["gap"], st["boost"])
    core = A.astype(np.float32) / 255.0
    ex = dilate(A > 60, st["dilate_k"]).astype(np.float32) * 255
    tight = np.array(Image.fromarray(np.clip(ex, 0, 255).astype(np.uint8), "L")
                     .filter(ImageFilter.GaussianBlur(st["blur_tight"]))).astype(np.float32)
    soft = np.array(Image.fromarray(A, "L")
                    .filter(ImageFilter.GaussianBlur(st["blur_soft"]))).astype(np.float32)
    ga = (tight * st["w_tight"] + soft * st["w_soft"]) * st["glow_gain"] \
         * (1.0 - core * st["core_dig"])
    ga = np.clip(ga, 0, 255)

    def layer(rgb, alpha):
        im = Image.new("RGBA", size, tuple(int(v) for v in rgb) + (0,))
        im.putalpha(Image.fromarray(alpha.astype(np.uint8), "L"))
        return im

    out = Image.alpha_composite(layer(glow_rgb, ga),
                                layer(C.FILE_PARTS["white_fill"], A))
    # 高斯模糊会拖出 alpha=1~7 的长尾（视觉完全不可见），但它会让贴片
    # 溢出清除窗上沿 3px、压到纸片下沿，还会让「窗口外 0 改动」自检失败。
    # 截掉这段长尾：alpha>8 的 bbox 实测正好落在清除窗内。
    a = np.array(out)
    a[a[:, :, 3] < 8, 3] = 0
    return Image.fromarray(a, "RGBA")


def place7(base, patch, cx, cy, tag=""):
    """逐像素 straight-alpha 合成；断言贴片确有墨迹、落位不越界。"""
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
    oa = sa + ba * (1.0 - sa)
    orgb = (src[:, :3] * sa + base[ty, tx, :3].astype(np.float32) * ba * (1.0 - sa)) \
           / np.maximum(oa, 1e-6)
    base[ty, tx, :3] = np.clip(orgb, 0, 255).astype(np.uint8)
    base[ty, tx, 3:4] = np.clip(oa * 255, 0, 255).astype(np.uint8)


def bins(alpha):
    a = alpha.astype(np.int32)
    return np.array([int(((a > 0) & (a <= 60)).sum()),
                     int(((a > 60) & (a <= 150)).sum()),
                     int(((a > 150) & (a <= 250)).sum()),
                     int((a > 250).sum())], np.float32)


def calibrate():
    """按方法 1.4：用原图 alpha 四档的分布比例校准 glow 参数，别凭观感调 gain。"""
    cfg = C.FILE_PARTS
    target = np.array(cfg["target_bins"], np.float32)
    tp = target / target.sum()
    f = font(cfg["style"]["font_size"])
    win_w = cfg["clear_x"][1] - cfg["clear_x"][0]      # 154，两格合窗
    # 用单格 79×33 的中位窗口打分：把贴片落到 79 宽画布中心
    CW, CH = 79, cfg["clear_h"]
    best = []
    for k in (5, 7, 9):
        for bt in (1.5, 2.0, 2.5):
            for bs in (3.5, 4.5, 5.5):
                for gain in (0.7, 0.9, 1.1, 1.4, 1.7, 2.1):
                    for boost in (1.0, 1.2, 1.35):
                        st = dict(cfg["style"])
                        st.update(dilate_k=k, blur_tight=bt, blur_soft=bs,
                                  glow_gain=gain, boost=boost)
                        p = glow_patch((160, 100), "读档", f, st, cfg["row_glow"][0])
                        a = np.array(p)[:, :, 3]
                        ys, xs = np.nonzero(a > 8)
                        if not len(xs):
                            continue
                        # 裁到墨迹 bbox 再居中放进 CW×CH
                        sub = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                        can = np.zeros((CH, CW), np.uint8)
                        h, w = sub.shape
                        px, py = (CW - w) // 2, (CH - h) // 2
                        if h > CH or w > CW or px < 0 or py < 0:
                            continue
                        can[py:py + h, px:px + w] = sub
                        bb = bins(can)
                        if bb.sum() < 100:
                            continue
                        bp = bb / bb.sum()
                        # 四档分布误差 + 总量误差（轻量）
                        score = float(np.abs(bp - tp).sum()) + \
                                0.10 * abs(float(bb.sum()) / target.sum() - 1.0)
                        best.append((score, k, bt, bs, gain, boost, bb.astype(int)))
    best.sort(key=lambda z: z[0])
    log("=== 光晕参数网格校准（目标分档 %s）===" % target.astype(int))
    log("目标比例", np.round(tp, 3))
    for z in best[:8]:
        score, k, bt, bs, gain, boost, bb = z
        log("  score %.4f  k=%d bt=%.1f bs=%.1f gain=%.2f boost=%.2f  bins=%s" %
            (score, k, bt, bs, gain, boost, bb))
    return best[0]


def build():
    cfg = C.FILE_PARTS
    A = load(cfg["name"])
    assert A.shape[:2][::-1] == cfg["size"], "尺寸不符: %s" % (A.shape,)
    arr = A.copy()
    stroke = np.zeros(A.shape[:2], bool)
    clear = np.zeros(A.shape[:2], bool)

    x0, x1 = cfg["clear_x"]
    for y0 in cfg["clear_y0"]:
        y1 = y0 + cfg["clear_h"]
        stroke[y0:y1, x0:x1] = A[y0:y1, x0:x1, 3] > 150
        arr[y0:y1, x0:x1] = 0
        clear[y0:y1, x0:x1] = True

    f = font(cfg["style"]["font_size"])
    patches = {}
    for key, word, _ in cfg["words"]:
        for ri, glow_rgb in enumerate(cfg["row_glow"]):
            patches[(key, ri)] = glow_patch(A.shape[:2][::-1], word, f,
                                            cfg["style"], glow_rgb)

    for ri, cy in enumerate(cfg["centers_y"]):
        for key, word, cx in cfg["words"]:
            place7(arr, patches[(key, ri)], cx, cy,
                   tag="%s_r%d" % (key, ri))

    # 边界收敛（4.5）：高斯模糊的 alpha 8~12 长尾会溢出清除窗 1px，
    # 压到纸片下沿 / 行间。窗口外一律还原成原图像素；被切掉的那圈
    # 只有 3~5% 不透明度，视觉无感，但「窗口外 0 改动」能严格成立。
    arr[~clear] = A[~clear]

    save(arr, cfg["name"])
    np.save(str(C.WORK_DIR / ("b7_%s_stroke.npy" % cfg["name"])), stroke)
    np.save(str(C.WORK_DIR / ("b7_%s_erase.npy" % cfg["name"])), clear)
    log("  file_parts      LOAD→读档 / SAVE→存档 × 3 行  清除 %d px" % int(clear.sum()))
    log("完成，输出 ->", C.DST_DIR)


def main():
    log("字体:", C.SERIF)
    if len(sys.argv) > 1 and sys.argv[1] == "calibrate":
        calibrate()
        return
    build()


if __name__ == "__main__":
    main()
