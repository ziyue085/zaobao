#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 输出可读性检查（零依赖）

为什么单独做一层检查：
    Gate 只保证"这条能不能发"，不保证"发出去读不读得下去"。
    早报的实际使用场景是在微信里几分钟扫完，所以排版与句长是硬指标，
    不能靠人肉眼每次去数。

检查项（与任务书第二十一节逐条对应）：
    1. 标题短      —— 每个加粗标题不超过 MAX_TITLE 个字符
    2. 每条 1—3 句 —— 每个正文段落按中文句读切分，句数不超过 MAX_SENTENCES
    3. 无超长段落  —— 单段不超过 MAX_PARA 个字符
    4. 无 Markdown 表格 —— 出现 |---| 分隔行即判失败
    5. 链接可点击  —— 来源链接必须是 http(s) 绝对地址，不得是相对路径或裸文本
    6. 读得完      —— 按 300 字/分钟估算，整期不超过 MAX_MINUTES 分钟

用法：
    python tests/check_output_readability.py
    python tests/check_output_readability.py --json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EVAL_DIR = os.path.join(REPO, "tests", "evals")

MAX_TITLE = 30          # 标题字符数上限
MAX_SENTENCES = 3       # 每段句数上限
MAX_PARA = 180          # 单段字符数上限
MAX_MINUTES = 5.0       # 整期阅读时长上限（分钟）
CPM = 300.0             # 中文阅读速度估算：300 字/分钟

_SENT_SPLIT = re.compile(r"[。！？!?；;]")
_BOLD_TITLE = re.compile(r"^\*\*(.+?)\*\*$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}")


def _sentences(text):
    parts = [p for p in _SENT_SPLIT.split(text) if p.strip()]
    return parts or ([text] if text.strip() else [])


def check_text(md, label):
    """返回 (issues, metrics)。issues 是 [(level, code, detail)]。"""
    issues = []
    titles, paras, links = [], [], []

    for raw in md.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        m = _BOLD_TITLE.match(line)
        if m:
            titles.append(m.group(1).strip())
            continue
        if _TABLE_SEP.match(line) and "|" in line:
            issues.append(("FAIL", "MD_TABLE", "出现 Markdown 表格分隔行：%s" % line[:40]))
            continue
        if line.startswith("- ") or line.startswith("* "):
            # top_pick 摘要行，按短句处理，不计入段落长度
            continue
        if line.startswith("来源：") or line.startswith("统计窗口："):
            for _, url in _LINK.findall(line):
                links.append(url)
            continue
        paras.append(line)
        for _, url in _LINK.findall(line):
            links.append(url)

    for t in titles:
        if len(t) > MAX_TITLE:
            issues.append(("FAIL", "TITLE_TOO_LONG",
                           "标题 %d 字 > %d：%s" % (len(t), MAX_TITLE, t)))

    for p in paras:
        n = len(_sentences(p))
        if n > MAX_SENTENCES:
            issues.append(("FAIL", "TOO_MANY_SENTENCES",
                           "段落 %d 句 > %d：%s…" % (n, MAX_SENTENCES, p[:32])))
        if len(p) > MAX_PARA:
            issues.append(("FAIL", "PARA_TOO_LONG",
                           "段落 %d 字 > %d：%s…" % (len(p), MAX_PARA, p[:32])))

    for u in links:
        if not re.match(r"^https?://", u):
            issues.append(("FAIL", "LINK_NOT_CLICKABLE", "非绝对地址链接：%s" % u[:60]))

    body = "".join(titles) + "".join(paras)
    minutes = round(len(body) / CPM, 2)
    if minutes > MAX_MINUTES:
        issues.append(("FAIL", "TOO_LONG_TO_READ",
                       "估算 %.2f 分钟 > %.1f 分钟" % (minutes, MAX_MINUTES)))

    metrics = {
        "round": label,
        "titles": len(titles),
        "max_title_len": max([len(t) for t in titles], default=0),
        "paragraphs": len(paras),
        "max_sentences": max([len(_sentences(p)) for p in paras], default=0),
        "max_para_len": max([len(p) for p in paras], default=0),
        "links": len(links),
        "chars": len(body),
        "est_minutes": minutes,
        "issues": issues,
    }
    return issues, metrics


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check_output_readability.py")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dir", default=EVAL_DIR)
    args = parser.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.dir, "*", "output.md")))
    if not files:
        print("没找到任何 output.md", file=sys.stderr)
        return 2

    results, failed = [], 0
    for path in files:
        label = os.path.basename(os.path.dirname(path))
        with open(path, "r", encoding="utf-8") as fh:
            md = fh.read()
        issues, metrics = check_text(md, label)
        results.append(metrics)
        if issues:
            failed += 1

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for m in results:
            status = "FAIL" if m["issues"] else "PASS"
            print("%-16s %s  条=%d 标题≤%d字 段落≤%d句/%d字 链接=%d 约%.2f分钟" % (
                m["round"], status, m["titles"], m["max_title_len"],
                m["max_sentences"], m["max_para_len"], m["links"],
                m["est_minutes"]))
            for lvl, code, detail in m["issues"]:
                print("      - [%s] %s：%s" % (lvl, code, detail))
        print("")
        print("TERMINAL_STATUS=%s  通过 %d / 共 %d" % (
            "FAIL" if failed else "PASS", len(results) - failed, len(results)))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
