# 审计 · 2026-10-02

统计窗口终点：2026-10-02T22:00:00+08:00

## 总量

- 候选总数：6
- 收录（PASS/UPDATED）：2
  - 其中：PASS 2
- 丢弃：4
- 最终条目数：2

## 收录分布

- universal_policy：1
- social：1

## 各 Gate 拒绝数

- evidence：4

## 逐条审计

### c02 · PASS

- 标题：青岛胶州湾第二隧道盾构掘进全部完成
- 栏目：social｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=False｜可输出=True

### c03 · PASS

- 标题：国家发展改革委推出系列举措支持服务业扩能提质
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True

### c01 · DROP

- 标题：国庆假期首日全社会跨区域人员流动量超3.29亿人次
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：例行假日客流统计，同类数据每月每假都发，不构成政策或事件变化。

### c04 · DROP

- 标题：G217线独库公路10月8日20时起实施冬季封闭
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：地方道路的季节性通行安排，属地方普通政策，无全国意义。

### c05 · DROP

- 标题：全国秋粮收获过三成
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：例行农情调度数据，逐旬发布，不构成事件。

### c06 · DROP

- 标题：国庆假期首日高速公路充电量创节假日单日历史新高
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：假日单日充电量属例行监测数据，不构成政策或重大事件。

## 整期级发现

- [INFO] INSUFFICIENT_CROSS_SOURCE（c01）
- [INFO] POLICY_PRIMARY_MISSING（c04）
- [INFO] POLICY_PRIMARY_MISSING（c05）
- [INFO] POLICY_PRIMARY_MISSING（c06）
- [INFO] QUASI_PRIMARY_USED（c01）
- [INFO] QUASI_PRIMARY_USED（c03）
- [INFO] SOURCE_TIER_JUSTIFIED（c04）
- [INFO] SOURCE_TIER_JUSTIFIED（c05）
- [INFO] SOURCE_TIER_JUSTIFIED（c06）
