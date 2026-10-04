#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 变异测试（证明回归测试不是空转）

一次全绿不算证据。必须有证据表明：把某条规则破坏掉，测试会转红。

做法：
    1. 把项目复制到临时目录（绝不在仓库内做破坏）
    2. 每次只改一处
    3. 跑回归测试，比对「应当转红的步骤集合」
    4. 恢复文件，进入下一处

两种断言模式：
    expect          精确匹配 —— 转红集合必须完全等于期望集合
    expect_include  子集匹配 —— 只要求「必须包含」，用于刻意做宽的变异
                    （例如让某个检查无条件触发）。这种变异设计上就会
                    大面积转红，逐条枚举期望没有额外信息量。

用法：
    python tests/mutate.py
    python tests/mutate.py --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

CHECK = "scripts/zaobao_check.py"

MUTATIONS = [
    {
        "name": "M01 gates 字典缺键不再报错",
        "file": CHECK,
        "old": "        if key not in gates:\n",
        "new": "        if False:\n",
        "why": "「未检查 ≠ 已通过」在闸门字典这一层失效",
        "expect": {"case-09 step5"},
    },
    {
        "name": "M01b has_material_event 缺席不再报错",
        "file": CHECK,
        "old": '        if "has_material_event" not in cand:\n',
        "new": "        if False:\n",
        "why": "「未检查 ≠ 已通过」在栏目字段这一层失效",
        "expect": {"case-09 step3"},
    },
    {
        "name": "M02 时间窗外不再阻断（BLOCK 降为 INFO）",
        "file": CHECK,
        "old": 'findings.append(fnd("TIME_OUT_OF_WINDOW", BLOCK, 0, cand.get("id"),',
        "new": 'findings.append(fnd("TIME_OUT_OF_WINDOW", INFO, 0, cand.get("id"),',
        "why": "旧闻可以照常发出",
        "expect": {"case-03 step1", "case-03 step3", "case-04 step3"},
    },
    {
        "name": "M03 跨日去重失效",
        "file": CHECK,
        "old": '        if rec.get("fingerprint") != fp:\n            continue\n',
        "new": "        if True:\n            continue\n",
        "why": "同一事件可以连发三天",
        "expect": {"case-08 step1", "case-08 step2", "case-08 step3", "case-08 step4"},
    },
    {
        "name": "M04 本期内部去重失效",
        "file": CHECK,
        "old": "        if len(items) == 1:\n",
        "new": "        if True:\n",
        "why": "同一事件换标题后重复出现",
        "expect": {"case-02 step1", "case-02 step2"},
    },
    {
        "name": "M05 候选层标题党检查关闭",
        "file": CHECK,
        "old": ('    pool = _text_pool(cand)\n\n'
                '    for word in CLICKBAIT_WORDS:\n'),
        "new": ('    pool = _text_pool(cand)\n\n'
                '    for word in []:\n'),
        "why": "「重磅」「炸裂」可以进标题",
        "expect": {"case-12 step1"},
    },
    {
        "name": "M05b 渲染层标题党检查关闭",
        "file": CHECK,
        "old": ('    for word in CLICKBAIT_WORDS:\n'
                '        if word in text:\n'),
        "new": ('    for word in []:\n'
                '        if word in text:\n'),
        "why": "只在渲染文本里出现的情绪词漏网",
        "expect": {"case-12 step7"},
    },
    {
        "name": "M13 影响分析与预测检查关闭",
        "file": CHECK,
        "old": ('    for word in ANALYSIS_WORDS:\n'
                '        for seg in pool:\n'),
        "new": ('    for word in []:\n'
                '        for seg in pool:\n'),
        "why": "「利好」「要涨」可以进正文",
        "expect": {"case-12 step1", "case-12 step2"},
    },
    {
        "name": "M14 投资建议检查关闭",
        "file": CHECK,
        "old": ('    for word in ADVICE_WORDS:\n'
                '        for seg in pool:\n'),
        "new": ('    for word in []:\n'
                '        for seg in pool:\n'),
        "why": "「建议买入」可以进正文",
        "expect": {"case-12 step8"},
    },
    {
        "name": "M06 表格检查关闭",
        "file": CHECK,
        "old": "        if TABLE_LINE_RE.match(line) or TABLE_SEP_RE.match(line):\n",
        "new": "        if False:\n",
        "why": "微信阅读格式失守",
        "expect": {"case-12 step5"},
    },
    {
        "name": "M07 二手来源披露要求取消",
        "file": CHECK,
        "old": '    if tier == "SECONDARY_ONLY" and cand.get("disclosure") != DISCLOSURE_SECONDARY:\n',
        "new": "    if False:\n",
        "why": "二手报道被当成一手发出",
        "expect": {"case-05 step1"},
    },
    {
        "name": "M08 主体别名归并关闭",
        "file": CHECK,
        "old": "    for canonical, variants in aliases.items():\n",
        "new": "    for canonical, variants in {}.items():\n",
        "why": "换称呼即被当成新事件",
        "expect": {"case-02 step1", "case-02 step2", "case-08 step4"},
    },
    {
        "name": "M09 检查无条件触发（过度拦截）",
        "file": CHECK,
        "old": 'def _check_language(cand, findings):\n    title = str(cand.get("title") or "")\n',
        "new": ('def _check_language(cand, findings):\n'
                '    title = str(cand.get("title") or "")\n'
                '    findings.append(fnd("CLICKBAIT_TITLE", BLOCK, 2, title, "MUTANT"))\n'),
        "why": "把「宁可不发」变成「一律不发」",
        "expect_include": {"case-11 step1", "case-12 step6"},
    },
    {
        "name": "M10 意外但重要每日上限取消",
        "file": CHECK,
        "old": "    if len(unexp) > UNEXPECTED_MAX_PER_DAY:\n",
        "new": "    if False:\n",
        "why": "该栏目可以被灌水",
        "expect": {"case-10 step2"},
    },
    {
        "name": "M11 Top 条数上限取消",
        "file": CHECK,
        "old": ('    if len(top) > TOP_PICK_MAX:\n'
                '        findings.append(fnd("TOP3_PADDING", BLOCK, 3, "issue",'),
        "new": ('    if False:\n'
                '        findings.append(fnd("TOP3_PADDING", BLOCK, 3, "issue",'),
        "why": "Top 可以凑数",
        "expect": {"case-07 step4"},
    },
    {
        "name": "M12 搜索引擎 URL 当作来源",
        "file": CHECK,
        "old": '        hit = is_never_source(url, ctx.get("never_a_source"))\n',
        "new": "        hit = None\n",
        "why": "搜索引擎结果页可以当证据",
        "expect": {"case-12 step3"},
    },
]


def _copy_project(dest):
    def ignore(_dir, names):
        return [n for n in names
                if n in (".git", "__pycache__", ".pytest_cache", "runs", "out")]

    shutil.copytree(REPO, dest, ignore=ignore)


def _run_suite(root):
    proc = subprocess.run(
        [sys.executable, os.path.join("tests", "run_regression.py"), "--json"],
        cwd=root, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode not in (0, 1):
        raise RuntimeError("回归测试异常退出 %s\n%s\n%s" % (
            proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:]))
    return json.loads(proc.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mutate.py")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="zaobao_mut_")
    root = os.path.join(tmp, "proj")
    try:
        _copy_project(root)

        baseline = _run_suite(root)
        print("基线：%d 步，PASS=%d FAIL=%d" % (
            baseline["steps"], baseline["passed"], baseline["failed"]))
        if baseline["failed"]:
            print("基线不干净，变异测试无意义。先修回归。")
            return 2

        results, ok_count = [], 0
        for mut in MUTATIONS:
            path = os.path.join(root, mut["file"])
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
            hits = src.count(mut["old"])
            if hits != 1:
                results.append({"name": mut["name"], "status": "TARGET_MISSING",
                                "detail": "目标片段出现 %d 次（应为 1 次）" % hits})
                print("SKIP  %-34s 目标片段出现 %d 次" % (mut["name"], hits))
                continue

            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(src.replace(mut["old"], mut["new"]))
            try:
                report = _run_suite(root)
            finally:
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(src)

            observed = {"%s step%d" % (r["case"], r["step"])
                        for r in report["results"] if not r["ok"]}

            if "expect" in mut:
                mode = "精确"
                caught = observed == mut["expect"]
                detail = ("缺失=%s 多余=%s"
                          % (sorted(mut["expect"] - observed),
                             sorted(observed - mut["expect"])))
            else:
                mode = "子集"
                caught = mut["expect_include"] <= observed
                detail = "缺失=%s" % sorted(mut["expect_include"] - observed)

            status = "CAUGHT" if caught else "NOT_CAUGHT"
            if caught:
                ok_count += 1
            results.append({"name": mut["name"], "status": status, "mode": mode,
                            "observed": sorted(observed), "detail": detail})
            print("%-6s %-34s 转红 %2d 步  %s" % (
                status, mut["name"], len(observed), mode))
            if args.verbose or not caught:
                print("        why: %s" % mut["why"])
                print("        observed: %s" % sorted(observed))
                if detail.strip() != "缺失=[] 多余=[]":
                    print("        diff: %s" % detail)

        total = len([m for m in MUTATIONS])
        print()
        print("捕获 %d/%d" % (ok_count, total))
        print("MUTATION_STATUS=%s" % ("PASS" if ok_count == total else "FAIL"))
        return 0 if ok_count == total else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
