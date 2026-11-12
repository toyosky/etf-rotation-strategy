#!/usr/bin/env python3
"""Independent consistency and estimand audit of archived V2 research JSON.

This script does not refit parameters or claim a tradable signal.
Run: python research/taxonomy_v3/audit_v2_consistency_v1.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "output_v32/drawdown_rebuild_exact_uncensored_v2.json"
REPORT = ROOT / "output_v32/drawdown_rebuild_v2_consistency_audit.md"

def main():
    z = json.loads(DATA.read_text(encoding="utf-8"))
    s, c = z["stats"], z["censoring"]
    assert c["all_events_before_censor"] == (c["calendar_censored_n"] +
        c["missing_future_quotes_n"] + c["mature_valid_n"])
    assert s["TRAIN"]["episodes"] + s["VALID"]["episodes"] == c["mature_valid_n"]
    assert s["2025"]["episodes"] + s["2026"]["episodes"] == s["VALID"]["episodes"]
    for name, v in s.items():
        assert v["episodes"] == v["already_in_confirmed_rebuild"] + v["new_rebuild_eligible_episodes"], name
        assert 0 <= v["new_rebuild_within20"] <= v["new_rebuild_eligible_episodes"], name
        assert abs(v["new_rebuild_within20_pct"] -
            100*v["new_rebuild_within20"]/v["new_rebuild_eligible_episodes"]) < .011, name
        assert v["d10_n"] == v["episodes"], name
    assert s["2025"]["new_rebuild_within20"] + s["2026"]["new_rebuild_within20"] == s["VALID"]["new_rebuild_within20"]
    p25=s["2025"]["new_rebuild_within20_pct"]
    p26=s["2026"]["new_rebuild_within20_pct"]
    diff=round(p25-p26,2)
    assert diff == 35.06
    # A V2 signal-detection statistic is NOT a trading return or an early warning hit rate.
    # Its 20-day future outcome cannot condition an entry on the event date.
    lines=[
        "# V2独立一致性与估计对象审计", "",
        "数据源：drawdown_rebuild_exact_uncensored_v2.json；仅审计已归档汇总，不重新读取行情。", "",
        "## 可复核检查",
        f"- 事件守恒：{c['all_events_before_censor']} = {c['calendar_censored_n']} 时间删失 + {c['missing_future_quotes_n']} 报价缺失 + {c['mature_valid_n']} 成熟事件，PASS。",
        f"- 训练/验证：{s['TRAIN']['episodes']} + {s['VALID']['episodes']} = {c['mature_valid_n']}，PASS。",
        f"- 验证年度：{s['2025']['episodes']} + {s['2026']['episodes']} = {s['VALID']['episodes']}，PASS。",
        "- 各组事前已有确认与新重建合格分母守恒，计数、百分比和10日收益样本量一致，PASS。",
        f"- 2025新重建检测率{p25:.2f}%，2026为{p26:.2f}%，相差{diff:.2f}个百分点。此为描述性差异，未建立差异的联合置信区间。", "",
        "## 尚未解决的估计对象问题", "",
        "1. 新重建检测率的分母是可观测超跌修复事件且事前未确认者，不能当作原OLS对全部真实超跌反弹的召回率；仍缺独立的反弹真值定义。",
        "2. 修复触发日后的20日内是否重建是未来结果；以此分组的10日收益有未来信息，绝不可作为当日交易筛选。",
        "3. 当前确认延迟从已触发5日反弹条件的日子计算，不是从事后最低价，也不是反弹的真正起点；需要短周期预警与同样严格的当时可知基准。",
        "4. 2025与2026的宏观/行业暴露、上市ETF集合与同日相关性不同，35.06个百分点差距不能归因于市场状态或机制失效。",
        "5. 月份区块区间仅针对各年度检测率；2025仅9个月、2026仅10个月，且基金之间同日相关。需要共同月份/状态控制与联合重采样。",
        "6. V2基于2026年静态分类、只覆盖有合格历史的现存基金；无法作为PIT策略收益。",
        "7. 报告中的D10是修复触发后收益，并非OLS确认后收益；两者的收益对比必须以各自信号的下一开盘统一计算。",
        "",
        "## 结论与下一实验",
        "本轮只确认归档统计内部一致、检测率年际差异显著可见（描述性），不证明OLS存在正alpha。",
        "下一步在同一事件集合上保存逐事件的as-of特征、确认日、未来收益和删失标记，采用时间块配对，比较短周期预警与26日确认的真实入场时点；先冻结规则再验证。",
        "不得修改main、实盘任务或持仓。", ""
    ]
    REPORT.write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
