# 审计 · 2026-10-04

统计窗口终点：2026-10-04T09:00:00+08:00

## 总量

- 候选总数：12
- 收录（PASS/UPDATED）：5
  - 其中：PASS 5
- 丢弃：7
- 最终条目数：5

## 收录分布

- universal_policy：2
- investment：1
- ai：1
- social：1

## 各 Gate 拒绝数

- freshness：5
- output：2

## 逐条审计

### c01 · PASS

- 标题：商务部对原产于欧盟的进口对硝基甲苯发起反倾销立案调查
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=True｜交叉来源=1｜历史命中=False｜实质事件=True｜可输出=True

### c02 · PASS

- 标题：应急管理部视频调度国庆假期安全防范工作
- 栏目：social｜声明状态：PASS｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=True｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=True

### c03 · PASS

- 标题：中国海油流花油田二次开发项目累产原油突破200万吨
- 栏目：investment｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=True｜可输出=True

### c04 · PASS

- 标题：Aleph Alpha 开源发布 Kolibri-1 模型
- 栏目：ai｜声明状态：PASS｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=True｜交叉来源=2｜历史命中=False｜实质事件=True｜可输出=True

### c05 · PASS

- 标题：国铁集团优化老年旅客淡季购票优惠措施
- 栏目：universal_policy｜声明状态：PASS｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence WARN!  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=False｜可输出=True
- 理由：POLICY_PRIMARY_MISSING

### c06 · DROP

- 标题：工信部公布8月末5G基站总数达519.5万个
- 栏目：universal_policy｜声明状态：LOW_VALUE｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=True｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：例行统计发布，不进入输出。

### c07 · DROP

- 标题：民政部提示防范以「民惠通」等为名的非法养老App诈骗
- 栏目：universal_policy｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：一手发布为2026年9月22日，超出24小时窗口；10月3日的报道属二次传播。

### c08 · DROP

- 标题：市场监管总局发布《国家统一推行自愿性认证制度管理办法（试行）》
- 栏目：universal_policy｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：总局官网公告日期为2026年9月30日，超出24小时窗口；10月3—4日的报道属二次传播。

### c09 · DROP

- 标题：Google 原型卫星搭载4枚TPU芯片发射升空
- 栏目：ai｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：卫星于2026年10月1日发射，媒体报道集中在10月3日；事件本体超出24小时窗口。

### c10 · DROP

- 标题：Google 发布新一代前沿模型 Gemini 4 Argon
- 栏目：ai｜声明状态：OLD｜证据：VERIFIED_PRIMARY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=True｜交叉来源=1｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：官方博客发布日期为2026年9月30日（美国时间），已超出24小时窗口；10月2—3日的报道属二次传播。

### c11 · DROP

- 标题：国家发展改革委民营局向民营企业公开推介52个投资项目
- 栏目：universal_policy｜声明状态：OLD｜证据：SECONDARY_ONLY
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=False｜一手=False｜交叉来源=0｜历史命中=False｜实质事件=False｜可输出=False
- 丢弃说明：新华社10月2日发布，超出24小时窗口。

### c12 · DROP

- 标题：我国首个深水油田二次开发项目累产原油突破200万吨
- 栏目：investment｜声明状态：DUPLICATE｜证据：VERIFIED_CROSS_SOURCE
- Gate：structure PASS✓  freshness PASS✓  evidence PASS✓  duplication PASS✓  importance PASS✓  category PASS✓  output PASS✓
- 派生：窗口内=True｜一手=False｜交叉来源=2｜历史命中=False｜实质事件=True｜可输出=False
- 丢弃说明：本期内部重复，保留 c03

## 整期级发现

- [INFO] SECONDARY_SOURCE_MISSING（c07）
- [INFO] SECONDARY_SOURCE_MISSING（c09）
- [INFO] SECONDARY_SOURCE_MISSING（c11）
- [WARN] POLICY_PRIMARY_MISSING（c05）
- [INFO] POLICY_PRIMARY_MISSING（c07）
- [INFO] POLICY_PRIMARY_MISSING（c08）
- [INFO] POLICY_PRIMARY_MISSING（c11）
- [INFO] MATERIAL_UPDATE_MISSING（c09）
- [INFO] MATERIAL_UPDATE_MISSING（c10）
- [INFO] DUPLICATE_IN_ISSUE（c12）
- [INFO] TIME_OUT_OF_WINDOW（c07）
- [INFO] TIME_OUT_OF_WINDOW（c08）
- [INFO] TIME_OUT_OF_WINDOW（c09）
- [INFO] TIME_OUT_OF_WINDOW（c10）
- [INFO] TIME_OUT_OF_WINDOW（c11）
