# -*- coding: utf-8 -*-
"""Q90 weight adapter smoke tests without jqdata; unittest + AST extraction.

Tests only extracted pure helpers/execution adapters to avoid importing jqdata in CI.
Production feature flag remains False until signal feed, fill reconciliation and
intraday execution are separately audited.
"""
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
    "q90_actual_position_weight",
    "q90_validate_signal_for_target",
    "build_q90_position_plan",
    "q90_holding_matches_plan",
    "q90_target_value",
    "execute_weight_sells_at_1400",
    "execute_weight_buy_at_1405",
}
FUNCS = [item for item in TREE.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in NAMES]
assert {x.name for x in FUNCS} == NAMES
CODE = compile(ast.Module(body=FUNCS, type_ignores=[]), str(ROOT / "strategy" / "main.py"), "exec")
ETF = "513100.XSHG"
OTHER = "159529.XSHE"


class FakePortfolio:
    def __init__(self, holding=10000, symbol=ETF, capital=10000):
        self.total_value = capital
        self.positions = {}
        if holding:
            self.positions[symbol] = types.SimpleNamespace(value=holding, total_amount=1000)


class FakeContext:
    def __init__(self, holding=10000, symbol=ETF):
        self.portfolio = FakePortfolio(holding, symbol)


class Tests(unittest.TestCase):
    def setUp(self):
        self.log = []
        self.orders = []
        self.g = types.SimpleNamespace(
            void_in_void=False, void_routed=False,
            q90_signal={"date": "2026-11-20", "symbol": ETF, "E": 0.3},
            pending_signal_date="2026-11-20",
            pending_target=ETF, pending_target_weight=0.7,
            pending_preserve_shares=False, pending_buy_target=None,
            pending_buy_weight=None, entry_checked=True, entry_blocked=False,
            entry_reason="",
        )
        self.env = {
            "g": self.g, "np": types.SimpleNamespace(isfinite=math.isfinite),
            "RISK_POOL": {ETF, OTHER}, "CASH_SIGNAL_SYMBOL": "511220.XSHG",
            "Q90_SIZING_ENABLED": True,
            "Q90_MIN_E": 0.05, "Q90_CHANGE_BAND": 0.05,
            "Q90_WEIGHT_TOLERANCE": 0.005,
            "log": types.SimpleNamespace(info=self.log.append, warning=self.log.append),
            "managed_holdings": lambda c: [
                s for s, p in c.portfolio.positions.items() if p.total_amount > 0
            ],
            "safe_target_value": lambda s, v: (self.orders.append((s, v)), None),
            "entry_preflight_reason": lambda *a, **kw: None,
            "execution_veto_fallback": lambda *a, **kw: OTHER,
            "current_price": lambda sym: (1.0, None),
            "today_high": lambda *a: 1.0,
            "display": str,
            "INTRADAY_HIGH_DRAWDOWN_LIMIT": 0.02,
            "clear_pending": lambda: self.log.append("clear"),
        }
        exec(CODE, self.env)

    def call(self, name, *args):
        return self.env[name](*args)

    def test_final_symbol_same_pit_signal_sized(self):
        context = FakeContext()
        self.assertEqual(
            self.call("build_q90_position_plan", context, "2026-11-20", ETF, [ETF]),
            (0.7, False, "Q90同资产双向目标仓位"),
        )

    def test_v1_veto_forecast_cannot_be_reused(self):
        context = FakeContext(7000, symbol=ETF)
        self.g.q90_signal["symbol"] = OTHER
        weight, preserve, reason = self.call(
            "build_q90_position_plan", context, "2026-11-20", ETF, [ETF])
        self.assertAlmostEqual(weight, 0.7)
        self.assertTrue(preserve)
        self.assertIn("缺同资产Q90", reason)
        self.assertIsNone(self.call("q90_validate_signal_for_target", "2026-11-20", ETF))

    def test_stale_forecast_rejected(self):
        self.g.q90_signal["date"] = "2026-11-19"
        self.assertIsNone(self.call("q90_validate_signal_for_target", "2026-11-20", ETF))

    def test_void_freeze_keeps_existing_position(self):
        self.g.void_in_void = True
        self.g.q90_signal["E"] = 0.0
        weight, preserve, reason = self.call(
            "build_q90_position_plan", FakeContext(7000), "2026-11-20", ETF, [ETF])
        self.assertAlmostEqual(weight, 0.7)
        self.assertTrue(preserve)
        self.assertIn("Void冻结", reason)

    def test_void_routed_to_bond_ignores_q90(self):
        self.g.void_in_void = True
        self.g.void_routed = True
        w, preserve, reason = self.call(
            "build_q90_position_plan", FakeContext(), "2026-11-20", "511220.XSHG", [ETF])
        self.assertEqual(w, 1.0)
        self.assertFalse(preserve)

    def test_weight_match_not_symbol_only(self):
        context = FakeContext(7000)
        self.g.pending_target_weight = 0.9
        self.assertFalse(self.call("q90_holding_matches_plan", context, ETF))
        self.g.pending_target_weight = 0.7
        self.assertTrue(self.call("q90_holding_matches_plan", context, ETF))

    def test_partial_sell_calls_target_value_not_zero(self):
        context = FakeContext()
        self.call("execute_weight_sells_at_1400", context)
        self.assertEqual(self.orders, [(ETF, 7000.0)])
        self.assertEqual(self.g.pending_buy_target, ETF)

    def test_partial_buy_to_weight(self):
        context = FakeContext(7000)
        self.g.pending_target_weight = 0.9
        self.g.pending_buy_target = ETF
        self.call("execute_weight_buy_at_1405", context)
        self.assertEqual(self.orders, [(ETF, 9000.0)])

    def test_partial_buy_veto_never_unwinds_prior_reduction(self):
        context = FakeContext(7000)
        self.g.pending_target_weight = 0.9
        self.g.pending_buy_target = ETF
        self.env["entry_preflight_reason"] = lambda *a, **kw: "溢价阻止"
        self.call("execute_weight_buy_at_1405", context)
        self.assertEqual(self.orders, [])
        self.assertTrue(any("溢价阻止" in str(x) for x in self.log))

    def test_0931_buy_veto_persists_at_1405(self):
        context = FakeContext(7000)
        self.g.pending_target_weight = 0.9
        self.g.pending_buy_target = ETF
        self.g.entry_blocked = True
        self.g.entry_reason = "09:31跳空保护"
        self.call("execute_weight_buy_at_1405", context)
        self.assertEqual(self.orders, [])

    def test_void_freeze_no_order(self):
        context = FakeContext(7000)
        self.g.pending_target_weight = 0.7
        self.g.pending_preserve_shares = True
        self.call("execute_weight_sells_at_1400", context)
        self.assertEqual(self.orders, [])

    def test_full_cash_sells_old(self):
        context = FakeContext()
        self.g.pending_target = None
        self.g.pending_target_weight = 0
        self.call("execute_weight_sells_at_1400", context)
        self.assertEqual(self.orders, [(ETF, 0)])


if __name__ == "__main__":
    unittest.main()
