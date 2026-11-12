# 冻结行情完整性阻断根因审计（2026-11-13）

## 复核证据

- 载体连续性重跑 GitHub Actions [43283330355](https://github.com/toyosky/etf-rotation-strategy/actions/runs/43283330355) 在哈希门禁失败，未产出有效研究数据。
- GitHub Actions 日志：下载文件实际 SHA256 `7a218407280309b475998668ccd3d232cfc67efda307f97db3f76fef7324b644`，大小 17,166,998 字节；研究分类 `output_v32/summary.json` 要求 `9d55f6e0a511be72609e799b19d04c1b44e2555374298bceef102a0481a067fb`。
- [Release API](https://api.github.com/repos/toyosky/etf-rotation-strategy/releases/tags/research-data-fullmarket-current) 在本轮检查时显示 `refreshed_daily_bars.parquet` asset id `740827992`，创建/更新时间 2026-11-12 19:39:51 UTC，size 17,166,998，digest `sha256:7a218407280309b475998668ccd3d232cfc67efda307f97db3f76fef7324b644`，与失败日志完全一致。
- `summary.json` 仍保存旧哈希 `9d55f6e0...`。因此已确定：**标签名为 current 的 Release 资产已被替换，原研究所指的字节级冻结数据不再由该标签提供**。这不证明新文件的行数、覆盖日期、价格字段是否改变；必须做内容差异核验，不能只更新预期哈希。

## 修复原则（不碰正式数据流）

1. 不得将脚本中的预期哈希直接改为 `7a2184...`，不得关闭门禁。
2. 从旧 Actions artifact、不可变 release asset、原始归档备份中恢复 `9d55f6e0...` 版本，按内容哈希复验后建立不可变研究快照（单独版本标签和 manifest，保留 asset id、SHA256、字节数、截止日、行数、字段、采集时点）。
3. 如果旧字节不可恢复，必须同时保存旧研究结果为历史证据、新文件为**另一数据版本**；比较旧新文件日期、symbol、OHLC、amount 的差异，并在新版本上完整重跑 V1/V2/载体连续性及一致性审计，不能把新结果与旧分母直接拼接。
4. 给研究工作流添加下载后双重核验（Release API digest + 固定研究 manifest），禁止仅以 `research-data-fullmarket-current` 作为“冻结”标识。
5. 在恢复或正式版本迁移前，载体连续性检测率标记 **BLOCKED**；V2 的 72.46% 仅是旧归档代码口径，不可静默迁移到新资产。

## 本轮结果

本轮完成失败原因的可核验定位和防误用决策；未执行数据回测、未得到载体切换统计，也未修改 main / 实盘 / Supabase。下一轮优先定位旧归档可恢复来源或建立严格版本迁移。