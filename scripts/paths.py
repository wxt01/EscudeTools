#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paths.py —— 统一的「项目目录」解析

所有脚本共用，避免任何硬编码路径。解析顺序：

  1. 命令行参数 --project <目录>
  2. 环境变量 HANHUA_PROJECT
  3. 从当前目录逐级向上找 project.json
  4. 从本脚本所在目录逐级向上找 project.json
  5. 都没有 → 用当前目录

项目结构（由 prepare.py 自动创建）：

  <项目>/
  ├── project.json        配置（game_dir / engine_tool / bins / font / data）
  ├── 0_backup/           原版资源包备份
  ├── 1_unpack/           解包产物 output/（script/ data/ gfx/）
  ├── 2_json_jp/          导出的日文 JSON（每脚本一个文件）
  ├── 3_json_cn/          译文 JSONL
  ├── 4_pristine/         干净底版（script.db、db_*.db、gfx/font/ja_jp、gfx/sys）
  ├── 5_build/            构建中间产物（cmap.json、pages/）
  └── 6_release/          成品资源包
"""

import json
import os
import sys

DEFAULT_DIRS = {
    "backup": "0_backup",
    "unpack": "1_unpack",
    "json_jp": "2_json_jp",
    "json_cn": "3_json_cn",
    "pristine": "4_pristine",
    "build": "5_build",
    "release": "6_release",
}

DEFAULT_CFG = {
    "game_dir": "",
    "engine_tool": "",
    "bins": ["script.bin", "data.bin", "gfx.bin"],
    "dirs": dict(DEFAULT_DIRS),
    "font": {"face": r"C:\Windows\Fonts\msyh.ttc", "index": 0, "max_page": 83},
    "data": {
        "name_table": "登場人物_01",
        "name_col": "名前_44",
        "id_col": "キャラID_14",
        "ui_table": "TEXT_00",
        "ui_id_col": "ID_44",
        "ui_text_col": "Text_44",
    },
}


def _walk_up(start, name="project.json", limit=8):
    d = os.path.abspath(start)
    for _ in range(limit):
        if os.path.isfile(os.path.join(d, name)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def find_root(cli=None):
    """定位项目根目录"""
    if cli:
        return os.path.abspath(cli)
    env = os.environ.get("HANHUA_PROJECT", "").strip()
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    hit = _walk_up(os.getcwd())
    if hit:
        return hit
    here = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
    hit = _walk_up(here)
    if hit:
        return hit
    return os.path.abspath(os.getcwd())


def load_cfg(root):
    """读取 project.json，缺字段用默认值补齐"""
    cfg = json.loads(json.dumps(DEFAULT_CFG))  # 深拷贝
    p = os.path.join(root, "project.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def dirs(root=None, cli=None):
    """返回 {名称: 绝对路径}，并附带 root / cfg"""
    root = root or find_root(cli)
    cfg = load_cfg(root)
    d = {k: os.path.join(root, v) for k, v in cfg["dirs"].items()}
    d["root"] = root
    d["cfg"] = cfg
    return d


def ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


def need_file(path, hint=""):
    if not os.path.exists(path):
        msg = f"缺少文件：{path}"
        if hint:
            msg += f"\n  {hint}"
        sys.exit(msg)
    return path


def engine_tool(d):
    """取引擎工具路径并校验"""
    p = (d["cfg"].get("engine_tool") or "").strip()
    if not p:
        sys.exit("project.json 里没有配置 engine_tool，见 vendor/README.md")
    if not os.path.isfile(p):
        sys.exit(f"engine_tool 指向的文件不存在：{p}")
    return p


def add_project_arg(ap):
    ap.add_argument("--project", default="", help="项目目录（含 project.json）；默认自动向上查找")
    return ap


if __name__ == "__main__":
    d = dirs()
    print("项目根：", d["root"])
    for k in DEFAULT_DIRS:
        mark = "✓" if os.path.isdir(d[k]) else "·"
        print(f"  {mark} {k:<9} {d[k]}")
