# 已知断点与可靠性说明

规则写得再细，也会在两类地方失效。这两类断点比"规则本身写错了"更常见，也更难发现。

## 一、规则可测 ≠ 真实可靠

`tests/run_regression.py` 全绿，只证明**规则层正确**，不证明规则层接通了真实输入。

| 断点 | 症状 | 本项目的处理 |
|---|---|---|
| 自然语言 → 结构化状态 | 同一句话被抽成不同状态，规则层再对也没用 | 见下文第二节 |
| 评价单一 → 漏判 | 只检查了第一条，后面的问题被漏掉 | 逐候选遍历 + 逐 code 汇总（`check_candidate` 对每条候选跑全部检查） |

## 二、自然语言 → 状态：v0.1.1 改成「程序算，不问模型」

模型读一句新闻，要把它变成结构化的状态。这一步没有确定性保证。
v0.1.0 的应对方式是让模型自报 checklist（`gates.*_checked: true`），
字段缺席即 BLOCK —— 看起来很严，但**判定主体仍然是模型**：
它写 `time_window_checked: true`，程序就只能相信它。

### 1. v0.1.1 的做法：自报降级，派生由程序算

```
事实字段（模型填，可被程序核对）
  published_at / event_time / discovered_at
  material_update{claim, published_at, source_url}
  new_progress_at + new_progress_type
  sources[].url / tier / publisher / is_first_party / tier_reason
  watchlist_subject
```

程序据此推出派生状态（`derive()`）：

```
is_within_24h / is_future / has_primary_source / primary_source_count
verification_source_count / has_cross_source_verification
has_discovery_only_source / history_match / is_material_update
material_update_substantiated / is_output_eligible
```

**放行只看派生状态，不看模型怎么说。**

### 2. 自报字段怎么处理的

| 情况 | 处理 |
|---|---|
| `gates` / `has_material_event` 完全缺席 | `LEGACY_CHECKED_FIELDS_IGNORED`，INFO，不阻断 |
| 显式写了 `false` | `LEGACY_GATE_REPORTED_FALSE`，WARN，不阻断 |
| 用自报 `true` 想换放行 | **不做任何事** —— 放行由派生状态决定 |

两者在 schema 里都标了 `deprecated`。保留读取只为兼容旧数据，不再作为依据。

### 3. 三态仍然存在，但挪到了事实字段上

「未检查 ≠ 已通过」这条铁律没有取消，只是作用对象变了：

- `published_at` 缺席 → 时效无从计算 → 不能放行（不是"默认通过"）
- `material_update` 三字段缺一 → `material_update_substantiated = false` → 不能标 UPDATED
- `new_progress_at` 填了但没有 `new_progress_type` → 不允许升级为 `UPDATED`
  （只有"时间"没有"类型"，说明还没想清楚这算不算实质新进展）
- 投资条目没有 `watchlist_subject` → 主体准入无从校验 → 不能输出

测试用例 `case-03 step3`、`case-04 step3`、`case-15 step6` 盯的就是这几条。

### 4. 为什么这样更好

v0.1.0 的逻辑是「你说你查了，我就信」。v0.1.1 的逻辑是「你给出原始字段，我自己算」。
区别在于：前者模型可以什么都不查、只把 `checked` 全填 true 就通过；
后者模型必须真拿到 URL、真拿到发布时间，否则程序算不出放行所需的状态。

## 三、结构性缺陷 vs 证据充分性缺陷

这两类问题的严重度不同，混在一起处理会让报告变成噪声：

| 类型 | 例子 | 什么时候 BLOCK |
|---|---|---|
| **结构性缺陷** | URL 不合法、搜索引擎当来源、来源层级无法自证、栏目被排除、标题党、投资建议、影响分析、fingerprint 不完整、时间字段缺失 | **任何时候** |
| **证据充分性缺陷** | 来源不够两家互证、缺披露标记、primary_url 缺失、只有社交平台作来源、栏目准入门槛不满足 | **仅当该条真的进入输出时**；否则降为 INFO |

理由：一个已经被判为 `LOW_VALUE` 或 `DUPLICATE` 的候选，不需要再满足栏目准入条件。
否则一份 30 条的候选清单会产生上百条无关阻断，真正的问题被淹没。

实现见 `scripts/zaobao_check.py: _sev_for_status()`。

## 四、检查器能做什么、不能做什么

### 能做（可判定）

- 字段是否缺失（含三态缺席）
- 时间是否落在窗口内、是否有资格升级为 UPDATED
- fingerprint 是否与历史、与本期重复
- 枚举是否合法
- 计数是否越界（Top ≤ 3、「意外但重要」≤ 3、条目总数）
- 字面违规（标题党词表、建议／分析词表、表格、搜索 URL、"没有新闻"式表述）

### 不能做（不可判定）

- **这条新闻重不重要** —— 判断重要性仍是模型的工作，规则层只在明显越界时拦
- 标题是否"真的"直接表达了事实（只能查长度、问号、词表）
- 来源是否"真的"可靠（只能按域名清单与 `is_first_party` 判定）
- 摘要是否忠实地转述了原文
- 一条信息是否构成"实质新进展"（只能按 `new_progress_type` 枚举判定）

**结论**：规则层是网，不是墙。它保证"明显错误不发出去"，不保证"发出去的都是对的"。

## 五、已知的具体薄弱点

1. **词表是穷举式的。** 新出现的标题党词、新的"分析味道"表述不会自动被拦。词表需要定期补充（`scripts/zaobao_check.py` 顶部常量）。
2. **域名清单不可能完备。** `config/sources.yaml` 里没有的域名需要人工判级，并把判断写进 `tier_reason`。
   v0.1.1 为此加了两条对称的补证通道（`is_first_party + tier_reason` → 一手；
   `tier: trusted_secondary + tier_reason` → 可信二手），两条都要求留下理由并记 INFO。
3. **重要性判断是最大的残留依赖，也是误收的主要来源。** 23 条实战产出里 5 条误收，**全部**属于
   "事实没错但不该占版面"。可以归纳出两个稳定模式：
   - **例行公事 / 照稿表态**：假期安全调度、发布会介绍规划安排、领导署名文章。
     记叙体通稿天然长得像新闻，Gate 分不出"改了规则"和"表了个态"。
   - **同类尺度不一致**：发改委"推出系列举措"被收录，八部门"指导意见"被拒。
     判据接近，结论相反。
   程序能保证的是主体范围、时效、证据、去重 —— **保证不了"这件事值不值得占版面"。**
4. **栏目归类没有量化标准。** 程序只校验栏目在不在 priority 里，不判断归得对不对。
   v0.1.1 的 9 期实测里没有出现错栏，但样本量不足以说明这一类已经解决。
5. **标题是否被来源支持，校验不了。** 能校验 URL 可不可引用，校验不了这条标题有没有超出该 URL 的范围。
6. **微信排版尚未收紧。** `tests/check_output_readability.py` 按"标题 ≤ 30 字"检查，9 期里 3 期超标。
   渲染器的 `TITLE_MAX_CHARS = 45` 是宽松上限，没有针对微信阅读调过。属 v0.1.2 待办。
7. **跨语言转述无法核对。** 英文来源转成中文时，若出现翻译偏差，规则层看不出来。
8. **同一 app 内的历史状态只能靠本地文件。** 换机器需要手动迁移 `data/history.jsonl`。
9. **单一轮检索覆盖不全。** 同窗口换一批查询词重跑，两轮的重叠率可能只有 2/11（实测）。
   真实使用中必须承认这一点，不能把"这轮没搜到"当成"没有发生"。

## 六、定期体检清单

| 频率 | 动作 |
|---|---|
| 每次运行 | `zaobao_check.py check-issue` 无 BLOCK 才发 |
| 每次出稿 | `tests/check_output_readability.py` 通过（标题长度 / 句数 / 表格 / 链接） |
| 每周 | 人工回看已发内容，把新的误判词补进词表 |
| 每月 | 检查 `data/history.jsonl` 大小，跑一次 `prune` |
| 每次改规则 | 跑 `tests/run_regression.py` + `tests/mutate.py`，两者都 PASS 才算改完 |
| 每季度 | 重跑一组实战评估轮次（`tests/run_eval_round.py`），看误收/漏收有没有变化 |
