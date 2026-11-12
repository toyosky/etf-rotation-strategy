# ETF/LOF 分类 V3.1 官方 CSI 指数目录补证

目标：只用官方当前指数代码—全称登记，修复 V3 的指数身份候选；不根据价格收益和 ETF 简称自动融合。

## 实际冻结覆盖变化

| 指标 | V3 | V3.1 |
|---|---:|---:|
| 总基金数 | 2147 | 2147 |
| 官方完整名称或代码—全称 | 1081 | 1583 |
| 当前分类通过 | 770 | 1474 |
| 待复核 | 1377 | 673 |
| 其中官方代码—全称未核实 | 682 | 123 |
| 行情内当前分类通过 | 733 | 1403 |
| 行情内精确指数组 | 268 | 414 |
| 分类身份/状态变动产品 | — | 1207 |

## 代表标的现状

| 代码 | V3.1 身份 | 分类批准 | 待复核原因 |
|---|---|---|---|
| 159981 | 易盛郑商所能源化工指数A | 是 | 无 |
| 159883 | 中证全指医疗器械指数 | 是 | 无 |
| 512170 | 中证医疗指数 | 是 | 无 |
| 516060 | 中证创新药产业指数 | 是 | 无 |
| 513290 | 纳斯达克生物科技指数 | 是 | 无 |
| 501018 | 无官方跟踪指数 | 否 | OFFICIALLY_VERIFIED_NON_PASSIVE_STRATEGY_EXCLUDED |
| 510300 | 沪深300指数 | 是 | 无 |
| 510330 | 沪深300指数 | 是 | 无 |
| 159100 | 巴西伊博维斯帕指数 | 是 | 无 |
| 520870 | 巴西IBOVESPA指数 | 是 | 无 |

## 尚未完成

- 不同指数可能存在持仓高度重叠；本轮没有做未经证实的跨指数合并。
- 当前官方索引及基金资料 2026-11-12 才采集，不能覆盖其之前的历史效力。
- 执行属性（币种、结算、溢价披露时点等）仍需单独核实；本轮不批准交易池。
- LOF 非指数策略不得根据比较基准或拟合指数制造被动跟踪身份。
- 保留 Draft PR，不修改生产数据库/OLS/站点。

## 典型更新（前 25 项）

- 158000 港股通金融ETF鹏华: SZSE_FITTED_CODE:H11146 → CSI:H11146；分类 待审 → 通过
- 158001 价值ETF嘉实: SZSE_FITTED_CODE:980081 → OFFICIAL_INDEX_CODE:980081；分类 待审 → 通过
- 158003 港股通医疗ETF嘉实: SZSE_FITTED_CODE:932069 → CSI:932069；分类 待审 → 通过
- 158005 工程机械ETF博时: SZSE_FITTED_CODE:931752 → CSI:931752；分类 待审 → 通过
- 158006 化工ETF博时: SZSE_FITTED_CODE:000813 → CSI:000813；分类 待审 → 通过
- 158008 储能电池ETF华夏: SZSE_FITTED_CODE:980027 → OFFICIAL_INDEX_CODE:980027；分类 待审 → 通过
- 158009 航空航天ETF南方: SZSE_FITTED_CODE:CN5082 → OFFICIAL_INDEX_CODE:CN5082；分类 待审 → 通过
- 158010 医疗ETF嘉实: SZSE_FITTED_CODE:399989 → CSI:399989；分类 待审 → 通过
- 158012 云计算ETF南方: SZSE_FITTED_CODE:931469 → CSI:931469；分类 待审 → 通过
- 158013 航空航天ETF易方达: SZSE_FITTED_CODE:CN5082 → OFFICIAL_INDEX_CODE:CN5082；分类 待审 → 通过
- 158017 化工ETF易方达: SZSE_FITTED_CODE:000813 → CSI:000813；分类 待审 → 通过
- 158019 电池ETF永赢: SZSE_FITTED_CODE:931719 → CSI:931719；分类 待审 → 通过
- 158023 红利低波ETF万家: SZSE_FITTED_CODE:931848 → CSI:931848；分类 待审 → 通过
- 158027 工业互联网ETF易方达: SZSE_FITTED_CODE:931495 → CSI:931495；分类 待审 → 通过
- 158028 稀有金属ETF招商: SZSE_FITTED_CODE:930632 → CSI:930632；分类 待审 → 通过
- 158030 航空航天ETF汇添富: SZSE_FITTED_CODE:CN5082 → OFFICIAL_INDEX_CODE:CN5082；分类 待审 → 通过
- 158031 创业板人工智能ETF易方达: SZSE_FITTED_CODE:970070 → OFFICIAL_INDEX_CODE:970070；分类 待审 → 通过
- 158032 化工ETF景顺: SZSE_FITTED_CODE:000813 → CSI:000813；分类 待审 → 通过
- 158036 卫星ETF华夏: SZSE_FITTED_CODE:931594 → CSI:931594；分类 待审 → 通过
- 158037 机器人ETF博时: SZSE_FITTED_CODE:H30590 → CSI:H30590；分类 待审 → 通过
- 158040 科创创业人工智能ETF国联安: SZSE_FITTED_CODE:932456 → CSI:932456；分类 待审 → 通过
- 158041 创业板算力ETF华夏: SZSE_FITTED_CODE:970083 → OFFICIAL_INDEX_CODE:970083；分类 待审 → 通过
- 158043 价值ETF南方: SZSE_FITTED_CODE:980081 → OFFICIAL_INDEX_CODE:980081；分类 待审 → 通过
- 158046 卫星ETF南方: SZSE_FITTED_CODE:931594 → CSI:931594；分类 待审 → 通过
- 158049 创业板算力ETF广发: SZSE_FITTED_CODE:970083 → OFFICIAL_INDEX_CODE:970083；分类 待审 → 通过
