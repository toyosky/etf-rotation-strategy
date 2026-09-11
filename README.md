# ETF Rotation Strategy

私有量化策略仓库，用于保存聚宽 ETF 轮动策略的正式代码、规则说明、研究记录与版本历史。

## 当前正式版本

- Strategy ID: `SEVEN_STAR_F1_CASH_DEFENSE_FROZEN_V1`
- 平台：聚宽（JoinQuant）回测 / 模拟盘
- 模式：固定 7 只 ETF 候选池，收盘生成 Top1 信号，下一交易日执行
- 现金信号：`511220.XSHG` 成为 Top1 时映射为现金

正式代码位于：`strategy/main.py`

腾讯后复权 ETF/LOF 日线由 GitHub Actions 每天增量更新到 Supabase。部署、
校验和手动补跑说明见 [Tencent HFQ daily-bar sync](docs/TENCENT_DAILY_BARS_SYNC.md)。

## 目录

```text
strategy/main.py          当前正式聚宽策略
docs/strategy-spec.md     当前冻结规则说明
docs/changelog.md         版本变更记录
research/README.md        后续实验与研究入口
```

## 安全说明

仓库中不保存 PushPlus Token 等密钥。`strategy/main.py` 中的 `PUSHPLUS_TOKEN` 保持为空；部署到聚宽时请在自己的运行副本中填入 Token，且不要提交该密钥。

## 版本管理约定

- `main`：仅保存当前认可的正式版本。
- 每次策略规则发生实质变化，使用独立 commit 记录。
- 实验性改动优先记录在 `research/`，验证通过后再进入正式策略。
- Commit message 应说明规则变化，而不是只写“update”。
