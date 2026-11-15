# -*- coding: utf-8 -*-
"""
_work.py —— 界面图工作区的统一解析（所有 config_*.py 都从这里取路径）

解析顺序：
  1. 环境变量 UI_WORK_ROOT（手动指定，最高优先）
  2. 当前项目（向上找 project.json）下的 7_图片/
  3. 旧布局兼容：工具包上一级的 12_界面图工作区/
  4. 工具包目录内自建（单独下载本工具包时）

为什么不再各写一份：多游戏并存时，工作区必须跟着"当前项目"走，
否则给 A 游戏做的图会跑到 B 游戏的工作区里，或落回工具包。
"""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _project_root() -> Path | None:
    env = os.environ.get("HANHUA_PROJECT", "").strip()
    if env and (Path(env) / "project.json").is_file():
        return Path(env)
    d = Path(os.getcwd())
    for _ in range(10):
        if (d / "project.json").is_file():
            return d
        if d.parent == d:
            break
        d = d.parent
    return None


def resolve() -> Path:
    env = os.environ.get("UI_WORK_ROOT", "").strip()
    if env:
        return Path(env)
    root = _project_root()
    if root:
        return root / "7_图片"
    old = HERE.parent / "12_界面图工作区"
    if old.is_dir():
        return old
    return HERE / "_工作区"


ROOT = resolve()
SRC_DIR = ROOT / "待做原图"
DST_DIR = ROOT / "待交付"
WORK_DIR = ROOT / "工作输出"

for _p in (ROOT, SRC_DIR, DST_DIR, WORK_DIR):
    _p.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    print("工作区：", ROOT)
    print("  待做原图 ->", SRC_DIR)
    print("  待交付   ->", DST_DIR)
    print("  工作输出 ->", WORK_DIR)
