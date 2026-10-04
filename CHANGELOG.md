# 变更记录

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.1] - 2026-10-04

### 这一版在修什么

v0.1.0 的三个结构性问题：

1. **放行依据是模型自报的。** 候选里写 `time_window_checked: true`、`primary_source_checked: true`，
   程序就只能相信它。等于把"我查过了"当成了"事实成立"。
2. **规则是几十个零散 code，看不出主线。** 83 个 code 平铺在一起，
   没人能从顶层读懂"一条内容是怎么被放行的"。
3. **来源判定靠黑名单。** 黑名单不可能覆盖整个互联网，
   遇到清单外的域名只能束手无策。

这一版的核心原则只有一句：**能由程序根据原始字段计算的判断，不允许继续依赖模型自报。**

### Changed

- **`checked` 型自报字段不再作为放行依据。**
  `gates.*_checked` 与 `has_material_event` 保留读取以兼容旧数据，
  但字段缺席不再判为失败（记 `LEGACY_CHECKED_FIELDS_IGNORED` INFO），
  显式为 false 只记 WARN，不再阻断。
- **候选改为保存可审计事实，而不是保存结论。**
  新增 `published_at` / `event_time` / `discovered_at` / `material_update{claim,published_at,source_url}` /
  `previous_event_id` / `importance_reason` / `watchlist_subject`。
  `has_material_event` 被 `material_update` 事实块取代 —— 不是"我相信有事件"，而是"凭什么说有事件"。
- **引入七个顶层 Gate。** `structure / freshness / evidence / duplication / importance / category / output`。
  rule code 退化为 Gate 内部的诊断信息（`finding.gate` 归口），
  顶层逻辑改成 `run_structure_gate()` … `run_output_gate()`，读代码从 Gate 开始读。
- **来源判定改为正向证据优先。** 新增 `scripts/zaobao_classify.py`，
  输出 9 个类别（PRIMARY_OFFICIAL / PRIMARY_COMPANY / PRIMARY_AUTHOR / PRIMARY_PAPER /
  PRIMARY_REPOSITORY / TRUSTED_SECONDARY / DISCOVERY_ONLY / UNKNOWN / REJECTED）。
  先问"是不是原始发布者"，再问"是不是政府/监管/交易所"，最后才落到"有没有可靠独立来源交叉确认"。
  黑名单只用于排除搜索引擎结果页与内容农场。
- **增加实战评估层。** `tests/evals/` 保存真实窗口的候选集、审计、输出与人工标签；
  `tests/run_eval_round.py` 把一轮候选走完整条流程并落盘；
  `tests/run_eval_summary.py` 把逐条人工标签汇总成记分卡；
  `tests/compare_rounds.py` 比对同窗口两轮检索的差异。
  新增 `docs/evaluation.md`。
- **增加输出可读性检查层。** 新增 `tests/check_output_readability.py`：
  按微信阅读标准检查标题长度、每段句数、单段字符数、Markdown 表格、
  来源链接是否可点击、整期阅读时长。Gate 只管"能不能发"，这一层管"读不读得下去"。
- `audit` 子命令改为输出可审计的收录/丢弃理由，并给出逐 Gate 的拒绝数；
  `derive` 子命令可以直接查看程序算出的派生状态。
- `SKILL.md` 新增第六节「候选里写什么：事实字段，不是结论」与七个顶层 Gate 的说明。

### 实战评估结果（v0.1.1 验收依据）

6 轮真实窗口 + 1 组三段跨日链路，共 23 条产出，逐条人工打标签：

```text
TOTAL_OUTPUT_ITEMS=23   GOOD=18   SHOULD_NOT_INCLUDE=5
BAD_SOURCE=0   OLD=0   DUPLICATE=0   WRONG_CATEGORY=0
MISSED_IMPORTANT=4      GOOD_RATE=0.78
REGRESSION_STATUS=PASS      15 用例 / 85 步
CLI_SMOKE_STATUS=PASS       29 项
MUTATION_STATUS=PASS        25/25
```

各轮验证的重点：

| 轮次 | 场景 | 结果 |
|---|---|---|
| round-01 | 当前真实 24 小时 | 12 候选 → 5 条输出；5 条媒体转载的旧闻被判 OLD |
| round-02 | 同窗口换查询词重跑 | 8 候选 → 3 条输出；误收（清单外个股并购）被 Gate 拦下 |
| round-03 | 历史高密度日 | 12 候选 → 7 条输出，未失控、未超限 |
| round-04 | 历史低密度日 | 6 候选 → 2 条输出，**不凑数** |
| round-05 | 跨日 PASS → DUPLICATE → UPDATED | 三条链路全部判定正确；Day2 零输出且用标准表述 |
| round-06 | 来源压力测试 | 5 候选 → 2 条输出；三类来源缺陷被三种 code 分别拒绝 |

**最重要的一条结论**：这套改造的价值不在"架构更干净"，而在旧闻、重复、来源不成立这三类
**可以由程序判定**的错误已经归零（`OLD=0 / DUPLICATE=0 / BAD_SOURCE=0`）。
剩下的 5 条误收全部属于"事实没错但不该占版面"，即重要性判断 —— 那是刻意保留给模型的部分。

### Fixed

- **投资／AI 条目缺少实质事件证据仍可输出** —— 改为必须给出字段完整的 `material_update`，
  且时间必须落在窗口内、来源 URL 不能是搜索页。
- **声明 UPDATED 却拿不出新进展** —— 新增 `UPDATED_NOT_SUBSTANTIATED`：
  必须给出 `new_progress_at + new_progress_type`，或字段完整的 `material_update`。
- **"只有可信二手"可以靠写一句披露标记就放行** ——
  新增 `SECONDARY_SOURCE_MISSING`：程序必须能算出一条可信来源，否则这不叫"仅有可信二手"。
- **投资栏目只校验事件类型、不校验主体** ——
  清单外的个股并购也能进（Round 2 实战评估实际抓到一次）。
  新增 `watchlist_subject`：投资条目必须声明对应清单里的哪一项，由程序对着 config 校验引用。
- **交叉验证的"独立发布者"实际按主机名去重** ——
  同一家媒体的两个子域（`finance.people.com.cn` / `society.people.com.cn`）会被误算成两家。
  改为按 `publisher` 计数。
- **本期内部去重把"来源更少"当成更好** ——
  同一事件同时有一手版和转载版时，会保转载、丢一手。排序键由 `len(srcs)` 改为 `-len(srcs)`。
- **同一个聚合页被多条内容当来源** —— 新增 `SOURCE_URL_REUSED` 警告（≥3 条）。
- **清单外域名拿不到"可信二手"资格** —— 新增与"第一方 + 理由"对称的补证通道：
  声明 `tier: trusted_secondary` 并写明 `tier_reason` 的清单外域名，可计入交叉验证（记 `SOURCE_TIER_JUSTIFIED` INFO）。
- `sources.yaml` 补齐三条被实战评估撞出来的主流媒体域名：`chinanews.com`（中新网移动端）、`gmw.cn`（光明网）、`cnr.cn`（央广网）。

### 版本级说明

- `schemas/candidate.schema.json` 中 `has_material_event` 与 `gates` 标记为 deprecated。
- 回归夹具随架构变化有若干处调整，全部按
  `OLD_EXPECTATION= / WHY_WRONG= / NEW_EXPECTATION=` 记录在 `docs/evaluation.md`，
  没有为了让测试变绿而偷偷改 expectation。

### 未修项（明确留到 v0.1.2）

1. **标题长度没有按微信阅读收紧。** 渲染器的 `TITLE_MAX_CHARS = 45` 是宽松硬上限；
   新加的可读性检查按 30 字判，9 期里 3 期超标（最长 36 字）。
   **没有为了让新写的检查变绿而调阈值**，保留 FAIL 记录在案。
2. **重要性判断仍是模型在做。** 本轮 5 条误收全部来自这一类。可归纳的两个模式
   （例行公事／照稿表态、同类尺度不一致）已写入 `references/reliability-gaps.md`，
   但没有可判定的实现方案。
3. **栏目归类仍是模型在做。** 程序只校验栏目在不在 priority 里。

### 本轮实际修掉的缺陷

不是设计出来的，是实战轮次撞出来的，共 6 处：

| # | 缺陷 | 撞出的轮次 | 修法 |
|---|---|---|---|
| 1 | 交叉验证的"独立发布者"实际按主机名去重 | round-01 | 改按 `publisher` 计数 |
| 2 | `sources.yaml` 未收录中新网／光明网，真实政策被误拦 | round-01 | 补三个域名 |
| 3 | 「仅有可信二手」只要写一句披露标记就放行 | round-02 | 新增 `SECONDARY_SOURCE_MISSING` |
| 4 | 投资栏目只校验事件类型、不校验主体 | round-02 | 新增 `watchlist_subject` 绑定校验 |
| 5 | 本期去重保转载、丢一手（排序键符号反了） | round-03 | `len(srcs)` → `-len(srcs)` |
| 6 | 同一聚合页被多条内容当来源 | round-03 | 新增 `SOURCE_URL_REUSED` |

另有 2 处是评测脚本自身的编排缺陷（逐条 BLOCK 拖住整期不渲染、DUPLICATE 被覆盖成 UNVERIFIED），
修在 `tests/run_eval_round.py` 的 `_render_blocking()` / `_resolve_blocked()`。

## [0.1.0] - 2026-10-04

### 第一版可运行规范

初始版本，主要解决六件事：

1. **信息筛选** —— 六栏优先级、各栏目的准入与过滤清单、数量不作硬性要求
2. **一手来源优先** —— 三层来源分级 + 「发布者是否即事件主体」的唯一判据
3. **时间窗口** —— 默认 24 小时，以及八种允许进入窗口的"实质新进展"
4. **跨日去重** —— 主体 + 核心动作 + 核心事件构成 fingerprint，两级去重
5. **证据状态** —— 五档 evidence_status，决定能否输出与是否需要披露标记
6. **微信阅读格式** —— 无表格、来源行规范、无内容栏目不出现

不做的事：数据库、Docker、Redis、向量库、Web 后台、外部依赖。

#### 新增

- `SKILL.md` —— 模型运行时主指令（3513 字符）
- `README.md` —— 11 节完整说明
- `config/watchlist.yaml` —— 关注清单（含主体别名表）
- `config/sources.yaml` —— 来源三层分级 + 永不可作来源清单
- `prompts/research.md` / `verify.md` / `render.md`
- `references/evidence-status.md` / `dedup.md` / `reliability-gaps.md`
- `schemas/candidate.schema.json` / `history.schema.json`
- `scripts/zaobao_check.py` —— 确定性规则层，零依赖，83 个规则 code
- `scripts/zaobao_render.py` —— 渲染器，渲染前后双重自检
- `tests/cases/*.json` —— 14 个用例 / 67 个断言步骤
- `tests/run_regression.py` / `run_cli_smoke.py` / `mutate.py`
- `tests/test-cases.md` / `regression-checklist.md`
- `examples/` —— 正面样例、空期次样例、反面样例
- `docs/design-notes.md`

#### 验证

```text
REGRESSION_STATUS=PASS     14 用例 / 67 步
CLI_SMOKE_STATUS=PASS      19 项
MUTATION_STATUS=PASS       16/16 变异被捕获
```

#### 设计裁决

- **`UPDATED` 可输出。** 原始规范第十二节"只有 PASS 可以进入最终输出"与
  Case 4"UPDATED，可以输出新进展"冲突；本版本按 Case 4 处理，
  把 `PASS` 与 `UPDATED` 都定义为可输出终态。见 `docs/design-notes.md` 第二节。
- **缺陷分两类。** 结构性缺陷任何时候 BLOCK；证据充分性缺陷仅在条目真的进入
  输出时 BLOCK，否则降为 INFO，避免被丢弃的候选淹没报告。

#### 已知限制

见 `README.md` 第 11 节与 `references/reliability-gaps.md`。
其中「测试覆盖率」为：83 个规则 code 中 54 个被夹具正面断言，其余部分由 CLI
冒烟覆盖，部分属于需要构造非法输入的畸形分支，当前未覆盖。
