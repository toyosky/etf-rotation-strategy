# 本轮冻结证据归档

GitHub Release：<https://github.com/toyosky/etf-rotation-strategy/releases/tag/research-taxonomy-v3-20261112>

资源：`taxonomy-v3-evidence-20261112.tar.gz`（使用仓库访问身份下载草稿 Release）。

SHA-256：`1c21c656a1de052f8263b453ed800c7146dd919bc8825bde8a5a906bc9bbeb8d`

解压内容：

- `taxonomy-profiles/`：2,147 只基金的辅助资料解析 JSON 与原始 HTML gzip。原响应字节哈希可用解压 HTML 核对。
- `taxonomy-official/`：官方 JSON 解析 payload、观测时间、原请求 URL、原响应 SHA-256。保留语义完整的 JSON，但没有保留原 HTTP 字节/头；文件自身哈希以构建 manifest 为准。
- `refreshed_daily_bars.parquet`：实际读取并核验过的 2,003 只行情快照，1,439,205 行，截止 2026-11-11。

行情 SHA-256：`9d55f6e0a511be72609e799b19d04c1b44e2555374298bceef102a0481a067fb`

metadata 全量只读备份、官方 payload、CSV/JSON/Parquet 分类产物和报告保存在同一研究提交中；无凭据写入这些文件。生产表未改动。

本文件中的 Release 和资源将在完成上传校验后交付；真实 GitHub 执行结果以最终交付消息为准。
