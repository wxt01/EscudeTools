# -*- coding: utf-8 -*-
"""
擦字之后的「补底」二选一。

默认：扩散补底（纯 numpy + PIL，零依赖）——
    低频用「归一化卷积」从 mask 外的真实像素插值出局部底色，
    再做少量 Jacobi 松弛衔接边界；高频补一点与周围统计一致的颗粒噪声。
    ★ 别把 mask 内初值设成全图均值：多状态雪碧图各行底色差别很大，
      大片擦除区会变成一块偏亮、发平的补丁。
    ★ 也别用「平移借用别处的高频残差」来补纹理：会把其它格子的文字
      残差一起搬进擦除区，留下字母虚影（本项目实际踩过）。
    后端固定不自动切换，是为了同一组参数在任何机器上给出一致结果、便于排查。

可选：把 USE_CV2 改成 True 走 OpenCV Telea inpaint ——
    沿等照度线把笔画之间的真实纹理推进来，对做旧斑驳、木纹效果更好，
    但这条分支没有在本项目成品上验收过，交付前请自己看放大图。

为什么不用「整行平移复制纹理」：
    逐行从不同源行取样会产生行间颜色跳变和水平条纹，在木牌上尤其明显
    （这是本项目实际踩过的坑，见《汉化方法与思路.md》）。
    笔画很窄时，扩散插值比复制大块纹理更干净。

mask 建议：文字颜色阈值 + 3px 膨胀，覆盖描边与抗锯齿过渡带。
别把 mask 做成整块矩形 —— 笔画之间的原始底板是最宝贵的纹理来源。
"""
import numpy as np
from PIL import Image, ImageFilter

# 默认固定使用扩散补底，避免环境里装没装 cv2 导致结果不同、难以排查。
# 想试 inpaint 时把 USE_CV2 改成 True（需 pip install opencv-python-headless），
# 但那条分支的效果没有在本次成品上验收过，交付前请自己看放大图。
USE_CV2 = False
HAS_CV2 = False
if USE_CV2:
    try:
        import cv2
        HAS_CV2 = True
    except ImportError:
        HAS_CV2 = False


def diffuse_repair(arr, mask, iters=220, noise_gain=0.55, seed=7):
    """以 mask 外真实像素为边界的调和扩散 + 高频噪声回补。arr: uint8 RGBA。"""
    rgb = arr[:, :, :3].astype(np.float32)
    out = rgb.copy()
    known = ~mask
    if known.sum() == 0:
        return arr.copy()

    # ---- 低频：归一化卷积，只让 mask 外的真实像素参与插值
    # 等价于「把洞外的颜色按高斯权重铺进来」，不含任何文字信息，
    # 所以既不会留下字形负影，也不会因为全图均值而偏亮。
    Hh, Ww = mask.shape
    wf = np.array(Image.fromarray((known * 255).astype(np.uint8), "L")
                  .filter(ImageFilter.GaussianBlur(14))).astype(np.float32) / 255.0
    num = np.zeros((Hh, Ww, 3), dtype=np.float32)
    num[known] = rgb[known]
    low = np.stack([
        np.array(Image.fromarray(np.clip(num[:, :, c], 0, 255).astype(np.uint8), "L")
                 .filter(ImageFilter.GaussianBlur(14))).astype(np.float32)
        for c in range(3)], axis=2)
    low = np.clip(low / np.maximum(wf[:, :, None], 1e-3), 0, 255)
    out[mask] = low[mask]
    # 少量松弛把边界接顺（初值已经是局部底色，不需要几百次）
    for _ in range(min(iters, 45)):
        avg = (np.roll(out, 1, 0) + np.roll(out, -1, 0) +
               np.roll(out, 1, 1) + np.roll(out, -1, 1)) * 0.25
        out[mask] = avg[mask]

    # ---- 高频：只补幅度，不借别处的残差
    blur = np.array(Image.fromarray(rgb.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)
    resid = rgb - blur
    ring = (np.array(Image.fromarray((mask * 255).astype(np.uint8))
                     .filter(ImageFilter.MaxFilter(5))) > 0) & known
    sigma = float(resid[ring].std()) if ring.any() else float(resid[known].std())
    rng = np.random.default_rng(seed)
    n = rng.normal(0.0, 1.0, (Hh, Ww)).astype(np.float32)
    out[mask] += (n * sigma * noise_gain)[mask, None]
    out = np.clip(out, 0, 255)

    res = arr.copy()
    res[:, :, :3] = out.astype(np.uint8)
    # 边界 1px 半混合，消掉抗锯齿细边
    core = np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.MinFilter(3))) > 0
    edge = mask & ~core
    if edge.any():
        res[edge, :3] = (0.5 * arr[edge, :3].astype(np.float32) +
                         0.5 * res[edge, :3].astype(np.float32)).astype(np.uint8)
    return res


def patch_repair(arr, mask, cells):
    """
    有实心底板、且底板是「统计平稳的做旧纹理」时，用同格干净样本回填。

    为什么不用纯扩散：整词擦除后 mask 会连成一大片，四周剩下的参考像素
    往往是按钮的暗边，扩散/归一化卷积会把这份偏暗铺满整块，形成暗矩形。
    这里低频取「每列 mask 外像素的中位色」（保住水平渐变与真实亮度），
    高频从该格干净像素的真实残差里确定性取样（保住做旧颗粒）。

    cells: [(x0, x1, y0, y1)]，一格一个窗口，通常与擦字窗口一致。
    取样用固定公式而不是随机数，换机器结果一致、便于排查。
    """
    rgb = arr[:, :, :3].astype(np.float32)
    out = rgb.copy()
    excl = np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.MaxFilter(5))) > 0
    for x0, x1, y0, y1 in cells:
        sub = rgb[y0:y1, x0:x1]
        ok = ~excl[y0:y1, x0:x1]
        w = x1 - x0
        colbase = np.full((w, 3), np.nan, dtype=np.float32)
        for j in range(w):
            v = sub[:, j][ok[:, j]]
            if len(v) >= 2:
                colbase[j] = np.median(v, axis=0)
        good = ~np.isnan(colbase[:, 0])
        if good.sum() < 2:
            colbase[:] = np.median(sub[ok], axis=0) if ok.any() else 0
        else:
            for c in range(3):
                colbase[:, c] = np.interp(np.arange(w), np.where(good)[0], colbase[good, c])
        samples = (sub - colbase[None, :, :])[ok]
        if len(samples) < 8:
            continue
        yy, xx = np.where(mask[y0:y1, x0:x1])
        if len(yy) == 0:
            continue
        idx = (yy * 37 + xx * 101) % len(samples)
        tmp = sub.copy()
        tmp[yy, xx] = np.clip(colbase[xx] + samples[idx], 0, 255)
        out[y0:y1, x0:x1] = tmp

    res = arr.copy()
    res[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
    # 边界 1px 半混合，消掉硬边
    core = np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.MinFilter(3))) > 0
    edge = mask & ~core
    if edge.any():
        res[edge, :3] = (0.5 * arr[edge, :3].astype(np.float32) +
                         0.5 * res[edge, :3].astype(np.float32)).astype(np.uint8)
    return res


def repair(arr, mask, spans=None, radius=4):
    """
    arr   : (H,W,4) uint8 RGBA
    mask  : (H,W) bool，True = 需要修复
    spans : 兼容旧接口，扩散法不需要
    返回  : (H,W,4) uint8
    """
    if HAS_CV2:
        bgr = cv2.cvtColor(np.ascontiguousarray(arr[:, :, :3]), cv2.COLOR_RGB2BGR)
        filled = cv2.inpaint(bgr, (mask.astype(np.uint8) * 255), radius, cv2.INPAINT_TELEA)
        out = arr.copy()
        out[:, :, :3] = cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)
        return out
    return diffuse_repair(arr, mask)


def backend_name():
    return "OpenCV Telea inpaint" if HAS_CV2 else "numpy 扩散补底（默认后端，零依赖）"
