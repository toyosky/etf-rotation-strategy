"""Regression: a dated premium veto must not permanently freeze Top1."""
import unittest
import pandas as pd
from automation.build_live_forward import apply_execution_overrides, ranked_raw_top1

class LiveExecutionModelTest(unittest.TestCase):
    def test_confirmed_veto_is_not_permanent_freeze(self):
        path=pd.DataFrame({
            "signal_date":pd.to_datetime(["2026-09-28","2026-09-29","2026-09-30","2026-10-08","2026-11-06"]),
            "target":["159981","159509","501018","501018","511220"],
            "route_decision":["BASE"]*5,"sides":[0]*5,
        })
        overrides={"baseline":[{
            "signal_date":"2026-09-29","model_target":"159509",
            "final_target":"159981","decision":"VOID_EXIT_BLOCKED_PREMIUM",
            "filter":"PREMIUM10","premium_pct":0.3001,"premium_limit":0.10}]}
        result,audit=apply_execution_overrides(path,"baseline",overrides)
        self.assertEqual(len(audit),1)
        self.assertEqual(result["target"].tolist(),["159981","159981","501018","501018","511220"])
        self.assertEqual(result["execution_status"].iloc[1],"CONFIRMED_OVERRIDE")
        self.assertEqual(result["execution_status"].iloc[2],"MODEL_SWITCH_UNVERIFIED")
        self.assertEqual(result["execution_filter"].iloc[2],"PREMIUM_UNVERIFIED")
        self.assertEqual(result["sides"].tolist(),[1,0,2,0,2])

    def test_raw_top1_excludes_cash(self):
        d=pd.Timestamp("2026-11-12")
        scores=pd.DataFrame({"511220":[0.0],"164824":[2.423169],
                             "513290":[1.618685],"159981":[-0.2]},index=[d])
        self.assertEqual(ranked_raw_top1(scores,d,("164824","513290","159981","511220")),
                         ("164824",2.423169))
        scores.loc[d,["164824","513290"]]=[-1.0,0.0]
        self.assertEqual(ranked_raw_top1(scores,d,("164824","513290","159981","511220")),
                         (None,None))

if __name__=="__main__":
    unittest.main()
