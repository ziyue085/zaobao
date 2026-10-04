#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 确定性规则层（零依赖，仅标准库）

设计边界（重要）
----------------
本脚本只做「可判定」的检查：

    ✅ 字段是否缺失 / 是否三态缺席
    ✅ 时间是否落在 24 小时窗口内
    ✅ fingerprint 是否与最近 N 天历史重复、本期内部是否重复
    ✅ evidence_status 与来源层级是否自洽
    ✅ 枚举是否合法、计数是否越界
    ✅ 字面违规（标题党、投资建议、影响分析、表格、把「没搜到」写成「没新闻」）

它**不做**研究、不生成内容、不判断「这条新闻重不重要」。
判断重要性是模型在 SKILL.md 流程里的工作，本脚本只负责在模型出错时拦住它。

分级
----
    BLOCK  禁止输出。存在任一 BLOCK 即视为本期不可发布。
    WARN   必须显式处理（可在报告中说明后放行）。
    INFO   记录用，不影响发布。

发现项结构固定为 code / severity / priority / scope / message / detail。
code 稳定不变，因为测试按 code 断言。

用法
----
    zaobao_check.py check-issue   <issue.json>  [--repo .] [--now ISO] [--json]
    zaobao_check.py check-candidate <candidate.json> [--repo .] [--now ISO] [--json]
    zaobao_check.py check-render  <output.md>   --issue <issue.json> [--repo .] [--json]
    zaobao_check.py check-config  [--repo .] [--json]
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

REQUIRED_GATES = [
    "time_window_checked", "history_dedup_checked", "issue_dedup_checked",
    "primary_source_checked", "url_checked", "no_analysis_checked",
]

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


def fnd(code, severity, priority, scope, message, detail=""):
    return {
        "code": code,
        "severity": severity,
        "priority": priority,
        "scope": scope,
        "message": message,
        "detail": detail,
    }


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
    return {
        "block": sum(1 for x in findings if x["severity"] == BLOCK),
        "warn": sum(1 for x in findings if x["severity"] == WARN),
        "info": sum(1 for x in findings if x["severity"] == INFO),
        "codes": sorted({x["code"] for x in findings}),
    }

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
# URL
# ────────────────────────────────────────────────────────────────


def host_of(url):
    if not isinstance(url, str):
        return ""
    m = re.match(r"^https?://([^/?#]+)", url.strip(), re.I)
    if not m:
        return ""
    return m.group(1).lower().split("@")[-1].split(":")[0]


def domain_hit(host, domains):
    for d in domains or []:
        d = str(d).strip().lower()
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return d
    return None


def is_never_source(url, never_list):
    """搜索引擎结果页、内容农场 —— 永远不能作为来源。"""
    if not isinstance(url, str):
        return None
    host = host_of(url)
    if not host:
        return None
    path = url.strip()
    for entry in never_list or []:
        entry = str(entry).strip().lower()
        if not entry:
            continue
        if "/" in entry:
            dom, _, pathpart = entry.partition("/")
            if domain_hit(host, [dom]) and ("/" + pathpart) in path:
                return entry
        elif domain_hit(host, [entry]):
            return entry
    return None


def is_valid_url(url):
    return bool(re.match(r"^https?://[^\s/]+", str(url or "").strip(), re.I))

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


def _check_time(cand, ctx, findings):
    now = ctx["now"]
    window = timedelta(hours=ctx.get("window_hours", WINDOW_HOURS))
    status = cand.get("status")

    event_dt = parse_dt(cand.get("event_date"))
    if event_dt is None:
        findings.append(fnd("TIME_FIELD_MISSING", BLOCK, 0, cand.get("id"),
                            "event_date 缺失或无法解析",
                            str(cand.get("event_date"))))
        return

    np_at = parse_dt(cand.get("new_progress_at"))
    np_type = cand.get("new_progress_type")
    has_new_progress = (
        np_type in NEW_PROGRESS_TYPES
        and np_at is not None
        and timedelta(0) <= (now - np_at) <= window
    )

    if event_dt > now:
        findings.append(fnd("TIME_IN_FUTURE", BLOCK, 0, cand.get("id"),
                            "事件时间晚于当前时间", str(cand.get("event_date"))))
        return

    if (now - event_dt) <= window:
        if has_new_progress and status == "OLD":
            findings.append(fnd("STATUS_SHOULD_BE_UPDATED", BLOCK, 0, cand.get("id"),
                                "事件在窗内且有新进展，却被标为 OLD"))
        return

    # 事件本身在窗外
    if has_new_progress:
        if status != "UPDATED":
            findings.append(fnd("STATUS_SHOULD_BE_UPDATED", BLOCK, 0, cand.get("id"),
                                "旧事件出现实质新进展，状态应为 UPDATED",
                                "当前 %s，new_progress_type=%s" % (status, np_type)))
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


def _check_sources(cand, ctx, findings):
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

    valid_srcs = []
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
        declared = domain_hit(host, ctx.get("%s_domains" % s_tier) or [])
        if s_tier == "primary" and not declared:
            if not s.get("is_first_party") or not str(s.get("tier_reason") or "").strip():
                findings.append(fnd(
                    "PRIMARY_TIER_NOT_JUSTIFIED", BLOCK, 1, cid,
                    "域名不在 primary 清单中，且未声明 is_first_party + tier_reason",
                    url))
                continue
            if domain_hit(host, ctx.get("discovery_domains") or []):
                findings.append(fnd(
                    "DISCOVERY_DOMAIN_AS_PRIMARY", WARN, 3, cid,
                    "把通常只用于发现线索的平台声明为一手来源，需确认发布者确为当事人或官方账号",
                    url))
        valid_srcs.append(s)

    if not valid_srcs:
        return

    primary_srcs = [s for s in valid_srcs if s.get("tier") == "primary"]
    quasi_srcs = [
        s for s in valid_srcs
        if domain_hit(host_of(str(s.get("url"))), ctx.get("quasi_primary_domains") or [])
    ]

    if tier == "VERIFIED_PRIMARY" and not primary_srcs:
        findings.append(fnd("PRIMARY_SOURCE_MISSING", _sev_for_status(cand), 1, cid,
                            "声明 VERIFIED_PRIMARY 但没有任何 primary 来源"))

    if tier == "VERIFIED_CROSS_SOURCE":
        publishers = {
            str(s.get("publisher") or host_of(str(s.get("url"))))
            for s in valid_srcs
            if s.get("tier") in ("primary", "trusted_secondary")
        }
        if len(publishers) < 2:
            findings.append(fnd("INSUFFICIENT_CROSS_SOURCE", _sev_for_status(cand), 1, cid,
                                "声明多源交叉印证，但可信来源不足 2 家",
                                ", ".join(sorted(publishers))))
        if primary_srcs:
            findings.append(fnd("CROSS_SOURCE_HAS_PRIMARY", _sev_for_status(cand, WARN), 3, cid,
                                "已存在一手来源，evidence_status 宜升为 VERIFIED_PRIMARY"))

    if tier == "SECONDARY_ONLY" and cand.get("disclosure") != DISCLOSURE_SECONDARY:
        findings.append(fnd("MISSING_DISCLOSURE", _sev_for_status(cand), 1, cid,
                            "仅有可信二手报道，必须标注「%s」" % DISCLOSURE_SECONDARY,
                            "disclosure=%s" % cand.get("disclosure")))

    if tier == "UNVERIFIED":
        if cand.get("disclosure") != DISCLOSURE_UNVERIFIED:
            findings.append(fnd("MISSING_DISCLOSURE", _sev_for_status(cand), 1, cid,
                                "证据不足，必须标注「%s」" % DISCLOSURE_UNVERIFIED,
                                "disclosure=%s" % cand.get("disclosure")))
        if cand.get("section") != "unexpected":
            findings.append(fnd("UNVERIFIED_NOT_ALLOWED", _sev_for_status(cand), 1, cid,
                                "UNVERIFIED 只允许出现在「意外但重要」，且国内普通新闻应直接删除",
                                "section=%s" % cand.get("section")))

    if len(valid_srcs) == len([
            s for s in valid_srcs if s.get("tier") == "discovery_only"]):
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


def _check_section_gate(cand, findings):
    """栏目准入门槛。

    门槛类问题只在条目真的进入输出时才是阻断项 —— 一个已经被丢弃的候选
    不需要再满足栏目准入条件，否则报告会被无关噪声淹没。
    """
    sec = cand.get("section")
    cid = cand.get("id")
    status = cand.get("status")

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

    if sec in ("investment", "ai"):
        if "has_material_event" not in cand:
            findings.append(fnd("GATE_FIELD_UNCHECKED", BLOCK, 0, cid,
                                "has_material_event 缺席 —— 未检查 ≠ 已通过",
                                "section=%s" % sec))
        elif cand.get("has_material_event") is False:
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


def _check_gates(cand, findings):
    if not is_output(cand):
        return
    gates = cand.get("gates")
    cid = cand.get("id")
    if not isinstance(gates, dict):
        findings.append(fnd("GATE_FIELD_UNCHECKED", BLOCK, 0, cid,
                            "gates 整体缺席 —— 未检查 ≠ 已通过"))
        return
    for key in REQUIRED_GATES:
        if key not in gates:
            findings.append(fnd("GATE_FIELD_UNCHECKED", BLOCK, 0, cid,
                                "闸门字段缺席，视同未检查", key))
        elif gates.get(key) is not True:
            findings.append(fnd("GATE_NOT_PASSED", BLOCK, 0, cid,
                                "闸门未通过却标记为 PASS", key))


def _check_history(cand, ctx, findings):
    cid = cand.get("id")
    fp = candidate_fingerprint(cand, ctx.get("aliases"))
    days = ctx.get("history_dedup_days", HISTORY_DEDUP_DAYS)
    now = ctx["now"]

    np_at = parse_dt(cand.get("new_progress_at"))
    has_new_progress = (
        cand.get("new_progress_type") in NEW_PROGRESS_TYPES
        and np_at is not None
        and (now - np_at) >= timedelta(0)
    )

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


def check_candidate(cand, ctx):
    """对单条候选执行全部可判定检查。"""
    findings = []
    if not isinstance(cand, dict):
        return [fnd("CANDIDATE_NOT_OBJECT", BLOCK, 0, "?", "候选不是对象")]

    cid = cand.get("id") or "?"

    if cand.get("status") not in STATUSES:
        findings.append(fnd("STATUS_INVALID", BLOCK, 0, cid,
                            "status 非法", str(cand.get("status"))))

    sec = cand.get("section")
    if sec in (ctx.get("banned_sections") or []):
        findings.append(fnd("BANNED_SECTION", BLOCK, 2, cid,
                            "该栏目已被明确排除", str(sec)))
    elif sec not in (ctx.get("sections") or {}):
        findings.append(fnd("SECTION_NOT_IN_WATCHLIST", BLOCK, 3, cid,
                            "栏目不在 watchlist 的 priority/sections 中", str(sec)))

    for field in ("entity", "action", "object"):
        if not norm_text(cand.get(field)):
            findings.append(fnd("FINGERPRINT_INCOMPLETE", BLOCK, 1, cid,
                                "fingerprint 组成部分缺失", field))

    _check_time(cand, ctx, findings)
    _check_sources(cand, ctx, findings)
    _check_language(cand, findings)
    _check_section_gate(cand, findings)
    _check_gates(cand, findings)
    _check_history(cand, ctx, findings)

    if cand.get("top_pick") and not is_output(cand):
        findings.append(fnd("STATUS_NOT_PASS", BLOCK, 0, cid,
                            "非可输出状态的条目被放进了「今天最值得看的 N 件事」",
                            "status=%s" % cand.get("status")))

    return sort_findings(findings)


def best_source_rank(cand):
    """来源质量排序键：越小越好。一手 > 二手 > 社交；同为来源时优先第一方。"""
    srcs = [s for s in (cand.get("sources") or []) if isinstance(s, dict)]
    ranks = [TIER_RANK.get(s.get("tier"), 9) for s in srcs]
    first_party = 0 if any(s.get("is_first_party") for s in srcs) else 1
    return (min(ranks) if ranks else 9, first_party, len(srcs))


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

    order = ctx.get("sections_order") or []
    for cand in output:
        if cand.get("section") not in order:
            findings.append(fnd("SECTION_NOT_IN_PRIORITY", BLOCK, 3, cand.get("id"),
                                "栏目不在 priority 中，不得输出", str(cand.get("section"))))

    stats = {
        "candidates": len(cands),
        "pass": len(output),
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
# 打印
# ────────────────────────────────────────────────────────────────

_SEV_TAG = {BLOCK: "✗ BLOCK", WARN: "! WARN ", INFO: "· INFO "}


def print_findings(findings, limit=None):
    shown = findings if limit is None else front_stage(findings, limit)
    if not shown:
        print("  （无发现）")
    for x in shown:
        print("  %s [P%d] %-34s %s" % (
            _SEV_TAG.get(x["severity"], x["severity"]),
            x["priority"], x["code"], x["scope"]))
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
        "fingerprint", "record", "prune"])
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
