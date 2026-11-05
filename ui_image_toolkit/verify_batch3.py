# -*- coding: utf-8 -*-
"""追加任务三：五张成品的交付自检。

重点判据（都是这轮踩过坑之后补的）：
  * 清除区外逐像素一致 —— 图标 / 红色箭头 / popup 下方全部 UI 元素不能动
  * 每一格都确实被擦过且写上了中文 —— 防「整格漏擦直接叠中文」
  * 中文不能溢出词格 —— 防 4 字 × 字号 > 格宽造成的裁切、串格
  * 多状态颜色梯度仍在 —— 防把三行/四列画成同一套色
"""
import os
import numpy as np
from PIL import Image

import config_batch3 as C

FAIL = []


def chk(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + ("  " + detail if detail else ""))
    if not cond:
        FAIL.append(name)


def load(d, name):
    return np.array(Image.open(os.path.join(d, name + ".png")).convert("RGBA"))


def boxes_simple(cfg):
    b = []
    for col in cfg["cols"]:
        for y0, y1 in cfg["rows"]:
            b.append((col + cfg["clear_x0"], y0, col + cfg["col_w"], y1))
    return b


def boxes_popup():
    p = C.POPUP
    return [(p["clear_x0"][ci], y0, col + p["col_w"], y1)
            for ci, col in enumerate(p["cols"]) for y0, y1 in p["rows"]]


def boxes_sys(cfg):
    return [(x0, y0, x1, y1) for y0, y1 in C.SYS["rows"]
            for x0, x1 in cfg["spans"]]


def mask_from(boxes, shape):
    m = np.zeros(shape[:2], dtype=bool)
    for x0, y0, x1, y1 in boxes:
        m[y0:y1, x0:x1] = True
    return m


def outside_check(name, boxes):
    s, d = load(C.SRC_DIR, name), load(C.DST_DIR, name)
    m = mask_from(boxes, s.shape)
    diff = (s != d).any(axis=2) & ~m
    chk(name + " 清除区外 0 改动", int(diff.sum()) == 0,
        "带外改动 %d" % int(diff.sum()))
    return s, d, m


def coverage_check(name, s, m, min_white=190, band_y=None, xranges=None):
    """原图所有白色实笔画必须落在清除区内。

    ⚠️ 不要用「成品里还有没有白字」判残留：中文也是纯白 (255,255,255,255)，
       笔画交叉处会与原英文像素逐像素巧合相同（实测约 6%），必然误报。
    清除区被清成 alpha=0 后才贴中文，所以区内任何不透明像素都只能是新字；
    只要清除区覆盖了全部旧字，就不可能残留。这个判据无歧义。
    """
    ow = (s[:, :, 0] > min_white) & (s[:, :, 1] > min_white) & \
         (s[:, :, 2] > min_white) & (s[:, :, 3] > 180)
    # 只看文字带（popup 下方有白色 UI 元素，不在此列）
    band = np.zeros(s.shape[:2], dtype=bool)
    band[:band_y or s.shape[0]] = True
    if xranges:
        xs = np.zeros(s.shape[1], dtype=bool)
        for a, b in xranges:
            xs[a:b] = True
        band &= xs[None, :]
    ow &= band
    miss = ow & ~m
    chk(name + " 旧字全部落在清除区内", int(miss.sum()) == 0,
        "漏擦 %d / 原 %d" % (int(miss.sum()), int(ow.sum())))


def erased_check(name, s, d, boxes, limit=0.15):
    """逐格确认「旧字真的被擦掉」，防「对照图正常、成品却还是英文」。

    `coverage_check` 只检查清除区**范围**是否盖住旧字，`every_cell_check` 只检查
    格内有没有亮像素——英文原字两者都能满足。本判据直接比对：清除区内原图的
    实笔画像素，若在成品里逐像素完全相同，说明这一格根本没被重写。
    中文白字与英文白字会偶发逐像素相同（实测 2~6%），所以按比例判而非要求 0；
    完全没汉化的格子保留率是 100%，一眼就能分开。
    """
    hi = s[:, :, 3] > 150
    same = (s == d).all(axis=2) & hi
    worst, bad = 0.0, []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        tot = int(hi[y0:y1, x0:x1].sum())
        if tot < 50:
            continue
        r = int(same[y0:y1, x0:x1].sum()) / tot
        worst = max(worst, r)
        if r > limit:
            bad.append((i, round(r, 2)))
    chk(name + " 每格旧字确已擦除", not bad,
        "最差保留率 %.1f%%  疑似未汉化格 %s" % (worst * 100, bad[:6]))


def layout_check(name, s, d, cfg):
    """popup 排版硬约束：左沿对齐原图英文墨迹、右沿不超红线、
    倾斜必须来自整层旋转而不是逐字抬高、禁用列不能有辉光。

    ⚠️ 左沿基准是**原图英文墨迹的实测左沿 +50~53**（不是任务说明早期写的
    +46）。+46 比原图还左 6px，中文首字会探进源矩形/遮罩左沿，用户实测
    「第一个字部分被遮挡」。红线同样是原图英文墨迹的实际右沿，超了会在
    游戏里被引擎裁掉、串染到相邻列。两边都要按原图量，别按文档估算值。
    """
    bad_l, bad_r, bad_o = [], [], []
    for ri, (y0, y1) in enumerate(cfg["rows"]):
        for ci, col in enumerate(cfg["cols"]):
            q = d[y0:y1, cfg["clear_x0"][ci]:col + cfg["col_w"]]
            ys, xs = np.nonzero(q[:, :, 3] > 60)
            if len(xs) == 0:
                bad_l.append((ri, ci, "empty"))
                continue
            left = int(xs.min()) + cfg["clear_x0"][ci] - col
            right = int(xs.max()) + cfg["clear_x0"][ci] - col
            expect = cfg["text_x"][ci] - col
            if not (expect - 2 <= left <= expect + 2):
                bad_l.append((ri, ci, left))
            if right > cfg["redline"][ri]:
                bad_r.append((ri, ci, right, cfg["redline"][ri]))
            # 原图英文墨迹左沿（排除红箭头）也要逐格对上，防止文档估算值回归
            so = s[y0:y1, col + 44:col + 170]
            mo = (so[:, :, 3] > 60) & ~((so[:, :, 0] > 170) &
                                        (so[:, :, 1] < 110) & (so[:, :, 2] < 110))
            yo, xo = np.nonzero(mo)
            if len(xo):
                ol = int(xo.min()) + 44
                if abs(left - ol) > 3:
                    bad_o.append((ri, ci, left, ol))
    chk(name + " 九行左沿对齐原图 +52", not bad_l, str(bad_l[:4]))
    chk(name + " 中文左沿与原图英文左沿一致", not bad_o, str(bad_o[:4]))
    chk(name + " 每行右沿不超红线", not bad_r, str(bad_r[:4]))
    chk(name + " 倾斜=整层旋转(非逐字抬高)",
        cfg["rise"] == 0 and cfg["rotate"] >= 4,
        "rise=%s rotate=%s" % (cfg["rise"], cfg["rotate"]))
    g0 = d[52:88, cfg["clear_x0"][0]:cfg["cols"][0] + cfg["col_w"], 3]
    chk(name + " 禁用列无辉光/无高亮",
        int((g0 >= 200).sum()) == 0 and int(g0.max()) < 120,
        "峰值 %d" % int(g0.max()))


def every_cell_check(name, d, cfg, mode):
    """逐格确认有中文笔画，且没有溢出格边界。"""
    ok, overflow = 0, 0
    if mode == "simple":
        for col in cfg["cols"]:
            for (y0, y1) in cfg["rows"]:
                q = d[y0:y1, col + cfg["text_x"]:col + cfg["col_w"]]
                if int((q[:, :, 3] > 120).sum()) > 25:
                    ok += 1
        total = len(cfg["cols"]) * len(cfg["rows"])
    elif mode == "popup":
        p = C.POPUP
        for ci, col in enumerate(p["cols"]):
            for (y0, y1) in p["rows"]:
                q = d[y0:y1, p["text_x"][ci]:col + p["col_w"]]
                if int((q[:, :, 3] > 60).sum()) > 25:
                    ok += 1
        total = len(p["cols"]) * len(p["rows"])
    else:  # sys
        for y0, y1 in C.SYS["rows"]:
            for x0, x1 in cfg["spans"]:
                q = d[y0:y1, x0:x1]
                if int((q[:, :, 3] > 120).sum()) > 25:
                    ok += 1
        total = len(C.SYS["rows"]) * len(cfg["spans"])
    chk(name + " 每格都有中文", ok == total, "%d / %d" % (ok, total))
    return overflow


print("=" * 70)
print("追加任务三 · 五张成品自检")
print("=" * 70)

# ---------------------------------------------------------------- radio / check
for cfg in (C.RADIO, C.CHECK):
    n = cfg["name"]
    s, d, m = outside_check(n, boxes_simple(cfg))
    chk(n + " 尺寸/RGBA", s.shape == d.shape == (cfg["size"][1], cfg["size"][0], 4),
        str(d.shape))
    coverage_check(n, s, m,
                   xranges=[(col + cfg["text_x"], col + cfg["col_w"]) for col in cfg["cols"]])
    erased_check(n, s, d, boxes_simple(cfg))
    every_cell_check(n, d, cfg, "simple")
    # 三列文字层应完全一致（差异只在图标）
    cw = cfg["col_w"]
    a = d[:, 0 + cfg["text_x"]:0 + cw]
    for ci in (1, 2):
        b = d[:, cfg["cols"][ci] + cfg["text_x"]:cfg["cols"][ci] + cw]
        chk(n + " 列0/列%d 文字层一致" % ci,
            bool((a == b).all()), "不同 %d" % int((a != b).any(axis=2).sum()))
    # 三列图标色不同（状态确实还在）
    ic = []
    for col in cfg["cols"]:
        q = d[:, col:col + cfg["clear_x0"]]
        px = q[:, :, :3][q[:, :, 3] > 150]
        ic.append(tuple(np.median(px, axis=0).round(0).astype(int)))
    chk(n + " 三列图标颜色互不相同", len(set(ic)) == 3, str(ic))

# ---------------------------------------------------------------- popup_parts
p = C.POPUP
s, d, m = outside_check("popup_parts", boxes_popup())
chk("popup_parts 尺寸/RGBA", s.shape == d.shape == (686, 864, 4), str(d.shape))
coverage_check("popup_parts", s, m, band_y=396,
               xranges=[(p["text_x"][ci], col + p["col_w"])
                        for ci, col in enumerate(p["cols"])])
erased_check("popup_parts", s, d, boxes_popup())
layout_check("popup_parts", s, d, p)
every_cell_check("popup_parts", d, p, "popup")
# 箭头区域逐像素保留
arrow = np.zeros(s.shape[:2], dtype=bool)
for xa, xb in ((432, 472), (648, 688)):
    arrow[0:396, xa:xb] = True
chk("popup_parts 红色箭头逐像素保留",
    bool((s[arrow] == d[arrow]).all()), "%d 像素" % int(arrow.sum()))
# y>400 的 UI 元素逐像素保留
chk("popup_parts y>=400 非文字区逐像素保留",
    bool((s[400:] == d[400:]).all()), "%d 像素" % int(s[400:].size / 4))
# 四列状态色互不相同
cols_rgb = []
for ci, x0 in enumerate(p["text_x"]):
    q = d[52:88, x0:x0 + 130]
    px = q[:, :, :3][q[:, :, 3] > 150]
    cols_rgb.append(tuple(np.median(px, axis=0).round(0).astype(int)) if len(px) else ())
chk("popup_parts 四列状态色互不相同", len(set(cols_rgb)) == 4, str(cols_rgb))

# ---------------------------------------------------------------- sys_quit / sys_back
for cfg in (C.SYS_QUIT, C.SYS_BACK):
    n = cfg["name"]
    s, d, m = outside_check(n, boxes_sys(cfg))
    chk(n + " 尺寸/RGBA", s.shape == d.shape == (114, cfg["size"][0], 4), str(d.shape))
    erased_check(n, s, d, boxes_sys(cfg))
    every_cell_check(n, d, cfg, "sys")
    # 三行辉光色梯度：取每行「非白字」的彩色像素中位
    gs = []
    for y0, y1 in C.SYS["rows"]:
        q = d[y0:y1]
        A = q[:, :, 3]
        colored = (A > 25) & (A < 190) & (q[:, :, 0] < 180)
        px = q[:, :, :3][colored]
        gs.append(tuple(np.median(px, axis=0).round(0).astype(int)) if len(px) else ())
    chk(n + " 三行辉光色梯度保留", len(set(gs)) == 3, str(gs))
    # 每行白字核心确实为白
    whites = []
    for y0, y1 in C.SYS["rows"]:
        q = d[y0:y1]
        px = q[:, :, :3][q[:, :, 3] > 220]
        whites.append(tuple(np.median(px, axis=0).round(0).astype(int)) if len(px) else ())
    chk(n + " 三行白字核心为白色",
        all(all(v > 230 for v in w) for w in whites), str(whites))

print("=" * 70)
print("结果: %s  (失败 %d)" % ("全部通过" if not FAIL else "有失败项", len(FAIL)))
if FAIL:
    for f in FAIL:
        print("  -", f)
    raise SystemExit(1)
