# 变更记录

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
