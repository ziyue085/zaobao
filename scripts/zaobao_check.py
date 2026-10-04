#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 确定性规则层（零依赖，仅标准库）

设计边界（重要）
----------------
本脚本只做「可判定」的检查：

    ✅ 字段是否缺失 / 是否三态缺席
    ✅ 时间是否落在 24 小时窗口内（由程序按时间字段计算，不采信模型自报）
    ✅ fingerprint 是否与最近 N 天历史重复、本期内部是否重复
    ✅ 来源类别与 evidence_status 是否自洽（由程序分类，不采信模型声明）
    ✅ 枚举是否合法、计数是否越界
    ✅ 字面违规（标题党、投资建议、影响分析、表格、把「没搜到」写成「没新闻」）

它**不做**研究、不生成内容、不判断「这条新闻重不重要」。
判断重要性是模型在 SKILL.md 流程里的工作，本脚本只负责在模型出错时拦住它。

v0.1.1 架构：七个顶层 Gate
--------------------------
规则不再是一盘散沙的 80 多个 code，而是归到七个稳定的顶层 Gate：

    structure    结构完好性：schema、必填字段、URL、时间格式、枚举
    freshness    时效性：24 小时窗口、旧闻、实质新进展、UPDATED 是否成立
    evidence     证据：一手来源、交叉印证、evidence_status 是否合理、披露标记
    duplication  去重：本期内部、跨日历史、fingerprint、UPDATED
    importance   注意力价值：是否值得占版面（允许模型判断，但必须留理由）
    category     栏目：归类是否合理、门槛是否满足、同一事件只进一个栏目
    output       最终裁决：PASS / UPDATED 是否真的可以进入输出

`run_*_gate()` 是**看懂这份代码的入口**。rule code 退化为 Gate 内部的诊断信息，
继续保留（测试按 code 断言），但不再是架构本身。

程序计算 vs 模型自报
--------------------
v0.1.1 起，以下判断由程序根据**事实字段**自行计算，不再采信模型自报：

    is_within_24h / has_primary_source / verification_source_count
    has_cross_source_verification / history_match / is_material_update
    is_output_eligible

v0.1.0 的 `gates.*_checked` 与 `has_material_event` 保留可读，
但已标记 deprecated，**不再作为放行依据**。

分级
----
    BLOCK  禁止输出。存在任一 BLOCK 即视为本期不可发布。
    WARN   必须显式处理（可在报告中说明后放行）。
    INFO   记录用，不影响发布。

发现项结构固定为 code / severity / priority / gate / scope / message / detail。
code 稳定不变，因为测试按 code 断言。

用法
----
    zaobao_check.py check-issue   <issue.json>  [--repo .] [--now ISO] [--json]
    zaobao_check.py check-candidate <candidate.json> [--repo .] [--now ISO] [--json]
    zaobao_check.py check-render  <output.md>   --issue <issue.json> [--repo .] [--json]
    zaobao_check.py check-config  [--repo .] [--json]
    zaobao_check.py audit         <issue.json>  [--repo .] [--now ISO] [--out-md P] [--json]
    zaobao_check.py derive        <issue.json>  [--repo .] [--now ISO] [--json]
    zaobao_check.py fingerprint   --entity E --action A --object O [--repo .]
    zaobao_check.py record        --issue <issue.json> --history <history.jsonl> [--write]
    zaobao_check.py prune         --history <history.jsonl> [--days 30] [--write]

issue.json 支持两种结构：
    裸数据  {"date": "...", "candidates": [ ... ]}
    夹具    {"id": "...", "steps": [ {"input": {"candidates": [...]}} ]}
入口会显式识别，不猜。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, date, timedelta, timezone

# 统一来源分类器（同目录，零依赖叶子模块）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zaobao_classify as zcl  # noqa: E402

# ────────────────────────────────────────────────────────────────
# 常量（全部具名，便于单点调整）
# ────────────────────────────────────────────────────────────────

CST = timezone(timedelta(hours=8))

WINDOW_HOURS = 24                 # 默认时间窗
HISTORY_DEDUP_DAYS = 30           # 跨日去重回看天数
HISTORY_MIN_DAYS = 7              # 规范要求至少 7 天
HISTORY_RETENTION_DAYS = 30       # 历史文件保留天数
UNEXPECTED_MAX_PER_DAY = 3        # 「意外但重要」每日上限
TOP_PICK_MAX = 3                  # 「今天最值得看的N件事」上限
ISSUE_MAX_ITEMS = 12              # 超过则 WARN
TITLE_MIN_CHARS = 6
TITLE_MAX_CHARS = 45
BODY_MIN_FACTS = 1
BODY_MAX_FACTS = 3

CORRECT_EMPTY_PHRASE = "本期未检索到符合收录标准的条目"

BLOCK, WARN, INFO = "BLOCK", "WARN", "INFO"
_SEV_RANK = {BLOCK: 0, WARN: 1, INFO: 2}

SECTIONS = [
    "universal_policy", "investment", "ai",
    "social", "people_ideas", "unexpected",
]

EVIDENCE_STATUSES = [
    "VERIFIED_PRIMARY", "VERIFIED_CROSS_SOURCE",
    "SECONDARY_ONLY", "UNVERIFIED", "REJECTED",
]

STATUSES = ["NEW", "UPDATED", "OLD", "DUPLICATE", "UNVERIFIED", "LOW_VALUE", "PASS"]

# 可进入最终输出的终态。
# 规范里「只有 PASS 可以进入最终输出」与 Case 4「UPDATED，可以输出新进展」
# 相互矛盾；这里按 Case 4 处理：PASS 表示本期新事件，UPDATED 表示对历史事件的
# 实质新进展，两者都是「可输出终态」。OLD / DUPLICATE / UNVERIFIED / LOW_VALUE
# 一律不可输出。详见 docs/design-notes.md「规则冲突」一节。
OUTPUT_STATUSES = ("PASS", "UPDATED")

NEW_PROGRESS_TYPES = [
    "official_confirmation", "new_announcement", "official_document",
    "new_data", "penalty_or_judgment", "investigation_result",
    "product_launch", "rumor_confirmed", "rumor_refuted",
]

# ── 顶层 Gate（v0.1.1）────────────────────────────────────────────
# 顺序即执行顺序。结构没过就没必要谈时效与证据。
GATES = [
    "structure", "freshness", "evidence",
    "duplication", "importance", "category", "output",
]

# v0.1.0 的六个模型自报闸门字段。保留只为兼容读取，
# **不再作为放行依据** —— 程序改为自行计算时效与证据。
LEGACY_CHECKED_FIELDS = [
    "time_window_checked", "history_dedup_checked", "issue_dedup_checked",
    "primary_source_checked", "url_checked", "no_analysis_checked",
]

# material_update 事实块的三个必需字段。缺一个就不算证明。
MATERIAL_UPDATE_FIELDS = ["claim", "published_at", "source_url"]

DISCLOSURE_SECONDARY = "尚未见一手确认"
DISCLOSURE_UNVERIFIED = "待核实"

TIER_RANK = {"primary": 0, "trusted_secondary": 1, "discovery_only": 2}

# 标题党词表：出现在标题中直接 BLOCK。
CLICKBAIT_WORDS = [
    "重磅", "炸裂", "史诗级", "震惊", "突发大消息", "惊呆", "逆天",
    "王炸", "爆了", "炸了", "震撼", "大消息", "惊天", "史上最",
]

# 投资建议类：任何位置出现即 BLOCK。
ADVICE_WORDS = [
    "建议买入", "建议卖出", "可以买", "值得买入", "建议加仓", "建议减仓",
    "建仓", "止盈", "止损", "目标价", "买入评级", "增持评级", "减持评级",
    "抄底", "上车", "仓位建议",
]

# 影响分析 / 预测类：任何位置出现即 BLOCK。
ANALYSIS_WORDS = [
    "利好", "利空", "值得关注", "可能上涨", "可能下跌", "有望上涨", "有望突破",
    "将会上涨", "将会下跌", "看多", "看空", "后市", "影响分析", "预计将上涨",
    "利好于", "利空于", "要涨", "要跌",
]

# 把「没搜索到」写成「没有新闻」——明令禁止。
NO_NEWS_FALLACY_PHRASES = [
    "没有新闻", "无新闻", "今日无新闻", "暂无新闻", "今天没什么新闻",
    "没有值得关注的新闻", "无重要新闻", "今日平安无事", "今天没有大事",
    "无重大新闻", "今天无事发生",
]

# 廉价凑数特征：AI 栏目里属于「过滤掉」的类型。
LOW_VALUE_MARKERS = [
    "普通融资", "完成A轮", "完成B轮", "完成天使轮", "发布预告", "预告即将",
    "排行榜", "榜单第", "热搜第一但无实据",
]

TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:\-|]{3,}\|[\s:\-|]*$")
CITATION_RE = re.compile(r"来源：\[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\)")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")

# ────────────────────────────────────────────────────────────────
# 发现项
# ────────────────────────────────────────────────────────────────


def fnd(code, severity, priority, scope, message, detail="", gate=None):
    return {
        "code": code,
        "severity": severity,
        "priority": priority,
        "gate": gate,
        "scope": scope,
        "message": message,
        "detail": detail,
    }


def tag_gate(findings, gate):
    """把一组发现项归到某个 Gate 名下。

    rule code 是 Gate 内部的诊断信息；Gate 才是架构。
    归口在这里做，避免给 80 多处 fnd() 调用逐一手写 gate 参数。
    """
    for item in findings:
        if not item.get("gate"):
            item["gate"] = gate
    return findings


def has_block(findings):
    return any(x["severity"] == BLOCK for x in findings)


def sort_findings(findings):
    """按优先级 + 严重度排序。priority 数字越小越靠前。"""
    return sorted(
        findings,
        key=lambda x: (x["priority"], _SEV_RANK.get(x["severity"], 9), x["code"]),
    )


def front_stage(findings, max_items=3, min_severity=WARN):
    """前台展示：去掉 INFO、按 code 去重、截断。30 条全摊出去等于没有优先级。"""
    ceiling = _SEV_RANK.get(min_severity, 1)
    out, seen = [], set()
    for x in sort_findings(findings):
        if _SEV_RANK.get(x["severity"], 9) > ceiling:
            continue
        key = (x["code"], x["scope"])
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
        if len(out) >= max_items:
            break
    return out


def summarize(findings):
    by_gate = {}
    for x in findings:
        g = x.get("gate") or "ungated"
        slot = by_gate.setdefault(g, {"block": 0, "warn": 0, "info": 0})
        slot[x["severity"].lower()] += 1
    return {
        "block": sum(1 for x in findings if x["severity"] == BLOCK),
        "warn": sum(1 for x in findings if x["severity"] == WARN),
        "info": sum(1 for x in findings if x["severity"] == INFO),
        "codes": sorted({x["code"] for x in findings}),
        "by_gate": by_gate,
    }


def gate_results(findings):
    """把发现项按 Gate 归口，给出每个 Gate 的结论。

    PASS   该 Gate 无阻断项
    WARN   只有警告，需要显式处理
    BLOCK  存在阻断项
    """
    out = {g: "PASS" for g in GATES}
    for x in findings:
        g = x.get("gate")
        if g not in out:
            continue
        if x["severity"] == BLOCK:
            out[g] = "BLOCK"
        elif x["severity"] == WARN and out[g] == "PASS":
            out[g] = "WARN"
    return out

# ────────────────────────────────────────────────────────────────
# 时间
# ────────────────────────────────────────────────────────────────


def parse_dt(value):
    """宽松解析 ISO 8601。无时区信息时按 +08:00 解释。"""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00").replace("z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt


def parse_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def now_default():
    return datetime.now(CST)

# ────────────────────────────────────────────────────────────────
# 文本归一化
# ────────────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(
    r"[\s\u3000·、,，。.;；:：!！?？\"'“”‘’()（）\[\]【】<>《》/\\|_\-—~～+*&^%$#@`]+"
)

CORP_SUFFIXES = [
    "股份有限责任公司", "股份有限公司", "有限责任公司", "集团有限公司",
    "有限公司", "控股集团", "集团", "公司",
]


def norm_text(value):
    return _PUNCT_RE.sub("", str(value if value is not None else "")).lower()


def canon_entity(name, aliases=None):
    """把主体收敛到 canonical 名称。

    先查别名表（子串命中即归并），再剥掉常见公司后缀。
    目的是让「中芯国际」「SMIC」「中芯国际集成电路制造有限公司」收敛到同一个 key，
    否则换标题转载会被误判成两条新闻。
    """
    raw = norm_text(name)
    if not raw:
        return ""
    aliases = aliases or {}
    for canonical, variants in aliases.items():
        pool = [canonical] + list(variants or [])
        for item in pool:
            token = norm_text(item)
            if token and token in raw:
                return norm_text(canonical)
    for suffix in CORP_SUFFIXES:
        token = norm_text(suffix)
        if token and raw.endswith(token) and len(raw) > len(token) + 1:
            return raw[: -len(token)]
    return raw


def make_fingerprint(entity, action, obj, aliases=None):
    """主体 + 核心动作 + 核心事件。刻意不含标题。"""
    return "{}#{}#{}".format(
        canon_entity(entity, aliases), norm_text(action), norm_text(obj)
    )


def candidate_fingerprint(cand, aliases=None):
    explicit = cand.get("fingerprint")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return make_fingerprint(
        cand.get("entity"), cand.get("action"), cand.get("object"), aliases
    )

# ────────────────────────────────────────────────────────────────
# URL（统一走 zaobao_classify，避免两处实现漂移）
# ────────────────────────────────────────────────────────────────


def host_of(url):
    return zcl.host_of(url)


def domain_hit(host, domains):
    return zcl.domain_hit(host, domains)


def is_never_source(url, never_list):
    """搜索引擎结果页、内容农场 —— 永远不能作为来源。"""
    return zcl.is_never_source(url, never_list)


def is_valid_url(url):
    return bool(re.match(r"^https?://[^\s/]+", str(url or "").strip(), re.I))

# ────────────────────────────────────────────────────────────────
# 派生层：由程序根据事实字段计算结论（v0.1.1 核心）
# ────────────────────────────────────────────────────────────────


def derive(cand, ctx):
    """根据候选里的事实字段，由程序自行计算派生状态。

    这一层的存在就是为了回答一个问题：**能不能不让模型自报？**

        is_within_24h             ← published_at / event_date 与当前时间
        has_primary_source        ← 来源分类器算出的类别
        verification_source_count ← 独立发布者计数
        has_cross_source_verification ← 上一项 >= 2
        history_match             ← fingerprint 与历史记录比对
        is_material_update        ← 历史命中 + 有实质新进展
        is_output_eligible        ← 时效与证据都成立，且状态是可输出终态

    模型如果声明 `time_checked=true` 但发布时间是 30 小时前，
    这里算出来的 `is_within_24h` 仍然是 false —— 自报不再是放行依据。
    """
    now = ctx["now"]
    window = timedelta(hours=ctx.get("window_hours", WINDOW_HOURS))
    d = {"fingerprint": candidate_fingerprint(cand, ctx.get("aliases"))}

    # ── 时效 ────────────────────────────────────────────────
    pub = parse_dt(cand.get("published_at") or cand.get("event_date")
                   or cand.get("event_time"))
    d["published_at"] = pub.isoformat() if pub else None
    d["is_future"] = bool(pub and pub > now)
    d["is_within_24h"] = bool(pub and timedelta(0) <= (now - pub) <= window)

    # ── 实质新进展：new_progress_* 或 material_update 任一成立即可 ──
    np_at = parse_dt(cand.get("new_progress_at"))
    np_type = cand.get("new_progress_type")
    np_ok = bool(
        np_type in NEW_PROGRESS_TYPES
        and np_at is not None
        and timedelta(0) <= (now - np_at) <= window
    )
    d["new_progress_fields_ok"] = np_ok

    mu = cand.get("material_update")
    legacy_present = "has_material_event" in cand
    d["material_update_present"] = mu is not None
    d["legacy_material_flag"] = bool(legacy_present and not isinstance(mu, dict))
    d["material_update_substantiated"] = None

    if isinstance(mu, dict):
        mu_at = parse_dt(mu.get("published_at"))
        mu_url = str(mu.get("source_url") or "")
        mu_claim = str(mu.get("claim") or "").strip()
        mu_ok = bool(
            mu_claim
            and mu_at is not None
            and timedelta(0) <= (now - mu_at) <= window
            and is_valid_url(mu_url)
            and not is_never_source(mu_url, ctx.get("never_a_source"))
        )
        d["material_update_substantiated"] = mu_ok
        d["has_material_event"] = mu_ok
    elif mu is not None:
        # 存在但不是对象 —— 结构性缺陷，结构 Gate 会报
        d["material_update_substantiated"] = False
        d["has_material_event"] = False
    elif legacy_present:
        # v0.1.0 自报字段：可读、可用，但会被标记 deprecated
        d["has_material_event"] = cand.get("has_material_event") is True
    else:
        d["has_material_event"] = False

    d["has_new_progress"] = bool(np_ok or d.get("material_update_substantiated"))

    # ── 来源（由分类器计算，不采信 sources[].tier 声明）──
    classes = zcl.classify_sources(cand, ctx)
    d["source_classes"] = [c["class"] for c in classes]
    d["source_class_counts"] = zcl.summarize_classes(classes)
    d["has_primary_source"] = any(c["is_primary"] for c in classes)
    d["primary_source_count"] = sum(1 for c in classes if c["is_primary"])
    # 独立发布者计数：按「来源 dict」取 publisher，而不是按分类结论 dict。
    # 分类结论里没有 publisher 字段，误传进去会导致永远退回主机名 ——
    # 那样同一家媒体的两个子域（news.sina.com.cn / finance.sina.com.cn）
    # 会被误算成两家独立来源。
    src_dicts = [s for s in (cand.get("sources") or []) if isinstance(s, dict)]
    trusted = [s for s, c in zip(src_dicts, classes)
               if c["is_primary"] or c["class"] == zcl.TRUSTED_SECONDARY]
    publishers = {zcl.publisher_key(s) for s in trusted if zcl.publisher_key(s)}
    d["verification_source_count"] = len(publishers)
    d["verification_publishers"] = sorted(publishers)
    d["has_cross_source_verification"] = len(publishers) >= 2
    d["has_discovery_only_source"] = any(
        c["class"] == zcl.DISCOVERY_ONLY for c in classes)
    d["only_discovery_source"] = bool(classes) and all(
        c["class"] == zcl.DISCOVERY_ONLY for c in classes)
    d["tier_mismatch_count"] = sum(1 for c in classes if c["mismatch"])

    # ── 投资主体是否落在关注清单（能对 config 直接校验的事实）──
    inv_ref = str(cand.get("watchlist_subject") or "").strip()
    d["watchlist_subject"] = inv_ref or None
    d["watchlist_subject_bound"] = bool(
        cand.get("section") == "investment"
        and inv_ref and inv_ref in (ctx.get("investment_subjects") or set()))

    # ── 去重 ────────────────────────────────────────────────
    days = ctx.get("history_dedup_days", HISTORY_DEDUP_DAYS)
    matches = []
    for rec in ctx.get("history_records") or []:
        if not isinstance(rec, dict) or rec.get("fingerprint") != d["fingerprint"]:
            continue
        rec_date = parse_date(rec.get("date"))
        if rec_date is None:
            continue
        if (now.date() - rec_date).days <= days:
            matches.append(rec)
    d["history_match"] = bool(matches)
    d["history_match_count"] = len(matches)
    d["is_material_update"] = bool(d["history_match"] and d["has_new_progress"])

    # ── 最终可输出性（程序意见，供审计与 Gate 参考）──
    declared_evidence = cand.get("evidence_status")
    d["freshness_ok"] = bool(d["is_within_24h"] or d["has_new_progress"])
    d["evidence_ok"] = bool(
        d["has_primary_source"]
        or d["has_cross_source_verification"]
        or declared_evidence in ("SECONDARY_ONLY", "UNVERIFIED")
    )
    d["is_output_eligible"] = bool(
        cand.get("status") in OUTPUT_STATUSES
        and d["freshness_ok"]
        and d["evidence_ok"]
    )
    return d


def derive_issue(issue, ctx):
    """对整期候选逐条计算派生状态。"""
    return [derive(c, ctx) for c in iter_candidates(issue)]


# ────────────────────────────────────────────────────────────────
# 配置：YAML 读取（PyYAML 优先，缺失时用内置子集解析器）
# ────────────────────────────────────────────────────────────────


def _strip_comment(line):
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out)


def _split_kv(text):
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == ":":
            rest = text[i + 1:]
            if rest == "" or rest[0] in " \t":
                return text[:i].strip(), rest.strip()
    return None, None


def _split_flow(text):
    parts, buf, quote, depth = [], [], None, 0
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p != ""]


def _scalar(text):
    v = text.strip()
    if v == "":
        return ""
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in _split_flow(v[1:-1])]
    if v.startswith("{") and v.endswith("}"):
        out = {}
        for item in _split_flow(v[1:-1]):
            k, _, val = item.partition(":")
            out[k.strip()] = _scalar(val)
        return out
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("null", "Null", "NULL", "~"):
        return None
    if v in ("true", "True", "yes", "on"):
        return True
    if v in ("false", "False", "no", "off"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _parse_block(lines, idx, indent):
    first_text = lines[idx][1]
    if first_text.startswith("-"):
        items = []
        while idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("-"):
            body = lines[idx][1][1:].strip()
            idx += 1
            if body == "":
                if idx < len(lines) and lines[idx][0] > indent:
                    val, idx = _parse_block(lines, idx, lines[idx][0])
                else:
                    val = None
                items.append(val)
                continue
            key, value = _split_kv(body)
            if key and value is not None and key:
                mapping = {}
                if value == "":
                    if idx < len(lines) and lines[idx][0] > indent:
                        sub, idx = _parse_block(lines, idx, lines[idx][0])
                        mapping[key] = sub
                    else:
                        mapping[key] = None
                else:
                    mapping[key] = _scalar(value)
                while idx < len(lines) and lines[idx][0] > indent:
                    k2, v2 = _split_kv(lines[idx][1])
                    if k2 is None:
                        break
                    idx += 1
                    if v2 == "":
                        if idx < len(lines) and lines[idx][0] > indent:
                            sub, idx = _parse_block(lines, idx, lines[idx][0])
                            mapping[k2] = sub
                        else:
                            mapping[k2] = None
                    else:
                        mapping[k2] = _scalar(v2)
                items.append(mapping)
            else:
                items.append(_scalar(body))
        return items, idx

    mapping = {}
    while idx < len(lines) and lines[idx][0] == indent:
        key, value = _split_kv(lines[idx][1])
        if key is None:
            idx += 1
            continue
        idx += 1
        if value == "":
            if idx < len(lines) and lines[idx][0] > indent:
                sub, idx = _parse_block(lines, idx, lines[idx][0])
                mapping[key] = sub
            else:
                mapping[key] = None
        else:
            mapping[key] = _scalar(value)
    return mapping, idx


def mini_yaml_load(text):
    """内置 YAML 子集解析器 —— 仅覆盖本项目 config/ 所用结构。

    支持：缩进嵌套映射、`- ` 序列、`- key: value` 起始的内联映射及其续行、
    内联 `[a, b]` 与 `{a: b}`、`#` 注释、单双引号。

    不支持：锚点与别名、多行标量（| 与 >）、复杂键、多文档。
    这些特性本项目不需要；若将来需要，请安装 PyYAML。
    """
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip()))
    if not lines:
        return {}
    value, _ = _parse_block(lines, 0, lines[0][0])
    return value


def load_yaml_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # type: ignore
    except ImportError:
        return mini_yaml_load(text), "mini_yaml"
    return yaml.safe_load(text), "pyyaml"


def _investment_subjects(watch):
    """关注清单里「投资」栏目认可的主体集合。

    为什么放在这里：主体名单是**可枚举的事实**，程序可以直接对着 config 校验。
    v0.1.0 只校验事件类型（"并购重组"就放行），从不校验主体，
    等于把「该不该关注这家公司」整个交给了模型 —— 这正是 Round 2 实战评估里
    一条清单外个股的并购被误收的原因。

    命中范围：institutions + assets + 全部别名的 canonical 与变体。
    """
    inv = ((watch.get("sections") or {}).get("investment") or {})
    names = set()
    for key in ("institutions", "assets"):
        for x in (inv.get(key) or []):
            t = str(x).strip()
            if t:
                names.add(t)
    for canonical, variants in (watch.get("aliases") or {}).items():
        c = str(canonical).strip()
        if c:
            names.add(c)
        for v in (variants or []):
            t = str(v).strip()
            if t:
                names.add(t)
    return names


def load_config(repo_root, now=None):
    watch_path = os.path.join(repo_root, "config", "watchlist.yaml")
    src_path = os.path.join(repo_root, "config", "sources.yaml")
    watch, w_engine = load_yaml_file(watch_path)
    sources, s_engine = load_yaml_file(src_path)
    watch = watch or {}
    sources = sources or {}

    primary_block = sources.get("primary") or {}
    secondary_block = sources.get("trusted_secondary") or {}
    discovery_block = sources.get("discovery_only") or {}

    return {
        "watchlist": watch,
        "sources": sources,
        "engines": {"watchlist": w_engine, "sources": s_engine},
        "ctx": {
            "repo_root": repo_root,
            "sections": watch.get("sections") or {},
            "sections_order": watch.get("priority") or [],
            "banned_sections": watch.get("banned_sections") or [],
            "aliases": watch.get("aliases") or {},
            "window_hours": ((watch.get("meta") or {}).get("window_hours") or WINDOW_HOURS),
            "timezone": (watch.get("meta") or {}).get("timezone") or "+08:00",
            "primary_domains": primary_block.get("domains") or [],
            "trusted_domains": secondary_block.get("domains") or [],
            "quasi_primary_domains": secondary_block.get("quasi_primary") or [],
            "discovery_domains": discovery_block.get("domains") or [],
            "never_a_source": sources.get("never_a_source") or [],
            "investment_subjects": _investment_subjects(watch),
            "history_records": [],
            "history_dedup_days": HISTORY_DEDUP_DAYS,
            "history_retention_days": HISTORY_RETENTION_DAYS,
            "now": now or now_default(),
        },
    }


def make_ctx(repo_root, now=None, history_records=None):
    cfg = load_config(repo_root, now=now)
    ctx = cfg["ctx"]
    if history_records is not None:
        ctx["history_records"] = history_records
    return ctx

# ────────────────────────────────────────────────────────────────
# 规则：配置
# ────────────────────────────────────────────────────────────────


def check_config(repo_root, now=None):
    findings = []
    cfg = load_config(repo_root, now=now)
    watch, sources = cfg["watchlist"], cfg["sources"]

    priority = watch.get("priority") or []
    sections = watch.get("sections") or {}
    banned = watch.get("banned_sections") or []

    if not priority:
        findings.append(fnd("CONFIG_PRIORITY_MISSING", BLOCK, 0,
                            "watchlist.priority", "priority 为空，无法确定栏目顺序"))
    for sec in priority:
        if sec not in sections:
            findings.append(fnd("CONFIG_SECTION_UNDEFINED", BLOCK, 1,
                                "watchlist.sections",
                                "priority 中的栏目未在 sections 中定义", str(sec)))
    for sec in banned:
        if sec in priority:
            findings.append(fnd("CONFIG_BANNED_SECTION_IN_PRIORITY", BLOCK, 2,
                                "watchlist.banned_sections",
                                "被排除的栏目出现在了 priority 中", str(sec)))
    unknown = [s for s in sections if s not in SECTIONS]
    if unknown:
        findings.append(fnd("CONFIG_SECTION_UNKNOWN", WARN, 3, "watchlist.sections",
                            "存在规范未定义的栏目名", ", ".join(unknown)))

    unexp = (sections.get("unexpected") or {}).get("max_per_day")
    if unexp is None:
        findings.append(fnd("CONFIG_UNEXPECTED_LIMIT_MISSING", WARN, 3,
                            "watchlist.sections.unexpected",
                            "未设置 max_per_day，「意外但重要」每日上限失去约束"))
    elif int(unexp) > UNEXPECTED_MAX_PER_DAY:
        findings.append(fnd("CONFIG_UNEXPECTED_LIMIT_RAISED", WARN, 3,
                            "watchlist.sections.unexpected",
                            "max_per_day 高于规范上限 3",
                            "当前值 %s" % unexp))

    pr = sources.get("primary") or {}
    se = sources.get("trusted_secondary") or {}
    di = sources.get("discovery_only") or {}
    for name, block in (("primary", pr), ("trusted_secondary", se), ("discovery_only", di)):
        if not (block or {}).get("domains"):
            findings.append(fnd("CONFIG_SOURCE_TIER_EMPTY", BLOCK, 1,
                                "sources.%s" % name,
                                "来源层级为空，层级判断将失效"))
    if not sources.get("never_a_source"):
        findings.append(fnd("CONFIG_NEVER_SOURCE_EMPTY", WARN, 3, "sources.never_a_source",
                            "未定义「永不作为来源」清单，搜索引擎 URL 可能被当成证据"))

    tiers = {
        "primary": set(str(d).lower() for d in (pr.get("domains") or [])),
        "trusted_secondary": set(str(d).lower() for d in (se.get("domains") or [])),
        "discovery_only": set(str(d).lower() for d in (di.get("domains") or [])),
    }
    names = list(tiers)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            overlap = tiers[names[i]] & tiers[names[j]]
            if overlap:
                findings.append(fnd("CONFIG_SOURCE_TIER_OVERLAP", WARN, 4,
                                    "sources",
                                    "同一域名被登记在多个层级",
                                    "%s ∩ %s = %s" % (names[i], names[j],
                                                      ", ".join(sorted(overlap)))))

    retention = HISTORY_RETENTION_DAYS
    if retention < HISTORY_MIN_DAYS:
        findings.append(fnd("CONFIG_HISTORY_RETENTION_SHORT", WARN, 4, "history",
                            "历史保留天数低于规范要求的 7 天", str(retention)))

    hours = (watch.get("meta") or {}).get("window_hours")
    if hours not in (None, WINDOW_HOURS):
        findings.append(fnd("CONFIG_WINDOW_CHANGED", INFO, 5, "watchlist.meta.window_hours",
                            "时间窗已偏离默认 24 小时", str(hours)))
    if not (watch.get("aliases") or {}):
        findings.append(fnd("CONFIG_ALIASES_EMPTY", INFO, 5, "watchlist.aliases",
                            "未配置主体别名，跨来源换称呼的事件可能被当成两条"))

    inv = sections.get("investment") or {}
    if not ((inv.get("institutions") or []) or (inv.get("assets") or [])):
        findings.append(fnd("CONFIG_INVESTMENT_SUBJECTS_EMPTY", WARN, 3,
                            "watchlist.sections.investment",
                            "投资栏目没有可枚举的主体清单，主体准入校验会失效"))

    for engine_name, engine in (cfg.get("engines") or {}).items():
        if engine == "mini_yaml":
            findings.append(fnd("CONFIG_USING_MINI_YAML", INFO, 5, engine_name,
                                "未安装 PyYAML，已回退到内置子集解析器"))
    return sort_findings(findings)

# ────────────────────────────────────────────────────────────────
# 规则：候选
# ────────────────────────────────────────────────────────────────


def _text_pool(cand):
    parts = [cand.get("title") or "", cand.get("background") or ""]
    body = cand.get("body_facts")
    if isinstance(body, list):
        parts.extend(str(x) for x in body)
    return parts


def _check_language(cand, findings):
    title = str(cand.get("title") or "")
    pool = _text_pool(cand)

    for word in CLICKBAIT_WORDS:
        if word in title:
            findings.append(fnd("CLICKBAIT_TITLE", BLOCK, 2, title,
                                "标题含标题党词汇", word))
    for word in ADVICE_WORDS:
        for seg in pool:
            if word in seg:
                findings.append(fnd("ADVICE_LEAK", BLOCK, 2, cand.get("id"),
                                    "出现投资建议表述", "%s → %s" % (word, seg)))
                break
    for word in ANALYSIS_WORDS:
        for seg in pool:
            if word in seg:
                findings.append(fnd("ANALYSIS_LEAK", BLOCK, 2, cand.get("id"),
                                    "出现影响分析或预测表述", "%s → %s" % (word, seg)))
                break
    for phrase in NO_NEWS_FALLACY_PHRASES:
        for seg in pool:
            if phrase in seg:
                findings.append(fnd("NO_NEWS_FALLACY", BLOCK, 0, cand.get("id"),
                                    "把「没搜索到」写成「没有新闻」", phrase))
                break

    if len(title) > TITLE_MAX_CHARS:
        findings.append(fnd("TITLE_TOO_LONG", WARN, 4, title,
                            "标题过长，不像直接陈述事实", "%d 字" % len(title)))
    if len(title) < TITLE_MIN_CHARS:
        findings.append(fnd("TITLE_TOO_SHORT", WARN, 4, title,
                            "标题过短，可能未说明事实", "%d 字" % len(title)))
    if title.rstrip().endswith(("？", "?")):
        findings.append(fnd("TITLE_NOT_FACTUAL", WARN, 4, title,
                            "标题使用疑问句，应直接陈述事实"))
    if title.startswith("突发"):
        findings.append(fnd("TITLE_NOT_FACTUAL", WARN, 4, title,
                            "标题以「突发」开头，属情绪化写法"))

    body = cand.get("body_facts")
    if not isinstance(body, list) or not (BODY_MIN_FACTS <= len(body) <= BODY_MAX_FACTS):
        findings.append(fnd("BODY_FACT_COUNT_INVALID", BLOCK, 3, cand.get("id"),
                            "事实句数量应在 %d—%d 之间" % (BODY_MIN_FACTS, BODY_MAX_FACTS),
                            str(body)))


def _check_time(cand, ctx, d, findings):
    """时效判定。窗口与"是否有新进展"都取自派生层，不采信模型自报。

    v0.1.1 起，模型写 `time_window_checked: true` 不再有任何作用 ——
    时间是否落在窗口内由 published_at / event_date 与当前时间算出来。
    """
    now = ctx["now"]
    status = cand.get("status")

    event_dt = parse_dt(cand.get("published_at") or cand.get("event_date"))
    if event_dt is None:
        # 缺时间字段已由结构 Gate 报出（TIME_FIELD_MISSING），这里只做短路。
        return

    # 窗口与"是否有新进展"都取自派生层 —— 模型写 checked=true 不改变这两项。
    has_new_progress = bool(d.get("has_new_progress"))
    within_window = bool(d.get("is_within_24h"))

    # 声明 UPDATED 就必须拿得出可核实的实质新进展。
    if status == "UPDATED" and not has_new_progress:
        findings.append(fnd(
            "UPDATED_NOT_SUBSTANTIATED", _sev_for_status(cand), 0, cand.get("id"),
            "标为 UPDATED 但找不到可核实的实质新进展",
            "需要 new_progress_at+new_progress_type，或字段完整的 material_update"))

    if event_dt > now:
        findings.append(fnd("TIME_IN_FUTURE", BLOCK, 0, cand.get("id"),
                            "事件时间晚于当前时间", str(event_dt)))
        return

    if within_window:
        if has_new_progress and status == "OLD":
            findings.append(fnd("STATUS_SHOULD_BE_UPDATED", BLOCK, 0, cand.get("id"),
                                "事件在窗内且有新进展，却被标为 OLD"))
        return

    # 事件本身在窗外
    if has_new_progress:
        if status != "UPDATED":
            findings.append(fnd("STATUS_SHOULD_BE_UPDATED", BLOCK, 0, cand.get("id"),
                                "旧事件出现实质新进展，状态应为 UPDATED",
                                "当前 %s" % status))
        return

    if status == "OLD":
        findings.append(fnd("TIME_OUT_OF_WINDOW", INFO, 5, cand.get("id"),
                            "事件超出 24 小时窗口，已正确判为 OLD"))
    else:
        findings.append(fnd("TIME_OUT_OF_WINDOW", BLOCK, 0, cand.get("id"),
                            "事件超出 24 小时窗口且无实质新进展",
                            "event_date=%s" % cand.get("event_date")))
        findings.append(fnd("STATUS_SHOULD_BE_OLD", BLOCK, 0, cand.get("id"),
                            "状态应为 OLD／DUPLICATE，而不是 %s" % status))


def is_output(cand):
    """该候选是否属于「可输出终态」。"""
    return cand.get("status") in OUTPUT_STATUSES


def _sev_for_status(cand, when_output=BLOCK, otherwise=INFO):
    """证据充分性类判定：只有条目真的进入输出时才是阻断项。

    结构性缺陷（URL 不合法、搜索引擎当来源、层级无法自证、栏目被排除、
    标题党、建议与分析泄漏）不走这里 —— 它们任何时候都是 BLOCK。
    """
    if is_output(cand) or cand.get("top_pick"):
        return when_output
    return otherwise


def _check_sources(cand, ctx, d, findings):
    """证据判定。一手与否由分类器计算，不采信 sources[].tier 声明。"""
    cid = cand.get("id")
    tier = cand.get("evidence_status")
    if tier not in EVIDENCE_STATUSES:
        findings.append(fnd("EVIDENCE_STATUS_INVALID", BLOCK, 0, cid,
                            "evidence_status 非法", str(tier)))
        return
    if tier == "REJECTED":
        if is_output(cand) or cand.get("top_pick"):
            findings.append(fnd("REJECTED_IN_OUTPUT", BLOCK, 0, cid,
                                "已判 REJECTED 的条目不应出现在输出中"))
        else:
            findings.append(fnd("EVIDENCE_REJECTED", INFO, 5, cid,
                                "证据已判定不可用，正确做法是整条丢弃",
                                str(cand.get("reject_reason") or "")))

    srcs = cand.get("sources")
    if not isinstance(srcs, list) or not srcs:
        findings.append(fnd("SOURCE_MISSING", BLOCK, 1, cid, "sources 为空"))
        return

    valid_srcs, valid_classes = [], []
    for s in srcs:
        if not isinstance(s, dict):
            continue
        url = str(s.get("url") or "")
        if not is_valid_url(url):
            findings.append(fnd("URL_INVALID", BLOCK, 1, cid,
                                "来源 URL 不是合法的 http(s) 地址", url))
            continue
        hit = is_never_source(url, ctx.get("never_a_source"))
        if hit:
            findings.append(fnd("SEARCH_URL_AS_SOURCE", BLOCK, 1, cid,
                                "搜索引擎或内容农场页面不能作为来源", "%s (%s)" % (url, hit)))
            continue
        host = host_of(url)
        s_tier = s.get("tier")
        if s_tier not in TIER_RANK:
            findings.append(fnd("SOURCE_TIER_INVALID", BLOCK, 1, cid,
                                "来源层级非法", "%s → %s" % (url, s_tier)))
            continue
        cls = zcl.classify_source(s, ctx)
        declared = domain_hit(host, ctx.get("%s_domains" % s_tier) or [])
        if s_tier == "primary" and not declared and not cls["justified_first_party"]:
            findings.append(fnd(
                "PRIMARY_TIER_NOT_JUSTIFIED", BLOCK, 1, cid,
                "域名不在 primary 清单中，且未声明 is_first_party + tier_reason",
                url))
            continue
        if cls["is_primary"] and domain_hit(host, ctx.get("discovery_domains") or []):
            findings.append(fnd(
                "DISCOVERY_DOMAIN_AS_PRIMARY", WARN, 3, cid,
                "把通常只用于发现线索的平台声明为一手来源，需确认发布者确为当事人或官方账号",
                url))
        if cls.get("justified_trusted_secondary"):
            findings.append(fnd(
                "SOURCE_TIER_JUSTIFIED", INFO, 5, cid,
                "来源域名不在 trusted_secondary 清单中，凭声明与分层理由计入可信二手",
                url))
        valid_srcs.append(s)
        valid_classes.append(cls)

    if not valid_srcs:
        return

    pairs = list(zip(valid_srcs, valid_classes))
    primary_srcs = [s for s, c in pairs if c["is_primary"]]
    quasi_srcs = [s for s, c in pairs if c["quasi_primary"]]

    if tier == "VERIFIED_PRIMARY" and not d.get("has_primary_source"):
        findings.append(fnd("PRIMARY_SOURCE_MISSING", _sev_for_status(cand), 1, cid,
                            "声明 VERIFIED_PRIMARY 但没有任何一手来源"))

    if tier == "VERIFIED_CROSS_SOURCE":
        if d.get("verification_source_count", 0) < 2:
            findings.append(fnd("INSUFFICIENT_CROSS_SOURCE", _sev_for_status(cand), 1, cid,
                                "声明多源交叉印证，但可信来源不足 2 家",
                                ", ".join(d.get("verification_publishers") or [])))
        if d.get("has_primary_source"):
            findings.append(fnd("CROSS_SOURCE_HAS_PRIMARY", _sev_for_status(cand, WARN), 3, cid,
                                "已存在一手来源，evidence_status 宜升为 VERIFIED_PRIMARY"))

    if tier == "SECONDARY_ONLY":
        if cand.get("disclosure") != DISCLOSURE_SECONDARY:
            findings.append(fnd("MISSING_DISCLOSURE", _sev_for_status(cand), 1, cid,
                                "仅有可信二手报道，必须标注「%s」" % DISCLOSURE_SECONDARY,
                                "disclosure=%s" % cand.get("disclosure")))
        # 「仅有可信二手」这句话本身也要能被程序验证。
        # v0.1.1 早期版本只检查 disclosure 标记，导致「随便挂一条清单外域名、
        # 只要写上『尚未见一手确认』就能放行」—— 放行依据又回到了模型身上。
        # 现在改为：程序按来源分类器算出的可信来源（一手或可信二手）发布者数
        # 必须 ≥ 1；一条都算不出来，就说明它并不是「仅有可信二手」。
        if d.get("verification_source_count", 0) < 1:
            findings.append(fnd(
                "SECONDARY_SOURCE_MISSING", _sev_for_status(cand), 1, cid,
                "声明「仅有可信二手」，但程序按来源分类器算不出一条可信来源",
                "计算类别：%s" % json.dumps(d.get("source_class_counts") or {},
                                          ensure_ascii=False)))

    if tier == "UNVERIFIED":
        if cand.get("disclosure") != DISCLOSURE_UNVERIFIED:
            findings.append(fnd("MISSING_DISCLOSURE", _sev_for_status(cand), 1, cid,
                                "证据不足，必须标注「%s」" % DISCLOSURE_UNVERIFIED,
                                "disclosure=%s" % cand.get("disclosure")))
        if cand.get("section") != "unexpected":
            findings.append(fnd("UNVERIFIED_NOT_ALLOWED", _sev_for_status(cand), 1, cid,
                                "UNVERIFIED 只允许出现在「意外但重要」，且国内普通新闻应直接删除",
                                "section=%s" % cand.get("section")))

    if d.get("only_discovery_source"):
        findings.append(fnd("DISCOVERY_ONLY_AS_SOLE_EVIDENCE", _sev_for_status(cand), 1, cid,
                            "只有社交平台作为来源，不能单独作为重要事实的证据"))

    primary_url = cand.get("primary_url")
    if is_output(cand):
        if not isinstance(primary_url, str) or not primary_url.strip():
            findings.append(fnd("PRIMARY_URL_MISSING", BLOCK, 1, cid,
                                "可输出条目必须给出 primary_url"))
        else:
            urls = {str(s.get("url") or "") for s in valid_srcs}
            if primary_url not in urls:
                findings.append(fnd("PRIMARY_URL_NOT_IN_SOURCES", BLOCK, 1, cid,
                                    "primary_url 不在 sources 列表中", primary_url))

    if cand.get("section") == "universal_policy":
        if not primary_srcs and not quasi_srcs:
            findings.append(fnd("POLICY_PRIMARY_MISSING",
                                _sev_for_status(cand, WARN), 2, cid,
                                "普适性政策缺少一手或准一手来源"))
        elif not primary_srcs and quasi_srcs:
            findings.append(fnd("QUASI_PRIMARY_USED", INFO, 5, cid,
                                "普适性政策使用准一手来源（中央文件通稿）",
                                host_of(str(quasi_srcs[0].get("url")))))


def _check_importance(cand, ctx, d, findings):
    """重要性 Gate：这条信息是否值得占用用户注意力？

    重要性本身不可判定，所以这里**保留模型的语义判断**，
    但要求它留下可审计的理由（material_update 事实块），而不是一个 `important=true`。

    门槛类问题只在条目真的进入输出时才是阻断项 —— 一个已经被丢弃的候选
    不需要再满足栏目准入条件，否则报告会被无关噪声淹没。
    """
    cid = cand.get("id")
    sec = cand.get("section")
    status = cand.get("status")

    if sec in ("investment", "ai"):
        mu = cand.get("material_update")
        if isinstance(mu, dict):
            if not d.get("material_update_substantiated"):
                missing = [f for f in MATERIAL_UPDATE_FIELDS
                           if not str(mu.get(f) or "").strip()]
                findings.append(fnd(
                    "MATERIAL_UPDATE_UNSUBSTANTIATED", _sev_for_status(cand), 3, cid,
                    "material_update 未能自证：需要非空 claim、窗口内的 published_at、可用的 source_url",
                    ("缺少字段：%s" % "、".join(missing)) if missing
                    else "字段齐全但时间不在窗口内或来源不可用"))
        elif d.get("legacy_material_flag"):
            findings.append(fnd(
                "LEGACY_MATERIAL_FLAG", INFO, 5, cid,
                "使用 v0.1.0 的 has_material_event 自报字段；建议改为 material_update 事实块"))
        else:
            findings.append(fnd(
                "MATERIAL_UPDATE_MISSING", _sev_for_status(cand), 3, cid,
                "投资／AI 条目必须给出 material_update 事实块，缺失即无法证明存在实质事件",
                "应有字段：%s" % "、".join(MATERIAL_UPDATE_FIELDS)))

        if not d.get("has_material_event"):
            if is_output(cand) or cand.get("top_pick"):
                findings.append(fnd("LOW_VALUE_PRICE_ONLY", BLOCK, 3, cid,
                                    "仅有正常价格波动、无实质事件，不得因「用户关注」而强行输出"))
            elif status == "LOW_VALUE":
                findings.append(fnd("LOW_VALUE_PRICE_ONLY", INFO, 5, cid,
                                    "价格波动类信息已正确判为 LOW_VALUE"))

    pool = " ".join(_text_pool(cand))
    for marker in LOW_VALUE_MARKERS:
        if marker in pool:
            findings.append(fnd("LOW_VALUE_BOILERPLATE", WARN, 3, cid,
                                "疑似凑数内容，需确认是否属于应过滤的类型", marker))
            break


def _check_category(cand, ctx, d, findings):
    """栏目 Gate：归类是否合理、门槛是否满足、同一事件只进一个栏目。"""
    sec = cand.get("section")
    cid = cand.get("id")

    if sec == "unexpected":
        if not cand.get("unexpected_gate"):
            findings.append(fnd("UNEXPECTED_GATE_MISSING", _sev_for_status(cand), 3, cid,
                                "进入「意外但重要」必须声明属于哪一类高门槛事件"))

    if sec == "social":
        ttype = cand.get("topic_type")
        if not ttype:
            findings.append(fnd("SOCIAL_TOPIC_TYPE_MISSING", _sev_for_status(cand), 3, cid,
                                "社会热点必须给出 topic_type"))
        if ttype in ("entertainment", "celebrity") and cand.get("subject_confirmed") is not True:
            findings.append(fnd("GOSSIP_UNCONFIRMED", _sev_for_status(cand), 3, cid,
                                "娱乐／名人条目必须由当事人或官方正式确认；传闻不得写成事实",
                                "subject_confirmed=%s" % cand.get("subject_confirmed")))

    if sec == "people_ideas":
        sig = cand.get("idea_signal")
        if not isinstance(sig, dict) or not any(bool(v) for v in sig.values()):
            findings.append(fnd("IDEA_SIGNAL_MISSING", _sev_for_status(cand), 3, cid,
                                "人物与思想信号必须至少命中一项：新观点/新数据/新方法/新判断/新技术细节"))

    _check_investment_subject(cand, ctx, d, findings)


def _check_investment_subject(cand, ctx, d, findings):
    """投资栏目的主体必须落到关注清单上 —— 对着 config 校验，不采信模型判断。

    模型可以做的是「指明这条对应清单里的哪一项」（watchlist_subject），
    程序做的是「这一项到底在不在清单里」。声明一个引用，比声明一个结论
    更容易被程序否掉。
    """
    if cand.get("section") != "investment":
        return
    cid = cand.get("id")
    ref = str(cand.get("watchlist_subject") or "").strip()
    known = ctx.get("investment_subjects") or set()
    if not ref:
        findings.append(fnd(
            "INVESTMENT_SUBJECT_UNBOUND", _sev_for_status(cand), 2, cid,
            "投资条目必须声明 watchlist_subject，指明它对应关注清单里的哪个机构／标的／类别",
            "entity=%s" % cand.get("entity")))
    elif ref not in known:
        findings.append(fnd(
            "INVESTMENT_SUBJECT_UNKNOWN", _sev_for_status(cand), 2, cid,
            "watchlist_subject 不在 config/watchlist.yaml 的投资主体里",
            "%s（清单内共 %d 项）" % (ref, len(known))))


def _check_legacy_checked(cand, findings):
    """v0.1.0 的模型自报闸门字段 —— v0.1.1 起降级为参考信息。

    为什么不再阻断：时效与证据现在由程序按事实字段自行计算，
    模型说"我查过了"既不能加信任，也不能减信任。
    因此：字段缺席不报错；字段存在只记 INFO；显式为 false 记 WARN
    （那说明产出流程本身可能没做完，值得看一眼，但不该拦住一条事实齐全的新闻）。
    """
    gates = cand.get("gates")
    cid = cand.get("id")
    if gates is None:
        return
    if not isinstance(gates, dict):
        findings.append(fnd("LEGACY_CHECKED_FIELDS_IGNORED", INFO, 5, cid,
                            "gates 不是对象，已完全忽略"))
        return
    findings.append(fnd("LEGACY_CHECKED_FIELDS_IGNORED", INFO, 5, cid,
                        "检测到 v0.1.0 的模型自报 checked 字段；v0.1.1 起不再作为放行依据",
                        "结论由程序按事实字段自行计算"))
    for key in LEGACY_CHECKED_FIELDS:
        if key in gates and gates.get(key) is not True:
            findings.append(fnd("LEGACY_GATE_REPORTED_FALSE", WARN, 3, cid,
                                "模型自报某项检查未通过；该字段已不再阻断，但说明流程可能没做完",
                                key))


def _check_history(cand, ctx, d, findings):
    """跨日去重。是否"有实质新进展"取自派生层。"""
    cid = cand.get("id")
    fp = d.get("fingerprint") or candidate_fingerprint(cand, ctx.get("aliases"))
    days = ctx.get("history_dedup_days", HISTORY_DEDUP_DAYS)
    now = ctx["now"]

    has_new_progress = bool(d.get("has_new_progress"))

    for rec in ctx.get("history_records") or []:
        if not isinstance(rec, dict):
            continue
        if rec.get("fingerprint") != fp:
            continue
        rec_date = parse_date(rec.get("date"))
        if rec_date is None:
            findings.append(fnd("HISTORY_LINE_INVALID", WARN, 4, cid,
                                "历史记录 date 无法解析", json.dumps(rec, ensure_ascii=False)))
            continue
        age = (now.date() - rec_date).days
        if age > days:
            continue
        if has_new_progress and cand.get("status") == "UPDATED":
            findings.append(fnd("HISTORY_MATCH_UPDATED", INFO, 5, cid,
                                "与历史事件同一 fingerprint，但存在实质新进展，按 UPDATED 输出",
                                "%s (%s 天前)" % (fp, age)))
        elif cand.get("status") == "DUPLICATE":
            findings.append(fnd("DUPLICATE_HISTORY", INFO, 5, cid,
                                "已正确判为历史重复", fp))
        else:
            findings.append(fnd("DUPLICATE_HISTORY", BLOCK, 0, cid,
                                "与最近 %d 天内已输出事件重复，且无实质新进展" % days,
                                "%s（%s 天前输出：%s）" % (fp, age, rec.get("title"))))


# ────────────────────────────────────────────────────────────────
# 七个顶层 Gate —— 读懂这份代码从这里开始
# ────────────────────────────────────────────────────────────────


def run_structure_gate(cand, ctx, d):
    """结构 Gate：schema、必填字段、URL、时间格式、枚举、输入结构。

    结构缺陷任何情况下都是 BLOCK —— 一条连字段都不完整的候选，
    没有讨论时效与证据的必要。
    """
    if not isinstance(cand, dict):
        return [fnd("CANDIDATE_NOT_OBJECT", BLOCK, 0, "?", "候选不是对象",
                    gate="structure")]

    out = []
    cid = cand.get("id") or "?"

    if cand.get("status") not in STATUSES:
        out.append(fnd("STATUS_INVALID", BLOCK, 0, cid,
                       "status 非法", str(cand.get("status"))))

    sec = cand.get("section")
    if sec in (ctx.get("banned_sections") or []):
        out.append(fnd("BANNED_SECTION", BLOCK, 2, cid,
                       "该栏目已被明确排除", str(sec)))
    elif sec not in (ctx.get("sections") or {}):
        out.append(fnd("SECTION_NOT_IN_WATCHLIST", BLOCK, 3, cid,
                       "栏目不在 watchlist 的 priority/sections 中", str(sec)))

    for field in ("entity", "action", "object"):
        if not norm_text(cand.get(field)):
            out.append(fnd("FINGERPRINT_INCOMPLETE", BLOCK, 1, cid,
                           "fingerprint 组成部分缺失", field))

    if parse_dt(cand.get("published_at") or cand.get("event_date")) is None:
        out.append(fnd("TIME_FIELD_MISSING", BLOCK, 0, cid,
                       "published_at / event_date 缺失或无法解析",
                       str(cand.get("published_at") or cand.get("event_date"))))

    mu = cand.get("material_update")
    if mu is not None and not isinstance(mu, dict):
        out.append(fnd("MATERIAL_UPDATE_INVALID", BLOCK, 1, cid,
                       "material_update 必须是对象", type(mu).__name__))

    # 字面违规（标题党、建议、分析、把"没搜到"写成"没新闻"、事实句计数）
    _check_language(cand, out)
    return tag_gate(out, "structure")


def run_freshness_gate(cand, ctx, d):
    """时效 Gate：24 小时窗口、旧闻、实质新进展、UPDATED 是否成立。"""
    out = []
    _check_time(cand, ctx, d, out)
    return tag_gate(out, "freshness")


def run_evidence_gate(cand, ctx, d):
    """证据 Gate：一手来源、交叉印证、evidence_status 是否合理、披露标记。"""
    out = []
    _check_sources(cand, ctx, d, out)
    return tag_gate(out, "evidence")


def run_duplication_gate(cand, ctx, d):
    """去重 Gate：跨日历史、fingerprint、UPDATED（本期内部去重在整期层做）。"""
    out = []
    _check_history(cand, ctx, d, out)
    return tag_gate(out, "duplication")


def run_importance_gate(cand, ctx, d):
    """重要性 Gate：这条信息是否值得占用用户注意力。"""
    out = []
    _check_importance(cand, ctx, d, out)
    return tag_gate(out, "importance")


def run_category_gate(cand, ctx, d):
    """栏目 Gate：归类是否合理、门槛是否满足。"""
    out = []
    _check_category(cand, ctx, d, out)
    return tag_gate(out, "category")


def run_output_gate(cand, ctx, d):
    """输出 Gate：PASS / UPDATED 是否可以真的进入输出。

    v0.1.0 的裁决保留：PASS 与 UPDATED 都是可输出终态，不退回"只有 PASS"。
    同时把 v0.1.0 的模型自报 checked 字段收口在这里并降级为参考信息。
    """
    out = []
    if cand.get("top_pick") and not is_output(cand):
        out.append(fnd("STATUS_NOT_PASS", BLOCK, 0, cand.get("id"),
                       "非可输出状态的条目被放进了「今天最值得看的 N 件事」",
                       "status=%s" % cand.get("status")))
    _check_legacy_checked(cand, out)
    return tag_gate(out, "output")


GATE_RUNNERS = [
    ("structure", run_structure_gate),
    ("freshness", run_freshness_gate),
    ("evidence", run_evidence_gate),
    ("duplication", run_duplication_gate),
    ("importance", run_importance_gate),
    ("category", run_category_gate),
    ("output", run_output_gate),
]


def check_candidate(cand, ctx, want_audit=False):
    """对单条候选依次执行七个 Gate。

    返回 findings（列表）；want_audit=True 时返回 (findings, audit)。
    audit 里含 decision / decision_reasons / gate_results / derived ——
    目的是让人一眼看出"为什么收录 / 为什么丢弃"。
    """
    if not isinstance(cand, dict):
        f = [fnd("CANDIDATE_NOT_OBJECT", BLOCK, 0, "?", "候选不是对象",
                 gate="structure")]
        return (f, None) if want_audit else f

    d = derive(cand, ctx)
    findings = []
    for _name, runner in GATE_RUNNERS:
        findings.extend(runner(cand, ctx, d))
    findings = sort_findings(findings)

    if not want_audit:
        return findings

    blocks = [x["code"] for x in findings if x["severity"] == BLOCK]
    warns = [x["code"] for x in findings if x["severity"] == WARN]
    if blocks:
        decision = "BLOCKED"
    elif is_output(cand):
        decision = cand.get("status")
    else:
        decision = "DROP"
    audit = {
        "id": cand.get("id"),
        "title": cand.get("title"),
        "section": cand.get("section"),
        "declared_status": cand.get("status"),
        "evidence_status": cand.get("evidence_status"),
        "reject_reason": cand.get("reject_reason"),
        "primary_url": cand.get("primary_url"),
        "decision": decision,
        "decision_reasons": sorted(set(blocks + warns)),
        "blocked_by": sorted(set(blocks)),
        "warned_by": sorted(set(warns)),
        "gate_results": gate_results(findings),
        "derived": d,
    }
    return findings, audit


def best_source_rank(cand):
    """来源质量排序键：越小越好。一手 > 二手 > 社交；同为来源时优先第一方。

    第三项是「来源条数」，用负数是为了让**更多来源**排在前面。
    早先写成正数，等于把"只有一条来源"当成更好的选择，
    结果同一事件同时有一手版和转载版时，会保转载、丢一手。
    """
    srcs = [s for s in (cand.get("sources") or []) if isinstance(s, dict)]
    ranks = [TIER_RANK.get(s.get("tier"), 9) for s in srcs]
    first_party = 0 if any(s.get("is_first_party") for s in srcs) else 1
    return (min(ranks) if ranks else 9, first_party, -len(srcs))


def resolve_issue_duplicates(cands, aliases=None):
    """本期内部去重：同一 fingerprint 只保留来源质量最好的一条。"""
    groups = {}
    for cand in cands:
        groups.setdefault(candidate_fingerprint(cand, aliases), []).append(cand)
    kept, dropped = [], []
    for fp, items in groups.items():
        if len(items) == 1:
            kept.append(items[0])
            continue
        ranked = sorted(items, key=lambda c: (best_source_rank(c), str(c.get("id"))))
        kept.append(ranked[0])
        dropped.extend(ranked[1:])
    return kept, dropped

# ────────────────────────────────────────────────────────────────
# 规则：整期
# ────────────────────────────────────────────────────────────────


def check_issue(issue, ctx):
    findings = []
    cands = list(iter_candidates(issue))

    if not cands:
        findings.append(fnd("ISSUE_NO_CANDIDATES", INFO, 5, "issue",
                            "本期无任何候选；信息少时就少写，允许只输出标准说明"))
        return findings, {"candidates": 0, "pass": 0, "top_pick": 0, "kept": 0, "dropped": 0}

    aliases = ctx.get("aliases")
    for cand in cands:
        findings.extend(check_candidate(cand, ctx))

    kept, dropped = resolve_issue_duplicates(cands, aliases)
    for cand in dropped:
        cid = cand.get("id")
        if is_output(cand) or cand.get("top_pick"):
            findings.append(fnd("DUPLICATE_IN_ISSUE", BLOCK, 1, cid,
                                "同一事件在本期出现多次且都被标为可输出；只应保留来源最好的一条",
                                candidate_fingerprint(cand, aliases)))
        else:
            findings.append(fnd("DUPLICATE_IN_ISSUE", INFO, 5, cid,
                                "本期内部重复，已按来源质量合并",
                                candidate_fingerprint(cand, aliases)))

    output = [c for c in kept if is_output(c)]

    unexp = [c for c in output if c.get("section") == "unexpected"]
    if len(unexp) > UNEXPECTED_MAX_PER_DAY:
        findings.append(fnd("UNEXPECTED_OVER_LIMIT", BLOCK, 3, "issue",
                            "「意外但重要」超过每日上限",
                            "%d 条 > %d 条" % (len(unexp), UNEXPECTED_MAX_PER_DAY)))

    top = [c for c in output if c.get("top_pick")]
    if len(top) > TOP_PICK_MAX:
        findings.append(fnd("TOP3_PADDING", BLOCK, 3, "issue",
                            "「今天最值得看的 N 件事」超过 3 条",
                            "top=%d" % len(top)))

    if len(output) > ISSUE_MAX_ITEMS:
        findings.append(fnd("TOO_MANY_ITEMS", WARN, 4, "issue",
                            "条目数超出常规区间 5—12",
                            "%d 条" % len(output)))
    if not output:
        findings.append(fnd("EMPTY_ISSUE", INFO, 5, "issue",
                            "本期无合格条目，应输出标准说明而非「没有新闻」"))

    # 同一个 URL 被多条内容当来源：通常意味着没有为每条内容找到各自的原文，
    # 而是拿一个周报/汇总页凑数。聚合页本身可信，但它不是「这条新闻」的来源。
    url_users = {}
    for cand in output:
        for s in (cand.get("sources") or []):
            if not isinstance(s, dict):
                continue
            u = str(s.get("url") or "")
            if u:
                url_users.setdefault(u, []).append(str(cand.get("id")))
    for url, ids in sorted(url_users.items()):
        if len(ids) >= 3:
            findings.append(fnd("SOURCE_URL_REUSED", WARN, 4, "issue",
                                "同一个来源 URL 被 3 条以上内容引用，通常说明没有找到各自的一手来源",
                                "%s ← %s" % (url, "、".join(ids))))

    order = ctx.get("sections_order") or []
    for cand in output:
        if cand.get("section") not in order:
            findings.append(fnd("SECTION_NOT_IN_PRIORITY", BLOCK, 3, cand.get("id"),
                                "栏目不在 priority 中，不得输出", str(cand.get("section"))))

    # deliverable：既声明可输出、又没有 BLOCK 的条目。
    # `pass` 统计的是"声明为可输出"，会被阻断项打脸；真正能发出去的是 deliverable。
    blocked_ids = {
        x.get("scope") for x in findings
        if x["severity"] == BLOCK and x.get("scope") not in (None, "issue")
    }
    deliverable = [c for c in output if c.get("id") not in blocked_ids]

    stats = {
        "candidates": len(cands),
        "pass": len(output),
        "deliverable": len(deliverable),
        "top_pick": len(top),
        "kept": len(kept),
        "dropped": len(dropped),
    }
    return sort_findings(findings), stats

# ────────────────────────────────────────────────────────────────
# 规则：渲染结果
# ────────────────────────────────────────────────────────────────


def check_render(text, issue, ctx):
    findings = []
    if not isinstance(text, str):
        return [fnd("RENDER_NOT_TEXT", BLOCK, 0, "render", "渲染结果不是文本")]
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")

    for i, line in enumerate(lines, 1):
        if TABLE_LINE_RE.match(line) or TABLE_SEP_RE.match(line):
            findings.append(fnd("TABLE_NOT_ALLOWED", BLOCK, 2, "行 %d" % i,
                                "输出不得使用 Markdown 表格", line.strip()[:60]))
            break

    for word in CLICKBAIT_WORDS:
        if word in text:
            findings.append(fnd("CLICKBAIT_TITLE", BLOCK, 2, "render",
                                "正文含标题党词汇", word))
    for word in ADVICE_WORDS:
        if word in text:
            findings.append(fnd("ADVICE_LEAK", BLOCK, 2, "render",
                                "正文含投资建议表述", word))
    for word in ANALYSIS_WORDS:
        if word in text:
            findings.append(fnd("ANALYSIS_LEAK", BLOCK, 2, "render",
                                "正文含影响分析或预测表述", word))
    for phrase in NO_NEWS_FALLACY_PHRASES:
        if phrase in text:
            findings.append(fnd("NO_NEWS_FALLACY", BLOCK, 0, "render",
                                "把「没搜索到」写成「没有新闻」", phrase))

    cands = list(iter_candidates(issue)) if issue else []
    output = [c for c in cands if is_output(c)]

    if not output:
        if CORRECT_EMPTY_PHRASE not in text:
            findings.append(fnd("EMPTY_ISSUE_PHRASE_MISSING", BLOCK, 0, "render",
                                "本期无条目时必须使用标准表述",
                                CORRECT_EMPTY_PHRASE))

    for cand in cands:
        if is_output(cand):
            continue
        title = str(cand.get("title") or "").strip()
        if len(title) >= TITLE_MIN_CHARS and title in text:
            findings.append(fnd("REJECTED_IN_OUTPUT", BLOCK, 0, cand.get("id"),
                                "未通过（非 PASS）的条目出现在了输出中", title))

    for cand in output:
        title = str(cand.get("title") or "").strip()
        if title and title not in text:
            findings.append(fnd("OUTPUT_ITEM_MISSING", BLOCK, 3, cand.get("id"),
                                "PASS 条目未出现在输出中", title))
        url = str(cand.get("primary_url") or "")
        if url and url not in text:
            findings.append(fnd("CITATION_MISSING", BLOCK, 1, cand.get("id"),
                                "输出中缺少该条目的来源引用", url))

    cited = set()
    for m in CITATION_RE.finditer(text):
        cited.add(m.group("url"))
    for m in MD_LINK_RE.finditer(text):
        cited.add(m.group(1))
    allowed = set()
    for cand in output:
        for s in cand.get("sources") or []:
            if isinstance(s, dict) and s.get("url"):
                allowed.add(str(s["url"]))
    stray = cited - allowed
    if stray:
        findings.append(fnd("CITATION_UNKNOWN_SOURCE", WARN, 2, "render",
                            "输出中引用了候选清单之外的链接",
                            ", ".join(sorted(stray)[:3])))

    top = [c for c in output if c.get("top_pick")]
    if len(top) > TOP_PICK_MAX:
        findings.append(fnd("TOP3_PADDING", BLOCK, 3, "render",
                            "「今天最值得看的 N 件事」超过 3 条",
                            "top=%d" % len(top)))
    if top:
        head = None
        for line in lines:
            if "今天最值得看的" in line:
                head = line
                break
        if head is None:
            findings.append(fnd("TOP_SECTION_MISSING", WARN, 4, "render",
                                "存在 top_pick 条目但缺少「今天最值得看的 N 件事」标题"))
        else:
            m = re.search(r"(\d+)\s*件", head)
            if m and int(m.group(1)) != len(top):
                findings.append(fnd("TOP_COUNT_MISMATCH", BLOCK, 3, "render",
                                    "标题声明条数与实际条数不一致",
                                    "%s vs %d" % (m.group(1), len(top))))
        # 一句话概述是否真的写出来了 —— 与标题是否存在无关，独立检查。
        for cand in top:
            line_text = str(cand.get("top_pick_line") or "").strip()
            if line_text and line_text not in text:
                findings.append(fnd("TOP_LINE_MISSING", WARN, 4, cand.get("id"),
                                    "top_pick 条目缺少一句话概述", line_text))

    for cand in output:
        sec = cand.get("section")
        label = ((ctx.get("sections") or {}).get(sec) or {}).get("label") or sec
        if label not in text:
            findings.append(fnd("SECTION_HEADING_MISSING", WARN, 4, cand.get("id"),
                                "输出中缺少栏目标题", label))

    for sec in (ctx.get("sections_order") or []):
        label = ((ctx.get("sections") or {}).get(sec) or {}).get("label")
        if label and label in text and not any(
                c.get("section") == sec for c in output):
            findings.append(fnd("EMPTY_SECTION_RENDERED", BLOCK, 3, sec,
                                "无内容的栏目不应出现在输出中", str(label)))

    for bad in (ctx.get("banned_sections") or []):
        if bad in text:
            findings.append(fnd("BANNED_SECTION", BLOCK, 2, "render",
                                "输出中出现被排除的栏目", str(bad)))

    blank = re.findall(r"\n{4,}", text)
    if blank:
        findings.append(fnd("FORMAT_BLANK_LINES", WARN, 5, "render",
                            "存在多余空行，影响手机阅读", "%d 处" % len(blank)))

    return sort_findings(findings)

# ────────────────────────────────────────────────────────────────
# 输入结构适配：裸数据 vs 测试夹具
# ────────────────────────────────────────────────────────────────


def iter_candidates(payload):
    """同时接受裸数据与夹具结构。

    裸数据：{"candidates": [...]} 或 {"date": ..., "items": [...]}
    夹具：  {"id": "test-01", "steps": [{"input": {...}}]}
    若不显式识别 steps，把夹具当裸数据读会静默产出错误结论而不报错。
    """
    if payload is None:
        return
    if isinstance(payload, list):
        for item in payload:
            for c in iter_candidates(item):
                yield c
        return
    if not isinstance(payload, dict):
        return

    if "steps" in payload and isinstance(payload["steps"], list):
        for step in payload["steps"]:
            if isinstance(step, dict):
                for key in ("input", "candidates", "issue"):
                    if key in step:
                        for c in iter_candidates(step[key]):
                            yield c
                        break
        return

    for key in ("candidates", "items"):
        if isinstance(payload.get(key), list):
            for c in iter_candidates(payload[key]):
                yield c
            return

    if isinstance(payload.get("issue"), dict):
        for c in iter_candidates(payload["issue"]):
            yield c
        return

    if payload.get("entity") or payload.get("section") or payload.get("fingerprint"):
        yield payload


def iter_issues(payload):
    """从文件里取出一个或多个 issue 结构。"""
    if isinstance(payload, dict) and isinstance(payload.get("steps"), list):
        for step in payload["steps"]:
            if isinstance(step, dict) and isinstance(step.get("input"), dict):
                yield step["input"]
        return
    if isinstance(payload, dict) and isinstance(payload.get("issue"), dict):
        yield payload["issue"]
        return
    if isinstance(payload, dict):
        yield payload

# ────────────────────────────────────────────────────────────────
# 历史记录读写
# ────────────────────────────────────────────────────────────────


def load_history(path):
    records, findings = [], []
    if not os.path.exists(path):
        return records, findings
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                findings.append(fnd("HISTORY_LINE_INVALID", WARN, 4, "行 %d" % i,
                                    "历史文件存在无法解析的行"))
                continue
            if not isinstance(rec, dict) or not rec.get("fingerprint"):
                findings.append(fnd("HISTORY_LINE_INVALID", WARN, 4, "行 %d" % i,
                                    "历史记录缺少 fingerprint"))
                continue
            records.append(rec)
    return records, findings


def build_history_records(issue, ctx, run_date):
    cands, _ = resolve_issue_duplicates(list(iter_candidates(issue)), ctx.get("aliases"))
    out = []
    for cand in cands:
        if not is_output(cand):
            continue
        fp = candidate_fingerprint(cand, ctx.get("aliases"))
        out.append({
            "event_id": "%s-%s" % (run_date, fp[:12]),
            "date": run_date,
            "entity": canon_entity(cand.get("entity"), ctx.get("aliases")),
            "action": norm_text(cand.get("action")),
            "object": norm_text(cand.get("object")),
            "title": cand.get("title"),
            "primary_url": cand.get("primary_url"),
            "fingerprint": fp,
            "section": cand.get("section"),
            "evidence_status": cand.get("evidence_status"),
            "was_update": cand.get("status") == "UPDATED",
            "superseded_fingerprint": cand.get("fingerprint")
            if cand.get("status") == "UPDATED" else None,
        })
    return out


def existing_keys(records):
    return {(r.get("fingerprint"), str(r.get("date"))) for r in records}


def prune_history(records, now, days=HISTORY_RETENTION_DAYS):
    kept = []
    for rec in records:
        d = parse_date(rec.get("date"))
        if d is None or (now.date() - d).days <= days:
            kept.append(rec)
    return kept

# ────────────────────────────────────────────────────────────────
# 审计：一眼看出为什么收录 / 为什么丢弃
# ────────────────────────────────────────────────────────────────


DECISION_DROPPED_IN_ISSUE = "DROPPED_IN_ISSUE"


def audit_issue(issue, ctx, run_date=None):
    """对整期候选逐条执行 Gate，并给出可审计的收录/丢弃理由。

    输出既是机器可读的 JSON，也能渲染成 audit.md。
    目的不是增加复杂度，而是回答"这条为什么进来了 / 为什么没进来"。
    """
    cands = list(iter_candidates(issue))
    findings_all, audits = [], []
    for c in cands:
        f, a = check_candidate(c, ctx, want_audit=True)
        findings_all.extend(f)
        audits.append(a)

    kept, dropped = resolve_issue_duplicates(cands, ctx.get("aliases"))
    dropped_ids = {c.get("id") for c in dropped}
    for a in audits:
        if a and a["id"] in dropped_ids and a["decision"] in OUTPUT_STATUSES:
            a["decision"] = DECISION_DROPPED_IN_ISSUE
            a["decision_reasons"] = sorted(set(a["decision_reasons"] + ["DUPLICATE_IN_ISSUE"]))

    issue_findings, stats = check_issue(issue, ctx)

    accepted = [a for a in audits if a and a["decision"] in OUTPUT_STATUSES]
    rejected = [a for a in audits if a and a["decision"] not in OUTPUT_STATUSES]

    # 发现项计数：每个 Gate 报了多少条 BLOCK。
    blocked_by_gate = {}
    for x in findings_all:
        if x["severity"] == BLOCK:
            g = x.get("gate") or "ungated"
            blocked_by_gate[g] = blocked_by_gate.get(g, 0) + 1

    # 条目归口：每个 Gate「挡下」了多少条候选。
    # 归口规则：优先 BLOCK，其次 WARN，最后 INFO；同级按 Gate 顺序取第一个。
    # 一个发现项都没有的条目，说明是 output Gate 按状态挡下的（如 LOW_VALUE、OLD）。
    by_scope = {}
    for x in findings_all:
        sc = x.get("scope")
        if sc in (None, "issue", "?"):
            continue
        by_scope.setdefault(sc, []).append(x)
    gate_order = {g: i for i, g in enumerate(GATES)}

    rejected_by_gate = {}
    for a in rejected:
        if a["decision"] == DECISION_DROPPED_IN_ISSUE:
            rejected_by_gate["duplication"] = rejected_by_gate.get("duplication", 0) + 1
            continue
        cand_findings = [x for x in by_scope.get(a["id"], [])
                         if x.get("gate") in gate_order]
        cand_findings.sort(key=lambda x: (_SEV_RANK[x["severity"]],
                                          gate_order[x["gate"]]))
        g = cand_findings[0]["gate"] if cand_findings else "output"
        rejected_by_gate[g] = rejected_by_gate.get(g, 0) + 1

    accepted_by_status = {}
    for a in accepted:
        accepted_by_status[a["decision"]] = accepted_by_status.get(a["decision"], 0) + 1
    accepted_by_section = {}
    for a in accepted:
        sec = a.get("section") or "?"
        accepted_by_section[sec] = accepted_by_section.get(sec, 0) + 1

    return {
        "date": str(issue.get("date") or (run_date or ctx["now"].strftime("%Y-%m-%d")))[:10],
        "now": ctx["now"].isoformat(),
        "candidates": len(cands),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "final_items": stats.get("deliverable", stats.get("pass", 0)),
        "stats": stats,
        "blocked_by_gate": blocked_by_gate,
        "rejected_by_gate": rejected_by_gate,
        "accepted_by_status": accepted_by_status,
        "accepted_by_section": accepted_by_section,
        "accepted": accepted,
        "rejected": rejected,
        "issue_findings": issue_findings,
    }


_AUDIT_GLYPH = {"PASS": "✓", "WARN": "!", "BLOCK": "✗"}


def render_audit_md(rep):
    """把审计结果写成 markdown。给人看的，栏目与顺序保持稳定。"""
    lines = []
    lines.append("# 审计 · %s" % rep["date"])
    lines.append("")
    lines.append("统计窗口终点：%s" % rep["now"])
    lines.append("")
    lines.append("## 总量")
    lines.append("")
    lines.append("- 候选总数：%d" % rep["candidates"])
    lines.append("- 收录（PASS/UPDATED）：%d" % rep["accepted_count"])
    if rep.get("accepted_by_status"):
        lines.append("  - 其中：" + "、".join(
            "%s %d" % (k, v) for k, v in sorted(rep["accepted_by_status"].items())))
    lines.append("- 丢弃：%d" % rep["rejected_count"])
    lines.append("- 最终条目数：%d" % rep["final_items"])
    lines.append("")

    if rep.get("accepted_by_section"):
        lines.append("## 收录分布")
        lines.append("")
        seen_sections = []
        for sec in list(SECTIONS) + sorted(rep["accepted_by_section"]):
            if sec in rep["accepted_by_section"] and sec not in seen_sections:
                seen_sections.append(sec)
                lines.append("- %s：%d" % (sec, rep["accepted_by_section"][sec]))
        lines.append("")

    if rep["rejected_by_gate"]:
        lines.append("## 各 Gate 拒绝数")
        lines.append("")
        for g in GATES:
            n = rep["rejected_by_gate"].get(g, 0)
            if n:
                lines.append("- %s：%d" % (g, n))
        extra = [g for g in rep["rejected_by_gate"] if g not in GATES]
        for g in sorted(extra):
            lines.append("- %s：%d" % (g, rep["rejected_by_gate"][g]))
        lines.append("")

    lines.append("## 逐条审计")
    lines.append("")
    for a in rep["accepted"] + rep["rejected"]:
        lines.append("### %s · %s" % (a["id"], a["decision"]))
        lines.append("")
        lines.append("- 标题：%s" % (a["title"] or ""))
        lines.append("- 栏目：%s｜声明状态：%s｜证据：%s"
                     % (a["section"], a["declared_status"], a["evidence_status"]))
        gr = a["gate_results"]
        lines.append("- Gate：" + "  ".join(
            "%s %s%s" % (g, gr.get(g, "PASS"), _AUDIT_GLYPH.get(gr.get(g, "PASS"), ""))
            for g in GATES))
        d = a["derived"]
        lines.append("- 派生：窗口内=%s｜一手=%s｜交叉来源=%d｜历史命中=%s｜实质事件=%s｜可输出=%s"
                     % (d.get("is_within_24h"), d.get("has_primary_source"),
                        d.get("verification_source_count", 0), d.get("history_match"),
                        d.get("has_material_event"), d.get("is_output_eligible")))
        if a["decision_reasons"]:
            lines.append("- 理由：%s" % "、".join(a["decision_reasons"]))
        if a.get("reject_reason"):
            lines.append("- 丢弃说明：%s" % a["reject_reason"])
        lines.append("")

    if rep["issue_findings"]:
        lines.append("## 整期级发现")
        lines.append("")
        for x in rep["issue_findings"]:
            lines.append("- [%s] %s（%s）" % (x["severity"], x["code"], x["scope"]))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ────────────────────────────────────────────────────────────────
# 打印
# ────────────────────────────────────────────────────────────────

_SEV_TAG = {BLOCK: "✗ BLOCK", WARN: "! WARN ", INFO: "· INFO "}


def print_findings(findings, limit=None):
    shown = findings if limit is None else front_stage(findings, limit)
    if not shown:
        print("  （无发现）")
    for x in shown:
        print("  %s [P%d] %-34s %s%s" % (
            _SEV_TAG.get(x["severity"], x["severity"]),
            x["priority"], x["code"], x["scope"],
            ("  <%s>" % x["gate"]) if x.get("gate") else ""))
        print("        %s" % x["message"])
        if x["detail"]:
            print("        → %s" % x["detail"])
    stats = summarize(findings)
    print("  小计：BLOCK=%d WARN=%d INFO=%d" % (stats["block"], stats["warn"], stats["info"]))

# ────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────


def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="zaobao_check.py",
        description="早间情报确定性规则层（零依赖）")
    parser.add_argument("command", choices=[
        "check-issue", "check-candidate", "check-render", "check-config",
        "audit", "derive", "fingerprint", "record", "prune"])
    parser.add_argument("path", nargs="?", help="输入文件路径")
    parser.add_argument("--repo", default=".", help="仓库根目录（默认当前目录）")
    parser.add_argument("--issue", help="check-render 用的候选文件")
    parser.add_argument("--history", help="历史 JSONL 路径")
    parser.add_argument("--now", help="覆盖当前时间（ISO 8601），用于测试")
    parser.add_argument("--entity")
    parser.add_argument("--action")
    parser.add_argument("--object")
    parser.add_argument("--days", type=int, default=HISTORY_RETENTION_DAYS)
    parser.add_argument("--write", action="store_true", help="真正写入历史文件")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--out-md", help="audit 子命令：把审计报告写成 markdown")
    parser.add_argument("--limit", type=int, default=3, help="前台展示条数上限")
    args = parser.parse_args(argv)

    repo = os.path.abspath(args.repo)
    now = parse_dt(args.now) or now_default()

    def emit(findings, extra=None):
        payload = {
            "command": args.command,
            "summary": summarize(findings),
            "findings": findings,
        }
        if extra:
            payload.update(extra)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_findings(findings, limit=args.limit)
        return 1 if has_block(findings) else 0

    if args.command == "fingerprint":
        cfg = load_config(repo, now=now)
        fp = make_fingerprint(args.entity, args.action, args.object, cfg["ctx"]["aliases"])
        if args.json:
            print(json.dumps({"fingerprint": fp}, ensure_ascii=False))
        else:
            print(fp)
        return 0

    if args.command == "check-config":
        return emit(check_config(repo, now=now))

    ctx = make_ctx(repo, now=now)

    if args.command == "derive":
        payload = _read_json(args.path)
        rows = []
        for issue in iter_issues(payload):
            for c in iter_candidates(issue):
                rows.append({"id": c.get("id"), "derived": derive(c, ctx)})
        if args.json:
            print(json.dumps({"derived": rows}, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                d = row["derived"]
                print("%-6s 窗口内=%-5s 一手=%-5s 交叉=%d 历史命中=%-5s 实质事件=%-5s 可输出=%s"
                      % (row["id"], d.get("is_within_24h"), d.get("has_primary_source"),
                         d.get("verification_source_count", 0), d.get("history_match"),
                         d.get("has_material_event"), d.get("is_output_eligible")))
        return 0

    if args.command == "audit":
        payload = _read_json(args.path)
        first = next(iter_issues(payload), {})
        rep = audit_issue(first, ctx)
        if args.out_md:
            with open(args.out_md, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render_audit_md(rep))
        if args.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            sys.stdout.write(render_audit_md(rep))
        return 1 if has_block(rep["issue_findings"]) else 0

    if args.command == "check-candidate":
        payload = _read_json(args.path)
        findings = []
        for cand in iter_candidates(payload):
            findings.extend(check_candidate(cand, ctx))
        return emit(findings)

    if args.command == "check-issue":
        payload = _read_json(args.path)
        all_findings, stats_list = [], []
        for issue in iter_issues(payload):
            found, stats = check_issue(issue, ctx)
            all_findings.extend(found)
            stats_list.append(stats)
        return emit(sort_findings(all_findings), {"issues": stats_list})

    if args.command == "check-render":
        if not args.issue:
            parser.error("check-render 需要 --issue")
        text = _read_text(args.path)
        issue = _read_json(args.issue)
        first = next(iter_issues(issue), {})
        return emit(check_render(text, first, ctx))

    if args.command in ("record", "prune"):
        if not args.history:
            parser.error("%s 需要 --history" % args.command)
        records, findings = load_history(args.history)
        if args.command == "prune":
            kept = prune_history(records, now, args.days)
            findings.append(fnd("HISTORY_PRUNED", INFO, 5, os.path.basename(args.history),
                                "按保留天数裁剪历史", "%d → %d 条" % (len(records), len(kept))))
            if args.write:
                with open(args.history, "w", encoding="utf-8") as fh:
                    for rec in kept:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return emit(findings)

        if not args.path and not args.issue:
            parser.error("record 需要 issue 文件（位置参数或 --issue）")
        issue = _read_json(args.issue or args.path)
        run_date = args.now[:10] if args.now else now.strftime("%Y-%m-%d")
        added = []
        seen = existing_keys(records)
        for one in iter_issues(issue):
            for rec in build_history_records(one, ctx, run_date):
                key = (rec["fingerprint"], rec["date"])
                if key in seen:
                    continue
                seen.add(key)
                added.append(rec)
        if args.write and added:
            with open(args.history, "a", encoding="utf-8") as fh:
                for rec in added:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        findings.append(fnd("HISTORY_RECORDED", INFO, 5,
                            os.path.basename(args.history),
                            "写入历史记录" if args.write else "试运行，未写入",
                            "新增 %d 条" % len(added)))
        return emit(findings, {"added": added})

    return 0


if __name__ == "__main__":
    sys.exit(main())
