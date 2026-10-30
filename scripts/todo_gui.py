#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汉化待办处理 —— 像后台待办一样，一条条过，逐条决定译文。

双击「汉化待办.bat」或「汉化待办.exe」启动。
左侧是待办清单，右侧是这条的原文 / 我给初稿 / 你写最终版。
Ctrl+Enter 保存并跳下一条。

只改项目译文目录（默认 3_json_cn）里的译文，不碰游戏文件。改完跑 python build.py --no-gfx 重新出包。
"""

import json
import os
import re
import shutil
import sys
import time

BASE = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
sys.path.insert(0, BASE)
import paths

_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
_D = paths.dirs(cli=_arg)
CN_DIR = _D["json_cn"]
BK_ROOT = os.path.join(_D["root"], "备份")
STATE = os.path.join(_D["root"], "待办进度.json")

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
TAG = re.compile(r"<[^>]{1,16}>")
MOAN = re.compile(r"(あ[ぁァ]|ん[っッ]|は[ぁァ]|く[っッ]|ぁ|ぃ|う[ぅゥ]|お[ぉォ])")
NSFW = re.compile(r"(気持ち|挿|中出|膣|乳|腰|舐|咥|精|濡|絶頂|イか|イク|孕|犯|肉|奥)")

CATS = ["未译", "成人向", "拟声词", "超长", "残留日文"]


def categorize(fn, jp, zh):
    plain = TAG.sub("", jp or "")
    if not zh:
        return "未译"
    if "_H" in fn.upper() or NSFW.search(plain):
        return "成人向"
    if MOAN.search(plain) and len(plain) < 40:
        return "拟声词"
    if len(TAG.sub("", zh)) > len(plain) * 1.6 + 10 and len(TAG.sub("", zh)) > 40:
        return "超长"
    if KANA.search(zh):
        return "残留日文"
    return None


def load_items():
    items = []
    if not os.path.isdir(CN_DIR):
        return items
    for fn in sorted(f for f in os.listdir(CN_DIR) if f.endswith(".jsonl")):
        path = os.path.join(CN_DIR, fn)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                cat = categorize(fn, o.get("jp"), o.get("zh"))
                if cat:
                    items.append({
                        "file": fn, "index": o.get("index"),
                        "jp": o.get("jp", ""), "draft": o.get("zh", ""),
                        "cat": cat, "done": False,
                    })
    return items


def _save_one(fn, changes):
    """把 {index: zh} 写回对应 jsonl"""
    path = os.path.join(CN_DIR, fn)
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            if o.get("index") in changes:
                o["zh"] = changes[o["index"]]
            rows.append(o)
    with open(path, "w", encoding="utf-8") as f:
        for o in rows:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")


def selftest():
    items = load_items()
    from collections import Counter
    print(f"待办 {len(items)} 条")
    print(Counter(i["cat"] for i in items))
    for i in items[:5]:
        print(f"  [{i['cat']}] {i['file']}:{i['index']}")
        print(f"    JP {i['jp'][:40]}")
        print(f"    ZH {i['draft'][:40]}")


def main_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, font as tkfont

    items = load_items()
    root = tk.Tk()
    root.title("汉化待办处理")
    root.geometry("1100x720")

    done_state = {}
    if os.path.exists(STATE):
        try:
            done_state = json.load(open(STATE, encoding="utf-8"))
        except Exception:
            done_state = {}
    for it in items:
        key = f"{it['file']}#{it['index']}"
        if done_state.get(key):
            it["done"] = True
            it["draft"] = done_state[key]

    if not items:
        # 没有待办也照常打开窗口：搜索替换、翻看改动都还能用
        root.title("汉化待办处理（当前没有待办，可用「搜索替换」整理译文）")

    # ---------- 顶部筛选 ----------
    top = tk.Frame(root, padx=10, pady=8)
    top.pack(fill="x")
    tk.Label(top, text="类别：", font=("Microsoft YaHei", 10)).pack(side="left")
    cat_vars = {}
    for c in CATS:
        v = tk.BooleanVar(value=True)
        cat_vars[c] = v
        tk.Checkbutton(top, text=c, variable=v, command=lambda: refresh(),
                       font=("Microsoft YaHei", 10)).pack(side="left", padx=4)
    only_todo = tk.BooleanVar(value=True)
    tk.Checkbutton(top, text="只看未处理", variable=only_todo, command=lambda: refresh(),
                   font=("Microsoft YaHei", 10)).pack(side="left", padx=12)
    prog = tk.Label(top, text="", font=("Microsoft YaHei", 10, "bold"))
    prog.pack(side="right")

    # ---------- 主体 ----------
    body = tk.PanedWindow(root, orient="horizontal", sashwidth=6)
    body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    left = tk.Frame(body)
    cols = ("cat", "pos", "brief")
    tree = ttk.Treeview(left, columns=cols, show="headings", height=25)
    tree.heading("cat", text="类别")
    tree.heading("pos", text="位置")
    tree.heading("brief", text="原文摘要")
    tree.column("cat", width=80, anchor="center")
    tree.column("pos", width=150, anchor="w")
    tree.column("brief", width=260, anchor="w")
    sb = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    body.add(left, width=520)

    right = tk.Frame(body, padx=12)
    body.add(right)

    tk.Label(right, text="日文原文", font=("Microsoft YaHei", 10, "bold"), anchor="w").pack(fill="x")
    t_jp = tk.Text(right, height=5, wrap="word", font=("Microsoft YaHei", 11),
                   bg="#f4f4f4", state="disabled")
    t_jp.pack(fill="x", pady=(2, 10))

    tk.Label(right, text="我给的初稿（只读，可作参考）", font=("Microsoft YaHei", 10, "bold"), anchor="w").pack(fill="x")
    t_draft = tk.Text(right, height=5, wrap="word", font=("Microsoft YaHei", 11),
                      bg="#f4f4f4", state="disabled")
    t_draft.pack(fill="x", pady=(2, 10))

    tk.Label(right, text="你的译文（直接改这里）", font=("Microsoft YaHei", 10, "bold"), anchor="w").pack(fill="x")
    t_edit = tk.Text(right, height=10, wrap="word", font=("Microsoft YaHei", 12))
    t_edit.pack(fill="both", expand=True, pady=(2, 8))

    btns = tk.Frame(right)
    btns.pack(fill="x")
    visible = []

    def say(msg):
        prog.config(text=msg)

    def current():
        sel = tree.selection()
        if not sel:
            return None
        i = int(sel[0])
        return visible[i] if i < len(visible) else None

    def show(it):
        t_jp.config(state="normal"); t_jp.delete("1.0", "end"); t_jp.insert("1.0", it["jp"]); t_jp.config(state="disabled")
        t_draft.config(state="normal"); t_draft.delete("1.0", "end"); t_draft.insert("1.0", it["draft"]); t_draft.config(state="disabled")
        t_edit.delete("1.0", "end"); t_edit.insert("1.0", it.get("final", it["draft"]))
        t_edit.focus_set()

    def refresh(keep=None):
        tree.delete(*tree.get_children())
        visible.clear()
        for it in items:
            if not cat_vars[it["cat"]].get():
                continue
            if only_todo.get() and it["done"]:
                continue
            visible.append(it)
            iid = str(len(visible) - 1)
            tree.insert("", "end", iid=iid, values=(
                it["cat"], f"{it['file'][:22]}:{it['index']}", (it.get("final") or it["draft"] or it["jp"])[:40]))
        n_done = sum(1 for x in items if x["done"])
        say(f"已处理 {n_done} / 共 {len(items)}　｜　当前显示 {len(visible)} 条")
        if visible:
            target = keep if keep is not None and keep < len(visible) else 0
            tree.selection_set(str(target))
            tree.see(str(target))
            show(visible[target])

    def backup_once():
        if getattr(backup_once, "done", False):
            return
        os.makedirs(BK_ROOT, exist_ok=True)
        dst = os.path.join(BK_ROOT, "GUI_" + time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(dst, exist_ok=True)
        for fn in os.listdir(CN_DIR):
            if fn.endswith(".jsonl"):
                shutil.copy2(os.path.join(CN_DIR, fn), os.path.join(dst, fn))
        backup_once.done = True
        print("已备份到", dst)

    def save_state():
        data = {f"{i['file']}#{i['index']}": i.get("final") for i in items if i["done"] and i.get("final")}
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def save_current(advance=True):
        it = current()
        if not it:
            return
        try:
            pos = int(tree.selection()[0])
        except Exception:
            pos = None
        saved_key = (it["file"], it["index"])
        text = t_edit.get("1.0", "end").rstrip("\n")
        it["final"] = text
        it["done"] = True
        backup_once()
        _save_one(it["file"], {it["index"]: text})
        save_state()
        if advance:
            refresh()
            # 从刚保存的这条往后找第一条未处理的接着改，不要跳回列表顶部
            start = 0
            for k, x in enumerate(visible):
                if (x["file"], x["index"]) == saved_key:
                    start = k + 1
                    break
            for k in list(range(start, len(visible))) + list(range(0, start)):
                if not visible[k]["done"]:
                    tree.selection_set(str(k))
                    tree.see(str(k))
                    show(visible[k])
                    break
        else:
            say(f"已保存：{it['file']}:{it['index']}")

    def skip():
        idx = int(tree.selection()[0]) + 1 if tree.selection() else 0
        if idx >= len(visible):
            idx = 0
        if visible:
            tree.selection_set(str(idx)); tree.see(str(idx)); show(visible[idx])

    def restore():
        it = current()
        if not it:
            return
        t_edit.delete("1.0", "end"); t_edit.insert("1.0", it["draft"])

    def adopt_all():
        if not messagebox.askyesno("确认", "把所有「未处理」的条目都采用我给的初稿？\n（之后还可以再单独改）"):
            return
        cnt = 0
        backup_once()
        for it in items:
            if not it["done"] and cat_vars[it["cat"]].get():
                it["final"] = it["draft"]
                it["done"] = True
                _save_one(it["file"], {it["index"]: it["draft"]})
                cnt += 1
        save_state()
        refresh()
        say(f"已批量采用 {cnt} 条")

    # ---- 搜索替换 ----
    def search_replace():
        win = tk.Toplevel(root)
        win.title("搜索替换（只改中文译文，自动先备份）")
        win.geometry("760x480")
        top = tk.Frame(win); top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="查找：", font=("Microsoft YaHei", 10)).pack(side="left")
        e_find = tk.Entry(top, font=("Microsoft YaHei", 11), width=24); e_find.pack(side="left", padx=4)
        tk.Label(top, text="替换为：", font=("Microsoft YaHei", 10)).pack(side="left", padx=(10, 0))
        e_rep = tk.Entry(top, font=("Microsoft YaHei", 11), width=24); e_rep.pack(side="left", padx=4)
        status = tk.Label(win, text="输入关键词后点「查找」", font=("Microsoft YaHei", 10), fg="#555")
        status.pack(fill="x", padx=8)
        lb = tk.Listbox(win, font=("Microsoft YaHei", 10))
        lb.pack(fill="both", expand=True, padx=8, pady=6)

        hits = []

        def do_find():
            nonlocal hits
            word = e_find.get().strip()
            lb.delete(0, "end")
            if not word:
                status.config(text="请先输入要查找的词")
                return
            hits = []
            for fn in sorted(f for f in os.listdir(CN_DIR) if f.endswith(".jsonl")):
                for line in open(os.path.join(CN_DIR, fn), encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if word in (o.get("zh") or ""):
                        hits.append((fn, o.get("index", 0), o.get("zh") or ""))
            for fn, idx, zh in hits[:400]:
                lb.insert("end", f"[{fn}:{idx}] {zh[:70]}")
            files = len(set(h[0] for h in hits))
            status.config(text=f"找到 {len(hits)} 处，涉及 {files} 个文件" + ("（仅显示前 400 条）" if len(hits) > 400 else ""))

        def do_replace():
            word = e_find.get().strip()
            new = e_rep.get()
            if not word:
                status.config(text="请先输入要查找的词")
                return
            if not hits:
                status.config(text="请先点「查找」")
                return
            n = sum(h[2].count(word) for h in hits)
            if not messagebox.askyesno("确认替换",
                    f"共 {len(hits)} 行、{n} 处「{word}」将替换为「{new}」。\n替换前会自动备份，确定？"):
                return
            backup_once()
            by_file = {}
            for fn, idx, zh in hits:
                by_file.setdefault(fn, {})[idx] = zh.replace(word, new)
            for fn, changes in by_file.items():
                _save_one(fn, changes)
            for fn, idx, zh in hits:
                for it in items:
                    if it["file"] == fn and it["index"] == idx:
                        it["final"] = zh.replace(word, new)
                        it["done"] = True
            save_state()
            refresh()
            status.config(text=f"完成：{len(hits)} 行已替换（共 {n} 处）。要改下一批请重新「查找」")
            lb.delete(0, "end")

        tk.Button(top, text="查找", command=do_find, font=("Microsoft YaHei", 10),
                  padx=10).pack(side="left", padx=6)
        tk.Button(top, text="全部替换", command=do_replace, font=("Microsoft YaHei", 10, "bold"),
                  bg="#2d7d46", fg="white", padx=10).pack(side="left", padx=6)

    tk.Button(btns, text="保存并下一条 (Ctrl+Enter)", command=save_current,
              font=("Microsoft YaHei", 11, "bold"), bg="#2d7d46", fg="white",
              padx=14, pady=6).pack(side="left")
    tk.Button(btns, text="只保存", command=lambda: save_current(False),
              font=("Microsoft YaHei", 10), padx=10, pady=6).pack(side="left", padx=6)
    tk.Button(btns, text="跳过", command=skip,
              font=("Microsoft YaHei", 10), padx=10, pady=6).pack(side="left")
    tk.Button(btns, text="恢复初稿", command=restore,
              font=("Microsoft YaHei", 10), padx=10, pady=6).pack(side="left", padx=6)
    tk.Button(btns, text="搜索替换", command=search_replace,
              font=("Microsoft YaHei", 10), padx=10, pady=6).pack(side="left", padx=6)
    tk.Button(btns, text="全部采用初稿", command=adopt_all,
              font=("Microsoft YaHei", 10), padx=10, pady=6).pack(side="right")

    tree.bind("<<TreeviewSelect>>", lambda e: show(current()) if current() else None)
    root.bind("<Control-Return>", lambda e: save_current())

    refresh()
    root.mainloop()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main_gui()
