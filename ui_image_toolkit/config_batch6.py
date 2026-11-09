# -*- coding: utf-8 -*-
"""
追加任务五 + 任务六（8 张）的全部几何与配色参数。

所有坐标都从 原图/ 当前文件实测，不是任务说明里的估算值：
  任务说明写 title 411x67、dialog 231x685，实测是 411x97、231x585；
  任务说明把两张 parts.png 写成同一个名字，实际文件已拆成
  chart_parts.png（342x287）与 config_parts.png（430x294）。
一律以文件为准（用户当期口述：「正常将图片内容汉化就行，不要过多在意任务要求」）。

本批 7 种「字背后是什么」：
  wood        亮木牌烙字（title）          → 局部暗差 mask + 扩散补底
  brush       青色笔刷条白字（quit/dialog）→ 白+暗描边 mask + 按列插值
  tape        浅棕胶带上的深红字（rate）   → 暗红 mask + 胶带同色回填
  clear_only  只擦字不写（chart_parts）   → 透明底整窗清 alpha=0
  paper       纸片标题/浅棕字（panel/dialog MARKING）→ 局部暗差 + 扩散补底
  shadow      透明底白字带黑影（confirm） → 文字带整窗清 alpha=0 + 白字黑柔光
  config      config_parts 两类小格        → MUTE 透明底清窗 / ALL 青块调和补底
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 2026-11-09 新布局：脚本与 待做原图/待交付/工作输出 同级，ROOT = HERE。
ROOT = HERE
SRC_DIR = ROOT / "待做原图"
DST_DIR = ROOT / "待交付"
WORK_DIR = ROOT / "工作输出"
WORK_DIR.mkdir(exist_ok=True)
DST_DIR.mkdir(exist_ok=True)

SERIF_CANDIDATES = [
    r"C:\Windows\Fonts\STSONG.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
]
SERIF = next((p for p in SERIF_CANDIDATES if os.path.exists(p)), None)
ALPHA_BOOST = 1.30

ALL_NAMES = ["title", "quit", "rate", "chart_parts", "dialog",
             "panel", "confirm_parts", "config_parts"]

# ---------------------------------------------------------------- 1 title.png
# 木牌亮区实测 x30~325 / y22~65；FLOWCHART 深棕烙字中位 (104,44,17)。
# 木牌边缘焦斑也是暗的，所以 stroke 额外要求 lum>45，只取亮区里的笔画。
TITLE = dict(
    name="title", size=(411, 97), word="流程图",
    win=(25, 18, 335, 70), center=(176.0, 43.5),
    style=dict(font_size=36, gap=5, fill=(56, 31, 23),
               outline=(120, 78, 48), outline_a=70, boost=ALPHA_BOOST),
)

# ---------------------------------------------------------------- 2 quit.png
# 3 行 × 3 列，每格 110x38。白字实测：
#   TITLE (21,12)-(88,25) / QUIT (137,12)-(191,29) / BACK (245,12)-(303,25)
#   第 2 行同 x、y+38；第 3 行同 x、y+76（第 3 行白判据会蹭到笔刷边缘白点，
#   左沿仍按 21/137/245 记）。
QUIT = dict(
    name="quit", size=(330, 114),
    rows=[0, 38, 76],
    cols=[0, 110, 220],
    words=["返回标题", "退出游戏", "返回"],
    centers_x=[54.5, 164.0, 274.0],
    style=dict(font_size=17, gap=1, fill=(255, 255, 255),
               outline=(6, 92, 96), outline_a=80, boost=1.35),
)

# ---------------------------------------------------------------- 3 rate.png
# Flow 深红字实测 (58,73)-(87,80)，叠在浅棕胶带上（胶带 y约 64~84）。
# 胶带色实测中位约 (188,158,108)；% / 斜杠 / 两套红色数字全保留。
# 胶带实测：y65~70 是深棕上缘 (165,138,83)，y71~82 主体 (179,156,110)，
# y83+ 已是白色纸片。样本只取主体，整窗按列插值会把 y83 的白卷进来。
RATE = dict(
    name="rate", size=(240, 162), word="流程",
    win=(50, 68, 100, 86), center=(72.5, 76.5),
    tape_sample=(52, 71, 98, 82),
    style=dict(font_size=11, gap=1, fill=(79, 29, 29),
               outline=None, outline_a=0, boost=1.50),
)

# ---------------------------------------------------------------- 4 chart_parts.png
# 右下「日目」白字：日 x219~231 / 目 x240~254，y265~285。
# 只擦「目」（中文说「3日」不需要「目」），x235 起与「日」右沿留 4px 间隙。
CHART_PARTS = dict(
    name="chart_parts", size=(342, 287),
    erase_win=(235, 260, 259, 287),
    keep_win=(215, 260, 235, 287),      # 「日」必须逐像素保留
)

# ---------------------------------------------------------------- 5 dialog.png
# MARKING 深黑字 (10,146)-(99,163)，右侧两行小字与上方横线是装饰，保留。
# BLOCK JUMP 三行白字 (35,279)-(174,295) / +38 / +76，笔刷行高 38。
DIALOG = dict(
    name="dialog", size=(231, 585),
    mark_win=(6, 142, 100, 163), mark_center=(54.5, 154.5),
    jump_rows=[272, 310, 348], jump_center_x=104.5,
    jump_win_x=(25, 190),
    mark_style=dict(font_size=18, gap=2, fill=(39, 30, 19),
                    outline=None, outline_a=0, boost=1.40),
    jump_style=dict(font_size=18, gap=2, fill=(255, 255, 255),
                    outline=(6, 80, 84), outline_a=80, boost=1.35),
)

# ---------------------------------------------------------------- 6 panel.png
# 四张纸片上的标题，实测墨迹与配色（局部暗差 bbox）：
PANEL = dict(
    name="panel", size=(374, 720),
    labels=[
        # win 上下沿必须都落在同一张纸片内，按列插值才不会把绿色面板卷进来。
        dict(tag="Information", word="信息", win=(105, 4, 270, 27),
             center=(186.0, 15.5), font_size=20, gap=2,
             style=dict(fill=(48, 46, 40), outline=None, outline_a=0, boost=1.35)),
        dict(tag="BLOCK", word="方块", win=(185, 114, 285, 136),
             center=(234.5, 125.0), font_size=16, gap=2,
             style=dict(fill=(160, 143, 105), outline=None, outline_a=0, boost=1.45)),
        dict(tag="PREVIEW", word="预览", win=(180, 320, 295, 346),
             center=(235.5, 334.0), font_size=16, gap=2,
             style=dict(fill=(165, 138, 122), outline=None, outline_a=0, boost=1.45)),
        # 这条浅灰横条：填色必须取「窗内未改动的干净纸色」实测值。
        # 首版填 (185,187,169) 太暗，改动区均色 169 对周围 209，色差 42，
        # 6x 放大下是一块边界清晰的深色矩形补丁。实测窗内净区中位约
        # (209,213,198)，改后色差降到个位数。
        dict(tag="FLOWCHART SCALING", word="流程图缩放", win=(92, 550, 288, 572),
             center=(187.5, 561.0), font_size=16, gap=2,
             fill_color=(209, 213, 198),
             style=dict(fill=(62, 65, 55), outline=None, outline_a=0, boost=1.40)),
    ],
)

# ---------------------------------------------------------------- 7 confirm_parts.png
# 三处「次回から確認しない」白字带黑影，实测白字：
#   (71,602)-(273,621) / (368,602)-(570,621) / (665,599)-(867,621)
# 左边三个青色小方块 x15~52 / 315~340 / 612~650，清窗从文字左沿前 6px 起，不碰青块。
# ○× 菱形按钮 y<220、CAUTION 胶带 y220~580、右侧竖条、白色勾选 x899+ 全部禁止改动。
CONFIRM = dict(
    name="confirm_parts", size=(1368, 647), word="下次不再确认",
    wins=[(62, 595, 282, 630), (359, 595, 579, 630), (656, 592, 880, 630)],
    centers=[(172.0, 611.5), (469.0, 611.5), (766.0, 609.5)],
    # 保留原黑色渐变阴影带：只擦白字笔画，按列插值补回深色，不再整窗清 alpha。
    style=dict(font_size=16, gap=1, fill=(244, 244, 244),
               outline=(0, 0, 0), outline_a=85, boost=1.50),
    keep=[(0, 0, 1368, 220), (0, 220, 1368, 580), (0, 580, 60, 647),
          (282, 580, 359, 647), (579, 580, 656, 647), (880, 580, 1368, 647)],
)

# ---------------------------------------------------------------- 8 config_parts.png
# MUTE 12 格：行 y0=0/42/84，列 x0=168/210/252/294，
#   文字墨迹 (171..206, y0+1..y0+8) 等 4 列，前两列白 (255,255,255)、
#   后两列深灰 (42,42,42)。文字在透明底，整窗清 alpha=0 即可。
# ALL 6 格：列 x0=336/378，行 y0=0/42/84，白字叠在青色噪点块上，
#   青块 y3~38、白框自 y21 起，文字窗 (x0+5, ry+6)-(x0+41, ry+19)。
# ★ 同一张图里两套行高：MUTE 是 42px 网格（字 y1/43/85），
#   ALL 却是 47px 网格（字 y7/54/101、白框自 y21/68/115 起）。
#   按 42 猜 ALL 会让第三行整行漏擦，旧 ALL 与中文叠在一起（首版翻车）。
CONFIG_PARTS = dict(
    name="config_parts", size=(430, 294),
    rows=[0, 42, 84],                  # MUTE
    all_rows=[0, 47, 94],              # ALL
    mute_cols=[168, 210, 252, 294],
    all_cols=[336, 378],
    mute_style={
        "light": dict(font_size=11, gap=1, fill=(255, 255, 255),
                      outline=(70, 70, 70), outline_a=55, boost=1.45),
        "dark":  dict(font_size=11, gap=1, fill=(42, 42, 42),
                      outline=None, outline_a=0, boost=1.45),
    },
    all_style=dict(font_size=12, gap=1, fill=(250, 253, 253),
                   outline=(4, 52, 60), outline_a=50, boost=1.50),
    all_dilate=7,          # 白字 + 深蓝描边并集后外扩，去掉整圈投影字影
)
