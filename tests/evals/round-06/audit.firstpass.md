# 审计 · 2026-10-04

统计窗口终点：2026-10-04T09:00:00+08:00

## 总量

- 候选总数：5
- 收录（PASS/UPDATED）：2
  - 其中：PASS 2
- 丢弃：3
- 最终条目数：2

## 收录分布

- universal_policy：2

## 各 Gate 拒绝数

- evidence：3

## 逐条审计

### c01 · PASS

- 标题：商务部对原产于欧盟的进口对硝基甲苯发起反倾销立案调查
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=True｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True

### c02 · PASS

- 标题：国铁集团优化老年旅客淡季购票优惠措施
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c03 · BLOCKED

- 标题：我国首个深水油田二次开发项目累产原油突破200万吨
- 栏目：investment｜声明状态：PASS｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence BLOCK✗  duplication PASS✓  importance BLOCK✗  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=False｜可输出=False
- 理由：LOW_VALUE_PRICE_ONLY、MATERIAL_UPDATE_UNSUBSTANTIATED、SEARCH_URL_AS_SOURCE

### c04 · BLOCKED

- 标题：国家医保局统一7类医用耗材医保通用名
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence BLOCK✗  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING、SECONDARY_SOURCE_MISSING

### c05 · BLOCKED

- 标题：国庆档电影总票房突破3亿元
- 栏目：social｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence BLOCK✗  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=False｜可输出=True
- 理由：DISCOVERY_ONLY_AS_SOLE_EVIDENCE、SECONDARY_SOURCE_MISSING

## 整期级发现

- [BLOCK] DISCOVERY_ONLY_AS_SOLE_EVIDENCE（c05）
- [BLOCK] SEARCH_URL_AS_SOURCE（c03）
- [BLOCK] SECONDARY_SOURCE_MISSING（c04）
- [BLOCK] SECONDARY_SOURCE_MISSING（c05）
- [WARN] POLICY_PRIMARY_MISSING（c02）
- [WARN] POLICY_PRIMARY_MISSING（c04）
- [BLOCK] LOW_VALUE_PRICE_ONLY（c03）
- [BLOCK] MATERIAL_UPDATE_UNSUBSTANTIATED（c03）
- [INFO] SOURCE_TIER_JUSTIFIED（c02）
