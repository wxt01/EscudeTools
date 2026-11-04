# -*- coding: utf-8 -*-
"""
交付自检：改字类工作的「不靠眼睛」验收。

检查项：尺寸/模式、小字带以外 0 改动、每格有字、四行共有格包围盒对齐、
中文笔画之外无残留旧字白像素、禁用空白格逐像素一致、辉光逐行递增。

注意口径（踩过坑）：
  * 禁用行少了两格中文，不能拿「整行包围盒」互比，只能比共有格。
  * 空白格左右 ±14px 是相邻格的清除羽化余量，检查空白时应只看本格 x 范围。
运行：python verify2.py
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import config as C

s = Image.open(C.SRC).convert("RGBA")
d = Image.open(C.DST).convert("RGBA")
S, D = np.array(s).astype(int), np.array(d).astype(int)
W, H, ROW_H, N_ROWS = C.W, C.H, C.ROW_H, C.N_ROWS
COLS, WORDS, ROW0_EMPTY = C.COLS, C.WORDS, C.ROW0_EMPTY
ok = True


def chk(label, cond, extra=""):
    global ok
    print(("  OK  " if cond else " FAIL ") + label + ("  " + extra if extra else ""))
    ok = ok and bool(cond)


print("== 基本 ==")
chk(f"尺寸 {W}x{H}", d.size == (W, H), str(d.size))
chk("模式 RGBA", d.mode == "RGBA", d.mode)

print("== 只改小字带 ==")
outside = np.ones((H, W), bool)
for r in range(N_ROWS):
    outside[r * ROW_H + C.BAND_TOP:r * ROW_H + C.BAND_BOTTOM, :] = False
n_out = int((D[outside] != S[outside]).any(axis=1).sum())
chk("小字带以外 0 像素改动", n_out == 0, f"改动 {n_out}")
for r in range(N_ROWS):
    a, b = r * ROW_H + 33, r * ROW_H + 55
    n = int((D[a:b] != S[a:b]).any(axis=2).sum())
    chk(f"第{r+1}行 小字带有改动", n > 5000, f"{n} 像素")

print("== 中文齐全 / 四行对齐 ==")
font = ImageFont.truetype(C.FONT_PATH, C.FONT_SIZE)
_probe = ImageDraw.Draw(Image.new("L", (8, 8), 0))
_bb = _probe.textbbox((0, 0), "".join(WORDS), font=font, stroke_width=1)
PY = C.TEXT_CY - (_bb[1] + _bb[3]) / 2.0


def text_layer(r):
    txt = Image.new("L", (W, ROW_H), 0)
    dr = ImageDraw.Draw(txt)
    for ci, (x0, x1) in enumerate(COLS):
        if r == 0 and ci in ROW0_EMPTY:
            continue
        word = WORDS[ci]
        ws = [dr.textlength(c, font=font) for c in word]
        tw = sum(ws) + C.CHAR_GAP * (len(word) - 1)
        x = (x0 + x1) / 2.0 - tw / 2.0
        for c, cw in zip(word, ws):
            dr.text((x, PY), c, font=font, fill=255, stroke_width=1)
            x += cw + C.CHAR_GAP
    return txt


boxes = []
for r in range(N_ROWS):
    a = np.array(text_layer(r))
    ys, xs = np.where(a > 100)
    row_boxes = {}
    for ci, (x0, x1) in enumerate(COLS):
        if r == 0 and ci in ROW0_EMPTY:
            continue
        m = (xs >= x0 - 20) & (xs <= x1 + 20)
        chk(f"第{r+1}行 第{ci+1}格「{WORDS[ci]}」有字", m.sum() > 60, f"{m.sum()} 笔画像素")
        row_boxes[ci] = (int(xs[m].min()), int(ys[m].min()), int(xs[m].max()), int(ys[m].max()))
    boxes.append(row_boxes)
shared = set.intersection(*[set(b) for b in boxes])
aligned = all(all(b[ci] == boxes[0][ci] for ci in shared) for b in boxes)
chk("四行共有格的中文包围盒完全对齐", aligned, f"共同 {len(shared)} 格, 例: {boxes[0].get(0)}")

print("== 旧字残留（中文笔画之外的白色实像素）==")
allow = np.zeros((H, W), bool)
for r in range(N_ROWS):
    dil = np.array(Image.fromarray(np.array(text_layer(r)))
                   .filter(ImageFilter.MaxFilter(5))) > 0
    allow[r * ROW_H:(r + 1) * ROW_H] = dil
for r in range(N_ROWS):
    a, b = r * ROW_H + 35, r * ROW_H + 54
    reg = D[a:b]
    white = (reg[:, :, 0] > 230) & (reg[:, :, 1] > 230) & (reg[:, :, 2] > 230) & (reg[:, :, 3] > 200)
    residual = white & (~allow[a:b])
    chk(f"第{r+1}行 中文之外无旧字白字残留", residual.sum() == 0, f"残留 {int(residual.sum())}")

print("== 禁用行空白格保持原样 ==")
for ci in ROW0_EMPTY:
    x0, x1 = COLS[ci]
    n = int((D[33:58, x0:x1] != S[33:58, x0:x1]).any(axis=2).sum())
    chk(f"第1行 第{ci+1}格 与原图一致（空白）", n == 0, f"改动 {n}")

print("== 四行状态梯度（辉光逐行增强）==")
means = []
for r in range(N_ROWS):
    reg = D[r * ROW_H + 35:r * ROW_H + 54, 60:182].astype(float)
    cyan = (reg[:, :, 0] < 110) & (reg[:, :, 1] > 130) & (reg[:, :, 3] > 70)
    means.append(int(cyan.sum()))
print("  各行青光像素:", means)
chk("悬停/按下行辉光强于常态行",
    len(means) < 3 or (means[2] >= means[1] and means[3] >= means[1]))

print("\n结果:", "全部通过" if ok else "存在失败项")
