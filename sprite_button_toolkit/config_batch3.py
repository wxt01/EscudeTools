# -*- coding: utf-8 -*-
"""
追加任务三：快捷栏 / 右键菜单 / 确认框 / 系统按钮 五张图的全部参数。

⚠️ 这些坐标、颜色、字号都是对这五张图**实测**的结果，不是通用常数。
   换图请照《汉化方法与思路.md》第 3 节的流程重新量。

本批图与之前最大的区别：
  * 全部是「透明背景 + 文字/图标」，没有底板 → 擦字 = 把矩形清成 alpha=0，
    不需要 inpaint / 扩散补底 / 纹理回填（那套是 button.png / title.png 用的）。
  * 多状态列里的**文字层往往是逐像素复制的**，差异只在图标颜色或辉光色。
    先做「列/行两两差分」确认这一点，能复用一套字形就别画 N 套。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_DIR = os.path.join(ROOT, "原图")
DST_DIR = os.path.join(ROOT, "交付成品放这里")
WORK_DIR = os.path.join(HERE, "_输出")
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(DST_DIR, exist_ok=True)


def find_font(kind):
    """kind='serif' 衬线（配原图拉丁衬线体/日文明朝体）
       kind='sans'  黑体（任务说明指定 popup_parts 用黑体系）"""
    cand = {
        "serif": [r"C:\Windows\Fonts\simsun.ttc",
                  "/usr/share/fonts/truetype/arphic/uming.ttc",
                  "/System/Library/Fonts/Songti.ttc"],
        "sans": [r"C:\Windows\Fonts\msyhbd.ttc",
                 r"C:\Windows\Fonts\msyh.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                 "/System/Library/Fonts/PingFang.ttc"],
        # 常规字重。粗黑体在这类「细斜体 + 柔光」图上会直接毁掉美术风格，
        # 别图省事一律用 msyhbd。本图拿它和宋体并排比过，最后选了宋体，
        # 这个候选留着是为了下次换图时有两个字重/字形可直接对照。
        "sans_light": [r"C:\Windows\Fonts\msyh.ttc",
                       "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                       "/System/Library/Fonts/PingFang.ttc"],
    }[kind]
    for p in cand:
        if os.path.exists(p):
            return p
    raise RuntimeError("找不到 %s 中文字体，请在 config_batch3.find_font 里补本机路径" % kind)


SERIF = find_font("serif")
SANS = find_font("sans")
SANS_LIGHT = find_font("sans_light")

# ================================================================ radio_button.png
# 585×217 = 3 列状态(青/亮青/金) × 7 行按钮。左侧圆形图标占 x 2..27(相对列)，
# 白字从 x=40 起左对齐。实测三列文字层逐像素几乎一致，差异只在图标颜色。
RADIO = dict(
    name="radio_button", size=(585, 217),
    col_w=195, cols=[0, 195, 390],
    rows=[(0, 31), (31, 62), (62, 93), (93, 124), (124, 155), (155, 186), (186, 217)],
    text_x=40,            # 相对列左界；图标右沿 27，留 13px 余量
    clear_x0=38,          # 清除区左界（不碰图标）
    words=["菜单", "设置", "回顾记录", "流程图", "自动播放", "跳过播放", "隐藏文本框"],
    font=SERIF, font_size=20, char_gap=1,
    text_rgb=(255, 255, 255),
    # 宋体细横画在 20px 下抗锯齿后 alpha 只有 ~120，合成到深底会显灰；
    # 文字层 alpha 乘这个系数把中间调推到 255，白字实像素才能追上原图。
    weight=1.75,
)

# ================================================================ check_box.png
# 606×450 = 3 列状态 × 15 行。方框图标 x 2..37(相对列)，白字从 x=49 起。
CHECK = dict(
    name="check_box", size=(606, 450),
    col_w=202, cols=[0, 202, 404],
    rows=[(i * 30, (i + 1) * 30) for i in range(15)],
    text_x=49, clear_x0=46,
    words=["存档", "读档", "快速存档", "快速读档", "覆盖数据", "删除数据",
           "收藏语音", "删除收藏", "返回上一选项", "前进下一选项", "场景跳转",
           "重置设置", "返回标题", "退出游戏", "其他"],
    font=SERIF, font_size=21, char_gap=1,
    text_rgb=(255, 255, 255), weight=1.75,
)

# ================================================================ popup_parts.png
# 864×686。实测是 **4 列状态 × 9 行**（任务说明只写了 8 项、x 0..155，
# 与文件不符；以实际文件为准）。四列 x 偏移 216，状态分别为：
#   0 暗褐禁用 / 1 米白字+深褐描边 / 2 红描边+白光 / 3 橙红描边+白光
# 列 2/3 每行左侧另有红色箭头（x 433..467 / 649..683），必须逐像素保留。
# y 0..43 是 FLOWCHART 行（说明表格未列，按同任务 radio_button 定稿译「流程图」）。
POPUP = dict(
    name="popup_parts", size=(864, 686),
    col_w=216, cols=[0, 216, 432, 648],
    # 每行 y 区间 = 原图 alpha>0 的连续段，直接整段清成透明，行间本来就是透明的
    rows=[(0, 44), (52, 88), (96, 132), (138, 176), (182, 220),
          (226, 264), (271, 308), (316, 352), (360, 396)],
    text_x=[50, 265, 481, 697],     # 各列文字左沿（相对全图）
    clear_x0=[45, 258, 475, 691],   # 清除区左界；列2/3 停在箭头右侧
    words=["流程图", "存档", "读档", "快速存档", "快速读档",
           "设置", "返回标题", "退出游戏", "返回"],

    # —— 返工（用户反馈：字变正了 / 太粗 / 红白关系反了）——
    # 原图是细斜体拉丁字，整行左下→右上约 6~8°（PCA 实测 -6.5°），
    # 字母本身也是斜体。中文用「逐字基线递升 + 整层斜切」两件事一起模拟：
    # 只加大 shear 会把方块字拉歪，只递升又会变成阶梯。
    # 原图是衬线斜体拉丁字。常规黑体试过，笔画太匀、太现代；
    # 宋体横细竖粗、末端有顿角，倾斜后和原图最贴。粗黑体 msyhbd 一律别用。
    font=SERIF, font_size=23, char_gap=4,
    rise=2.0,              # 每字比前一字抬高 px（基线上坡）
    shear=0.30,            # 字形斜体；旧的 0.16 实测质心斜率只有 -0.20，等于没斜
    # 左边距不写死：patch 左界 = clear_x0，文字起点 = text_x - clear_x0。
    # 斜切底部左移 5px、柔光 blur 4.2 向左扩散，都会被裁在清除区内部，
    # 既不切掉第一个字，也不把光漏到清除区外（outside_check 会抓）。

    # 原图 SAVE 行每列实测 alpha 分层（总 alpha 183k）：
    #   >200    n=289  细描边 —— 竟然是最实的一层，颜色随状态变化
    #   120~200 n=428  半透明字身（暖白/暖粉，不是纯白实心）
    #   30~120  n=675  暖白柔光
    # 旧版是实心白字(核心 901，3 倍) + 粗色边 + 几乎没有柔光(91)，
    # 所以又粗又不发光、红白观感也反了。现在：字身半透明、描边 1px、柔光给足。
    # 宋体比黑体细，同样的 gain 会偏淡，字身比黑体版再提一档
    body_gain=0.80,
    glow_rgb=(255, 241, 209),
    # 按原图分层扫描定半径与强度：原图光晕层 n=675 / 总 alpha 183k，
    # 宋体版第一遍只有 300 / 155k。半径 6.0 虽然数据同样达标，但会把
    # 字间 4px 空隙糊成一团雾板；改用「小半径 + 高强度」的等价组合
    # (5.0 / 2.8：光晕 662 / 总量 188k)，光贴笔画，字间仍透底。
    glow_blur=5.0, glow_gain=2.8,
    edge_alpha=1.0,
    # fill=字身色 / edge=1px 细描边色 / glow=柔光强度 / alpha=整层缩放
    # ★ 常态描边色直接抄原图实测中位 (69,55,52)；早先用 (36,22,24)
    #   比原图暗一截，把米白字身整个压成灰字。
    # 禁用态只靠柔光堆面积，字身 alpha 峰值必须 <120。
    styles=[
        dict(fill=(196, 179, 160), edge=None,         glow=0.50, alpha=0.55),
        dict(fill=(255, 245, 217), edge=(69, 55, 52), glow=1.00, alpha=0.90),
        dict(fill=(255, 226, 200), edge=(226, 8, 0),  glow=1.00, alpha=0.90),
        dict(fill=(255, 232, 205), edge=(250, 49, 0), glow=1.00, alpha=0.90),
    ],
)

# ================================================================ sys_quit / sys_back
# 实测三行 **alpha 完全相同**，只是辉光 RGB 不同；白字核心恒为纯白。
# 所以：一套字形 + 每行换一个辉光色，天然复现三行梯度。
SYS = dict(
    glow_rgb=[(6, 120, 140), (8, 221, 203), (78, 255, 240)],
    white=(255, 255, 255),
    font=SERIF, font_size=19, char_gap=0,
    # 4 字中文 × 19px = 76px，必须小于 83px 词格宽；22px 会溢出并串到相邻格。
    # 辉光用小半径高斯模糊，不用 MaxFilter 外扩：外扩会把汉字之间填满成青色矩形板。
    glow_blur=4.2, glow_gain=1.75, core_weight=1.40,
    rows=[(0, 38), (38, 76), (76, 114)],
)
# ⚠️ 对齐别用「词格几何中心」。实测原图 TITLE / QUIT / BACK 的墨迹中心是
#    44.5 / 129.5 / 208.0，而三格中心是 41.5 / 124.5 / 207.5 —— 按格居中会让
#    「返回标题」左 3px、「退出游戏」左 5px（用户明确指出）。
#    正确判据是「原字墨迹中心 ↔ 中文墨迹中心」，中心要逐格量原图，不要算格子。
SYS_QUIT = dict(name="sys_quit", size=(249, 114),
                spans=[(0, 83), (83, 166), (166, 249)],
                words=["返回标题", "退出游戏", "返回"],
                centers=[44.5, 129.5, 208.0])
SYS_BACK = dict(name="sys_back", size=(80, 114),
                spans=[(0, 80)], words=["返回"], centers=[39.0])
