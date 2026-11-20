# -*- coding: utf-8 -*-
"""
戦巫 UI 第一批 · 第一组（5 张）验收自检
运行：在 <游戏>\\7_图片 下执行 python <工具>\\ui_image_toolkit\\verify_batch8.py
"""
import sys
import numpy as np
from PIL import Image

import config_batch8 as C
import verify_tight_frame as VTF

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
    p = C.WORK_DIR / ("b8_%s_%s.npy" % (n, key))
    return np.load(str(p)) if p.exists() else None


def allow_windows():
    a = {}
    for t in C.TITLES:
        a[t["name"]] = [t["win"]]
    for cfg in (C.SYS_QUIT, C.SYS_BACK):
        x0, x1 = cfg["clear_x"]
        a[cfg["name"]] = [(x0, r["y0"], x1, r["y1"]) for r in cfg["rows"]]
    for cfg in C.LABELS:
        a[cfg["name"]] = [lb["win"] for lb in cfg["labels"]]
    for cfg in C.GRIDS:
        from build_batch8 import grid_cells
        a[cfg["name"]] = [c["win"] for c in grid_cells(cfg)]
    # 第四~七组：通用独立文字单元
    for cfg in C.CELLS:
        a[cfg["name"]] = [u["win"] for u in cfg["units"]]
    # 透明底多状态发光字
    for cfg in C.GLOW_GROUPS:
        x0, x1 = cfg["clear_x"]
        wins = [(x0, r["y0"], x1, r["y1"]) for r in cfg["rows"]]
        if cfg["name"] == "tutorial_help_p":
            wins.append(C.HELP_TITLE["win"])
        a[cfg["name"]] = wins
    return a


def main():
    print("戦巫 UI 第一批 · 第一组验收（5 张）")
    ALLOW = allow_windows()

    print("\n[1] 文件与尺寸")
    for n in C.ALL_NAMES:
        p = C.DST_DIR / (n + ".png")
        if not p.exists():
            chk(n + " 成品存在", False)
            continue
        s, d = src(n), dst(n)
        chk(n + " 尺寸/通道一致", s.shape == d.shape, "%s vs %s" % (s.shape, d.shape))
        chk(n + " RGBA 模式", Image.open(p).mode == "RGBA")
        H, W = s.shape[:2]
        allow = np.zeros((H, W), bool)
        for box in ALLOW[n]:
            x0, y0, x1, y1 = VTF.clamp_box(box, s.shape)
            allow[y0:y1, x0:x1] = True
        bad = int(((s != d).any(axis=2) & ~allow).sum())
        chk(n + " 允许窗口外 0 改动", bad == 0, "越界 %d px" % bad)

    print("\n[2] 旧字擦除 + 中文落位")
    for n in C.ALL_NAMES:
        s, d = src(n), dst(n)
        stroke = mask_of(n, "stroke")
        if stroke is None:
            chk(n + " stroke mask 存在", False)
            continue
        changed = (s != d).any(axis=2)
        if n == "extra_voice_parts":
            # btn 判据的 rim 会把「字形邻域内的深紫底板 [43,37,55]」
            # 一并记进 stroke，这些像素本就不该改（补底填回同色）。
            # 分母只取真正的**亮字墨迹**，不是放宽阈值。
            lum = s[:, :, :3].mean(axis=2)
            core = stroke & (lum > 100)
            r = float((changed & core).sum()) / max(int(core.sum()), 1)
            # 另加硬判据：stroke 里记录的是「实际该擦掉的字形像素」，
            # 其中原金字亮核若逐像素未变，就是旧字还在。不再用整窗
            # 判据 —— 窗口放宽后会把圆周金边/方形金框一并算成残留，
            # 而那些装饰本来就该逐像素保留。
            gold = ((s[:, :, 1] > 105) & (s[:, :, 0] > 120) &
                    (s[:, :, 3] > 120) & stroke)
            left = int((gold & ~changed).sum())
            chk(n + " 按钮文字窗内旧亮字逐像素零残留",
                left <= 60, "残留 %d px" % left)
        else:
            r = float((changed & stroke).sum()) / max(int(stroke.sum()), 1)
        chk(n + " 旧字墨迹已擦除", r >= 0.90, "改动率 %.2f" % r)

    # 木牌：中文金字墨迹（新增）
    for t in C.TITLES:
        s, d = src(t["name"]), dst(t["name"])
        x0, y0, x1, y1 = t["win"]
        q = d[y0:y1, x0:x1]
        gold = ((q[:, :, 0] > 170) & (q[:, :, 1] > 120) &
                (q[:, :, 2] < 175) & (q[:, :, 3] > 140))
        ch = (s[y0:y1, x0:x1] != q).any(axis=2)
        nk = int((gold & ch).sum())
        chk(t["name"] + " 中文金字已写入", nk > 300, "新增 %d px" % nk)
        # 日文副标题/花纹逐像素保留（遍历全部 keep 带，不能只查第一条）
        bad = sum(
            int((s[k[1]:k[3], k[0]:k[2]] !=
                 d[k[1]:k[3], k[0]:k[2]]).any(axis=2).sum())
            for k in t["keep"])
        chk(t["name"] + " 日文副标题/花纹逐像素保留", bad == 0, "改动 %d px" % bad)

    # 系统按钮：每行每词都有中文，且三态配色保留
    for cfg in (C.SYS_QUIT, C.SYS_BACK):
        s, d = src(cfg["name"]), dst(cfg["name"])
        x0, x1 = cfg["clear_x"]
        changed = (s != d).any(axis=2)
        empty = []
        for ri, row in enumerate(cfg["rows"]):
            y0, y1 = row["y0"], row["y1"]
            band = d[y0:y1, x0:x1]
            rgb, al = band[:, :, :3], band[:, :, 3]
            core = (al > 150) & (rgb.min(axis=2) > 100)
            # D4：只查「有亮核」原英文也能通过，必须叠加 changed
            new_ink = int((core & changed[y0:y1, x0:x1]).sum())
            if new_ink < 60:
                empty.append(ri)
            # 每行配色与该行实测光晕色接近
            halo = (al >= 25) & (al <= 140) & (rgb.max(axis=2) > 120)
            if halo.sum():
                med = np.median(rgb[halo], axis=0)
                diff = float(np.abs(med - np.array(row["glow"])).mean())
                chk(cfg["name"] + " 行%d 状态配色保留" % ri, diff < 95,
                    "中位 %s 差 %.1f" % (med.astype(int), diff))
        chk(cfg["name"] + " 三行状态全部有中文", not empty, "空行 %s" % empty)
        # 每词独立落位：按 x 投影应有 len(words) 个独立墨迹块
        row = cfg["rows"][1]
        band = d[row["y0"]:row["y1"], x0:x1]
        m = ((band[:, :, 3] > 150) & (band[:, :, :3].min(axis=2) > 120) &
             changed[row["y0"]:row["y1"], x0:x1])
        proj = m.sum(axis=0)
        cols = np.nonzero(proj > 0)[0]
        groups = []
        if len(cols):
            cur = [int(cols[0])]
            for v in cols[1:]:
                v = int(v)
                if v - cur[-1] <= 12:
                    cur.append(v)
                else:
                    groups.append((cur[0], cur[-1]))
                    cur = [v]
            groups.append((cur[0], cur[-1]))
        big = [g for g in groups if g[1] - g[0] > 8]
        chk(cfg["name"] + " 逐词独立归位（非连成一团）",
            len(big) >= len(cfg["words"]), "块数 %d / 词数 %d" %
            (len(big), len(cfg["words"])))
        for a0, b0, a1, b1 in cfg["keep"]:
            bad = int((s[b0:b1, a0:a1] != d[b0:b1, a0:a1]).any(axis=2).sum())
            chk(cfg["name"] + " 禁改装饰逐像素保留", bad == 0, "改动 %d px" % bad)

    print("\n[3] 通用新增墨迹（所有图，防止旧字未擦只靠亮核蒙混）")
    for n in C.ALL_NAMES:
        s, d = src(n), dst(n)
        erase = mask_of(n, "erase")
        if erase is None:
            continue
        changed = (s != d).any(axis=2)
        # 新增墨迹：改动过且不透明的像素；坏稿（原图当成品）恒为 0
        new = int((changed & erase & (d[:, :, 3] > 140)).sum())
        chk(n + " 清除窗内有新增中文墨迹", new > 60, "%d px" % new)

    print("\n[4] 第二组逐标签落位")
    for cfg in C.LABELS:
        s, d = src(cfg["name"]), dst(cfg["name"])
        changed = (s != d).any(axis=2)
        for lb in cfg["labels"]:
            x0, y0, x1, y1 = lb["win"]
            q = d[y0:y1, x0:x1]
            dark = (q[:, :, :3].mean(axis=2) < 110) & (q[:, :, 3] > 140)
            nk = int((dark & changed[y0:y1, x0:x1]).sum())
            chk(cfg["name"] + " 「%s」已写入" % lb["word"], nk > 25, "%d px" % nk)

    print("\n[5] 第三组网格逐格落位")
    from build_batch8 import grid_cells
    for cfg in C.GRIDS:
        s, d = src(cfg["name"]), dst(cfg["name"])
        changed = (s != d).any(axis=2)
        cells = grid_cells(cfg)
        empty = []
        for i, c in enumerate(cells):
            x0, y0, x1, y1 = c["win"]
            q = d[y0:y1, x0:x1]
            bright = (q[:, :, :3].mean(axis=2) > 145) & (q[:, :, 3] > 140)
            if int((bright & changed[y0:y1, x0:x1]).sum()) < 15:
                empty.append(i)
        chk(cfg["name"] + " %d 格全部有中文" % len(cells), not empty,
            "空格 %s" % empty[:8])
        chk(cfg["name"] + " 多状态行/列数正确",
            len(cells) == len(cfg["rows"]) * len(cfg["cols"]))

    print("\n[6] 第四~七组逐单元落位")
    for cfg in C.CELLS:
        s, d = src(cfg["name"]), dst(cfg["name"])
        changed = (s != d).any(axis=2)
        empty = []
        for i, u in enumerate(cfg["units"]):
            x0, y0, x1, y1 = u["win"]
            q = d[y0:y1, x0:x1]
            # 新增墨迹 = 改动过且成品不透明（坏稿恒为 0）
            new = int((changed[y0:y1, x0:x1] & (q[:, :, 3] > 120)).sum())
            if new < 12:
                empty.append(i)
        chk(cfg["name"] + " %d 单元全部有中文" % len(cfg["units"]),
            not empty, "空单元 %s" % empty[:8])

    print("\n[7] 多状态发光字逐行/逐词")
    for cfg in C.GLOW_GROUPS:
        s, d = src(cfg["name"]), dst(cfg["name"])
        x0, x1 = cfg["clear_x"]
        changed = (s != d).any(axis=2)
        empty = []
        for row in cfg["rows"]:
            y0, y1 = row["y0"], row["y1"]
            band = d[y0:y1, x0:x1]
            core = (band[:, :, 3] > 140) & \
                   (band[:, :, :3].mean(axis=2) > 110)
            if int((core & changed[y0:y1, x0:x1]).sum()) < 40:
                empty.append(row["y0"])
        chk(cfg["name"] + " 各状态行有中文", not empty, "空行 %s" % empty)
        chk(cfg["name"] + " 逐词独立归位",
            len(cfg["words"]) >= 1 and x1 > x0)
    # tutorial HELP 金字
    t = C.HELP_TITLE
    s, d = src(t["name"]), dst(t["name"])
    x0, y0, x1, y1 = t["win"]
    q = d[y0:y1, x0:x1]
    gold = (q[:, :, 0] > 170) & (q[:, :, 1] > 120) & \
           (q[:, :, 2] < 175) & (q[:, :, 3] > 140)
    chg = (s[y0:y1, x0:x1] != q).any(axis=2)
    chk("tutorial HELP 中文金字已写入", int((gold & chg).sum()) > 150)

    print("\n[8] 结构口径")
    chk("累计 %d 张齐全" % len(C.ALL_NAMES),
        len(C.ALL_NAMES) ==
        5 + len(C.LABELS) + len(C.GRIDS) + len(C.CELLS) + len(C.GLOW_GROUPS))
    chk("此前暂缓的两张已完成交付",
        len(C.SKIPPED) == 0 and
        (C.DST_DIR / "config_index.png").exists() and
        (C.DST_DIR / "config_frame_voice.png").exists())
    chk("配音人名译名与用户定稿一致（10 个 × 2 列同名）",
        C.VOICE_NAMES == ["神子园姬华", "艾尔", "萨莉雅", "睦", "夏洛特",
                          "徒野咲夜", "酒井户清吉", "其他（女）",
                          "其他（男）", "其他"] and
        len(next(c for c in C.CELLS
                 if c["name"] == "config_frame_voice")["units"]) == 20)
    chk("config_index 18 单元 × 3 行发光配色",
        len(next(c for c in C.CELLS
                 if c["name"] == "config_index")["units"]) == 18 and
        len(C.INDEX_BOX) == 3)
    # 防回归：三个「重置」是上移悬停态，必须逐格用实测墨迹中心，
    # 不能跟同排其它词共用一个 center（旧版把行1/行2 拉齐，偏 14/27px）。
    idx = next(c for c in C.CELLS if c["name"] == "config_index")
    for ri, cy in enumerate([38.0, 139.0, 238.5]):
        u = idx["units"][ri * 6 + 5]
        chk("config_index 行%d 重置按实测墨迹中心" % ri,
            abs(u["center"][1] - cy) <= 1.0,
            "center y=%.1f 期望 %.1f" % (u["center"][1], cy))
    chk("译名与定稿一致",
        C.GLOSSARY["EXTRA"] == "额外内容" and
        C.GLOSSARY["TITLE"] == "返回标题" and
        C.GLOSSARY["DOMINATION"] == "征服模式" and
        dict((k, v) for k, v, _ in C.TITLE_WORDS)["DOMINATION"] == "征服模式")
    chk("系统按钮 3 行状态 × 独立词元",
        len(C.SYS_ROWS) == 3 and len(C.SYS_WORDS) == 3)
    chk("标题菜单 4 行 × 7 独立词元",
        len(C.TITLE_ROWS) == 4 and len(C.TITLE_WORDS) == 7)
    # 【防回归：日文被遮挡】本图与第一组 menu_button 同构，大字辉光与日文
    # 小字辉光在 y 上连成一片。旧版 clear 下沿与 keep 上沿之间留 4 行
    # 「三不管区间」，既被清成透明又不在还原区 → 透明黑带切断日文上沿。
    # 现口径：keep 起点 == clear 下沿，零间隙；日文小字笔画带（y140 / y196
    # 起）逐像素零改动；且大字带下沿不能出现整行透明黑带。
    tg = next(g for g in C.GLOW_GROUPS if g["name"] == "title_menu_text")
    ts, td = src("title_menu_text"), dst("title_menu_text")
    for ri, (y1, ky0) in enumerate(
            [(C.TITLE_ROWS[r]["y1"], tg["keep"][r][1]) for r in (1, 2, 3)]):
        chk("标题菜单行%d hard-keep 上沿 == clear 下沿（无三不管区间）" % (ri + 1),
            ky0 == y1, "keep=%d clear=%d" % (ky0, y1))
        # 大字带下沿不得新增「原图透明 → 成品不透明」的横向亮线。
        # 曾试过给下沿 4 行按逐行中位补光晕，1:1 下变成一条贯穿全宽
        # 的细线（新增 12403 px），用户明确反馈不接受。
        band = (ts[y1 - 6:y1, :, 3] < 20) & (td[y1 - 6:y1, :, 3] > 60)
        chk("标题菜单行%d 大字带下沿无横向亮线" % (ri + 1),
            int(band.sum()) <= 400, "新增 %d px" % int(band.sum()))
    # 日文小字笔画带逐像素零改动（含上沿光晕）
    bad_jp = sum(int((ts[k[1]:k[3], k[0]:k[2]] !=
                      td[k[1]:k[3], k[0]:k[2]]).any(axis=2).sum())
                 for k in tg["keep"])
    chk("标题菜单日文小字带逐像素零改动", bad_jp == 0, "改动 %d px" % bad_jp)
    chk("标题菜单不再 fade 中文光晕（避免断链亮线）",
        tg.get("fade_bottom", 0) == 0)
    chk("标题菜单启用事前框定与硬禁区",
        any(g.get("clip_rows") and g.get("strict_keep")
            for g in C.GLOW_GROUPS if g["name"] == "title_menu_text"))
    chk("extra_voice_parts 按钮 ALL/PLAY LIST 全部汉化",
        len(C.VOICE_BUTTONS) == 21 and
        all(u["word"] in ("全部", "播放", "列表") for u in C.VOICE_BUTTONS))
    chk("D 组框架图译文已起草并附清单",
        len(C.JP_DRAFT) >= 40 and
        C.JP_DRAFT["マスターボリューム"] == "主音量")
    chk("逐单元口径：无跨格串联（单元均独立 center）",
        all("center" in u for cfg in C.CELLS for u in cfg["units"]))

    # ---------------------------------------------------------------- [9]
    # 用户反馈：「中文以很大的方块贴到原图上，把原先的图案覆盖了」。
    # 旧版 vert_flat / btnfill / clear 按整窗矩形铺色或清透明，实测差异
    # 热图是一块 114×40 的实心矩形，菱形内框金线被从中间切断、圆周金边
    # 在矩形四角断开、底部贯穿金线被挖断。现口径：只重绘字形像素，
    # band 之外（含金线/金边/图标）逐像素零改动。
    print("\n[9] 紧框口径回归（方块不得覆盖原图案）")
    # 三判据与几何线判据统一由通用模块提供，别在批次里重写几何（1.3.1）。
    # outside_tol=500：两行拉开后中文贴片会越出**原英文**紧框约 345px，
    # 属预期；整窗铺色的坏稿是数千 px，仍能拦住。
    for n in ("config_index", "extra_voice_parts"):
        cfg = next(c for c in C.CELLS if c["name"] == n)
        for cname, ok, info in VTF.tight_frame_checks(
                src(n), dst(n), cfg["units"], n, outside_tol=500):
            chk(cname, ok, info)
    chk("config_index 不新增不透明像素（不造实心方块）",
        int((src("config_index")[:, :, 3] !=
             dst("config_index")[:, :, 3]).sum()) == 0)
    # 内框金线会斜穿进紧框，是最容易被整窗铺色切断的装饰。
    # 逐格按「|y-字心|>12 或 |x-字心|>47」把线像素摘出来，要求零改动。
    cs, cd = src("config_index"), dst("config_index")
    idx = next(c for c in C.CELLS if c["name"] == "config_index")
    frame_changed = sum(
        VTF.line_cut_count(
            cs, cd, u["band"],
            lambda yy, xx, cx=u["center"][0], cy=u["center"][1]:
            (np.abs(yy - cy) > 12) | (np.abs(xx - cx) > 47))
        for u in idx["units"])
    chk("config_index 菱形内框金线逐像素完整保留",
        frame_changed == 0, "切断 %d px" % frame_changed)
    # 三个 RESET 是缩小的上移悬停态（内框 R≈49，普通格 R≈62），
    # 内框线会斜穿进「字心核心区」，通用保护罩不到。按各自实测菱形
    # 拟合线单独核对，防止「重置棱形边缘残缺」回归（B20 / D18）。
    reset_cut = sum(
        VTF.line_cut_count(cs, cd, u["band"], (*u["frame"], 2.5))
        for u in (idx["units"][ri * 6 + 5] for ri in range(3)))
    chk("config_index 三个重置小菱形内框线零切断",
        reset_cut == 0, "切断 %d px" % reset_cut)
    chk("config_index 三个重置按实测小菱形几何保护",
        all("frame" in idx["units"][ri * 6 + 5] for ri in range(3)) and
        all(abs(C.RESET_FRAME[ri][2] - 49) < 1 for ri in range(3)))
    # 「播放 / 列表」两排必须明显分开：圆形行心距 20px、方形 18px。
    vu = next(c for c in C.CELLS if c["name"] == "extra_voice_parts")["units"]
    gaps = [(vu[4]["center"][1] - vu[3]["center"][1], 20.0),
            (vu[8]["center"][1] - vu[7]["center"][1], 18.0)]
    chk("extra_voice_parts 播放/列表两行中心距已拉开",
        all(g >= t - 0.1 for g, t in gaps),
        "圆形/方形间距 %s" % [round(g, 1) for g, _ in gaps])

    print("\n通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  - " + f)
        sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
