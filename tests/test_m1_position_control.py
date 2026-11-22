# -*- coding: utf-8 -*-
"""M1 + Q90 position-control adapter tests without importing JoinQuant."""
import ast
import math
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "strategy" / "main.py").read_text("utf-8")
TREE = ast.parse(SOURCE)
NAMES = {
    "finite_number",
    "m1_clip",
    "m1_compute_sizing",
    "m1_validate_signal_for_target",
    "m1_actual_position_weight",
    "build_m1_position_plan",
    "m1_holding_matches_plan",
    "m1_target_value",
    "execute_m1_weight_sells_at_1400",
    "execute_m1_weight_buy_at_1405",
}
FUNCS = [
    item for item in TREE.body
    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in NAMES
]
assert {item.name for item in FUNCS} == NAMES
CODE = compile(ast.Module(body=FUNCS, type_ignores=[]), str(ROOT / "strategy" / "main.py"), "exec")

ETF = "513100.XSHG"
OTHER = "159529.XSHG"
CASH = "511220.XSHG"
CARRIER = "513500.XSHG"


def valid_signal(symbol=ETF):
    return {
        "date": "2026-11-20",
        "data_asof": "2026-11-20",
        "symbol": symbol,
        "scope": "per_asset_final_target",
        "model_version": "per-asset-oos-v1",
        "q90": 0.08,
        "normal_risk": 0.05,
        "p0": 0.25,
        "p_vol": 0.20,
        "recent_err": 0.04,
        "n_recent": 120,
    }


class FakePortfolio:
    def __init__(self, positions=None, capital=10000):
        self.total_value = capital
        self.positions = {}
        for symbol, value in (positions or {}).items():
            self.positions[symbol] = types.SimpleNamespace(
                value=value, total_amount=1000 if value > 0 else 0
            )


class FakeContext:
    def __init__(self, positions=None, capital=10000):
        self.portfolio = FakePortfolio(positions, capital)


class Tests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.orders = []
        self.g = types.SimpleNamespace(
            void_in_void=False,
            void_routed=False,
            m1_risk_signal=valid_signal(),
            pending_signal_date="2026-11-20",
            pending_target=ETF,
            pending_target_weight=0.64,
            pending_preserve_shares=False,
            pending_preserve_portfolio=False,
            pending_buy_target=None,
            pending_buy_weight=None,
            pending_m1_diagnostics=None,
            entry_checked=True,
            entry_blocked=False,
            entry_reason=None,
        )
        self.env = {
            "g": self.g,
            "np": types.SimpleNamespace(isfinite=math.isfinite),
            "RISK_POOL": [ETF, OTHER],
            "CASH_SIGNAL_SYMBOL": CASH,
            "US_CARRIER_SYMBOL": CARRIER,
            "M1_POSITION_CONTROL_ENABLED": True,
            "M1_LAMBDA": 0.65,
            "M1_MAX_PROBABILITY_CORRECTION": 0.12,
            "M1_MIN_MATURED_SAMPLES": 40,
            "M1_Q90_BASELINE_MULTIPLIER": 1.10,
            "M1_PROBABILITY_MULTIPLIER_SLOPE": 2.0,
            "M1_PROBABILITY_MULTIPLIER_MAX": 1.8,
            "M1_WEIGHT_TOLERANCE": 0.005,
            "INTRADAY_HIGH_DRAWDOWN_LIMIT": 0.02,
            "log": types.SimpleNamespace(
                info=self.logs.append, warning=self.logs.append
            ),
            "managed_holdings": lambda c: [
                s for s, p in c.portfolio.positions.items() if p.total_amount > 0
            ],
            "safe_target_value": lambda s, v: (self.orders.append((s, v)), None),
            "entry_preflight_reason": lambda *a, **kw: None,
            "execution_veto_fallback": lambda *a, **kw: CASH,
            "current_price": lambda symbol: (1.0, None),
            "today_high": lambda *a: 1.0,
            "display": str,
            "clear_pending": self.clear_pending,
        }
        exec(CODE, self.env)

    def clear_pending(self):
        self.logs.append("clear")
        self.g.pending_signal_date = None

    def call(self, name, *args):
        return self.env[name](*args)

    def test_m1_formula_matches_frozen_equation(self):
        result = self.call("m1_compute_sizing", valid_signal())
        self.assertAlmostEqual(result["correction"], 0.026)
        self.assertAlmostEqual(result["p_m1"], 0.276)
        self.assertAlmostEqual(result["base_e"], 0.3125)
        self.assertAlmostEqual(result["probability_multiplier"], 1.152)
        self.assertAlmostEqual(result["e"], 0.36)
        self.assertAlmostEqual(result["target_weight"], 0.64)

    def test_fewer_than_40_matured_samples_falls_back_to_p0(self):
        signal = valid_signal()
        signal["n_recent"] = 39
        signal["recent_err"] = 0.20
        result = self.call("m1_compute_sizing", signal)
        self.assertEqual(result["correction"], 0.0)
        self.assertEqual(result["p_m1"], signal["p0"])

    def test_residual_correction_is_capped_at_12_percentage_points(self):
        signal = valid_signal()
        signal["recent_err"] = 0.80
        result = self.call("m1_compute_sizing", signal)
        self.assertAlmostEqual(result["correction"], 0.12)
        signal["recent_err"] = -0.80
        result = self.call("m1_compute_sizing", signal)
        self.assertAlmostEqual(result["correction"], -0.12)

    def test_invalid_q90_or_probability_rejected(self):
        signal = valid_signal()
        signal["q90"] = 0
        self.assertIsNone(self.call("m1_compute_sizing", signal))
        signal = valid_signal()
        signal["p_vol"] = 1.2
        self.assertIsNone(self.call("m1_compute_sizing", signal))

    def test_signal_requires_exact_date_symbol_scope_and_data_asof(self):
        self.assertIsNotNone(
            self.call("m1_validate_signal_for_target", "2026-11-20", ETF)
        )
        for key, value in [
            ("date", "2026-11-19"),
            ("data_asof", "2026-11-19"),
            ("symbol", OTHER),
            ("scope", "raw_top1_only"),
            ("model_version", ""),
        ]:
            signal = valid_signal()
            signal[key] = value
            self.g.m1_risk_signal = signal
            self.assertIsNone(
                self.call("m1_validate_signal_for_target", "2026-11-20", ETF),
                key,
            )

    def test_final_target_uses_its_own_m1_signal(self):
        context = FakeContext({ETF: 10000})
        plan = self.call(
            "build_m1_position_plan", context, "2026-11-20", ETF, [ETF]
        )
        self.assertEqual(plan[0], ETF)
        self.assertAlmostEqual(plan[1], 0.64)
        self.assertFalse(plan[2])
        self.assertFalse(plan[3])
        self.assertIsNotNone(plan[5])

    def test_missing_signal_does_not_open_new_risk_position(self):
        self.g.m1_risk_signal = None
        plan = self.call(
            "build_m1_position_plan", FakeContext(), "2026-11-20", ETF, []
        )
        self.assertEqual(plan[0], ETF)
        self.assertEqual(plan[1], 0.0)
        self.assertFalse(plan[2])
        self.assertIn("禁止新开", plan[4])

    def test_missing_signal_preserves_existing_same_symbol_shares(self):
        self.g.m1_risk_signal = None
        plan = self.call(
            "build_m1_position_plan",
            FakeContext({ETF: 7000}),
            "2026-11-20",
            ETF,
            [ETF],
        )
        self.assertAlmostEqual(plan[1], 0.70)
        self.assertTrue(plan[2])
        self.assertIn("保持现有份额", plan[4])

    def test_void_freezes_actual_holding_weight_and_ignores_m1(self):
        self.g.void_in_void = True
        self.g.m1_risk_signal = valid_signal()
        plan = self.call(
            "build_m1_position_plan",
            FakeContext({ETF: 7000}),
            "2026-11-20",
            ETF,
            [ETF],
        )
        self.assertEqual(plan[0], ETF)
        self.assertAlmostEqual(plan[1], 0.70)
        self.assertTrue(plan[2])
        self.assertFalse(plan[3])

    def test_void_without_holding_stays_in_cash(self):
        self.g.void_in_void = True
        plan = self.call(
            "build_m1_position_plan", FakeContext(), "2026-11-20", ETF, []
        )
        self.assertIsNone(plan[0])
        self.assertEqual(plan[1], 0.0)
        self.assertTrue(plan[2])

    def test_void_multiple_holdings_freezes_account_and_stops_trading(self):
        self.g.void_in_void = True
        plan = self.call(
            "build_m1_position_plan",
            FakeContext({ETF: 5000, OTHER: 3000}),
            "2026-11-20",
            ETF,
            [ETF, OTHER],
        )
        self.assertTrue(plan[3])
        self.g.pending_preserve_portfolio = True
        self.g.pending_target_weight = 0
        self.call("execute_m1_weight_sells_at_1400", FakeContext({ETF: 5000, OTHER: 3000}))
        self.assertEqual(self.orders, [])

    def test_void_routed_target_keeps_existing_route_weight_policy(self):
        self.g.void_in_void = True
        self.g.void_routed = True
        self.g.m1_risk_signal = None
        plan = self.call(
            "build_m1_position_plan", FakeContext({ETF: 7000}), "2026-11-20", CARRIER, [ETF]
        )
        self.assertEqual(plan[0], CARRIER)
        self.assertEqual(plan[1], 1.0)
        self.assertFalse(plan[2])

    def test_partial_sell_uses_m1_target_value(self):
        context = FakeContext({ETF: 10000})
        self.g.pending_target_weight = 0.64
        self.call("execute_m1_weight_sells_at_1400", context)
        self.assertEqual(self.orders, [(ETF, 6400.0)])
        self.assertEqual(self.g.pending_buy_target, ETF)

    def test_partial_buy_uses_m1_target_value(self):
        context = FakeContext({ETF: 6400})
        self.g.pending_target_weight = 0.80
        self.g.pending_buy_target = ETF
        self.call("execute_m1_weight_buy_at_1405", context)
        self.assertEqual(self.orders, [(ETF, 8000.0)])

    def test_1405_veto_does_not_reverse_prior_reduction(self):
        context = FakeContext({ETF: 6400})
        self.g.pending_target_weight = 0.80
        self.g.pending_buy_target = ETF
        self.env["entry_preflight_reason"] = lambda *a, **kw: "溢价阻止"
        self.call("execute_m1_weight_buy_at_1405", context)
        self.assertEqual(self.orders, [])
        self.assertTrue(any("溢价阻止" in str(x) for x in self.logs))

    def test_old_unfilled_holding_blocks_new_asset_buy(self):
        context = FakeContext({OTHER: 10000})
        self.g.pending_buy_target = ETF
        self.g.pending_target_weight = 0.64
        self.call("execute_m1_weight_buy_at_1405", context)
        self.assertEqual(self.orders, [])
        self.assertTrue(any("旧仓未清" in str(x) for x in self.logs))

    def test_zero_target_weight_never_buys(self):
        self.g.pending_buy_target = ETF
        self.g.pending_target_weight = 0.0
        self.call("execute_m1_weight_buy_at_1405", FakeContext())
        self.assertEqual(self.orders, [])


if __name__ == "__main__":
    unittest.main()
