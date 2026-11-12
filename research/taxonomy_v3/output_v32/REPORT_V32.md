# ETF/LOF 经济暴露 V3.2 实际补证与回归报告

本轮修复同指数别名拆分、跨市场区域和民企标签错误，并继续补证。生产数据库、正式 OLS、持仓与现有交易定时任务未改动。

| 口径 | V3.1 | V3.2 |
|---|---:|---:|
| 总基金数 | 2147 | 2147 |
| 当前被动指数分类通过 | 1477 | 1549 |
| 通过率 | 68.79% | 72.15% |
| 兼容旧口径的待复核/池外队列 | 670 | 598 |
| 代码—全称桥接待核实原因数 | 119 | 51 |
| 当前通过集合的精确指数/保守暴露组 | 420 | 430 |

当前通过集合含 13 种一级标签、67 种二级标签；三级标签未核实的保持空值。

新口径区分：经济身份已核实 1552 只；真正尚有未解决分类问题 595 只；已核实但排除于默认被动指数池 3 只。原因可重叠，不能相加当基金数。

## 已修复与补证

- 159100、520870 的官方文件均明确写出 IBOVESPA，现共享精确键和暴露 ID；不同目标 ETF 留在产品复制方式层，不制造两个独立趋势机会。
- 富时中国国企开放共赢指数按官方 80只A股、20只香港上市公司范围标为 CN_HK；159973 的民企指数改为 PRIVATE_ENTERPRISE。宽泛的“富时中国/MSCI中国”不再自动填为纯CN。
- 恒生17组官方编制方案的价格代码已逐行核对；股息累计、净累计代码没有混入价格指数别名。恒生A股电网设备按实际A股范围处理，编制机构品牌不代替经济区域。
- 国证现金流/家电/信用债/科创债、中证A100双市场代码及纳斯达克100桥接均有冻结原文件；同指数不同写法统一到经过证实的身份。
- 医药LOF四组A/C份额以官方被动投资目标和份额代码表补证；中药LOF的当前ETF联接方式单独保留，不把业绩比较基准独自作为被动跟踪证据。
- 501018、159934、161226 属于已核实的池外策略/非指数参考，不再被统计成“身份尚未查清”；needs_review保留旧池口径，classification_status与unresolved_reasons说明实际状态。

## 当前同口径去重

实际行情 2003 只、1,439,205 行。当前分类通过且有行情 1476 只 → 精确指数 427 组 → 保守细分暴露 427 组；区域×资产类型×一级标签 35 组。其他基金是证据/策略排除，不能当成去重节省。没有未经核实的跨指数合并。

## 真实样例

| 代码 | 官方指数/法定策略 | 精确键 | 状态 |
|---|---|---|---|
| 159100 | 巴西伊博维斯帕指数 | INDEX_NAME:9a82a9f28ca239cd19a0 | VERIFIED_CURRENT_INDEX |
| 520870 | 巴西IBOVESPA指数 | INDEX_NAME:9a82a9f28ca239cd19a0 | VERIFIED_CURRENT_INDEX |
| 517090 | 富时中国国企开放共赢指数 | INDEX_NAME:e0a1421a673c7346af39 | VERIFIED_CURRENT_INDEX |
| 517180 | 富时中国国企开放共赢指数 | INDEX_NAME:e0a1421a673c7346af39 | VERIFIED_CURRENT_INDEX |
| 159973 | 国证民企领先100指数 | OFFICIAL_INDEX_CODE:399362 | VERIFIED_CURRENT_INDEX |
| 159320 | 恒生A股电网设备指数 | HSI:HSCAUPG | VERIFIED_CURRENT_INDEX |
| 159102 | 恒生生物科技指数 | HSI:HSBIO | VERIFIED_CURRENT_INDEX |
| 159166 | 国证自由现金流指数 | OFFICIAL_INDEX_CODE:980092 | VERIFIED_CURRENT_INDEX |
| 159501 | 纳斯达克100指数 | NASDAQ:NDX | VERIFIED_CURRENT_INDEX |
| 159923 | 中证A100指数 | CSI:000903 | VERIFIED_CURRENT_INDEX |
| 501005 | 中证精准医疗主题指数 | CSI:930719 | VERIFIED_CURRENT_INDEX |
| 501006 | 中证精准医疗主题指数 | CSI:930719 | VERIFIED_CURRENT_INDEX |
| 501007 | 中证互联网医疗主题指数 | CSI:930720 | VERIFIED_CURRENT_INDEX |
| 501009 | 中证生物科技主题指数 | CSI:930743 | VERIFIED_CURRENT_INDEX |
| 501011 | 中证中药指数 | CSI:930641 | VERIFIED_CURRENT_INDEX |
| 501012 | 中证中药指数 | CSI:930641 | VERIFIED_CURRENT_INDEX |
| 501018 | 全球原油基金中基金（非被动指数） | 无（非指数） | VERIFIED_EXCLUDED_STRATEGY |
| 159934 | 上海黄金交易所 Au99.99 现货合约 | 无（非指数） | VERIFIED_EXCLUDED_STRATEGY |
| 161226 | 上海期货交易所白银期货主力合约收益 | 无（非指数） | VERIFIED_EXCLUDED_STRATEGY |

## 时间与执行边界

当前资料最早从2026-11-13进入日期接口。2017/2021/2025等早期日期不会因当前补证而获得标签。执行属性批准数仍为0；未运行策略收益回测，也未批准实际交易池。
发现 0 条当前报告记载的合同有效日期早于抓取日、晚于首根行情的记录，见 strategy_history_review.json。501011/501012 的当前合同生效日为2022-12-02，而上市/行情更早；需取得转型时点原公告，才能建立历史策略区间。当前记录没有据此回填。

另保存 3 条恒生生物科技指数历史变更线索（2024-12-09更名及指数值缩放、2025-09-08选样范围变化、2025-09-15代码变化）。资料来自当前编制方案的修改记录，未核实当年的原始公告公布时间，所以不自动生成历史可用区间。

## 实际验证

- 44 项测试通过，失败/错误/跳过均为0。包含真实巴西双产品只能贡献一个代表、跨市场区域、民企、LOF A/C与非指数状态回归。
- 官方CSI原始工作簿与 2388 条解析记录一致；39 份成功采集PDF及文本哈希已核对。失败链接保留请求记录，没有据此批准分类。
- 13 个生成文件及完整manifest重复构建逐字节一致；Parquet实际以PAR1开头并可读，非LFS指针。
- 冻结输入均在仓库与既有归档中，run_v32.py离线完成验收；只修改独立研究工作流，无定时触发。

## 剩余复核原因

| 原因 | 条目数（重叠） |
|---|---:|
| AUXILIARY_TRACKING_IDENTITY_ONLY | 21 |
| ENHANCED_STRATEGY_REQUIRES_MANDATE_REVIEW | 76 |
| INDEX_ECONOMIC_REGION_OR_ASSET_NOT_VERIFIED | 13 |
| INDEX_SECTOR_CLASSIFICATION_NOT_VERIFIED | 53 |
| LOF_LEGAL_TRACKING_MANDATE_NOT_VERIFIED | 107 |
| NOT_IN_CAPTURED_OFFICIAL_LISTS | 24 |
| OFFICIALLY_VERIFIED_NON_INDEX_REFERENCE_EXCLUDED | 2 |
| OFFICIALLY_VERIFIED_NON_PASSIVE_STRATEGY_EXCLUDED | 1 |
| OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED | 51 |
| OFFICIAL_FITTED_CODE_MISSING | 179 |
| OFFICIAL_LIST_HAS_NO_TRACKED_INDEX | 142 |

后续仍需逐份核实剩余LOF/增强策略、解决其余指数身份桥接、补历史变更公告及执行证据。当前比例不是全市场分类或无前视回测已经完成的声明。
