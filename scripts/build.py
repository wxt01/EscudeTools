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


def _font_root(d):
    return os.path.join(d["pristine"], "gfx", "font")


def _has_size_dirs(path):
    """该目录下是否直接就是 12/ 14/ … 字号目录（无语言层布局）"""
    try:
        return any(s.isdigit() and os.path.isdir(os.path.join(path, s)) for s in os.listdir(path))
    except OSError:
        return False


def pristine_font_dir(d):
    """返回「含字号目录」的那一层。兼容两种封包布局：
       gfx\\font\\ja_jp\\12\\…（带语言层，千艶万匣）
       gfx\\font\\12\\…      （无语言层，戦巫センナギ）"""
    base = _font_root(d)
    if not os.path.isdir(base):
        sys.exit(f"缺少干净字库底版：{base}\n先跑 prepare.py")
    # 优先 ja_jp（日文原字库），否则取第一个语言子目录
    for name in ("ja_jp", "jp", "ja"):
        p = os.path.join(base, name)
        if os.path.isdir(p):
            return p
    if _has_size_dirs(base):
        return base
    subs = [s for s in os.listdir(base) if os.path.isdir(os.path.join(base, s))]
    if not subs:
        sys.exit(f"{base} 下没有字号目录")
    return os.path.join(base, subs[0])


def unpack_font_dir(d, src):
    """底版字库目录 → 解包树里对应的目录（保持同样的层级，别再套一层）"""
    dst_root = os.path.join(d["unpack"], "output", "gfx", "font")
    rel = os.path.relpath(src, _font_root(d))
    return dst_root if rel in (".", "") else os.path.join(dst_root, rel)


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

    dst = unpack_font_dir(d, src)
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
    """只重写 .001（台词表），让 .bin（指令流 + __text 关键字表）保持原版字节。

    为什么不用 type 0（工具注释里自己写着 unstable）：
      实测 -e -t 0 连 .bin 一起重写，产物能被 -v 载入、但 export 全失败（247/247），
      等于把指令流写坏；而 -e -t 1 生成的 .001 在未改文本时与原版**逐字节一致**，
      原版 .bin + 新 .001 再用 -v -t 0 导出 494/494 全过 —— 这条路可验证、可回滚。
    """
    out = os.path.join(d["unpack"], "output")
    script_dir = os.path.join(out, "script")
    paths.need_file(script_dir, "先跑 prepare.py 解包")
    tool = paths.engine_tool(d)

    sm = os.path.join(out, "script_sm.db")
    if os.path.isfile(sm):
        os.remove(sm)
    run([tool, "-v", script_dir, "-t", "1"], cwd=out)
    paths.need_file(sm, "type 1 导出没有生成 script_sm.db（确认 .001 文件在 output\\script 里）")

    log = run([sys.executable, os.path.join(HERE, "hx.py"), "inject",
               sm, d["json_cn"], cmap_path], cwd=HERE)
    for l in [l for l in log.strip().splitlines() if l.strip()][-2:]:
        print("  " + l)

    run([tool, "-e", sm, "-t", "1"], cwd=out)
    repack = os.path.join(out, "repack")
    if not os.path.isdir(repack) or not os.listdir(repack):
        raise RuntimeError("脚本回封没有产物，检查 -e 的输入是否为 script_sm.db 文件")
    n = 0
    for fn in os.listdir(repack):
        shutil.move(os.path.join(repack, fn), os.path.join(script_dir, fn))
        n += 1
    shutil.rmtree(repack, ignore_errors=True)
    print(f"  台词表回封 {n} 个 .001（.bin 未改动）")


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

    # data_zh.json：data.bin 里其它表的文本（技能名/说明、仪式行为、帮助文本…）
    # 键格式：<db 文件名>|<表>|<列>|<rowid>
    dz = os.path.join(d["root"], "data_zh.json")
    if os.path.isfile(dz):
        payload = json.load(open(dz, encoding="utf-8"))
        per_db = {}
        for k, zh in payload.items():
            parts = k.split("|")
            if len(parts) == 4 and isinstance(zh, str) and zh:
                per_db.setdefault(parts[0], []).append((parts[1], parts[2], int(parts[3]), zh))
        total_dz = 0
        for dbname, rows in per_db.items():
            p = os.path.join(out, dbname)
            if not os.path.isfile(p):
                print(f"  ! 没有 {dbname}，跳过 {len(rows)} 条")
                continue
            c = sqlite3.connect(p)
            for t, col, rid, zh in rows:
                try:
                    c.execute(f'update "{t}" set "{col}"=? where rowid=?', (encode(zh), rid))
                    total_dz += 1
                except sqlite3.Error as e:
                    print(f"  ! 写入 {t}.{col} 失败：{e}")
                    break
            c.commit()
            c.close()
        print(f"  其它表文本写入 {total_dz} 行")

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
    # 自动生成的说明写到 使用说明_auto.txt；使用说明.txt 只在不存在时生成。
    # 这样项目里手写的说明（版本变更、残留项、已知问题）不会被每次构建冲掉。
    auto = os.path.join(rel, "使用说明_auto.txt")
    with open(auto, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    hand = os.path.join(rel, "使用说明.txt")
    if not os.path.isfile(hand):
        shutil.copy2(auto, hand)
        print("  已生成 使用说明.txt（之后可手改，构建不再覆盖）")
    print(f"  已部署到 {rel}")


def _warn_if_pages_pristine(d):
    """--no-gfx 仍会整包重打 gfx.bin。若解包树里的字库页还是原版（没画中文），
    重打出来就是原版字库，中文会整片消失。这里提前拦住，避免误毁补丁。"""
    src = pristine_font_dir(d)
    dst = unpack_font_dir(d, src)
    if not os.path.isdir(dst):
        sys.exit(f"解包树里没有字库页：{dst}\n先跑一次全量构建")
    # 只抽查「码表真正落到的页」——00/01 页是 ASCII 与假名，画中文不会动它们，
    # 老逻辑只比前两页，会把「已汉化」误判成「没画过」（戦巫センナギ 实测踩到）。
    pages = _cmap_pages(os.path.join(d["build"], "cmap", "cmap.json"))
    sample = pages[:2] + pages[len(pages) // 2:len(pages) // 2 + 2] + pages[-2:] if pages else [0, 1]
    same = diff = 0
    for size in sorted(os.listdir(src)):
        sp = os.path.join(src, size)
        if not os.path.isdir(sp):
            continue
        for page in sorted(set(sample)):
            fn = f"{page:02d}.png"
            dp = os.path.join(dst, size, fn)
            if not os.path.isfile(dp):
                diff += 1
                continue
            with open(os.path.join(sp, fn), "rb") as f1, open(dp, "rb") as f2:
                if f1.read() == f2.read():
                    same += 1
                else:
                    diff += 1
        if same and diff:
            break
    if same and not diff:
        sys.exit("解包树里的字库页与底版完全相同（还没画中文）。\n"
                 "--no-gfx 会整包重打 gfx.bin，中文会消失。\n"
                 "先跑一次全量构建，之后改译文再用 --no-gfx。")
    print(f"  字库页检查（抽查第 {','.join(str(x) for x in sorted(set(sample)))} 页）："
          f"{diff} 处已汉化 / {same} 处未变，可以安全重打")


def _cmap_pages(cmap_path):
    """码表里的占位字落在哪些字库页（复刻引擎 put_char 的 JIS 区/点算法）"""
    try:
        with open(cmap_path, encoding="utf-8") as f:
            cmap = json.load(f)
    except Exception:
        return []
    pages = set()
    for ph in cmap.values():
        try:
            b = str(ph).encode("cp932")
        except Exception:
            continue
        if len(b) != 2:
            continue
        lead, trail = b[0], b[1]
        if lead <= 0x9F:
            ku = (lead - 0x81) * 2 + 0x21
        else:
            ku = (lead - 0xC1) * 2 + 0x21
        if trail >= 0x9F:
            ku += 1
        page = ku - 0x21
        if 0 <= page <= 93:
            pages.add(page)
    return sorted(pages)


def run_qa(d, strict=False):
    """打包前文本质检（qa_text.py）。拦截项不为 0 就中止构建。"""
    qa = os.path.join(HERE, "qa_text.py")
    if not os.path.isfile(qa):
        print("  ! 没有 qa_text.py，跳过质检")
        return
    p = subprocess.run([sys.executable, qa, "--project", d["root"]]
                       + (["--strict"] if strict else []),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-5:]:
        print("  " + line)
    if p.returncode == 2:
        sys.exit("文本质检不通过（明细见 <项目>\\审校报告.txt）。\n"
                 "  修完再构建；确认要强制出包可加 --skip-qa。")
    if p.returncode not in (0, 3):
        print(f"  ! 质检脚本异常退出（{p.returncode}）：{(p.stderr or '')[-300:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="", help="项目目录（含 project.json）")
    ap.add_argument("--no-gfx", action="store_true", help="跳过字库与界面图，只重打脚本")
    ap.add_argument("--skip-ui", action="store_true", help="跳过界面图替换")
    ap.add_argument("--skip-qa", action="store_true", help="跳过打包前的文本质检（不推荐）")
    ap.add_argument("--strict-qa", action="store_true", help="质检警告也视为失败")
    args = ap.parse_args()

    d = paths.dirs(cli=args.project)
    os.environ["HANHUA_PROJECT"] = d["root"]   # 子进程（hx.py 等）据此定位项目
    print(f"项目：{d['root']}")
    if not os.path.isfile(os.path.join(d["root"], "project.json")):
        sys.exit("该目录里没有 project.json，先跑 prepare.py")
    paths.need_file(os.path.join(d["unpack"], "output"), "先跑 prepare.py 解包")

    cmap_path = os.path.join(d["build"], "cmap", "cmap.json")

    if args.no_gfx:
        paths.need_file(cmap_path, "没有现成码表，先跑一次全量构建")
        _warn_if_pages_pristine(d)
        cmap = json.load(open(cmap_path, encoding="utf-8"))
    else:
        step("收集中文用字")
        need = collect_chars(d["json_cn"], [
            os.path.join(d["root"], "names_zh.json"),
            os.path.join(d["root"], "ui_zh.json"),
            os.path.join(d["root"], "data_zh.json"),
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

    if not args.skip_qa:
        step("文本质检（qa_text.py）")
        run_qa(d, strict=args.strict_qa)

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
