# -*- coding: utf-8 -*-
"""
四张 frame_*.png 的布局与文案（文案全部来自 任务说明.md 的用户定稿，勿改）。

实测结论（拿不准时先重跑 diag_frame.py 这类投影诊断，别凭印象）：
  * 四张都是 RGBA **透明叠加层**：深色背景是游戏里另画的，图里是透明的。
    所以擦字 = 把文字带清成 alpha=0，不需要补背景纹理。
  * 白色日文带青色外发光，下方约 +27px 处是青色水彩笔触（装饰，必须保留）。
    文字带 y 与笔触带 y 不重叠，清除窗口止于文字底 +3px 即可。
  * 三列中心固定 x = 220 / 640 / 1058，行间距 127px。
    frame_text 因为顶部有照片，整体比其它图下移一行（y 149.5 / 276 / 403）。
  * frame_text 实际尺寸是 1280x672，不是文档里写的 566 —— 以实际文件为准。
  * frame_manual 的键位行是左对齐的（不是居中），标题才居中；
    块1 实际没有鼠标行，块2 是「ホイール↑」、块3 是「左クリック/ホイール↓」。

对齐原则：跟随原图。标题/设置项居中于列中心，键位行左对齐于原 x 起点。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC_DIR = HERE.parent / "原图"
DST_DIR = HERE.parent / "交付成品放这里"
WORK_DIR = HERE / "_输出"

# 每列：(清除窗口 x0, x1, 文字中心 x)
COLS = [(20, 410, 220), (440, 830, 640), (870, 1250, 1058)]

# 字体：原日文是无衬线斜体，中文用雅黑系更贴；白字另有青色外发光
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]
import os
FONT = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)

# 样式：字号 / 颜色 / 是否带青光 / 字距
STYLES = {
    "white":  dict(size=20, rgb=(233, 247, 246), gap=1, glow=True),
    "green":  dict(size=17, rgb=(56, 240, 8), gap=0, glow=False),
    "yellow": dict(size=17, rgb=(240, 240, 72), gap=0, glow=False),
    "note":   dict(size=15, rgb=(226, 238, 236), gap=0, glow=False),
}
GLOW_RGB = (0, 190, 190)
GLOW = dict(expand=5, tight_blur=2.0, tight_w=0.42,
            soft_blur=5.5, soft_w=0.20, core_keep=0.02)


def _frame(size, rows):
    """把 (清除y0,清除y1,文字中心y,[三列文案]) 展开成 clears / texts。"""
    clears, texts = [], []
    for y0, y1, cy, words in rows:
        for ci, w in enumerate(words):
            if w is None:
                continue                       # 保留原图（BGM / BGV / 空位）
            x0, x1, cx = COLS[ci]
            clears.append((x0, x1, y0, y1))
            texts.append(dict(x=cx, cy=cy, text=w, style="white", align="center"))
    return dict(size=size, clears=clears, texts=texts)


FRAMES = {}

# ---------------------------------------------------------------- 文字页 9 条
FRAMES["frame_text"] = _frame((1280, 672), [
    (133, 164, 149.5, ["普通场景窗口不透明度", "事件场景窗口不透明度", "已读颜色设定"]),
    (260, 290, 276,   ["文字显示速度", "自动播放显示速度", "自动播放选项后"]),
    (387, 417, 403,   ["跳过选项后", "跳过速度", "未读跳过"]),
])

# ---------------------------------------------------------------- 系统页 8 条
FRAMES["frame_system"] = _frame((1280, 566), [
    (6, 37, 22.5,    ["画面尺寸", "保存后退出", "光标自动追踪"]),
    (133, 164, 149.5, ["光标自动隐藏", "提示消息", "环境设定"]),
    (260, 290, 276,   [None, "右键·Esc 设置", None]),
    (387, 417, 403,   [None, "确认对话框", None]),
])

# ---------------------------------------------------------------- 声音页 9 条（BGM/BGV 原样保留）
FRAMES["frame_sound"] = _frame((1280, 566), [
    (6, 37, 22.5,    ["主音量", None, "环境音"]),
    (133, 164, 149.5, [None, "H 场景效果音", "效果音"]),
    (260, 290, 276,   ["系统效果音", "语音", "点击时停止语音"]),
])

# ---------------------------------------------------------------- 操作说明页
_man_clears, _man_texts = [], []


def _cl(ci, y0, y1, xspan=None):
    if xspan is None:
        x0, x1, _ = COLS[ci]
    else:
        x0, x1 = xspan
    _man_clears.append((x0, x1, y0, y1))


def _txt(x, cy, text, style="white", align="center"):
    _man_texts.append(dict(x=x, cy=cy, text=text, style=style, align=align))


# 组1：三个块的标题 + 键盘行 + 鼠标行
for ci in range(3):
    _cl(ci, 6, 36)
for ci, title in enumerate(["隐藏消息窗口", "回顾记录", "推进消息"]):
    _txt(COLS[ci][2], 22, title)
for ci in range(3):
    _cl(ci, 48, 73)
for ci, keyname in enumerate(["Space", "Back Space", "Enter"]):
    _txt([43, 461, 879][ci], 60, "键盘 : " + keyname, "green", "left")
# 块1 实际没有鼠标行；块2 是 ホイール↑，块3 是 左クリック/ホイール↓
for ci in (1, 2):
    _cl(ci, 77, 100)
_txt(461, 89, "鼠标 : 滚轮↑", "yellow", "left")
_txt(879, 89, "鼠标 : 左键/滚轮↓", "yellow", "left")

# 组2：块4 / 块5
for ci in (0, 1):
    _cl(ci, 133, 164)
_txt(220, 149.5, "取消·返回")
_txt(640, 149.5, "特殊跳过")
for ci in (0, 1):
    _cl(ci, 175, 198)
_txt(43, 186, "键盘 : Esc", "green", "left")
_txt(461, 186, "键盘 : Ctrl", "green", "left")
_cl(0, 204, 226)
_txt(43, 215, "鼠标 : 右键", "yellow", "left")
_cl(1, 202, 240, xspan=(440, 840))
_txt(451, 211.5, "注意：无论「未读跳过」设置如何，", "note", "left")
_txt(451, 229.5, "已读与未读都会被跳过。", "note", "left")

FRAMES["frame_manual"] = dict(size=(1280, 566), clears=_man_clears, texts=_man_texts)

# 青色水彩笔触的实际 y 带（从原图量出），自检时逐像素核对这些像素没被动过。
# 不能从「每条 clear 的 y1+N」推：frame_manual 的键位行紧跟在标题后面，
# 会被误当成笔触。
BRUSH_BANDS = {
    "frame_text":   [(166, 174), (293, 301), (420, 428)],
    "frame_system": [(40, 48), (167, 174), (293, 301), (420, 428)],
    "frame_sound":  [(40, 48), (167, 174), (293, 301)],
    "frame_manual": [(40, 48), (167, 174)],
}
