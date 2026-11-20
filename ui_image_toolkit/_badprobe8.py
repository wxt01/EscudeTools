# -*- coding: utf-8 -*-
"""第一组坏稿探针：确认 verify_batch8.py 能拦住「没汉化」和「漏一行」。"""
import shutil
import sys
from pathlib import Path
import numpy as np
from PIL import Image

import config_batch8 as C
import verify_batch8 as V

BAD = C.WORK_DIR / "badprobe8"
GOOD_DST = C.DST_DIR


def arr(p):
    return np.array(Image.open(p).convert("RGBA")).astype(np.int32)


def run(dst_dir):
    V.PASS.clear()
    V.FAIL.clear()
    saved = V.C.DST_DIR
    V.C.DST_DIR = Path(dst_dir)
    try:
        V.main()
        raise AssertionError("坏稿竟然通过了自检！")
    except SystemExit as e:
        assert e.code == 1, "坏稿竟然通过了自检！"
    finally:
        V.C.DST_DIR = saved
    return list(V.FAIL)


def main():
    print("=" * 60)
    print("探针 A：整图坏稿（原图当成品）")
    print("=" * 60)
    fA = run(C.SRC_DIR)
    print("\n失败 %d 条：" % len(fA))
    for f in fA[:8]:
        print("   - " + f)
    assert len(fA) >= 8, "整图坏稿没被拦住"
    assert any("旧字墨迹" in x or "中文金字" in x or "空行" in x for x in fA)
    print(">>> 探针 A 通过\n")

    if BAD.exists():
        shutil.rmtree(BAD)
    BAD.mkdir(parents=True)
    for n in C.ALL_NAMES:
        shutil.copy2(GOOD_DST / (n + ".png"), BAD / (n + ".png"))
    # 定点破坏 1：只把木牌大字还原成英文
    t = C.TITLES[0]
    p = BAD / (t["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (t["name"] + ".png"))
    x0, y0, x1, y1 = t["win"]
    d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)
    # 定点破坏 2：只把 sys_quit 第 1 行还原成英文（模拟漏行）
    cfg = C.SYS_QUIT
    p = BAD / (cfg["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (cfg["name"] + ".png"))
    row = cfg["rows"][1]
    x0, x1 = cfg["clear_x"]
    d[row["y0"]:row["y1"], x0:x1] = s[row["y0"]:row["y1"], x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    # 定点破坏 3：D 组框架图一个金框还原成日文（模拟漏一个设置项）
    cfg = next(c for c in C.CELLS if c["name"] == "config_frame_sound")
    p = BAD / (cfg["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (cfg["name"] + ".png"))
    u = cfg["units"][1]
    x0, y0, x1, y1 = u["win"]
    d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    # 定点破坏 4：C 组 popup 第 3 列整列还原（模拟漏一列状态）
    cfg = next(c for c in C.CELLS if c["name"] == "common_popup_parts")
    p = BAD / (cfg["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (cfg["name"] + ".png"))
    for u in cfg["units"][2::4]:
        x0, y0, x1, y1 = u["win"]
        d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    # 定点破坏 5：title_menu_text 一行还原成英文（模拟漏一个状态行）
    cfg = next(c for c in C.GLOW_GROUPS if c["name"] == "title_menu_text")
    p = BAD / (cfg["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (cfg["name"] + ".png"))
    row = cfg["rows"][1]
    x0, x1 = cfg["clear_x"]
    d[row["y0"]:row["y1"], x0:x1] = s[row["y0"]:row["y1"], x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    # 定点破坏 6：抹掉一行日文假名副标题（用户反馈的「日文被覆盖」）。
    # 旧自检 band 从清除窗下沿之后起、只查幸存的下半截，正是漏检点。
    d = arr(p)
    k0, ky0, k1, ky1 = cfg["keep"][2]      # 行 2 日文带 y142..164
    d[ky0:ky1, k0:k1] = 0
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    # 定点破坏 7：extra_voice_parts 一个按钮单元还原成英文 ALL
    cfg = next(c for c in C.CELLS if c["name"] == "extra_voice_parts")
    p = BAD / (cfg["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (cfg["name"] + ".png"))
    u = cfg["units"][5]                    # 第 1 行圆形 ALL
    x0, y0, x1, y1 = u["win"]
    d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    # 定点破坏 8：config_index 一个菱形还原成英文
    cfg = next(c for c in C.CELLS if c["name"] == "config_index")
    p = BAD / (cfg["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (cfg["name"] + ".png"))
    u = cfg["units"][7]
    x0, y0, x1, y1 = u["win"]
    d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    # 定点破坏 9：config_frame_voice 一个人名单元还原成日文
    cfg = next(c for c in C.CELLS if c["name"] == "config_frame_voice")
    p = BAD / (cfg["name"] + ".png")
    d, s = arr(p), arr(C.SRC_DIR / (cfg["name"] + ".png"))
    u = cfg["units"][3]
    x0, y0, x1, y1 = u["win"]
    d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    print("=" * 60)
    print("探针 B：定点坏稿（9 处，含日文带被覆盖 / 按钮漏汉化 / 两张新图）")
    print("=" * 60)
    fB = run(BAD)
    print("\n失败 %d 条：" % len(fB))
    for f in fB:
        print("   - " + f)
    assert any("中文金字已写入" in x for x in fB), "漏检：木牌未汉化"
    assert any("三行状态全部有中文" in x or "逐词独立" in x for x in fB), "漏检：漏行"
    assert any("config_frame_sound" in x and "单元" in x for x in fB), \
        "漏检：D 组金框漏一个设置项"
    assert any("common_popup_parts" in x and "单元" in x for x in fB), \
        "漏检：popup 漏一整列状态"
    assert any("title_menu_text" in x for x in fB), \
        "漏检：标题菜单漏一个状态行"
    assert any("禁改装饰逐像素保留" in x or "允许窗口外" in x for x in fB), \
        "漏检：日文假名副标题被抹（本轮修复的核心回归点）"
    assert any("extra_voice_parts" in x and "单元" in x for x in fB), \
        "漏检：按钮 ALL 漏汉化"
    assert any("config_index" in x and "单元" in x for x in fB), \
        "漏检：发光菱形漏一格"
    assert any("config_frame_voice" in x and "单元" in x for x in fB), \
        "漏检：配音人名漏一格"
    assert len(fB) <= 26, "误伤过多：%d 条" % len(fB)
    print(">>> 探针 B 通过：9 处定点破坏被精确点名")
    print("\n坏稿探针全部通过。")
    return 0


if __name__ == "__main__":
    main()
