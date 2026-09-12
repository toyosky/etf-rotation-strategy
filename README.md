# ETF Rotation Strategy

私有量化研究仓库，用于维护 ETF/LOF 日线数据、轮动策略、候选池研究、OLS 趋势研究与 GitHub Actions 自动化。

## 当前定位

仓库分为四层：

```text
strategy/      正式策略代码

automation/    长期运行的数据维护脚本
research/      尚未进入正式策略的研究与验证

docs/          规则、架构、数据管线与版本说明
.github/       GitHub Actions
```

详细边界见 [`docs/REPOSITORY_ARCHITECTURE.md`](docs/REPOSITORY_ARCHITECTURE.md)。

## 正式策略

- Strategy ID: `SEVEN_STAR_F1_CASH_DEFENSE_FROZEN_V1`
- 平台：聚宽（JoinQuant）回测 / 模拟盘
- 正式代码：`strategy/main.py`
- 冻结规则：`docs/strategy-spec.md`

固定池策略目前作为研究 benchmark。新的全市场 / 动态资产大类研究在验证完成前，不直接修改正式策略。

## 日线数据管线

腾讯 Westock HFQ ETF/LOF 日线：

```text
Tencent Westock
  -> GitHub Actions
  -> automation/tencent_daily_sync.py
  -> Supabase PostgreSQL public.daily_bars
  -> research views / downstream research
```

生产 workflow：`.github/workflows/tencent-daily-bars-sync.yml`

当前设计：

- 每天北京时间 23:30 自动运行
- 最近 14 个自然日重复抓取并 upsert
- `(symbol, date)` 唯一键保证幂等
- 价格/OHLC 完整性校验
- stale symbol 校验
- 失败触发 PushPlus（需 GitHub Secret `PUSHPLUS_TOKEN`）

部署和补跑说明见 [`docs/TENCENT_DAILY_BARS_SYNC.md`](docs/TENCENT_DAILY_BARS_SYNC.md)。

## 数据存储原则

PostgreSQL 只长期保存核心事实表、元数据、质量状态和轻量研究摘要。

大型研究中间产物，例如全市场特征矩阵、Walk-Forward 明细、相关性矩阵和参数扫描结果，优先保存为 Parquet 到 Supabase Storage，避免挤占 PostgreSQL 免费数据库额度。

## Research

研究入口：[`research/README.md`](research/README.md)。

当前研究主线优先级：

1. 固定池作为冻结 benchmark。
2. 研究资产大类 / Universe 对 OLS 剩余趋势寿命的影响。
3. 月度 past-only 候选池与 Walk-Forward。
4. 再验证 V1 / score takeover 等 timing 层。
5. 最后再回到分钟级执行优化。

## 安全

仓库不保存：

- PushPlus Token
- Supabase 数据库密码
- Supabase service role key
- 其他 API key / credential

所有自动化密钥只通过 GitHub Actions Secrets 注入。

## 版本管理

- `main`：当前正式代码、可复现研究和基础设施。
- 正式策略变更必须独立 commit，并更新文档。
- 实验性逻辑优先留在 `research/`。
- Commit message 应说明实质变化，避免只有 `update`。
