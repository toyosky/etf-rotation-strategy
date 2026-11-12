# ETF/LOF 经济暴露分类：当前交付 V3.2

当前报告：[output_v32/REPORT_V32.md](output_v32/REPORT_V32.md)。本轮冻结日为2026-11-12。
V3、V3.1 的报告和 JSON 保留为历史审计基线；当前入口为 `output_v32/`。
生产元数据、正式 OLS、实盘持仓和现有交易定时任务均未改动。

## 当前状态与字段

每只产品保留官方指数身份、独立经济暴露、区域/行业描述、法定策略、来源与时间边界。
不能把字段非空当成核验完成，也不能把当前分类通过当成已经可以交易。

- `classification_status=VERIFIED_CURRENT_INDEX`：当前被动指数分类通过，执行属性仍需核实。
- `VERIFIED_EXCLUDED_STRATEGY`：经济身份已经核实，但主动FOF、现货参考或期货主力合约不属于默认精确指数池。它们不是未知分类。
- `NEEDS_REVIEW`：仍有未解决的分类问题，见 `unresolved_reasons`。
- `economic_classification_verified`：独立于池资格的经济身份状态。
- `needs_review`：保留旧版“未通过默认指数池检查”的兼容口径，包含已知池外策略；不能直接当作未分类人数。
- `exact_index_key` / `exposure_id`：经过证实的相同指数别名才统一；不同指数暂分别保留，不以一级行业直接去重。
- `index_code_namespace` / `index_return_variant`：有证据时说明厂商代码和价格/收益版本；未核实时留空。恒生价格代码未与股息累计、净累计代码合并。
- `replication_method` / `share_class`：保留目标ETF复制、A/C份额等产品区别。基金公司和份额名称不制造新的指数身份。

不强制填 `index_code`、编制机构、交易币种或结算方式。官方只证实名称时可以用稳定名称键，不能编造代码。
LOF必须由官方投资目标/策略证明被动关系，不能只根据“拟合指数”或业绩比较基准批准。
指数描述与收益/OLS逻辑分离；行业描述来自底层指数证据，不能替代所有规则和持仓的穿透审阅。

## 文件

- `snapshot/metadata.json`：原 Supabase 全表只读备份，保留全部2,064行；原表未被覆盖。
- `audit_source.sql`、`snapshot/schema.json`、`summary.json`、`overlaps.json`、`bars.json`、`storage.json`：真实结构及原始只读审计。
- `snapshot/official/`：原交易所、上证/国证 JSON payload。
- `snapshot/official_v31/`：官方 CSI 原始 XLSX、解析目录与追加国证响应。
- `snapshot/supplement_v32/`：官方原PDF、文本、请求状态、原始字节和文本哈希。失败链接也保留，不据此批准分类。
- `index_aliases.json`：经证实的代码/全称别名；新映射附文档引用和必需的代码表行，`evidence.py`核对。
- `fund_contract_evidence_v31.json`：累积法定策略证据（文件名延续V3.1），含V3.2补证及A/C份额。
- `output_v32/classifications.{json,csv,parquet}`：当前分类数据。新Parquet是直接可读的数据文件，不是LFS指针；原大型价格数据的LFS政策未改变。
- `output_v32/review_queue.{json,csv}`、`identity_review.json`、`quality_audit.json`：复核原因与重复暴露审计。
- `output_v32/strategy_history_review.json`：当前资料报告的合同日期与早期历史冲突线索，不能自动变成历史分类。
- `output_v32/index_history_review.json`：官方当前方案记载的更名、代码与选样范围变更；原始历史公布时间未核实，不回填区间。
- `output_v32/manifest.json`、`validation.json`、`execution_checks.json`：输入/代码/产物哈希、真实数据检查、测试与重复构建结果。

## 离线复现

Python 3.12；从仓库根目录运行：

```bash
python -m venv .venv-taxonomy
.venv-taxonomy/bin/pip install -r research/taxonomy_v3/requirements.lock
mkdir -p /tmp/taxonomy-v32/archive
git fetch origin research/taxonomy-v3-evidence-20261112
git show 8037109205eb36a3514c5f14d8f2f8c2dba3d351:research/taxonomy_v3/archive/taxonomy-v3-evidence-20261112.tar.gz > /tmp/taxonomy-v32/frozen.tar.gz
tar -xzf /tmp/taxonomy-v32/frozen.tar.gz -C /tmp/taxonomy-v32/archive
cp /tmp/taxonomy-v32/archive/refreshed_daily_bars.parquet /tmp/taxonomy-v32/
.venv-taxonomy/bin/python -m research.taxonomy_v3.run_v32 --work /tmp/taxonomy-v32
```

行情SHA-256必须为：`9d55f6e0a511be72609e799b19d04c1b44e2555374298bceef102a0481a067fb`。
脚本合并冻结官方来源，规范重建辅助facts文件，核对原始CSI工作簿及解析内容、官方PDF/文本哈希，构建两次并比较字节，验证真实产物、运行测试、生成报告。
没有网络请求或数据库写入；不是自动滚动分类程序。工作流只在研究分支源码/证据变化或手动触发时运行，没有定时触发。

原始辅助HTML及冻结价格归档见 [ARCHIVE.md](ARCHIVE.md)。新增PDF证据已直接归档在本研究分支。
如需完全复现原V3，而非当前代码，应使用 [815d8df版本说明](https://github.com/toyosky/etf-rotation-strategy/blob/815d8df/research/taxonomy_v3/README.md)。

## 新一轮采集

`collect_official.py`采集交易所和指数目录，`prepare_universe.py`取元数据、官方清单与实际行情的并集，`collect.py`按代码校验、分只缓存辅助资料。
`collect_documents_v32.py`批量下载已定位的官方文件，保存PDF、文本和哈希；它不自动批准新映射。成功缓存不重复请求，单项缺失不阻断其余资料。

每个采集日使用新的目录，保留旧冻结版本；不覆盖本轮证据。官方分页必须完整，当前快照日期必须与实际证据日期匹配，不能传旧日期伪造历史快照。
新增别名应附完整来源、代码行/名称证据及回归用例；失败文件不能作为分类证据。

## 日期接口与代表选择

```python
import json
from research.taxonomy_v3.model import classifications_at
from research.taxonomy_v3.representatives import Policy, select_representatives

rows=json.load(open('research/taxonomy_v3/output_v32/classifications.json'))
active, excluded=classifications_at(rows, '2021-01-04')  # 本轮真实返回空池

# bars、calendar、decision_date、dated_execution_observations由调用者提供。
# 此调用必须发生在任何OLS信号计算、候选过滤或排名之前。
result=select_representatives(rows, bars, calendar, decision_date,
    policy=Policy(), risk_observations=dated_execution_observations)
```

返回 `representatives`、`eligible`、逐只 `excluded` 及 `data_through`。
默认使用上一交易日已完成的60交易日平均成交额、200根上市后有效历史和最近10日有效价量，按流动性、历史长度和代码确定唯一代表。
显式交易日历决定上一交易日；缺少上一日行情不会回退到更早的最后行情。窗口不在删掉不合格日期后压缩。
输入收益/OLS列不会决定代表；溢价敏感产品必须有决策时已知的前一交易日溢价。跟踪误差缺失不编成零，停牌和异常行情有独立排除原因。

行情需要 symbol、date、open、high、low、close、amount，成交额单位须核验为人民币元。
可选 `available_on` 表示历史行情真正可用日。风险输入包含 symbol、observation_date、known_from，以及 premium、tracking_error、suspended；溢价以小数比例表示。
NAV日期不能代替公布日。当前归档是回补/复权价格，尚无完整逐日可用性证明。

## 时间和交易边界

分类采用半开 `[valid_from, valid_to)`，同一基金的重叠区间直接拒绝。`known_from`与资料有效日分开。
当前资料最早从2026-11-13进入日期接口，没有因找到旧报告就向2021年回填。
501011/501012当前报告记载2022-12-02合同生效，但其历史更早；需要转型原公告及完整历史证据，不能以首根行情证明当前策略。
所有实际产品的 `execution_attributes_verified` 仍为false；本轮没有批准真实交易池或运行严格历史策略回测。
后续OLS计算还需检查整个特征窗口内策略与分类的连续性。

本分支没有生产表写入入口。未来如需更新生产元数据，另做备份、差异预览、验证和可回滚实施；本次研究提交不隐式发布。
