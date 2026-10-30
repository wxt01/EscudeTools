#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成待处理清单 —— 双击「生成待处理清单.bat」运行

翻译跑完后跑一次，会在本目录生成「待处理清单.txt」，
把我处理得保守、拿不准、或干脆没处理的东西全部列出来，你照着补就行。
"""

import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import paths

_D = paths.dirs(cli=(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None))
CN_DIR = _D["json_cn"]
OUT = os.path.join(_D["root"], "待处理清单.txt")

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
TAG = re.compile(r"<[^>]{1,16}>")
RUBY = re.compile(r"<ruby[^>]*>(.*?)</ruby>")
# 喘息/拟声特征
MOAN = re.compile(r"(あ[ぁァ]|ん[っッ]|は[ぁァ]|く[っッ]|ぁ|ぃ|う[ぅゥ]|お[ぉォ])")
# 成人向常见词（判断是否 H 段落）
NSFW = re.compile(r"(気持ち|挿|中出|膣|乳|腰|舐|舐め|咥|精|濡|絶頂|イか|イク|孕|犯|肉|奥|奥さん)")


def load_rows():
    """同一 (文件, 行号) 可能因重试出现多条，取最后一条非空译文"""
    rows = []
    if not os.path.isdir(CN_DIR):
        return rows
    for fn in sorted(f for f in os.listdir(CN_DIR) if f.endswith(".jsonl")):
        best = {}
        with open(os.path.join(CN_DIR, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                k = o.get("index")
                old = best.get(k)
                if old is None or (not old.get("zh") and o.get("zh")):
                    best[k] = o
                elif old.get("zh") and not o.get("zh"):
                    pass
                else:
                    best[k] = o
        for k in sorted(best, key=lambda x: (x is None, x)):
            o = best[k]
            o["_file"] = fn
            rows.append(o)
    return rows


def main():
    rows = load_rows()
    if not rows:
        print(f"没找到译文，请确认目录：{CN_DIR}")
        return

    # 读角色表，判断说话人是否已知
    known_ids = set()
    db = os.path.join(_D["pristine"], "db_scripts.db")
    if os.path.exists(db):
        import sqlite3
        try:
            c = sqlite3.connect(db)
            tbl = (_D["cfg"].get("data", {}) or {}).get("name_table", "登場人物_01")
            n = c.execute(f'select count(*) from "{tbl}"').fetchone()[0]
            known_ids = set(range(n + 1))
        except Exception:
            known_ids = set()

    buckets = {
        "h": [],        # H 段落
        "moan": [],     # 拟声词
        "long": [],     # 可能溢出
        "ruby": [],     # 注音被简化
        "unknown": [],  # 说话人未识别
        "empty": [],    # 空译
        "jpleft": [],   # 残留日文
    }

    for o in rows:
        jp = o.get("jp") or ""
        zh = o.get("zh") or ""
        fn = o.get("_file", "")
        idx = o.get("index", 0)
        is_h_file = "_H" in fn.upper()
        plain_jp = TAG.sub("", jp)

        if not zh:
            buckets["empty"].append((fn, idx, jp, zh))
            continue
        if KANA.search(zh):
            buckets["jpleft"].append((fn, idx, jp, zh))
        if is_h_file or NSFW.search(plain_jp):
            buckets["h"].append((fn, idx, jp, zh))
        if MOAN.search(plain_jp) and len(plain_jp) < 40:
            buckets["moan"].append((fn, idx, jp, zh))
        if len(TAG.sub("", zh)) > len(plain_jp) * 1.6 + 10 and len(TAG.sub("", zh)) > 40:
            buckets["long"].append((fn, idx, jp, zh))
        if RUBY.search(jp) and "<ruby" not in zh:
            buckets["ruby"].append((fn, idx, jp, zh))
        cid = o.get("char")
        if cid is not None and known_ids and cid not in known_ids and zh:
            buckets["unknown"].append((fn, idx, jp, zh))

    def sec(title, key, advice, limit=12):
        items = buckets[key]
        lines.append("")
        lines.append(f"【{title}】{len(items)} 行")
        if advice:
            lines.append(f"  处理建议：{advice}")
        if items:
            files = len(set(i[0] for i in items))
            lines.append(f"  涉及 {files} 个脚本文件")
            for fn, idx, jp, zh in items[:limit]:
                lines.append(f"    · [{fn} 第{idx}行]")
                lines.append(f"      日文：{jp[:90]}")
                lines.append(f"      译文：{zh[:90]}")
            if len(items) > limit:
                lines.append(f"    …… 还有 {len(items) - limit} 行，见对应 jsonl 文件")

    lines = []
    lines.append("=" * 66)
    lines.append("待处理清单")
    lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"译文总量：{len(rows)} 行")
    lines.append("=" * 66)
    lines.append("")
    lines.append("下面是「我处理得保守 / 拿不准 / 没处理」的内容。")
    lines.append("改动方式：双击「替换工具.bat」输入词就能批量换；单句精修直接改项目里的译文目录（默认 3_json_cn）。")
    lines.append("改完跑一句 python scripts\\build.py --no-gfx 就会重新出包（改到字库才需要不带 --no-gfx）。")
    lines.append("")
    lines.append("【速览】")
    lines.append(f"  成人向描写（可加浓）      {len(buckets['h'])} 行")
    lines.append(f"  拟声词/喘息（建议过一遍）  {len(buckets['moan'])} 行")
    lines.append(f"  可能溢出对话框            {len(buckets['long'])} 行")
    lines.append(f"  注音被简化                {len(buckets['ruby'])} 行")
    lines.append(f"  说话人未识别              {len(buckets['unknown'])} 行")
    lines.append(f"  空译/失败                 {len(buckets['empty'])} 行")
    lines.append(f"  残留日文                  {len(buckets['jpleft'])} 行")

    sec("一、成人向描写：我按保守口径处理，你可以自行加浓", "h",
        "这些行我做的是「能读、不别扭」的版本，露骨度和用词偏克制。想要更贴近原作的强度，用替换工具批量换词，或逐行改。")

    sec("二、拟声词/喘息：节奏拿不准，建议你过一遍", "moan",
        "日语拟声词没有固定中译，我按常见处理（はぁ→哈啊、んっ→唔嗯）。同一角色前后不一致的，用替换工具统一。")

    sec("三、可能撑破对话框的长句", "long",
        "中文超过原文 1.6 倍，进游戏可能顶到框外。建议缩短或手动断行（用 <r> 换行）。")

    sec("四、原文的假名注音已去掉", "ruby",
        "日文原文在生僻词上有假名小字（ruby），中文没有注音习惯，我统一去掉、只留汉字。如果你希望某些词保留注音，需要单独指定。")

    lines.append("")
    lines.append(f"【五、说话人没认出来，语气可能跑偏】{len(buckets['unknown'])} 行")
    if buckets["unknown"]:
        from collections import Counter
        cnt = Counter(o.get("char") for o in rows if o.get("char") is not None and o["char"] not in known_ids and o.get("zh"))
        lines.append("  处理建议：打开 characters.tsv，把这些 ID 补上中文名（格式：ID<TAB>名字<TAB>备注），")
        lines.append("           然后删掉这些行的缓存重翻，语气会准很多。")
        lines.append("  未登记的 ID 及行数：" + "、".join(f"{k}（{v}行）" for k, v in cnt.most_common(15)))
        for fn, idx, jp, zh in buckets["unknown"][:5]:
            lines.append(f"    · [{fn} 第{idx}行] {jp[:60]} → {zh[:60]}")

    sec("六、空译 / 翻译失败，需要重跑", "empty",
        "这些行没有译文，游戏里会显示空白。删掉对应缓存行重跑即可。")

    sec("七、残留日文，需要修", "jpleft",
        "译文中还有假名，多为语气词或未译的专有名词。")

    lines.append("")
    lines.append("-" * 66)
    lines.append("【八、本流程从头到尾没有处理的内容】")
    lines.append("")
    lines.append("1. 图片里的文字（未处理）")
    lines.append("   标题 LOGO、UI 按钮底图、菜单图标、CG 内嵌字、STAFF 名单图 —— 这些是图片，")
    lines.append("   改文本无用，需要逐张重绘。见 docs/05-界面图汉化.md 的适用范围。")
    lines.append("2. 视频与歌词（未处理）")
    lines.append("   OP/ED 视频里的字幕、主题曲歌词 —— 需要听译 + 字幕压制。")
    lines.append("3. 字体观感（有差异）")
    lines.append("   本版位图字库由系统字体渲染，与其他汉化补丁的字库相比：")
    lines.append("   字重偏粗、字距略松。功能上不缺字，观感上细看能看出差别。")
    lines.append("4. 特殊符号")
    lines.append("   音符 ♪ 一类符号在中文字体里可能没有字形，未覆盖的格子会沿用原字形，")
    lines.append("   位置正常；但若某行同时含中文与符号，视觉上会有点不统一。")
    lines.append("5. 引擎硬编码文本")
    lines.append("   极少数引擎内部提示（如启动失败弹窗）写在程序里，不在数据文件中，未处理。")
    lines.append("6. 语音/音效")
    lines.append("   语音仍为原音，未做中文配音。")
    lines.append("")
    lines.append("【九、本版实际覆盖到的范围】")
    lines.append(f"   台词 {len(rows)} 行（含成人向场景，全部经过处理）")
    lines.append("   角色名与界面文本：视项目配置而定（names_zh.json / ui_zh.json 有则写入）")
    lines.append("   字库：按译文实际用字生成，见 5_build/cmap/cmap.json")
    lines.append("-" * 66)
    lines.append("清单生成完毕。")

    text = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"\n已写入：{OUT}")


if __name__ == "__main__":
    main()
