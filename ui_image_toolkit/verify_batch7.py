# -*- coding: utf-8 -*-
"""
追加任务七（file_parts.png）验收自检。运行：python verify_batch7.py
坏稿探针：python _badprobe7.py

口径沿用第 4~6 批：声明允许改动窗口、窗口外 0 改动；旧字墨迹区必须有足够
比例被重画；每格用「新增字色墨迹」判有中文；逐像素保留的装饰单独核对。
本批额外加两条强判据：
  · 白字墨迹 bbox 宽度必须是中文 2 字（≤50），原英文 4 字母是 57~62px；
  · 三行光晕 RGB 必须与实测三态配色一致，且三行 alpha 分档完全相同
    （原图三行就是同一套 alpha 换色，别把状态差异弄丢）。
"""
import sys
import numpy as np
from PIL import Image

import config_batch7 as C

PASS, FAIL = [], []


def chk(name, cond, info=""):
    (PASS if cond else FAIL).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + str(info)) if info else ""))


def L(p):
    return np.array(Image.open(p).convert("RGBA")).astype(np.int32)


def src(n):
    return L(C.SRC_DIR / (n + ".png"))


def dst(n):
    return L(C.DST_DIR / (n + ".png"))


def mask_of(key):
    p = C.WORK_DIR / ("b7_file_parts_%s.npy" % key)
    return np.load(str(p)) if p.exists() else None


def allow_windows():
    cfg = C.FILE_PARTS
    x0, x1 = cfg["clear_x"]
    return [(x0, y0, x1, y0 + cfg["clear_h"]) for y0 in cfg["clear_y0"]]


def bins(alpha):
    a = alpha.astype(np.int32)
    return np.array([int(((a > 0) & (a <= 60)).sum()),
                     int(((a > 60) & (a <= 150)).sum()),
                     int(((a > 150) & (a <= 250)).sum()),
                     int((a > 250).sum())], np.int32)


def cell_windows():
    cfg = C.FILE_PARTS
    out = []
    for cy in cfg["centers_y"]:
        for key, word, cx in cfg["words"]:
            out.append((key, word, (int(cx) - 40, int(cy) - 16,
                                    int(cx) + 41, int(cy) + 17)))
    return out


def main():
    print("追加任务七 · file_parts.png 验收")
    cfg = C.FILE_PARTS
    n = cfg["name"]
    s, d = src(n), dst(n)
    ALLOW = allow_windows()

    print("\n[1] 文件与尺寸")
    chk(n + " 尺寸/通道一致", s.shape == d.shape, "%s vs %s" % (s.shape, d.shape))
    chk(n + " RGBA 模式", Image.open(C.DST_DIR / (n + ".png")).mode == "RGBA")
    H, W = s.shape[:2]
    allow = np.zeros((H, W), bool)
    for x0, y0, x1, y1 in ALLOW:
        allow[y0:y1, x0:x1] = True
    bad = int(((s != d).any(axis=2) & ~allow).sum())
    chk(n + " 允许窗口外 0 改动", bad == 0, "越界 %d px" % bad)

    print("\n[2] 旧字擦除 + 中文落位")
    stroke = mask_of("stroke")
    clear = mask_of("erase")
    if stroke is None or clear is None:
        chk(n + " stroke/erase mask 存在", False)
    else:
        changed = (s != d).any(axis=2)
        r = float((changed & stroke).sum()) / max(int(stroke.sum()), 1)
        chk(n + " 旧字墨迹已擦除", r >= 0.95, "改动率 %.2f" % r)
        chk(n + " 清除窗内原图实笔画全部被改",
            int((changed & clear & (s[:, :, 3] > 150)).sum()) > 1500,
            "%d px" % int((changed & clear & (s[:, :, 3] > 150)).sum()))

    empty, ghost, wide = [], [], []
    for i, (key, word, w) in enumerate(cell_windows()):
        x0, y0, x1, y1 = w
        q = d[y0:y1, x0:x1]
        rgb, al = q[:, :, :3], q[:, :, 3]
        wh = (rgb.min(axis=2) > 200) & (al > 150)
        new_ink = int((wh & changed[y0:y1, x0:x1]).sum())
        if new_ink < 100:
            empty.append(i)
        if int(changed[y0:y1, x0:x1].sum()) < 200:
            ghost.append(i)
        ys, xs = np.nonzero(wh)
        width = int(xs.max() - xs.min() + 1) if len(xs) else 999
        if width > 50:            # 原英文 LOAD 62 / SAVE 57，中文 2 字 39~40
            wide.append((i, width))
    chk(n + " 6 格每格有中文（新增白字墨迹）", not empty, "空格 %s" % empty)
    chk(n + " 6 格每格确实重画过", not ghost, "未改格 %s" % ghost)
    chk(n + " 6 格白字 bbox 是中文 2 字（非英文 4 字母）", not wide, "超宽 %s" % wide)

    print("\n[3] 三行状态与配色")
    x0, x1 = cfg["clear_x"]
    row_med, row_bins = [], []
    for k, y0 in enumerate(cfg["clear_y0"]):
        q = d[y0:y0 + cfg["clear_h"], x0:x1]
        rgb, al = q[:, :, :3], q[:, :, 3]
        halo = (al >= 30) & (al <= 120) & (rgb[:, :, 0] < 150) & \
               (rgb[:, :, 1] > 100) & (rgb[:, :, 2] > 100)
        med = np.median(rgb[halo], axis=0).astype(int) if halo.sum() else np.zeros(3, int)
        row_med.append(med)
        row_bins.append(bins(al))
        diff = float(np.abs(med - np.array(cfg["row_glow"][k])).mean())
        chk(n + " 行%d 光晕配色与实测一致" % k, diff <= 10,
            "%s vs %s 差 %.1f" % (med, cfg["row_glow"][k], diff))
        core = (al > 240) & (rgb.min(axis=2) > 190)
        chk(n + " 行%d 白字为纯白" % k,
            core.sum() > 100 and np.median(rgb[core], axis=0).min() > 245,
            "n=%d" % int(core.sum()))
    chk(n + " 三行 alpha 分档完全相同（同一套字形）",
        np.array_equal(row_bins[0], row_bins[1]) and
        np.array_equal(row_bins[1], row_bins[2]),
        "%s / %s / %s" % (row_bins[0], row_bins[1], row_bins[2]))
    chk(n + " 三行光晕色确有状态差异",
        row_med[0][1] < row_med[1][1] < row_med[2][1],
        "G %s" % [int(m[1]) for m in row_med])

    print("\n[4] 逐像素保留的装饰")
    bad = 0
    for a0, b0, a1, b1 in cfg["keep"]:
        bad += int((s[b0:b1, a0:a1] != d[b0:b1, a0:a1]).any(axis=2).sum())
    chk(n + " 纸片/CHANGE/Day/NO./箭头/数字/图标/头像 逐像素保留",
        bad == 0, "改动 %d px" % bad)

    print("\n[5] 结构口径")
    chk(n + " 3 行 × 2 列 = 6 格",
        len(cfg["clear_y0"]) == 3 and len(cfg["words"]) == 2 and len(cell_windows()) == 6)
    chk(n + " 译名 LOAD→读档 / SAVE→存档",
        cfg["words"][0][1] == "读档" and cfg["words"][1][1] == "存档")
    chk(n + " 只改 SAVE/LOAD 两项（清除窗仅覆盖按钮文字带）",
        len(ALLOW) == 3 and all(w[2] - w[0] == 154 for w in ALLOW))

    print("\n通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  - " + f)
        sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
