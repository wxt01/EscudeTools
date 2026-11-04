# -*- coding: utf-8 -*-
"""
本任务的全部「需要按图重测」的参数，集中在这里。

换一张雪碧图时，先用 inspect_sprite.py 量出下面的几何量，再改这里，
build2.py / verify2.py / compare.py 不用动。

⚠️ 这些数值是本次对 1092x244 这张图的**实测结果**，不是通用常数。
   尤其 ROW_H / COLS / BAND / ROW0_EMPTY / TEXT_CY，换图必须重新量。
   颜色与强度（发光、字重）也需要对着原图小字重新取样，别直接照抄。
"""
import os

# ---------------------------------------------------------------- 路径（相对本文件夹，可整体拷走）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # 「标题按钮汉化」根目录
SRC = os.path.join(ROOT, "原图", "menu_button.png")
DELIVERY = os.path.join(ROOT, "交付成品放这里")
WORK = os.path.join(HERE, "_输出")
DST = os.path.join(DELIVERY, "menu_button.png")
SAMPLE = os.path.join(DELIVERY, "对比样张.png")
os.makedirs(WORK, exist_ok=True)
os.makedirs(DELIVERY, exist_ok=True)

# ---------------------------------------------------------------- 几何
W, H, ROW_H = 1092, 244, 61    # 图宽、图高、单个状态行的高度（H / 状态数）
N_ROWS = 4                     # 状态数：0 禁用 / 1 常态 / 2 悬停 / 3 按下
COLS = [(65, 176), (345, 415), (549, 619), (657, 721),
        (774, 859), (936, 985), (1004, 1084)]
# 每格小字的 x 包围盒，可略宽于真实字形；用 inspect_sprite.py 的列投影找连续段
BAND_TOP, BAND_BOTTOM = 31, 60  # 行内小字带 y 范围（相对行首），大字主体在 BAND_TOP 以上
TEXT_CY = 43.5                 # 中文视觉中心的 y（相对行首），约等于原小字带中心
ROW0_EMPTY = {4, 6}            # 禁用行里原本就没有小字的格（CONFIG / QUIT）
CLEAR_PAD_X = 14               # 清除区左右外扩：推到离文字足够远、辉光已衰减的位置
EDGE = 9                       # 清除区左右羽化宽度

# ---------------------------------------------------------------- 文案与字体
WORDS = ["继续游戏", "额外剧情", "后日谈", "读取存档",
         "更改设置", "额外内容", "退出游戏"]

def find_font():
    """优先微软雅黑 Bold（小字号下笔画实、白字面积接近原图日文）。
    换平台时按候选顺序回退；如果回退到别的字体，字号/字距/发光都要重新调。"""
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise RuntimeError("找不到中文字体，请在 config.find_font() 里补上本机字体路径")

FONT_PATH = find_font()
FONT_SIZE = 15                 # 视觉重量对齐原图日文小字；再小复杂字（谈/戏）会发虚
CHAR_GAP = 3                   # 字间距：拉开笔画密度，字间能透出黑底，避免光晕糊成片

# ---------------------------------------------------------------- 四行状态样式
# 每行：文字色 / 描边色 / 发光色 / 发光强度 / 文字整体不透明度
TEXT_TINT = {0: (195, 208, 208), 1: (248, 254, 254),
             2: (250, 255, 255), 3: (252, 255, 255)}
OUTLINE = {0: (0, 62, 62), 1: (0, 69, 68),
           2: (10, 130, 124), 3: (18, 165, 155)}
GLOW_RGB = {0: (5, 186, 183), 1: (0, 252, 255),
            2: (24, 241, 207), 3: (44, 244, 224)}
GLOW_GAIN = {0: 0.30, 1: 1.00, 2: 1.35, 3: 1.70}
TEXT_ALPHA = {0: 0.55, 1: 1.0, 2: 1.0, 3: 1.0}

# 外发光层：(高斯半径, 强度比, alpha 幂次)
# 幂次 >1 是关键：把模糊后字间的低 alpha 压没，只留紧贴笔画的一圈光。
GLOW_LAYERS = ((1.2, 1.00, 1.0), (2.6, 0.25, 2.2))
TEXT_ALPHA_BOOST = 1.35        # 文字层最终加实，补救小字号抗锯齿发虚
OUTLINE_ALPHA = 90             # 描边太重会压暗细笔画
BG_PREVIEW = (18, 22, 26, 255) # 对照图用的深色底，贴近游戏实际显示
