# -*- coding: utf-8 -*-
"""
glyph_unit.py —— 紧框口径通用实现（字周围有装饰 / 渐变时的默认路线）

方法文档 `汉化方法与思路.md` 1.3.1。适用判据：0.1 Q6 = 有，即文字墨迹框外
10px 环带里存在细金线、内框斜线、圆周金边、贯穿分隔线、图标或渐变。

核心纪律：**修改区域的形状由字形决定，不由窗口决定。**
`band` 只用来找字形并擦除；`win` 只是允许区与落位上限，不是可铺色的范围；
中文贴片按渲染后中文墨迹 bbox 事前框定；发光态用字形软掩膜淡出，不用矩形 clip。

四个函数互不依赖批次配置，任何批次 `from glyph_unit import ...` 即可复用：
  glyph_fill        只填 mask 覆盖像素的局部归一化卷积补底
  glow_glyph        发光字：上下干净行取底色 + 字形核外扩整片擦净 + 几何线保护
  tight_clip        按渲染后中文墨迹 bbox 生成贴片事前框
  soft_patch_shape  按中文字形生成 0~1 软掩膜，让光晕顺着字淡出

参数含义与取值口径见方法文档 1.3.1 / 4.0 B18~B21；**换图必须重新量几何**。
依赖：numpy + Pillow（与工具包其余脚本一致，不需要 cv2 / scipy）。
"""
import numpy as np
from PIL import Image, ImageFilter


def glyph_fill(arr, A, mask, band, transparent=False):
    """只重绘 mask 覆盖的**字形像素**，绝不铺任何矩形。

    旧路线（vert_flat / btnfill / clear）把整个 win 铺成一块平色或清成透明，
    方块边缘笔直，把菱形内框线、圆周金边、按钮径向渐变、标签金线一起盖掉。
    逐行取「一个统一中位色」也会在圆形按钮的径向渐变上留下一道深色带。
    正解：归一化卷积局部补底 —— 每个字形像素的替换色 = 它邻域内
    「非字形且不透明」真实像素的加权均值，随径向/纵向渐变连续变化，
    填回去与周围无缝；mask 之外一律逐像素不动，alpha 不碰。
    transparent=True：标签在透明底上，字形像素直接清成 alpha=0。
    """
    x0, y0, x1, y1 = band
    H, W = arr.shape[:2]
    out = arr.copy()
    sub = out[y0:y1, x0:x1]
    mm = mask[y0:y1, x0:x1]
    if transparent:
        sub[mm] = 0
        return out
    # 邻域只外扩 5px，且只取「暗底板」像素。外扩更多会把相邻格的
    # 白勾号 / 茶杯图标 / 金框算进来；不外扩又会在窄窗口里取不到样本。
    bx0, by0 = max(0, x0 - 5), max(0, y0 - 5)
    bx1, by1 = min(W, x1 + 5), min(H, y1 + 5)
    rgb = A[by0:by1, bx0:bx1, :3].astype(np.float32)
    lum_all = rgb.mean(axis=2)
    opaque = A[by0:by1, bx0:bx1, 3] > 150
    valid = (opaque & (lum_all < 155) &
             (~mask[by0:by1, bx0:bx1])).astype(np.float32)
    v8 = (valid * 255).astype(np.uint8)
    den = np.array(Image.fromarray(v8, "L")
                   .filter(ImageFilter.GaussianBlur(3.0)),
                   dtype=np.float32)
    bg = np.zeros(rgb.shape, np.float32)
    for c in range(3):
        n8 = np.clip(rgb[:, :, c] * valid, 0, 255).astype(np.uint8)
        num = np.array(Image.fromarray(n8, "L")
                       .filter(ImageFilter.GaussianBlur(3.0)),
                       dtype=np.float32)
        bg[:, :, c] = num * 255.0 / np.maximum(den, 1.0)
    # 邻域内一个有效样本都没有时，回退色取本格真实底板（暗像素中位），
    # 不能硬编码深蓝 —— 那会把红格整块刷成深蓝矩形。
    dark_all = rgb[opaque & (lum_all < 155)]
    fallback = (np.median(dark_all, axis=0) if len(dark_all)
                else np.median(rgb[opaque], axis=0) if opaque.any()
                else np.array([43.0, 37.0, 55.0]))
    bg[den < 20] = fallback
    local = bg[y0 - by0:y1 - by0, x0 - bx0:x1 - bx0]
    tmp = sub[:, :, :3].copy()
    tmp[mm] = np.clip(local[mm], 0, 255).astype(np.uint8)
    sub[:, :, :3] = tmp
    return out


def glow_glyph(arr, A, band, center, frame=None, dilate_k=3):
    """发光菱形：从**上下干净行**取纵向底色，擦净整片旧英文光晕。

    glyph_fill 是「同一行左右取样」，但这一格的光晕横向铺满整行，
    左右样本全是黄色，取最暗 60% 中位仍是黄色 —— 等于把擦掉的光晕
    又填回去，成品看到的就是一条笔直的黄色横带。菱形底色只随 y 缓慢
    渐变、不随 x 变，所以正解是从 band 上下各 8px 的干净行取暗底板，
    纵向插值出每一行的真实底色，再只重绘字形 mask 覆盖的像素。
    细金线用局部亮像素密度（2px 细线 vs 成片光晕）单独保护。
    """
    x0, y0, x1, y1 = band
    H, W = A.shape[:2]
    pad = 8
    top = A[max(0, y0 - pad):y0, x0:x1].reshape(-1, 4)
    bot = A[y1:min(H, y1 + pad), x0:x1].reshape(-1, 4)

    def darkmed(s):
        ok = (s[:, 3] > 150) & (s[:, :3].mean(axis=1) < 110)
        if ok.sum() < 10:
            ok = s[:, 3] > 150
        return (np.median(s[ok, :3], axis=0) if ok.sum()
                else np.array([40.0, 30.0, 70.0]))

    ct, cb = darkmed(top), darkmed(bot)
    hh = y1 - y0
    t = np.linspace(0, 1, hh)[:, None]
    C = ct[None, :] * (1 - t) + cb[None, :] * t          # (hh,3)
    q = A[y0:y1, x0:x1].astype(np.float32)
    d = np.abs(q[:, :, :3] - C[:, None, :]).mean(axis=2)
    # 旧英文光晕有一条很宽的淡尾（d 只有 5~15）。若按 d 做连续淡出，
    # 淡尾衰减处就会留下一圈椭圆轮廓。正解：以「明显是字/光晕」的核
    # 为准，外扩 7px 把淡尾整片圈进来一律擦净，只在**已经完全是底板**
    # 的地方做 2px 羽化 —— 羽化落在干净底色上，肉眼看不到任何边界。
    core = ((d > 12) & (q[:, :, 3] > 50)).astype(np.uint8) * 255
    core[q[:, :, 3] <= 50] = 0
    dil = Image.fromarray(core, "L").filter(ImageFilter.MaxFilter(15))
    w = np.array(dil.filter(ImageFilter.GaussianBlur(2.0)),
                 dtype=np.float32) / 255.0
    r, g, b, al = q[:, :, 0], q[:, :, 1], q[:, :, 2], q[:, :, 3]
    goldline = (r > 140) & (g > 110) & (b < 180) & (al > 200)
    # 【内框金线保护】菱形内框满足 |x-cx|+|y-cy| ≈ 62 的斜线，
    # 在字带上下沿会斜穿进 band。它与金色字/光晕的局部密度几乎一样，
    # 密度判据分不开（实测本轮翻车：四条斜线被从中间切断）。
    # 改用几何：字与光晕都集中在 |x-cx|<=45 且 |y-cy|<=12 的核心区，
    # 内框线只要落在核心区之外就整段逐像素保护，绝不擦也不填。
    yy, xx = np.mgrid[y0:y1, x0:x1]
    far = (np.abs(yy - center[1]) > 12) | (np.abs(xx - center[0]) > 47)
    on_frame = np.zeros(goldline.shape, bool)
    if frame is not None:
        # 小菱形（上移悬停态 RESET）内框线 R≈47，斜线会斜穿进「字心核心区」，
        # 只靠 far 保护不到。按逐格实测菱形拟合 |x-fcx|+|y-fcy|=R，
        # 把落在这条线上的金线像素一并逐像素保护。字/光晕集中在
        # |dx|+|dy| < 30，与 R=47 相差 17px 以上，不会被误保。
        fcx, fcy, R = frame
        on_frame = (np.abs(np.abs(xx - fcx) + np.abs(yy - fcy) - R) <= 2.5)
    # 拟合已精确到 ±0.5px，保护带只留 ±2.5px；不再向外膨胀，
    # 否则会把斜线内侧 5px 的旧字光晕一起保住，留下孤立小金点。
    protect = goldline & (far | on_frame)
    w[protect] = 0.0
    newrgb = (q[:, :, :3] * (1 - w[:, :, None]) +
              C[:, None, :] * w[:, :, None])
    out = arr.copy()
    out[y0:y1, x0:x1, :3] = np.clip(newrgb, 0, 255).astype(np.uint8)
    # stroke 只记「真正的旧字/光晕核心」，不记外扩到干净底板的羽化区 ——
    # 后者本来就是底色，填回同色不算改动，会把自检的改动率稀释成假失败。
    em = np.zeros((H, W), bool)
    em[y0:y1, x0:x1] = ((d > 12) & (q[:, :, 3] > 50) & ~protect)
    return out, em


def tight_clip(patch, cx, cy, pad=2):
    """按贴片**渲染后的中文墨迹 bbox** 生成事前框，方块只比字大 pad 像素。"""
    a = np.array(patch)
    al = a[:, :, 3]
    ys, xs = np.nonzero(al > 60)
    assert len(xs), "贴片无墨迹"
    dx = int(round(cx - (xs.min() + xs.max()) / 2.0))
    dy = int(round(cy - (ys.min() + ys.max()) / 2.0))
    # 只按「字形实墨」量边界：发光贴片的 soft 光晕 alpha>0 能拖出十几像素，
    # 若把它算进框就又变成一个大方块。光晕超出框的部分由 feather 自然淡出。
    yy, xx = np.nonzero(al > 60)
    return (int(xx.min() + dx - pad), int(yy.min() + dy - pad),
            int(xx.max() + 1 + dx + pad), int(yy.max() + 1 + dy + pad))


def soft_patch_shape(patch, cx, cy, size, k=11, blur=2.5):
    """按**中文字形**生成 0~1 软掩膜：字核为 1，外扩几像素后平滑淡出。

    发光贴片自带的高斯光晕若用矩形 clip 硬裁，切口就是一条笔直的黄色
    光带（用户反馈「方块盖住图案」）。改用「字形外扩 + 高斯羽化」的
    软掩膜乘到贴片 alpha 上，光晕顺着字形圆润收边，没有任何直边。
    """
    a = np.array(patch)
    al = a[:, :, 3]
    ys, xs = np.nonzero(al > 60)
    assert len(xs), "贴片无墨迹"
    dx = int(round(cx - (xs.min() + xs.max()) / 2.0))
    dy = int(round(cy - (ys.min() + ys.max()) / 2.0))
    core = (al > 60).astype(np.uint8) * 255
    soft = (Image.fromarray(core, "L").filter(ImageFilter.MaxFilter(k))
            .filter(ImageFilter.GaussianBlur(blur)))
    W, H = size
    canvas = Image.new("L", (W, H), 0)
    canvas.paste(soft, (dx, dy))
    return np.array(canvas, dtype=np.float32) / 255.0
