# 本轮冻结证据归档

独立归档提交：[8037109](https://github.com/toyosky/etf-rotation-strategy/commit/8037109205eb36a3514c5f14d8f2f8c2dba3d351)。

分支：`research/taxonomy-v3-evidence-20261112`。

资源：[taxonomy-v3-evidence-20261112.tar.gz](https://github.com/toyosky/etf-rotation-strategy/blob/8037109205eb36a3514c5f14d8f2f8c2dba3d351/research/taxonomy_v3/archive/taxonomy-v3-evidence-20261112.tar.gz)。

Release 上传端点返回 HTTP 401，未成功发布新的 Release；改由已验证可用的 Git 推送单独归档，不改动已有 Release。大文件保存在归档分支，未加入代码 PR 的差异。

```bash
git fetch origin research/taxonomy-v3-evidence-20261112
git show FETCH_HEAD:research/taxonomy_v3/archive/taxonomy-v3-evidence-20261112.tar.gz > /tmp/taxonomy-v3-evidence-20261112.tar.gz
sha256sum /tmp/taxonomy-v3-evidence-20261112.tar.gz
tar -xzf /tmp/taxonomy-v3-evidence-20261112.tar.gz -C /tmp/taxonomy-evidence
```

先创建 `/tmp/taxonomy-evidence` 解压目录。使用仓库访问身份读取该私有仓库。

SHA-256：`1c21c656a1de052f8263b453ed800c7146dd919bc8825bde8a5a906bc9bbeb8d`

解压内容：

- `taxonomy-profiles/`：2,147 只基金的辅助资料解析 JSON 与原始 HTML gzip。原响应字节哈希可用解压 HTML 核对。
- `taxonomy-official/`：官方 JSON 解析 payload、观测时间、原请求 URL、原响应 SHA-256。保留语义完整的 JSON，但没有保留原 HTTP 字节/头；文件自身哈希以构建 manifest 为准。
- `refreshed_daily_bars.parquet`：实际读取并核验过的 2,003 只行情快照，1,439,205 行，截止 2026-11-11。

行情 SHA-256：`9d55f6e0a511be72609e799b19d04c1b44e2555374298bceef102a0481a067fb`

metadata 全量只读备份、官方 payload、CSV/JSON/Parquet 分类产物和报告保存在同一研究提交中；无凭据写入这些文件。生产表未改动。

GitHub 实际执行记录保存在 `output/github_delivery.json`，最终提交与 PR 链接见交付消息。
