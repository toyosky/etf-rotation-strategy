# ETF重建扩散实验触发的分类复核清单 V1

建立时间：2026-11-12。范围：V3.2已核实的当前指数身份及一级/二级描述标签，非595只全量未核实基金的补录任务。

## 优先审计：上位类别与下位类别重复扩散

| 当前二级标签 | 可能重复计数的其他标签 | 证据要求 | 当前处置 |
| --- | --- | --- | --- |
| ENERGY_EQUITY | COAL_EQUITY、OIL_GAS_EQUITY | 追踪指数官方成分表、权重及规则；确认是否含煤炭/油气 | 只在保守敏感性实验排除，不改变事实分类 |
| NON_BANK_FINANCIALS | INSURANCE、SECURITIES | 官方非银指数与保险/证券成分股、权重 | 同上 |
| INFORMATION_TECHNOLOGY | ARTIFICIAL_INTELLIGENCE、SOFTWARE、SEMICONDUCTOR | IT综合指数和各细分指数的成分交集、行业权重 | 同上 |
| EQUIPMENT | GRID_EQUIPMENT、MACHINERY、ROBOTICS | 设备/装备指数方法学及成分权重 | 同上 |
| BIOTECH | INNOVATIVE_DRUGS、CXO | 核查创新药/生物科技指数成分与业务收入占比 | 未自动合并，待证据 |

关键原则：同一经济暴露中的两只产品不应增加扩散计数；但是**相同持股的一部分**也不一定说明两个指数等价。经济等价需要事先确定可复核门槛，例如权重重叠率、成分股集中度以及行业收入暴露，再将覆盖信息作为信号强弱特征，而不是依据收益倒推分类。

## 首批需要溯源的示例

1. A股医药：2026-07-01 以 159992 创新药为先行者，之后观察到 BIOTECH/INNOVATIVE_DRUGS/MEDICAL_DEVICES/TCM/VACCINES 五个描述标签。需核查创新药与生物科技实际成分重合，而不应直接当五个独立资金流向。
2. A股金融：2026-06-11 以 512800 银行为先行者，随后计入 BANKS/INSURANCE/NON_BANK_FINANCIALS/SECURITIES。这里非银行金融可能包含保险和证券，属于高优先级重复风险。
3. A股能源：2026-07-22 以 159930 为先行者，之后出现 COAL_EQUITY/ENERGY_EQUITY/OIL_GAS_EQUITY。综合能源指数与煤炭/油气构成可能重叠。
4. A股工业：2026-06-23 电网设备先行，后续 DEFENSE/GRID_EQUIPMENT/ROBOTICS。它们属于同一一级行业但经济驱动未必相同，不应称为同一资金主线。
5. A股科技：2026-06-18 半导体先行，后续 DATA/ARTIFICIAL_INTELLIGENCE/INDUSTRIAL_IOT/INFORMATION_TECHNOLOGY。应分开评估上位IT指数与狭义主题的重叠。

## 验证操作规则

- 保持官方精确指数键，任何收益结果都不能反向修改`exact_index_key`。
- 以指数公司规则书、成分股权重及历史生效日为证据；缺失时标签保留但标记“描述性，不保证独立”。
- 第一轮比较当前细分标签和排除上位泛类的保守版本；分别报告5日/10日、样本量、未来10日收益和同行业超额，使用日期/月份区块不确定性衡量。
- 当前 V3.2 分类记录最早2026-11-13可知，不得将2021–2026年回溯分类当作真实历史PIT。
- 独立研究分支，禁止影响正式策略、日线同步、持仓、交易通知和现有定时任务。

关联脚本：`audit_intrasector_diffusion_v1.py`。输出：`output_v32/intrasector_diffusion_v1.md` 与 JSON。
