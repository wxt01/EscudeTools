# -*- coding: utf-8 -*-
"""
追加任务七：file_parts.png（753×980）存/读档页部件。

用户两轮收敛后定稿：**只译 SAVE / LOAD 两项**，其余（CHANGE 黄胶带、Day、
NO.、◀▶ 箭头、数字、图标、头像条）全部保留。追加任务八（CAUTION 胶带）已取消。

★ 结构关键（实测，别猜）：
  3 行状态 × 2 列文字（LOAD 左 / SAVE 右），行距 34px。
  三行的 **alpha 通道逐像素完全相同**，白核都是纯白 (255,255,255)，
  状态差异**只在光晕 RGB**：行0 暗青 / 行1 亮青 / 行2 亮青绿。
  所以只做一套中文 alpha 层，三行分别上色即可（方法 1.2）。

  属于「A 类透明底发光字」：整块清 alpha=0（连辉光一起），清除区形状与
  字形无关、内部完全均匀，再重画白字 + 青光。

边界（实测）：
  · 白核 LOAD x254..315 / SAVE x335..391，y 777..792 / +34 / +68
  · y768 是纸片下沿与文字光晕之间的**全空行**，清除窗上沿取 768 不碰纸片
  · y870 起是第 4 行数字「6789…」，清除窗下沿到 869(exclusive) 安全
  · x240..245 在文字行高度 0 白像素，清除窗左沿 246 不碰 ▶ 箭头
  · 日历 Day / NO. / CHANGE 胶带都在 x>500，与清除窗不重叠
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC_DIR = ROOT / "待做原图"
DST_DIR = ROOT / "待交付"
WORK_DIR = HERE / "_输出"
WORK_DIR.mkdir(exist_ok=True)
DST_DIR.mkdir(exist_ok=True)

SERIF_CANDIDATES = [
    r"C:\Windows\Fonts\STSONG.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
]
SERIF = next((p for p in SERIF_CANDIDATES if os.path.exists(p)), None)

ALL_NAMES = ["file_parts"]

FILE_PARTS = dict(
    name="file_parts", size=(753, 980),
    # 3 个清除窗（每行一个矩形，LOAD/SAVE 合并，避免格间留 2px 光晕）
    clear_x=(246, 400),
    clear_y0=[768, 802, 836],
    clear_h=33,
    # 6 格落位中心（按原英文白字墨迹中心，不是词格几何中心）
    words=[("LOAD", "读档", 284.5), ("SAVE", "存档", 363.0)],
    centers_y=[784.5, 818.5, 852.5],
    # 原图白字 bbox，供自检逐格核对
    old_white={"LOAD": (254, 777, 315, 792), "SAVE": (335, 777, 391, 792)},
    # 三行光晕色（严格判据实测：alpha 30~120 且 r<150,g>100,b>100 的中位）
    row_glow=[(6, 120, 140), (8, 221, 203), (78, 255, 240)],
    white_fill=(255, 255, 255),
    # 渲染参数（由 calibrate() 网格搜索定，见 build_batch7.py）
    # calibrate() 给出数值最优（gain 0.90 / 18 号字），但 4x 并排目视发现
    # 中文偏小、青光偏弱，重量感明显轻于原图英文。按方法 1.4「数据达标≠视觉达标」
    # 又做了 A~D 四组并排目视，定稿 C 组：20 号字 + 字距 3 + 柔光 6.0 + gain 1.50。
    # 该参数下贴片 alpha>8 的 bbox 实测 x257..312 / y768..800，
    # 正好落在清除窗内，不碰纸片下沿(y<=767)与第 4 行数字(y>=870)。
    style=dict(font_size=20, gap=3, boost=1.35,
               dilate_k=5, blur_tight=2.5, blur_soft=6.0,
               w_tight=0.62, w_soft=0.38, glow_gain=1.50,
               core_dig=0.94),
    # 目标 alpha 分档（每格 79×33 窗口内，三行相同），用于校准打分
    target_bins=(1201, 711, 460, 156),
    # 逐像素禁改区（除 3 个清除窗之外的一切）
    keep=[(0, 0, 753, 768), (0, 869, 753, 980),
          (0, 768, 246, 869), (400, 768, 753, 869)],
)
