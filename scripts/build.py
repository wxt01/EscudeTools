#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py —— 一键构建：码表 → 字库 → 注入 → 回封 → 出包

前置：先跑过 prepare.py（需要 4_pristine/ 里的干净底版）

用法：
  python build.py --project <项目目录>              # 全量构建
  python build.py --project <项目目录> --no-gfx     # 只重打脚本（改译文后用，约 1 分钟）
  python build.py --project <项目目录> --skip-ui    # 跳过界面图替换

产出：<项目>/6_release/{script,gfx,data}.bin + 使用说明.txt

为什么每次都从 4_pristine 取底版：
  注入是「往库里写」，如果反复在已经写过中文的库上再写一遍，
  旧的占位符会被当成正常字符保留下来，越改越脏。所以每次都从干净库复制。
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, cwd=None, check=False):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    if check and p.returncode != 0:
        raise RuntimeError(f"命令失败：{' '.join(map(str, cmd))}\n{out[-1200:]}")
    return out


def step(msg):
    print(f"\n=== {msg}")


def pick(obj, *keys, default=""):
    for k in keys:
        if isinstance(obj, dict) and obj.get(k):
            return obj[k]
    return default


# ---------- 用字收集 ----------

def collect_chars(cn_dir, extra_files):
    need = set()
    if os.path.isdir(cn_dir):
        for fn in os.listdir(cn_dir):
            if not fn.endswith(".jsonl"):
                continue
            with open(os.path.join(cn_dir, fn), encoding="utf-8") as f:
                for line in f:
                    try:
                        zh = json.loads(line).get("zh") or ""
                    except Exception:
                        continue
                    need.update(zh)
    for p in extra_files:
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                for v in data.values():
                    if isinstance(v, str):
                        need.update(v)
            except Exception:
                pass
    # 只保留非 ASCII 字符（ASCII 走字库第 0 页，本来就存在）
    return {c for c in need if ord(c) > 0x7F}


# ---------- 各步骤 ----------

def make_cmap(d, need):
    tmp = paths.ensure(os.path.join(d["build"], "_chars"))
    with open(os.path.join(tmp, "all.jsonl"), "w", encoding="utf-8") as f:
        for i, c in enumerate(sorted(need)):
            f.write(json.dumps({"index": i, "zh": c}, ensure_ascii=False) + "\n")
    out = os.path.join(d["build"], "cmap")
    cfg = d["cfg"]
    font = cfg.get("font", {})
    log = run([sys.executable, os.path.join(HERE, "gen_font.py"),
               "--text", tmp, "--out", out,
               "--exclude-text", d["json_jp"],
               "--max-page", str(font.get("max_page", 83)),
               "--base", font.get("face", r"C:\Windows\Fonts\msyh.ttc")])
    tail = [l for l in log.strip().splitlines() if l.strip()][-2:]
    for l in tail:
        print("  " + l)
    p = os.path.join(out, "cmap.json")
    if not os.path.isfile(p):
        raise RuntimeError("码表没有生成：\n" + log[-1500:])
    return p


def pristine_font_dir(d):
    base = os.path.join(d["pristine"], "gfx", "font")
    if not os.path.isdir(base):
        sys.exit(f"缺少干净字库底版：{base}\n先跑 prepare.py")
    # 优先 ja_jp（日文原字库），否则取第一个子目录
    for name in ("ja_jp", "jp", "ja"):
        p = os.path.join(base, name)
        if os.path.isdir(p):
            return p
    subs = [s for s in os.listdir(base) if os.path.isdir(os.path.join(base, s))]
    if not subs:
        sys.exit(f"{base} 下没有字号目录")
    return os.path.join(base, subs[0])


def paint_pages(d, cmap_path):
    src = pristine_font_dir(d)
    out = os.path.join(d["build"], "pages")
    cfg = d["cfg"].get("font", {})
    log = run([sys.executable, os.path.join(HERE, "gen_fontpages.py"),
               "--cmap", cmap_path, "--fontdir", src, "--out", out,
               "--font", cfg.get("face", r"C:\Windows\Fonts\msyh.ttc"),
               "--index", str(cfg.get("index", 0))])
    for l in [l for l in log.strip().splitlines() if l.strip()][-2:]:
        print("  " + l)
    if not os.path.isdir(out):
        raise RuntimeError("字库页没有生成：\n" + log[-1500:])

    dst = os.path.join(d["unpack"], "output", "gfx", "font", os.path.basename(src))
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(out, dst)
    print(f"  字库页已替换 → {dst}")


def apply_ui(d, clean_sys):
    """界面图片文字替换（可选；没有配置就跳过）"""
    labels = os.path.join(d["root"], "ui_labels.json")
    if not os.path.isdir(clean_sys):
        print("  没有原版 sys 目录，跳过")
        return
    dst = os.path.join(d["unpack"], "output", "gfx", "sys")
    jobs = []
    # 设置界面（按行栅格）
    if os.path.isfile(labels):
        out = os.path.join(d["build"], "ui_config")
        log = run([sys.executable, os.path.join(HERE, "ui_image_patch.py"),
                   "--in", clean_sys, "--out", out, "--labels", labels])
        print("  " + (log.strip().splitlines()[-1] if log.strip() else ""))
        jobs.append(out)
    # 零散图（确认框等）
    misc = os.path.join(d["root"], "ui_misc.json")
    if os.path.isfile(misc):
        out = os.path.join(d["build"], "ui_misc")
        run([sys.executable, os.path.join(HERE, "ui_inpaint_patch.py"),
             "--in", clean_sys, "--out", out, "--config", misc])
        jobs.append(out)
    if not jobs:
        print("  没有 ui_labels.json / ui_misc.json，跳过（见 docs/05）")
        return
    for out in jobs:
        for root_, _, files in os.walk(out):
            for fn in files:
                s = os.path.join(root_, fn)
                rel = os.path.relpath(s, out)
                t = os.path.join(dst, rel)
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.copy2(s, t)
    print("  界面图已替换")


def build_script(d, cmap_path):
    out = os.path.join(d["unpack"], "output")
    db = os.path.join(out, "script.db")
    src = os.path.join(d["pristine"], "script.db")
    paths.need_file(src, "先跑 prepare.py")
    shutil.copy2(src, db)

    log = run([sys.executable, os.path.join(HERE, "hx.py"), "inject",
               db, d["json_cn"], cmap_path], cwd=HERE)
    for l in [l for l in log.strip().splitlines() if l.strip()][-2:]:
        print("  " + l)

    tool = paths.engine_tool(d)
    run([tool, "-e", db, "-t", "0"], cwd=out)
    repack = os.path.join(out, "repack")
    if not os.path.isdir(repack) or not os.listdir(repack):
        raise RuntimeError("脚本回封没有产物，检查 -e 的输入是否为 script.db 文件")
    n = 0
    for fn in os.listdir(repack):
        shutil.move(os.path.join(repack, fn), os.path.join(out, "script", fn))
        n += 1
    shutil.rmtree(repack, ignore_errors=True)
    print(f"  脚本回封 {n} 个文件")


def build_data(d, cmap):
    out = os.path.join(d["unpack"], "output")
    dbs = [f for f in os.listdir(d["pristine"]) if f.startswith("db_") and f.endswith(".db")]
    if not dbs:
        print("  没有数据库，跳过")
        return
    for f in dbs:
        shutil.copy2(os.path.join(d["pristine"], f), os.path.join(out, f))

    cfg = d["cfg"].get("data", {})
    name_tbl, name_col = cfg.get("name_table", ""), cfg.get("name_col", "")
    ui_tbl, ui_col = cfg.get("ui_table", ""), cfg.get("ui_text_col", "")

    def encode(s):
        return "".join(cmap.get(ch, ch) for ch in s)

    def apply(json_path, db_name, table, col):
        p = os.path.join(d["root"], json_path)
        if not (os.path.isfile(p) and table and col):
            return 0
        data = json.load(open(p, encoding="utf-8"))
        dbp = os.path.join(out, db_name)
        if not os.path.isfile(dbp):
            return 0
        c = sqlite3.connect(dbp)
        n = 0
        for rid, zh in data.items():
            if not isinstance(zh, str):
                continue
            try:
                c.execute(f'update "{table}" set "{col}"=? where rowid=?', (encode(zh), int(rid)))
                n += 1
            except sqlite3.Error as e:
                print(f"  ! 写入 {table} 失败：{e}")
                break
        c.commit()
        c.close()
        return n

    n1 = apply("names_zh.json", "db_scripts.db", name_tbl, name_col)
    n2 = apply("ui_zh.json", "db_localize.db", ui_tbl, ui_col)
    if n1:
        print(f"  人名写入 {n1} 行")
    if n2:
        print(f"  界面文本写入 {n2} 行")

    mdb = os.path.join(d["unpack"], "mdb")
    shutil.rmtree(mdb, ignore_errors=True)
    os.makedirs(mdb)
    for f in os.listdir(out):
        if f.startswith("db_") and f.endswith(".db"):
            shutil.copy2(os.path.join(out, f), mdb)
    tool = paths.engine_tool(d)
    run([tool, "-f", mdb], cwd=mdb)
    moved = 0
    for f in os.listdir(mdb):
        if f.endswith(".bin"):
            shutil.move(os.path.join(mdb, f), os.path.join(out, "data", f))
            moved += 1
    print(f"  数据库回封 {moved} 个")


def repack(d):
    out = os.path.join(d["unpack"], "output")
    tool = paths.engine_tool(d)
    run([tool, "-r", out], cwd=out)
    res = {}
    for fn in d["cfg"].get("bins") or ["script.bin", "gfx.bin", "data.bin"]:
        p = os.path.join(out, fn)
        if not os.path.isfile(p):
            raise RuntimeError(f"整包重打缺少 {fn}")
        res[fn] = p
        print(f"  {fn} {os.path.getsize(p)/1048576:.1f} MB")
    return res


def stats(d):
    """统计译文规模，写进说明文件"""
    n = chars = 0
    cn = d["json_cn"]
    if os.path.isdir(cn):
        for fn in os.listdir(cn):
            if not fn.endswith(".jsonl"):
                continue
            for line in open(os.path.join(cn, fn), encoding="utf-8"):
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if o.get("zh"):
                    n += 1
                    chars += len(o["zh"])
    return n, chars


def deploy(d, outs):
    rel = paths.ensure(d["release"])
    for fn, p in outs.items():
        shutil.copy2(p, os.path.join(rel, fn))
    n, chars = stats(d)
    lines = [
        "语言本地化补丁 —— 使用说明",
        "=" * 40,
        "",
        "【怎么用】",
        "  1. 先把游戏目录里原有的同名文件复制一份备份",
        "  2. 把本文件夹里的资源包拖进游戏目录，提示替换时选「替换」",
        "  3. 启动游戏，即为中文",
        "  ※ 替换前请先退出游戏，否则会因文件占用导致卡顿甚至失败。",
        "",
        "【想还原】",
        "  把备份的原文件拖回去覆盖即可。",
        "  本补丁不改 exe、不写注册表、不动系统字体，还原是彻底的。",
        "",
        "【技术说明】",
        "  中文通过「SJIS 占位码位 + 重绘位图字库」实现：",
        "  译文先映射成日文里的冷门字符，再把那些格子里画上中文字形，",
        "  引擎以为在显示日文，实际画出来的是中文。",
        "",
    ]
    if n:
        lines.append(f"【本包规模】台词 {n} 行 / {chars} 字")
        lines.append("")
    lines += [
        "【未处理】",
        "  · 图片内的文字（标题按钮、UI 底图、CG 内嵌字、STAFF 图等）",
        "  · OP/ED 视频字幕与歌词",
        "  · 语音仍为原音",
        "  · 引擎硬编码的提示文本",
        "",
        "【观感】",
        "  字库由系统字体渲染，与其他汉化补丁的字库相比字重/字距有差异。",
    ]
    with open(os.path.join(rel, "使用说明.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  已部署到 {rel}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="", help="项目目录（含 project.json）")
    ap.add_argument("--no-gfx", action="store_true", help="跳过字库与界面图，只重打脚本")
    ap.add_argument("--skip-ui", action="store_true", help="跳过界面图替换")
    args = ap.parse_args()

    d = paths.dirs(cli=args.project)
    print(f"项目：{d['root']}")
    if not os.path.isfile(os.path.join(d["root"], "project.json")):
        sys.exit("该目录里没有 project.json，先跑 prepare.py")
    paths.need_file(os.path.join(d["unpack"], "output"), "先跑 prepare.py 解包")

    cmap_path = os.path.join(d["build"], "cmap", "cmap.json")

    if args.no_gfx:
        paths.need_file(cmap_path, "没有现成码表，先跑一次全量构建")
        cmap = json.load(open(cmap_path, encoding="utf-8"))
    else:
        step("收集中文用字")
        need = collect_chars(d["json_cn"], [
            os.path.join(d["root"], "names_zh.json"),
            os.path.join(d["root"], "ui_zh.json"),
        ])
        if not need:
            sys.exit("译文目录为空，先跑 hx.py translate")
        print(f"  需要字符 {len(need)} 个")

        step("生成码表")
        cmap_path = make_cmap(d, need)
        cmap = json.load(open(cmap_path, encoding="utf-8"))
        print(f"  码表 {len(cmap)} 条")

        step("绘制字库页")
        paint_pages(d, cmap_path)

        if not args.skip_ui:
            step("替换界面图")
            apply_ui(d, os.path.join(d["pristine"], "gfx", "sys"))

    step("注入译文并回封脚本")
    build_script(d, cmap_path)

    if os.path.isdir(os.path.join(d["unpack"], "output", "data")):
        step("写人名/界面文本并回封数据库")
        build_data(d, cmap)

    step("整包重打")
    outs = repack(d)

    step("输出")
    deploy(d, outs)
    print("\n构建完成。")


if __name__ == "__main__":
    main()
