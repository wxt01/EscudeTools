# -*- coding: utf-8 -*-
"""
verify_tight_frame.py —— 紧框口径通用自检（方法文档 1.3.1 第五步）

任何批次接手「字周围有装饰 / 渐变」的图（0.1 Q6 = 有），都应把本模块的
检查接进自己的 verify_batchN.py，而不是各批次重写一遍几何判据。
本模块**不负责打印 / 退出**，只返回 (检查名, 是否通过, 说明) 三元组，
由批次脚本用自己的 chk() 上报，项数与命名保持批次自治。

三条主判据（tight_frame_checks）：
  1. 紧框外金色装饰像素 0 改动 —— 拦住内框线 / 圆边 / 标签金线被蹭掉；
  2. 改动几乎全在紧框内 —— 拦住把整窗当可动范围；
  3. 紧框内仍保留 ≥8% 未改动像素 —— **专门拦「整块铺色」**，
     比任何色差判据都可靠：整窗铺色会让这个数趋近 0。

辅助判据（line_cut_count）：按几何把装饰线像素摘出来数切断量，
用于悬停态 / 缩小格这类「通用保护罩不到」的特例（4.0 B20、D18）。

依赖：numpy。换图重新量 band / 几何 / 容差，别照抄任何数字。
"""
import numpy as np


def gold_line_mask(rgba):
    """常见的金色装饰线判据：高不透明 + 暖金 + 蓝通道低。

    换图前先量原图装饰线的实际 RGB；色系不同就自己传一个 mask 进来。
    """
    return ((rgba[:, :, 0] > 140) & (rgba[:, :, 1] > 110) &
            (rgba[:, :, 2] < 180) & (rgba[:, :, 3] > 200))


def clamp_box(box, shape):
    """把窗口坐标夹到图像内。

    4.0 D17：第 1 行单元算出负 y 时，numpy 负切片是「从末尾数」的反向
    切片，会把允许窗口写空、成品上沿被逐像素还原成英文，且没有任何报错。
    build 与 verify 两处都该用这个夹一次。
    """
    H, W = shape[:2]
    x0, y0, x1, y1 = box
    return (max(0, x0), max(0, y0), min(W, x1), min(H, y1))


def band_mask(shape, units, key="band", fallback="win"):
    """把若干单元的紧框合成一张全图 bool 掩膜。"""
    m = np.zeros(shape[:2], bool)
    for u in units:
        x0, y0, x1, y1 = clamp_box(u.get(key, u.get(fallback)), shape)
        m[y0:y1, x0:x1] = True
    return m


def tight_frame_checks(src, dst, units, name, outside_tol=500,
                       min_untouched_ratio=0.08, decoration=None):
    """返回 3 条紧框口径检查结果 [(检查名, 通过?, 说明), ...]。

    src / dst : RGBA 数组（任意整型）
    units     : 配置单元列表，每个至少有 band（或退化用 win）
    outside_tol : 允许的紧框外改动像素。两行排版把中文行心拉开时，
                  贴片必然越出**原英文**紧框几像素，需留容差（本项目 345）。
                  整窗铺色的坏稿是数千 px，500 的默认值仍能拦住。
    decoration : 可选，自定义装饰像素 bool 掩膜；不传则用 gold_line_mask
    """
    band = band_mask(src.shape, units)
    deco = (gold_line_mask(src) if decoration is None else decoration) & ~band
    changed = (src != dst).any(axis=2)
    deco_bad = int((changed & deco).sum())
    out_band = int((changed & ~band).sum())
    untouched = int((~changed & band).sum())
    area = int(band.sum())
    return [
        (name + " 紧框外金色装饰（内框线/圆边/标签金线）逐像素保留",
         deco_bad == 0, "改动 %d px" % deco_bad),
        (name + " 改动几乎全部落在紧框内（允许两行拉开的外移）",
         out_band <= outside_tol, "框外改动 %d px" % out_band),
        (name + " 紧框内非整块铺色（仍保留原底板像素）",
         untouched >= min_untouched_ratio * area,
         "未改动 %d / %d px" % (untouched, area)),
    ]


def line_cut_count(src, dst, band, selector, decoration=None):
    """统计 band 内「原图装饰线像素」在成品里被改动的数量。

    selector 两种写法：
      * callable(yy, xx) -> bool：自定义几何（如「离字心足够远」）
      * (fcx, fcy, R, tol)：菱形 / 圆形内框线
        |x-fcx| + |y-fcy| = R，容差 tol 由**拟合残差**决定（B20）
    """
    H, W = src.shape[:2]
    x0, y0, x1, y1 = clamp_box(band, src.shape)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    if callable(selector):
        line = selector(yy, xx)
    else:
        fcx, fcy, R, tol = selector
        line = np.abs(np.abs(xx - fcx) + np.abs(yy - fcy) - R) <= tol
    gline = (gold_line_mask(src) if decoration is None else decoration)
    sel = gline[y0:y1, x0:x1] & line
    diff = (src[y0:y1, x0:x1] != dst[y0:y1, x0:x1]).any(axis=2)
    return int((sel & diff).sum())
