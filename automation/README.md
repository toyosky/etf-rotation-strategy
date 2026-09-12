# Automation

这里保存长期运行的数据维护脚本，不保存一次性研究实验。

当前生产任务：

- `tencent_daily_sync.py`：腾讯 Westock HFQ ETF/LOF 日线增量同步到 Supabase。
- `tencent_daily_universe.csv`：当前同步标的清单。
- `test_tencent_daily_sync.py`：同步脚本单元检查。

对应 workflow：`.github/workflows/tencent-daily-bars-sync.yml`。

## 约定

自动化脚本必须：

- 幂等；
- 可手动补跑；
- 有写入后的完整性校验；
- 不把密钥写入仓库；
- 长期任务失败时有告警；
- 大型研究结果优先写 Parquet / Supabase Storage，而不是无限扩张数据库。

以后若新增 Storage 上传、公用数据库连接或数据质量巡检，优先在这里建立可复用模块，而不是复制到每个 workflow。
