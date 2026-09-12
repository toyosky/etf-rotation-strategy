# Repository Architecture

本仓库同时承担正式策略、数据自动化、研究实验和文档记录四类职责。为了避免研究代码污染正式策略，后续统一按以下边界维护。

## 1. Production strategy

`strategy/`

只保存已经冻结或准备实盘/模拟盘使用的正式策略代码。实验信号、参数扫描、临时诊断不得直接写入这里。

## 2. Automation / data pipeline

`automation/`

保存长期运行的数据维护脚本，例如腾讯 HFQ 日线同步。自动化脚本应满足：

- 可重复执行（idempotent）
- 写入前后有完整性检查
- 密钥只通过 GitHub Actions Secrets 注入
- 失败由 workflow 明确告警
- 大型研究产物优先输出 Parquet 到 Supabase Storage，而不是持续扩张 PostgreSQL

当前生产自动化：

- `automation/tencent_daily_sync.py`
- `.github/workflows/tencent-daily-bars-sync.yml`

## 3. Research

`research/`

保存尚未进入正式策略的研究代码和实验记录。

研究代码按“假设 -> 数据 -> 方法 -> 结果 -> 结论”组织。长期原则：

- 固定 15 池作为 benchmark，不直接用全历史结果反向删改
- 动态候选池必须采用 past-only / walk-forward
- 中间大矩阵和参数扫描结果不要长期写入 PostgreSQL
- 可复现的大结果保存为 Parquet；数据库只保存摘要、状态和小型索引表

历史脚本暂时保留原路径，避免破坏已有 workflow。后续新增研究优先使用子目录，例如：

```text
research/
  asset_class/
  universe/
  ols/
  execution/
```

旧研究脚本在确认不再被 workflow 引用后，再迁入 `research/archive/`。

## 4. Documentation

`docs/`

保存正式规则、数据管线说明、架构说明和 changelog。重要研究结论应有 Markdown 记录，而不是只存在于 Actions 日志或临时输出中。

## 5. GitHub Actions

`.github/workflows/`

Workflow 分两类：

- Production：定时运行、影响 Supabase 或正式数据管线。
- Research：手动触发或一次性验证，不应默认定时运行。

当前明确的 Production workflow：

- `tencent-daily-bars-sync.yml`

其余 workflow 默认按 Research 看待，除非后续在文档中明确升级为 Production。

## 6. Storage policy

### PostgreSQL

适合：

- `daily_bars` 核心事实数据
- 标的元数据
- 数据质量状态
- 当前候选池
- OLS episode 摘要
- 最终回测指标

### Supabase Storage / Parquet

适合：

- 全市场日频特征矩阵
- Walk-forward 大型中间结果
- correlation / ranking 大矩阵
- 参数扫描逐日结果
- 历史研究快照

建议 Storage 路径：

```text
quant-research/
  features_daily/year=YYYY/
  universe_snapshots/
  backtests/<experiment>/
  diagnostics/<experiment>/
```

### GitHub

只保存代码、配置、轻量 CSV/JSON、文档和 workflow；不要提交 Parquet、大型日志、数据库导出或 Secrets。

## 7. Change policy

- 正式策略规则变化：独立 commit，并更新 `docs/strategy-spec.md` / `docs/changelog.md`。
- 数据管线结构变化：同步修改脚本、workflow 和文档，并做数据库验收。
- 研究脚本：优先新增，不覆盖历史实验；结论稳定后再合并/归档。
- 不在 GitHub 中保存任何 Token、数据库密码或 service role key。
