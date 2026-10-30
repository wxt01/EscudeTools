#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hx.py —— Escu:de 汉化流水线（提取 / 翻译 / 注入 / 质检）

适配：EscudeTools 解出的 script.db（表结构：{脚本名}__mess(Mess)、{脚本名}__text(Text)）

用法：
  python hx.py stats   <script.db>
  python hx.py export  <script.db> <输出目录>          # 导出 name-message JSON（每脚本一个文件）
  python hx.py translate <json目录> <输出目录>          # 调 DeepSeek 批量翻译（带缓存、术语表、上下文）
  python hx.py inject  <script.db> <json_cn目录>        # 把中文写回 script.db
  python hx.py check   <json_cn目录>                    # 质检：残留日文/长度/标记丢失/空译

配置：同目录 config.json
  {
    "api_key": "sk-...",
    "endpoint": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "batch_size": 12,
    "context_lines": 6,
    "glossary": "glossary.tsv",
    "characters": "characters.tsv",
    "concurrency": 4
  }
"""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

TAG_RE = re.compile(r"<[^>]{1,16}>")
KANA_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
CJK_RE = re.compile(r"[\u4e00-\u9fa5]")

# ---------- 基础 ----------

def load_cfg(here):
    p = os.path.join(here, "config.json")
    if not os.path.exists(p):
        alt = os.path.join(here, "config.example.json")
        if os.path.exists(alt):
            print("提示：未找到 config.json，暂用 config.example.json（需要自己填 api_key）")
            p = alt
        else:
            sys.exit(f"缺少配置文件：{p}\n请把 config.example.json 复制为 config.json 并填写 api_key")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_tsv(path):
    """glossary.tsv: 日文<TAB>中文<TAB>说明(可选)"""
    rows = []
    if not path or not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                rows.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return rows


def protect(text):
    """把 <r> </ruby> 等标记换成占位符，避免模型改动"""
    tags = []

    def repl(m):
        tags.append(m.group(0))
        return f"\u3010{len(tags)-1}\u3011"

    return TAG_RE.sub(repl, text), tags


def load_terms(here, cfg):
    """合并 glossary.tsv + terms_fd2.tsv + characters.tsv，按日文长度降序（长词优先）"""
    pairs = {}

    def add(jp, zh):
        jp, zh = (jp or "").strip(), (zh or "").strip()
        if not jp or not zh:
            return
        # 注意：日文与中文写法相同的词（汉字人名、地名）也必须锁定，
        # 否则模型会自由发挥成“心之珠/珠儿”之类，破坏系列一致性
        if len(jp) > 12 or len(zh) > 12:
            return
        pairs.setdefault(jp, zh)

    for fn in (cfg.get("glossary"), cfg.get("terms"), "glossary.tsv", "terms_fd2.tsv"):
        if not fn:
            continue
        p = os.path.join(here, fn)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                cols = line.rstrip("\n").split("\t")
                if len(cols) >= 2:
                    add(cols[0], cols[1])

    # 角色表：ID -> 中文名，用于提示（昵称不算术语，不锁定）
    return sorted(pairs.items(), key=lambda x: -len(x[0]))


def lock_terms(text, term_list):
    """把术语替换成 〖Tn〗 占位符，返回 (新文本, {占位符: 中文})
    这样模型看不到原词，不可能翻错；译后按表还原。"""
    if not term_list or not text:
        return text, {}
    zh_of = dict(term_list)
    pat = re.compile("|".join(re.escape(k) for k, _ in term_list))
    mapping = {}

    def repl(m):
        w = m.group(0)
        tok = f"\u3016T{len(mapping)}\u3017"
        mapping[tok] = zh_of[w]
        return tok

    return pat.sub(repl, text), mapping


def restore_terms(text, mapping):
    """还原术语占位符；返回 (文本, 未被还原的占位符个数)"""
    lost = 0
    for tok, zh in mapping.items():
        if tok in text:
            text = text.replace(tok, zh)
        else:
            lost += 1
    return text, lost


def restore(text, tags):
    for i, t in enumerate(tags):
        text = text.replace(f"\u3010{i}\u3011", t)
        text = text.replace(f"[{i}]", t)          # 模型偶尔会丢全角括号
    return text


# ---------- stats ----------

def cmd_stats(db_path):
    con = sqlite3.connect(db_path)
    tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    mess = [t for t in tabs if t.endswith("__mess")]
    text = [t for t in tabs if t.endswith("__text")]
    n = chars = 0
    for t in mess:
        for (v,) in con.execute(f'select Mess from "{t}"'):
            if v:
                n += 1
                chars += len(TAG_RE.sub("", v))
    tn = tc = 0
    for t in text:
        for (v,) in con.execute(f'select Text from "{t}"'):
            if v and CJK_RE.search(v):
                tn += 1
                tc += len(v)
    print(f"脚本数 {len([t for t in tabs if not t.endswith('__mess') and not t.endswith('__text')])}")
    print(f"台词 {n} 行 / {chars} 字")
    print(f"其他文本 {tn} 条 / {tc} 字（含汉字才算）")
    print(f"合计约 {chars + tc} 字")


# ---------- export ----------

def cmd_export(db_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    con = sqlite3.connect(db_path)
    tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    scripts = [t for t in tabs if not t.endswith("__mess") and not t.endswith("__text")]
    total = 0
    unreferenced = []
    for s in sorted(scripts):
        # 说话人：INST_NAME 的参数是角色 ID，name 由 characters.tsv 映射
        rows = list(con.execute(f'select Offset, InstructionString, Parameter from "{s}" order by Offset'))
        items = []
        try:
            msgs = [r[0] for r in con.execute(f'select Mess from "{s}__mess"')]
        except sqlite3.OperationalError:
            msgs = []
        idx = 0
        cur_id = None
        used = set()
        for off, ins, par in rows:
            if ins == "INST_NAME":
                if par and len(par) == 4:
                    cur_id = int.from_bytes(par, "little", signed=True)
            elif ins == "INST_TEXT":
                # 关键：INST_TEXT 的参数就是 __mess 的下标。
                # 不能用“第几条 INST_TEXT”当索引——有的脚本中间会跳号，
                # 一旦跳号，计数器方案会让整段译文错位（实测 [弐] 有 2 个脚本、368 行受影响）。
                mi = int.from_bytes(par, "little", signed=True) if par and len(par) == 4 else idx
                if 0 <= mi < len(msgs):
                    items.append({"index": mi, "char": cur_id, "jp": msgs[mi]})
                    used.add(mi)
                idx += 1
        # 记录没有被 INST_TEXT 引用的台词行（实测多为“选择支”文本，由其他指令调用）
        left = [i for i in range(len(msgs)) if i not in used and (msgs[i] or "").strip()]
        for i in left:
            items.append({"index": i, "char": None, "jp": msgs[i], "note": "未引用"})
        if left:
            unreferenced.append((s, len(left), [msgs[i] for i in left[:3]]))
        if items:
            items.sort(key=lambda x: x["index"])
            with open(os.path.join(out_dir, s + ".json"), "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=1)
            total += len(items)
    if unreferenced:
        p = os.path.join(out_dir, "_未引用台词.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("# 这些台词行没有被 INST_TEXT 指令引用，本流程不会翻译它们\n")
            f.write("# 可能由其他指令使用（选项/回想/名字），进游戏时留意是否残留日文\n")
            for s, n, sample in unreferenced:
                f.write(f"{s}\t{n} 行\t样例：{ ' | '.join(x[:30] for x in sample)}\n")
    print(f"导出 {len(scripts)} 个脚本，共 {total} 条，输出到 {out_dir}")
    if unreferenced:
        print(f"⚠ 有 {len(unreferenced)} 个脚本存在未被引用的台词，已记录到 _未引用台词.txt")


# ---------- translate ----------

def build_prompt(batch, ctx_lines, glossary, charmap):
    sys_prompt = (
        "你是资深日译中游戏本地化译者，翻译的是日本成人向视觉小说。"
        "要求：\n"
        "1. 只输出一个 JSON 对象：{\"items\":[{\"i\":序号,\"s\":\"译文\"}]}，"
        "条数、顺序与输入完全一致，不要解释，不要加代码块标记。\n"
        "2. 保留所有\u3010n\u3011（换行/注音标记）和\u3016Tn\u3017（专有名词）占位符，位置不许变、不许删、不许改。\n"
        "3. 保持口语自然，符合角色身份与语气；不要翻译腔，不要书面化，不要添加原文没有的内容。\n"
        "4. 每行长度尽量不超过原文的1.3倍，避免撑破对话框。\n"
        "5. 省略号用……，引号用「」，破折号用——，不要用英文标点。\n"
        "6. 人名/地名/专有名词严格按术语表，不得自行改写。\n"
    )
    if charmap:
        sys_prompt += "角色ID对照：" + "；".join(f"{k}={v}" for k, v in charmap.items()) + "\n"

    lines = []
    if ctx_lines:
        lines.append("【前文（仅供理解，不要翻译）】")
        for c in ctx_lines:
            lines.append(c)
        lines.append("")
    hit = [g for g in glossary if any(g[0] in (b.get("jp") or "") for b in batch)]
    if hit:
        lines.append("【术语表】")
        for jp, zh, note in hit:
            lines.append(f"{jp}\t{zh}" + (f"\t{note}" if note else ""))
        lines.append("")
    lines.append("【待译】")
    payload = [{"i": i, "s": b["jp"]} for i, b in enumerate(batch)]
    lines.append(json.dumps(payload, ensure_ascii=False))
    return sys_prompt, "\n".join(lines)


def call_api(cfg, sys_prompt, user_prompt, retry=3):
    body = {
        "model": cfg.get("model", "deepseek-v4-flash"),
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 1.0,
        "response_format": {"type": "json_object"},
    }
    if cfg.get("reasoning_effort"):
        body["reasoning_effort"] = cfg["reasoning_effort"]
    data = json.dumps(body).encode()
    url = cfg["endpoint"].rstrip("/") + "/v1/chat/completions"
    for attempt in range(retry):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + cfg["api_key"]},
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                obj = json.loads(r.read().decode())
            txt = obj["choices"][0]["message"]["content"]
            return txt
        except Exception as e:
            if attempt == retry - 1:
                raise
            time.sleep(2 * (attempt + 1))


def parse_reply(txt, n):
    """兼容 {"items":[...]} / 裸数组 / {"0":"译文"} 三种形态"""
    txt = (txt or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(json)?|```$", "", txt, flags=re.M).strip()
    obj = None
    try:
        obj = json.loads(txt)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", txt, re.S)
        if m:
            try:
                obj = json.loads(m.group(1))
            except Exception:
                obj = None
    if obj is None:
        raise ValueError("无法解析 JSON")
    if isinstance(obj, dict):
        for k in ("items", "translations", "data", "result", "list"):
            if isinstance(obj.get(k), list):
                obj = obj[k]
                break
        else:
            # {"0":"译文","1":"译文"} 形态
            try:
                keys = sorted(int(k) for k in obj.keys() if str(k).lstrip("-").isdigit())
            except Exception:
                keys = []
            if keys:
                return [str(obj.get(str(i), obj.get(i, ""))) for i in range(n)]
            raise ValueError("无法解析 JSON")
    out = {}
    for it in obj:
        if isinstance(it, dict):
            i = it.get("i", it.get("index"))
            s = it.get("s") or it.get("zh") or it.get("text") or it.get("translation") or ""
            if i is not None:
                out[int(i)] = s
        elif isinstance(it, str):
            out[len(out)] = it
    return [out.get(i, "") for i in range(n)]


def do_batch(batch, ctx, cfg, glossary, charmap, depth=0, terms=None):
    """翻译一批；解析失败就二分重试，最小到单条。
    顺序：保护控制符 -> 锁定专有名词(占位符) -> 模型翻译 -> 还原术语 -> 还原控制符"""
    prepared, tagsets, termmaps = [], [], []
    for b in batch:
        p, t = protect(b["jp"] or "")
        p, tm = lock_terms(p, terms or [])
        prepared.append({"index": b["index"], "char": b.get("char"), "jp": p})
        tagsets.append(t)
        termmaps.append(tm)
    sys_p, user_p = build_prompt(prepared, ctx, glossary, charmap)
    try:
        zh = parse_reply(call_api(cfg, sys_p, user_p), len(batch))
        good = sum(1 for z in zh if z)
        if good >= max(1, int(len(batch) * 0.6)):
            out = []
            for z, tm, t in zip(zh, termmaps, tagsets):
                z, lost = restore_terms(z or "", tm)
                if lost:
                    print(f"  ! {lost} 个术语占位符未还原（模型丢了），该行需复查")
                out.append(restore(z, t))
            return out
    except Exception:
        pass
    if len(batch) == 1 or depth >= 3:
        return [""] * len(batch)
    mid = len(batch) // 2
    left = do_batch(batch[:mid], ctx, cfg, glossary, charmap, depth + 1, terms)
    right = do_batch(batch[mid:], ctx, cfg, glossary, charmap, depth + 1, terms)
    return left + right


def translate_file(path, out_path, cfg, glossary, charmap, terms=None):
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    cache = {}
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                    cache[o["index"]] = o
                except Exception:
                    pass
    todo = [it for it in items if it["index"] not in cache or not cache[it["index"]].get("zh")]
    bs = int(cfg.get("batch_size", 12))
    cs = int(cfg.get("context_lines", 6))
    wrote = 0
    with open(out_path, "a", encoding="utf-8") as fo:
        for start in range(0, len(todo), bs):
            batch = todo[start:start + bs]
            first = items.index(batch[0])
            ctx = [x["jp"] for x in items[max(0, first - cs):first] if x.get("jp")]
            zh_list = do_batch(batch, ctx, cfg, glossary, charmap, 0, terms)
            for b, z in zip(batch, zh_list):
                rec = {"index": b["index"], "char": b.get("char"), "jp": b["jp"], "zh": z}
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
                wrote += 1
            fo.flush()
    return wrote


def cmd_translate(json_dir, out_dir):
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = load_cfg(here)
    glossary = load_tsv(os.path.join(here, cfg.get("glossary", "glossary.tsv")))
    chars = load_tsv(os.path.join(here, cfg.get("characters", "characters.tsv")))
    charmap = {c[0]: c[1] for c in chars}
    terms = load_terms(here, cfg)
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(f for f in os.listdir(json_dir) if f.endswith(".json"))
    limit = int(cfg.get("max_lines", 0) or 0)
    if limit:
        files = files  # 行数上限在下面逐文件累计
    print(f"待译脚本 {len(files)} 个；提示词术语 {len(glossary)} 条；锁定术语 {len(terms)} 条；角色 {len(charmap)} 个"
          + (f"；本次上限 {limit} 行" if limit else "；不限行数（可改 config.json 的 max_lines 设上限）"))

    done = {"n": 0}

    def job(fn):
        if limit and done["n"] >= limit:
            return 0
        src = os.path.join(json_dir, fn)
        dst = os.path.join(out_dir, fn.replace(".json", ".jsonl"))
        n = translate_file(src, dst, cfg, glossary, charmap, terms)
        done["n"] += n
        print(f"  ✓ {fn} +{n}（累计 {done['n']}）")
        return n

    total = 0
    with ThreadPoolExecutor(max_workers=int(cfg.get("concurrency", 4))) as ex:
        for n in ex.map(job, files):
            total += n
    print(f"完成，共新增 {total} 条译文")


# ---------- inject ----------

def cmd_inject(db_path, json_dir, cmap_path=None):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    done = 0
    cmap = {}
    if cmap_path and os.path.exists(cmap_path):
        with open(cmap_path, encoding="utf-8") as f:
            cmap = json.load(f)
        print(f"启用码表映射，{len(cmap)} 条（中文字符 → SJIS 占位字符）")
    else:
        cmap = {}
    tbl = str.maketrans(cmap) if cmap else None
    for fn in sorted(f for f in os.listdir(json_dir) if f.endswith(".jsonl")):
        name = fn[:-6]
        zh = {}
        with open(os.path.join(json_dir, fn), encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                    if o.get("zh"):
                        zh[o["index"]] = o["zh"]
                except Exception:
                    pass
        if not zh:
            continue
        try:
            ids = [r[0] for r in cur.execute(f'select rowid from "{name}__mess" order by rowid')]
        except sqlite3.OperationalError:
            print(f"  ! 跳过 {name}（无 __mess 表）")
            continue
        for i, rid in enumerate(ids):
            if i in zh:
                s = zh[i].translate(tbl) if tbl else zh[i]
                cur.execute(f'update "{name}__mess" set Mess=? where rowid=?', (s, rid))
                done += 1
    con.commit()
    print(f"注入完成，共 {done} 行")


# ---------- check ----------

def cmd_check(json_dir):
    issues = {"残留假名": 0, "空译": 0, "标记丢失": 0, "过长": 0, "总行": 0}
    samples = []
    for fn in sorted(f for f in os.listdir(json_dir) if f.endswith(".jsonl")):
        with open(os.path.join(json_dir, fn), encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                jp, zh = o.get("jp") or "", o.get("zh") or ""
                if not jp:
                    continue
                issues["总行"] += 1
                if not zh:
                    issues["空译"] += 1
                    continue
                if KANA_RE.search(zh):
                    issues["残留假名"] += 1
                    samples.append((fn, jp, zh))
                if len(TAG_RE.findall(jp)) != len(TAG_RE.findall(zh)):
                    issues["标记丢失"] += 1
                if len(zh) > len(TAG_RE.sub("", jp)) * 1.6 + 8:
                    issues["过长"] += 1
    print(json.dumps(issues, ensure_ascii=False, indent=1))
    for s in samples[:10]:
        print("  残留:", s[0], "|", s[1][:30], "→", s[2][:30])


def cmd_slots(json_dir, out_tsv):
    """把 H 场景（文件名带 _H）的译文抽成待填表：文件名<TAB>行号<TAB>日文<TAB>现有译文
    你只需在最后一列写成自己想要的中文，再跑 fill 即可覆盖"""
    rows = []
    for fn in sorted(f for f in os.listdir(json_dir) if f.endswith(".jsonl")):
        is_h = "_H" in fn.upper()
        with open(os.path.join(json_dir, fn), encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                rows.append([fn, o.get("index"), (o.get("jp") or "").replace("\t", " "),
                             (o.get("zh") or "").replace("\t", " "),
                             "H" if is_h else ""])
    with open(out_tsv, "w", encoding="utf-8") as f:
        f.write("文件\t行号\t日文\t现有译文\t标记\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"已导出 {len(rows)} 行到 {out_tsv}；把第4列改成你要的译文后执行 fill")


def cmd_fill(json_dir, tsv_path):
    """按表回填：只覆盖第4列与现有译文不同的行"""
    table = {}
    with open(tsv_path, encoding="utf-8") as f:
        next(f, None)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4 and p[3].strip():
                table[(p[0], int(p[1]))] = p[3]
    n = 0
    for fn in sorted(set(k[0] for k in table)):
        path = os.path.join(json_dir, fn)
        if not os.path.exists(path):
            continue
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    out.append(line.rstrip("\n"))
                    continue
                k = (fn, o.get("index"))
                if k in table and table[k] != o.get("zh"):
                    o["zh"] = table[k]
                    n += 1
                out.append(json.dumps(o, ensure_ascii=False))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    print(f"回填完成，覆盖 {n} 行")


def cmd_replace(json_dir, map_tsv):
    """全文替换：查找<TAB>替换（用于术语统一、口头禅、露骨词一键换档）"""
    pairs = []
    with open(map_tsv, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0]:
                pairs.append((p[0], p[1]))
    total = 0
    for fn in sorted(f for f in os.listdir(json_dir) if f.endswith(".jsonl")):
        path = os.path.join(json_dir, fn)
        out, n = [], 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    out.append(line.rstrip("\n"))
                    continue
                z = o.get("zh") or ""
                for a, b in pairs:
                    if a in z:
                        z = z.replace(a, b)
                        n += 1
                o["zh"] = z
                out.append(json.dumps(o, ensure_ascii=False))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        total += n
    print(f"替换完成，共 {total} 处（{len(pairs)} 条规则）")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "stats":
        cmd_stats(sys.argv[2])
    elif cmd == "export":
        cmd_export(sys.argv[2], sys.argv[3])
    elif cmd == "translate":
        cmd_translate(sys.argv[2], sys.argv[3])
    elif cmd == "inject":
        cmd_inject(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "check":
        cmd_check(sys.argv[2])
    elif cmd == "slots":
        cmd_slots(sys.argv[2], sys.argv[3])
    elif cmd == "fill":
        cmd_fill(sys.argv[2], sys.argv[3])
    elif cmd == "replace":
        cmd_replace(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
