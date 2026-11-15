# ui_image_toolkit · 界面图文字汉化子工具

> 主管线（解包 → 解脚本 → 翻译 → 字库 → 回封）见根目录 `README.md`；
> 接手流程与判型见 `docs\02-图片汉化-接手.md`。
> 本模块只处理「文字直接烧在 PNG 里」的界面图：从 `gfx` 解包产物处理，成品随 `gfx.bin` 回封，不经过译文数据库。

---

## 一、目录

```
ui_image_toolkit\
├── _work.py            ★ 工作区解析（所有 config_*.py 都从这里取路径）
├── config_batchN.py    每批图的几何、译名、字色（改参数优先改这里）
├── build_batchN.py     生成成品
├── verify_batchN.py    自检（窗口外 0 改动 / 旧字无残留 / 装饰逐像素保留）
├── compare_batchN.py   对照图 + 成品 md5 前后同源
├── _badprobeN.py       坏稿探针（故意做坏一份，确认自检拦得住）
├── repair.py           补底三法（纯色 / 渐变 / 从邻行取样）
├── texture.py          整行平移补底（**已弃用**，保留作反面参考）
├── verify_all.py       跨批总检
├── examples\           示例（不含任何游戏美术图）
│   └── menu_button_单图\  config / build2 / verify2 / compare / layout / inspect_sprite
└── 汉化方法与思路.md    ★ 规范版方法论：六组案例 + 46 条错误总表
```

## 二、工作区

所有工作材料**不在工具包里**，跟着当前游戏项目走：

```
<游戏>\7_图片\
├── 待做原图\   日文原版图（主对话交付）
├── 待交付\     成品 + 对照图
├── 工作输出\   npy 掩码、诊断图、临时图
├── 交付归档\   历史任务说明与旧成品
├── 探索脚本\   一次性探针（大部分已过期，需重写）
└── 回归基准\   调试用差异样本
```

解析顺序（`_work.py`）：`UI_WORK_ROOT` 环境变量 → 当前项目（向上找 `project.json`）的 `7_图片` → 旧布局 `12_界面图工作区` → 工具包内 `_工作区`。

`python _work.py` 可直接打印当前解析到的工作区。多游戏并存时**必须**在游戏文件夹里运行，否则会退回兜底目录。

## 三、批次一览

| 批次 | 对应图 | 状态 |
|---|---|---|
| 第一批（示例） | 标题按钮菜单 `menu_button` 4 状态 × 7 按钮 | ✅ 已交付，脚本在 `examples\` |
| 02 | 确认框、某按钮 | 已并入 03 / 04 |
| 03 | 设置页 `button` / `index` / `title` | ✅ 已交付 |
| 04 | 四张 `frame_*.png` | ✅ 已交付 |
| 05 | 设置页补充 | 已并入 03 |
| 06 | 存读档大标题、木牌 | ✅ 已交付（`max_ink` 口径修正） |
| 07 | 多页签、失败稿与 pass2 计划 | 部分交付，`pass2/` 为阻断稿 |

## 四、依赖与运行

- **用系统 Python**（FontTools / Pillow / numpy 齐全）：`D:\Program Files (x86)\Python314\python.exe`
- Doubao 环境 PATH 里的 `python` 是沙箱自带的精简版（无 fontTools），会 `ModuleNotFoundError`。
- 用法：在 `ui_image_toolkit\` 目录内 `python build_batchN.py`，或在游戏文件夹里带 `UI_WORK_ROOT` 运行。

## 五、红线

- `gfx\font\`（位图字库页）**一个像素都不能动**——那是文本汉化的字库。
- 示例目录只放脚本与说明，**不放任何游戏美术图**；工作区里的图永不入库、永不外传。
- 明确保留项（数字、图标、LOGO、音声人名）一字不碰。
- 环境里跑不了游戏，最终观感必须真人在游戏内验收。
