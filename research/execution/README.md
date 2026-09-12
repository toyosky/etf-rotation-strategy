# Execution Research

用于 V1 成交额信号、Top1 接管/切换、分钟级执行、滑点和 QDII/LOF 交易约束研究。

研究顺序：

1. Universe / asset class 先稳定；
2. 日频 OLS 和 takeover 逻辑再稳定；
3. 最后优化分钟级执行。

不要用分钟级细节掩盖上游 Universe 或信号质量问题。
