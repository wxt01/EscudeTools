# -*- coding: utf-8 -*-
"""七张成品的交付自检：结构不变量 + 关键区域逐像素保护 + 文字齐全"""
import numpy as np
from PIL import Image
import config_pages as CP
import config_frames as CF

OK = 0
BAD = 0


def chk(name, cond, detail=""):
    global OK, BAD
    tag = "PASS" if cond else "FAIL"
    if cond:
        OK += 1
    else:
        BAD += 1
    print("  [%s] %-52s %s" % (tag, name, detail))


def load(p):
    return np.array(Image.open(p).convert("RGBA"))


print("=" * 78)
print("设置页三张")
print("=" * 78)
for name, size in [("button", CP.BUTTON_SIZE), ("index", CP.INDEX_SIZE),
                   ("title", CP.TITLE_SIZE)]:
    s = load(CP.SRC_DIR / (name + ".png"))
    d = load(CP.DST_DIR / (name + ".png"))
    chk(name + " 尺寸/通道", s.shape == d.shape and d.shape[2] == 4, str(d.shape))
    chk(name + " 尺寸等于原图", tuple(d.shape[:2][::-1]) == size, str(size))

# button：英文大字带之外（其实全图只有小字区能动）检查行状态底色保留
s, d = load(CP.SRC_DIR / "button.png"), load(CP.DST_DIR / "button.png")
# 新中文笔画与原英文位置不同，本来就会写在原 mask 之外。
# 正确口径：显著改动必须落在「每格每行的文字矩形」内，
# 英文大字 / 按钮边框 / 格间黑缝一个像素都不能动。
sig = (np.abs(s.astype(int) - d.astype(int)).max(axis=2) > 40)
allowed = np.zeros(s.shape[:2], dtype=bool)
for y0, y1 in CP.BUTTON_ROWS:
    for a, b in CP.BUTTON_WORD_SPANS:
        allowed[y0 + 5:y0 + 37, max(0, a - 12):min(s.shape[1], b + 12)] = True
chk("button 改动全在文字矩形内", int((sig & ~allowed).sum()) == 0,
    "越界 %d" % int((sig & ~allowed).sum()))
for r, (y0, y1) in enumerate(CP.BUTTON_ROWS):
    reg = d[y0:y1, :, :3].mean(axis=2)
    chk("button 第%d行 有中文白/红字" % (r + 1),
        int((reg > 150).sum()) > 150, "%d 亮像素" % int((reg > 150).sum()))

# ★ 逐格确认旧英文确实被擦过。早期按「第 3 行 = 深红字」写死阈值，
#   同行最后一格其实是青绿底白字，整格 mask=0、英文完整保留就叠了中文。
#   只检查「整图有没有字」发现不了，必须逐格数 mask 覆盖量。
bmask = np.load(str(CP.WORK_DIR / "button_mask.npy"))
cell_counts = [int(bmask[y0:y1, a:b].sum())
               for y0, y1 in CP.BUTTON_ROWS
               for a, b in CP.BUTTON_WORD_SPANS]
chk("button 30 格旧英文全部被擦除", min(cell_counts) > 300,
    "最少一格 %d 像素（漏擦时接近 0）" % min(cell_counts))

# index：三行齐全、第三行第6格空白
s, d = load(CP.SRC_DIR / "index.png"), load(CP.DST_DIR / "index.png")
for r, (y0, y1) in enumerate(CP.INDEX_ROWS):
    a = d[y0:y1, :, 3]
    chk("index 第%d行 有发光文字" % (r + 1), int((a > 150).sum()) > 300,
        "%d 实像素" % int((a > 150).sum()))
x0, x1 = CP.INDEX_SPANS[5]
chk("index 第3行 RESET 格保持空白", int(d[96:144, x0:x1, 3].max()) == 0,
    "alpha max %d" % int(d[96:144, x0:x1, 3].max()))

# 红态不能出现「实心下划线」。原版第三行是柔和红色外发光（实测光晕 alpha
# 峰值 ~120，上下渐隐），早期版本把发光下沿误判成红线、额外画了 2px 实心
# 红矩形，被用户当场指出。这里把该反馈固化成回归判据。
def longest_red_run(arr):
    m = ((arr[:, :, 0] > 230) & (arr[:, :, 1] < 70) &
         (arr[:, :, 2] < 60) & (arr[:, :, 3] > 200))
    best = 0
    for row in m[28:46]:
        run = cur = 0
        for v in row:
            cur = cur + 1 if v else 0
            run = max(run, cur)
        best = max(best, run)
    return best


r2 = d[96:144]
chk("index 第3行 无实心红色下划线", longest_red_run(r2) < 20,
    "最长连续红实线 %d px（原版 %d px）" %
    (longest_red_run(r2), longest_red_run(load(CP.SRC_DIR / "index.png")[96:144])))

# title：木牌外围（红绳、边框）未动
s, d = load(CP.SRC_DIR / "title.png"), load(CP.DST_DIR / "title.png")
sig = (np.abs(s.astype(int) - d.astype(int)).max(axis=2) > 40)
xa, xb, ya, yb = CP.TITLE_TEXT_SPAN
allowed = np.zeros(s.shape[:2], dtype=bool)
allowed[max(0, ya - 4):min(s.shape[0], yb + 4),
        max(0, xa - 4):min(s.shape[1], xb + 4)] = True
chk("title 改动全在木牌文字区内", int((sig & ~allowed).sum()) == 0,
    "越界 %d" % int((sig & ~allowed).sum()))

print("=" * 78)
print("框架图四张")
print("=" * 78)
for name, cfg in CF.FRAMES.items():
    s = load(CF.SRC_DIR / (name + ".png"))
    d = load(CF.DST_DIR / (name + ".png"))
    H, W = s.shape[:2]
    chk(name + " 尺寸/通道", s.shape == d.shape, str(d.shape))

    # 允许改动区 = 所有清除窗口的并集（含 4px 外扩）
    allow = np.zeros((H, W), dtype=bool)
    for x0, x1, y0, y1 in cfg["clears"]:
        allow[y0:min(H, y1 + 2), max(0, x0 - 8):min(W, x1 + 8)] = True
    changed = (s != d).any(axis=2)
    chk(name + " 改动不越出清除窗口", int((changed & ~allow).sum()) == 0,
        "越界 %d" % int((changed & ~allow).sum()))

    # 笔触带用配置里的实测 y 区间，不能从 clear 推（键位行紧跟标题会被误算）
    brush = np.zeros((H, W), dtype=bool)
    for ya, yb in CF.BRUSH_BANDS[name]:
        brush[ya:yb, :] = True
    keep = brush & (s[:, :, 3] > 0)
    chk(name + " 青色水彩笔触逐像素保留",
        bool((s[keep] == d[keep]).all()), "%d 像素" % int(keep.sum()))

    # 清除窗口内不应残留原图的白色日文：非新图层像素 alpha 必须为 0
    # 新图层颜色只有这几类，用 RGB 距离粗筛异常残留
    inner = np.zeros((H, W), dtype=bool)
    for x0, x1, y0, y1 in cfg["clears"]:
        inner[y0:y1, x0:x1] = True
    vis = inner & (d[:, :, 3] > 30)
    white_old = (s[:, :, 0] > 180) & (s[:, :, 1] > 180) & (s[:, :, 2] > 180)
    # 中文字也是白的，所以只统计「原白字位置但成品仍亮且不在新字附近」难判；
    # 结构保证清除窗口 alpha 先置 0，这里验证清除确实执行过
    cleared = inner & (s[:, :, 3] > 30) & (d[:, :, 3] == 0)
    chk(name + " 原文字位置确实被清空", int(cleared.sum()) > 200,
        "%d 像素" % int(cleared.sum()))
    chk(name + " 新文字已写入", int((vis & (d[:, :, :3].mean(axis=2) > 140)).sum()) > 200,
        "%d 亮像素" % int((vis & (d[:, :, :3].mean(axis=2) > 140)).sum()))

# 特殊：frame_sound 的 BGM / BGV 两格逐像素保留
s, d = load(CF.SRC_DIR / "frame_sound.png"), load(CF.DST_DIR / "frame_sound.png")
for label, ci, y0, y1 in [("BGM", 1, 6, 37), ("BGV", 0, 133, 164)]:
    x0, x1, _ = CF.COLS[ci]
    chk("frame_sound " + label + " 格完全未改动",
        bool((s[y0:y1, x0:x1] == d[y0:y1, x0:x1]).all()))

# 特殊：frame_text 顶部照片与底部黑框未动
s, d = load(CF.SRC_DIR / "frame_text.png"), load(CF.DST_DIR / "frame_text.png")
chk("frame_text 顶部照片未改动", bool((s[:115] == d[:115]).all()))
chk("frame_text 底部黑框未改动", bool((s[560:] == d[560:]).all()))

# 特殊：键名文案齐全
keys = ["Space", "Back Space", "Enter", "Esc", "Ctrl"]
texts = [t["text"] for t in CF.FRAMES["frame_manual"]["texts"]]
chk("frame_manual 五个键名全部写回", all(any(k in t for t in texts) for k in keys))
chk("frame_manual 定稿文案条数", len(texts) == 15, str(len(texts)))

print("=" * 78)
print("结果: %d 通过 / %d 失败" % (OK, BAD))
print("=" * 78)
raise SystemExit(1 if BAD else 0)
