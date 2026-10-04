#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 回归测试运行器

用法：
    python tests/run_regression.py                 # 跑全部用例
    python tests/run_regression.py --only case-03  # 只跑一个
    python tests/run_regression.py --json          # 机器可读结果
    python tests/run_regression.py --list          # 列出用例

断言全部按「规则 code」进行，而不是按提示文字。
另外会自动扫描 zaobao_check.py 中所有 fnd("CODE" 的出现，
构造 KNOWN_CODES，供反向对照用例断言「一个已知 code 都没触发」。
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CASES_DIR = os.path.join(HERE, "cases")

CHECK_PY = os.path.join(REPO, "scripts", "zaobao_check.py")
RENDER_PY = os.path.join(REPO, "scripts", "zaobao_render.py")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


zc = _load("zaobao_check", CHECK_PY)
zr = _load("zaobao_render", RENDER_PY)

with open(CHECK_PY, "r", encoding="utf-8") as fh:
    _SRC = fh.read()
KNOWN_CODES = sorted(set(re.findall(r'fnd\(\s*"([A-Z][A-Z0-9_]*)"', _SRC)))


class Failure(Exception):
    pass


def _codes(findings, severity=None):
    return [f["code"] for f in findings if severity is None or f["severity"] == severity]


def _by_code(findings):
    out = {}
    for f in findings:
        out.setdefault(f["code"], []).append(f)
    return out


def _require(cond, msg):
    if not cond:
        raise Failure(msg)


def _subset(needle, hay, what):
    missing = sorted(set(needle) - set(hay))
    _require(not missing, "%s 缺少预期 code：%s（实际：%s）" % (what, missing, sorted(set(hay))))


def _disjoint(bad, hay, what):
    hit = sorted(set(bad) & set(hay))
    _require(not hit, "%s 出现不应存在的 code：%s" % (what, hit))


def _expand(payload, spec_list):
    """按 step 的 expand 声明批量复制候选，用于测试数量类规则。

    spec: {"template": {...}, "count": n, "id_prefix": "x"}
    复制时把 id 与 entity/object 加上序号，避免被本期内部去重合并。
    """
    if not spec_list:
        return payload
    payload = json.loads(json.dumps(payload))
    for spec in spec_list:
        tpl = spec.get("template") or {}
        prefix = spec.get("id_prefix", "x")
        for i in range(1, int(spec.get("count", 0)) + 1):
            cand = json.loads(json.dumps(tpl))
            cand["id"] = "%s%d" % (prefix, i)
            cand["entity"] = "%s%d" % (cand.get("entity", ""), i)
            cand["object"] = "%s%d" % (cand.get("object", ""), i)
            payload.setdefault("candidates", []).append(cand)
    return payload


def run_step(case, step, index):
    """执行一个 step，返回 (ok, notes)。"""
    notes = []
    now = step.get("now") or case.get("now")
    history = step.get("history", case.get("history")) or []
    payload = _expand(step.get("input") or {}, step.get("expand"))
    expect = step.get("expect") or {}

    ctx = zc.make_ctx(REPO, now=zc.parse_dt(now), history_records=history)
    findings, stats = zc.check_issue(payload, ctx)

    # 渲染层：只要该 step 声明了任何 render_* 断言，或给了 render_text，就跑。
    needs_render = ("render_text" in step
                    or any(k.startswith("render_") for k in expect))
    text, rfind = None, []
    if needs_render:
        text = step["render_text"] if "render_text" in step else zr.render_issue(payload, ctx)
        rfind = zc.check_render(text, payload, ctx)

    # code 集合断言：渲染层的 code 与规则层一起看，避免「断言写对了地方却查了错的集合」。
    combined = _codes(findings) + _codes(rfind)

    if "block_count" in expect:
        got = len(_codes(findings, zc.BLOCK))
        _require(got == expect["block_count"],
                 "BLOCK 数不符：期望 %s，实际 %s → %s" % (
                     expect["block_count"], got, _codes(findings, zc.BLOCK)))
    if "warn_count" in expect:
        got = len(_codes(findings, zc.WARN))
        _require(got == expect["warn_count"],
                 "WARN 数不符：期望 %s，实际 %s → %s" % (
                     expect["warn_count"], got, _codes(findings, zc.WARN)))
    if "info_count" in expect:
        got = len(_codes(findings, zc.INFO))
        _require(got == expect["info_count"],
                 "INFO 数不符：期望 %s，实际 %s → %s" % (
                     expect["info_count"], got, _codes(findings, zc.INFO)))

    if "block_codes" in expect:
        _subset(expect["block_codes"], _codes(findings, zc.BLOCK), "BLOCK")
    if "warn_codes" in expect:
        _subset(expect["warn_codes"], _codes(findings, zc.WARN), "WARN")
    if "any_codes" in expect:
        _subset(expect["any_codes"], combined, "全部发现（规则层 + 渲染层）")
    if "absent_codes" in expect:
        _disjoint(expect["absent_codes"], combined, "全部发现（规则层 + 渲染层）")
    if "block_codes_absent" in expect:
        _disjoint(expect["block_codes_absent"], _codes(findings, zc.BLOCK), "BLOCK")

    for code, sev in (expect.get("severity") or {}).items():
        if sev is None:
            _disjoint([code], combined, "全部发现")
        else:
            all_by_code = _by_code(findings + rfind)
            _require(code in all_by_code,
                     "未出现期望的 code：%s（实际：%s）" % (code, sorted(set(combined))))
            actual = all_by_code[code][0]["severity"]
            _require(actual == sev, "%s 严重度不符：期望 %s，实际 %s" % (code, sev, actual))

    for key, want in (expect.get("stats") or {}).items():
        _require(stats.get(key) == want,
                 "stats.%s 不符：期望 %s，实际 %s" % (key, want, stats.get(key)))

    cands = list(zc.iter_candidates(payload))
    by_id = {c.get("id"): c for c in cands}

    if "fingerprint_same" in expect:
        for a, b in expect["fingerprint_same"]:
            fa = zc.candidate_fingerprint(by_id[a], ctx.get("aliases"))
            fb = zc.candidate_fingerprint(by_id[b], ctx.get("aliases"))
            _require(fa == fb, "%s / %s 的 fingerprint 应相同：%s vs %s" % (a, b, fa, fb))

    if "fingerprint_equals" in expect:
        for cid, want in expect["fingerprint_equals"].items():
            got = zc.candidate_fingerprint(by_id[cid], ctx.get("aliases"))
            _require(got == want, "%s 的 fingerprint 不符：期望 %s，实际 %s" % (cid, want, got))

    if "kept_id" in expect:
        kept, _ = zc.resolve_issue_duplicates(cands, ctx.get("aliases"))
        kept_ids = [c.get("id") for c in kept]
        _require(expect["kept_id"] in kept_ids,
                 "去重后应保留 %s，实际保留 %s" % (expect["kept_id"], kept_ids))

    if needs_render:
        if "render_block_count" in expect:
            got = len(_codes(rfind, zc.BLOCK))
            _require(got == expect["render_block_count"],
                     "渲染 BLOCK 数不符：期望 %s，实际 %s → %s" % (
                         expect["render_block_count"], got, _codes(rfind, zc.BLOCK)))
        if "render_warn_count" in expect:
            got = len(_codes(rfind, zc.WARN))
            _require(got == expect["render_warn_count"],
                     "渲染 WARN 数不符：期望 %s，实际 %s → %s" % (
                         expect["render_warn_count"], got, _codes(rfind, zc.WARN)))
        if "render_codes" in expect:
            _subset(expect["render_codes"], _codes(rfind), "渲染发现")
        if "render_absent_codes" in expect:
            _disjoint(expect["render_absent_codes"], _codes(rfind), "渲染发现")
        if "render_contains" in expect:
            for needle in expect["render_contains"]:
                _require(needle in text, "渲染结果缺少：%s" % needle)
        if "render_excludes" in expect:
            for needle in expect["render_excludes"]:
                _require(needle not in text, "渲染结果不应包含：%s" % needle)

    if expect.get("absent_all_known_codes"):
        _disjoint(KNOWN_CODES, combined, "反向对照（规则层 + 渲染层）")
        notes.append("KNOWN_CODES=%d 全部未触发" % len(KNOWN_CODES))

    return notes


def load_cases(only=None):
    cases = []
    for path in sorted(glob.glob(os.path.join(CASES_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as fh:
            case = json.load(fh)
        if only and case.get("id") != only:
            continue
        cases.append((path, case))
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run_regression.py")
    parser.add_argument("--only", help="只跑指定 case id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    cases = load_cases(args.only)
    if args.list:
        for _, c in cases:
            print("%-9s %-2d steps  %s" % (c.get("id"), len(c.get("steps") or []),
                                           c.get("title")))
        return 0
    if not cases:
        print("没有找到用例")
        return 2

    results, total_steps, failed = [], 0, 0
    for path, case in cases:
        cid = case.get("id")
        case_ok = True
        for i, step in enumerate(case.get("steps") or [], 1):
            total_steps += 1
            label = "%s step%d" % (cid, i)
            try:
                notes = run_step(case, step, i)
                results.append({"case": cid, "step": i, "ok": True,
                                "desc": step.get("desc"), "notes": notes})
                if not args.json:
                    print("PASS  %-16s %s" % (label, step.get("desc") or ""))
                    if args.verbose:
                        for n in notes:
                            print("        · %s" % n)
            except Failure as exc:
                case_ok = False
                failed += 1
                results.append({"case": cid, "step": i, "ok": False,
                                "desc": step.get("desc"), "error": str(exc)})
                if not args.json:
                    print("FAIL  %-16s %s" % (label, step.get("desc") or ""))
                    print("        ✗ %s" % exc)
            except Exception as exc:  # noqa: BLE001
                case_ok = False
                failed += 1
                results.append({"case": cid, "step": i, "ok": False,
                                "desc": step.get("desc"),
                                "error": "%s: %s" % (type(exc).__name__, exc)})
                if not args.json:
                    print("ERROR %-16s %s" % (label, step.get("desc") or ""))
                    print("        ✗ %s: %s" % (type(exc).__name__, exc))
        if not args.json:
            print("      %-16s %s" % (cid, "OK" if case_ok else "FAILED"))

    passed = total_steps - failed
    if args.json:
        print(json.dumps({
            "cases": len(cases),
            "steps": total_steps,
            "passed": passed,
            "failed": failed,
            "known_codes": KNOWN_CODES,
            "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print()
        print("用例 %d 个 / 断言步骤 %d 步：PASS=%d FAIL=%d" % (
            len(cases), total_steps, passed, failed))
        print("REGRESSION_STATUS=%s" % ("PASS" if failed == 0 else "FAIL"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
