# -*- coding: utf-8 -*-
"""
设置页面三张图的汉化生成器。

三张图按「字背后是什么」分成两条完全不同的工艺路线：

  A. 有底板（button / title）
     文字 mask（含描边膨胀）-> repair 用笔画之间的真实纹理补回 -> 居中重画中文
     ★ 最忌把笔画填成均匀色，那会留下字形负影（上一张图上翻过车）。
     ★ 也别把 mask 做成整块矩形：笔画之间的原始底板是最宝贵的纹理来源。

  B. 透明底 + 发光字（index）
     整行清空成透明 -> 按行重画「白字 + 下层描边 + 紧贴笔画的外发光」
     ★ 清除要整块均匀；辉光的低 alpha 必须压没，否则会糊成一片色板。
     ★ 发光层要用白字 alpha 挖空字核心，否则半透明细笔画会被染成光色。

三张图的中文都居中于「原英文词中心 / 格中心」——用户对这一组的明确要求。
（menu_button.png 那一组是右对齐，因为原图日文实测是严格右对齐；
  对齐方式要由原图量出来，不能凭习惯，详见《汉化方法与思路.md》第 3 节。）

运行：在 工具/ 目录执行 python build_pages.py
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config_pages as C
from repair import repair, patch_repair, backend_name


def log(*a):
    print(*a, flush=True)


def font(path, size):
    if path is None:
        raise RuntimeError("找不到中文字体，请改 config_pages.py 的字体候选路径")
    return ImageFont.truetype(path, size)


def baseline(font_obj, words, cy):
    """统一基线：用全部字符的 bbox 并集算一次，避免逐词 bbox 差异导致上下浮动。"""
    p = ImageDraw.Draw(Image.new("L", (8, 8), 0))
    bb = p.textbbox((0, 0), "".join(words), font=font_obj)
    return cy - (bb[1] + bb[3]) / 2.0


def draw_word(halo, core, word, f, cx, py, gap, fill, outline=None, outline_a=255):
    """
    逐字绘制（可控字距）。描边层与白色实字层分开渲染。

    绝不能用 PIL 的 stroke_width=1：宋体小字号笔画只有 1~2px，
    1px 描边会把白色实笔画吃掉，整字变成暗色空心字 —— 这里踩过一次。
    """
    ws = [core.textlength(ch, font=f) for ch in word]
    tw = sum(ws) + gap * (len(word) - 1)
    x = cx - tw / 2.0
    for ch, cw in zip(word, ws):
        if halo is not None and outline is not None:
            halo.text((x, py), ch, font=f, fill=outline + (outline_a,),
                      stroke_width=2, stroke_fill=outline + (outline_a,))
        core.text((x, py), ch, font=f, fill=fill)
        x += cw + gap
    return tw


def make_layers(size, words, f, centers, py, gap, styles, gain=1.45):
    """返回 (halo, core, core_alpha)；core 的 alpha 做加实，抗锯齿边缘变实。"""
    halo = Image.new("RGBA", size, (0, 0, 0, 0))
    core = Image.new("RGBA", size, (0, 0, 0, 0))
    hd, cd = ImageDraw.Draw(halo), ImageDraw.Draw(core)
    boxes = []
    for word, cx, st in zip(words, centers, styles):
        tw = draw_word(hd, cd, word, f, cx, py, gap,
                       st["text"] + (255,), st.get("outline"), st.get("outline_a", 0))
        boxes.append((cx - tw / 2.0, cx + tw / 2.0))
    ca = np.array(core.getchannel("A")).astype(np.float32)
    ca = np.clip(ca * gain, 0, 255).astype(np.uint8)
    core.putalpha(Image.fromarray(ca, "L"))
    return halo, core, ca.astype(np.float32) / 255.0, boxes


def dilate(mask, k=7):
    return np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.MaxFilter(k))) > 0


# ==================================================================== button
def build_button():
    src = Image.open(C.SRC_DIR / "button.png").convert("RGBA")
    assert src.size == C.BUTTON_SIZE, src.size
    arr = np.array(src).astype(np.uint8)
    f32 = arr.astype(np.float32)
    H, W = arr.shape[:2]
    f = font(C.SERIF, C.BUTTON_FONT_SIZE)
    log("button.png  字体", C.SERIF, "字号", C.BUTTON_FONT_SIZE)

    # ---- 1. 逐格自适应擦字：以「该格底板中位色」为基准找文字
    # 不能按行号假设颜色：本图第 3 行前 9 格是橙黄底深红字，
    # 第 10 格却是青绿底白字。写死阈值会让整格英文漏擦。
    mask = np.zeros((H, W), dtype=bool)
    cells = []                         # 每格擦字窗口，供同格纹理回填
    cell_look = {}                     # (行,格) -> (底色, 文字主色)
    ya_off, yb_off = C.BUTTON_TEXT_BAND
    for r, (y0, y1) in enumerate(C.BUTTON_ROWS):
        for ci, (a, b) in enumerate(C.BUTTON_WORD_SPANS):
            ya, yb = y0 + ya_off, y0 + yb_off
            xa, xb = max(0, a - C.BUTTON_CELL_PAD_X), min(W, b + C.BUTTON_CELL_PAD_X)
            q = f32[ya:yb, xa:xb, :3]
            base = np.median(q.reshape(-1, 3), axis=0)     # 底板占多数 → 中位数即底色
            diff = np.abs(q - base).sum(axis=2)
            m = diff > C.BUTTON_TEXT_DIFF
            # 文字主色取「差异最大的那部分」的中位，避开抗锯齿边缘与底板噪点
            color = None
            if m.any():
                hi = np.percentile(diff[m], 60)
                px = q[m & (diff >= hi)]
                if len(px):
                    color = tuple(int(v) for v in np.median(px, axis=0))
            cell_look[(r, ci)] = (tuple(int(v) for v in base), color)
            cells.append((xa, xb, ya, yb))
            mask[ya:yb, xa:xb] |= dilate(m, C.BUTTON_DILATE)
    # 实心做旧底板：用同格真实纹理回填，不用纯扩散（大片 mask 会补成偏暗矩形）
    clean = patch_repair(arr, mask, cells)
    log("  回填像素", int(mask.sum()), " 补底: 同格纹理回填")
    log("  逐格字色(第1行/第3行):",
        [cell_look[(0, i)][1] for i in range(len(C.BUTTON_WORDS))],
        [cell_look[(2, i)][1] for i in range(len(C.BUTTON_WORDS))])

    # ---- 2. 每行一个文字图层，居中于原英文词中心
    out = Image.fromarray(clean, "RGBA")
    for r, (y0, y1) in enumerate(C.BUTTON_ROWS):
        # 中文用「从该格原文字量出来的颜色」，同行的不同格可以完全不同。
        styles = []
        for ci in range(len(C.BUTTON_WORDS)):
            base, color = cell_look[(r, ci)]
            if color is None:
                styles.append(C.BUTTON_STYLE[r])
                continue
            if sum(color) / 3.0 > 170:                  # 浅字 → 底板压暗做描边
                outline = tuple(int(v * 0.30) for v in base)
                oa = 150
            else:                                       # 深字 → 底板提亮做描边
                outline = tuple(min(255, int(v * 0.90 + 40)) for v in base)
                oa = 110
            styles.append(dict(text=color, outline=outline, outline_a=oa))
        halo, core, ca, _ = make_layers(
            (W, H), C.BUTTON_WORDS, f, C.BUTTON_CENTERS,
            baseline(f, C.BUTTON_WORDS, y0 + C.BUTTON_CY[r]),
            C.BUTTON_CHAR_GAP, styles)
        txt = Image.alpha_composite(halo, core)
        out = Image.alpha_composite(out, txt)

    dst = C.DST_DIR / "button.png"
    out.save(dst)
    np.save(str(C.WORK_DIR / "button_mask.npy"), mask)
    log("  ->", dst)
    return out, mask


# ==================================================================== index
def build_index():
    src = Image.open(C.SRC_DIR / "index.png").convert("RGBA")
    assert src.size == C.INDEX_SIZE, src.size
    arr = np.array(src).astype(np.uint8)
    H, W = arr.shape[:2]
    f = font(C.SERIF, C.INDEX_FONT_SIZE)
    log("index.png   字体", C.SERIF, "字号", C.INDEX_FONT_SIZE)

    # ---- 1. 整行清空成透明（背景本来就透明，没有底板要保留）
    #         RGB 不动，只置 alpha=0 —— 透明区逐像素无变化，自检口径干净
    clean = arr.copy()
    for y0, y1 in C.INDEX_ROWS:
        clean[y0:y1, :, 3] = 0
    out = Image.fromarray(clean, "RGBA")

    # ---- 2. 每行重画：发光层在下，描边/白字在上
    for r, (y0, y1) in enumerate(C.INDEX_ROWS):
        st = C.INDEX_STYLE[r]
        centers = [(a + b) / 2.0 for a, b in C.INDEX_SPANS]
        words, styles = [], []
        for ci, w in enumerate(C.INDEX_WORDS):
            words.append(w)
            # 原英文是粗衬线白字 + 彩色外发光，没有深色描边。
            # 宋体细笔画一旦加 2px 深描边，整字会被染成描边色（踩过一次）。
            styles.append(dict(st, outline_a=0))
        halo, core, ca, boxes = make_layers(
            (W, H), words, f, centers,
            baseline(f, C.INDEX_WORDS, y0 + C.INDEX_CY[r]),
            C.INDEX_CHAR_GAP, styles)
        # 第 3 行第 6 格（RESET）原图为空：抹掉该格所有图层像素
        if C.INDEX_ROW2_EMPTY:
            ex0, ex1 = C.INDEX_SPANS[C.INDEX_ROW2_EMPTY[0]]
            for layer in (halo, core):
                ImageDraw.Draw(layer).rectangle([ex0 - 2, y0, ex1 + 2, y1], fill=(0, 0, 0, 0))
            ca[:, ex0 - 2:ex1 + 2] = 0
            boxes = [b for ci, b in enumerate(boxes) if ci not in C.INDEX_ROW2_EMPTY]

        txt = Image.alpha_composite(halo, core)

        # 不要给第 3 行加下划线！
        # 原图红态是「红色外发光整圈包住白字」，上下都有柔光、边缘模糊；
        # 早期版本把发光下沿误判成一条实心红线，额外画了 2px 红矩形，
        # 用户一眼看出不是原图的东西。红色氛围由下面的 glow 层负责即可。

        # 辉光：字形外扩(紧光) + 大半径柔光，再用白字 alpha 挖空字核心
        g = C.INDEX_GLOW
        ca_u8 = Image.fromarray((ca * 255).astype(np.uint8), "L")
        tight = np.array(ca_u8.filter(ImageFilter.MaxFilter(g["expand"]))
                         .filter(ImageFilter.GaussianBlur(g["tight_blur"]))).astype(np.float32) / 255.0
        soft = np.array(ca_u8.filter(ImageFilter.GaussianBlur(g["soft_blur"]))
                        ).astype(np.float32) / 255.0
        ga = (tight * g["tight_w"] + soft * g["soft_w"]) * 255.0 * st["gain"]
        ga *= (1.0 - ca * (1.0 - g["core_keep"]))   # ★ 外发光只在字外，别把白字染成光色

        # 词级柔光雾：原版彩色态是整片光雾包住白字（字上下 10px 外仍有光、
        # 横向填满字间空隙），单靠字形模糊够不到，先外扩字形再大半径模糊。
        # 不用「按词包围盒画矩形」——那会留下一块块圆角矩形光板。
        # menu_button 那类细字图不能这么做，会糊成色板；这里原图本来就长这样。
        hz = C.INDEX_HAZE
        if hz["alpha"] > 0:
            exp = ca_u8.filter(ImageFilter.MaxFilter(hz["expand"]))
            haze = np.array(exp.filter(ImageFilter.GaussianBlur(hz["blur"]))
                            ).astype(np.float32) / 255.0
            haze *= hz["alpha"] * (1.0 - ca * (1.0 - g["core_keep"]))
            ga = np.maximum(ga, haze)

        glow = Image.new("RGBA", (W, H), st["glow"] + (0,))
        glow.putalpha(Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8), "L"))
        layer = Image.alpha_composite(glow, txt)

        # 图层限制在本行内，不越界影响相邻状态
        la = np.array(layer.getchannel("A"))
        win = np.zeros((H, W), dtype=np.uint8)
        win[y0:y1, :] = 255
        layer.putalpha(Image.fromarray(np.minimum(la, win), "L"))
        out = Image.alpha_composite(out, layer)

    dst = C.DST_DIR / "index.png"
    out.save(dst)
    log("  ->", dst)
    return out


# ==================================================================== title
def build_title():
    src = Image.open(C.SRC_DIR / "title.png").convert("RGBA")
    assert src.size == C.TITLE_SIZE, src.size
    arr = np.array(src).astype(np.uint8)
    f32 = arr.astype(np.float32)
    H, W = arr.shape[:2]
    f = font(C.SERIF, C.TITLE_FONT_SIZE)
    log("title.png   字体", C.SERIF, "字号", C.TITLE_FONT_SIZE)

    # ---- 1. 深棕烙字 mask（限制在文字矩形内，避开木牌烧焦边框与红绳）
    m = ((f32[:, :, 0] < 138) & (f32[:, :, 1] < 108) &
         (f32[:, :, 2] < 92) & (f32[:, :, 3] > 175))
    box = np.zeros((H, W), dtype=bool)
    xa, xb, ya, yb = C.TITLE_TEXT_SPAN
    box[ya:yb, xa:xb] = True
    mask = dilate(m & box, 7) & dilate(box, 3)
    log("  回填像素", int(mask.sum()), " 补底:", backend_name())

    # ---- 2. 用笔画之间的真实木纹补回
    # 木牌的亮斑是水平渐变，同格纹理回填能保住它；扩散法会把字区补平。
    clean = patch_repair(arr, mask, [(xa, xb, ya, yb)])

    # ---- 3. 居中重画「设置」
    out = Image.fromarray(clean, "RGBA")
    st = dict(text=C.TITLE_TEXT_TINT, outline=C.TITLE_OUTLINE, outline_a=70)
    halo, core, ca, _ = make_layers(
        (W, H), [C.TITLE_WORD], f, [C.TITLE_CENTER[0]],
        baseline(f, [C.TITLE_WORD], C.TITLE_CENTER[1]), 4, [st], gain=1.25)
    txt = Image.alpha_composite(halo, core)
    out = Image.alpha_composite(out, txt)

    dst = C.DST_DIR / "title.png"
    out.save(dst)
    np.save(str(C.WORK_DIR / "title_mask.npy"), mask)
    log("  ->", dst)
    return out, mask


def main():
    C.WORK_DIR.mkdir(exist_ok=True)
    log("=" * 64)
    build_button()
    log("-" * 64)
    build_index()
    log("-" * 64)
    build_title()
    log("=" * 64)
    log("三张成品已写入:", C.DST_DIR)


if __name__ == "__main__":
    main()
