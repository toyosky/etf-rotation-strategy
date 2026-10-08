"""Run with python -m unittest discover -s strategy -p 'test_*.py'. No JQ service needed."""
import importlib.util
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock


class ExecutionProtectionTest(unittest.TestCase):
    def setUp(self):
        sys.modules.setdefault('jqdata', ModuleType('jqdata'))
        # 通知网络调用不属于这些状态/下单测试。
        sys.modules.setdefault('requests', ModuleType('requests'))
        spec = importlib.util.spec_from_file_location('jq_strategy', Path(__file__).with_name('main.py'))
        self.s = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.s)
        s = self.s
        s.g = SimpleNamespace()
        s.log = SimpleNamespace(info=Mock(), warning=Mock())
        s.reset_state()
        self.old = '159981.XSHE'
        self.new = '513100.XSHG'
        self.d = date(2026, 9, 30)
        s.g.pending_rows = [
            {'symbol': self.old, 'score': .244386, 'eligible': True},
            {'symbol': self.new, 'score': .978211, 'eligible': True},
            {'symbol': s.CASH_SIGNAL_SYMBOL, 'score': .036379, 'eligible': True},
        ]
        s.g.pending_signal_date = self.d
        s.g.pending_target = self.new
        s.g.pending_target_actual_close = 100
        self.ctx = SimpleNamespace(current_dt=datetime(2026, 10, 8, 14),
            portfolio=SimpleNamespace(positions={self.old: SimpleNamespace(total_amount=100)}, total_value=20000))
        s.actual_daily_close_on_date = Mock(return_value=100)
        s.current_price = Mock(return_value=(101, None))
        s.get_current_data = Mock(return_value={self.new: SimpleNamespace(last_price=101, paused=False, high_limit=110)})
        s.today_high = Mock(return_value=101)
        s.safe_target_value = Mock(return_value=(object(), None))
        self.fresh(self.new)

    def fresh(self, symbol):
        self.s.g.premium_snapshot[symbol] = {'date': self.d, 'premium': .02, 'blocked': False}
        self.s.g.premium_nav_status[symbol] = {'lag_trade_days': 0, 'no_nav': False}

    def test_lower_limit_reclassifies_already_processed_snapshot(self):
        s = self.s
        s.g.premium_policy_signature = (.15, 2, 0)
        s.g.premium_last_processed_date[self.new] = self.d
        s.g.premium_snapshot[self.new]['premium'] = .1404
        s.ensure_state()
        self.assertIn(self.new, s.g.premium_blacklist)
        self.assertEqual(s.g.premium_last_processed_date[self.new], self.d)

    def test_hot_updates_do_not_increment_recovery(self):
        s = self.s
        s.g.premium_blacklist.add(self.new)
        s.g.premium_policy_signature = (.15, 2, 0)
        s.ensure_state()
        s.ensure_state()
        self.assertIn(self.new, s.g.premium_blacklist)
        self.assertEqual(s.g.premium_recovery_streak[self.new], 0)

    def test_recovery_requires_two_new_confirmations(self):
        s = self.s
        s.g.premium_blacklist.add(self.new)
        s.apply_premium_observation(self.new, self.d, 108, 100)
        self.assertIn(self.new, s.g.premium_blacklist)
        s.apply_premium_observation(self.new, date(2026, 10, 8), 109, 100)
        self.assertNotIn(self.new, s.g.premium_blacklist)

    def test_duplicate_refresh_does_not_count_second_recovery_day(self):
        import pandas as pd
        s = self.s
        s.g.premium_blacklist.add(self.new)
        s.recent_trade_dates = Mock(return_value=[self.d])
        s.unit_nav_frame = Mock(return_value=pd.DataFrame({self.new: [100]}, index=[pd.Timestamp(self.d)]))
        s.actual_daily_close_on_date = Mock(return_value=108)
        s.refresh_premium_blacklist_for_date(self.d)
        s.refresh_premium_blacklist_for_date(self.d)
        self.assertIn(self.new, s.g.premium_blacklist)
        self.assertEqual(s.g.premium_recovery_streak[self.new], 1)

    def test_stale_nav_blocks_entry_without_blacklisting(self):
        s = self.s
        s.g.premium_nav_status[self.new]['lag_trade_days'] = 1
        self.assertIsNotNone(s.premium_entry_block_reason(self.new))
        self.assertNotIn(self.new, s.g.premium_blacklist)
        self.assertEqual(s.execution_veto_fallback(self.ctx, 'stale'), self.old)

    def test_missing_nav_blocks_entry(self):
        self.s.g.premium_snapshot.clear()
        self.assertIsNotNone(self.s.premium_entry_block_reason(self.new))

    def test_missing_gap_check_preserves_valid_old_holding(self):
        self.s.execute_sells_at_1400(self.ctx)
        self.s.safe_target_value.assert_not_called()
        self.assertEqual(self.s.g.v1_current_target, self.old)
        self.assertEqual(self.s.g.last_output_target, self.old)

    def test_paused_challenger_preserves_old(self):
        s = self.s
        s.g.entry_checked = True
        s.current_price = Mock(side_effect=lambda symbol: (None, 'paused') if symbol == self.new else (101, None))
        s.execute_sells_at_1400(self.ctx)
        s.safe_target_value.assert_not_called()
        self.assertEqual(s.g.v1_current_target, self.old)

    def test_invalid_old_holding_is_sold_when_entry_blocked(self):
        s = self.s
        s.g.pending_rows[0]['eligible'] = False
        s.execute_sells_at_1400(self.ctx)
        s.safe_target_value.assert_called_once_with(self.old, 0)
        self.assertIsNone(s.g.v1_current_target)

    def test_old_gap_risk_overrides_preservation(self):
        self.s.current_price = Mock(return_value=(96, None))
        self.s.execute_sells_at_1400(self.ctx)
        self.s.safe_target_value.assert_called_once_with(self.old, 0)

    def test_valid_switch_is_still_executed(self):
        s = self.s
        s.g.entry_checked = True
        s.execute_sells_at_1400(self.ctx)
        s.safe_target_value.assert_called_once_with(self.old, 0)
        self.assertEqual(s.g.pending_buy_target, self.new)

    def test_drawdown_known_before_sell_preserves_old(self):
        s = self.s
        s.g.entry_checked = True
        s.today_high = Mock(return_value=110)
        s.execute_sells_at_1400(self.ctx)
        s.safe_target_value.assert_not_called()
        self.assertEqual(s.g.v1_current_target, self.old)

    def test_void_carrier_failure_routes_to_defensive_asset(self):
        s = self.s
        s.g.pending_rows[0]['eligible'] = False
        s.g.void_in_void = True
        s.g.void_routed = True
        self.assertEqual(s.execution_veto_fallback(self.ctx, 'carrier blocked'), s.CASH_SIGNAL_SYMBOL)
        self.assertEqual(s.g.void_route_target, s.CASH_SIGNAL_SYMBOL)

    def test_equal_threshold_does_not_block_normal_or_recover_blocked(self):
        s = self.s
        s.apply_premium_observation(self.new, self.d, 110, 100)
        self.assertNotIn(self.new, s.g.premium_blacklist)
        s.g.premium_blacklist.add(self.new)
        s.apply_premium_observation(self.new, date(2026, 10, 8), 110, 100)
        self.assertIn(self.new, s.g.premium_blacklist)
        self.assertEqual(s.g.premium_recovery_streak[self.new], 0)

    def test_logged_oct8_case_keeps_actual_incumbent_after_threshold_update(self):
        s = self.s
        s.g.premium_policy_signature = (.15, 2, 0)
        s.g.premium_snapshot[self.new]['premium'] = .1404
        s.g.v1_current_target = self.new  # 上次热更新只改变了虚拟目标，未成交。
        s.g.v1_initialized = True
        s.g.pending_rows_date = self.d
        s.g.last_output_initialized = True
        self.ctx.previous_date = self.d
        s.refresh_premium_blacklist_for_date = Mock()
        s.log_execution_diagnostics = Mock()
        s.g.pending_map_snapshot = {
            'date': self.d, 'quadrant': 'NARROW_LEADERSHIP', 'breadth_pct': 38.46,
            'breadth_count': 5, 'gap_raw': 3.203096, 'gap_percentile': 56.35,
            'top1': '159509.XSHE',
        }
        for row in s.g.pending_rows:
            row.update(annualized=.8943, r_squared=.2733)
        s.ensure_state()
        s.finalize_next_day_plan_before_open(self.ctx)
        self.assertIn(self.new, s.g.premium_blacklist)
        self.assertEqual(s.g.pending_target, self.old)
        self.assertEqual(s.g.v1_current_target, self.old)
        s.safe_target_value.assert_not_called()

    def test_late_buy_failure_clears_virtual_target(self):
        s = self.s
        self.ctx.portfolio.positions = {}
        s.g.v1_current_target = self.new
        s.g.pending_buy_target = self.new
        s.g.premium_nav_status[self.new]['lag_trade_days'] = 1
        s.execute_buy_at_1405(self.ctx)
        s.safe_target_value.assert_not_called()
        self.assertIsNone(s.g.v1_current_target)
        self.assertIsNone(s.g.last_output_target)


if __name__ == '__main__':
    unittest.main()
