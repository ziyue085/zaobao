# 候选条目示例

## 一、一条候选长什么样

早间情报的中间产物是**候选清单**，不是渲染好的正文。每条候选按
`schemas/candidate.schema.json` 组织：

```json
{
  "id": "c01",
  "title": "中国人民银行开展6000亿元中期借贷便利操作",
  "section": "universal_policy",
  "entity": "中国人民银行",
  "action": "开展",
  "object": "6000亿元中期借贷便利操作",
  "event_date": "2026-10-04T09:00:00+08:00",
  "status": "PASS",
  "evidence_status": "VERIFIED_PRIMARY",
  "sources": [
    {
      "url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/20261004.html",
      "publisher": "中国人民银行",
      "tier": "primary",
      "is_first_party": true
    }
  ],
  "primary_url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/20261004.html",
  "body_facts": [
    "中国人民银行今日公告，开展6000亿元中期借贷便利操作，期限1年。",
    "公告显示本次操作利率与上次持平。"
  ],
  "background": null,
  "top_pick": true,
  "top_pick_line": "中国人民银行开展6000亿元中期借贷便利操作。",
  "has_material_event": true,
  "gates": {
    "time_window_checked": true,
    "history_dedup_checked": true,
    "issue_dedup_checked": true,
    "primary_source_checked": true,
    "url_checked": true,
    "no_analysis_checked": true
  }
}
```

## 二、几个关键字段

| 字段 | 为什么重要 |
|---|---|
| `entity` / `action` / `object` | 三者拼成 fingerprint，决定跨日去重。写法要归一化（用「中芯国际」而不是「SMIC」） |
| `event_date` | **事件发生时间**，不是报道时间。时间窗判断完全依赖它 |
| `new_progress_at` / `new_progress_type` | 两个都填齐才算「实质新进展」。只填时间不填类型不算 |
| `status` | `PASS` / `UPDATED` 才能进入输出 |
| `evidence_status` | 决定能否输出、要不要加披露标记 |
| `has_material_event` | 投资与 AI 栏目的必填项。缺这个字段直接 BLOCK |
| `gates` | 六道闸门。**字段缺席 = 未检查 = BLOCK**，missing 不等于 false |
| `top_pick_line` | 进 Top 段的那一句话。注意它只在渲染层被检查禁词 |

## 三、一份可以直接运行的完整输入

见 `tests/cases/case-11-reverse-control-clean.json` 的 `steps[0].input`。
它是一份完全合格的期次，可以直接跑：

```bash
# 抽出候选
python - <<'PY'
import json, io
case = json.load(io.open("tests/cases/case-11-reverse-control-clean.json", encoding="utf-8"))
io.open("issue.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(case["steps"][0]["input"], ensure_ascii=False, indent=2))
PY

# 跑闸门
python scripts/zaobao_check.py check-issue issue.json --repo . --now 2026-10-04T09:00:00+08:00

# 渲染
python scripts/zaobao_render.py issue.json --repo . --now 2026-10-04T09:00:00+08:00
```

## 四、注意

本文件里的 URL、机构名与数字都是**合成的示例数据**，路径不存在。
参见同目录 `README.md`。
