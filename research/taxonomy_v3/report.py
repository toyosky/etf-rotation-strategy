"""Render the research audit from the frozen, validated V3 build."""
from pathlib import Path
import json


def main():
    root=Path(__file__).parent
    out=root/'output'
    s=json.loads((out/'summary.json').read_text())
    audit=json.loads((out/'quality_audit.json').read_text())
    rows=json.loads((out/'classifications.json').read_text())
    accepted=[r for r in rows if not r['needs_review']]
    d=s['dedup_comparison']
    lines=['# ETF/LOF 经济暴露分类 V3：实际审计与交付（2026-11-12）','',
    '**这是已执行的独立研究分支及部分核实成果，不是全市场历史无前视分类已经完成。** 生产元数据、正式 OLS、持仓和定时任务均未改动。', '',
    '## A. 当前真实状态与分类覆盖','',
    '| 口径 | 数量 |', '|---|---:|',
    f"| Supabase 当前元数据视图基金数 | {s['legacy_current_count']} |",
    '| 原元数据标记当前上市 / 有历史行情 | 1,988 / 1,090 |',
    '| 原元数据待复核 / 非待复核 | 424 / 1,602 |',
    '| 原 underlying_key / risk_bucket 覆盖率 | 100% / 100% |',
    '| 原 style_sector 覆盖率 | 1,585 / 2,026 = 78.23% |',
    '| 当前生产日线库实际 ETF / LOF | 16 / 3 |',
    '| 当前生产日线实际行数 | 33,091 |',
    f"| 两交易所现行官方 ETF/LOF 清单 | {s['official_current_listed']}（ETF 1,720；LOF 403） |",
    f"| 审计全集（旧元数据、现行官方清单、行情并集） | {s['total_funds']} |",
    f"| 已取得官方完整跟踪指数名称或官方代码—全称链接 | {s['official_full_name_count']} / {s['total_funds']} = {100*s['official_full_name_count']/s['total_funds']:.2f}% |",
    f"| 另有官方拟合代码、名称链接仍待核实的 ETF | {s['officially_verified_index_identity']-s['official_full_name_count']} |",
    f"| 官方指数名称或拟合代码身份合计 | {s['officially_verified_index_identity']}（{s['officially_verified_index_identity_pct']}%） |",
    f"| 已通过当前分类检查的基金（尚非交易批准） | {s['fully_classified_current']} |",
    f"| 上述通过检查集合的精确指数 / 保守细分暴露组 | {s['exact_index_groups']} / {s['fine_exposure_groups']} |",
    f"| 上述集合的一级 / 二级标签种类 | {len({r['sector_level1'] for r in accepted})} / {len({r['sector_level2'] for r in accepted})} |",
    '| 三级行业 | 0；本轮没有足够证据填充，保留空值 |',
    f"| 待复核基金 | {s['needs_review']} |",
    f"| 无已核实 ETF 跟踪身份（含非指数/待证实 LOF） | {s['no_verified_tracking_identity']} |",
    f"| 已完成交易机制核验 / 采集日前历史分类 | {s['execution_verified_count']} / 0 |", '',
    '“字段填满”不等于“有证据”。旧版 1,602 只非待复核基金并非 1,602 只官方指数核实完成。旧元数据最近更新时间停留在 2026-09-11；生产库保留 19 只与旧 has_daily_bars 标志不是同一个口径。当前实际可交易数还需要停牌及执行证据，不能等同于上市数。', '',
    f"官方身份候选共有 {s['official_identity_candidate_groups']} 个键、初步细分描述 {s['provisional_fine_exposure_groups']} 组；其中包含代码—名称桥接未解决、经济属性未核实或增强策略。**它们不是已批准的独立经济机会数量。** 通过检查的 {s['fine_exposure_groups']} 组采用每个已核实指数单独保留的保守处理；尚未证明所有不同指数的经济驱动完全独立，也未批准任何跨指数合并。", '',
    '一级/二级标签来自已取得证据的底层指数名称所明确表达的范围，属于描述层；未逐一完成所有指数编制规则及持仓穿透审阅。光伏、电池、新能源保留产业链描述，不擅自断言均为设备股；综合医疗不硬贴纯器械或纯医疗服务，创新药产业不硬贴纯 CXO。未知范围进入复核。', '',
    '## B. 去重口径与真实映射','',
    f"行情文件实际读取 {s['archive_rows']:,} 行、{s['archive_symbols']} 只，日期 {s['archive_min_date']} 至 {s['archive_max_date']}；重复 symbol/date 为 {s['archive_duplicate_symbol_dates']}。Release 文件 SHA-256：`{s['archive_sha256']}`。", '',
    '| 步骤 | 基金或分组数 |', '|---|---:|',
    f"| 原始全量行情基金 | {d['raw_archive_symbols']} |",
    f"| 其中取得官方名称或拟合代码身份 | {d['verified_archive_symbols']} |",
    f"| 其中当前分类通过检查、可用于同口径映射对比 | {d['approved_archive_symbols']} |",
    f"| 在这 {d['approved_archive_symbols']} 只内精确指数去重 | {d['exact_index_groups']} |",
    f"| 在同一集合内细分经济暴露去重 | {d['fine_exposure_groups']} |",
    f"| 在同一集合内按区域 × 资产类型 × 一级标签唯一 | {d['broad_sector_groups']} |", '',
    f"原始 {d['raw_archive_symbols']} 只到通过检查的 {d['approved_archive_symbols']} 只之间，{d['raw_archive_symbols']-d['approved_archive_symbols']} 只是证据/分类排除，**不是去重节省**。一级唯一只用于说明粗粒度压缩程度，不作为默认研究池。精确与细分结果相同是因为本轮没有证据支持跨指数等价合并。", '',
    '| 基金 | 真实指数 / 待核实参考 | 精确键 | 细分描述 | 状态 |', '|---|---|---|---|---|']
    for symbol in ['510300','510330','510500','512010','512170','512290','516060','159883','588000','588130','512690','512480','159502','513290','159981','162719','501018']:
        r=next(x for x in rows if x['symbol']==symbol)
        name=r['index_name'] or r.get('auxiliary_index_name') or '无已核实跟踪指数'
        lines.append(f"| {symbol} {r['name']} | {name} | {r['exact_index_key'] or '—'} | {r['sector_level2'] or '待核实'} | {'待复核' if r['needs_review'] else '当前分类通过'} |")
    lines += ['',
    '沪深300 采用已核实的 000300/399300 代码别名，510300 和 510330 共享精确键；中证500 的 000905/399905 同样统一。增强基金可共享参考指数身份，但增强策略不因此与被动基金共享最终策略暴露，保留待核实。', '',
    '159883 的 H30217 来自深交所，当前全称来自辅助资料，尚缺官方代码—全称桥接，因此不能把它悄悄并入上交所同名称组。此类重复风险记录于 identity_review.json 和 quality_audit.json，全部排除于通过检查集合。162719、501018 等 LOF 不用业绩比较基准冒充法定跟踪指数；本轮不依据旧标签宣布它们的策略已经核实。', '',
    '## C. 分类质量审计与历史影响','',
    '| 旧粗粒度 underlying_key | 已找到官方身份的基金 | V3 候选键（含待核实桥接） | 已有官方名称/链接支持的不同指数组 |', '|---|---:|---:|---:|']
    for key in ['CHINA_HEALTHCARE','STAR_MARKET','CHINA_CONSUMER','CHINA_NEW_ENERGY','HK_BROAD']:
        g=next(x for x in audit['legacy_false_merges'] if x['legacy_underlying_key']==key)
        lines.append(f"| {key} | {len(g['funds'])} | {g['exact_indices']} | {g['proven_official_index_groups']} |")
    lines += ['',
    f"全量差异中有 {len(audit['legacy_false_merges'])} 个旧键跨多个 V3 身份候选键，其中 {sum(x['proven_official_index_groups']>1 for x in audit['legacy_false_merges'])} 个已由多个官方名称/链接证实不是单一指数。反向审计发现 {sum(x['assessment']=='SAME_INDEX_SPLIT_REPAIR' for x in audit['legacy_false_splits'])} 个可修复的同指数旧键拆分组，另有 {sum(x['assessment']=='RETAIN_STRATEGY_DIFFERENCES' for x in audit['legacy_false_splits'])} 组涉及策略差异，不当作纯错误删掉。仍有 {len(audit['unresolved_code_name_bridges'])} 个名称存在多个候选精确键，等待官方桥接。", '',
    '- 综合医药、医疗混合、创新药、生物医药、器械、科创生物医药、境外生物科技保留不同指数身份，不能统一压成 HEALTHCARE。',
    '- 科创板宽基与科创生物医药不再共享 STAR_MARKET 最终身份。港股金融、汽车、医疗也不能作为 HK_BROAD 的同指数基金。',
    '- 白酒、酒、食品饮料、家电、消费电子保留各自真实指数；新能源产业链不与原油期货或油气生产企业股票直接合组。',
    '- 旧 public.instrument_metadata 有 2,064 行，当前视图 2,026 只；511220、511380 各有两条有效期重叠记录。原表唯一约束仅约束 symbol/valid_from，不能阻止不同起点的区间重叠。V3 半开区间验证会拒绝这种输入。',
    '- 旧 historical_safe=true 仅 17 只，代码常以首根行情作为 valid_from，缺少逐期官方文件证明；这些标志不自动继承到 V3。',
    '- 159925 的归档首根行情是 1998-04-07，当前官方上市日期为 2013-04-11。可能涉及转型前身或源数据历史拼接，需核实；不以首根行情证明当前产品/指数历史，代表选择不计上市日前历史。',
    '- compute_indicators_v1.metadata 未按交易日期和有效期匹配，直接按 symbol 去重；build_representatives 先构造依赖信号相关条件的基金日样本，再按包含当天的成交额选择。audit_universe_dedup_v1 虽滞后一行成交额，但复用的是过滤后日期序列，上一行未必是上一交易日，资格过滤本身仍用当天数据。两者都不能视为严格历史代表池。原研究程序本次未修改。', '',
    '复核原因（基金可同时有多个原因，因此不可相加当基金数）：','',
    '| 原因 | 基金数 |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in sorted(s['review_reasons'].items())]
    lines += ['',
    '## D. 时间接口、代表选择和限制','',
    '`model.classifications_at(records, date)` 返回当时有效且已知、上市证据有效、被动策略已核实的分类与逐基金排除原因。V3 使用 `[valid_from, valid_to)`，known_from 独立于有效期。当前快照 valid_from=2026-11-12、known_from=2026-11-13；资料发布日期未知时 source_date=NULL，不用抓取日期假装公告日期。', '',
    '`representatives.select_representatives(classifications, bars, calendar, date, policy, risk_observations)` 返回 eligible、representatives、excluded、data_through。必须在任何 OLS 信号/候选排名之前调用；未入选的基金即使当天产生更高 OLS，也不替代代表。输入收益、OLS 列会被忽略。', '',
    '- 显式交易所日历决定上一交易日；滚动窗口不使用删掉不合格日期后压缩的基金时间轴。默认 60 个已完成交易日平均成交额、200 根上市后有效历史、最近 10 日有效价量，最低平均成交额 300 万。按成交额、历史长度、代码确定唯一代表。',
    '- 上一交易日缺失/停牌、异常 OHLC、窗口缺失、不可知行情、已知停牌公告均拒绝或排除；不会回退到更早的最后一根行情。当前/未来的成交额、收益和重复行情不能影响过去选择。',
    '- 溢价敏感产品要求上一交易日观测且决策时已公布的溢价；默认绝对值上限 3%。可选跟踪误差上限要求有可靠、当时可知的数据；缺失不会编成零。',
    '- quote_currency、settlement_mechanism、replication_method 尚未逐只核实，留空。所有 execution_attributes_verified=false，因此本轮没有宣称任何实际基金已获得完整执行批准。人工补证后可生成审核过的分类文件供接口使用；分类检查通过不等同可交易。',
    '- 若后续加入历史合同，需要建立真实版本区间并保留原始来源、公布日期及 known_from，不能把当前快照改个日期后回填。当前构建器只采集现行清单和快照，**尚未实现全市场历次合同/指数更换公告的自动抽取**。时间匹配接口支持多段历史，但历史数据还需补证。',
    '- OLS 特征计算还必须检查整个特征窗口的分类/策略连续性；本轮没有接入正式 OLS。过去未披露的分类、复权/回补价格、退市基金缺失等问题仍可能阻止严格无前视回测。', '',
    '真实接口检查覆盖 2021-01-04、2025-01-02、2026-11-11：每次代表 0、排除 2,147 只，原因是当前证据尚未生效。这验证了拒绝历史回填的边界，**不是策略回测结果**。测试用例验证了在资料齐全的模拟输入下可正常选出唯一代表。', '',
    '## E. 执行、证据与复现','',
    '- Supabase 全程 SELECT；完整元数据导出、当前覆盖摘要、重叠记录、实际结构及 Storage 对象清单位于 snapshot/。没有覆盖既有表，因此无需数据库回滚。若未来替换生产表，应另行备份、生成 diff、验证及准备恢复脚本，本分支不自动执行此动作。',
    '- 两交易所、上证和国证官方 JSON 响应保存在 snapshot/official/；辅助基金资料 facts、URL、观测时刻和原响应 SHA-256 位于 output/profiles.json。原始 HTML gzip 与完整请求缓存另存证据归档。辅助信息不能自动升级为官方证据。',
    '- 全市场历史价格实际下载自 GitHub Release research-data-fullmarket-current，已与仓库 data/full-market-rebuild-latest.json 的哈希核对。Supabase Storage 查得 57 个归档对象，其中包括 frozen_20260917 原始分年归档；本次实际读取验证的是 GitHub 更新快照，不把 Storage 对象清单当作其内容已全部下载校验。',
    '- 分类文件提供 JSON、CSV、Parquet；manifest.json 记录输入、代码、别名配置和各产物 SHA-256。运行方法与接口示例见 README.md。没有新增定时任务。',
    '- 代码测试、实际产物验证和重复构建结果见 output/validation.json 与 output/execution_checks.json；报告不会将未执行项目写成通过。', '',
    '优先待办：补官方代码—全称桥接；取得历史基金合同和更换指数/转型公告；核实 LOF 法定策略；补交易币种、结算与溢价公布时点证据；逐指数审阅编制规则，才考虑跨指数经济等价合并。当前数据适合审计和后续补证，不应直接替代正式历史研究池。', '']
    (root/'REPORT_20261112.md').write_text('\n'.join(lines))


if __name__=='__main__':
    main()
