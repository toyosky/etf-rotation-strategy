# ETF/LOF 经济暴露分类 V3（研究独立交付）

实际结果、覆盖率、已修复映射和限制见 [REPORT_20261112.md](REPORT_20261112.md)。
这是部分证据核实后的保守版本；**没有完成历史合同普查，没有任何实际基金获得完整执行属性批准**。
当前快照不能直接用于 2021 年严格回测。生产 OLS、元数据、持仓和定时任务未修改。

## 文件契约

- `snapshot/metadata.json`：Supabase 全表只读备份，保留全部 2,064 行和历史区间；不是只导出当前视图。
- `snapshot/schema.json`、`summary.json`、`overlaps.json`、`bars.json`、`storage.json`：实际结构及只读审计。
- `snapshot/official/`：交易所与指数官方原始 JSON 响应、实际请求 URL、观测时间、响应 SHA-256。
- `output/classifications.{json,csv,parquet}`：每只基金的当前 V3 记录。空值表示未知，不用旧标签自动补值。
- `output/review_queue.{json,csv}`：按基金追踪原因、置信状态、官方及辅助来源。
- `output/identity_review.json`：官方代码与全称未完成桥接的候选；禁止凭辅助名称静默合并。
- `output/quality_audit.json`：旧标签合并/拆分差异、增强策略差异及未解决桥接。
- `output/prelisting_history_review.json`：行情早于当前产品官方上市日期的记录。
- `output/profiles.json`：全量辅助资料 facts、URL、抓取时间、原始响应哈希；不等于官方合同。
- `output/manifest.json`：冻结输入、代码、别名配置与生成文件的校验和。
- `output/validation.json`、`execution_checks.json`：真实运行验收记录。
- `index_aliases.json`：只有取得证据的代码别名，包含证据原文、链接和日期。

沿用 `name`、`product_type`、`region_primary` 等既有语义，独立新增 `legal_fund_name`、`tracking_mode`、`exact_index_key`、`exposure_id`、`sector_level1/2/3`、`exposure_type`、来源、版本与审计字段。`legacy_*` 仅保留差异审计用途。没有要求修改原数据库字段。

`exact_index_key` 可来自官方代码或完整官方名称的哈希；后者不填造 `index_code`。
同一指数的已证实代码别名才统一；价格、全收益、净收益、低波、区域等限定不被粗暴清洗。
`exposure_id` 暂按已核实指数保守保留，增强策略单列待审；尚无跨指数等价合并。
一级/二级行业用于描述和审计，绝不参与最终身份生成。

## 从归档离线复现

Python 3.12；从仓库根目录运行。安装到独立虚拟环境：

```bash
python -m venv .venv-taxonomy
.venv-taxonomy/bin/pip install -r research/taxonomy_v3/requirements.lock
gh release download research-data-fullmarket-current --repo toyosky/etf-rotation-strategy \
  --pattern refreshed_daily_bars.parquet --dir /tmp/taxonomy-prices
```

该行情 Release 会更新，**本轮重现必须匹配**报告的 SHA-256：
`9d55f6e0a511be72609e799b19d04c1b44e2555374298bceef102a0481a067fb`。
本轮证据归档包含冻结行情副本，使用该副本可避免后续 Release 更新的影响；确切归档链接见 `ARCHIVE.md`。

将归档中的辅助缓存解压到 `/tmp/taxonomy-evidence`；也可从已提交的 facts 重建离线输入，无需重复请求：

```bash
.venv-taxonomy/bin/python - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/taxonomy-profiles'); p.mkdir(exist_ok=True)
for r in json.loads(Path('research/taxonomy_v3/output/profiles.json').read_text()):
    (p/(r['symbol']+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2))
PY
.venv-taxonomy/bin/python -m research.taxonomy_v3.build \
  --metadata research/taxonomy_v3/snapshot/metadata.json \
  --profiles /tmp/taxonomy-profiles \
  --official research/taxonomy_v3/snapshot/official \
  --bars /tmp/taxonomy-prices/refreshed_daily_bars.parquet \
  --snapshot-date 2026-11-12 --output /tmp/taxonomy-v3-reproduced
.venv-taxonomy/bin/python -m research.taxonomy_v3.validate \
  --output /tmp/taxonomy-v3-reproduced --bars /tmp/taxonomy-prices/refreshed_daily_bars.parquet
.venv-taxonomy/bin/python -m pytest research/taxonomy_v3/test_taxonomy.py -q
```

辅助 JSON 的空白/键顺序会改变输入文件字节哈希，但同一 facts 生成的分类产物保持一致；原始归档缓存用于复现完整输入哈希。

## 重新采集（只读、可断点恢复）

先通过 Supabase MCP 或只读数据库连接逐条执行 `audit_source.sql`，另存全量元数据及结构快照。
不提供生产表写入入口。每个采集日使用新的目录，避免把旧缓存假装成当天资料。

```bash
python -m research.taxonomy_v3.collect_official --cache /tmp/taxonomy-YYYYMMDD/official
python -m research.taxonomy_v3.prepare_universe \
  --metadata /path/to/metadata.json --official /tmp/taxonomy-YYYYMMDD/official \
  --bars /path/to/refreshed_daily_bars.parquet --output /tmp/taxonomy-YYYYMMDD/universe.json
python -m research.taxonomy_v3.collect \
  --universe /tmp/taxonomy-YYYYMMDD/universe.json --cache /tmp/taxonomy-YYYYMMDD/profiles --workers 6
```

官方分页检查条数与代码唯一性；不完整时先续采。辅助请求逐基金缓存成功或错误，资料缺失不会丢掉该基金；`--retry-errors` 只重试错误。
`build` 日期必须与证据抓取日相同，避免通过参数伪造历史快照。全量当前报告生成器 `report.py` 专用于本轮冻结审计，不是自动滚动报告模板。

## 按日期取分类与唯一代表

```python
import json
import pandas as pd
from research.taxonomy_v3.model import classifications_at
from research.taxonomy_v3.representatives import Policy, select_representatives

rows=json.load(open('research/taxonomy_v3/output/classifications.json'))
active, excluded=classifications_at(rows, '2021-01-04')  # 本轮真实返回 active=[]

# calendar 必须是调用者核验的、覆盖全部输入行情及决策日的交易所日历。
# 以下调用须在任何 OLS 计算/候选筛选之前完成。
result=select_representatives(rows, bars, calendar, decision_date,
    policy=Policy(), risk_observations=dated_execution_observations)
representatives=result['representatives']
```

接口亦可用命令行：

```bash
python -m research.taxonomy_v3.representatives \
  --classifications /path/to/reviewed-classifications.json \
  --bars /path/to/bars.parquet --calendar /path/to/verified-calendar.json \
  --date YYYY-MM-DD --risks /path/to/dated-risk-observations.json --output /tmp/representatives.json
```

日历是排序无重复的 ISO 日期数组；`calendar_observed.json` 仅是实际行情日期集合，不认证未来交易所日历。
行情至少需要 symbol、date、open、high、low、close、amount；金额单位必须先核验为人民币元。
可选 `available_on` 表示历史行情真正可用日，必须早于决策日。现有历史归档为回补/复权数据，没有完整逐日可用性证明。
溢价、跟踪误差、停牌信息输入包含 symbol、observation_date、known_from，及 premium、tracking_error、suspended；溢价是小数比例。
NAV 日期不能替代公布日。原 Supabase premium 表已有 first_seen_at、pit_safe、backfilled，但本轮未把回补记录当历史可知数据。

V3 区间一律半开 `[valid_from, valid_to)`；同一基金重叠直接报错。`known_from`、`listing_known_from` 是决策日开盘前可知的首日，非资料生效日。
本轮当前资料最早在 2026-11-13 可用于日期接口。没有历史合同，不向前延伸；有转换前身的历史行情不计入现行产品上市后长度。

基金还必须有审核过的执行字段：`execution_attributes_verified=true`，并附来源证据；当前记录全部 false。
缺少币种/结算/复制方式核验的产品不会获得代表资格。后续人工补证应形成新的可审核分类文件/历史区间，再通过验证，不直接修改生产表。

## 备份和回滚

本分支仅增加 `research/taxonomy_v3/`，不写任何数据库表、不部署、不修改工作流。
撤销研究文件可回滚本分支提交；生产数据无需恢复。
未来如批准写研究表或替换生产元数据，须另做完整备份、变更预览、区间/唯一性测试和回滚演练；本项目没有隐式自动发布动作。
