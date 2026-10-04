# 早间情报 · morning-intelligence

一个用来生成**中文个人早间情报**的技能：每天回答一个问题 ——
**过去 24 小时，我关注的领域发生了什么？**

产出是一份能在微信里几分钟读完的短文，只包含已经核实的新事实。

- 版本：**v0.1.1**
- 许可：MIT
- 依赖：**零**（Python 3.8+ 标准库即可运行；装了 PyYAML 会用，不装也能跑）

[![CI](https://github.com/ziyue085/zaobao/actions/workflows/ci.yml/badge.svg)](https://github.com/ziyue085/zaobao/actions/workflows/ci.yml)

---

## 1. 这是什么

一份**规则化的写作规范 + 一套确定性检查器**。

规范部分（`SKILL.md` + `prompts/` + `references/`）告诉模型怎么筛选、核验、写作。
检查器部分（`scripts/`）负责在模型出错时拦住它：

```bash
python scripts/zaobao_check.py check-issue issue.json --repo .
```

检查器只做**可判定**的事：字段是否缺失、时间是否落在窗口内、是否与历史重复、
枚举是否合法、计数是否越界、有没有出现标题党词或投资建议。
它不判断"这条新闻重不重要" —— 那是模型的活。

渲染器自带前后双重闸门，出现 `BLOCK` 会直接拒绝输出。

## 2. 适用场景

- 想每天读一份**不掺水**的领域速览，而不是刷无穷无尽的信息流
- 关注的领域相对固定（政策 / 投资 / AI / 社会 / 人物思想），但不想漏掉真正重要的事
- 讨厌"重磅""炸裂""值得关注""利好"这类词
- 希望**少发**而不是硬凑：只有 1 条就发 1 条，没有就发一句说明

不适用：需要实时行情、需要长文分析、需要投资决策支持。

## 3. 核心原则

**新、真、重要、简洁。**

v0.1.1 之上还有一条更根本的原则，其他规则都要服从它：

> **能由程序根据原始字段计算的判断，不允许继续依赖模型自报。**

所以候选里保存的是「可审计的事实」（发布时间、来源 URL、实质新进展的事实块、主体引用了关注清单的哪一项），
能不能放行由程序算：时效、一手来源、交叉验证、跨日去重、主体是否在清单内。
模型只负责两件程序做不了的事 —— **判断重要性**（要留下理由）与**归类**。

禁止：投资建议、股价预测、影响分析、政策推演、行动建议、为凑数加入低价值信息、
把"没搜索到"写成"没有新闻"、把传闻写成事实、把旧闻重新包装成新闻。

信息少时就少写。**信息少不是问题，掺水才是。**

输出优先级：普适性政策 → 投资 → AI → 社会热点 → 人物与思想信号 → 意外但重要。
无内容的栏目**整段不出现**。

## 4. 项目目录

```text
morning-intelligence/
├── SKILL.md                     模型运行时的主指令（< 6000 字符）
├── README.md                    本文件
├── CHANGELOG.md
├── LICENSE                      MIT
├── .gitignore / .gitattributes
├── .github/workflows/ci.yml     CI：push / PR 到 main 时跑五层检查
├── config/
│   ├── watchlist.yaml           关注什么（日常唯一需要改的文件）
│   └── sources.yaml             来源优先级
├── prompts/
│   ├── research.md              怎么发现候选
│   ├── verify.md                怎么核验与判证据状态
│   └── render.md                怎么渲染成微信可读正文
├── schemas/
│   ├── candidate.schema.json    候选条目契约
│   └── history.schema.json      历史记录契约
├── references/
│   ├── evidence-status.md       evidence_status 详解
│   ├── dedup.md                 去重与 fingerprint
│   └── reliability-gaps.md      已知断点与薄弱点
├── scripts/
│   ├── zaobao_check.py          确定性规则层 + 七个 Gate（零依赖）
│   ├── zaobao_classify.py       来源分类器（正向证据优先，9 个类别）
│   └── zaobao_render.py         渲染器（带自检闸门）
├── tests/
│   ├── cases/*.json             15 个用例 / 85 个断言步骤
│   ├── run_regression.py        回归运行器
│   ├── run_cli_smoke.py         命令行端到端冒烟（29 项）
│   ├── mutate.py                变异测试（25 处破坏）
│   ├── check_output_readability.py  输出可读性检查（标题长度 / 句数 / 表格 / 链接 / 时长）
│   ├── run_eval_round.py        实战评估：把一轮真实候选走完整条流程并落盘
│   ├── run_eval_summary.py      把逐条人工标签汇总成记分卡
│   ├── compare_rounds.py        比对同窗口两轮检索的差异
│   ├── evals/                   实战评估材料（候选 / 审计 / 输出 / 人工标签）
│   ├── test-cases.md            用例说明与覆盖矩阵
│   └── regression-checklist.md  三段式回归清单
├── examples/                    合成示例（含反面样例）
├── docs/design-notes.md         取舍、阈值依据、已知限制
├── docs/evaluation.md           实战评估方法、指标、各轮结果与已知限制
└── data/                        运行时数据目录（.gitkeep 占位）
```

**相对建议结构的调整与原因**：

| 调整 | 原因 |
|---|---|
| 增加 `scripts/`、`references/`、`docs/`、`CHANGELOG.md` | 把"可判定的规则"从提示词里拎出来变成代码；把方法论按需加载，避免主文件膨胀 |
| 增加 `tests/cases/*.json` 与 `mutate.py` | `test-cases.md` 只是说明，不能执行；需要一个能断言的数据夹具层，以及证明测试非空转的变异层 |
| 增加 `tests/run_cli_smoke.py` | 回归测试跑的是函数，不能证明命令行入口可用 |
| `examples/` 增加 `sample-output-bad.md` 与 `README.md` | 只有正面样例不足以说明"什么会被拦下" |
| 保留 `data/.gitkeep`，但 `.gitignore` 排除 `data/*.jsonl` | 历史记录是个人运行数据，必须本地持久化，但不应上传 |
| 增加 `.github/workflows/ci.yml` | 五层测试需要有人替我们每次跑；CI 与本地命令完全一致，不另立一套 |

## 5. 安装与使用

### 方式一：一句话安装（推荐）

把下面这句发给任意能读写文件的 AI 助手：

```text
请把 https://github.com/ziyue085/zaobao 安装成我的技能：
克隆到你的技能目录（例如 ~/.workbuddy/skills/ 或 ~/.claude/skills/），
目录名用 morning-intelligence；装好后确认 SKILL.md 存在，
然后告诉我这个技能在什么情况下会被触发。
```

装完后目录结构大致是：

```text
~/.workbuddy/skills/morning-intelligence/
├── SKILL.md
├── config/ prompts/ references/ scripts/ ...
```

### 方式二：手动克隆（兜底）

```bash
git clone https://github.com/ziyue085/zaobao.git morning-intelligence
```

然后把这个目录放到你的技能目录下。

### 方式三：纯对话型 AI（不能执行命令）

让它直接读取 `SKILL.md`，再把 `prompts/` 与 `references/` 里的文件按需提供给它。
最小可用集合是 `SKILL.md` + `config/watchlist.yaml`。

> **先改 `config/watchlist.yaml` 再跑。** 仓库里这份默认值是**作者本人的关注项**
> （投资栏目尤其如此）。关注项决定哪些主体能进候选、投资条目能否通过主体绑定校验，
> 所以装好后建议先按自己的关注范围改一遍 —— 只改这个文件，不用动代码。

### 日常使用

```bash
# 1. 让模型按 SKILL.md 的流程产出候选，写成 issue.json
#    结构见 schemas/candidate.schema.json 与 examples/sample-input.md

# 2. 跑闸门（有 BLOCK 就不发）
python scripts/zaobao_check.py check-issue issue.json --repo .

# 3. 渲染（自带前后双重自检，有 BLOCK 会拒绝输出）
python scripts/zaobao_render.py issue.json --repo . --out output.md

# 4. 把本期已输出的事件写入历史（跨日去重靠它）
python scripts/zaobao_check.py record issue.json --history data/history.jsonl
#    确认无误后加 --write 真正落盘

# 5. 每月裁剪一次历史
python scripts/zaobao_check.py prune --history data/history.jsonl --days 30 --write
```

其他命令：

```bash
python scripts/zaobao_check.py check-config --repo .          # 配置体检
python scripts/zaobao_check.py check-candidate c.json         # 单条候选
python scripts/zaobao_check.py check-render out.md --issue issue.json
python scripts/zaobao_check.py fingerprint --entity 中芯国际 --action 发布 \
       --object 2026年三季度报告
```

测试：

```bash
python tests/run_regression.py    # 期望 REGRESSION_STATUS=PASS
python tests/run_cli_smoke.py     # 期望 CLI_SMOKE_STATUS=PASS
python tests/mutate.py            # 期望 MUTATION_STATUS=PASS
python tests/check_output_readability.py   # 期望 TERMINAL_STATUS=PASS
```

> 注意：`record` 与渲染器写的路径是相对的，建议固定在同一台机器上运行，
> 并定期把 `data/history.jsonl` 备份走。

## 6. 如何修改关注列表

**只改 `config/watchlist.yaml`，不要动代码。**

### 加一个固定关注的公司

```yaml
sections:
  investment:
    assets:
      - 中芯国际
      - 纳斯达克100
      - 中国石化
      - 猪周期
      - 恒顺醋业
      - 中公教育
      - 新加的公司        # ← 加这里
```

### 给主体加别名（重要）

同一家公司被写成全称、简称、英文名时，如果不归并，跨日去重会失效：

```yaml
aliases:
  中芯国际:
    - SMIC
    - 中芯国际集成电路制造有限公司
  新加的公司:
    - 新公司的全称
    - 英文名
```

**新加关注对象时，顺手把别名也加上。**

### 调整栏目顺序

```yaml
priority:
  - universal_policy
  - investment
  - ai
  - social
  - people_ideas
  - unexpected
```

顺序即输出顺序。**没有内容的栏目不会出现**，所以列表长短不影响可读性。

### 改完检查

```bash
python scripts/zaobao_check.py check-config --repo .
```

会检查栏目定义是否完整、来源层级是否冲突、别名是否为空等。

## 7. 如何修改来源

改 `config/sources.yaml`，三层结构：

```yaml
primary:              # 一手：政府官网、监管机构、交易所、公司公告与官网、
  domains: [...]      #       官方博客/新闻稿/GitHub、正式论文、作者原文
trusted_secondary:    # 二手：高质量新闻媒体。只用于发现线索、交叉核验、补背景
  domains: [...]
  quasi_primary: [...]  # 中央文件通稿的实际首发渠道（新华社/央视/人民日报）
discovery_only:       # 社交平台。只用于发现线索
  domains: [...]
never_a_source:       # 搜索引擎结果页与内容农场：永不作为来源
  - baidu.com/s
  - google.com/search
```

三条使用须知：

1. **这份清单不可能覆盖全部新闻。** 遇到清单外的域名，按定义自行判级，
   并把判断写进候选的 `sources[].tier_reason`。若声明 `tier: primary` 但域名不在
   清单里，必须同时填 `is_first_party: true` 与 `tier_reason`，否则规则层直接 BLOCK。
2. **`primary` 里放了 `gov.cn` 这类父域**，它的子域（如 `mem.gov.cn`）会一并命中。
   这是有意的简化，也意味着不要把宽泛的父域放进 `discovery_only`。
3. 同一域名出现在多个层级会触发 `CONFIG_SOURCE_TIER_OVERLAP`（WARN）。

`tool_priority` 段是给模型看的执行顺序：能用专项工具拿到的，不要用搜索摘要替代。

## 8. 去重如何工作

### fingerprint

```
fingerprint = 归一化(主体) # 归一化(核心动作) # 归一化(核心事件)
例：中芯国际#发布#2026年三季度报告
```

**刻意不含标题。** 因为标题是媒体加工的产物：

```text
10-01  中芯国际发布2026年三季度报告
10-02  中芯国际三季报出炉，营收同比增长12%
10-03  SMIC 三季度业绩披露
```

按标题判重会得到三件事；按 fingerprint 判重只有一件。

### 两级去重

1. **本期内部**：同一 fingerprint 出现多次 → 只保留来源最好的一条
   （`primary` < `trusted_secondary` < `discovery_only`，同层级时第一方优先）。
   这就是「新华社、财联社、公司官网都报了，只发一次，优先公司官网」的实现。
2. **跨日**：对照 `data/history.jsonl`，回看至少 7 天（默认 30 天）。
   同一 fingerprint 且**没有实质新进展** → `DUPLICATE`，不输出。

**实质新进展**只认：官方确认、新公告、正式文件、新数据、处罚判决、调查结果、
产品正式上线、传闻被证实或证伪。转载、重新讨论、热度回升都不算。

有新进展时状态为 `UPDATED`，允许再次输出。

细节见 `references/dedup.md`。

## 9. evidence_status 如何工作

每条候选必须有一个证据状态，它同时决定三件事：**能不能发、要不要加标注、能不能进特定栏目**。

| 状态 | 含义 | 能否输出 | 必须披露 |
|---|---|---|---|
| `VERIFIED_PRIMARY` | 找到一手来源 | 可以 | 否 |
| `VERIFIED_CROSS_SOURCE` | 无一手，但两家以上独立可信来源互证 | 可以 | 否 |
| `SECONDARY_ONLY` | 只有可信二手报道 | 重要时可以 | **尚未见一手确认** |
| `UNVERIFIED` | 来源不足 | 仅限「意外但重要」 | **待核实** |
| `REJECTED` | 证据不可用 | 不可以 | — |

判"一手"的唯一标准：**发布者是不是这件事的主体本身。**

- 公司自己发的公告 → 一手
- 记者报道这家公司的公告 → 二手（哪怕记者来自官方媒体）
- 论文作者自己贴的预印本 → 一手
- 别人转述这篇论文 → 二手

社交平台只用于发现线索，**唯一例外**是发帖者本身就是当事人／官方账号／负责人／论文作者 ——
这时会升级为一手，但规则层会保留一条 WARN 提醒复查。

系统会拦下这些情况：声称一手却没有一手来源、声称多源互证却只有一家、
二手报道没写披露标记、只有社交平台作来源、把搜索引擎结果页写成来源。

细节见 `references/evidence-status.md`。

## 10. 示例输出

`examples/sample-output.md`（由 `scripts/zaobao_render.py` 真实生成）：

```markdown
# 早间情报 · 2026-10-04

统计窗口：2026-10-03 09:00 → 2026-10-04 09:00（北京时间）

## 今天最值得看的2件事

- OpenAI 发布支持视频输入的多模态模型。
- 应急管理部通报某地事故救援进展。

## AI

**OpenAI 发布支持视频输入的多模态模型**

OpenAI 今日在其官网发布支持视频输入的多模态模型。官方文档列出两种输入规格。

来源：[OpenAI](https://openai.com/index/video-input-model/)

## 社会热点

**应急管理部通报某地事故救援进展**

应急管理部今日通报某地事故救援进展。通报称现场救援仍在进行。

来源：[应急管理部](https://www.mem.gov.cn/xw/yjglbgzdt/20261004.shtml)

## 人物与思想信号

**研究团队发布论文提出推理模型评测新方法**

该团队在预印本论文中提出一种推理模型评测方法。论文给出该方法在两个公开数据集上的对照结果。

来源：[arXiv](https://arxiv.org/abs/2610.05678)
```

**注意**：示例中的 URL 与机构名是**合成测试数据**，不是真实新闻。

同一目录下还有：

- `sample-output-empty.md` —— 无合格条目时的输出（只有一句标准说明）
- `sample-output-bad.md` —— 反面样例，踩了表格、投资建议、影响分析、标题党、
  Top 段声明 3 条实际 2 条、引用搜索引擎页等错误，被规则层判出 14 个 BLOCK + 5 个 WARN

## 11. 已知限制

### 规则层能做到什么、不能做到什么

**能**：字段缺失（含三态缺席）、时间窗、去重、枚举合法性、计数越界、字面违规。

**不能**：判断重要性、判断标题是否真的陈述了事实、判断来源是否真的可靠、
判断摘要是否忠实转述、判断一条信息是否构成"实质新进展"（只能按枚举近似）。

**结论：规则层是网，不是墙。** 它保证"明显错误不发出去"，不保证"发出去的都是对的"。

### 最要紧的三条

1. **重要性与栏目归类仍完全依赖模型。** v0.1.1 已经把时效、证据、去重、主体范围
   全部改成程序计算（见 `docs/evaluation.md`），但"这件事值不值得占版面""该放哪个栏目"
   仍然只能由模型判断 —— 系统能做的是要求它留下 `importance_reason`，并在审计里把主体与原栏目标出来
   供人工复核。实测里这一类误收的典型是：`应急管理部视频调度`（假期例行调度）、
   `科技部介绍十五五安排`（发布会表态）、`八部门指导意见`（纲领性文件，无量化口径）——
   共同点是**叙了事、讲的话也对，但没有改变规则或资源分配**。
2. **词表是穷举式的。** 新出现的标题党词、新的"分析味"表述不会自动被拦。
   需要每周人工回看并补充 `scripts/zaobao_check.py` 顶部的词表并重跑测试。
3. **规则层校验不了"标题是否被这条 URL 支持"。** 它能校验 URL 是否可引用、
   是否落在可信清单里，但校验不了一条标题是不是超出了来源能支持的范围 ——
   它不看来源页的内容。标题与来源是否一致，目前只能靠人工复核
   （见 `tests/regression-checklist.md` 第四段）。

### 测试覆盖面

- 回归测试：15 用例 / 85 步骤，全绿；变异测试 25/25 捕获；CLI 冒烟 29/29；可读性检查 9 期 9 通过。
- 规则层共 80+ 个 code，夹具中被**正面断言**的有 60 余个。其余由 CLI 冒烟覆盖（`HISTORY_*` / `CONFIG_*`）
  或属于需要构造非法输入的畸形分支。详见 `tests/test-cases.md` 第五节的覆盖矩阵。
- 夹具是**合成数据**，证明的是规则逻辑。**「真实网络环境下到底行不行」由实战评估层回答** ——
  见 `docs/evaluation.md`：6 轮真实窗口 + 1 组三段跨日链路，23 条产出，GOOD_RATE 0.78。
- 实战评估里的「漏收重要事件」目前只能人工发现，`tests/evals/*/labels.json` 的
  `missed_important` 字段就是留给它的位置。

### 规则层对原始规范做了一处实质性放宽

规范第十二节说"只有 PASS 可以进入最终输出"，但 Case 4 要求 `UPDATED` 可以输出。
本项目把 `PASS` 与 `UPDATED` 都当作可输出终态。裁决理由见 `docs/design-notes.md` 第二节。

### 其他

- 历史状态是本地文件（`data/history.jsonl`），换机器需要手动迁移。
- 内置的 YAML 子集解析器不支持锚点、多行标量（`|` / `>`）、多文档。
  要用这些特性请安装 PyYAML（正确性由 `run_cli_smoke.py` 的等价性断言保证）。
- 跨语言转述无法核对：英文来源翻成中文时若出现翻译偏差，规则层看不出来。

---

## 更多文档

| 想看什么 | 去哪 |
|---|---|
| 模型运行时怎么执行 | [SKILL.md](SKILL.md) |
| 为什么这么设计、阈值依据 | [docs/design-notes.md](docs/design-notes.md) |
| 怎么加规则、怎么加测试 | [docs/design-notes.md](docs/design-notes.md) 第十节 |
| 实战效果到底怎么样、怎么复现 | [docs/evaluation.md](docs/evaluation.md) |
| 已知断点的完整清单 | [references/reliability-gaps.md](references/reliability-gaps.md) |
| 改完要怎么验证 | [tests/regression-checklist.md](tests/regression-checklist.md) |

## 许可

MIT，见 `LICENSE`。
