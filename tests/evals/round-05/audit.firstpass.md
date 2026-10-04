# 审计 · 2026-10-04

统计窗口终点：2026-10-04T09:00:00+08:00

## 总量

- 候选总数：3
- 收录（PASS/UPDATED）：2
  - 其中：PASS 1、UPDATED 1
- 丢弃：1
- 最终条目数：2

## 收录分布

- universal_policy：2

## 各 Gate 拒绝数

- duplication：1

## 逐条审计

### c02 · UPDATED

- 标题：商务部公布欧盟进口对硝基甲苯反倾销立案调查问卷
- 栏目：universal_policy｜声明状态：UPDATED｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=True｜交叉来源=1｜历史命中=True｜实质事件=True｜可输出=True

### c03 · PASS

- 标题：教育部部署开展2027届高校毕业生校园招聘月活动
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c01 · DROP

- 标题：青岛胶州湾第二隧道盾构掘进全部完成
- 栏目：social｜声明状态：DUPLICATE｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=True｜实质事件=False｜可输出=False
- 丢弃说明：与最近 7 天内已输出事件同一 fingerprint，且无实质新进展。

## 整期级发现

- [WARN] POLICY_PRIMARY_MISSING（c03）
- [INFO] DUPLICATE_HISTORY（c01）
- [INFO] HISTORY_MATCH_UPDATED（c02）
- [INFO] SOURCE_TIER_JUSTIFIED（c03）
