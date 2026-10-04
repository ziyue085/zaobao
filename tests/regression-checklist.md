# 回归清单

分四段：**自动**（脚本跑）、**变异**（证明脚本不是空转）、**可读性**（排版与阅读体验）、**人工**（脚本测不到的部分）。

---

## 第一段：自动回归

```bash
python tests/run_regression.py
python tests/run_cli_smoke.py
```

期望：

```text
REGRESSION_STATUS=PASS      （15 用例 / 85 步，全绿）
CLI_SMOKE_STATUS=PASS       （29 项，全绿）
```

任一 FAIL：**不要提交，也不要发情报**。先定位是哪条规则被改坏了。

---

## 第二段：变异测试

```bash
python tests/mutate.py
```

期望：`MUTATION_STATUS=PASS (25/25)`。

一次全绿不算证据。必须证明"把规则破坏掉，测试会转红"。

| 变异 | 破坏什么 | 期望转红的步骤 | 匹配方式 |
|---|---|---|---|
| M01 | `material_update` 缺失不再阻断 | case-09 step3 | 精确 |
| M01b | `material_update` 不再能支撑 UPDATED | case-15 step5 | 精确 |
| M02 | 时间窗外不再阻断 | case-03 step1/3、case-04 step3、case-15 step1 | 精确 |
| M03 | 跨日去重失效 | case-08 step1—4、case-15 step5 | 精确 |
| M04 | 本期内部去重失效 | case-02 step1/2、case-15 step4 | 精确 |
| M05 | 候选层标题党检查关闭 | case-12 step1 | 精确 |
| M05b | 渲染层标题党检查关闭 | case-12 step7 | 精确 |
| M06 | 表格检查关闭 | case-12 step5 | 精确 |
| M07 | 二手来源披露要求取消 | case-05 step1 | 精确 |
| M08 | 主体别名归并关闭 | case-02 step1/2、case-08 step4 | 精确 |
| M09 | 检查无条件触发（**过度拦截**） | case-11 step1、case-12 step6 | 子集 |
| M10 | 「意外但重要」每日上限取消 | case-10 step2 | 精确 |
| M11 | Top 条数上限取消 | case-07 step4 | 精确 |
| M12 | 搜索引擎 URL 当作来源 | case-12 step3、case-15 step2/7 | 精确 |
| M13 | 影响分析与预测检查关闭 | case-12 step1/2 | 精确 |
| M14 | 投资建议检查关闭 | case-12 step8 | 精确 |
| M15 | 来源分类器一手判定失效 | case-09 step4、case-11 step1、case-15 step3 | 子集 |
| M16 | 自报字段缺席重新变成失败 | case-09 step5、case-11 step1、case-12 step6、case-15 step3/16 | 精确 |
| M17 | `material_update` 未自证不再报错 | case-15 step6 | 精确 |
| M18 | 渲染来源优先级失效（改用列表首个来源） | case-15 step8 | 精确 |
| M19 | 结构门时间字段缺失不再报错 | case-13 step5 | 精确 |
| M20 | 独立发布者退回按主机名去重 | case-15 step12 | 子集 |
| M21 | 清单外域名不再能凭理由计入可信二手 | case-15 step10 | 子集 |
| M22 | 「仅有可信二手」不再校验可信来源 | case-15 step14 | 子集 |
| M23 | 同一个来源 URL 被多条内容反复引用不再提示 | case-15 step15 | 子集 |

匹配方式有两种：

- **精确匹配**：转红集合必须完全等于期望集合，多一步少一步都算失败。
- **子集匹配**：只要期望集合内的步骤都转红了就算通过。用于两类变异 ——
  一类刻意做宽（M09 让每个候选都多出一条 BLOCK，必然大面积转红，逐条枚举没有额外信息量），
  一类影响面天然很大（M15/M20/M21/M22/M23 触及所有候选的来源判定）。

### 看到 `NOT_CAUGHT` 时的顺序

先怀疑**期望清单写错了**，再怀疑测试。

本项目就踩过这个坑：最初 M01 期望 `case-09 step3` 转红，但 `case-09 step3` 断言的是
栏目字段层的 `GATE_FIELD_UNCHECKED`，而 M01 改的是闸门字典层 —— 变异打在了一个
测试没有覆盖的位置。这不是"测试没用"，是**测试有缺口**。修法是补夹具（`case-09 step5`），
再把变异拆成 M01 / M01b 两条。

v0.1.1 又踩了同一类坑两次：M07 的目标片段因合并条件行改动而 SKIP（变异根本没生效，
却因为"没转红"被报成失败）；M16 在新增 `case-15 step16` 之后期望集合没跟上，
报 `NOT_CAUGHT`。两次的教训一样：**改夹具之后要同步改变异的期望集合。**

---

## 第三段：可读性检查（微信版排版）

```bash
python tests/check_output_readability.py
```

期望：`TERMINAL_STATUS=PASS`。

它检查六件事：标题 ≤ 30 字、每段 ≤ 3 句、单段 ≤ 180 字、无 Markdown 表格、
来源链接必须是 http(s) 绝对地址、整期阅读时长 ≤ 5 分钟。

**注意**：当前 9 期里有 3 期标题超标（最长 36 字），所以这条现在会返回 FAIL。
这是**已知的、记录在案的**待办（收紧渲染器的 `TITLE_MAX_CHARS`，属 v0.1.2），
不是回归 —— 判断方式是看 FAIL 的条目是不是那 3 条已知的。
**不要为了让这条变绿而放宽阈值。**

---

## 第四段：人工回归（脚本测不到）

以下行为不可判定，必须由人过一遍。每次改动 `SKILL.md`、`prompts/` 或词表后执行。

### 1. 语气与可读性

- [ ] 通读一遍最终输出，像不像"有人在微信里发给你的一段话"？
- [ ] 有没有为了显得专业而堆砌术语？
- [ ] 每条 1—3 句，有没有哪条读起来喘不上气？

### 2. 事实层抽查

- [ ] 随机挑 2 条，回原始 URL 核对：标题说的是不是原文说的？
- [ ] 有没有把"报道称"写成"某某宣布"？
- [ ] 时间对不对：是事件发生时间，还是报道时间？

### 3. 判断层

- [ ] 有没有哪条其实是"值得知道"但不够"值得发"？该删。
- [ ] Top 段那几条，是不是真的比其余条目更重要？
- [ ] 「意外但重要」有没有凑数感？

### 4. 词表维护

- [ ] 今天有没有出现新的标题党词或"分析味"表述，但没被拦？
- [ ] 有的话，补进 `scripts/zaobao_check.py` 顶部的 `CLICKBAIT_WORDS` / `ANALYSIS_WORDS` / `ADVICE_WORDS`。
- [ ] 补完重跑第一段与第二段。

### 5. 来源清单维护

- [ ] 有没有遇到新的官方来源域名？补进 `config/sources.yaml` 的 `primary`。
- [ ] 有没有遇到新的可靠媒体？补进 `trusted_secondary`。
- [ ] 有没有发现某个域名被错误分层？改掉，并重跑 `check-config`。

### 6. 关注清单维护

- [ ] `config/watchlist.yaml` 里的 `investment.assets` 还是当前关心的吗？
- [ ] 新出现的主体别名（新的简称、英文名、全称）有没有补进 `aliases`？
  **没补就会导致跨日去重失效。**

---

## 提交前 Checklist

```text
[ ] python tests/run_regression.py    → REGRESSION_STATUS=PASS
[ ] python tests/run_cli_smoke.py     → CLI_SMOKE_STATUS=PASS
[ ] python tests/mutate.py            → MUTATION_STATUS=PASS
[ ] python tests/check_output_readability.py  → 只允许已知的 3 条标题超长
[ ] python scripts/zaobao_check.py check-config --repo .   → 无 BLOCK、无 WARN
[ ] 人工回归四段（语气 / 事实 / 判断 / 词表来源维护）过一遍
[ ] SKILL.md 字符数 < 6000
[ ] git status 干净（data/history.jsonl 不应出现在待提交列表里）
```

> `tests/evals/*/history.jsonl` **应当**提交 —— 它们是跨日去重测试的合成夹具，
> 不是个人运行时历史（个人历史在 `data/history.jsonl`，已被 `.gitignore` 排除）。
