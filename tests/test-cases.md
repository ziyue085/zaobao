# 测试用例说明

## 一、怎么跑

```bash
python tests/run_regression.py            # 断言全部用例
python tests/run_regression.py --list     # 列出用例与步数
python tests/run_regression.py --json     # 机器可读结果
python tests/run_regression.py --only case-03

python tests/mutate.py                    # 变异测试（证明测试不是空转）
python tests/run_cli_smoke.py             # 命令行端到端冒烟
```

断言全部按**规则 code** 进行，不按提示文字。code 定义见 `scripts/zaobao_check.py`。

## 二、断言字段

| 字段 | 含义 |
|---|---|
| `block_count` / `warn_count` / `info_count` | 该严重度的发现条数（**精确相等**） |
| `block_codes` / `warn_codes` / `any_codes` | 必须出现的 code（子集断言） |
| `absent_codes` / `block_codes_absent` | 必须不出现的 code |
| `absent_all_known_codes` | 规则层 + 渲染层的 83 个已知 code 一个都不许出现（反向对照专用） |
| `severity` | `{code: "BLOCK"/"WARN"/"INFO"}`，校验严重度而不只是存在性 |
| `stats` | 检查器返回的统计量（`pass` / `candidates` / `kept` / `dropped` / `top_pick`） |
| `fingerprint_same` | `[[idA,idB],...]` 断言两条候选的 fingerprint 相同 |
| `fingerprint_equals` | `{id: "期望值"}` |
| `kept_id` | 本期内部去重后应当保留的 id |
| `render_*` | 渲染层断言（`render_block_count` / `render_codes` / `render_contains` / `render_excludes`） |
| `render_text` | 直接给一段手写文本跑 `check-render`，不走渲染器 |
| `expand` | `[{template, count, id_prefix}]` 批量复制候选，用于测试数量类规则 |

## 三、用例对照表

| 用例 | 步数 | 对应 | 覆盖的规则 |
|---|---|---|---|
| `case-01` | 4 | 用户 Case 1 | 信息少时允许 0 条；凑数只给 WARN；空期次合法；**不得写「没有新闻」** |
| `case-02` | 2 | 用户 Case 2 | 本期内部去重；主体别名归并（全称／简称／英文名）；优先一手来源 |
| `case-03` | 3 | 用户 Case 3 | 超窗即 OLD；只有 `new_progress_at` 不足以升级 |
| `case-04` | 3 | 用户 Case 4 | 旧事件＋实质新进展 → UPDATED 可输出；`new_progress_type` 缺失不得升级 |
| `case-05` | 5 | 用户 Case 5 | SECONDARY_ONLY 必须披露；多源互证升级；UNVERIFIED 仅限「意外但重要」 |
| `case-06` | 3 | 用户 Case 6 | 只有传闻 → REJECT；当事人确认后可进社会热点（保留 1 条 WARN 留痕） |
| `case-07` | 4 | 用户 Case 7 | Top 按实际数量；**声明 3 条实际 2 条即 BLOCK**；非可输出状态不得进 Top |
| `case-08` | 4 | 用户 Case 8 | 跨日去重；有新进展才允许重发；换标题／换全称仍识别为同一事件 |
| `case-09` | 5 | 用户 Case 9 | 只有价格波动 → LOW_VALUE；`has_material_event` 缺席即 BLOCK；有实质事件正常输出 |
| `case-10` | 3 | 用户 Case 10 | 「意外但重要」可收录；每日上限 3 条；必须有高门槛类型声明 |
| `case-11` | 1 | **反向对照** | 完全合格的期次 → 0 BLOCK / 0 WARN / 0 INFO，且 83 个已知 code 一个都不触发 |
| `case-12` | 8 | 标题与来源要求 | 标题党、影响分析、投资建议、搜索 URL、禁用栏目、Markdown 表格、Top 一句话里的禁词 |
| `case-13` | 18 | 核验与证据规则 | 结构性缺陷（URL／来源／fingerprint／时间／枚举／计数／闸门）与证据充分性缺陷 |
| `case-14` | 4 | 输出结构 | 来源引用缺失、引用了清单外链接、空栏目、多余空行、Top 段缺失 |

合计 **14 个用例 / 67 个断言步骤**。

## 四、`case-12` 与 `case-13` 的分工

- `case-12` 测**字面层**：词表命中、禁用栏目、禁用格式。
- `case-13` 测**结构与证据层**：字段缺失、枚举非法、阈值越界、来源无法自证、闸门未通过。

两者都是"触发"型用例，重点是**该拦的必须拦住**。
`case-11` 是"不得过度触发"型用例，重点是**不该拦的绝不能拦**。

## 五、规则 code 覆盖矩阵

规则层现有 **83 个** code，夹具中被正面断言（必须出现）的有 **54 个**。

统计方式（可复现）：

```
KNOWN_CODES   = 扫描 scripts/zaobao_check.py 中所有 fnd("CODE" 的出现
ASSERTED      = 夹具 expect 中 block_codes ∪ warn_codes ∪ any_codes ∪ render_codes ∪ severity(非 null)
```

### 未被正面断言的 29 个

```text
CANDIDATE_NOT_OBJECT        CONFIG_ALIASES_EMPTY          CONFIG_BANNED_SECTION_IN_PRIORITY
CONFIG_HISTORY_RETENTION_SHORT  CONFIG_NEVER_SOURCE_EMPTY CONFIG_PRIORITY_MISSING
CONFIG_SECTION_UNDEFINED    CONFIG_SECTION_UNKNOWN        CONFIG_SOURCE_TIER_EMPTY
CONFIG_SOURCE_TIER_OVERLAP  CONFIG_UNEXPECTED_LIMIT_MISSING  CONFIG_UNEXPECTED_LIMIT_RAISED
CONFIG_USING_MINI_YAML      CONFIG_WINDOW_CHANGED         CROSS_SOURCE_HAS_PRIMARY
EMPTY_ISSUE                 EVIDENCE_STATUS_INVALID       HISTORY_LINE_INVALID
HISTORY_PRUNED              HISTORY_RECORDED              OUTPUT_ITEM_MISSING
PRIMARY_URL_NOT_IN_SOURCES  RENDER_NOT_TEXT               SECTION_HEADING_MISSING
SECTION_NOT_IN_PRIORITY     SOURCE_TIER_INVALID           TITLE_NOT_FACTUAL
TITLE_TOO_LONG              TITLE_TOO_SHORT
```

其中：

- `HISTORY_RECORDED` / `HISTORY_PRUNED` / `CONFIG_*` 由 `tests/run_cli_smoke.py` 在**命令行层面**覆盖（该脚本断言的是退出码与文件内容，不经过夹具断言机制）。
- `OUTPUT_ITEM_MISSING` / `SECTION_HEADING_MISSING` 在 `examples/sample-output-bad.md` 的实际判定中出现过，但未写成夹具断言。
- 其余属于"输入畸形"或"配置被改坏"分支，需要人为构造非法输入才能触发，当前未覆盖。

**这是已知的覆盖缺口，不是"全都测过了"。** 见 `references/reliability-gaps.md`。

## 六、已知的测试局限

1. 夹具用的是**合成数据**，URL 全部不存在。测试证明的是规则逻辑，不是"真实网络环境下能否跑通"。
2. 夹具里的 `now` 是硬编码的，所以时间相关断言是确定性的 —— 但也意味着**跨月／跨年／夏令时**这些边界没有被覆盖。
3. 没有对 `mini_yaml` 解析器做语法级的穷举测试，只做了"与 PyYAML 结果一致"的等价性测试（两个配置文件）。
4. 没有端到端测试"真的去联网抓一条新闻"这一步 —— 那部分不可判定，只能靠人工回归（见 `regression-checklist.md`）。
