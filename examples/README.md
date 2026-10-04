# 示例

本目录下所有文件都是**合成测试数据**，不是真实新闻。

- 人名、机构名后面的数字、URL 全部是虚构的，域名示例仅用于演示来源分级。
- 里面的 `arxiv.org` / `openai.com` / `pbc.gov.cn` 等真实域名只是为了让规则层的域名判定跑通，URL 路径本身不存在。
- 请勿把示例内容当成事实引用。

## 文件

| 文件 | 说明 |
|---|---|
| `sample-input.md` | 候选条目的结构说明与一份可直接运行的 JSON |
| `sample-output.md` | 合格期次的真实渲染结果（由 `scripts/zaobao_render.py` 生成） |
| `sample-output-empty.md` | 无合格条目时的真实渲染结果 |
| `sample-output-bad.md` | **反面样例**：一份集中了常见错误的输出，用于对照 |

## 反面样例的判定结果

`sample-output-bad.md` 用 `check-render` 跑出来是：

```text
BLOCK ×14   WARN ×5

ADVICE_LEAK            ANALYSIS_LEAK(×3)      CLICKBAIT_TITLE
TABLE_NOT_ALLOWED      CITATION_MISSING(×3)   OUTPUT_ITEM_MISSING(×3)
EMPTY_SECTION_RENDERED TOP_COUNT_MISMATCH     CITATION_UNKNOWN_SOURCE(WARN)
SECTION_HEADING_MISSING(WARN ×2)              TOP_LINE_MISSING(WARN ×2)
```

它同时踩了：Markdown 表格、投资建议、影响分析、标题党、Top 段声明 3 条实际只有 2 条、
引用搜索引擎页、渲染了空栏目、漏掉 3 条 PASS 条目的引用。

这正是规则层存在的意义 —— 这类输出**不应该发出去**。

## 复现方式

```bash
python scripts/zaobao_check.py check-render examples/sample-output-bad.md \
       --issue tests/cases/case-11-reverse-control-clean.json --repo .
```
