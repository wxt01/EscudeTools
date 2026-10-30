#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare.py —— 一键准备：备份 → 解包 → 解脚本 → 解数据库 → 提取 → 干净底版

用法：
  python prepare.py --project <项目目录>
  python prepare.py --project <项目目录> --game "D:\\Games\\XXX" --tool "D:\\Tools\\EscudeTools.exe"
  python prepare.py --project <项目目录> --force      # 已存在的产物重新生成

产物：
  0_backup/            原版资源包备份
  1_unpack/output/     解包结果（script/ data/ gfx/）+ script.db + db_*.db
  2_json_jp/           日文 JSON（每脚本一个，按剧情顺序）
  4_pristine/          干净底版（之后每次构建都从这里取，避免越改越脏）
  project.json         若不存在则按模板生成，并自动写入实测的最大字库页号
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (p.stdout or "") + (p.stderr or "")


def step(msg):
    print(f"\n=== {msg}")


def sjis_page(b):
    """两个字节 → 字库页号（引擎 put_char() 的算法）"""
    lead, trail = b[0], b[1]
    c0 = lead - (0x40 if lead >= 0xE0 else 0)
    c1 = trail - (1 if trail >= 0x80 else 0)
    page = (c0 - 0x80) * 2
    if c1 < 0x9E:
        page -= 1
    return page


def max_used_page(json_dir):
    """扫描日文原文，返回实际用到的最大字库页号（决定占位字能落在哪些页）"""
    top = 0
    for fn in os.listdir(json_dir):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(json_dir, fn), encoding="utf-8") as f:
            items = json.load(f)
        for it in items:
            for ch in it.get("jp") or "":
                try:
                    b = ch.encode("cp932")
                except UnicodeEncodeError:
                    continue
                if len(b) == 2:
                    top = max(top, sjis_page(b))
    return top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="项目目录")
    ap.add_argument("--game", default="", help="日文原版游戏目录")
    ap.add_argument("--tool", default="", help="解包工具完整路径")
    ap.add_argument("--force", action="store_true", help="已存在的产物重新生成")
    args = ap.parse_args()

    root = os.path.abspath(args.project)
    os.makedirs(root, exist_ok=True)
    d = paths.dirs(root)
    cfg = d["cfg"]

    if args.game:
        cfg["game_dir"] = os.path.abspath(args.game)
    if args.tool:
        cfg["engine_tool"] = os.path.abspath(args.tool)

    # ---------- 0. 配置 ----------
    step("项目配置")
    if not cfg.get("game_dir") or not os.path.isdir(cfg["game_dir"]):
        sys.exit("缺少 game_dir：在 project.json 里填写游戏目录，或用 --game 指定")
    if not cfg.get("engine_tool") or not os.path.isfile(cfg["engine_tool"]):
        sys.exit("缺少 engine_tool：填写解包工具路径，或用 --tool 指定")
    cfg_path = os.path.join(root, "project.json")
    if not os.path.isfile(cfg_path):
        tpl = os.path.join(os.path.dirname(HERE), "project.example.json")
        if os.path.isfile(tpl):
            with open(tpl, encoding="utf-8") as f:
                base = json.load(f)
            base.update({k: v for k, v in cfg.items() if k != "dirs"})
            cfg = base
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"  已生成 {cfg_path}")
    else:
        with open(cfg_path, encoding="utf-8") as f:
            cur = json.load(f)
        cur.update({"game_dir": cfg["game_dir"], "engine_tool": cfg["engine_tool"]})
        cfg = cur
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    tool = cfg["engine_tool"]
    game = cfg["game_dir"]
    bins = cfg.get("bins") or ["script.bin", "data.bin", "gfx.bin"]
    print(f"  游戏目录 {game}")
    print(f"  引擎工具 {tool}")

    for k in ("backup", "unpack", "json_jp", "json_cn", "pristine", "build", "release"):
        paths.ensure(d[k])

    # ---------- 1. 备份 ----------
    step("备份原版资源包")
    for b in bins:
        src = os.path.join(game, b)
        dst = os.path.join(d["backup"], b)
        if not os.path.isfile(src):
            print(f"  ! 找不到 {b}，跳过")
            continue
        if os.path.exists(dst) and not args.force:
            print(f"  = {b} 已备份")
            continue
        shutil.copy2(src, dst)
        print(f"  ✓ {b} {os.path.getsize(dst)/1048576:.1f} MB")

    # ---------- 2. 解包 ----------
    step("解包 ESC-ARC2")
    work = paths.ensure(os.path.join(d["unpack"]))
    out_root = os.path.join(work, "output")
    for b in bins:
        src = os.path.join(d["backup"], b)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(work, b))
    if os.path.isdir(out_root) and not args.force:
        print("  = output/ 已存在，跳过（加 --force 重来）")
    else:
        shutil.rmtree(out_root, ignore_errors=True)
        log = run([tool, "-u", work], cwd=work)
        n = log.lower().count("success")
        print(f"  解包完成（{n} 个包）→ {out_root}")

    script_dir = os.path.join(out_root, "script")
    data_dir = os.path.join(out_root, "data")
    if not os.path.isdir(script_dir):
        sys.exit("解包结果里没有 output/script，检查 bins 配置是否包含脚本包")

    # ---------- 3. 解脚本成库 ----------
    step("解脚本 → SQLite")
    db = os.path.join(out_root, "script.db")
    if os.path.exists(db) and not args.force:
        print(f"  = script.db 已存在")
    else:
        run([tool, "-v", script_dir, "-t", "0"], cwd=work)
        if not os.path.exists(db):
            sys.exit("没有生成 script.db，确认工具的 -v 参数用法")
        print(f"  ✓ script.db {os.path.getsize(db)/1048576:.1f} MB")

    # ---------- 4. 解数据库（人名 / 界面文本） ----------
    step("解数据库")
    if os.path.isdir(data_dir):
        run([tool, "-d", data_dir], cwd=work)
        dbs = [f for f in os.listdir(out_root) if f.startswith("db_") and f.endswith(".db")]
        print(f"  ✓ {len(dbs)} 个库：{', '.join(dbs) if dbs else '（无）'}")
    else:
        print("  ! 没有 output/data，跳过（该作品可能没有数据库）")

    # ---------- 5. 提取日文 ----------
    step("提取日文文本")
    jp = d["json_jp"]
    if os.path.isdir(jp) and os.listdir(jp) and not args.force:
        print(f"  = {jp} 已存在，跳过（加 --force 重来）")
    else:
        shutil.rmtree(jp, ignore_errors=True)
        os.makedirs(jp, exist_ok=True)
        log = run([sys.executable, os.path.join(HERE, "hx.py"), "export", db, jp])
        print("  " + log.strip().splitlines()[-1] if log.strip() else "")

    # ---------- 6. 干净底版 ----------
    step("制作干净底版（之后每次构建都从这里取）")
    pr = d["pristine"]
    shutil.copy2(db, os.path.join(pr, "script.db"))
    print("  ✓ script.db")
    for f in os.listdir(out_root):
        if f.startswith("db_") and f.endswith(".db"):
            shutil.copy2(os.path.join(out_root, f), os.path.join(pr, f))
    if any(f.startswith("db_") for f in os.listdir(pr)):
        print("  ✓ db_*.db")
    gfx = os.path.join(out_root, "gfx")
    if os.path.isdir(gfx):
        for sub in ("font/ja_jp", "font/zh_cn", "sys"):
            src = os.path.join(gfx, sub.replace("/", os.sep))
            if os.path.isdir(src):
                dst = os.path.join(pr, "gfx", sub.replace("/", os.sep))
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
                print(f"  ✓ gfx/{sub}")

    # ---------- 7. 自动推断可用页号 ----------
    step("推断占位字可用页号")
    try:
        top = max_used_page(jp)
        cfg.setdefault("font", {})
        old = cfg["font"].get("max_page")
        cfg["font"]["max_page"] = top
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"  原版正文用到的最大页号 = {top}（已写入 project.json，原值 {old}）")
        print("  占位字只会落在 1~%d 页；画到更后面的页引擎不渲染，会显示空白" % top)
    except Exception as e:
        print(f"  ! 推断失败：{e}")

    print("\n准备完成。下一步：")
    print("  1) 复制 config.example.json 为 scripts/config.json 并填 api_key")
    print("  2) python scripts/hx.py translate <项目>/2_json_jp <项目>/3_json_cn")
    print("  3) python scripts/build.py --project <项目>")


if __name__ == "__main__":
    main()
