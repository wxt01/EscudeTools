# -*- coding: utf-8 -*-
"""
追加任务四（13 张）自检。运行：在 工具/ 目录执行 python verify_batch4.py

判据分四类：
  1. 文件身份：存在 / 尺寸 / RGBA / 与对照图同源（由 compare_batch4 生成 md5）
  2. 改动范围：擦除 mask 之外逐像素 0 改动；需保留的图标、数字、% 、徽标、笔刷条保留
  3. 擦字结果：每个文字窗内「原图实笔画逐像素保留率」必须低（旧英文没留下）
  4. 排版与状态：格内必须有中文、左沿对齐、右沿不超格界、逐格状态配色正确
"""
import os
import sys
import numpy as np
from PIL import Image

import config_batch4 as C

PASS, FAIL = [], []


def chk(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("  OK   " if ok else "  FAIL ") + name + ("  " + str(detail) if detail else ""))


def L(d, n):
    return np.array(Image.open(d / (n + ".png")).convert("RGBA"))


def diff_outside(n, mask):
    # 允许改动区 = 擦除 mask 外扩 8px：中文重画时字形/淡描边/辉光会略微
    # 溢出擦除 mask（实心底板只擦了细笔画，中文却画在整块字位上）。
    # 扩 8px 仍然只覆盖字位附近，真正的图标数字保留由 keep_exact 逐像素把关。
    from PIL import ImageFilter
    allow = np.array(Image.fromarray((mask * 255).astype(np.uint8), "L")
                     .filter(ImageFilter.MaxFilter(17))) > 0
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    changed = (s != d).any(axis=2) & ~allow
    return int(changed.sum()), ~allow, s, d


def keep_exact(n, boxes, tag):
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    bad = 0
    for x0, y0, x1, y1 in boxes:
        bad += int((s[y0:y1, x0:x1] != d[y0:y1, x0:x1]).any(axis=2).sum())
    chk(n + " " + tag + " 逐像素保留", bad == 0, "改动 %d px" % bad)


def keep_except_windows(n, windows, tag, pad=3):
    """
    第 5 批起改用：声明「允许改动的窗口」，窗口外一律逐像素 0 改动。

    比列一堆 keep 框更严：图标、数字、箭头、头像、笔刷条、徽标外圈
    只要有一个像素被动到就会报出来。窗口只留 3px 余量给描边/辉光溢出。
    """
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    H, W = s.shape[:2]
    allow = np.zeros((H, W), bool)
    for w in windows:
        # 允许写成 5 元组自带 pad：辉光标签比小格字溢得更远，分别给余量。
        x0, y0, x1, y1 = w[:4]
        p = w[4] if len(w) > 4 else pad
        allow[max(0, y0-p):min(H, y1+p),
              max(0, x0-p):min(W, x1+p)] = True
    bad = int(((s != d).any(axis=2) & ~allow).sum())
    chk(n + " " + tag + " 窗口外逐像素保留", bad == 0,
        "窗口外改动 %d px" % bad)


def erased_check(n, boxes, tag, thr=0.80):
    """
    用 build 阶段记录的 stroke mask（原图真正的文字笔画）判断旧字改动率。
    实心底板的 alpha 全是 255，不能拿 alpha 当「旧字」判据 —— 那样整块
    底板都会被算进去，保留率自然虚高。
    """
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    p = C.WORK_DIR / ("b4_%s_stroke.npy" % n)
    if not p.exists():
        chk(n + " " + tag + " stroke 已记录", False)
        return
    stroke = np.load(p)
    changed = (s != d).any(axis=2) & stroke
    rate = changed.sum() / max(stroke.sum(), 1)
    chk(n + " " + tag + " 旧字已擦除", rate >= thr,
        "笔画改动率 %.1f%%" % (100 * rate))


def cell_ink(n, boxes, tag, minimum=40):
    """格内确实画了新东西：统计与原图的差异像素（底板本身不透明，不能数 alpha）。"""
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    counts = []
    for x0, y0, x1, y1 in boxes:
        counts.append(int((s[y0:y1, x0:x1] != d[y0:y1, x0:x1]).any(axis=2).sum()))
    chk(n + " " + tag + " 每格有中文", min(counts) >= minimum,
        "最少 %d px 改动" % min(counts))


def main():
    print("追加任务四 · 自检")
    names = C.ALL_NAMES
    for n in names:
        p = C.DST_DIR / (n + ".png")
        chk(n + " 成品存在", p.exists())
        if not p.exists():
            continue
        s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
        chk(n + " 尺寸/RGBA", s.shape == d.shape and d.shape[2] == 4, str(d.shape))
        mp = C.WORK_DIR / ("b4_%s_erase.npy" % n)
        chk(n + " 擦除 mask 已记录", mp.exists())
        if mp.exists():
            mask = np.load(mp)
            bad, _, _, _ = diff_outside(n, mask)
            chk(n + " 擦除区外 0 改动", bad == 0, "%d px" % bad)

    # ---- 1 四块木牌
    print("\n[1] 木牌标题")
    for cfg in C.TITLES:
        n = cfg["name"]
        w = cfg["win"]
        erased_check(n, [w], "烙字", 0.80)
        cell_ink(n, [w], "中文", 200)
    keep_exact("save_title", [(0, 0, 411, 10), (340, 0, 411, 97)], "红绳与牌外", )

    # ---- 2 率牌（% 与数字整块保留）
    print("\n[2] 鉴赏率牌")
    for cfg in C.RATES:
        n = cfg["name"]
        erased_check(n, [cfg["win"]], "金字", 0.80)
        cell_ink(n, [cfg["win"]], "中文", 60)
        keep_exact(n, [(170, 0, 242, 99), (0, 70, 242, 99)], "% 与数字")

    # ---- 3 stand_back（左右箭头装饰）
    print("\n[3] stand_back")
    n = "stand_back"
    erased_check(n, [(8, 3, 102, 36), (8, 41, 102, 74), (8, 79, 102, 112)],
                 "三行 BACK", 0.80)
    cell_ink(n, [(8, y0, 102, y1) for y0, y1 in C.STAND_BACK["rows"]],
             "三行中文", 60)
    keep_exact(n, [(0, 0, 8, 114), (102, 0, 110, 114)], "左右箭头装饰")

    # ---- 4 extra_mode（六列 × 三行，配色例外）
    print("\n[4] extra_mode")
    n = "extra_mode"
    cfg = C.EXTRA_MODE
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    cells, bad_l, bad_r, bad_empty = [], [], [], []
    for ri, (y0, y1) in enumerate(cfg["rows"]):
        for ci, (x0, x1) in enumerate(cfg["cols"]):
            q = d[y0:y1, x0:x1]
            ink = q[:, :, 3] > 60
            if not ink.any():
                bad_empty.append((ri, ci))
                continue
            ys, xs = np.nonzero(ink)
            left, right = int(xs.min()), int(xs.max())
            if abs(left - (cfg["lefts"][ci] - x0)) > 4:
                bad_l.append((ri, ci, left))
            if right >= x1 - x0 - 2:
                bad_r.append((ri, ci, right, x1 - x0))
            cells.append((x0, y0, x1, y1))
    chk(n + " 18 格均有中文", not bad_empty, str(bad_empty[:3]))
    chk(n + " 六列左沿对齐原字", not bad_l, str(bad_l[:3]))
    chk(n + " 右沿不越格界", not bad_r, str(bad_r[:3]))
    erased_check(n, cells, "18 格英文", 0.95)
    # 逐格配色：第 3 行除第 4 格外应偏红，第 4 格应偏青白
    red_rows, blue_c3 = [], []
    for ci, (x0, x1) in enumerate(cfg["cols"]):
        for ri, (y0, y1) in enumerate(cfg["rows"]):
            q = d[y0:y1, x0:x1]
            core = q[:, :, 3] > 190
            if not core.any():
                continue
            r, g, b = np.median(q[:, :, :3][core], axis=0)
            if ri == 2 and ci != 3:
                red_rows.append(r - g > 90)
            if ri == 2 and ci == 3:
                blue_c3.append(g - r > 20 or (r > 200 and g > 200))
    chk(n + " 第 3 行五格红字", len(red_rows) == 5 and all(red_rows),
        str(red_rows))
    chk(n + " 第 3 行第 4 格仍为白/青字", bool(blue_c3) and all(blue_c3),
        str(blue_c3))

    # ---- 5 stand_parts（左侧图标/数字/箭头保留；徽标两个白框内允许改）
    print("\n[5] stand_parts")
    n = "stand_parts"
    cfg = C.STAND_PARTS
    erased_check(n, [(470, y0, 645, y1) for y0, y1 in cfg["rows"]],
                 "六行 RESET", 0.80)
    cell_ink(n, [(470, y0, 645, y1) for y0, y1 in cfg["rows"]],
             "六行中文", 100)
    # 用户第 5 批要求：六行中文都要居中到墨迹中心 555
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    centers, bad_c = [], []
    for y0, y1 in cfg["rows"]:
        q = d[y0:y1, 470:645]
        w = ((q[:, :, 0] > 200) & (q[:, :, 1] > 205) &
             (q[:, :, 2] > 200) & (q[:, :, 3] > 170))
        ys, xs = np.nonzero(w)
        c = 470 + (xs.min() + xs.max()) / 2.0
        centers.append(round(c, 1))
        if abs(c - cfg["center_x"]) > 4:
            bad_c.append((y0, round(c, 1)))
    chk(n + " 六行中文居中到 555", not bad_c,
        "中心 %s 偏差 %s" % (centers, bad_c))
    badge_dark = []
    for bl in C.BADGE_LABELS:
        x0, y0, x1, y1 = bl["box"]
        q = d[y0 + 1:y1 - 1, x0 + 1:x1 - 1]
        old = s[y0 + 1:y1 - 1, x0 + 1:x1 - 1]
        dark = ((q[:, :, 0] < 190) & (q[:, :, 1] < 130) &
                (q[:, :, 2] < 140)).sum()
        changed = int((q != old).any(axis=2).sum())
        # 只数深色像素会被原稿的 Back/Front 蒙混过关，必须同时要求框被重画过。
        badge_dark.append((bl["word"], int(dark), changed))
    chk(n + " 徽标 Back/Front 两框均有中文",
        all(v >= 25 and ch >= 60 for _, v, ch in badge_dark), str(badge_dark))
    keep_except_windows(n,
        [(cfg["win_x"][0], y0, cfg["win_x"][1], y1) for y0, y1 in cfg["rows"]] +
        [bl["box"] for bl in C.BADGE_LABELS],
        "图标/数字/上下箭头/徽标外圈")

    # ---- 6 三张透明标签图（图标、数字、笔刷线保留）
    print("\n[6] 部件图标签")
    for cfg in C.GLOW_LABELS:
        n = cfg["name"]
        erased_check(n, [lb["win"] for lb in cfg["labels"]], "英文标签", 0.95)
        cell_ink(n, [lb["win"] for lb in cfg["labels"]], "中文标签", 60)
    keep_except_windows("music_parts",
        [tuple(lb["win"]) + (5,) for cfg2 in C.GLOW_LABELS
         if cfg2["name"] == "music_parts" for lb in cfg2["labels"]] +
        [C.NOW_PLAYING["win"]],
        "顶部青条/图标按钮/图钉/数字面板", pad=3)
    keep_except_windows("voice_parts",
        [tuple(lb["win"]) + (5,) for cfg2 in C.GLOW_LABELS
         if cfg2["name"] == "voice_parts" for lb in cfg2["labels"]] +
        [c["win"] for c in C.VOICE_SMALL_CELLS],
        "头像/箭头方块/勾选/垃圾桶/数字区/徽标", pad=3)
    keep_except_windows("visual_parts",
        [lb["win"] for cfg2 in C.GLOW_LABELS if cfg2["name"] == "visual_parts"
         for lb in cfg2["labels"]],
        "播放箭头与数字", pad=3)

    # ---- 7 第 5 批新增：NOW PLAYING、徽标、15 个小格
    print("\n[7] 第 5 批口述修订")
    n = "music_parts"
    w = C.NOW_PLAYING["win"]
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    q = d[w[1]:w[3], w[0]:w[2]]
    yellow = (q[:, :, 0] > 200) & (q[:, :, 1] > 150) & (q[:, :, 2] < 120) & (q[:, :, 3] > 40)
    core = (q[:, :, 0] > 230) & (q[:, :, 1] > 230) & (q[:, :, 2] > 210) & (q[:, :, 3] > 150)
    chk(n + " NOW PLAYING 窗口有黄光白字", yellow.sum() > 400 and core.sum() > 60,
        "黄光 %d / 白字 %d px" % (yellow.sum(), core.sum()))
    old = s[w[1]:w[3], w[0]:w[2]]
    oldwhite = ((old[:, :, 0] > 225) & (old[:, :, 1] > 225) &
                (old[:, :, 2] > 200) & (old[:, :, 3] > 100))
    rate = ((old != q).any(axis=2) & oldwhite).sum() / max(oldwhite.sum(), 1)
    chk(n + " NOW PLAYING 旧字已擦除", rate > 0.95,
        "笔画改动率 %.1f%%" % (100 * rate))

    n = "voice_parts"
    s, d = L(C.SRC_DIR, n), L(C.DST_DIR, n)
    empty, ghost, overflow = [], [], []
    for c in C.VOICE_SMALL_CELLS:
        x0, y0, x1, y1 = c["win"]
        q = d[y0:y1, x0:x1]
        old = s[y0:y1, x0:x1]
        white = ((q[:, :, 0] > 200) & (q[:, :, 1] > 205) &
                 (q[:, :, 2] > 200) & (q[:, :, 3] > 170))
        oldwhite = ((old[:, :, 0] > 200) & (old[:, :, 1] > 205) &
                    (old[:, :, 2] > 200) & (old[:, :, 3] > 170))
        changed = (old != q).any(axis=2)
        # 白像素数会连原稿英文一起算进去，必须同时要求这一格确实被重画过。
        if white.sum() < 25 or changed.sum() < 120:
            empty.append(c["tag"])
        r = (changed & oldwhite).sum() / max(oldwhite.sum(), 1)
        if r < 0.90:
            ghost.append((c["tag"], round(r, 2)))
    chk(n + " 15 格均有中文", not empty, str(empty[:4]))
    chk(n + " 15 格 ALL/PLAY LIST 旧字已擦除", not ghost, str(ghost[:4]))
    chk(n + " 小格数量 = 15（9 ALL + 6 PLAY LIST）",
        len(C.VOICE_SMALL_CELLS) == 15, str(len(C.VOICE_SMALL_CELLS)))

    print("\n结果: %d 通过 / %d 失败" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项:")
        for f in FAIL:
            print("  -", f)
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
