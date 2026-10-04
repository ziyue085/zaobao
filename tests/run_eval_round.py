#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 实战评估轮次运行器（零依赖）

把一轮真实候选集走完整条流程，并把「过程」落盘，供人工复核：

    <round>/candidates.json          人工/检索产出的原始候选（原样保留）
    <round>/candidates.resolved.json 走完 Gate 回路后的提交版本
    <round>/accepted.json            收录条目（PASS / UPDATED）
    <round>/rejected.json            丢弃条目（含丢弃理由）
    <round>/audit.md                 人看的审计报告
    <round>/audit.json               机读的审计报告
    <round>/output.md                微信版正文
    <round>/run-meta.json            本轮统计（候选数 / 各 Gate 拒绝数 / 最终条数）

为什么要有 candidates.resolved.json：
    第一遍提交时，同一事件被不同媒体转载是常态，Gate 会报 DUPLICATE_IN_ISSUE。
    正确动作是把重复条目标成 DUPLICATE，而不是绕过 Gate 硬渲染。
    两个文件都留下，是为了让"改了什么"可以核对。

用法：
    python tests/run_eval_round.py tests/evals/round-01 [--now 2026-10-04T09:00:00+08:00]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPTS = os.path.join(REPO, "scripts")


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


zc = _load("zaobao_check")
zr = _load("zaobao_render")


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# 证据/来源类阻断：命中即说明这条候选拿不出证据，正确动作是丢弃。
_EVIDENCE_BLOCKS = {
    "SEARCH_URL_AS_SOURCE", "URL_INVALID", "PRIMARY_TIER_NOT_JUSTIFIED",
    "DISCOVERY_ONLY_AS_SOLE_EVIDENCE", "INSUFFICIENT_CROSS_SOURCE",
    "PRIMARY_SOURCE_MISSING", "SOURCE_MISSING", "REJECTED_IN_OUTPUT",
    "SOURCE_TIER_INVALID", "PRIMARY_URL_MISSING", "PRIMARY_URL_NOT_IN_SOURCES",
    "EVIDENCE_STATUS_INVALID",
}


def _resolve_blocked(issue, ctx, findings):
    """把被 Gate 阻断的候选改成「不输出」—— 这是 Gate 要求的正确动作。

    只处理 scope 落在候选 id 上的 BLOCK；整期级 BLOCK（如条目数超限）
    属于编排问题，不该由单条候选背。
    """
    cand_ids = {c.get("id") for c in zc.iter_candidates(issue)}
    blocked = {}
    for f in findings:
        sc = f.get("scope")
        if f["severity"] == "BLOCK" and sc in cand_ids:
            blocked.setdefault(sc, []).append(f["code"])
    if not blocked:
        return issue, {}

    resolved = json.loads(json.dumps(issue, ensure_ascii=False))
    changes = {}
    for cand in resolved.get("candidates") or []:
        cid = cand.get("id")
        codes = blocked.get(cid)
        if not codes:
            continue
        # 已经被判为非输出终态（例如刚改判为 DUPLICATE）的条目不再重复标注，
        # 否则会把"本期内部重复"这个更准确的理由覆盖掉。
        if cand.get("status") not in zc.OUTPUT_STATUSES:
            continue
        # 改判到哪个状态，取决于 Gate 给的理由 —— 跨日重复就该是 DUPLICATE，
        # 不能一律写成 UNVERIFIED，否则重跑时 DUPLICATE_HISTORY 依旧成立。
        if "DUPLICATE_HISTORY" in codes:
            cand["status"] = "DUPLICATE"
        else:
            cand["status"] = "UNVERIFIED"
        if any(c in _EVIDENCE_BLOCKS for c in codes):
            cand["evidence_status"] = "REJECTED"
        cand.pop("top_pick", None)
        cand.pop("top_pick_line", None)
        cand["reject_reason"] = "Gate 阻断（%s），已丢弃" % "、".join(sorted(set(codes)))
        changes[cid] = sorted(set(codes))
    return resolved, changes


def _render_blocking(findings, issue):
    """渲染前仍该拦下来的 BLOCK。

    只保留两类：
      1. 整期级 BLOCK（条目数超上限之类，属于编排问题）；
      2. 落在「仍处于可输出状态」的候选上的 BLOCK。

    一条已经被判为不可输出的候选，它的结构性缺陷不再可能污染成品 ——
    再拿它拦住整期，只会让一条坏候选拖垮整期的输出。
    注意这不改变任何严重度判定：候选自身该报 BLOCK 还是报 BLOCK，
    只是编排层不再让「已丢弃的东西」决定「还出的东西」能不能出。
    """
    cands = list(zc.iter_candidates(issue))
    all_ids = {c.get("id") for c in cands}
    out_ids = {c.get("id") for c in cands if c.get("status") in zc.OUTPUT_STATUSES}
    keep = []
    for f in findings:
        if f["severity"] != zc.BLOCK:
            continue
        sc = f.get("scope")
        if sc in all_ids and sc not in out_ids:
            continue
        keep.append(f)
    return keep


def _resolve_duplicates(issue, ctx):
    """把本期内部重复条目改判为 DUPLICATE —— 这是 Gate 要求的正确动作。"""
    cands = list(zc.iter_candidates(issue))
    kept, dropped = zc.resolve_issue_duplicates(cands, ctx.get("aliases"))
    dropped_ids = {c.get("id") for c in dropped}
    keeper_of = {}
    for c in dropped:
        fp = zc.candidate_fingerprint(c, ctx.get("aliases"))
        for k in kept:
            if zc.candidate_fingerprint(k, ctx.get("aliases")) == fp:
                keeper_of[c.get("id")] = k.get("id")
                break

    resolved = json.loads(json.dumps(issue, ensure_ascii=False))
    changed = []
    for cand in resolved.get("candidates") or []:
        cid = cand.get("id")
        if cid in dropped_ids:
            cand["status"] = "DUPLICATE"
            cand["reject_reason"] = "本期内部重复，保留 %s" % keeper_of.get(cid, "?")
            cand.pop("top_pick", None)
            cand.pop("top_pick_line", None)
            changed.append(cid)
    return resolved, changed


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run_eval_round.py")
    parser.add_argument("round_dir", help="如 tests/evals/round-01")
    parser.add_argument("--now", help="覆盖当前时间（ISO 8601）")
    parser.add_argument("--history",
                        help="跨日去重用的历史 JSONL；不传则读 <round>/history.jsonl")
    args = parser.parse_args(argv)

    round_dir = os.path.abspath(args.round_dir)
    if not os.path.isdir(round_dir):
        print("目录不存在：%s" % round_dir, file=sys.stderr)
        return 2

    cand_path = os.path.join(round_dir, "candidates.json")
    with open(cand_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    issue = next(zc.iter_issues(payload), {})
    now = zc.parse_dt(args.now) or zc.now_default()

    # 跨日去重必须能喂历史记录进来，否则 Round 5 这类
    # 「Day1 PASS / Day2 DUPLICATE / Day3 UPDATED」的链路根本没法被测到。
    hist_path = args.history or os.path.join(round_dir, "history.jsonl")
    history, hist_findings = zc.load_history(hist_path)
    ctx = zc.make_ctx(REPO, now=now, history_records=history)

    # 1) 第一遍：整期检查（保留原始提交的结论，便于事后核对改了什么）
    pre, stats = zc.check_issue(issue, ctx)
    rep_first = zc.audit_issue(issue, ctx)
    _write_json(os.path.join(round_dir, "audit.firstpass.json"), rep_first)
    with open(os.path.join(round_dir, "audit.firstpass.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(zc.render_audit_md(rep_first))

    # 2) 按 Gate 要求处理本期内部重复与证据不成立的条目，得到提交版本
    resolved, dup_changed = _resolve_duplicates(issue, ctx)
    resolved, blocked_changed = _resolve_blocked(resolved, ctx, pre)
    if dup_changed or blocked_changed:
        _write_json(os.path.join(round_dir, "candidates.resolved.json"), resolved)

    # 3) 提交版本重跑全套 Gate 并出审计
    r_issue = next(zc.iter_issues(resolved), {})
    post, r_stats = zc.check_issue(r_issue, ctx)
    rep = zc.audit_issue(r_issue, ctx)
    _write_json(os.path.join(round_dir, "audit.json"), rep)
    with open(os.path.join(round_dir, "audit.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(zc.render_audit_md(rep))
    _write_json(os.path.join(round_dir, "accepted.json"), rep["accepted"])
    _write_json(os.path.join(round_dir, "rejected.json"), rep["rejected"])

    # 4) 仍有 BLOCK 就不渲染
    rendered = False
    blocking = _render_blocking(post, r_issue)
    if blocking:
        print("提交版本仍有 BLOCK，未渲染：", file=sys.stderr)
        zc.print_findings(blocking, limit=10)
    else:
        text = zr.render_issue(r_issue, ctx)
        check = zc.check_render(text, r_issue, ctx)
        if zc.has_block(check):
            print("渲染后自检未通过：", file=sys.stderr)
            zc.print_findings(check, limit=10)
        else:
            with open(os.path.join(round_dir, "output.md"), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            rendered = True

    meta = {
        "round_dir": os.path.basename(round_dir),
        "date": str(issue.get("date") or now.strftime("%Y-%m-%d"))[:10],
        "now": now.isoformat(),
        "window": {
            "start": (now - zc.timedelta(hours=ctx.get("window_hours", zc.WINDOW_HOURS))).isoformat(),
            "end": now.isoformat(),
        },
        "first_pass": {
            "summary": zc.summarize(pre),
            "stats": stats,
            "accepted_count": rep_first["accepted_count"],
            "rejected_count": rep_first["rejected_count"],
            "final_items": rep_first["final_items"],
            "rejected_by_gate": rep_first["rejected_by_gate"],
        },
        "resolved_duplicates": dup_changed,
        "resolved_blocked": blocked_changed,
        "submit_stats": r_stats,
        "submit_summary": zc.summarize(post),
        "accepted_count": rep["accepted_count"],
        "rejected_count": rep["rejected_count"],
        "accepted_by_status": rep.get("accepted_by_status", {}),
        "accepted_by_section": rep.get("accepted_by_section", {}),
        "final_items": rep["final_items"],
        "rejected_by_gate": rep["rejected_by_gate"],
        "rendered": rendered,
    }
    _write_json(os.path.join(round_dir, "run-meta.json"), meta)

    print("候选总数         %d" % stats.get("candidates", 0))
    print("首轮：BLOCK=%d WARN=%d INFO=%d" % (
        sum(1 for x in pre if x["severity"] == "BLOCK"),
        sum(1 for x in pre if x["severity"] == "WARN"),
        sum(1 for x in pre if x["severity"] == "INFO")))
    print("本期内部重复改判 %s" % (dup_changed or "无"))
    print("被阻断改判丢弃   %s" % (blocked_changed or "无"))
    print("收录 / 丢弃      %d / %d" % (rep["accepted_count"], rep["rejected_count"]))
    print("最终条目数       %d" % rep["final_items"])
    print("各 Gate 拒绝数   %s" % json.dumps(rep["rejected_by_gate"], ensure_ascii=False))
    print("已渲染 output.md %s" % ("是" if rendered else "否"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
