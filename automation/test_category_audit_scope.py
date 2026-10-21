import unittest
from automation.build_category_audit_scope import build, classify


class CategoryAuditScopeTest(unittest.TestCase):
    def test_separate_consumer_baijiu_hk_cashflow(self):
        data=[
            ("501090","消费龙头LOF","2026-10-20"),
            ("159520","消费龙头ETF工银","2026-10-20"),
            ("161725","白酒基金LOF","2026-10-20"),
            ("160632","酒LOF","2026-10-19"),
            ("513970","恒生消费ETF景顺","2026-10-20"),
            ("520520","恒生消费ETF华泰柏瑞","2026-10-20"),
            ("159222","自由现金流ETF易方达","2026-10-20"),
            ("513400","道琼斯ETF鹏华","2026-10-20"),
            ("501300","美元债LOF","2026-10-19"),
        ]
        candidates=[dict(symbol=s,name=n,stage="REBUILDING_QUALIFIED",
                         first_qualified_date=d,cross_date="2026-10-19",
                         r2=0.3,annual=0.2) for s,n,d in data]
        current={"market_data_date":"2026-10-20",
                 "next_strategy_target":{"signal_date":"2026-10-20",
                    "model_target":"501018","model_target_name":"南方原油LOF","symbol":"159981"}}
        market={"as_of":"2026-10-20","data_quality_gate":"PASS","asof_coverage":0.97,
                "raw_qualified":len(candidates),"qualified_candidates":candidates}
        metadata={"161725":{"region_primary":"CN","exposure_level2":"CONSUMER",
                             "needs_review":False,"confidence":0.82},
                  "520520":{"region_primary":"HK","exposure_level2":"HK_BROAD",
                            "needs_review":False,"confidence":0.82},
                  "501300":{"region_primary":"CN","exposure_level1":"CHINA_EQUITY",
                            "exposure_level2":"CHINA_EQUITY_OTHER",
                            "needs_review":True,"confidence":0.65}}
        out=build(current,market,metadata,{"status":"CASH","as_of":"2026-10-20"})
        self.assertEqual(out["all_market_rebuild_count"],9)
        self.assertEqual(out["unique_symbols"],10)
        groups={row["category_id"]:row for row in out["categories"]}
        self.assertEqual(groups["CN_CONSUMER"]["count"],2)
        self.assertEqual(groups["CN_BAIJIU"]["count"],2)
        self.assertEqual(groups["HK_CONSUMER"]["count"],2)
        self.assertEqual(groups["CN_CASHFLOW_FACTOR"]["count"],1)
        self.assertEqual(groups["CRUDE_OIL"]["ols_top1"],"501018")
        self.assertTrue(groups["US_BONDS"]["needs_review"])
        self.assertEqual(sum(x["count"] for x in out["categories"]),10)
        self.assertEqual(out["new_rebuild_count"],7)

    def test_no_silent_other_bucket(self):
        a=classify("588999","未分类主题ETF",{})
        b=classify("589000","另一个未知ETF",{})
        self.assertNotEqual(a["key"],b["key"])
        self.assertTrue(a["needs_review"])

    def test_fail_closed_on_stale_snapshot(self):
        current={"market_data_date":"2026-10-20",
                 "next_strategy_target":{"signal_date":"2026-10-20","model_target":"501018"}}
        market={"as_of":"2026-10-19","data_quality_gate":"PASS",
                "asof_coverage":0.96,"raw_qualified":0,"qualified_candidates":[]}
        with self.assertRaises(ValueError):
            build(current,market,{})


if __name__=="__main__":
    unittest.main()
