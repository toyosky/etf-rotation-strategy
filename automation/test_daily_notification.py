import unittest
from automation.notify_rebuild_candidates import build_report

class DailyReportTest(unittest.TestCase):
    def test_ols_and_full_market(self):
        current={"market_data_date":"2026-10-20",
                 "next_strategy_target":{"signal_date":"2026-10-20","model_target":"501018","model_target_name":"原油",
                 "raw_top1_score":2.5,"raw_top1_qualifies_cash":True,
                 "v1_target":"501018","v1_target_name":"原油",
                 "strategy_model_target":"159981","strategy_model_target_name":"能源化工",
                 "symbol":"159981","name":"能源化工"}}
        candidates=[
          {"symbol":"520870","name":"巴西","stage":"REBUILDING_QUALIFIED","first_qualified_date":"2026-10-20","cross_date":"2026-10-19","r2":0.35,"annual":0.30},
          {"symbol":"501090","name":"基金","stage":"REBUILDING_QUALIFIED","first_qualified_date":"2026-10-19","cross_date":"2026-10-18","r2":0.25,"annual":0.20}
        ]
        market={"as_of":"2026-10-20","data_quality_gate":"PASS","listed_requested":1500,
                "asof_coverage":0.95,"symbols_with_asof_close":1425,
                "qualified_candidates":candidates,"raw_qualified":2}
        title,body=build_report({},current,market,premium={
            "symbol":"501018","signal_date":"2026-10-20","premium_pct":None,"reason":"NOT_READY"})
        self.assertIn("固定候选池 OLS 与防御执行",body)
        self.assertIn("原始 OLS 风险资产 Top1：**501018 原油**",body)
        self.assertIn("防御状态调整后目标：**159981 能源化工**",body)
        self.assertIn("501018 原油",body)
        self.assertIn("全市场 R² 趋势重建合格候选",body)
        self.assertIn("520870 巴西",body)
        self.assertIn("501090 基金",body)
        self.assertIn("Premium10：无法计算",body)

    def test_missing_signal_layers_fail_closed(self):
        current={"market_data_date":"2026-11-12",
                 "next_strategy_target":{"signal_date":"2026-11-12","model_target":"511220"}}
        market={"as_of":"2026-11-12","data_quality_gate":"PASS",
                "listed_requested":1500,"asof_coverage":0.95,"symbols_with_asof_close":1425,
                "qualified_candidates":[],"raw_qualified":0}
        with self.assertRaisesRegex(ValueError,"separation"):
            build_report({},current,market)

if __name__=="__main__":
    unittest.main()
