# -*- coding: utf-8 -*-
"""
追加任务四（存/读档页 + EXTRA 界面，13 张）的全部几何与配色参数。

所有坐标都从 原图/ 实测，不是估算；换图必须重新量。
本批同时存在 6 种「字背后是什么」的模型，按 kind 分派：

  board       木牌烙字（4 张 411×97）      实心做旧木纹 → 同组差分 mask + 同格纹理回填
  rate        鉴赏率牌金字（3 张 242×99）  深棕木牌    → 黄色判据 mask + 同格纹理回填
  button      青色按钮白字（stand_back）    实心青底    → 白色判据 mask + 同格纹理回填
  brush       笔刷条白字（stand_parts）     实心青笔刷  → 白色判据 mask + 同格纹理回填
  glow_grid   透明辉光网格（extra_mode）    透明底      → 整格清 alpha=0 + 按格配色重画
  glow_label  透明辉光标签（3 张部件图）    透明底      → 标签窗清 alpha=0 + 重画

硬约束（任务说明）：尺寸/状态行数不变、每格文字落在自己的源矩形内、
左对齐到原英文墨迹左沿（不按格居中）、图标数字与装饰全部保留。

★ 第 5 节 stand_parts 例外：用户看完成品后明确要求「都居中」，
  已改为 cx=555（原英文墨迹中心实测 554.5~555），逐行居中。
  「左对齐、勿居中」是通用默认，不是铁律，永远以用户当期口述为准。

★ 状态颜色绝不按行号假设：extra_mode 第 3 行前 5 格是红字红光，
  唯独第 4 格 STAND 仍是白字青光 —— 与上一批 button.png 第 10 格同一个坑。
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC_DIR = ROOT / "原图"
DST_DIR = ROOT / "交付成品放这里"
WORK_DIR = HERE / "_输出"
WORK_DIR.mkdir(exist_ok=True)
DST_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------- 字体
# 本批原英文全是衬线体（Times / 雕版风），中文选华文宋体最贴；
# 粗黑体 msyhbd 一律别用（上一批 popup_parts 已被用户批评过）。
SERIF_CANDIDATES = [
    r"C:\Windows\Fonts\STSONG.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
]
SERIF = next((p for p in SERIF_CANDIDATES if os.path.exists(p)), None)

# ---------------------------------------------------------------- 通用
# 白色字层的 alpha 加实：宋体小字号细横发灰，抗锯齿边缘要压实
ALPHA_BOOST = 1.30
# 擦字 mask 的膨胀量按模型分别写在 build 里：亮木牌 5、其余 3。
# 统一给大膨胀会让细笔画连成一整块，补底后必定出现矩形补丁（见 3.5）。

# ---------------------------------------------------------------- 1 四块木牌
# 同组两张图的底板逐像素相同（差分只落在字区），所以用「两字形并集」
# 作为擦字 mask —— 比亮度阈值可靠：木牌本身的烧焦暗斑不会被误判成字。
# center = 原英文墨迹 bbox 中心（同组差分实测）：
#   SAVE/LOAD  (66,22)-(187,59) → (126.5, 40.5)
#   EXTRA/VOICE(87,19)-(243,58) → (165.0, 38.5)
TITLES = [
    dict(name="save_title",  word="存档",     pair="load_title",
         win=(58, 14, 198, 67), center=(126.5, 40.5)),
    dict(name="load_title",  word="读档",     pair="save_title",
         win=(58, 14, 198, 67), center=(126.5, 40.5)),
    dict(name="extra_title", word="额外内容", pair="voice_title",
         win=(80, 13, 250, 65), center=(165.0, 38.5)),
    dict(name="voice_title", word="语音鉴赏", pair="extra_title",
         win=(80, 13, 250, 65), center=(165.0, 38.5)),
]
TITLE_STYLE = dict(font_size=36, gap=5,
                   fill=(56, 31, 23),        # 烙印深棕（title.png 环境设置同款）
                   outline=(120, 78, 48), outline_a=70,
                   boost=ALPHA_BOOST)

# ---------------------------------------------------------------- 2 三张鉴赏率牌
# 金字墨迹实测：MUSIC (28,46)-(99,59) / SCENE (27,46)-(99,59) /
#               GALLERY (13,45)-(113,59)。% 在 x175~227、数字在 y79~98，全保留。
RATES = [
    dict(name="music_rate",  word="音乐", left=28, win=(5, 38, 170, 66)),
    dict(name="scene_rate",  word="场景", left=27, win=(5, 38, 170, 66)),
    dict(name="visual_rate", word="画廊", left=13, win=(5, 38, 170, 66)),
]
RATE_STYLE = dict(font_size=18, gap=2, baseline_y=59.5,
                  fill=(248, 198, 62),      # 金字实测 (245,195,59) 提一档
                  outline=(58, 24, 8), outline_a=110,
                  boost=1.35)
RATE_KEEP = [(170, 30, 242, 99)]           # % 与数字行，禁止改动

# ---------------------------------------------------------------- 3 stand_back
# 3 行状态，青色按钮不透明；白字实测 (25,12)-(82,25) / (25,50)-(82,63) /
# (25,85)-(82,101)。左右箭头装饰在 x<12 与 x>95，必须保留。
STAND_BACK = dict(
    name="stand_back", size=(110, 114), word="返回",
    rows=[(0, 38), (38, 76), (76, 114)],
    win_x=(8, 102), center_x=53.5,
    style=dict(font_size=20, gap=2, fill=(255, 255, 255),
               outline=(6, 92, 96), outline_a=80, boost=1.30),
)

# ---------------------------------------------------------------- 4 extra_mode
# 6 按钮 × 3 行状态；每行 48px。格右界 = 下一格起点（红线），
# 原英文右沿实测 122/232/334/441/544/651，全部落在各自格内。
EXTRA_MODE = dict(
    name="extra_mode", size=(667, 144),
    rows=[(0, 48), (48, 96), (96, 144)],
    cols=[(0, 138), (138, 248), (248, 350), (350, 451), (451, 560), (560, 667)],
    words=["画廊", "场景", "语音", "立绘", "音乐", "制作"],
    lefts=[15, 153, 262, 359, 465, 575],     # 原英文墨迹左沿
    cy=[23.5, 71.5, 119.5],                  # 原字墨迹中心 y
    font_size=21, gap=3,
    # 逐行主色；第 3 行第 4 格（STAND / 立绘）例外，仍是白字青光
    row_styles=[
        dict(fill=(255, 255, 255), glow=(6, 120, 140),  glow_gain=0.85),
        dict(fill=(252, 255, 254), glow=(8, 221, 203),  glow_gain=0.95),
        dict(fill=(244, 58, 18),   glow=(255, 15, 15),  glow_gain=1.00),
    ],
    exceptions={
        (2, 3): dict(fill=(255, 255, 255), glow=(78, 255, 240), glow_gain=0.95),
    },
    boost=ALPHA_BOOST,
)

# ---------------------------------------------------------------- 5 stand_parts
# CHARA RESET ×3 + ALL RESET ×3，六行都压在青色笔刷条上（不透明）。
# 白字实测左沿：CHARA 486 / ALL 501；行 2、5 量到的 481 是笔刷条边缘白点，
# 不是字，别拿它当左沿。
STAND_PARTS = dict(
    name="stand_parts", size=(710, 336),
    rows=[(128, 158), (158, 188), (188, 218),
          (218, 248), (248, 278), (278, 308)],
    words=["重置角色"] * 3 + ["全部重置"] * 3,
    # 原英文墨迹左沿，仅作测量记录：CHARA 486 / ALL 501。
    # 第 5 批用户改口要求逐行居中，落位改用 center_x，不再用 lefts。
    lefts=[486, 486, 486, 501, 501, 501],
    center_x=555.0,                 # 原英文墨迹中心 554.5 / 555.0，六行一致
    win_x=(470, 645),
    style=dict(font_size=20, gap=2, fill=(250, 253, 252),
               outline=(4, 78, 82), outline_a=90, boost=1.28),
)

# 5b 红色圆形徽标上的两个白底小框（原「Front ▼」在任务说明里写"保留不动"，
# 用户第 5 批改口要求汉化）。实测白框边界与文字墨迹：
#   Back  白框 (667,149)-(697,161)，字墨迹 ~(669,151)-(695,159)，深红
#   Front 白框 (651,163)-(681,175)，字墨迹 ~(653,165)-(679,173)，深红
# 上箭头 (651~663,148~163)、下箭头 (684~697,165~176) 必须逐像素保留。
BADGE_LABELS = [
    dict(word="回去", box=(667, 149, 697, 161)),   # Back
    dict(word="向前", box=(651, 163, 681, 175)),   # Front
]
BADGE_STYLE = dict(font_size=9, gap=0, fill=(96, 18, 30), boost=1.35)
BADGE_PALE = (246, 240, 240)      # 白框实测底色 (247,241,241) 取中值

# ---------------------------------------------------------------- 6 透明辉光标签
# 三张部件图的标签都是「透明底 + 白衬线字 + 青色外发光」。
# 清除窗口只包住字与辉光，不碰下方的青色笔刷横线 / 斜杠 / 数字 / 图标。
GLOW_LABELS = [
    dict(
        name="music_parts", size=(586, 646), font_size=21, gap=3,
        glow=(10, 170, 185), glow_gain=0.80,
        labels=[
            dict(word="操作",     left=123, win=(112, 58, 256, 87),  cy=72.5),
            dict(word="音量",     left=94,  win=(84, 103, 212, 131), cy=117.5),
            dict(word="音乐列表", left=185, win=(176, 148, 348, 177), cy=162.5),
        ],
    ),
    dict(
        name="voice_parts", size=(1135, 476), font_size=21, gap=3,
        glow=(10, 170, 185), glow_gain=0.55,
        labels=[
            dict(word="收藏语音", left=28,  win=(20, 359, 224, 386),  cy=371.5),
            dict(word="播放列表", left=461, win=(453, 359, 584, 386), cy=371.5),
        ],
    ),
    dict(
        name="visual_parts", size=(1280, 141), font_size=21, gap=3,
        glow=(10, 190, 200), glow_gain=0.90,
        labels=[
            dict(word="返回", left=1048, win=(1040, 106, 1120, 137), cy=121.5),
            dict(word="返回", left=1128, win=(1120, 106, 1200, 137), cy=121.5),
            dict(word="返回", left=1208, win=(1200, 106, 1280, 137), cy=121.5),
        ],
    ),
]
LABEL_STYLE = dict(fill=(252, 255, 254), boost=ALPHA_BOOST)

# ---------------------------------------------------------------- 7 用户口述修订（第 5 批）
# 用户看完成品后追加的 5 处：NOW PLAYING、徽标 Back/Front、顶部 ALL/PLAY LIST，
# 以及 stand_parts 六行居中。译名以用户当期消息为准（覆盖 任务说明.md 的旧结论）。

# 7a music_parts 底部黄色 NOW PLAYING → 正在播放
# 原白字墨迹 (397,563)-(510,572)，黄光 (388,555)-(518,580)，光色 (255,216,0)。
# 清除窗 (388,552)-(522,582)：左边不碰三个图钉（止于 x387），下边不碰白色数字（起于 y589）。
NOW_PLAYING = dict(
    name="music_parts", word="正在播放",
    win=(388, 552, 522, 582),
    cx=453.5, cy=567.5,               # 原英文墨迹中心 (397+510)/2
    font_size=14, gap=2,
    fill=(255, 253, 247),             # 原白字实测 (255,253,247)
    glow=(255, 216, 0), glow_gain=0.95, boost=1.45,
)

# 7b voice_parts 顶部小格：主网格 47px 行 × 右侧组 38px 行，两套行高不同！
# 主网格列：c0=0~47 / c11=517~564 / c12=564~611 / c13=611~658
# 右侧组：PLAY LIST 列 927~970，行 y0 = 0 / 38 / 76
# 字窗只包住文字，不碰 c12/c13 下方的白色箭头与方块图标（图标自 y21 起）。
VOICE_GRID_ROWS = [0, 47, 94]
VOICE_RIGHT_ROWS = [0, 38, 76]

def _voice_cells():
    out = []
    for ry in VOICE_GRID_ROWS:
        specs = [
            ("ALL 左列",        (3, 9, 44, 37),     ["所有"],          16, 1),
            ("PLAY LIST 左列",  (519, 5, 561, 40),  ["播放", "列表"],  15, 1),
            ("ALL 箭头格",      (569, 3, 606, 18),  ["所有"],          13, 0),
            ("ALL 方块格",      (616, 3, 653, 18),  ["所有"],          13, 0),
        ]
        for tag, w, lines, fs, gap in specs:
            out.append(dict(tag=tag, win=(w[0], w[1] + ry, w[2], w[3] + ry),
                            lines=lines, font_size=fs, gap=gap))
    for ry in VOICE_RIGHT_ROWS:
        out.append(dict(tag="PLAY LIST 右组",
                        win=(929, 3 + ry, 968, 34 + ry),
                        lines=["播放", "列表"], font_size=14, gap=1))
    return out

VOICE_SMALL_CELLS = _voice_cells()        # 15 格
VOICE_CELL_STYLE = dict(
    fill=(252, 255, 254), outline=(4, 52, 60), outline_a=45, boost=1.55,
    dilate=7,            # 白字 + 暗描边并集再外扩，去掉英文的深色投影
    resid_gain=0.55,     # 高频只从真正的青色像素取，别把暗边/图标混进来
)

# ---------------------------------------------------------------- 验收口径
ALL_NAMES = [d["name"] for d in TITLES] + [d["name"] for d in RATES] + [
    "stand_back", "extra_mode", "stand_parts",
    "music_parts", "voice_parts", "visual_parts"]
