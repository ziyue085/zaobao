#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 两轮实战评估比对（零依赖）

同一时间窗口跑两遍，最容易暴露的不是规则错，而是**检索本身不稳定**。
这个脚本回答四个问题：

    same_event_overlap       两轮都发现的同一事件
    newly_added              第二轮新发现
    missing_from_second_run  第一轮有、第二轮没再发现
    decision_changed         同一事件在两轮里裁决不同

用法：
    python tests/compare_rounds.py tests/evals/round-01 tests/evals/round-02
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _load(round_dir):
    path = os.path.join(round_dir, "audit.json")
    with open(path, "r", encoding="utf-8") as fh:
        rep = json.load(fh)
    rows = {}
    for a in rep["accepted"] + rep["rejected"]:
        fp = (a.get("derived") or {}).get("fingerprint")
        if not fp:
            continue
        rows[fp] = {
            "id": a.get("id"),
            "title": a.get("title"),
            "decision": a.get("decision"),
            "section": a.get("section"),
            "declared": a.get("declared_status"),
        }
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="compare_rounds.py")
    parser.add_argument("a", help="第一轮目录")
    parser.add_argument("b", help="第二轮目录")
    parser.add_argument("--out", help="把结果写成 markdown")
    args = parser.parse_args(argv)

    ra, rb = _load(args.a), _load(args.b)
    overlap = sorted(set(ra) & set(rb))
    added = sorted(set(rb) - set(ra))
    missing = sorted(set(ra) - set(rb))
    changed = [fp for fp in overlap if ra[fp]["decision"] != rb[fp]["decision"]]

    lines = []
    lines.append("# 两轮比对 · %s vs %s" % (
        os.path.basename(args.a.rstrip("/\\")),
        os.path.basename(args.b.rstrip("/\\"))))
    lines.append("")
    lines.append("- 同一事件重叠：%d" % len(overlap))
    lines.append("- 第二轮新增：%d" % len(added))
    lines.append("- 第二轮未再发现：%d" % len(missing))
    lines.append("- 裁决发生变化：%d" % len(changed))
    lines.append("")
    lines.append("## 同一事件重叠")
    lines.append("")
    for fp in overlap:
        lines.append("- %s ← %s / %s（%s → %s）" % (
            fp, ra[fp]["id"], rb[fp]["id"], ra[fp]["decision"], rb[fp]["decision"]))
    if not overlap:
        lines.append("- （无）")
    lines.append("")
    lines.append("## 第二轮新增")
    lines.append("")
    for fp in added:
        lines.append("- [%s] %s（%s）" % (rb[fp]["section"], rb[fp]["title"], rb[fp]["decision"]))
    if not added:
        lines.append("- （无）")
    lines.append("")
    lines.append("## 第二轮未再发现")
    lines.append("")
    for fp in missing:
        lines.append("- [%s] %s（%s）" % (ra[fp]["section"], ra[fp]["title"], ra[fp]["decision"]))
    if not missing:
        lines.append("- （无）")
    lines.append("")
    lines.append("## 裁决变化")
    lines.append("")
    for fp in changed:
        lines.append("- %s：%s → %s" % (fp, ra[fp]["decision"], rb[fp]["decision"]))
    if not changed:
        lines.append("- （无）")
    lines.append("")
    text = "\n".join(lines).rstrip() + "\n"

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("已写入 %s" % args.out)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
