#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 渲染器（零依赖）

把通过检查的候选项渲染成适合微信阅读的正文。

它同时是一道闸门：渲染前先跑 check_issue，渲染后再跑 check_render，
任一步存在 BLOCK 且未加 --force，就拒绝输出并退出码 1。

用法：
    zaobao_render.py <issue.json> [--repo .] [--out PATH] [--now ISO]
                                  [--force] [--json] [--quiet]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "zaobao_check", os.path.join(_HERE, "zaobao_check.py"))
zc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zc)

TOP_HEADING = "今天最值得看的{n}件事"


def _sentences(facts):
    text = ""
    for item in facts or []:
        s = str(item).strip()
        if not s:
            continue
        if s[-1] not in "。！？.!?":
            s += "。"
        text += s
    return text


def _source_lines(cand, ctx):
    srcs = [s for s in (cand.get("sources") or []) if isinstance(s, dict)]
    primary_url = str(cand.get("primary_url") or "")
    chosen, seen = [], set()
    for s in srcs:
        if str(s.get("url") or "") == primary_url:
            chosen.append(s)
            seen.add(str(s.get("url")))
            break
    if not chosen and srcs:
        chosen.append(srcs[0])
        seen.add(str(srcs[0].get("url")))
    if cand.get("evidence_status") == "VERIFIED_CROSS_SOURCE":
        for s in srcs:
            url = str(s.get("url") or "")
            if url in seen or s.get("tier") == "discovery_only":
                continue
            chosen.append(s)
            seen.add(url)
            if len(chosen) >= 2:
                break
    parts = ["[%s](%s)" % (s.get("publisher") or zc.host_of(str(s.get("url"))),
                           s.get("url")) for s in chosen]
    line = "来源：" + "、".join(parts)
    tag = cand.get("disclosure")
    if tag:
        line += "（%s）" % tag
    return line


def render_issue(issue, ctx):
    ctx = dict(ctx)
    ctx.setdefault("now", zc.now_default())
    cands, _ = zc.resolve_issue_duplicates(list(zc.iter_candidates(issue)), ctx.get("aliases"))
    output = [c for c in cands if zc.is_output(c)]

    now = ctx["now"]
    hours = ctx.get("window_hours", zc.WINDOW_HOURS)
    start = now - timedelta(hours=hours)
    run_date = str(issue.get("date") or now.strftime("%Y-%m-%d"))[:10]

    lines = ["# 早间情报 · %s" % run_date, ""]
    lines.append("统计窗口：%s → %s（北京时间）" % (
        start.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d %H:%M")))
    lines.append("")

    if not output:
        lines.append(zc.CORRECT_EMPTY_PHRASE + "。")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    top = [c for c in output if c.get("top_pick")]
    if top:
        lines.append("## " + TOP_HEADING.format(n=len(top)))
        lines.append("")
        for cand in top:
            text = str(cand.get("top_pick_line") or cand.get("title") or "").strip()
            lines.append("- " + text)
        lines.append("")

    order = [s for s in (ctx.get("sections_order") or [])]
    labels = ctx.get("sections") or {}
    for sec in order:
        group = [c for c in output if c.get("section") == sec]
        if not group:
            continue
        label = (labels.get(sec) or {}).get("label") or sec
        lines.append("## " + str(label))
        lines.append("")
        for cand in group:
            lines.append("**%s**" % str(cand.get("title") or "").strip())
            lines.append("")
            lines.append(_sentences(cand.get("body_facts")))
            lines.append("")
            bg = str(cand.get("background") or "").strip()
            if bg:
                if bg[-1] not in "。！？.!?":
                    bg += "。"
                lines.append(bg)
                lines.append("")
            lines.append(_source_lines(cand, ctx))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zaobao_render.py",
                                     description="早间情报渲染器（带自检闸门）")
    parser.add_argument("issue", help="候选 issue JSON")
    parser.add_argument("--repo", default=".", help="仓库根目录")
    parser.add_argument("--out", help="输出文件路径（默认打印到 stdout）")
    parser.add_argument("--now", help="覆盖当前时间（ISO 8601）")
    parser.add_argument("--force", action="store_true", help="存在 BLOCK 时仍输出")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出发现项")
    parser.add_argument("--quiet", action="store_true", help="不打印发现项")
    args = parser.parse_args(argv)

    repo = os.path.abspath(args.repo)
    now = zc.parse_dt(args.now) or zc.now_default()
    ctx = zc.make_ctx(repo, now=now)

    with open(args.issue, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    issue = next(zc.iter_issues(payload), {})

    pre, stats = zc.check_issue(issue, ctx)
    if zc.has_block(pre) and not args.force:
        if not args.quiet:
            print("渲染前检查未通过，已拒绝输出：", file=sys.stderr)
            zc.print_findings(pre, limit=5)
        return 1

    text = render_issue(issue, ctx)
    post = zc.check_render(text, issue, ctx)
    if zc.has_block(post) and not args.force:
        if not args.quiet:
            print("渲染后自检未通过，已拒绝输出：", file=sys.stderr)
            zc.print_findings(post, limit=5)
        return 1

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        if not args.quiet:
            print("已写入 %s" % args.out, file=sys.stderr)
    else:
        sys.stdout.write(text)

    if args.json:
        print(json.dumps({
            "stats": stats,
            "pre": zc.summarize(pre),
            "post": zc.summarize(post),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
