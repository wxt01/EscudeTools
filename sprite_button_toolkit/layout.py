# -*- coding: utf-8 -*-
"""
统一布局：所有中文按「右对齐到原图日文末尾」计算绘制起点。

为什么不用 textlength 直接算：
  逐字绘制带 CHAR_GAP 和 1px 描边时，理论宽度与实际像素外沿会差 1~2px，
  七个格各自差一点，末尾就对不齐。所以先渲染探针图层量真实外沿，再平移。

build2.py 与 verify2.py 都调用这里的 word_starts()，保证「生成」和「自检」
用的是同一套坐标，不会出现自检拿旧位置去查残留而误报。
"""
import numpy as np
from PIL import Image, ImageDraw
import config as C


def word_starts(font):
    """返回每个词的绘制起点 x（四行共用，状态切换不位移）。

    以 x=0 逐字渲染一个只含 alpha 的探针图层，量出字形（含 1px 描边）的
    真实右边界 right，再平移到目标 COLS[ci][1] - RIGHT_INSET。
    """
    starts = []
    for ci, word in enumerate(C.WORDS):
        probe = Image.new("L", (max(C.W, 512), 80), 0)
        d = ImageDraw.Draw(probe)
        x = 0.0
        for ch in word:
            d.text((x, 20), ch, font=font, fill=255,
                   stroke_width=1, stroke_fill=C.OUTLINE_ALPHA)
            x += d.textlength(ch, font=font) + C.CHAR_GAP
        a = np.array(probe)
        cols = np.where((a > C.ALIGN_ALPHA_THRESHOLD).any(axis=0))[0]
        right = int(cols.max())
        target = C.COLS[ci][1] - C.RIGHT_INSET
        starts.append(float(target - right))
    return starts


if __name__ == "__main__":
    from PIL import ImageFont
    f = ImageFont.truetype(C.FONT_PATH, C.FONT_SIZE)
    ss = word_starts(f)
    print("目标右边界 = COLS右线 -", C.RIGHT_INSET)
    for ci, (s, (x0, x1), w) in enumerate(zip(ss, C.COLS, C.WORDS)):
        print(f"  格{ci} {w:6s}: 起点 {s:7.1f}  预计左沿 {s-2:7.1f}  "
              f"目标右沿 {x1-C.RIGHT_INSET:5d}  格范围 {x0}..{x1}")
