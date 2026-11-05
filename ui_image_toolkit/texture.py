# -*- coding: utf-8 -*-
"""
有底板的图，擦字之后必须把「真实纹理」补回去。

为什么不用纯色/渐变/拟合：
    做旧底板（金属、木牌、烧焦边缘）的斑驳是高频噪声，人眼对「一片均匀色」
    极其敏感，哪怕平均色完全一致，也会看成一块补丁。之前在透明底板上
    「填成发光带颜色」翻车，本质是同一类错误。

这里的做法（纯 numpy/PIL，不依赖 cv2/scipy）：
    1. 从图像自身取一块真实纹理，垂直平移到待填区域 —— 噪声是真的，不是合成的；
    2. 逐扫描行用「该格内未被文字遮住的像素」的中位色做加性校正，
       这样垂直渐变、按钮边缘的明暗都保留下来；
    3. 源行 / 水平相位轮换，避免同一条纹理被平铺出可见的重复；
    4. mask 边界 1px 羽化，消掉笔画抗锯齿留下的细边。

这个模块只假设「底板在同一格内、同一水平行上是统计平稳的」。
若底板有强透视、强方向性条纹或跨格的大图案，请改采样窗口或换 inpainting。
"""
import numpy as np


def _row_median(arr, mask, x0, x1, y0, y1):
    """参考窗口内每一行的中位 RGBA（只用非 mask 像素）。"""
    H = arr.shape[0]
    lo, hi = max(0, y0 - 24), min(H, y1 + 24)
    med = np.full((H, 4), np.nan, dtype=np.float32)
    cover = np.zeros(H, dtype=np.float32)
    for y in range(lo, hi):
        sel = ~mask[y, x0:x1]
        px = arr[y, x0:x1][sel]
        cover[y] = sel.mean()
        if len(px) >= 4:
            med[y] = np.median(px, axis=0)
    # 缺失行用最邻近的有效行补齐
    good = np.where(~np.isnan(med[:, 0]))[0]
    if len(good) == 0:
        med[:] = np.array([0, 0, 0, 255], dtype=np.float32)
        cover[:] = 1.0
    else:
        for y in range(lo, hi):
            if np.isnan(med[y, 0]):
                j = good[np.argmin(np.abs(good - y))]
                med[y] = med[j]
    return med, cover


def fill_with_texture(arr, mask, x0, x1, y0, y1,
                      dy_candidates=(-19, -14, -10, 10, 14, 19),
                      hshifts=(0, 37, -41, 19, -23),
                      feather=True):
    """
    arr  : (H,W,4) float32 RGBA，会被复制，不原地修改
    mask : (H,W) bool，True = 需要重建的像素（建议已含描边膨胀）
    x0,x1: 该格参考窗口的左右边界（含底板、不含相邻格）
    y0,y1: 该行状态的上下边界
    返回  : 填充后的 ndarray
    """
    out = arr.copy()
    H, W = arr.shape[:2]
    med, cover = _row_median(arr, mask, x0, x1, y0, y1)

    # 可用的源行：在本格窗口内几乎没有 mask（即干净底板）
    lo, hi = max(0, y0 - 24), min(H, y1 + 24)
    src_rows = [y for y in range(lo, hi) if cover[y] > 0.80]
    if not src_rows:
        src_rows = [y for y in range(lo, hi) if cover[y] > 0.50]
    if not src_rows:
        src_rows = list(range(lo, hi))

    x0i, x1i = max(0, x0), min(W, x1)
    if x1i <= x0i:
        return out

    for y in range(max(0, y0), min(H, y1)):
        xs = np.where(mask[y, x0i:x1i])[0] + x0i
        if len(xs) == 0:
            continue
        # 选源行：优先按 dy 候选，退化为「最近的高覆盖行」
        ys = None
        for dy in dy_candidates:
            cand = y + dy
            if lo <= cand < hi and cover[cand] > 0.80:
                ys = cand
                break
        if ys is None:
            ys = min(src_rows, key=lambda t: abs(t - y))
        delta = med[y] - med[ys]
        # 水平相位：随 y 轮换，避免上下行复制同一条纹理
        hs = hshifts[(y - y0) % len(hshifts)]
        for x in xs:
            sx = x + hs
            if not (x0i <= sx < x1i) or mask[ys, sx]:
                sx = x - hs
            if not (x0i <= sx < x1i) or mask[ys, sx]:
                sx = x
            src = arr[ys, sx]
            out[y, x, :3] = np.clip(src[:3] + delta[:3], 0, 255)
            out[y, x, 3] = src[3] if src[3] > 0 else arr[y, x, 3]

    if feather:
        # 边界 1px：原图与新纹理各半，消掉抗锯齿细边
        ring = mask.copy()
        ring[1:, :] &= mask[:-1, :]
        ring[:-1, :] &= mask[1:, :]
        ring[:, 1:] &= mask[:, :-1]
        ring[:, :-1] &= mask[:, 1:]
        edge = mask & ~ring
        ys, xs = np.where(edge)
        if len(ys):
            out[ys, xs] = 0.5 * arr[ys, xs] + 0.5 * out[ys, xs]

    return out
