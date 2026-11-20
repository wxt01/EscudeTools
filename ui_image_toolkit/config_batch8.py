# -*- coding: utf-8 -*-
"""
戦巫〈センナギ〉UI 第一批 · 第 8 批配置
第一组：红色花卉纹金字标题 3 张 + 透明底三态发光按钮 2 张。

★ 用户当期口径：图里文字是**独立单元**（格 / 标签 / 按钮词），因排版紧凑彼此贴近，
  可能被连读成连贯词。按单元逐个识别、逐个翻译、按各自原 bbox 放回原位，
  不做跨单元语义串联，不因拼接出的字面组合改变处理方式。

★ 方法论判型（docs/02）：红底花卉纹 + 金字属于「纹理压在字下」的高难底板。
  本批先用 diffuse_texture 试补，放大验收若出现明显补丁，按方法论保留原文并记录，
  不硬做。日文假名副标题是片假名音译装饰（エクストラ / セーブ / ロード），
  与上方大字同义，保留原文不重复造词，交付清单里标注。
"""
import os
from pathlib import Path
from _work import ROOT, SRC_DIR, DST_DIR, WORK_DIR  # noqa: E402

SERIF_CANDIDATES = [
    r"C:\Windows\Fonts\STSONG.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
]
SERIF = next((p for p in SERIF_CANDIDATES if os.path.exists(p)), None)

ALL_NAMES = ["extra_extra_title", "file_save_title", "file_load_title",
             "common_sys_quit", "common_sys_back",
             # 第二组：浅金底深字标签
             "extra_music_rate", "extra_scene_rate", "extra_staff_parts",
             # 第三组：多状态按钮网格
             "config_button", "config_radio_button"]

# 2026-11-16：此前暂缓的两张已按用户给定口径完成，不再有跳过项。
# config_frame_voice：人名定稿（10 个，两列完全一致）。
# config_index：用户指出「就是很简单的发光文字汉化」。上轮把窗口扩到整圈
# 光晕、又用扩散补底从菱形间透明空隙取样，才做出黑横条与斑驳噪点；
# 改为窗口严格贴住文字带（避开菱形金边）+ 深色底中位回填 + 逐行发光配色。
SKIPPED = []

# ---------------------------------------------------------------- 红底花卉纹金字标题
# 实测：金字 RGB 中位 [232,208,100]；大字 y15..55，日文小字 y61..79（保留）。
# 三张图底板像素完全一致（同款斜切花卉纹），只换大字。
GOLD = (232, 208, 100)
TITLE_STYLE = dict(font_size=36, gap=3, fill=GOLD,
                   outline=None, outline_a=0, boost=1.20)
TITLES = [
    dict(name="extra_extra_title", size=(341, 102), word="额外内容",
         win=(30, 10, 255, 58), center=(142.5, 34.5),
         keep=[(0, 58, 341, 102)]),          # 日文副标题 + 花纹
    dict(name="file_save_title", size=(341, 102), word="存档",
         win=(56, 10, 218, 58), center=(137.0, 35.0),
         keep=[(0, 58, 341, 102)]),
    dict(name="file_load_title", size=(341, 102), word="读档",
         win=(56, 10, 238, 58), center=(147.0, 35.0),
         keep=[(0, 58, 341, 102)]),
]

# ---------------------------------------------------------------- 透明底三态发光按钮
# common_sys_quit（309×120）：3 行 × 3 词，行 0 金色描边字 / 行 1 白字黄光 / 行 2 粉字粉光
SYS_WORDS = [("TITLE", "返回标题", 55.0),
             ("QUIT", "退出游戏", 160.0),
             ("BACK", "返回", 257.5)]
SYS_ROWS = [
    dict(y0=4, y1=36, cy=19.5, fill=(219, 185, 104), glow=(150, 110, 40),
         gain=0.55, boost=1.20),
    dict(y0=39, y1=79, cy=59.5, fill=(255, 255, 255), glow=(198, 151, 23),
         gain=1.10, boost=1.30),
    dict(y0=80, y1=119, cy=99.5, fill=(255, 235, 238), glow=(255, 103, 121),
         gain=1.10, boost=1.30),
]
SYS_QUIT = dict(name="common_sys_quit", size=(309, 120),
                clear_x=(2, 307), rows=SYS_ROWS, words=SYS_WORDS,
                font_size=21, gap=1,
                keep=[(0, 0, 309, 4), (0, 119, 309, 120)])

# common_sys_back（474×120）：左侧红色斜切花纹是装饰（绝对不碰），
# 右侧 x>=378 是 3 行 BACK 发光字。
SYS_BACK = dict(name="common_sys_back", size=(474, 120),
                clear_x=(378, 474), rows=SYS_ROWS,
                words=[("BACK", "返回", 426.0)],
                font_size=21, gap=1,
                keep=[(0, 0, 378, 120)])

# ---------------------------------------------------------------- 交付译名表
# ---------------------------------------------------------------- 第二组：浅金底深字标签
# 实测：MUSIC/SCENE 黑字 x56..123 / 56..125、y16..29（胶带浅金渐变），
# 花形装饰在 x<45 与 x>140，% 与 0123456789 白数字在 y>=45 —— 全部保留。
# 金条上的深蓝黑字 RGB [19,16,45]，y9..26。
LABEL_STYLE = dict(fill=(20, 16, 40), boost=1.35, gap=1)
LABELS = [
    dict(name="extra_music_rate", size=(188, 100), font_size=16,
         labels=[dict(word="音乐", win=(49, 8, 131, 37), center=(89.5, 22.5))]),
    dict(name="extra_scene_rate", size=(188, 100), font_size=16,
         labels=[dict(word="场景", win=(49, 8, 133, 37), center=(90.5, 22.5))]),
    dict(name="extra_staff_parts", size=(1229, 35), font_size=17,
         labels=[dict(word="角色语音", win=(46, 3, 332, 31), center=(188.0, 17.0)),
                 dict(word="制作名单", win=(650, 3, 956, 31), center=(802.5, 17.5))]),
]

# ---------------------------------------------------------------- 第三组：多状态按钮网格
# 实测（亮字投影，窗口均落在按钮内部，不碰菱形/胶囊边框）：
#   config_index 3 行 × 6 菱形：行 y31..45 / 133..160 / 233..274，
#     词块 x (37,104)(171,259)(318,403)(459,553)(604,696)(750,813)
#   config_button 3 行 × 10 胶囊：行 y60..76 / 106..121 + 行0 y约15..32，
#     词块 x (44,93)(192,227)(293,407)(457,523)(602,656)(735,805)
#            (875,943)(1015,1085)(1134,1244)(1342,1464)
#   config_radio_button 6 行 × 3 列：行 y8..23 / 41..56 / 74..89 / 106..124 /
#     139..157 / 172..189；列 x (43..169)(218..344)(393..519)
GRIDS = [
    dict(name="config_button", size=(1547, 138), font_size=17, gap=1,
         axis="row", kind="light", boost=1.40,
         row_fills=[(240, 205, 120), (255, 245, 235), (255, 220, 130)],
         rows=[(8, 36, 22), (55, 82, 68), (100, 127, 113)],
         cols=[(38, 100), (186, 234), (287, 413), (451, 529), (596, 662),
               (729, 811), (869, 949), (1009, 1091), (1128, 1250), (1336, 1470)],
         words=["关", "开", "普通", "快速", "窗口", "全屏", "保持", "返回", "取消", "应用"]),
    dict(name="config_radio_button", size=(525, 198), font_size=15, gap=1,
         axis="col", kind="light", boost=1.35,
         mode="transparent",     # 实测窗口内 2491 像素 alpha=0，是透明底白字，无需补底
         row_fills=[(235, 235, 235)] * 6,
         rows=[(4, 27, 16), (37, 60, 49), (70, 93, 82),
               (102, 128, 115), (135, 161, 148), (168, 193, 180)],
         cols=[(40, 172), (215, 347), (390, 522)],
         words=["菜单", "设置", "回顾记录", "自动播放", "跳过播放", "隐藏文本框"]),
]

GLOSSARY = {
    "EXTRA": "额外内容", "SAVE": "存档", "LOAD": "读档",
    "TITLE": "返回标题", "QUIT": "退出游戏", "BACK": "返回",
    "MUSIC": "音乐", "SCENE": "场景",
    "CHARACTER VOICE": "角色语音", "PRODUCTION STAFF": "制作名单",
    "TEXT": "文本", "SYSTEM": "系统", "SOUND": "声音", "CHARACTER": "角色",
    "SHORT CUT": "快捷键", "RESET": "重置",
    "OFF": "关", "ON": "开", "NORMAL": "普通", "FAST": "快速",
    "WINDOW": "窗口", "FULL": "全屏", "KEEP": "保持", "CANCEL": "取消",
    "SETTING": "应用", "MENU": "菜单", "BACK LOG": "回顾记录",
    "オート再生": "自动播放", "スキップ再生": "跳过播放", "フレーム消去": "隐藏文本框",
    # 第四~七组新增
    "CONTINUE": "继续游戏", "NEW GAME": "开始游戏", "CONFIG": "环境设置",
    "DOMINATION": "征服模式", "Q.SAVE": "快速存档", "Q.LOAD": "快速读档",
    "HELP": "帮助", "CHANGE": "切换", "CONTROL": "操作", "VOLUME": "音量",
    "MUSIC LIST": "音乐列表", "FAVORITE VOICE": "收藏语音",
    "PLAY LIST": "播放列表", "MUTE": "静音",
    "BGM": "背景音乐", "BGV": "背景语音",
    "次回から確認しない": "下次不再确认",
}

# ============================================================================
# 第四~七组：剩余 16 张 · 通用「独立文字单元」配置
#
# ★ 用户硬口径：图里文字是独立单元（格 / 标签 / 按钮词 / 设置项），因排版紧凑
#   彼此贴近可能连读成词。按单元逐个识别、逐个翻译、按各自原 bbox 放回原位，
#   不跨单元串联，也不因拼接出的字面组合改变处理方式或跳过任何一个单元。
#
# kind（底板判型 → 决定擦字与补底路线）：
#   flat    浅金/纸底 + 深棕字：local_dark 找笔画 + 窗内干净纸色中位回填
#   clear   透明/深底 + 亮字：整窗清 alpha=0，不补底（补底反而造色板）
#   diffuse 复杂纹理/渐变底 + 亮字：相对底色亮度差找字 + diffuse_texture 跟随纹理
#   glow    透明底多状态发光字：整行清 alpha + 逐行配色重画（含光晕）
#
# 每个单元 win 都内缩到文字墨迹区，避开金框边线、勾选框、图标、数字。
# 所有单元窗口之外一律逐像素还原，装饰零差异。
# ============================================================================

def _grid(words, xs, ys, axis="cell", fills=None, ink=None, kind=None, dilate=None):
    """按 行 y 区间 × 列 x 区间 展开成独立单元（逐字、逐个放回原位）。

    axis="cell" 每格一个词（框架图 3 列 × 3 行 = 9 个不同设置项）；
    axis="row"  每行同一个词、各列只是不同状态（popup 4 列 / check_box 3 列）。
    fills 按列给字色（多状态列字色不同时用）。
    """
    out = []
    for ri, (y0, y1) in enumerate(ys):
        for ci, (x0, x1) in enumerate(xs):
            word = (words[ri * len(xs) + ci] if axis == "cell"
                    else words[ri] if len(words) > 1 else words[0])
            u = dict(win=(x0, y0, x1, y1),
                     center=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
                     word=word)
            if fills is not None:
                u["fill"] = fills[ci]
            if ink is not None:
                u["ink"] = ink
            if kind is not None:
                u["kind"] = kind
            if dilate is not None:
                u["dilate"] = dilate
            out.append(u)
    return out


INK_BROWN = (32, 26, 28)      # 浅金框上的深棕字（实测）
INK_WHITE = (238, 236, 230)   # 深色底上的白字
INK_GOLD = (219, 185, 104)    # 深色底上的金字（实测）
INK_GOLD_LIGHT = (250, 228, 155)
INK_PAPER_DARK = (58, 54, 52)
GREEN_TIP = (147, 232, 136)   # 操作说明绿字（实测）
GOLD_TIP = (245, 213, 102)    # 操作说明金字（实测）
WHITE_TIP = (250, 250, 250)   # 操作说明白注释（实测）

# 浅金框通用列（1280 宽图，3 列；框内缩避开描边）
FRAME_COLS = [(23, 403), (449, 829), (876, 1256)]
FRAME_ROWS_3 = [(12, 34), (124, 146), (236, 258)]
FRAME_ROWS_TEXT = [(124, 146), (236, 258), (348, 370)]

def _voice_buttons():
    """extra_voice_parts 按钮阵列：ALL / PLAY LIST 逐独立文字单元汉化。

    ★ 2026-11-16 返工（用户反馈「中文以很大的方块贴上去、盖住原图案」）：
      旧版按整窗矩形补底 —— btnfill 的 rim 判据把圆内暗底一起卷进 mask，
      再整片铺成浅色平板；clear 又把底部标签整块清成透明，连 y331 / y360
      两条金色细线一起挖掉；圆周金边也正好落在矩形四角被切掉。
      正解：每个单元只有两个**紧贴字形的框**：
        band = 原英文墨迹 bbox ±2px —— 只在这里按字形 mask 擦旧字；
        win  = 稍外放几 px —— 只用来容纳中文贴片和自检允许区。
      中文贴片另按「渲染后中文墨迹 bbox」事前框定（clip_pad），不沿用 band。
      圆周金边、方形金框、勾号/方框图标、标签上下金线全在框外逐像素保留。
    """
    fills = [(190, 160, 98), (245, 195, 150), (225, 175, 125)]
    # 3 行 × 7 单元：逐格实测原英文墨迹 bbox（已排除圆周金边 / 方形金框）
    rows = [
        [("全部", (6, 17, 46, 34)), ("播放", (580, 14, 615, 24)),
         ("列表", (581, 28, 616, 38)), ("全部", (633, 9, 666, 19)),
         ("全部", (685, 9, 718, 19)), ("播放", (1014, 2, 1057, 17)),
         ("列表", (1014, 18, 1057, 33))],
        [("全部", (6, 69, 46, 86)), ("播放", (580, 66, 615, 76)),
         ("列表", (581, 80, 616, 90)), ("全部", (633, 61, 666, 71)),
         ("全部", (685, 61, 718, 71)), ("播放", (1014, 35, 1057, 51)),
         ("列表", (1014, 53, 1057, 67))],
        [("全部", (6, 121, 46, 138)), ("播放", (580, 118, 615, 128)),
         ("列表", (581, 132, 616, 142)), ("全部", (633, 113, 666, 123)),
         ("全部", (685, 113, 718, 123)), ("播放", (1014, 70, 1057, 85)),
         ("列表", (1014, 86, 1057, 101))],
    ]
    out = []
    for ri, row in enumerate(rows):
        for i, (word, (x0, y0, x1, y1)) in enumerate(row):
            # 「播放 / 列表」是两行排版。原英文行心距只有 14~16px，
            # 中文 16px 字高会上下贴死甚至笔画交叠（用户反馈）。
            # 按各自原行心向两侧推开：圆形行心距 20px、方形 18px；
            # 方形格子只有 34px 高，字号收到 14 才留得出 3px 空隙。
            two_line = i in (1, 2, 5, 6)
            if i in (1, 2):            # 圆形 PLAY LIST
                dy, fsz, wy = (-3 if i == 1 else 3), 16, 10
            elif i in (5, 6):          # 方形 PLAY LIST
                dy, fsz, wy = (-0.5 if i == 5 else 1.5), 15, 8
            else:
                dy, fsz, wy = 0, 16, 6
            cy = (y0 + y1) / 2.0 + dy
            out.append(dict(
                # y0 必须夹到 0：第 1 行方形按钮 y=2，直接减 6 会得到负
                # 坐标，numpy 负切片把 allow 写空，成品上沿被逐像素还原成
                # 英文（实测「PLAY」残留 226px）。两行单元还要额外放宽，
                # 否则拉开后的中文贴片会被 assert / allow 裁掉。
                win=(x0 - 4, max(0, y0 - wy), x1 + 4, y1 + wy),
                band=(x0 - 2, y0 - 2, x1 + 2, y1 + 2),   # 只擦旧字的紧框
                center=((x0 + x1) / 2.0, cy),
                word=word, kind="glyph", ink="btngold",
                dilate=5, protect_border=2, clip_pad=2,
                boost=1.50, fill=fills[ri], font_size=fsz))
    return out


VOICE_BUTTONS = _voice_buttons()

# ---------------------------------------------------------------- 2026-11-16 追加两张
# config_index：3 行 × 6 列发光菱形。用户定调「就是很简单的发光文字汉化」——
# 窗口严格贴住文字带（避开菱形金边斜边），深色底中位回填，逐行换发光配色。
INDEX_WORDS = ["文本", "系统", "声音", "角色", "快捷键", "重置"]
INDEX_ROW_STYLE = [
    dict(fill=(219, 185, 104), glow=None, gain=0.0),
    dict(fill=(245, 240, 225), glow=(198, 151, 23), gain=1.00),
    dict(fill=(255, 235, 238), glow=(255, 103, 121), gain=1.00),
]
# 18 格**逐格实测**原文字亮核 bbox (x0,y0,x1,y1)。
# 第 6 列 RESET 三行是「上移的悬停/选中态」，实测中心 y=39 / 139 / 238.5，
# 而同排其它词是 38 / 152 / 266 —— 旧版按整排 (y0+y1)/2 统一给 center，
# 把它们跟其它词对齐了，行1 偏下 14px、行2 偏下 27px（用户反馈「位置不对、
# 与其它字进行了对齐」）。正解：每格用各自实测墨迹中心，窗口按 bbox 收紧，
# 中文贴片再按原图 alpha 菱形轮廓软裁，棱角不超出斜边。
INDEX_BOX = [
    [(37, 31, 104, 45), (171, 31, 259, 45), (318, 31, 403, 45),
     (459, 31, 553, 45), (604, 31, 696, 46), (750, 33, 813, 45)],
    [(36, 145, 104, 160), (170, 144, 260, 160), (317, 144, 404, 160),
     (458, 144, 553, 160), (603, 144, 696, 160), (749, 133, 814, 145)],
    [(36, 258, 105, 274), (170, 258, 260, 274), (317, 258, 404, 274),
     (458, 258, 553, 274), (603, 258, 696, 274), (749, 232, 814, 245)],
]
# 最右列三个 RESET 是「上移悬停态」，菱形整体比同排其它格小一圈：
# 逐行拟合原图内框金线（|x-cx|+|y-cy|=R），普通格 R≈62，这三格 R≈47。
# 旧版统一按「离字心 |x|>47」保护内框线，小菱形的内框线正好落进这个
# 保护区内侧，被当成旧字擦掉 → 用户反馈「三个重置棱形边缘还是残缺」。
# 逐行逐 y 拟合内框金线（|x-fcx|+|y-fcy|=R）：三格 R 都是 49，
# 中心 y=40/138/238，拟合残差仅 ±0.5px。旧版把中心取成 42/141/238、
# R=47，残差摆到 45.5~51.5，只能把保护带放宽到 ±7，结果把斜线内侧
# 5px 的旧字光晕也一起保住，冒出几个孤立小金点。
RESET_FRAME = [(781.5, 40.0, 49.0), (781.5, 138.0, 49.0),
               (781.5, 238.0, 49.0)]


def _index_cells():
    out = []
    for ri, row in enumerate(INDEX_BOX):
        st = INDEX_ROW_STYLE[ri]
        for ci, (bx0, by0, bx1, by1) in enumerate(row):
            # ★ 返工：旧版 rowflat/vert_flat 把整个 win 矩形铺成平色，
            #   实测差异热图是一块 114×40 的实心红矩形，把菱形内框金线
            #   从中间切断（用户反馈「棱角超出菱形、图案被盖住」）。
            #   现改为：band=字 bbox±4 只按字形擦旧字/光晕；win=稍外放
            #   只用来容纳中文光晕；中文贴片按渲染后墨迹 bbox 事前框定。
            #   框外（含菱形内框线、外金边、菱形渐变）逐像素零改动。
            u = dict(win=(bx0 - 9, by0 - 18, bx1 + 9, by1 + 18),
                     band=(bx0 - 10, by0 - 10, bx1 + 10, by1 + 10),
                     center=((bx0 + bx1) / 2.0, (by0 + by1) / 2.0),
                     word=INDEX_WORDS[ci],
                     kind="glyph", ink="glowband", dilate=3,
                     fill=st["fill"], font_size=19)
            if ci == 5:                # 三个「重置」用实测小菱形几何保金线
                u["frame"] = RESET_FRAME[ri]
            if st["glow"]:
                # 发光态：旧英文光晕整片擦掉，中文光晕按「中文字形软掩膜」
                # 淡出，不用矩形 clip 硬裁（硬裁会留下笔直的黄色光带）。
                u.update(glow=st["glow"], gain=st["gain"], soft_shape=True)
            else:
                # 暗态金字笔画细，boost 提到 1.7 让它在深蓝菱形上够清晰
                u.update(clip_pad=3, boost=1.70)
            out.append(u)
    return out


# config_frame_voice：10 行 × 2 列，两列是同一人名（左暗化头像 / 右彩色头像）。
# 译名由用户 2026-11-16 定稿，顺序为从第一行往下数。
VOICE_NAMES = ["神子园姬华", "艾尔", "萨莉雅", "睦", "夏洛特",
               "徒野咲夜", "酒井户清吉", "其他（女）", "其他（男）", "其他"]
# 逐行实测：原名白字墨迹 bbox（左列 x / 绝对 y），中文译名估宽。
# 【窗口必须按每行原名实际宽度收紧】旧版固定 x7..165 一整格 158px 宽，
# 再用 dist 判据把花卉纹/头像亮部一起判成「字」，等于把整格铺成平色；
# 中文比原名短时（如「睦」22px vs ムツ 43px）右侧就空出一块平板，
# 用户反馈「原名扣得太生硬、出现一块空缺」。收紧窗口后中文短也不留空。
VOICE_BOX = [
    (14, 13, 156, 37), (16, 196, 67, 211), (17, 371, 104, 391),
    (19, 550, 61, 568), (17, 728, 150, 746), (15, 904, 139, 926),
    (16, 1081, 154, 1104), (19, 1260, 139, 1282),
    (19, 1438, 139, 1460), (19, 1617, 88, 1637),
]


def _voice_name_cells():
    out = []
    for ri, word in enumerate(VOICE_NAMES):
        lx, ty, rx, by = VOICE_BOX[ri]
        width = len(word) * 22 * 0.95       # 中文墨迹估算宽，保持原图左沿对齐
        for ci, off in enumerate([0, 314]):
            out.append(dict(
                win=(lx - 3 + off, ty - 3, rx + 4 + off, by + 4),
                center=(lx + off + width / 2.0, (ty + by) / 2.0),
                word=word, kind="stroke", ink="light", dilate=1,
                fill=(255, 245, 245), glow=(255, 90, 110), gain=0.70,
                font_size=22, clip=True))
    return out


CELLS = [
    # ---------------------------------------------------------------- D 组：金框日文设置项
    dict(name="config_frame_sound", size=(1280, 538), kind="flat",
         font_size=20, gap=1, boost=1.35, fill=INK_BROWN,
         units=_grid([
             "主音量", "背景音乐", "背景语音",
             "环境音", "场景音效", "音效",
             "系统音效", "语音", "点击时停止语音",
         ], FRAME_COLS, FRAME_ROWS_3)),
    dict(name="config_frame_system", size=(1280, 538), kind="flat",
         font_size=19, gap=1, boost=1.35, fill=INK_BROWN,
         units=_grid([
             "画面尺寸", "存档结束后", "光标自动跟随",
             "光标自动隐藏", "报告消息", "字体及非活动状态设置",
         ], FRAME_COLS, [(12, 34), (124, 146)]) + [
             dict(win=(23, 236, 1256, 258), center=(639.5, 247), word="右键・Esc 设置"),
             dict(win=(23, 348, 1256, 370), center=(639.5, 359), word="确认对话框"),
         ]),
    dict(name="config_frame_manual", size=(1280, 538), kind="flat",
         font_size=19, gap=1, boost=1.35, fill=INK_BROWN,
         units=_grid([
             "隐藏文本框", "回顾记录", "推进文本",
             "取消・返回", "特殊跳过", "战斗快进",
         ], FRAME_COLS, [(12, 34), (124, 146)]) + [
             # 金框下方的键位说明：英文键名（Space/Esc/Ctrl…）属保留项，
             # 日文引导词逐单元译出，按各自原 bbox 放回，不做跨行串联。
             # 窗口上下各留足余量：clear 路线会把窗口内清成透明，
             # 中文墨迹一旦超出窗口边界就被 arr[~allow]=A[~allow] 裁碎。
             dict(win=(28, 42, 252, 68), center=(140, 53), word="键盘：Space",
                  kind="clear", ink="light", fill=GOLD_TIP, font_size=14),
             dict(win=(452, 42, 712, 68), center=(582, 53), word="键盘：Back Space",
                  kind="clear", ink="light", fill=GOLD_TIP, font_size=14),
             dict(win=(882, 42, 1252, 68), center=(1067, 53), word="键盘：Enter",
                  kind="clear", ink="light", fill=GOLD_TIP, font_size=14),
             dict(win=(452, 68, 712, 96), center=(582, 82), word="鼠标：滚轮↑",
                  kind="clear", ink="light", fill=GREEN_TIP, font_size=14),
             dict(win=(882, 68, 1252, 96), center=(1067, 82), word="鼠标：左键／滚轮↓",
                  kind="clear", ink="light", fill=GREEN_TIP, font_size=14),
             dict(win=(28, 154, 252, 181), center=(140, 166), word="键盘：Esc",
                  kind="clear", ink="light", fill=GOLD_TIP, font_size=14),
             dict(win=(28, 181, 252, 209), center=(140, 194), word="鼠标：右键",
                  kind="clear", ink="light", fill=GREEN_TIP, font_size=14),
             dict(win=(452, 154, 712, 181), center=(582, 166), word="键盘：Ctrl",
                  kind="clear", ink="light", fill=GOLD_TIP, font_size=14),
             dict(win=(882, 154, 1252, 181), center=(1067, 166), word="键盘：Ctrl",
                  kind="clear", ink="light", fill=GOLD_TIP, font_size=14),
             dict(win=(452, 182, 832, 218), center=(642, 199),
                  word="※无论「未读跳过」如何设置，已读、未读都将被跳过。",
                  kind="clear", ink="light", fill=WHITE_TIP, font_size=13),
         ]),
    dict(name="config_frame_text", size=(1280, 644), kind="flat",
         font_size=18, gap=1, boost=1.35, fill=INK_BROWN,
         units=_grid([
             "普通场景窗口透明度", "事件场景窗口透明度", "已读颜色设置",
             "文字显示速度", "自动播放显示速度", "自动播放选项后",
             "跳过播放选项后", "跳过速度", "未读跳过",
         ], FRAME_COLS, FRAME_ROWS_TEXT)),
    # config_check_box：3 列 × 16 行白字长清单，红框在 x202..237 / 402..437（禁改）
    # 实测：紫色空框在 x0..39、红色勾选框在 x202..237 / 402..437，都是禁改装饰。
    # 首版窗口从 x8 起把紫框一起清掉；现收紧到 x46 起、右沿 200/400/598，
    # 透明底白字走整窗清 alpha（该区域本来就没有不透明底板，回填反而造色板）。
    dict(name="config_check_box", size=(600, 448), kind="clear",
         font_size=15, gap=0, boost=1.30, fill=INK_WHITE,
         units=_grid([
             "行动决定", "熟练度分配", "道具使用", "重新战斗",
             "存档", "读档", "快速存档", "快速读档",
             "覆盖数据", "删除数据", "语音登记", "语音删除",
             "恢复默认设置", "返回标题", "退出游戏", "其他",
         ], [(46, 200), (246, 400), (446, 598)],
             [(1, 23), (31, 51), (60, 80), (87, 107), (115, 134),
              (145, 163), (171, 191), (201, 219), (228, 248), (256, 275),
              (283, 303), (311, 330), (339, 360), (367, 388),
              (396, 416), (424, 444)], axis="row", ink="light")),

    # ---------------------------------------------------------------- C 组：popup 4 列 × 8 行
    # 纸底浅米带纹理；四列状态字色不同（禁用灰 / 深灰 / 红 / 亮红），逐列分别给色
    # 实测四列状态：禁用灰 / 深灰 / 红字带白描边 / 亮红字带白描边。
    # 前两列是暗字（flat）；后两列是彩字，用 colored 判据 + 扩散补底，
    # 否则会留下整圈白色描边字影和白色亮块补丁。
    dict(name="common_popup_parts", size=(612, 320), kind="flat",
         font_size=17, gap=0, boost=1.30, fill=INK_PAPER_DARK,
         col_fills=[(178, 172, 158), (58, 54, 52), (234, 0, 33), (255, 76, 102)],
         units=_grid([
             "存档", "读档", "快速存档", "快速读档",
             "设置", "返回标题", "退出游戏", "返回",
         ], [(14, 150), (166, 298), (315, 450), (468, 602)],
             [(5, 30), (39, 64), (72, 99), (106, 133),
              (141, 166), (175, 199), (207, 234), (243, 268)],
             axis="row")),
    # 白描边比红字核宽 3~6px，窗口必须外扩；但中文仍按原列/行中心归位，
    # 否则中文会随扩窗一起偏移。

    # file_index：右侧 LOAD/SAVE 胶囊各 3 行；左侧数字菱形与圆形箭头全禁改
    dict(name="file_index", size=(856, 384), kind="diffuse",
         font_size=19, gap=1, boost=1.30, fill=INK_GOLD,
         units=[
             dict(win=(742, 3, 850, 37), center=(796, 20), word="读档"),
             dict(win=(742, 41, 850, 75), center=(796, 58), word="读档"),
             dict(win=(742, 79, 850, 113), center=(796, 96), word="读档"),
             dict(win=(742, 119, 850, 153), center=(796, 136), word="存档"),
             dict(win=(742, 157, 850, 191), center=(796, 174), word="存档"),
             dict(win=(742, 195, 850, 229), center=(796, 212), word="存档"),
         ]),

    # ---------------------------------------------------------------- E 组：CHANGE 橘色胶带
    # CHANGE 是白字 + 一圈橙色立体投影，投影比白核宽 8~12px。
    # 只擦白核会留下 CH..GE 橙影；用「白字 ∪ 橙影」联合判据，
    # 再按列插值从上下沿真实像素重建水平横条渐变。
    dict(name="file_save_parts", size=(632, 493), kind="band",
         font_size=25, gap=1, boost=1.25, fill=(255, 250, 240),
         units=[dict(win=(0, 350, 158, 388), center=(79, 368), word="切换",
                     ink="band_all", dilate=3)]),
    dict(name="file_load_parts", size=(632, 493), kind="band",
         font_size=25, gap=1, boost=1.25, fill=(255, 250, 240),
         units=[dict(win=(0, 350, 158, 388), center=(79, 368), word="切换",
                     ink="band_all", dilate=3)]),

    # ---------------------------------------------------------------- F 组：鉴赏页 / MUTE
    dict(name="extra_music_parts", size=(658, 517), kind="flat",
         font_size=19, gap=1, boost=1.35, fill=INK_BROWN,
         units=[
             dict(win=(95, 31, 260, 58), center=(177, 44.5), word="操作"),
             dict(win=(430, 31, 580, 58), center=(505, 44.5), word="音量"),
             dict(win=(180, 66, 380, 93), center=(280, 79.5), word="音乐列表"),
         ]),
    # 实测：标签是浅金字 [219,185,104] 压在透明底上（窗内 alpha=0 占多数），
    # 不是深字。首版 flat 暗差判据擦除仅 50px，中文还写成深棕看不见。
    # 走整窗清 alpha；窗口左沿收紧避开 x≈10..30 / x≈510..530 的花形装饰。
    # 底部两条标签走 clear（透明底金字）；上方 3 行按钮阵列的 ALL / PLAY LIST
    # 共 21 个独立文字单元走 darkfill（实心圆底，只擦笔画不挖洞）。
    # 底部两条标签：旧版 clear 把 256×25 整块清成透明，连 y331/y360 两条
    # 贯穿金线一起挖断。现只擦金字笔画（透明底直接 alpha=0），金线在框外。
    dict(name="extra_voice_parts", size=(1176, 418), kind="glyph",
         font_size=17, gap=1, boost=1.30, fill=GOLD_TIP,
         units=[
             dict(win=(34, 330, 290, 355), band=(30, 333, 288, 353),
                  center=(162, 343), word="收藏语音", kind="glyph",
                  ink="labelgold", transparent=True, dilate=1,
                  clip_pad=2, boost=1.45, fill=GOLD_TIP, font_size=19),
             dict(win=(536, 330, 700, 355), band=(532, 333, 698, 353),
                  center=(618, 343), word="播放列表", kind="glyph",
                  ink="labelgold", transparent=True, dilate=1,
                  clip_pad=2, boost=1.45, fill=GOLD_TIP, font_size=19),
         ] + VOICE_BUTTONS),
    dict(name="config_parts", size=(286, 323), kind="clear",
         font_size=14, gap=0, boost=1.35, fill=INK_GOLD,
         units=_grid(["静音"], [(176, 219), (220, 264)],
                     [(0, 12), (44, 56), (88, 100)], axis="row")),

    # ---------------------------------------------------------------- G 组：确认框 3 组
    dict(name="common_confirm_parts", size=(1258, 400), kind="flat",
         font_size=18, gap=1, boost=1.35, fill=INK_BROWN,
         units=[dict(win=(78, 360, 362, 393), center=(220, 376.5), word="下次不再确认"),
                dict(win=(446, 360, 730, 393), center=(588, 376.5), word="下次不再确认"),
                dict(win=(814, 360, 1098, 393), center=(956, 376.5), word="下次不再确认")]),

    # ---------------------------------------------------------------- 2026-11-16 追加
    # 人名图：10 行 × 2 列同名，白字粉光压在深色花卉纹 + 角色头像上。
    dict(name="config_frame_voice", size=(628, 1780), kind="diffuse",
         font_size=22, gap=1, boost=1.25, fill=(255, 245, 245),
         units=_voice_name_cells()),
    # 发光菱形：只重绘字形像素，不铺整窗平色（内框金线必须完整）。
    dict(name="config_index", size=(842, 342), kind="glyph",
         font_size=19, gap=1, boost=1.45, fill=(219, 185, 104),
         units=_index_cells()),
]

# ---------------------------------------------------------------- 透明底多状态发光字
# title_menu_text：4 行 × 7 词；行 0 禁用暗态 / 行 1 金字 / 行 2 白字黄光 / 行 3 粉字粉光
# 每行大字下方的日文假名副标题按既定口径保留原文，清除窗只罩大字带。
TITLE_WORDS = [("CONTINUE", "继续游戏", 95.5),
               ("NEW GAME", "开始游戏", 285.5),
               ("LOAD", "读取存档", 430.5),
               ("CONFIG", "环境设置", 551.0),
               ("DOMINATION", "征服模式", 735.5),
               ("EXTRA", "额外内容", 916.5),
               ("QUIT", "退出游戏", 1040.0)]
# 【方法文档 3.2 的正解】本图与第一组 menu_button 同构：每格上方英文发光大字、
# 下方一行日文假名小字，两者的辉光在 y 上**连成一片、没有透明间隙**。
# 不能靠「按 y 切成两段 + 整行清 alpha」处理：大字带下沿的 3~4 行既是大字光晕
# 尾部、又是日文小字的上沿光晕，切掉后中文 fade 又压到 0，就出现一条透明黑带，
# 目视即「日文被遮挡」。逐 y 实测（原图非透明像素数）：
#   行1 y86..89 差 815 / 行2 y138..141 差 3969 / 行3 y194..197 差 3970
#   行0 只差 109（暗态无强光晕）→ 正好对应「第一行正常、后三行被遮挡」。
# 正解：把 clear 窗下沿**提到日文上沿光晕起点之前**，让这段光晕整段留在
# strict_keep 硬禁区里逐像素还原；中文贴片 clip 同步收窄、光晕在下沿淡出。
# 大字笔画实测到 y135（行2）/ y191（行3）为止，y138..141 是纯光晕（逐 y 约
# 900/1101 px 横向贯穿，不是笔画），保留不会残留英文字形。
TITLE_ROWS = [
    dict(y0=4, y1=28, cy=15.0, fill=(150, 138, 118), glow=(90, 80, 60),
         gain=0.35, boost=1.15),
    dict(y0=56, y1=85, cy=68.0, fill=(219, 185, 104), glow=(150, 110, 40),
         gain=0.55, boost=1.20),
    dict(y0=112, y1=140, cy=123.0, fill=(255, 255, 255), glow=(198, 151, 23),
         gain=1.05, boost=1.30),
    dict(y0=164, y1=196, cy=177.0, fill=(255, 235, 238), glow=(255, 103, 121),
         gain=1.05, boost=1.30),
]

GLOW_GROUPS = [
    dict(name="title_menu_text", size=(1101, 220),
         clear_x=(0, 1101), rows=TITLE_ROWS, words=TITLE_WORDS,
         font_size=22, gap=1,
         # 【硬禁区上沿必须 == 大字带 clear 下沿，中间不留 1px 三不管区间】
         # 逐 y 实测日文上沿光晕：行1 y86 / 行2 y138 / 行3 y194。旧版 clear
         # 到 88/142/198 而 keep 从 88/142/198 起，y86..87 / 138..141 /
         # 194..197 既被清成透明、又不在还原区、中文 fade 又压到 0 → 一条
         # 透明黑带切断日文上沿，就是用户说的「日文被遮挡」。
         # 硬禁区从 clear 下沿起，一直覆盖到下一行大字上沿：日文小字及其
         # **上沿光晕峰值带**（实测 y136/137、y191..193）整段逐像素还原。
         # keep 起点 = 日文小字**笔画**上沿（y140 / y196），把光晕峰值带
         # y136..139 / y191..195 留给中文光晕覆盖，避免出现一条孤立的亮线。
         keep=[(0, 28, 1101, 56), (0, 85, 1101, 112),
               (0, 140, 1101, 164), (0, 196, 1101, 220)],
         clip_rows=True, strict_keep=True,
         # 【整块清 0，不做任何整行补底】大字辉光与日文辉光连成一片，
         # 没有方法文档 3.2 前提里「辉光已衰减到 0 的透明区」可羽化。
         # 试过三种补底都翻车：下沿羽化回原图 → 混回英文笔画（字影）；
         # 逐行中位铺满 → 实心色带；下沿 4 行铺光晕 → 1:1 下一条贯穿
         # 全宽的水平细线（原本透明处新增 12403 个不透明像素）。
         # 正解：大字带清 0 后完全交给中文贴片自带的光晕重新照亮，
         # keep 区逐像素保护日文小字（含上沿光晕），两者自然接上。
         # 不再 fade：clip 已把中文严格框在大字带内；fade 反而压掉
         # 中文光晕下沿，与日文上沿光晕断链。
         fade_bottom=0),
    # tutorial_help_p：BACK 3 态（左侧 x4..98），数字 0123456789 与圆形箭头禁改
    dict(name="tutorial_help_p", size=(341, 274),
         clear_x=(2, 100),
         rows=[dict(y0=145, y1=180, cy=162.5, fill=(219, 185, 104),
                    glow=(150, 110, 40), gain=0.55, boost=1.20),
               dict(y0=185, y1=222, cy=203.5, fill=(255, 255, 255),
                    glow=(198, 151, 23), gain=1.05, boost=1.30),
               dict(y0=228, y1=266, cy=247.0, fill=(255, 235, 238),
                    glow=(255, 103, 121), gain=1.05, boost=1.30)],
         words=[("BACK", "返回", 51.0)], font_size=22, gap=1,
         keep=[(100, 140, 341, 274), (0, 0, 341, 140)]),
    # extra_visual_parts：BACK 3 态横排（金 / 白 / 粉），左侧数字与箭头禁改
    # BACK 三态是横排（不是竖排三行），每列一个状态色：金 / 白+黄光 / 粉+粉光。
    # 首版把三列当成三行去套光晕，做成空心描边小字。现按列给各自光晕色。
    dict(name="extra_visual_parts", size=(1280, 131),
         clear_x=(980, 1280),
         rows=[dict(y0=82, y1=122, cy=102.0, fill=(255, 250, 240),
                    glow=(198, 151, 23), gain=0.95, boost=1.35)],
         words=[("BACK0", "返回", 1027.0), ("BACK1", "返回", 1127.5),
                ("BACK2", "返回", 1228.5)],
         font_size=22, gap=1,
         word_fills=[(219, 185, 104), (255, 255, 255), (255, 235, 238)],
         word_glows=[(150, 110, 40), (198, 151, 23), (255, 103, 121)],
         keep=[(0, 0, 980, 131)]),
]

# tutorial_help_p 顶部 HELP 是红底花卉纹金字，走第一组木牌路线
# 实测：HELP 衬线大字 y20..58 且带深色描边；日文「-ヘルプ-」在 y67..83，
# 按既定口径保留原文。首版窗口罩到 y84 把日文一起擦了，且只擦金字笔画
# 留下整圈虚线描边。现收窄窗口、整块清底再扩散补回红底花卉纹。
HELP_TITLE = dict(name="tutorial_help_p", word="帮助",
                  win=(50, 16, 296, 60), center=(173.0, 38.0),
                  font_size=34,
                  keep=[(0, 60, 341, 140)])

ALL_NAMES += [
    # C 组
    "common_popup_parts", "file_index", "title_menu_text", "tutorial_help_p",
    # D 组
    "config_frame_sound", "config_frame_system", "config_frame_manual",
    "config_frame_text", "config_check_box",
    # E 组
    "file_save_parts", "file_load_parts",
    # F 组
    "extra_music_parts", "extra_visual_parts", "extra_voice_parts", "config_parts",
    # G 组
    "common_confirm_parts",
    # 2026-11-16 追加：人名已定稿 / 发光字按普通工艺重做
    "config_frame_voice", "config_index",
]

# popup 原始列/行中心（扩窗前的文字墨迹中心，中文按此归位）
POPUP_CX = [82.5, 232.0, 385.0, 537.0]
POPUP_CY = [17.5, 51.5, 85.5, 119.5, 153.5, 187.0, 220.5, 255.5]

# 多状态列字色展开：每列独立给色，逐格落位时各用各的
for _c in CELLS:
    if "col_fills" in _c:
        _n = len(_c["col_fills"])
        for _i, _u in enumerate(_c["units"]):
            _ci = _i % _n
            _u["fill"] = _c["col_fills"][_ci]
            if _c["name"] == "common_popup_parts":
                # 中文仍按原列/行中心归位（窗口为覆盖白描边外扩过）
                _u["center"] = (POPUP_CX[_ci], POPUP_CY[_i // _n])
                if _ci >= 2:
                    # 红/亮红字带白描边：联合判据擦净整圈描边，
                    # 再用窗内干净纸色中位回填（扩散会把白描边当样本摊出亮块）
                    _u["ink"] = "colored_rim"
                    _u["kind"] = "flat"
                    _u["dilate"] = 3

# 译名清单（D 组框架图与 G 组确认框为起草译文，交付附清单供用户过目）
JP_DRAFT = {
    "マスターボリューム": "主音量", "BGM": "背景音乐", "BGV": "背景语音",
    "環境音": "环境音", "Hシーン効果音": "场景音效", "効果音": "音效",
    "システム効果音": "系统音效", "音声": "语音",
    "クリック時のボイス停止": "点击时停止语音",
    "画面サイズ": "画面尺寸", "セーブ終了後": "存档结束后",
    "カーソル自動追尾": "光标自动跟随", "カーソル自動消去": "光标自动隐藏",
    "報告メッセージ": "报告消息",
    "フォント・非アクティブ動作等の設定": "字体及非活动状态设置",
    "右クリック・Esc設定": "右键・Esc 设置", "確認ダイアログ": "确认对话框",
    "メッセージウィンドウ消去": "隐藏文本框", "バックログ": "回顾记录",
    "メッセージ送り": "推进文本", "キャンセル・戻る": "取消・返回",
    "特殊スキップ": "特殊跳过", "バトル早送り": "战斗快进",
    "通常シーンウィンドウの不透明度": "普通场景窗口透明度",
    "イベントシーンウィンドウの不透明度": "事件场景窗口透明度",
    "既読カラー設定": "已读颜色设置", "メッセージ表示速度": "文字显示速度",
    "オート再生表示速度": "自动播放显示速度", "オート再生選択肢後": "自动播放选项后",
    "スキップ再生選択肢後": "跳过播放选项后", "スキップスピード": "跳过速度",
    "未読スキップ": "未读跳过",
    "行動決定": "行动决定", "練度の割り振り": "熟练度分配", "薬の使用": "道具使用",
    "戦闘やり直し": "重新战斗", "セーブ": "存档", "ロード": "读档",
    "クイックセーブ": "快速存档", "クイックロード": "快速读档",
    "データの上書き": "覆盖数据", "データの消去": "删除数据",
    "ボイス登録": "语音登记", "ボイス消去": "语音删除",
    "設定を初期化": "恢复默认设置", "タイトルに戻る": "返回标题",
    "ゲーム終了": "退出游戏", "その他": "其他",
    "次回から確認しない": "下次不再确认",
}
