# 审计 · 2026-09-30

统计窗口终点：2026-09-30T09:45:00+08:00

## 总量

- 候选总数：12
- 收录（PASS/UPDATED）：7
  - 其中：PASS 7
- 丢弃：5
- 最终条目数：7

## 收录分布

- universal_policy：7

## 各 Gate 拒绝数

- freshness：2
- evidence：3

## 逐条审计

### c01 · PASS

- 标题：中国人民银行调整完善若干货币政策工具
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=True｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c02 · PASS

- 标题：三部门发布居民购房贷款贴息政策
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=True｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c03 · PASS

- 标题：八部门印发金融支持服务业扩能提质指导意见
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c04 · PASS

- 标题：科技部介绍「十五五」推进科技强国建设安排
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=True｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c05 · PASS

- 标题：国务院国资委提出十五五做好新央企组建和战略性重组
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c06 · PASS

- 标题：9月制造业PMI回升至50.1%重返扩张区间
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c11 · PASS

- 标题：农业农村部印发全国畜牧兽医行业发展十五五规划
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c07 · DROP

- 标题：中国人民银行开展905亿元7天期逆回购操作
- 栏目：investment｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：公开市场操作公告时间为9月29日09:20，超出24小时窗口；且属例行操作。

### c08 · DROP

- 标题：国务院9月重要政策汇总发布
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：汇总稿，无新增事实，不进入输出。

### c09 · DROP

- 标题：国务院常务会研究宏观政策发力提效
- 栏目：universal_policy｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：会议为9月28日，超出24小时窗口；9月29—30日的报道属二次传播。

### c10 · DROP

- 标题：央行调整多项货币政策工具，PSL利率降至1.5%
- 栏目：universal_policy｜声明状态：DUPLICATE｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：本期内部重复，保留 c01

### c12 · DROP

- 标题：外汇局公布8月国际收支货物和服务贸易顺差数据
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：例行数据发布，不进入输出。

## 整期级发现

- [WARN] POLICY_PRIMARY_MISSING（c01）
- [WARN] POLICY_PRIMARY_MISSING（c02）
- [WARN] POLICY_PRIMARY_MISSING（c03）
- [WARN] POLICY_PRIMARY_MISSING（c04）
- [WARN] POLICY_PRIMARY_MISSING（c05）
- [WARN] POLICY_PRIMARY_MISSING（c06）
- [WARN] POLICY_PRIMARY_MISSING（c11）
- [INFO] INVESTMENT_SUBJECT_UNBOUND（c07）
- [INFO] POLICY_PRIMARY_MISSING（c08）
- [INFO] POLICY_PRIMARY_MISSING（c09）
- [INFO] POLICY_PRIMARY_MISSING（c10）
- [INFO] POLICY_PRIMARY_MISSING（c12）
- [INFO] MATERIAL_UPDATE_MISSING（c07）
- [WARN] SOURCE_URL_REUSED（issue）
- [INFO] DUPLICATE_IN_ISSUE（c10）
- [INFO] SOURCE_TIER_JUSTIFIED（c01）
- [INFO] SOURCE_TIER_JUSTIFIED（c02）
- [INFO] SOURCE_TIER_JUSTIFIED（c02）
- [INFO] SOURCE_TIER_JUSTIFIED（c03）
- [INFO] SOURCE_TIER_JUSTIFIED（c04）
- [INFO] SOURCE_TIER_JUSTIFIED（c04）
- [INFO] SOURCE_TIER_JUSTIFIED（c05）
- [INFO] SOURCE_TIER_JUSTIFIED（c06）
- [INFO] SOURCE_TIER_JUSTIFIED（c07）
- [INFO] SOURCE_TIER_JUSTIFIED（c08）
- [INFO] SOURCE_TIER_JUSTIFIED（c09）
- [INFO] SOURCE_TIER_JUSTIFIED（c10）
- [INFO] SOURCE_TIER_JUSTIFIED（c11）
- [INFO] SOURCE_TIER_JUSTIFIED（c12）
- [INFO] TIME_OUT_OF_WINDOW（c07）
- [INFO] TIME_OUT_OF_WINDOW（c09）
