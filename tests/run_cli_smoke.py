#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 命令行端到端冒烟测试

回归测试跑的是规则函数；这个脚本跑的是**真实的命令行入口**，
覆盖库测试覆盖不到的部分：

    - check-config / fingerprint / record / prune / check-issue / check-render
    - 历史文件真的被写入、真的被裁剪
    - 渲染器在存在 BLOCK 时真的拒绝输出
    - 内置 YAML 子集解析器与 PyYAML 结果一致（回退路径不能只是"看起来能跑"）

用法：
    python tests/run_cli_smoke.py
    python tests/run_cli_smoke.py --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CASES = os.path.join(HERE, "cases")

CHECK = os.path.join(REPO, "scripts", "zaobao_check.py")
RENDER = os.path.join(REPO, "scripts", "zaobao_render.py")

RESULTS = []


def run(args, cwd=None):
    proc = subprocess.run([sys.executable] + args, cwd=cwd or REPO,
                          capture_output=True, text=True, encoding="utf-8")
    return proc


def run_json(args, cwd=None):
    proc = run(args + ["--json"], cwd)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError("无法解析 JSON 输出：\nSTDOUT=%s\nSTDERR=%s"
                             % (proc.stdout[-1500:], proc.stderr[-1500:]))
    return proc.returncode, payload


def check(name, cond, detail=""):
    RESULTS.append({"name": name, "ok": bool(cond), "detail": detail})
    return bool(cond)


def step_input(case_file, index, tmp):
    with open(os.path.join(CASES, case_file), "r", encoding="utf-8") as fh:
        case = json.load(fh)
    step = case["steps"][index]
    path = os.path.join(tmp, "%s_%d.json" % (case["id"], index + 1))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(step["input"], fh, ensure_ascii=False, indent=2)
    return path, (step.get("now") or case.get("now"))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run_cli_smoke.py")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="zaobao_cli_")
    try:
        # 1. 配置自检
        rc, payload = run_json([CHECK, "check-config", "--repo", REPO])
        check("check-config 无 BLOCK", payload["summary"]["block"] == 0,
              json.dumps(payload["summary"], ensure_ascii=False))
        check("check-config 无 WARN", payload["summary"]["warn"] == 0,
              json.dumps(payload["summary"], ensure_ascii=False))

        # 2. 内置 YAML 解析器与 PyYAML 一致性（回退路径）
        try:
            import yaml  # noqa: F401
            has_yaml = True
        except ImportError:
            has_yaml = False
        if has_yaml:
            sys.path.insert(0, os.path.join(REPO, "scripts"))
            import importlib.util
            spec = importlib.util.spec_from_file_location("zc_smoke", CHECK)
            zc = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(zc)
            same_all = True
            for name in ("watchlist.yaml", "sources.yaml"):
                with open(os.path.join(REPO, "config", name), "r", encoding="utf-8") as fh:
                    text = fh.read()
                import yaml as _yaml
                if _yaml.safe_load(text) != zc.mini_yaml_load(text):
                    same_all = False
            check("mini_yaml 与 PyYAML 结果一致", same_all)
        else:
            check("mini_yaml 与 PyYAML 结果一致", True, "SKIPPED: 未安装 PyYAML")

        # 3. fingerprint 归一化
        out = run([CHECK, "fingerprint", "--repo", REPO,
                   "--entity", "SMIC", "--action", "发布",
                   "--object", "2026年三季度报告"])
        got = out.stdout.strip()
        check("fingerprint 主体归并", got == "中芯国际#发布#2026年三季度报告", got)

        out = run([CHECK, "fingerprint", "--repo", REPO,
                   "--entity", "中国石油化工股份有限公司", "--action", "发布",
                   "--object", "2026年三季度报告"])
        check("fingerprint 全称归并",
              out.stdout.strip() == "中国石化#发布#2026年三季度报告", out.stdout.strip())

        # 4. check-issue 退出码
        ok_input, _ = step_input("case-11-reverse-control-clean.json", 0, tmp)
        rc, payload = run_json([CHECK, "check-issue", ok_input, "--repo", REPO,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("合格期次退出码为 0", rc == 0, "rc=%s" % rc)

        bad_input, _ = step_input("case-13-structural-defects.json", 1, tmp)
        rc, payload = run_json([CHECK, "check-issue", bad_input, "--repo", REPO,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("含 BLOCK 的期次退出码为 1", rc == 1, "rc=%s" % rc)
        check("含 BLOCK 的期次报出 PRIMARY_TIER_NOT_JUSTIFIED",
              "PRIMARY_TIER_NOT_JUSTIFIED" in payload["summary"]["codes"])

        # 4b. v0.1.1：audit 子命令（逐条 decision / gate_results / derived）
        aud_input, _ = step_input("case-11-reverse-control-clean.json", 0, tmp)
        aud_md = os.path.join(tmp, "audit.md")
        rc, payload = run_json([CHECK, "audit", aud_input, "--repo", REPO,
                                "--out-md", aud_md,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("audit 退出码为 0", rc == 0, "rc=%s" % rc)
        check("audit 报告含 accepted/rejected 与逐条 gate_results",
              payload["accepted_count"] == 3
              and all("gate_results" in a for a in payload["accepted"]),
              json.dumps(payload.get("accepted_count"), ensure_ascii=False))
        check("audit 写出 markdown", os.path.exists(aud_md)
              and "逐条审计" in open(aud_md, encoding="utf-8").read())

        # 4c. v0.1.1：derive 子命令（程序计算派生状态）
        rc, payload = run_json([CHECK, "derive", aud_input, "--repo", REPO,
                                "--now", "2026-10-04T09:00:00+08:00"])
        rows = {r["id"]: r["derived"] for r in payload["derived"]}
        check("derive 推出 has_primary_source", rows["c01"]["has_primary_source"] is True,
              json.dumps(rows.get("c01"), ensure_ascii=False))
        check("derive 推出 is_within_24h", rows["c01"]["is_within_24h"] is True)
        check("derive 推出 has_material_event", rows["c01"]["has_material_event"] is True)

        # 4d. v0.1.1：模型自报 checked 字段不作数
        t2_input, _ = step_input("case-15-fact-first-derivation.json", 1, tmp)
        rc, payload = run_json([CHECK, "check-issue", t2_input, "--repo", REPO,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("自报 primary_checked=true 但只有搜索页 → 仍报 SEARCH_URL_AS_SOURCE",
              "SEARCH_URL_AS_SOURCE" in payload["summary"]["codes"],
              json.dumps(payload["summary"], ensure_ascii=False))

        t1_input, _ = step_input("case-15-fact-first-derivation.json", 0, tmp)
        rc, payload = run_json([CHECK, "check-issue", t1_input, "--repo", REPO,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("自报 time_window_checked=true 但超出 24 小时 → 仍报 TIME_OUT_OF_WINDOW",
              "TIME_OUT_OF_WINDOW" in payload["summary"]["codes"])

        # 4e. v0.1.1：不写任何自报字段、只给事实字段 → 放行
        t3_input, _ = step_input("case-15-fact-first-derivation.json", 2, tmp)
        rc, payload = run_json([CHECK, "check-issue", t3_input, "--repo", REPO,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("事实字段齐全、无自报字段 → 无 BLOCK 无 WARN 无 INFO",
              payload["summary"]["block"] == 0 and payload["summary"]["warn"] == 0
              and payload["summary"]["info"] == 0,
              json.dumps(payload["summary"], ensure_ascii=False))

        # 4f. v0.1.1：投资／AI 缺 material_update → 不得放行
        t5b_input, _ = step_input("case-15-fact-first-derivation.json", 5, tmp)
        rc, payload = run_json([CHECK, "check-issue", t5b_input, "--repo", REPO,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("material_update 未自证 → UPDATED_NOT_SUBSTANTIATED",
              "UPDATED_NOT_SUBSTANTIATED" in payload["summary"]["codes"],
              json.dumps(payload["summary"], ensure_ascii=False))

        # 5. 历史写入
        history = os.path.join(tmp, "history.jsonl")
        args_rec = [CHECK, "record", ok_input, "--repo", REPO, "--history", history,
                    "--now", "2026-10-04T09:00:00+08:00"]
        rc, payload = run_json(args_rec)
        check("record 试运行新增 3 条", len(payload["added"]) == 3,
              str(len(payload.get("added") or [])))
        check("record 试运行不落盘", not os.path.exists(history))

        run(args_rec + ["--write"])
        with open(history, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().split("\n") if ln.strip()]
        check("record --write 写入 3 行", len(lines) == 3, str(len(lines)))

        rc, payload = run_json(args_rec + ["--write"])
        check("重复 record 不产生新记录", len(payload["added"]) == 0,
              str(len(payload.get("added") or [])))

        # 6. 非可输出状态不得进历史
        new_input, _ = step_input("case-08-repeat-for-three-days.json", 0, tmp)
        history2 = os.path.join(tmp, "history2.jsonl")
        rc, payload = run_json([CHECK, "record", new_input, "--repo", REPO,
                                "--history", history2,
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("status=NEW 的候选不进历史", len(payload["added"]) == 0,
              str(payload.get("added")))

        # 7. 历史裁剪
        with open(history, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "event_id": "old", "date": "2026-01-01", "entity": "旧主体",
                "action": "发布", "object": "旧事件", "title": "旧事件",
                "primary_url": "https://example.com/old",
                "fingerprint": "旧主体#发布#旧事件"}, ensure_ascii=False) + "\n")
        rc, payload = run_json([CHECK, "prune", "--repo", REPO, "--history", history,
                                "--days", "30", "--write",
                                "--now", "2026-10-04T09:00:00+08:00"])
        check("prune 报出 HISTORY_PRUNED",
              "HISTORY_PRUNED" in payload["summary"]["codes"])
        with open(history, "r", encoding="utf-8") as fh:
            after = [ln for ln in fh.read().split("\n") if ln.strip()]
        check("prune 真的删掉了过期记录", len(after) == 3, str(len(after)))

        # 8. 渲染器闸门
        out_md = os.path.join(tmp, "blocked.md")
        proc = run([RENDER, bad_input, "--repo", REPO, "--out", out_md,
                    "--now", "2026-10-04T09:00:00+08:00"])
        check("渲染器在 BLOCK 时拒绝输出", proc.returncode == 1 and not os.path.exists(out_md),
              "rc=%s exists=%s" % (proc.returncode, os.path.exists(out_md)))

        out_md2 = os.path.join(tmp, "ok.md")
        proc = run([RENDER, ok_input, "--repo", REPO, "--out", out_md2,
                    "--now", "2026-10-04T09:00:00+08:00"])
        text = open(out_md2, encoding="utf-8").read() if os.path.exists(out_md2) else ""
        check("渲染器在合格期次正常写出", proc.returncode == 0 and "早间情报" in text,
              "rc=%s len=%d" % (proc.returncode, len(text)))

        # 9. check-render 子命令
        bad_md = os.path.join(tmp, "bad.md")
        with open(bad_md, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        rc, payload = run_json([CHECK, "check-render", bad_md, "--issue", ok_input,
                                "--repo", REPO])
        check("check-render 抓到表格", "TABLE_NOT_ALLOWED" in payload["summary"]["codes"],
              json.dumps(payload["summary"], ensure_ascii=False))
        check("check-render 退出码为 1", rc == 1, "rc=%s" % rc)

        passed = sum(1 for r in RESULTS if r["ok"])
        for r in RESULTS:
            print("%-6s %s%s" % ("PASS" if r["ok"] else "FAIL", r["name"],
                                 ("   [%s]" % r["detail"]) if (args.verbose or not r["ok"]) else ""))
        print()
        print("CLI 冒烟 %d/%d" % (passed, len(RESULTS)))
        print("CLI_SMOKE_STATUS=%s" % ("PASS" if passed == len(RESULTS) else "FAIL"))
        return 0 if passed == len(RESULTS) else 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
