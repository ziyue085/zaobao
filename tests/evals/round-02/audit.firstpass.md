# 审计 · 2026-10-04

统计窗口终点：2026-10-04T09:00:00+08:00

## 总量

- 候选总数：8
- 收录（PASS/UPDATED）：3
  - 其中：PASS 3
- 丢弃：5
- 最终条目数：3

## 收录分布

- universal_policy：3

## 各 Gate 拒绝数

- freshness：2
- evidence：2
- category：1

## 逐条审计

### c01 · PASS

- 标题：商务部对原产于欧盟的进口对硝基甲苯发起反倾销立案调查
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=True｜交叉来源=1｜历史命中=False｜实质事件=True｜可输出=True

### c02 · PASS

- 标题：国铁集团优化老年旅客淡季购票优惠措施
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c04 · PASS

- 标题：自然资源部公布1—8月新一轮找矿突破进展
- 栏目：universal_policy｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True

### c03 · DROP

- 标题：国家医保局发布7类医用耗材分类与代码及医保通用名
- 栏目：universal_policy｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：国家医保局官网通知公告日期为2026年9月18日，超出24小时窗口；10月2—3日的报道属二次传播。

### c05 · DROP

- 标题：我国首个百兆瓦级压缩二氧化碳储能项目并网发电
- 栏目：unexpected｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：项目于10月2日并网，10月3日《新闻联播》报道；事件本体超出24小时窗口。

### c06 · BLOCKED

- 标题：中国联通：结构调整基金拟减持不超过1.2%股份
- 栏目：investment｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence BLOCK✗  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=True｜可输出=True
- 理由：DISCOVERY_ONLY_AS_SOLE_EVIDENCE、SECONDARY_SOURCE_MISSING

### c07 · BLOCKED

- 标题：峰岹科技拟1.18亿美元收购Sciosense全部股份
- 栏目：investment｜声明状态：PASS｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category BLOCK✗  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=True｜可输出=True
- 理由：INVESTMENT_SUBJECT_UNBOUND

### c08 · DROP

- 标题：教育部部署开展2027届高校毕业生校园招聘月活动
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：部署类工作通报，不进入输出。

## 整期级发现

- [BLOCK] DISCOVERY_ONLY_AS_SOLE_EVIDENCE（c06）
- [BLOCK] SECONDARY_SOURCE_MISSING（c06）
- [INFO] PRIMARY_SOURCE_MISSING（c08）
- [INFO] SECONDARY_SOURCE_MISSING（c03）
- [BLOCK] INVESTMENT_SUBJECT_UNBOUND（c07）
- [WARN] POLICY_PRIMARY_MISSING（c02）
- [INFO] POLICY_PRIMARY_MISSING（c03）
- [INFO] QUASI_PRIMARY_USED（c04）
- [INFO] QUASI_PRIMARY_USED（c08）
- [INFO] SOURCE_TIER_JUSTIFIED（c07）
- [INFO] SOURCE_TIER_JUSTIFIED（c08）
- [INFO] TIME_OUT_OF_WINDOW（c03）
- [INFO] TIME_OUT_OF_WINDOW（c05）
