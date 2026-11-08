# -*- coding: utf-8 -*-
"""
坏稿探针：确认 verify_batch7.py 真能拦住「没汉化」。
探针 A：原图直接当成品 → 应大量 FAIL。
探针 B：只把行 0 的 LOAD 格还原成英文，其余保持正品 → 应精确点名、不误伤。
运行：python _badprobe7.py
"""
import shutil
import sys
from pathlib import Path
import numpy as np
from PIL import Image

import config_batch7 as C
import verify_batch7 as V

BAD = C.WORK_DIR / "badprobe7"
GOOD_DST = C.DST_DIR
NAME = C.FILE_PARTS["name"]


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
    print("=" * 62)
    print("探针 A：整图坏稿（原图直接当成品）")
    print("=" * 62)
    fA = run(C.SRC_DIR)
    print("\n探针 A 失败项 %d 条：" % len(fA))
    for f in fA[:8]:
        print("   - " + f)
    # 原图当成品时，尺寸/配色/装饰/结构口径本来就都该通过，
    # 真正该红的是「未汉化」这几条，5 条足够拦下，不必要求满屏 FAIL。
    assert len(fA) >= 4, "整图坏稿没被拦住"
    assert any("中文" in x or "擦除" in x or "白字" in x for x in fA), "没检出未汉化"
    print(">>> 探针 A 通过：坏稿被拦下\n")

    if BAD.exists():
        shutil.rmtree(BAD)
    BAD.mkdir(parents=True)
    shutil.copy2(GOOD_DST / (NAME + ".png"), BAD / (NAME + ".png"))
    p = BAD / (NAME + ".png")
    d = arr(p)
    s = arr(C.SRC_DIR / (NAME + ".png"))
    # 行 0 的 LOAD 格（含光晕）还原成原图英文
    x0, y0, x1, y1 = 246, 768, 325, 801
    d[y0:y1, x0:x1] = s[y0:y1, x0:x1]
    Image.fromarray(d.astype(np.uint8), "RGBA").save(p)

    print("=" * 62)
    print("探针 B：定点坏稿（只把行 0 的 LOAD 还原成英文）")
    print("=" * 62)
    fB = run(BAD)
    print("\n探针 B 失败项 %d 条：" % len(fB))
    for f in fB:
        print("   - " + f)
    want = ["6 格每格有中文", "6 格白字 bbox 是中文 2 字", "6 格每格确实重画过"]
    for w in want:
        assert any(w in f for f in fB), "漏检：" + w
    assert len(fB) <= 8, "误伤过多：%d 条" % len(fB)
    print(">>> 探针 B 通过：单点破坏被精确点名，其余项未误伤")
    print("\n坏稿探针全部通过。")
    return 0


if __name__ == "__main__":
    main()
