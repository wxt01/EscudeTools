# -*- coding: utf-8 -*-
"""
设置页面三张图的全部参数。换图时优先改这里。

所有几何量都是从 `原图/` 实测出来的，不是猜的：
  - button.png : 3 行 × 10 列，实心做旧底板，每格中心 = 原英文词中心
  - index.png  : 3 行 × 6 列，文字悬在透明背景上带外发光；第 3 行第 6 格原本是空的
  - title.png  : 单张木牌，深棕衬线字压在亮黄斑驳纹理上

本组图与 menu_button.png 的关键差异：
  menu_button 的小字背后是**透明**的（没有底板），所以可以「整块清除成透明」；
  这三张里 button / title 的字背后是**真实纹理**，必须补回纹理，不能填纯色；
  index 才是和 menu_button 同类的「透明底 + 发光字」。
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC_DIR = ROOT / "原图"
DST_DIR = ROOT / "交付成品放这里"
WORK_DIR = HERE / "_输出"
WORK_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------- 字体
# 原英文都是衬线体（Times / 类似雕版），中文选宋体系比黑体更贴。
# 跨平台按候选顺序找，找到哪个用哪个；找不到会退回 PIL 默认（此时应手动装字体）。
SERIF_CANDIDATES = [
    r"C:\Windows\Fonts\STSONG.TTF",        # 华文宋体：衬线明显、笔画秀气
    r"C:\Windows\Fonts\simsun.ttc",        # 中易宋体
    r"C:\Windows\Fonts\SimsunExtG.ttf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]
SANS_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def pick_font(candidates):
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


SERIF = pick_font(SERIF_CANDIDATES)
SANS = pick_font(SANS_CANDIDATES)

# ---------------------------------------------------------------- button.png
BUTTON_SIZE = (1523, 126)
BUTTON_ROWS = [(0, 42), (42, 84), (84, 126)]
# 每格参考窗口（按钮底板内部，避开格间的黑色竖缝）
BUTTON_SPANS = [
    (11, 132), (156, 279), (303, 426), (450, 573), (597, 720),
    (744, 867), (891, 1014), (1038, 1161), (1185, 1308), (1351, 1509),
]
# 原英文词的中心（r0/r1 白字包围盒实测），中文居中于此 = 视觉位置不变
BUTTON_CENTERS = [72, 220.5, 366.5, 514, 660.5, 807, 955, 1101.5, 1248.5, 1422.5]
BUTTON_WORDS = ["关", "开", "普通", "快速", "窗口", "全屏", "保持", "返回", "取消", "应用"]
# 原英文词包围盒（r0/r1 白字实测），用于限定清除窗口
BUTTON_WORD_SPANS = [(50, 94), (205, 236), (315, 418), (485, 543), (637, 684),
                     (776, 838), (923, 987), (1071, 1132), (1202, 1295), (1369, 1476)]
BUTTON_FONT_SIZE = 21
BUTTON_CHAR_GAP = 2
BUTTON_CY = [21, 21, 21]           # 行内相对 y（代码里会加行起点）
# ★ 不要按行号假设文字颜色。本图第三行前 9 格是橙黄底+深红字，
#   但第 10 格（SETTING / 应用）仍是青绿底+白字 —— 早期写死「第三行=深红字」，
#   那一格的白英文一个像素都没被识别，直接叠了中文（用户当场指出）。
#   现在 build_pages.py 逐格量底板色和文字主色；下面这组只作为量不到时的兜底。
BUTTON_STYLE = [
    dict(text=(247, 252, 250), outline=(8, 45, 50), outline_a=150),
    dict(text=(247, 252, 250), outline=(8, 52, 48), outline_a=150),
    dict(text=(154, 24, 18), outline=(255, 232, 190), outline_a=110),
]
# 逐格自适应擦字参数
BUTTON_TEXT_DIFF = 150      # 与该格底板中位色的 RGB 绝对差之和，超过判为文字
BUTTON_TEXT_BAND = (7, 34)  # 行内相对 y：只取文字带，避开按钮圆角外的黑背景
BUTTON_CELL_PAD_X = 9       # 词框左右外扩，抓描边/投影
BUTTON_DILATE = 7           # 膨胀尺寸，覆盖抗锯齿与描边边缘

# ---------------------------------------------------------------- index.png
INDEX_SIZE = (731, 144)
INDEX_ROWS = [(0, 48), (48, 96), (96, 144)]
INDEX_SPANS = [(10, 83), (101, 207), (223, 319), (334, 480), (497, 628), (638, 728)]
INDEX_WORDS = ["文本", "系统", "声音", "角色", "快捷键", "重置"]
INDEX_FONT_SIZE = 24
INDEX_CHAR_GAP = 2
INDEX_CY = [24, 24, 24]            # 行内相对 y（代码里会加行起点）
INDEX_ROW2_EMPTY = [5]             # 第 3 行 RESET 原图为空，保持透明
# 每行：字色 / 描边 / 发光色 / 发光强度
# 辉光色是从原图「alpha 40..200」的半透明像素里量出来的众数，不是挑的。
# 第三行（选中/红态）没有下划线：原版是红色外发光整圈包住白字，
# 上下都有柔光。别再按「红条」去补一条实心线。
INDEX_STYLE = [
    dict(text=(240, 250, 252), outline=(16, 78, 108), glow=(6, 122, 140),
         gain=0.80),
    dict(text=(244, 253, 252), outline=(12, 88, 84), glow=(10, 222, 202),
         gain=0.86),
    dict(text=(255, 248, 242), outline=(165, 18, 10), glow=(245, 28, 12),
         gain=0.92),
]
# 外发光 = 字形外扩(紧光) + 大半径柔光。
# 只做高斯模糊不够：字外 1px 的 alpha 只有个位数，肉眼看等于没发光。
# 但外扩也不能大：汉字笔画密，外扩 3px 会把字间空隙填满、糊成一块色板。
INDEX_GLOW = dict(expand=5,          # MaxFilter 尺寸，字形外扩 ~2px
                  tight_blur=1.8, tight_w=0.52,
                  soft_blur=6.0, soft_w=0.26,
                  core_keep=0.02)    # 字核心保留多少辉光（挖空，防止白字被染色）

# 词级柔光雾：index.png 的彩色态和 menu_button 不同，原版是「整片光雾」
# 包住白字——实测字上下 10px 外 alpha 仍有 15~50，且横向填满字间空隙。
# 只做字形模糊够不到那么远，所以先把字形外扩再大半径模糊。
# ★ 别用「按词包围盒画矩形再模糊」：那样每个词后面会看出一块圆角矩形光板，
#   就是用户批评过的色板感。字形外扩的边缘跟随字形起伏，才和原版一致。
# 注意别把这层照搬到细字透明雪碧图上。alpha=0 可整体关掉。
INDEX_HAZE = dict(alpha=135, expand=11, blur=6.0)

# ---------------------------------------------------------------- title.png
TITLE_SIZE = (411, 97)
TITLE_WORD = "环境设置"          # 任务说明.md 用户定稿（四字，与木牌宽度匹配）
TITLE_FONT_SIZE = 34
TITLE_CENTER = (162, 41)            # 原 CONFIG 字形包围盒中心
TITLE_TEXT_TINT = (56, 31, 23)      # 烙印深棕
TITLE_OUTLINE = (120, 78, 48)       # 极淡的暖描边，模拟墨迹渗开
TITLE_REF_SPAN = (48, 288, 8, 80)  # 木牌内部（纹理采样窗口）
TITLE_TEXT_SPAN = (62, 262, 14, 68)  # 文字可能落到的范围（mask 搜索窗）

# ---------------------------------------------------------------- 验收口径
# 「非文字区 0 改动」的窗口：每行内允许改动的小字带
BUTTON_BAND = (6, 37)               # 行内 y 相对范围
INDEX_BAND = (2, 46)
