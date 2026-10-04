#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 实战评估汇总（零依赖）

把每轮人工复核的标签（tests/evals/<round>/labels.json）汇总成一份可比较的记分卡。

为什么不用代码覆盖率当 KPI：
    规则层的行覆盖率再高，也回答不了"这份早报读起来到底行不行"。
    这份汇总统计的是真实使用效果：误收、漏收、来源可靠性、重复、旧闻。

用法：
    python tests/run_eval_summary.py
    python tests/run_eval_summary.py --out tests/evals/EVAL_SUMMARY.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EVAL_DIR = os.path.join(REPO, "tests", "evals")

LABELS = [
    "GOOD", "SHOULD_NOT_INCLUDE", "BAD_SOURCE", "OLD",
    "DUPLICATE", "TOO_VERBOSE", "WRONG_CATEGORY", "UNVERIFIED",
]


def _load_rounds():
    rounds = []
    if not os.path.isdir(EVAL_DIR):
        return rounds
    for name in sorted(os.listdir(EVAL_DIR)):
        path = os.path.join(EVAL_DIR, name, "labels.json")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            rounds.append((name, json.load(fh)))
    return rounds


def aggregate(rounds):
    rows, totals = [], dict.fromkeys(LABELS, 0)
    totals["TOTAL_OUTPUT_ITEMS"] = 0
    totals["MISSED_IMPORTANT"] = 0
    for name, data in rounds:
        counts = dict.fromkeys(LABELS, 0)
        items = data.get("items") or []
        for it in items:
            lab = str(it.get("label") or "UNVERIFIED").upper()
            if lab not in counts:
                lab = "UNVERIFIED"
            counts[lab] += 1
        missed = len(data.get("missed_important") or [])
        issue_note = data.get("issue_note")
        row = {
            "round": name,
            "date": data.get("date"),
            "TOTAL_OUTPUT_ITEMS": len(items),
            "MISSED_IMPORTANT": missed,
            "ISSUE_NOTE": issue_note,
        }
        row.update(counts)
        goods = counts["GOOD"]
        row["GOOD_RATE"] = round(goods / len(items), 3) if items else None
        rows.append(row)

        totals["TOTAL_OUTPUT_ITEMS"] += len(items)
        totals["MISSED_IMPORTANT"] += missed
        for lab in LABELS:
            totals[lab] += counts[lab]
    if totals["TOTAL_OUTPUT_ITEMS"]:
        totals["GOOD_RATE"] = round(
            totals["GOOD"] / totals["TOTAL_OUTPUT_ITEMS"], 3)
    else:
        totals["GOOD_RATE"] = None
    return rows, totals


def render_md(rows, totals):
    lines = ["# 实战评估记分卡", ""]
    lines.append("统计口径：只看真实产出的每一条内容，逐条人工打标签。")
    lines.append("")
    lines.append("## 逐轮")
    lines.append("")
    header = ["轮次", "日期", "输出条数", "GOOD", "误收", "来源差",
              "旧闻", "重复", "过长", "错栏", "未核实", "漏收重要", "GOOD_RATE"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for r in rows:
        lines.append("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d | %s |" % (
            r["round"], r.get("date") or "", r["TOTAL_OUTPUT_ITEMS"],
            r["GOOD"], r["SHOULD_NOT_INCLUDE"], r["BAD_SOURCE"], r["OLD"],
            r["DUPLICATE"], r["TOO_VERBOSE"], r["WRONG_CATEGORY"],
            r["UNVERIFIED"], r["MISSED_IMPORTANT"],
            "—" if r["GOOD_RATE"] is None else "%.2f" % r["GOOD_RATE"]))
    lines.append("")
    lines.append("## 合计")
    lines.append("")
    lines.append("- TOTAL_OUTPUT_ITEMS：%d" % totals["TOTAL_OUTPUT_ITEMS"])
    lines.append("- GOOD_ITEMS：%d" % totals["GOOD"])
    lines.append("- SHOULD_NOT_INCLUDE：%d" % totals["SHOULD_NOT_INCLUDE"])
    lines.append("- BAD_SOURCE：%d" % totals["BAD_SOURCE"])
    lines.append("- OLD_ITEMS：%d" % totals["OLD"])
    lines.append("- DUPLICATE_ITEMS：%d" % totals["DUPLICATE"])
    lines.append("- TOO_VERBOSE：%d" % totals["TOO_VERBOSE"])
    lines.append("- WRONG_CATEGORY：%d" % totals["WRONG_CATEGORY"])
    lines.append("- UNVERIFIED：%d" % totals["UNVERIFIED"])
    lines.append("- MISSED_IMPORTANT：%d" % totals["MISSED_IMPORTANT"])
    lines.append("- GOOD_RATE：%s" % (
        "—" if totals["GOOD_RATE"] is None else "%.2f" % totals["GOOD_RATE"]))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run_eval_summary.py")
    parser.add_argument("--out", default=os.path.join(EVAL_DIR, "EVAL_SUMMARY.md"))
    args = parser.parse_args(argv)

    rounds = _load_rounds()
    if not rounds:
        print("没有找到任何 labels.json，先跑 run_eval_round.py 并人工打标签。",
              file=sys.stderr)
        return 2
    rows, totals = aggregate(rounds)
    md = render_md(rows, totals)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    with open(os.path.join(EVAL_DIR, "EVAL_SUMMARY.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump({"rounds": rows, "totals": totals}, fh,
                  ensure_ascii=False, indent=2)
        fh.write("\n")
    sys.stdout.write(md)
    print("已写入 %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
