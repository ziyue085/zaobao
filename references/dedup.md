# 跨日去重与 fingerprint

这是本项目最重要的一项能力，也是最容易做得不到位的一项。

## 一、问题

同一件事会被不同媒体用不同标题反复报道：

```
10-01  中芯国际发布2026年三季度报告
10-02  中芯国际三季报出炉，营收同比增长12%
10-03  SMIC 三季度业绩披露
10-04  中芯国际三季报持续引发讨论
```

如果按标题判重，这四条会被当成四件不同的事。

## 二、fingerprint 的构造

```
fingerprint = 归一化(主体) + "#" + 归一化(核心动作) + "#" + 归一化(核心事件)
```

例：

```
中芯国际#发布#2026年三季度报告
中国人民银行#开展#6000亿元中期借贷便利操作
市场监管总局#公布#某食品企业抽检调查结果
```

**刻意不含标题。** 标题是媒体加工的产物，主体＋动作＋事件才是事件本身。

### 归一化规则

1. 去掉所有空白与标点（中英文标点都去）
2. 英文转小写
3. 主体先查别名表归并，再剥掉常见公司后缀

```
中国石油化工股份有限公司  →  中国石化
中石化                    →  中国石化
Sinopec                   →  中国石化
SMIC                      →  中芯国际
央行                       →  中国人民银行
```

别名表在 `config/watchlist.yaml: aliases`，**日常维护只需要改这里**。

## 三、两级去重

### 第一级：本期内部去重

同一 fingerprint 在本期出现多次 → 只保留**来源最好**的一条。

来源质量排序（越小越好）：

```
primary(0)  <  trusted_secondary(1)  <  discovery_only(2)
同层级时，is_first_party == true 的优先
```

其余判 `DUPLICATE`。这就是"新华社、财联社、公司官网都报道同一件事，只输出一次，且优先公司官网"的实现方式。

### 第二级：跨日去重

对照 `data/history.jsonl`，回看至少 7 天（默认 30 天）。

| 情形 | 判定 |
|---|---|
| 命中 fingerprint，无实质新进展 | `DUPLICATE`，不输出 |
| 命中 fingerprint，有实质新进展 | `UPDATED`，可以输出 |
| 未命中 | 正常流程 |

**实质新进展**的判定见 `prompts/verify.md`。转载、重新讨论、热度回升都不算。

## 四、历史文件的形态

一行一条 JSON，UTF-8，无数据库：

```json
{"event_id":"2026-10-04-中芯国际#发布#2","date":"2026-10-04","entity":"中芯国际","action":"发布","object":"2026年三季度报告","title":"中芯国际发布2026年三季度报告","primary_url":"https://...","fingerprint":"中芯国际#发布#2026年三季度报告","section":"investment","evidence_status":"VERIFIED_PRIMARY","was_update":false,"superseded_fingerprint":null}
```

字段定义见 `schemas/history.schema.json`。

**这个文件不进 Git**（见 `.gitignore`）。它是个人运行数据，不是项目源码。

## 五、维护命令

```bash
# 试运行：看看会写入哪些记录（不落盘）
python scripts/zaobao_check.py record --issue issue.json --history data/history.jsonl

# 真正写入
python scripts/zaobao_check.py record --issue issue.json --history data/history.jsonl --write

# 按保留天数裁剪
python scripts/zaobao_check.py prune --history data/history.jsonl --days 30 --write
```

只有状态为 `PASS` 或 `UPDATED` 的候选会被写入历史。

## 六、常见错误

| 错误 | 后果 |
|---|---|
| 把标题写进 fingerprint | 换标题即失效，去重形同虚设 |
| 主体不归一化直接入库 | 「SMIC」和「中芯国际」被当成两家 |
| object 写太细（带上具体数字） | 同一事件因数字微调而无法匹配 |
| object 写太粗（只写"财报"） | 不同年份的财报被判成同一件 |
| 历史文件被提交到 Git | 换机器后状态混乱；也把个人数据推到了公开仓库 |
| 用"感觉"代替查历史 | 连发三天同一件事 |

`object` 的粒度掌握：**能区分不同事件、但不因措辞变化而失效**。带上年份与期次（`2026年三季度报告`），不要带具体数值。
