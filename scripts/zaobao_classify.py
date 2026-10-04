#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早间情报 · 统一来源分类器（零依赖，v0.1.1 新增）

为什么改写这一层
----------------
v0.1.0 的做法是：模型声明 `sources[].tier`，程序检查声明与域名清单是否自洽。
这有两个问题：

1. 判定主体仍然是模型。程序只在"说不清理由"时拦一下。
2. `discovery_only` / `never_a_source` 这类黑名单**不可能覆盖整个互联网**，
   靠堆域名解决不了问题。

v0.1.1 改为**正向证据优先**：先回答「这个来源是不是原始发布者」，
再回答「是不是政府 / 监管 / 交易所」，再回答「是不是公司正式公告 /
官方博客 / GitHub / 论文原文」，最后才落到"不是的话，有没有可靠独立来源交叉确认"。
黑名单只作为辅助，专门排除搜索引擎结果页与内容农场。

输出 9 个类别（语义分层，名字可以改，语义不要改）：

    PRIMARY_OFFICIAL      政府、监管机构、交易所、境外官方机构
    PRIMARY_COMPANY       公司官方公告、官网、官方博客、官方新闻稿
    PRIMARY_AUTHOR        事件当事人本人的公开发布（负责人声明、作者原文）
    PRIMARY_PAPER         正式论文原文（arXiv、期刊）
    PRIMARY_REPOSITORY    官方代码仓库与模型发布页（GitHub、HuggingFace）
    TRUSTED_SECONDARY     高质量媒体；央媒通稿可另标 quasi_primary
    DISCOVERY_ONLY        只用于发现线索的平台
    UNKNOWN               清单外域名，需要人工说明分层理由
    REJECTED              搜索引擎结果页、内容农场 —— 永不作为来源

分类是**程序计算出的**结论，不是模型的声明。模型的 `tier` 只作为提示保留，
两者不一致时由规则层给出发现项。
"""

from __future__ import annotations

import re

# ────────────────────────────────────────────────────────────────
# 类别常量
# ────────────────────────────────────────────────────────────────

PRIMARY_OFFICIAL = "PRIMARY_OFFICIAL"
PRIMARY_COMPANY = "PRIMARY_COMPANY"
PRIMARY_AUTHOR = "PRIMARY_AUTHOR"
PRIMARY_PAPER = "PRIMARY_PAPER"
PRIMARY_REPOSITORY = "PRIMARY_REPOSITORY"
TRUSTED_SECONDARY = "TRUSTED_SECONDARY"
DISCOVERY_ONLY = "DISCOVERY_ONLY"
UNKNOWN = "UNKNOWN"
REJECTED = "REJECTED"

SOURCE_CLASSES = [
    PRIMARY_OFFICIAL, PRIMARY_COMPANY, PRIMARY_AUTHOR,
    PRIMARY_PAPER, PRIMARY_REPOSITORY,
    TRUSTED_SECONDARY, DISCOVERY_ONLY, UNKNOWN, REJECTED,
]

PRIMARY_CLASSES = frozenset({
    PRIMARY_OFFICIAL, PRIMARY_COMPANY, PRIMARY_AUTHOR,
    PRIMARY_PAPER, PRIMARY_REPOSITORY,
})

# 兼容 v0.1.0 的 tier 取值 → 计算类别
_TIER_TO_CLASS = {
    "primary": PRIMARY_OFFICIAL,
    "trusted_secondary": TRUSTED_SECONDARY,
    "discovery_only": DISCOVERY_ONLY,
}

# ────────────────────────────────────────────────────────────────
# 域名形态规则（正向证据的第一层：看后缀就知道是不是官方）
# ────────────────────────────────────────────────────────────────

# 政府域名后缀。命中即 PRIMARY_OFFICIAL。
_OFFICIAL_SUFFIXES = (
    ".gov.cn", ".gov", ".gov.uk", ".gov.hk", ".gov.au", ".gov.sg",
    ".go.jp", ".gob.es", ".gouv.fr", ".gov.br", ".gov.in",
    ".govt.nz", ".europa.eu", ".gov.ru", ".gov.za",
)

# 政府 / 央行 / 国际组织：以完整主机名精确匹配
_OFFICIAL_EXACT = frozenset({
    "gov.cn", "federalreserve.gov", "sec.gov", "esma.europa.eu",
    "ecb.europa.eu", "boj.or.jp", "imf.org", "worldbank.org",
    "oecd.org", "who.int", "un.org", "europa.eu", "whitehouse.gov",
    "congress.gov", "ecfr.gov",
})

# 交易所与登记结算机构
_EXCHANGE = frozenset({
    "sse.com.cn", "szse.cn", "bse.cn", "chinaclear.cn", "cninfo.com.cn",
    "neeq.com.cn", "cffex.com.cn", "shclearing.com.cn",
})

# 论文原文
_PAPER = frozenset({"arxiv.org", "nature.com", "science.org"})

# 代码仓库与模型发布页
_REPOSITORY = frozenset({"github.com", "huggingface.co"})


def host_of(url):
    """从 URL 取出主机名。非 http(s) 返回空串。"""
    if not isinstance(url, str):
        return ""
    m = re.match(r"^https?://([^/?#]+)", url.strip(), re.I)
    if not m:
        return ""
    return m.group(1).lower().split("@")[-1].split(":")[0]


def domain_hit(host, domains):
    """host 是否命中域名清单中的某一项（含子域）。返回命中的条目或 None。"""
    for d in domains or []:
        d = str(d).strip().lower()
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return d
    return None


def is_never_source(url, never_list):
    """搜索引擎结果页、内容农场 —— 永远不能作为来源。

    never_list 的条目可以是纯域名（整个站都排除），也可以是 `域名/路径前缀`
    （只排除该站下的搜索结果页，例如 `baidu.com/s`）。
    """
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


def _official_kind(host):
    """已知官方主机名 → 具体子类。不认识返回 None。"""
    if host in _OFFICIAL_EXACT:
        return PRIMARY_OFFICIAL
    if host in _EXCHANGE:
        return PRIMARY_OFFICIAL
    if host in _PAPER:
        return PRIMARY_PAPER
    if host in _REPOSITORY:
        return PRIMARY_REPOSITORY
    if any(host.endswith(sfx) for sfx in _OFFICIAL_SUFFIXES):
        return PRIMARY_OFFICIAL
    return None


def classify_host(host, ctx):
    """只看主机名，给出它的**默认**类别。这是正向证据的第一层。"""
    if not host:
        return UNKNOWN, "无法解析主机名"

    if domain_hit(host, ctx.get("never_a_source") or []) and "/" not in host:
        return REJECTED, "命中永不作为来源清单"

    kind = _official_kind(host)
    if kind is not None:
        return kind, "主机名形态或已知官方清单命中"

    if domain_hit(host, ctx.get("primary_domains") or []):
        # 落在 primary 清单但不是政府/交易所/论文/仓库 → 视为公司与组织官方
        return PRIMARY_COMPANY, "命中 sources.yaml primary 清单"

    if domain_hit(host, ctx.get("trusted_domains") or []):
        return TRUSTED_SECONDARY, "命中 trusted_secondary 清单"

    if domain_hit(host, ctx.get("discovery_domains") or []):
        return DISCOVERY_ONLY, "命中 discovery_only 清单"

    return UNKNOWN, "清单之外的域名，需人工说明分层理由"


def classify_source(src, ctx, entity=None):
    """对单条来源给出程序计算的类别。

    返回 dict：
        class        计算出的类别
        is_primary   是否为可支撑 VERIFIED_PRIMARY 的一手来源
        kind         与 class 同义，保留给报告可读性
        host         解析出的主机名
        reason       判定理由（可审计）
        declared     模型声明的 tier（仅作提示）
        mismatch     计算类别与声明类别是否不一致
        quasi_primary 是否为央媒通稿（准一手）
        justified_first_party 是否走了「第一方 + 理由」的补证路径
    """
    src = src if isinstance(src, dict) else {}
    url = str(src.get("url") or "")
    host = host_of(url)
    declared = src.get("tier")
    never = is_never_source(url, ctx.get("never_a_source"))

    out = {
        "url": url,
        "host": host,
        "declared": declared,
        "class": UNKNOWN,
        "kind": UNKNOWN,
        "is_primary": False,
        "reason": "",
        "mismatch": False,
        "quasi_primary": False,
        "justified_first_party": False,
        "justified_trusted_secondary": False,
    }

    if never:
        out["class"] = out["kind"] = REJECTED
        out["reason"] = "命中永不作为来源清单（%s）" % never
        out["mismatch"] = declared != "discovery_only"
        return out

    cls, reason = classify_host(host, ctx)

    # 未落在一手类别里时，允许用「第一方 + 分层理由」补证为一手。
    # 这是正向证据里"是不是原始发布者"这一问的人工通道，但必须留下理由。
    # 注意：这条通道同样适用于 discovery_only 域名（例如当事人本人的微博），
    # 但规则层会另出一项 WARN 提醒人工确认发布者身份。
    if cls not in PRIMARY_CLASSES:
        justified = bool(src.get("is_first_party")) and bool(str(src.get("tier_reason") or "").strip())
        if justified:
            reason = "未落在一手类别，但声明为第一方并给出了分层理由"
            cls = PRIMARY_OFFICIAL
            out["justified_first_party"] = True
        elif (host and declared == "trusted_secondary"
              and str(src.get("tier_reason") or "").strip()):
            # 与「第一方 + 理由」通道对称：域名清单不可能穷尽，
            # 声明为可信二手并写明分层理由的清单外域名，按可信二手计入交叉验证。
            # 必须同时有 host 与理由，避免空 URL 或随手声明把交叉验证撑起来。
            reason = "清单外域名，但声明为可信二手并给出了分层理由"
            cls = TRUSTED_SECONDARY
            out["justified_trusted_secondary"] = True

    out["class"] = out["kind"] = cls
    out["reason"] = reason
    out["is_primary"] = cls in PRIMARY_CLASSES

    if domain_hit(host, ctx.get("quasi_primary_domains") or []):
        out["quasi_primary"] = True

    effective_tier = {
        PRIMARY_OFFICIAL: "primary", PRIMARY_COMPANY: "primary",
        PRIMARY_AUTHOR: "primary", PRIMARY_PAPER: "primary",
        PRIMARY_REPOSITORY: "primary",
        TRUSTED_SECONDARY: "trusted_secondary",
        DISCOVERY_ONLY: "discovery_only",
        UNKNOWN: None, REJECTED: None,
    }.get(cls)
    if declared in _TIER_TO_CLASS and effective_tier and declared != effective_tier:
        out["mismatch"] = True

    return out


def classify_sources(cand, ctx):
    """对一条候选的全部来源分类。"""
    return [classify_source(s, ctx, cand.get("entity"))
            for s in (cand.get("sources") or []) if isinstance(s, dict)]


def publisher_key(src):
    """交叉验证时用来区分"是不是同一家"。优先取 publisher，缺失时退回主机名。"""
    pub = str(src.get("publisher") or "").strip()
    if pub:
        return pub
    return host_of(str(src.get("url") or ""))


def summarize_classes(classes):
    """把分类结果压成计数，放进审计输出。"""
    counts = {}
    for c in classes:
        counts[c["class"]] = counts.get(c["class"], 0) + 1
    return counts
