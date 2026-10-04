# 实战评估方法

这份文档回答一个问题：**怎么证明这份早报真的变好了？**

规则层的行覆盖率回答不了这个问题。83 个 rule code 全绿也不代表早报能读。
所以 v0.1.1 加了一层「实战评估」：拿真实时间窗口的真新闻，走完整条流程，
再把每一条产出逐条人工打标签，最后统计误收、漏收、旧闻、重复、来源可靠性。

---

## 1. 五层测试，各管一件事

| 层 | 命令 | 管什么 | 不通过意味着 |
|---|---|---|---|
| 回归 | `python tests/run_regression.py` | 每个 rule code 在给定输入下的行为 | 规则层坏了 |
| 冒烟 | `python tests/run_cli_smoke.py` | 命令行入口、退出码、文件读写 | 工具链坏了 |
| 变异 | `python tests/mutate.py` | 回归测试是不是空转（故意破坏规则，看会不会转红） | 测试没有证据力 |
| 可读性 | `python tests/check_output_readability.py` | 标题长度、句数、段落长度、表格、链接可点、阅读时长 | 内容对但读不下去 |
| 实战 | `python tests/run_eval_round.py <round>` | 真实窗口下整条链路的实际效果 | 早报本身不行 |

前四层是必要条件，第五层才是验收标准。**架构更漂亮但真实早报没有变好，不算 PASS。**

---

## 2. 窗口怎么定

- 默认窗口 = 当前时间向前 24 小时，时区 `+08:00`。
- 每轮评估都把 `now` 显式写进 `run-meta.json`，窗口起止同时落盘，事后可复核。
- 只掌握到「日期」精度的来源，`published_at` 按当日 `12:00` 记录，并在该轮 `candidates.json` 的 `note` 里说明。
- 判断只用截点当天可获得的信息，不用未来信息回头看「当时是否重要」。

---

## 3. 指标怎么算

逐条人工标签，词表固定：

`GOOD` / `SHOULD_NOT_INCLUDE` / `BAD_SOURCE` / `OLD` / `DUPLICATE` / `TOO_VERBOSE` / `WRONG_CATEGORY` / `UNVERIFIED`

汇总口径（`tests/run_eval_summary.py`）：

- `TOTAL_OUTPUT_ITEMS` —— 实际输出的条目总数
- `GOOD_ITEMS` —— 人工认为该收的条数
- `SHOULD_NOT_INCLUDE` —— 误收（事实没问题，但不该占版面）
- `BAD_SOURCE` —— 来源不成立却输出了
- `OLD_ITEMS` —— 旧闻被当新闻输出
- `DUPLICATE_ITEMS` —— 重复输出
- `WRONG_CATEGORY` —— 栏目归错
- `MISSED_IMPORTANT` —— 漏收的重要事件（逐轮单独列，并写明为什么漏）
- `GOOD_RATE = GOOD / TOTAL_OUTPUT_ITEMS`

**注意**：`MISSED_IMPORTANT` 不计入分母。漏收和误收是两类问题，混在一个比值里会互相掩盖。

---

## 4. 各轮结果

| 轮次 | 场景 | 输出 | GOOD | 误收 | 来源差 | 旧闻 | 重复 | 错栏 | 漏收重要 | GOOD_RATE |
|---|---|---|---|---|---|---|---|---|---|---|
| round-01 | 当前真实 24 小时 | 5 | 4 | 1 | 0 | 0 | 0 | 0 | 1 | 0.80 |
| round-02 | 同窗口独立重跑（换查询词） | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 1.00 |
| round-03 | 历史新闻密集日 2026-09-29/30 | 7 | 4 | 3 | 0 | 0 | 0 | 0 | 0 | 0.57 |
| round-04 | 历史低密度日 2026-10-02 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 |
| round-05 | 跨日去重 + UPDATED 同期并存 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.50 |
| round-05-day1 | 跨日链路第一步（首次出现） | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 |
| round-05-day2 | 跨日链路第二步（无新进展） | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| round-05-day3 | 跨日链路第三步（有实质新进展） | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 |
| round-06 | 来源压力测试 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 1.00 |
| **合计** | | **23** | **18** | **5** | **0** | **0** | **0** | **0** | **4** | **0.78** |

表中数字由 `python tests/run_eval_summary.py` 从各轮 `labels.json` 直接算出，不手工维护。
`round-05-day2` 输出 0 条是**正确结果**，不是漏收 —— 所以不做分母。

每轮的原始材料在 `tests/evals/<round>/`：

```text
candidates.json            检索产出的原始候选
candidates.resolved.json   走完 Gate 回路后的提交版本（改了什么一目了然）
audit.firstpass.json/.md   第一遍审计（含被拦下的原始形态）
audit.json / audit.md      提交版本的审计
accepted.json / rejected.json
output.md                  微信版正文
labels.json                逐条人工标签
run-meta.json              本轮统计
history.jsonl              跨日去重的输入历史（仅跨日轮次有）
```

---

## 5. 各轮的关键发现

### round-01（当前真实 24 小时）

- 5 条输出里 4 条站得住；`应急管理部视频调度` 属实但属假期例行调度，**误收 1 条**。
- 漏收 1 条：OpenAI 暂停最先进模型训练并取消 GPT-6.1 Astra 发布。
  **原因是检索覆盖不足** —— AI 线索只按「新模型发布」找，没覆盖「安全事件 / 人事变动」这条线。
  这是检索环节的漏，不是 Gate 的漏。
- 这一轮首跑还暴露了两个缺陷，已就地修掉：
  1. 交叉验证的「独立发布者」实际按主机名去重（`derive()` 把分类结论 dict 当成来源 dict 传给了 `publisher_key`）；
  2. `sources.yaml` 未收录 `chinanews.com` / `gmw.cn`，导致一条真实的国铁政策被误拦。

### round-02（同窗口独立重跑）

- **同一事件重叠只有 2 条，第二轮新增 6 条，第一轮有 9 条没再出现，裁决零变化。**
- 结论：规则层是稳定的，不稳定的是候选池。换一批查询词，`流花油田 200 万吨` 和 `Kolibri-1` 这种
  被评为 GOOD 的条目会整条消失。**这也是为什么「一轮检索 + 直接写稿」不可靠。**
- 本轮抓到一次真实误收：清单外个股（峰岹科技）的并购被放行 —— 投资栏目只校验事件类型、从不校验主体。
  已修：新增 `watchlist_subject` 绑定校验。
- 本轮还抓到：「仅有可信二手」原先只要写一句披露标记就能放行。已修：新增 `SECONDARY_SOURCE_MISSING`。

### round-03（历史新闻密集日）

- 候选 12 条 → 收录 7 条 → 输出 7 条。**没有失控，也没有触发 12 条上限。**
  密集日的正确行为不是把 13 件事都塞进去，而是照样逐条筛。
- 但人工复核发现，密度日的短板不是数量而是**尺度**：7 条里有 3 条是
  记者会表态（科技部「十五五」安排）、署名文章（国资委主任）、纲领性指导意见（八部门金融支持服务业），
  共同点是**叙了事、话也对，但没有改变规则或资源分配**。输出读起来像政务简报。
- 这与 round-01 的 `应急管理部视频调度`、round-04 的边界例是**同一类成因**：
  Importance Gate 能判断"有没有实质变化"的粗粒度，但无法区分"改了规则的事"和"表了个态的事"。
  这是当前体系最稳定、也最值得优先处理的一处能力缺口。
- 本轮自己犯的错：数条内容的来源指向同一个聚合页（检索深度不足，没拿到部委官网原文）。
  规则层因此报出 `SOURCE_URL_REUSED` 警告 —— 这条检查正是为此加的。

### round-04（历史低密度日 2026-10-02）

- 候选 6 条 → **输出 2 条**，没有为了凑到 5 条降低门槛，本期也没有硬造 Top 段（无 top_pick）。
  系统的默认行为是**少写而不是填满**，这一点比多收几条更有价值。
- 同日三条候选（独库公路封闭 / 秋粮收获过三成 / 假期高速充电量新高）用的是**同一个来源 URL**
  —— 新华社通稿在地方党媒的同一次转载。`SOURCE_URL_REUSED` 正确提示：不要把一份通稿的多个段落拆成多条。
- 保留的 `国家发展改革委服务业举措` 属边缘收录（带补贴项目扩面，但只有一条二手来源），
  它与 round-03 被判拒的「八部门指导意见」在判据上非常接近 —— 这一档边界是体系里最不稳定的地方，记为已知限制。

### round-05（跨日链路 PASS → DUPLICATE → UPDATED）

- Day1：事件首次出现 → `PASS`，输出。
- Day2：同一 fingerprint 被媒体再次讨论、窗口内无新进展 → `DUPLICATE_HISTORY`，**零输出**，
  且用的是标准表述「本期未检索到符合收录标准的条目」，没有写成「今天没有新闻」。
- Day3：同一 fingerprint 出现窗口内可核实的实质新进展 → `UPDATED`，放行输出。
- 三步链路全部成立，且裁决由程序按历史记录算，不看模型怎么说。
- 另外单独跑了一期**三种判定同存**的用例（`round-05/`）：去重拦下 1 条、UPDATED 放行 1 条、
  新事件（教育部招聘月）放行 1 条 —— 但后者被判为误收（年度例行部署），
  与 round-03 同一成因。

### round-06（来源压力测试）

同一个窗口，5 条候选分别配官方原文 / 权威二手 / 搜索引擎结果页 / 内容农场转载 / 社交聚合：

| 候选 | 唯一来源 | 裁决 | 拦截理由 |
|---|---|---|---|
| 商务部反倾销立案 | 商务部官网 | 输出 | — |
| 国铁老年票优惠 | 中国新闻网 + 中国网（新华社稿） | 输出 | — |
| 深水油田累产 200 万吨 | 百度搜索结果页 | 丢弃 | `SEARCH_URL_AS_SOURCE` |
| 医保局统一耗材通用名 | 搜狐转载 | 丢弃 | `SECONDARY_SOURCE_MISSING` |
| 国庆档票房破 3 亿 | 今日头条 | 丢弃 | `DISCOVERY_ONLY_AS_SOLE_EVIDENCE` |

**来源层级确实由程序执行，不是靠模型自觉。** 而且三种不同级别的来源缺陷被三种不同的
rule code 分别拒绝，没有出现"一个笼统的 LOW_TIER 把五条一起打死"——
拒绝理由是逐条可解释的。

---

## 6. 回归夹具的调整记录

架构变了，夹具要跟着变。但**不能为了让测试变绿而偷偷改 expectation**，
所以每一处改动都按下面三段式记录。

### 6.1 自报字段降级（v0.1.0 → v0.1.1 核心变化）

- 位置：`case-09 step3` / `step5`、`case-11 step1`、`case-12 step6`、`case-13 step11`
- `OLD_EXPECTATION=` 候选必须写满 v0.1.0 的六个 `gates.*_checked: true`，缺一项即判失败。
- `WHY_WRONG=` 这与本轮要修的问题直接冲突：把「模型说查过了」当成放行依据。
  字段缺席被当成失败，等于强迫模型继续自报。
- `NEW_EXPECTATION=` 字段缺席不报错；存在只记 `LEGACY_CHECKED_FIELDS_IGNORED` INFO；
  显式为 false 记 `LEGACY_GATE_REPORTED_FALSE` WARN。结论由程序按事实字段算。

### 6.2 投资条目的主体绑定

- 位置：`case-02`、`case-07`、`case-08`、`case-09`、`case-12`、`case-13`、`case-15` 中的投资候选
- `OLD_EXPECTATION=` 投资候选只需填 `section: investment` 即可，主体是什么不校验。
- `WHY_WRONG=` 这正是 round-02 抓到误收的原因：清单外个股的并购被放行。
  主体名单是可以枚举的事实，不该交给模型判断。
- `NEW_EXPECTATION=` 投资候选必须声明 `watchlist_subject`，指向 `config/watchlist.yaml` 的
  `institutions` / `assets` / 别名中的一项；对不上就报 `INVESTMENT_SUBJECT_UNBOUND`（输出时 BLOCK）。

### 6.3 新增测试

`case-15-fact-first-derivation.json` 从 T1—T8 扩到 **T1—T16（含 T5b 共 18 步）**，新增覆盖：

| 编号 | 验证 |
|---|---|
| T9 | 清单外域名 + `tier_reason` → 计入可信二手 |
| T10 | 清单外域名但给不出理由 → 不计入，仍按来源不足处理 |
| T11 | 同一家媒体的两个子域 → 只算一家发布者 |
| T12 | 声称「仅有可信二手」却给不出一条可信来源 → `SECONDARY_SOURCE_MISSING` |
| T13 | 合格条目超过 12 → 只 `TOO_MANY_ITEMS` 警告不阻断 |
| T14 | 三条内容共用同一个来源 URL → `SOURCE_URL_REUSED` |
| T15 | 投资条目没声明 `watchlist_subject` → `INVESTMENT_SUBJECT_UNBOUND` |
| T16 | 声明的主体不在清单里 → `INVESTMENT_SUBJECT_UNKNOWN` |

---

## 7. 已知限制

1. **单一轮检索覆盖不全。** round-02 证明重叠率只有 2/11。真实使用中必须承认这一点，
   不能把「这轮没搜到」当成「没有发生」。
2. **事后复盘拿不到当时的原文 URL。** 历史日期评估时，能检索到的往往是回溯稿，
   源 URL 的发布时间可能晚于评估截点。round-05-day1 就属于这种情况，已在候选文件里注明。
3. **标题与来源的匹配度校验不了。** 规则层能校验 URL 是否可引用、是否落在可信清单里，
   但校验不了「这条标题是否被这条 URL 支持」—— 它不看来源页的内容。标题与来源是否一致，
   目前只能靠人工复核（`tests/evals/*/labels.json` 的 note 与
   `tests/regression-checklist.md` 第四段是留痕处）。
4. **重要性判断仍完全依赖模型。** 系统能保证主体范围、时效、证据、去重，
   但「这件事值不值得占版面」还是模型在做（要求留下 `importance_reason`）。
   这是当前**最大的一处残留依赖**，也是误收的主要来源：23 条产出里 5 条误收，
   全部属于"事实没错但不该占版面"。细分成两种模式：
   - **例行公事 / 照稿表态**：round-01 的应急管理部视频调度、round-03 的科技部发布会与国资委署名文章；
   - **尺度不一致**：round-04 保留的发改委服务业举措，与 round-03 拒掉的八部门指导意见判据接近。
5. **栏目归类仍完全依赖模型。** 程序只校验栏目在不在 priority 里，不判断归得对不对。
   本轮 9 期产出里未出现错栏，但样本量不足以说明这一类已被解决。
6. **需要日期精度的地方只能取到日。** 多数中文新闻页不标注时刻，只能按当日 12:00 近似，
   窗口边界附近的判定会有 ±半天的不确定性。
7. **输出排版已按微信阅读收紧（v0.1.1 收尾时完成）。** `tests/check_output_readability.py`
   按「标题 ≤ 30 字」检查，9 期全部通过。这一处**没有靠放宽阈值解决** —— 渲染器的
   `TITLE_MAX_CHARS = 45` 仍是宽松硬上限（防「把一段话当标题」）；处理方式是把
   `round-05` 那条 31 字标题压缩到 24 字（事实与含义不变），使全部 9 期落在 30 字以内。

---

## 8. 复现方式

```bash
# 前三层
python tests/run_regression.py
python tests/run_cli_smoke.py
python tests/mutate.py

# 输出可读性（微信版排版）
python tests/check_output_readability.py

# 实战轮次（示例）
python tests/run_eval_round.py tests/evals/round-01 --now 2026-10-04T09:00:00+08:00
python tests/run_eval_round.py tests/evals/round-05-day3 --now 2026-10-04T09:00:00+08:00

# 汇总
python tests/compare_rounds.py tests/evals/round-01 tests/evals/round-02 \
  --out tests/evals/round-02/compare.md
python tests/run_eval_summary.py
```
