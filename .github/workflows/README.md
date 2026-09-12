# GitHub Actions

本目录的 workflow 分为生产自动化和研究实验两类。

## Production

### `tencent-daily-bars-sync.yml`

长期定时任务。每天抓取腾讯 Westock HFQ ETF/LOF 日线并 upsert 到 Supabase。

要求：

- 必须可重复运行
- 必须做数据完整性检查
- 失败必须保留日志并发送告警
- 所有密钥通过 GitHub Actions Secrets 注入

当前 Secrets：

- `ETF_DAILY_BARS_DATABASE_URL`
- `PUSHPLUS_TOKEN`

## Research workflows

除上述生产同步任务外，当前其余 workflow 默认视为研究实验或诊断工具。

这些 workflow 可以用于复现实验，但不应默认承担长期数据生产职责，除非在本文件中明确升级为 Production。

当前研究 workflow 包括但不限于：

- `asset-health.yml`
- `cluster90-*.yml`
- `corrected-health-cluster-walkforward.yml`
- `diagnose-monthly-pool-vs-fixed15.yml`
- `full-market-ols-storage.yml`
- `monthly-*.yml`
- `selected-top1-lifespan-diagnostic.yml`
- `trendability-stage1.yml`
- `validate-fixed15-vs-full-market.yml`
- `walk-forward-*.yml`

## 新 workflow 约定

新建 workflow 时应在文件名或注释里明确目的：

- `sync-*`：生产数据同步
- `research-*`：研究实验
- `diagnostic-*`：诊断
- `rebuild-*` / `repair-*`：维护或修复

长期定时任务必须同时满足：

1. 幂等；
2. 失败告警；
3. 输出可审计摘要；
4. 有明确的数据库/Storage 写入边界；
5. 不在 YAML 中硬编码任何密钥。
