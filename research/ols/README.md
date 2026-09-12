# OLS Research

用于 OLS 趋势识别、Top1 排名、episode、剩余趋势寿命和 takeover 诊断。

基准要求：

- OLS 主模型与固定池 benchmark 保持可复现；
- 先区分 Universe 效应与 Timing 效应，再讨论参数优化；
- 关注首次识别后的 5/10/20 日收益、Top1 持续期、MFE、MAE 和趋势生存概率；
- 精确阈值必须通过分位数 / Walk-Forward 等方式验证，避免历史路径过拟合。
