# -*- coding: utf-8 -*-
"""
追加任务五 + 六（8 张）的验收自检。运行：python verify_batch6.py
坏稿探针：python _badprobe6.py

口径沿用第 4/5 批：
  · 尺寸、模式、状态行数不变
  · 允许改动窗口之外一律 0 改动（声明窗口，而不是列一堆 keep_exact）
  · 旧字墨迹区必须有足够比例被重画过
  · 每个文字格必须有「新增的字色墨迹」，且整格确实被重画过
  · 明确禁改的图形/数字/装饰逐像素保留

★ 本版修订（第 6 批自检订正）：
  1) 旧版用固定色系判据（white/dark）判「有没有中文」，但同一张图里
     panel 的 BLOCK/PREVIEW 是浅棕字、config_parts 后两列 MUTE 是深灰字，
     被误判为空格（3 条假失败里的 2 条）。
     现改为「新增字色墨迹」：颜色取自 config_batch6 里各格实际声明的 fill，
     且要求该像素相对原图确实变过。既不会因字色不同误判，也不会把
     原图里同色系的英文/纸纹当成中文（原图基线恒为 0，见 _badprobe6.py）。
  2) 旧版第 [4] 节把 dd 赋成 dst("config_parts")，却拿它去切 chart_parts
     的擦除窗，读的是错图（config 在那块有 8 个不透明像素），导致
     「目已清空」假失败。现改为显式 dst("chart_parts")。
  3) 增加「目原图确实有字」检查，避免「本来就没字、擦了个寂寞」也算通过。
"""
import sys
import numpy as np
from PIL import Image

import config_batch6 as C

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


def mask_of(n, key):
    p = C.WORK_DIR / ("b6_%s_%s.npy" % (n, key))
    return np.load(str(p)) if p.exists() else None


# ---------------------------------------------------------------- 允许改动窗口
def allow_windows():
    a = {}
    a["title"] = [C.TITLE["win"]]
    q = C.QUIT
    a["quit"] = [(x0 + 4, ry + 3, x0 + 106, ry + 35)
                 for ry in q["rows"] for x0 in q["cols"]]
    a["rate"] = [C.RATE["win"]]
    a["chart_parts"] = [C.CHART_PARTS["erase_win"]]
    d = C.DIALOG
    a["dialog"] = [d["mark_win"]] + [
        (d["jump_win_x"][0], ry + 3, d["jump_win_x"][1], ry + 34)
        for ry in d["jump_rows"]]
    a["panel"] = [lb["win"] for lb in C.PANEL["labels"]]
    a["confirm_parts"] = C.CONFIRM["wins"]
    c = C.CONFIG_PARTS
    a["config_parts"] = (
        [(x0 + 1, ry, x0 + 40, ry + 12)
         for ry in c["rows"] for x0 in c["mute_cols"]] +
        # 右边界比中文落位窗多 3px：旧 "ALL" 尾笔在 x0+42..44 需要擦除
        [(x0 + 5, ry + 6, x0 + 44, ry + 19)
         for ry in c["all_rows"] for x0 in c["all_cols"]])
    return a


def outside_check(n, wins, pad=2):
    s, d = src(n), dst(n)
    H, W = s.shape[:2]
    allow = np.zeros((H, W), bool)
    for x0, y0, x1, y1 in wins:
        allow[max(0, y0 - pad):min(H, y1 + pad),
              max(0, x0 - pad):min(W, x1 + pad)] = True
    bad = int(((s != d).any(axis=2) & ~allow).sum())
    chk(n + " 允许窗口外 0 改动", bad == 0, "越界 %d px" % bad)


def old_erased(n, ratio=0.80):
    s, d = src(n), dst(n)
    stroke = mask_of(n, "stroke")
    if stroke is None:
        chk(n + " stroke mask 存在", False)
        return
    changed = (s != d).any(axis=2)
    r = float((changed & stroke).sum()) / max(int(stroke.sum()), 1)
    chk(n + " 旧字墨迹已擦除", r >= ratio, "改动率 %.2f" % r)


def new_ink(n, win, fill, tol=25):
    """新增字色墨迹：成品里是声明的 fill 色、不透明、且相对原图变过。

    只看颜色会误收原图里同色系的英文/纸纹（panel 原图同窗命中 94~575），
    所以叠加 changed 条件；原图当成品时该值恒为 0（坏稿探针可验）。
    """
    s, d = src(n), dst(n)
    x0, y0, x1, y1 = win
    q = d[y0:y1, x0:x1]
    f = np.array(fill, np.int32)
    fm = (np.abs(q[:, :, :3] - f).max(axis=2) <= tol) & (q[:, :, 3] > 150)
    ch = (s[y0:y1, x0:x1] != q).any(axis=2)
    return int((fm & ch).sum())


def _as_fills(fills, k):
    if (isinstance(fills, (list, tuple)) and len(fills) == 3
            and all(isinstance(v, (int, float)) for v in fills)):
        return [tuple(fills)] * k
    assert len(fills) == k, "fills 数量与窗口数不符"
    return [tuple(f) for f in fills]


def fill_cell_check(n, wins, fills, min_n, tag):
    s, d = src(n), dst(n)
    changed = (s != d).any(axis=2)
    F = _as_fills(fills, len(wins))
    empty, ghost = [], []
    for i, (w, f) in enumerate(zip(wins, F)):
        x0, y0, x1, y1 = w
        if int(changed[y0:y1, x0:x1].sum()) < 20:
            ghost.append(i)
        if new_ink(n, w, f) < min_n:
            empty.append(i)
    chk(n + " " + tag + " 每格有中文（新增字色墨迹）", not empty, "空格 %s" % empty)
    chk(n + " " + tag + " 每格确实重画过", not ghost, "未改格 %s" % ghost)


def keep_exact(n, boxes, tag):
    s, d = src(n), dst(n)
    bad = 0
    for x0, y0, x1, y1 in boxes:
        bad += int((s[y0:y1, x0:x1] != d[y0:y1, x0:x1]).any(axis=2).sum())
    chk(n + " " + tag + " 逐像素保留", bad == 0, "改动 %d px" % bad)


def main():
    print("追加任务五 + 六 · 8 张验收")
    ALLOW = allow_windows()

    print("\n[1] 文件与尺寸")
    for n in C.ALL_NAMES:
        p = C.DST_DIR / (n + ".png")
        if not p.exists():
            chk(n + " 成品存在", False)
            continue
        s, d = src(n), dst(n)
        chk(n + " 尺寸/通道一致", s.shape == d.shape,
            "%s vs %s" % (s.shape, d.shape))
        chk(n + " RGBA 模式", Image.open(p).mode == "RGBA")
        outside_check(n, ALLOW[n])

    print("\n[2] 旧字擦除 + 中文落位")
    for n in C.ALL_NAMES:
        if not (C.DST_DIR / (n + ".png")).exists():
            continue
        old_erased(n)

    q = C.QUIT
    quit_w = [(x0 + 4, ry + 3, x0 + 106, ry + 35)
              for ry in q["rows"] for x0 in q["cols"]]
    fill_cell_check("quit", quit_w, q["style"]["fill"], 45, "9 格 TITLE/QUIT/BACK")
    fill_cell_check("rate", [C.RATE["win"]], C.RATE["style"]["fill"], 25, "Flow")
    d = C.DIALOG
    fill_cell_check("dialog", [d["mark_win"]], d["mark_style"]["fill"], 35, "MARKING")
    jump_w = [(d["jump_win_x"][0], ry + 3, d["jump_win_x"][1], ry + 34)
              for ry in d["jump_rows"]]
    fill_cell_check("dialog", jump_w, d["jump_style"]["fill"], 80, "3 行 BLOCK JUMP")
    fill_cell_check("panel", [lb["win"] for lb in C.PANEL["labels"]],
                    [lb["style"]["fill"] for lb in C.PANEL["labels"]],
                    35, "4 个纸片标签")
    fill_cell_check("confirm_parts", C.CONFIRM["wins"], C.CONFIRM["style"]["fill"],
                    60, "3 处日文标签")
    c = C.CONFIG_PARTS
    mute_w = [(x0 + 1, ry, x0 + 40, ry + 12)
              for ry in c["rows"] for x0 in c["mute_cols"]]
    mute_f = [c["mute_style"]["light" if ci < 2 else "dark"]["fill"]
              for _ in c["rows"] for ci in range(len(c["mute_cols"]))]
    all_w = [(x0 + 5, ry + 6, x0 + 41, ry + 19)
             for ry in c["all_rows"] for x0 in c["all_cols"]]
    fill_cell_check("config_parts", mute_w, mute_f, 40, "MUTE 12 格（亮 6 / 暗 6）")
    fill_cell_check("config_parts", all_w, c["all_style"]["fill"], 20, "ALL 6 格")

    print("\n[3] 逐像素保留的图形/数字/装饰")
    keep_exact("chart_parts", [C.CHART_PARTS["keep_win"]], "「日」字")
    keep_exact("rate", [(0, 88, 240, 162), (100, 55, 240, 120),
                        (0, 0, 240, 55)], "数字/%/胶带外区域")
    keep_exact("confirm_parts", C.CONFIRM["keep"],
               "菱形按钮/CAUTION 胶带/勾选/竖条")
    # 右缘禁改区从 423 起：x420~422 是 ALL 旧字尾笔，属于应擦除区
    keep_exact("config_parts", [(0, 0, 160, 294), (423, 0, 430, 294),
                                (0, 126, 430, 294)],
               "加减喇叭图标/数字/下半部图形")
    keep_exact("dialog", [(0, 0, 231, 125), (100, 125, 231, 180),
                          (0, 180, 231, 260), (0, 395, 231, 585)],
               "纸片/表格/脸圈图标")
    keep_exact("panel", [(0, 40, 374, 95), (0, 160, 374, 300),
                         (0, 360, 374, 530), (0, 590, 374, 720)],
               "面板/铆钉/横线")

    print("\n[4] 结构口径")
    chk("config_parts MUTE 12 格 + ALL 6 格 = 18 格",
        len(mute_w) == 12 and len(all_w) == 6)
    chk("config_parts 两套行高（MUTE 42 / ALL 47）",
        c["rows"] == [0, 42, 84] and c["all_rows"] == [0, 47, 94])
    # 只擦「目」不写字：擦除窗内应全透明，且「日」区无改动
    ew = C.CHART_PARTS["erase_win"]
    ch = dst("chart_parts")                       # ← 旧版误用 dst("config_parts")
    a = ch[ew[1]:ew[3], ew[0]:ew[2]]
    chk("chart_parts 「目」已清空", int((a[:, :, 3] > 0).sum()) == 0,
        "残留 %d px" % int((a[:, :, 3] > 0).sum()))
    chk("chart_parts 「目」原图确实有字（非空擦）",
        int((src("chart_parts")[ew[1]:ew[3], ew[0]:ew[2], 3] > 0).sum()) > 20)
    # 防回归：旧 "ALL" 最右一撇在 x420~422，曾被擦除窗漏掉，每格留一个白点
    cd = dst("config_parts")
    for ry in c["all_rows"]:
        q = cd[ry + 8:ry + 19, 420:423]
        w = ((q[:, :, 0] > 165) & (q[:, :, 1] > 165) &
             (q[:, :, 2] > 165) & (q[:, :, 3] > 110))
        chk("config_parts ALL 尾笔白点已清除 y=%d" % ry, int(w.sum()) == 0,
            "残留 %d px" % int(w.sum()))
    chk("title FLOWCHART → 流程图 有字",
        new_ink("title", C.TITLE["win"], C.TITLE["style"]["fill"]) > 200)

    print("\n通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  - " + f)
        sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
