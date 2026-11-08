# -*- coding: utf-8 -*-
"""
坏稿探针：故意把成品改坏，确认 verify_batch6.py 真能拦住，而不是「怎么都全绿」。

探针 A（整图坏稿）：直接把 原图/ 当成品 —— 应大量失败。
探针 B（定点坏稿）：只把 3 个具体格子还原成原图英文，其余 7 张保持正品，
  自检应当精确点名这 3 处，且其它项仍通过。
运行：python _badprobe6.py
"""
import shutil
import sys
from pathlib import Path
import numpy as np
from PIL import Image

import config_batch6 as C
import verify_batch6 as V

BAD = C.WORK_DIR / "badprobe6"
GOOD_DST = C.DST_DIR          # 探针 A 会临时改 C.DST_DIR，先存住正品目录


def arr(p):
    return np.array(Image.open(p).convert("RGBA")).astype(np.int32)


def paste(name, win, from_src=True):
    """把某个窗口还原成原图（抹掉该处中文）。"""
    p = BAD / (name + ".png")
    d = arr(p)
    s = arr(C.SRC_DIR / (name + ".png"))
    x0, y0, x1, y1 = win
    d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)


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
        V.C.DST_DIR = saved       # 关键：还原，否则探针 B 会从 原图/ 复制
    return list(V.FAIL)


def main():
    print("=" * 66)
    print("探针 A：整图坏稿（原图直接当成品）")
    print("=" * 66)
    fA = run(C.SRC_DIR)
    print("\n探针 A 失败项 %d 条：" % len(fA))
    for f in fA[:8]:
        print("   - " + f)
    assert len(fA) >= 15, "整图坏稿没被拦住"
    assert any("旧字墨迹已擦除" in f for f in fA), "没检出旧字未擦"
    assert any("每格有中文" in f for f in fA), "没检出中文缺失"
    print(">>> 探针 A 通过：坏稿被拦下\n")

    if BAD.exists():
        shutil.rmtree(BAD)
    BAD.mkdir(parents=True)
    for n in C.ALL_NAMES:
        shutil.copy2(GOOD_DST / (n + ".png"), BAD / (n + ".png"))

    # 三处定点破坏
    paste("panel", C.PANEL["labels"][1]["win"])          # BLOCK → 还原英文
    c = C.CONFIG_PARTS
    paste("config_parts", (c["mute_cols"][2] + 1, c["rows"][0],
                           c["mute_cols"][2] + 40, c["rows"][0] + 12))  # 暗 MUTE 一格
    paste("chart_parts", C.CHART_PARTS["erase_win"])     # 「目」放回来
    paste("config_parts", (420, 8, 423, 19))             # ALL 尾笔白点放回来

    print("=" * 66)
    print("探针 B：定点坏稿（panel 一格 / MUTE 一格 / 「目」/ ALL 尾笔）")
    print("=" * 66)
    fB = run(BAD)
    print("\n探针 B 失败项 %d 条：" % len(fB))
    for f in fB:
        print("   - " + f)
    want = ["panel 4 个纸片标签 每格有中文",
            "config_parts MUTE 12 格（亮 6 / 暗 6） 每格有中文",
            "chart_parts 「目」已清空",
            "config_parts ALL 尾笔白点已清除"]
    for w in want:
        assert any(w in f for f in fB), "漏检：" + w
    assert len(fB) <= 8, "误伤过多，说明判据不稳：%d 条" % len(fB)
    print(">>> 探针 B 通过：4 处破坏被精确点名，其余项未误伤")
    print("\n坏稿探针全部通过。")
    return 0


if __name__ == "__main__":
    main()
