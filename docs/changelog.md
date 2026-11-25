# Changelog

## 2026-09-07 — Initial import

正式冻结版本：`SEVEN_STAR_F1_CASH_DEFENSE_FROZEN_V1`

- 初始化私有策略仓库。
- 导入当前认可的聚宽正式策略。
- 固化 7 ETF 候选池、Top1、现金信号、D2、反转冲击年龄与次日执行规则。
- 将 PushPlus Token 从仓库代码中移除，避免密钥进入 Git 历史。
- 后续每次正式规则变化均通过独立 commit 记录。

## 2026-11-22 — M1 + Q90 position sizing adapter (draft PR)

- 在FixV2/V1/Void执行框架中加入M1概率校准与Q90目标仓位计算：`P_M1=clip(P0+clip(0.65×recent_err,±12pp),0.005,0.995)`，成熟样本不足40时回退P0；`E=clip(clip(1−1.10×Dnormal/Q90,0,1)×clip(1+2×(P_M1−Pvol),0,1.8),0,1)`。
- 正常市场支持同一ETF每日部分减仓/补仓；信号必须与最终执行ETF及日期精确匹配。
- Void未路由时冻结账户实际份额和现金；Void防御路由继续沿用原有状态机。
- 缺少同日同标的有效M1预测时，不将缺失数据解释为零风险：同标的旧仓保留份额，新风险标的禁止新开仓。
- 删除未经验证的5%最小减仓和5个百分点调仓带宽。
- 增加M1公式、输入合同、Void规则和执行适配器单元测试。
- **M1_POSITION_CONTROL_ENABLED默认False**：目前尚无生产级逐ETF预测流水线；本PR仅集成计算/执行边界，不改变现行实盘行为。
