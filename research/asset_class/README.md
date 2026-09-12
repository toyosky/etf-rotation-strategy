# Asset Class Research

用于研究资产大类层面的机会集与 OLS 剩余趋势寿命。

优先问题：

- 哪些资产大类在 OLS 首次识别后仍有更长剩余趋势寿命？
- 是否能用 t 时点之前的数据判断下个月哪些资产大类值得启用？
- 动态资产大类筛选能否在相同 OLS / execution 下稳健优于固定池 benchmark？

默认采用月度 past-only / walk-forward 验证，不使用未来收益反向定义当期候选池。

大型逐日特征和中间矩阵优先输出 Parquet 到 Supabase Storage；数据库只保存轻量摘要和最终选择结果。
