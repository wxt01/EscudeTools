# -*- coding: utf-8 -*-
"""
标题按钮汉化 v2 —— 彻底重画，不再「涂掉日文补底」。

原图真实结构（8 倍放大 + 逐像素剖面实测）：
  * 日文小字 = 细白字 + 深青描边 + 青色外发光，直接叠在透明背景上；
    「发光带」其实是文字自己的辉光，不是独立底板。
  * 禁用行 CONFIG/QUIT 两格完全透明（alpha=0），证明那里没有底板。
  * 英文大字下缘辉光在行内 rel 28..38 缓慢衰减，横贯整行。

v1 的错误：把日文笔画填成 alpha=234 的青色 —— 凭空造了一块亮牌。

v2 做法：
  1. 每格把小字连同辉光整块清除（边界推到辉光已衰减处 + 宽羽化），
     内部统一换成「该行该高度从非小字列实测的真实背景」。
     区域内完全均匀 → 既没有字形负影，也没有矩形轮廓。
  2. 按原图方式重新渲染中文：冷白细字 + 1px 深青描边 +
     只对紧贴笔画的一圈上青光（模糊 alpha 做幂次压缩，不铺成板）。
     四行字形/位置完全一致，只有亮度和辉光按状态变化。
  3. 英文大字主体（rel < BAND_TOP）一个像素都不碰。
  4. 中文按原图日文的右对齐方式定位（字形右外沿距格右线 2px），不用居中。

参数全部来自 config.py；换图先跑 inspect_sprite.py 重测几何。
运行：python build2.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import config as C
import layout

SRC, DELIVERY, WORK, DST, SAMPLE = C.SRC, C.DELIVERY, C.WORK, C.DST, C.SAMPLE
W, H, ROW_H, N_ROWS = C.W, C.H, C.ROW_H, C.N_ROWS
COLS, WORDS, ROW0_EMPTY = C.COLS, C.WORDS, C.ROW0_EMPTY
BAND_TOP, BAND_BOTTOM = C.BAND_TOP, C.BAND_BOTTOM

src = Image.open(SRC).convert("RGBA")
print("使用字体:", C.FONT_PATH)
assert src.size == (W, H), f"尺寸不符: {src.size} != {(W, H)}；请改 config.W/H"
arr = np.array(src).astype(np.float32)

# ---------------------------------------------------------------- 0. 统一布局
# 原图日文是严格右对齐的（字形外沿距格右线恒为 2px），中文必须跟着右对齐。
# 用居中会让字数少的「继续游戏」缩在格中间、字数相对多的「额外内容」右端越界。
font = ImageFont.truetype(C.FONT_PATH, C.FONT_SIZE)
starts = layout.word_starts(font)          # 每词绘制起点，四行共用
_probe = ImageDraw.Draw(Image.new("L", (8, 8), 0))
_bb = _probe.textbbox((0, 0), "".join(WORDS), font=font, stroke_width=1)
PY = C.TEXT_CY - (_bb[1] + _bb[3]) / 2.0
print("中文起点(右对齐):", [round(v, 1) for v in starts])

# ---------------------------------------------------------------- 1. 小字列范围
zone = np.zeros(W, dtype=bool)          # 有小字（含辉光余量）的 x
for x0, x1 in COLS:
    zone[max(0, x0 - C.CLEAR_PAD_X): min(W, x1 + 15)] = True
clean_x = np.where(~zone)[0]            # 只有大字辉光的「干净列」

# ---------------------------------------------------------------- 1. 旧字笔画 mask（仅用于诊断打印）
# 最终清除采用整格矩形，不依赖 mask；保留它是为了在控制台确认「图里确实有旧字」。
core = np.zeros((H, W), dtype=bool)
for r in range(N_ROWS):
    y0, y1 = r * ROW_H + 35, r * ROW_H + 55
    b = arr[y0:y1]
    core[y0:y1] |= ((b[:, :, 0] > 225) & (b[:, :, 1] > 225) &
                    (b[:, :, 2] > 225) & (b[:, :, 3] > 110))
core &= zone[None, :]
for r in range(N_ROWS):
    ok = np.ones(W, dtype=bool)
    if r == 0:
        for ci in ROW0_EMPTY:
            x0, x1 = COLS[ci]
            ok[max(0, x0 - C.CLEAR_PAD_X): min(W, x1 + 15)] = False
    core[r * ROW_H:(r + 1) * ROW_H] &= ok[None, :]
dil = np.array(Image.fromarray((core * 255).astype(np.uint8))
               .filter(ImageFilter.MaxFilter(7))) > 0
print("旧字笔画(含描边)像素:", int(dil.sum()))

# ---------------------------------------------------------------- 2. 按格整块清除
# 试过「按字形连续距离场清除」：距离场会顺着字形团块勾出暗矩形 + 日文负影，弃用。
# 整格矩形清除 + 只在边界羽化，内部 100% 换成真实背景，区域内完全均匀。
keep = np.ones((H, W), dtype=np.float32)      # 1 = 保留原图，0 = 换成背景
EDGE = C.EDGE
t = np.arange(EDGE, dtype=np.float32) / EDGE
for r in range(N_ROWS):
    for ci, (x0, x1) in enumerate(COLS):
        if r == 0 and ci in ROW0_EMPTY:
            continue
        # 清除区左界跟着中文实际左沿扩展：右对齐后部分格（如「额外内容」）
        # 中文比日文长，会往左伸出原清除区，不扩展就会压在没清干净的背景上。
        xa = max(0, min(x0 - C.CLEAR_PAD_X,
                        int(starts[ci]) - C.CLEAR_PAD_EXTRA))
        xb = min(W, x1 + 15)
        fx = np.ones(xb - xa, dtype=np.float32)
        fx[:EDGE] = np.minimum(fx[:EDGE], t)
        fx[-EDGE:] = np.minimum(fx[-EDGE:], t[::-1])
        n = BAND_BOTTOM - BAND_TOP
        fy = np.ones(n, dtype=np.float32)
        fy[:3] = (0.30, 0.65, 1.0)            # 上边界尽快全清，别让旧字上缘漏掉
        fy[-4:] = (1.0, 0.75, 0.40, 0.12)
        wgt = np.outer(fy, fx)
        sl = np.s_[r * ROW_H + BAND_TOP:r * ROW_H + BAND_BOTTOM, xa:xb]
        keep[sl] = np.minimum(keep[sl], 1.0 - wgt)

# ---------------------------------------------------------------- 3. 每行每高度的真实背景
# 取该行「非小字列」像素的中位数 RGBA —— 即只含英文大字下缘辉光的背景。
bg = np.zeros((N_ROWS, ROW_H, 4), dtype=np.float32)
for r in range(N_ROWS):
    for rel in range(BAND_TOP, min(BAND_BOTTOM + 1, ROW_H)):
        px = arr[r * ROW_H + rel][clean_x]
        bg[r, rel] = np.median(px, axis=0)
print("背景 alpha 剖面 (r=1, rel 33..60):",
      [int(bg[min(1, N_ROWS - 1), t, 3]) for t in range(33, min(BAND_BOTTOM, ROW_H - 1), 3)])

out = arr.copy()
for r in range(N_ROWS):
    for rel in range(BAND_TOP, min(BAND_BOTTOM, ROW_H)):
        y = r * ROW_H + rel
        kk = keep[y]
        b = bg[r, rel]
        out[y, :, :3] = kk[:, None] * arr[y, :, :3] + (1 - kk)[:, None] * b[:3]
        out[y, :, 3] = kk * arr[y, :, 3] + (1 - kk) * b[3]

base = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
# 无字底图单独存一份：三栏对照能一眼分清「清除没做好」还是「重画没调好」
base.save(os.path.join(WORK, "clean_base.png"))

# ---------------------------------------------------------------- 4. 重新绘制中文
# font / PY / starts 已在第 0 节统一算好：四行共用同一字形、同一基线、同一水平位置，
# 状态切换时文字不会有任何位移。基线用全部中文字符 bbox 并集算一次，
# 避免按「每个词各自 bbox」定位时，因 "谈" bottom=20 / "续" bottom=18
# 之类差异造成最多 0.5px 的格间浮动（看起来像某个字偏上）。

# 新图层作用范围：上下羽化，绝不碰英文大字主体。
# 这几个数是本次实测的羽化形状，换图时按诊断出的辉光衰减高度重新给。
win = np.zeros((ROW_H, W), dtype=np.uint8)
win[33:56, :] = 255
win[31, :] = 60
win[32, :] = 160
win[56, :] = 200
win[57, :] = 120
win[58, :] = 50
win_img = Image.fromarray(win, "L")

for r in range(N_ROWS):
    txt = Image.new("RGBA", (W, ROW_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    for ci, (x0, x1) in enumerate(COLS):
        if r == 0 and ci in ROW0_EMPTY:
            continue
        word = WORDS[ci]
        widths = [d.textlength(ch, font=font) for ch in word]
        x = starts[ci]                    # 右对齐：末尾与日文完全相同的缩进
        for ch, cw in zip(word, widths):
            d.text((x, PY), ch, font=font, fill=C.TEXT_TINT[r] + (255,),
                   stroke_width=1, stroke_fill=C.OUTLINE[r] + (C.OUTLINE_ALPHA,))
            x += cw + C.CHAR_GAP

    if C.TEXT_ALPHA[r] < 1.0:
        a = np.array(txt.getchannel("A")).astype(np.float32)
        txt.putalpha(Image.fromarray(np.round(a * C.TEXT_ALPHA[r]).astype(np.uint8), "L"))

    # 两层外发光：近距离亮、远距离淡。
    # 关键是 power>1 的幂次压缩：模糊后字间的低 alpha 被压没，
    # 只留紧贴笔画的一圈亮青光；线性叠加会把整片字间糊成暗青底板（试过，弃用）。
    layers = []
    for radius, ratio, power in C.GLOW_LAYERS:
        blur = txt.filter(ImageFilter.GaussianBlur(radius))
        ba = np.array(blur.getchannel("A")).astype(np.float32) / 255.0
        ga = np.power(ba, power) * 255.0 * C.GLOW_GAIN[r] * ratio
        g = np.zeros((ROW_H, W, 4), dtype=np.uint8)
        g[:, :, 0], g[:, :, 1], g[:, :, 2] = C.GLOW_RGB[r]
        g[:, :, 3] = np.clip(ga, 0, 255).astype(np.uint8)
        gi = Image.fromarray(g, "RGBA")
        gi.putalpha(Image.fromarray(np.minimum(np.array(gi.getchannel("A")), win), "L"))
        layers.append(gi)

    # 抗锯齿笔画加实：小字号下「谈」这类多笔画字的捺脚容易淡没，
    # 看起来上重下轻。只加实最终文字层 alpha，辉光已在上面算完，不受影响。
    a = np.array(txt.getchannel("A")).astype(np.float32)
    a = np.clip(a * C.TEXT_ALPHA_BOOST, 0, 255)
    txt.putalpha(Image.fromarray(np.minimum(a, win).astype(np.uint8), "L"))

    row_img = base.crop((0, r * ROW_H, W, (r + 1) * ROW_H))
    for g in layers:
        row_img = Image.alpha_composite(row_img, g)
    row_img = Image.alpha_composite(row_img, txt)
    base.paste(row_img, (0, r * ROW_H))

# ---------------------------------------------------------------- 5. 自检 + 输出
res = np.array(base)
src_u8 = np.array(src)
assert base.size == (W, H)
outside = np.ones((H, W), dtype=bool)
for r in range(N_ROWS):
    outside[r * ROW_H + BAND_TOP: r * ROW_H + BAND_BOTTOM, :] = False
print("小字带以外被改动像素:", int((res[outside] != src_u8[outside]).any(axis=1).sum()))
for r in range(N_ROWS):
    n = int((res[r * ROW_H + 33:r * ROW_H + 55] != src_u8[r * ROW_H + 33:r * ROW_H + 55]).any(axis=2).sum())
    print(f"第{r+1}行 小字带改动像素: {n}")

base.save(DST)
print("成品:", DST)

def on_dark(im):
    return Image.alpha_composite(Image.new("RGBA", im.size, C.BG_PREVIEW), im).convert("RGB")

s2 = on_dark(src).resize((W * 2, H * 2), Image.LANCZOS)
d2 = on_dark(base).resize((W * 2, H * 2), Image.LANCZOS)
canvas = Image.new("RGB", (W * 2, H * 4 + 18), C.BG_PREVIEW[:3])
canvas.paste(s2, (0, 0))
canvas.paste(d2, (0, H * 2 + 18))
ImageDraw.Draw(canvas).line([(0, H * 2 + 8), (W * 2, H * 2 + 8)], fill=(210, 70, 70), width=2)
canvas.save(SAMPLE)
print("样张:", SAMPLE)
