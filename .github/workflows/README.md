# GitHub Actions

本目录只保留需要长期定时运行的 workflow。一次性研究、诊断和历史 Stage workflow 已移除；对应 Python / Markdown / findings 等研究代码与记录仍保留在仓库中，可按需手动恢复 workflow 复现实验。

## Retained scheduled workflows

### `tencent-daily-bars-sync.yml`

生产数据任务。每天抓取腾讯 Westock HFQ ETF/LOF 日线并 upsert 到 Supabase。

主要 Secrets：
- `ETF_DAILY_BARS_DATABASE_URL`
- `PUSHPLUS_TOKEN`

### `asset-health.yml`

月度 Asset Health 监控。保留原有定时运行逻辑，用于持续检查 Fix15 / 重点资产的 Top1 后续健康状态。

### `oure-stage7f-forward-monitor.yml`

冻结的 Stage7F 前瞻监控。工作日定时运行，用于保持原 prospective experiment 的连续性；不因后续研究结论回改历史定义。

## Repository policy

- 一次性研究实验只保存源代码、设计文档和 findings，不长期保留 GitHub Actions 入口。
- 新增长期 workflow 前应确认确实需要 schedule。
- 定时任务必须幂等、可审计，并通过 GitHub Secrets 注入密钥。
- 研究代码的删除与 workflow 清理是两件事；清理 workflow 不删除历史研究实现。
