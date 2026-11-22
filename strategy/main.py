# -*- coding: utf-8 -*-
"""FixV2 + V1(75) + Void Route Baseline v1 + S1日内执行 + 10%溢价执行保护。

这是2026-09-17冻结后的聚宽执行版。核心研究逻辑与GitHub冻结基线保持一致：

一、正常状态：FixV2 + V1(75)
- 固定14只风险资产（新增512800银行ETF）与511220现金比较器；
- 26日加权log-price OLS，名义半衰期10日（np.polyfit的w²为实际损失权重）；
- 风险Top1只有在自身趋势合格且score高于511220时才成为基础目标，否则基础目标为现金；
- V1仅抑制“纯排名换帅”：新Top1的ResistancePct252 >= 75%，且当日raw score增量 <= 0时，
  暂不换帅；若旧仓已经失效，则V1不得阻止切换。

二、State Map（只用raw OLS，不套recent_drop3/溢价）
- Breadth = 14只风险资产中 raw score > 511220 raw score 的比例，固定分母14；
- Leadership Gap = raw Top1 - raw Top2；
- Gap Percentile = Gap在截至当日最近252个有效交易日中的历史分位；
- Breadth < 50% 且 Gap Percentile < 50% => DEFENSIVE_VOID。

三、Void Route Baseline v1（冻结规则，不再样本内寻优）
- 首次进入DEFENSIVE_VOID：冻结进入前“实际策略输出target”，不接受Void当日的新换帅；
- Deepen1：Void内 Breadth 与 Gap Percentile 同时低于该次Void进入日水平，即记1次深化；
- frozen incumbent只有在 raw score <= 511220 raw score（或raw score不可用）时才算失效；
- 只有“Deepen1 + incumbent失效”同时成立才允许路由：
    * 513500上市满365日、raw score > 511220，且未被10%溢价执行保护阻断 -> 513500；
    * 否则 -> 511220；
- 一旦路由，在本次Void结束前保持route target；Void退出后恢复正常V1。

四、执行层保留原实盘约束
- T日收盘冻结评分；T+1开盘前补处理单位净值并形成最终目标；
- 10%溢价状态机继续作为“执行保护”，511220不参与溢价过滤；
- 09:31检查跳空/旧仓急跌，14:00卖出，14:05检查日内高点回撤后买入；
- 普通现金状态为真正空仓；Void失效后的511220路由则实际持有511220。

重要：
- 旧C2两日确认与动态C2 veto已退出主策略，避免形成未经验证的“C2 + Void”叠加版本。
- 513500只作为Void失败后的跨池Carrier，不参与FixV2日常Top1竞争。

五、M1 + Q90动态仓位适配器（默认关闭）
- 正常市场按最终可执行ETF的同日、同标的Q90与M1概率信号计算目标仓位；
- Void未路由时冻结账户实际份额与现金，暂停M1调仓；
- Void防御路由优先于M1，沿用原513500/511220路由；
- 缺少有效同标的预测时，不把缺失数据解释为零风险：旧仓保持份额，新风险标的禁止新开仓；
- M1_POSITION_CONTROL_ENABLED=False，生产级逐ETF预测流水线和执行验收完成前不得开启。
"""

import json
import math
import time

import numpy as np
import requests
from jqdata import *


STRATEGY_ID = "FIXV2_V1_75_VOID_ROUTE_BANK14_INTRADAY_S1_PREMIUM10"
PUSHPLUS_TOKEN = ""
PUSHPLUS_URL = "https://www.pushplus.plus/send"
PUSHPLUS_SEND_IN_BACKTEST = False
PUSHPLUS_CONNECT_TIMEOUT = 4
PUSHPLUS_READ_TIMEOUT = 10
PUSHPLUS_MAX_ATTEMPTS = 3
PUSHPLUS_RETRY_DELAYS = [2, 5]

# 正式OLS：26根日线；polyfit传入q后实际损失权重为q²。
LOOKBACK_DAYS = 25
NOMINAL_HALF_LIFE = 10.0
ANNUALIZATION = 250.0
DAILY_DROP_FLOOR = 0.97
HISTORY_COUNT = 80

CASH_SIGNAL_SYMBOL = "511220.XSHG"
US_CARRIER_SYMBOL = "513500.XSHG"

RISK_POOL = [
    "159934.XSHE", "159985.XSHE", "161226.XSHE", "513100.XSHG",
    "159957.XSHE", "159509.XSHE", "513290.XSHG", "159529.XSHE",
    "159981.XSHE", "501018.XSHG", "513530.XSHG", "511380.XSHG",
    "164824.XSHE", "512800.XSHG",
]
ETF_POOL = RISK_POOL + [CASH_SIGNAL_SYMBOL]
MANAGED_POOL = ETF_POOL + [US_CARRIER_SYMBOL]

ETF_NAMES = {
    "159934.XSHE": "黄金ETF",
    "159985.XSHE": "豆粕ETF",
    "161226.XSHE": "白银LOF",
    "513100.XSHG": "纳指ETF",
    "159957.XSHE": "创业板ETF",
    "159509.XSHE": "纳指科技ETF",
    "513290.XSHG": "纳指生物ETF",
    "159529.XSHG": "标普消费ETF",
    "159981.XSHE": "能源化工期货ETF",
    "501018.XSHG": "南方原油LOF",
    "513530.XSHG": "港股红利ETF",
    "511380.XSHG": "转债ETF",
    "164824.XSHE": "印度基金LOF",
    "512800.XSHG": "银行ETF华宝",
    "511220.XSHG": "城投债ETF（现金比较器/防守路由）",
    "513500.XSHG": "标普500ETF（US Carrier）",
}

# V1：120日成交额阻力画像；对严格先前252个画像做PIT分位，至少60个历史画像。
V1_RES_LOOKBACK = 120
V1_PCT_LOOKBACK = 252
V1_MIN_PROFILE_HISTORY = 60
V1_RES_PCT_THRESHOLD = 75.0
V1_PROFILE_FETCH_BARS = V1_RES_LOOKBACK + V1_PCT_LOOKBACK + 12

# State Map
MAP_GAP_LOOKBACK = 252
MAP_BREADTH_THRESHOLD = 50.0
MAP_GAP_THRESHOLD = 50.0
MAP_BOOTSTRAP_BARS = LOOKBACK_DAYS + MAP_GAP_LOOKBACK   # 25 + 252 = 277
MAP_RESTORE_BARS = 380   # 热更新时恢复当前连续Void episode，确保尾部有完整252日Gap历史
MAP_RESTORE_TAIL_DAYS = 80
VOID_DEEPEN_STREAK_REQUIRED = 1

# US Carrier
CARRIER_MIN_LISTING_DAYS = 365

# 开盘前补处理最近已发布的单位净值；净值必须和同日未复权收盘价配对。
PREMIUM_LIMIT = 0.10
PREMIUM_RECOVERY_DAYS = 2
PREMIUM_NAV_LOOKBACK_TRADE_DAYS = 15
PREMIUM_STATE_VERSION = 3
# 新买入必须有信号日的同日净值/收盘配对；不把滞后数据当作实时溢价。
PREMIUM_MAX_ENTRY_LAG = 0
RANK_LOG_TOP_N = 3
PREMIUM_MONITOR_POOL = list(RISK_POOL) + [US_CARRIER_SYMBOL]

# S1日内执行层
NEXT_DAY_PRICE_FLOOR = 0.97
INTRADAY_HIGH_DRAWDOWN_LIMIT = 0.02
INTRADAY_MINUTE_BAR_COUNT = 260

# M1 dynamic position sizing adapter. OFF until a validated per-asset, point-in-time
# signal feed exists for the FINAL executable ETF after V1/premium/Void routing.
# The current archived M1 OOS study is a raw-Top1 proxy; it must not be reused for
# another final ETF. Keep this disabled until the all-ETF feed is independently audited.
M1_POSITION_CONTROL_ENABLED = False
M1_LAMBDA = 0.65
M1_MAX_PROBABILITY_CORRECTION = 0.12
M1_MIN_MATURED_SAMPLES = 40
M1_Q90_BASELINE_MULTIPLIER = 1.10
M1_PROBABILITY_MULTIPLIER_SLOPE = 2.0
M1_PROBABILITY_MULTIPLIER_MAX = 1.8
M1_WEIGHT_TOLERANCE = 0.005

STRATEGY_STATE_VERSION = 1


def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_benchmark("000300.XSHG")
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0005,
            close_commission=0.0005,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    log.set_level("order", "error")
    reset_state()
    register_schedules()


def process_initialize(context):
    ensure_state()


def after_code_changed(context):
    ensure_state()
    unschedule_all()
    register_schedules()
    if context.current_dt.strftime("%H:%M") < "14:00":
        finalize_next_day_plan_before_open(context)
        if context.current_dt.strftime("%H:%M") >= "09:31":
            check_gap_at_0931(context)
    else:
        log.info("14:00后热更新：保留已执行计划，次交易日使用新规则")


def register_schedules():
    # T+1开盘前先用T日净值确认溢价，再确定当天唯一目标。
    run_daily(finalize_next_day_plan_before_open, time="before_open")
    run_daily(check_gap_at_0931, time="09:31")
    run_daily(execute_sells_at_1400, time="14:00")
    run_daily(execute_buy_at_1405, time="14:05")
    # T日收盘后只冻结评分，不再读取T日单位净值。
    run_daily(build_raw_ranking_after_close, time="after_close")


def reset_premium_state():
    g.premium_blacklist = set()
    g.premium_snapshot = {}
    g.premium_nav_pending = set()
    g.premium_nav_status = {}
    g.premium_recovery_streak = {}
    g.premium_last_processed_date = {}
    g.premium_state_version = PREMIUM_STATE_VERSION
    g.premium_policy_signature = premium_policy_signature()


def reset_state():
    g.pending_target = None
    g.pending_ranked = None
    g.pending_signal_date = None
    g.pending_rows = []
    g.pending_rows_date = None
    g.pending_target_actual_close = None
    g.pending_exit_actual_closes = {}
    g.pending_map_snapshot = None
    g.entry_checked = False
    g.entry_blocked = False
    g.entry_reason = None
    g.pending_buy_target = None
    g.pending_target_weight = 1.0
    g.pending_preserve_shares = False
    g.pending_preserve_portfolio = False
    g.pending_buy_weight = None
    g.pending_m1_diagnostics = None
    g.m1_risk_signal = None

    # 正常V1的后台状态；Void期间仍继续更新，Void退出后直接恢复。
    g.v1_current_target = None
    g.v1_initialized = False
    g.v1_decision = None
    g.v1_note = None

    # Void Route Baseline v1持久状态。
    g.void_in_void = False
    g.void_incumbent = None
    g.void_entry_breadth = None
    g.void_entry_gap_percentile = None
    g.void_deep_streak = 0
    g.void_routed = False
    g.void_route_target = None
    g.void_decision = None
    g.void_note = None
    g.last_output_target = None
    g.last_output_initialized = False

    # State Map的Gap滚动历史；首次需要时一次性PIT bootstrap，之后逐日追加。
    g.map_gap_history = []
    g.map_gap_last_date = None

    g.last_notice_key = None
    g.strategy_state_version = STRATEGY_STATE_VERSION
    reset_premium_state()


def reset_strategy_logic_state():
    """代码从旧C2版升级到Void版时，只重置策略逻辑状态，不破坏可重建的溢价状态。"""
    g.v1_current_target = None
    g.v1_initialized = False
    g.v1_decision = None
    g.v1_note = None

    g.void_in_void = False
    g.void_incumbent = None
    g.void_entry_breadth = None
    g.void_entry_gap_percentile = None
    g.void_deep_streak = 0
    g.void_routed = False
    g.void_route_target = None
    g.void_decision = None
    g.void_note = None

    g.last_output_target = None
    g.last_output_initialized = False
    g.map_gap_history = []
    g.map_gap_last_date = None
    g.pending_map_snapshot = None
    g.strategy_state_version = STRATEGY_STATE_VERSION


def ensure_state():
    defaults = {
        "pending_target": None,
        "pending_ranked": None,
        "pending_signal_date": None,
        "pending_rows": [],
        "pending_rows_date": None,
        "pending_target_actual_close": None,
        "pending_exit_actual_closes": {},
        "pending_map_snapshot": None,
        "entry_checked": False,
        "entry_blocked": False,
        "entry_reason": None,
        "pending_buy_target": None,
        "pending_target_weight": 1.0,
        "pending_preserve_shares": False,
        "pending_preserve_portfolio": False,
        "pending_buy_weight": None,
        "pending_m1_diagnostics": None,
        "m1_risk_signal": None,

        "v1_current_target": None,
        "v1_initialized": False,
        "v1_decision": None,
        "v1_note": None,

        "void_in_void": False,
        "void_incumbent": None,
        "void_entry_breadth": None,
        "void_entry_gap_percentile": None,
        "void_deep_streak": 0,
        "void_routed": False,
        "void_route_target": None,
        "void_decision": None,
        "void_note": None,

        "last_output_target": None,
        "last_output_initialized": False,
        "map_gap_history": [],
        "map_gap_last_date": None,
        "last_notice_key": None,
    }
    for key, value in defaults.items():
        if not hasattr(g, key):
            # 容器对象不要共享同一个默认引用。
            if isinstance(value, dict):
                value = dict(value)
            elif isinstance(value, list):
                value = list(value)
            elif isinstance(value, set):
                value = set(value)
            setattr(g, key, value)

    if getattr(g, "strategy_state_version", None) != STRATEGY_STATE_VERSION:
        log.info("检测到策略核心从旧版升级到Void Route Baseline v1，重置V1/Void状态")
        reset_strategy_logic_state()

    # 从旧版代码切换时，溢价池新增513500，因此重建溢价子状态。
    if getattr(g, "premium_state_version", None) != PREMIUM_STATE_VERSION:
        log.info("检测到溢价状态结构升级，重置溢价子状态并用历史净值重建")
        reset_premium_state()
    else:
        premium_defaults = {
            "premium_blacklist": set(),
            "premium_snapshot": {},
            "premium_nav_pending": set(),
            "premium_nav_status": {},
            "premium_recovery_streak": {},
            "premium_last_processed_date": {},
        }
        for key, value in premium_defaults.items():
            if not hasattr(g, key):
                setattr(g, key, value)

    ensure_premium_policy()


def premium_policy_signature():
    return (float(PREMIUM_LIMIT), int(PREMIUM_RECOVERY_DAYS), int(PREMIUM_MAX_ENTRY_LAG))


def ensure_premium_policy():
    """重评已配对快照；同一净值日不能因热更新重复累计恢复天数。"""
    signature = premium_policy_signature()
    if getattr(g, "premium_policy_signature", None) == signature:
        return
    for symbol, snapshot in g.premium_snapshot.items():
        premium = finite_number(snapshot.get("premium"))
        if premium is not None and premium > PREMIUM_LIMIT + 1e-12:
            g.premium_blacklist.add(symbol)
        # 已剔除资产仍需两个新的确认日，参数放宽不立即放行。
        g.premium_recovery_streak[symbol] = 0
        snapshot["blocked"] = symbol in g.premium_blacklist
        snapshot["recovery_streak"] = 0
    g.premium_policy_signature = signature
    log.info("溢价参数变更：已按%.0f%%重评历史快照；恢复计数重置，净值日期不重复累计" % premium_limit_pct())


def premium_entry_block_reason(symbol):
    if symbol is None or symbol == CASH_SIGNAL_SYMBOL:
        return None
    if symbol in g.premium_blacklist:
        return "确认溢价超过阈值或尚未完成恢复"
    snapshot = g.premium_snapshot.get(symbol)
    status = g.premium_nav_status.get(symbol, {})
    if not snapshot or status.get("no_nav", True):
        return "净值配对不可用，禁止新买入"
    lag = status.get("lag_trade_days")
    if lag is None or lag > PREMIUM_MAX_ENTRY_LAG or status.get("close_missing_date"):
        return "净值滞后或收盘未配对，禁止新买入"
    return None


def normalize_date(value):
    if value is None:
        return None
    return value.date() if hasattr(value, "date") else value


def display(symbol):
    return "现金" if symbol is None else "%s %s" % (
        symbol.split(".")[0],
        ETF_NAMES.get(symbol, ""),
    )


def is_sim_trade(context):
    return str(getattr(getattr(context, "run_params", None), "type", "")) == "sim_trade"


def notify(context, title, content):
    if not is_sim_trade(context) and not PUSHPLUS_SEND_IN_BACKTEST:
        return
    if not PUSHPLUS_TOKEN:
        return

    key = "%s:%s:%s" % (
        g.pending_signal_date,
        title,
        g.pending_target,
    )
    if key == g.last_notice_key:
        return

    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html",
        "channel": "wechat",
    }

    for attempt in range(1, PUSHPLUS_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                PUSHPLUS_URL,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                timeout=(PUSHPLUS_CONNECT_TIMEOUT, PUSHPLUS_READ_TIMEOUT),
            )
            http_status = response.status_code
            try:
                result = response.json()
            except Exception:
                result = None

            if isinstance(result, dict):
                api_code = result.get("code")
                api_msg = result.get("msg") or result.get("message") or ""
            else:
                api_code = None
                api_msg = ""
            try:
                api_success = int(api_code) == 200
            except Exception:
                api_success = False
            if http_status == 200 and api_success:
                g.last_notice_key = key
                if attempt > 1:
                    log.info("PushPlus第%d次尝试成功" % attempt)
                return
            log.warning(
                "PushPlus接口返回失败：第%d/%d次 | HTTP=%s | code=%s | msg=%s"
                % (attempt, PUSHPLUS_MAX_ATTEMPTS, http_status, api_code, api_msg)
            )
            transient = http_status >= 500 or api_code in (500, 502, 503, 504)
            if not transient:
                return
        except requests.exceptions.SSLError as exc:
            log.warning("PushPlus SSL连接失败：第%d/%d次 | %s" % (attempt, PUSHPLUS_MAX_ATTEMPTS, exc))
        except requests.exceptions.Timeout as exc:
            log.warning("PushPlus连接/读取超时：第%d/%d次 | %s" % (attempt, PUSHPLUS_MAX_ATTEMPTS, exc))
        except requests.exceptions.ConnectionError as exc:
            log.warning("PushPlus网络连接失败：第%d/%d次 | %s" % (attempt, PUSHPLUS_MAX_ATTEMPTS, exc))
        except Exception as exc:
            log.warning("PushPlus未知异常：第%d/%d次 | %s" % (attempt, PUSHPLUS_MAX_ATTEMPTS, exc))
        if attempt >= PUSHPLUS_MAX_ATTEMPTS:
            break
        delay = PUSHPLUS_RETRY_DELAYS[min(attempt - 1, len(PUSHPLUS_RETRY_DELAYS) - 1)]
        log.info("PushPlus将在%d秒后重试" % delay)
        time.sleep(delay)
    log.warning("PushPlus连续%d次发送失败，本次通知放弃" % PUSHPLUS_MAX_ATTEMPTS)


def completed_adjusted_closes_on_date(symbol, trade_date):
    frame = get_price(
        symbol,
        end_date=trade_date,
        count=HISTORY_COUNT,
        frequency="daily",
        fields=["close", "paused"],
        skip_paused=False,
        fq="post",
    )
    if frame is None or frame.empty:
        return None
    last_date = normalize_date(frame.index[-1])
    if last_date != trade_date:
        return None
    last_paused = frame["paused"].iloc[-1]
    if not np.isnan(last_paused) and bool(last_paused):
        return None
    values = frame["close"].dropna()
    return values.values


def actual_daily_close_on_date(symbol, trade_date):
    if symbol is None:
        return None
    frame = get_price(
        symbol,
        end_date=trade_date,
        count=1,
        frequency="daily",
        fields=["close"],
        skip_paused=False,
        fq=None,
    )
    if frame is None or frame.empty:
        return None
    last_date = normalize_date(frame.index[-1])
    if last_date != trade_date:
        return None
    value = float(frame["close"].iloc[-1])
    return value if np.isfinite(value) and value > 0 else None


def premium_limit_pct():
    return PREMIUM_LIMIT * 100.0


def recent_trade_dates(end_date, count):
    try:
        dates = get_trade_days(end_date=end_date, count=count)
    except Exception as exc:
        log.warning("交易日历读取失败（截至%s）：%s" % (end_date, exc))
        return []
    return sorted(normalize_date(item) for item in dates)


def unit_nav_frame(symbols, start_date, end_date):
    try:
        frame = get_extras(
            "unit_net_value",
            symbols,
            start_date=start_date,
            end_date=end_date,
            df=True,
        )
    except Exception as exc:
        log.warning("%s至%s单位净值批量读取失败：%s" % (start_date, end_date, exc))
        return None
    return frame if frame is not None and not frame.empty else None


def trade_day_lag(nav_date, signal_date, trade_dates):
    if nav_date is None:
        return None
    return sum(1 for item in trade_dates if nav_date < item <= signal_date)


def has_trade_date_gap(previous_date, current_date, trade_dates):
    if previous_date is None or current_date is None:
        return False
    between = [item for item in trade_dates if previous_date < item <= current_date]
    return len(between) > 1


def apply_premium_observation(symbol, nav_date, close, nav):
    premium = close / nav - 1.0
    was_blocked = symbol in g.premium_blacklist
    old_streak = int(g.premium_recovery_streak.get(symbol, 0))
    limit_pct = premium_limit_pct()
    action = None

    if premium > PREMIUM_LIMIT + 1e-12:
        g.premium_blacklist.add(symbol)
        g.premium_recovery_streak[symbol] = 0
        if not was_blocked:
            action = "加入黑名单"
    elif was_blocked and premium < PREMIUM_LIMIT - 1e-12:
        new_streak = old_streak + 1
        if new_streak >= PREMIUM_RECOVERY_DAYS:
            g.premium_blacklist.discard(symbol)
            g.premium_recovery_streak[symbol] = 0
            action = "连续%d个已确认净值日低于%.0f%%，恢复资格" % (
                PREMIUM_RECOVERY_DAYS,
                limit_pct,
            )
        else:
            g.premium_recovery_streak[symbol] = new_streak
            action = "低于%.0f%%确认%d/%d，继续剔除" % (
                limit_pct,
                new_streak,
                PREMIUM_RECOVERY_DAYS,
            )
    elif was_blocked:
        g.premium_blacklist.add(symbol)
        g.premium_recovery_streak[symbol] = 0
        action = "等于%.0f%%，继续剔除" % limit_pct
    else:
        g.premium_blacklist.discard(symbol)
        g.premium_recovery_streak[symbol] = 0

    is_blocked = symbol in g.premium_blacklist
    g.premium_snapshot[symbol] = {
        "date": nav_date,
        "close": close,
        "unit_nav": nav,
        "premium": premium,
        "blocked": is_blocked,
        "recovery_streak": int(g.premium_recovery_streak.get(symbol, 0)),
    }
    g.premium_last_processed_date[symbol] = nav_date

    if action:
        level = log.warning if (not was_blocked and is_blocked) or (was_blocked and not is_blocked) else log.info
        level(
            "%s：补处理%s净值，确认溢价%.2f%%（收盘%.4f/净值%.4f），%s"
            % (display(symbol), nav_date, premium * 100, close, nav, action)
        )
    elif is_blocked:
        log.info("%s：补处理%s净值，确认溢价%.2f%%，继续剔除" % (display(symbol), nav_date, premium * 100))


def premium_status_text(symbol):
    if symbol == CASH_SIGNAL_SYMBOL:
        return "现金信号，不参与溢价过滤"
    snapshot = g.premium_snapshot.get(symbol)
    status = g.premium_nav_status.get(symbol, {})
    if not snapshot:
        state = "剔除" if symbol in g.premium_blacklist else "待确认，禁止新买入"
        return "最近回看窗口内暂无可用净值，维持%s" % state
    nav_date = snapshot.get("date")
    lag = status.get("lag_trade_days")
    lag_text = ""
    if lag is not None and lag > 0:
        lag_text = "，滞后%d个交易日" % lag
    state = "剔除" if snapshot.get("blocked") else ("待确认，禁止新买入" if premium_entry_block_reason(symbol) else "历史配对通过（非实时溢价）")
    streak = int(snapshot.get("recovery_streak", 0))
    streak_text = ""
    if snapshot.get("blocked") and streak > 0:
        streak_text = "，恢复确认%d/%d" % (streak, PREMIUM_RECOVERY_DAYS)
    return "净值日%s%s，溢价%.2f%%，%s%s" % (
        nav_date,
        lag_text,
        snapshot.get("premium", 0.0) * 100,
        state,
        streak_text,
    )


def refresh_premium_blacklist_for_date(signal_date):
    ensure_premium_policy()
    trade_dates = recent_trade_dates(signal_date, PREMIUM_NAV_LOOKBACK_TRADE_DAYS)
    g.premium_nav_pending = set()
    g.premium_nav_status = {}
    if not trade_dates:
        for symbol in PREMIUM_MONITOR_POOL:
            g.premium_nav_pending.add(symbol)
        return
    start_date = trade_dates[0]
    frame = unit_nav_frame(PREMIUM_MONITOR_POOL, start_date, signal_date)
    if frame is None:
        for symbol in PREMIUM_MONITOR_POOL:
            g.premium_nav_pending.add(symbol)
            g.premium_nav_status[symbol] = {
                "signal_date": signal_date,
                "latest_nav_date": g.premium_last_processed_date.get(symbol),
                "lag_trade_days": None,
                "new_processed_count": 0,
                "no_nav": True,
            }
        log.warning("%s至%s未读取到任何单位净值，维持全部原溢价状态" % (start_date, signal_date))
        return

    for symbol in PREMIUM_MONITOR_POOL:
        available = []
        if symbol in frame.columns:
            for raw_date, raw_value in frame[symbol].dropna().items():
                nav_date = normalize_date(raw_date)
                value = float(raw_value)
                if nav_date is not None and nav_date <= signal_date and np.isfinite(value) and value > 0:
                    available.append((nav_date, value))
        available.sort(key=lambda item: item[0])
        if not available:
            g.premium_nav_pending.add(symbol)
            latest_processed = g.premium_last_processed_date.get(symbol)
            g.premium_nav_status[symbol] = {
                "signal_date": signal_date,
                "latest_nav_date": latest_processed,
                "lag_trade_days": trade_day_lag(latest_processed, signal_date, trade_dates),
                "new_processed_count": 0,
                "no_nav": True,
            }
            continue
        last_processed = normalize_date(g.premium_last_processed_date.get(symbol))
        new_items = [item for item in available if last_processed is None or item[0] > last_processed]
        processed_count = 0
        close_missing_date = None
        for nav_date, nav in new_items:
            if has_trade_date_gap(last_processed, nav_date, trade_dates):
                if symbol in g.premium_blacklist:
                    g.premium_recovery_streak[symbol] = 0
            close = actual_daily_close_on_date(symbol, nav_date)
            if close is None:
                close_missing_date = nav_date
                break
            apply_premium_observation(symbol, nav_date, close, nav)
            last_processed = nav_date
            processed_count += 1
        latest_processed = normalize_date(g.premium_last_processed_date.get(symbol))
        lag = trade_day_lag(latest_processed, signal_date, trade_dates)
        if latest_processed is None or latest_processed < signal_date:
            g.premium_nav_pending.add(symbol)
        g.premium_nav_status[symbol] = {
            "signal_date": signal_date,
            "latest_nav_date": latest_processed,
            "latest_available_nav_date": available[-1][0],
            "lag_trade_days": lag,
            "new_processed_count": processed_count,
            "close_missing_date": close_missing_date,
            "no_nav": False,
        }


def score_e_raw(values):
    result = {
        "eligible": False,
        "score": None,
        "annualized": None,
        "r_squared": None,
        "reasons": [],
    }
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values) & (values > 0)]
    if len(values) < LOOKBACK_DAYS + 1:
        result["reasons"].append("insufficient_history")
        return result
    prices = values[-(LOOKBACK_DAYS + 1):]
    y = np.log(prices)
    x = np.arange(len(y), dtype=float)
    weights = np.power(0.5, np.arange(len(y) - 1, -1, -1, dtype=float) / NOMINAL_HALF_LIFE)
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    fitted = float(intercept) + float(slope) * x
    fit_weights = np.square(weights)
    mean = float(np.average(y, weights=fit_weights))
    ss_res = float(np.sum(fit_weights * np.square(y - fitted)))
    ss_tot = float(np.sum(fit_weights * np.square(y - mean)))
    r_squared = float(np.clip(1.0 - ss_res / ss_tot, 0.0, 1.0)) if ss_tot else 0.0
    annualized = math.exp(float(slope) * ANNUALIZATION) - 1.0
    score = annualized * r_squared if annualized > 0 and r_squared > 0 else 0.0
    result.update({"score": float(score), "annualized": float(annualized), "r_squared": r_squared})
    if score <= 0:
        result["reasons"].append("score_not_positive")
    ratios = prices[-4:] / prices[-4]
    if np.min(ratios[1:] / ratios[:-1]) < DAILY_DROP_FLOOR:
        result["reasons"].append("recent_daily_drop")
    result["eligible"] = not result["reasons"]
    return result


def rank_on_date(trade_date):
    rows = []
    for symbol in ETF_POOL:
        try:
            values = completed_adjusted_closes_on_date(symbol, trade_date)
            row = score_e_raw(values if values is not None else [])
            row["symbol"] = symbol
            rows.append(row)
        except Exception as exc:
            log.warning("评分失败%s（%s）：%s" % (display(symbol), trade_date, exc))
            rows.append({
                "symbol": symbol,
                "eligible": False,
                "score": None,
                "annualized": None,
                "r_squared": None,
                "reasons": ["data_error"],
            })
    return rows


REASON_NAMES = {
    "insufficient_history": "历史数据不足",
    "score_not_positive": "score非正",
    "recent_daily_drop": "近三日存在单日跌幅超过3%",
    "data_error": "数据读取或计算异常",
}


def sorted_eligible_rows(rows):
    return sorted(
        [row for row in rows if row.get("eligible")],
        key=lambda row: (row.get("score", float("-inf")), row.get("symbol", "")),
        reverse=True,
    )


def sorted_executable_rows(rows):
    return [row for row in sorted_eligible_rows(rows) if not premium_entry_block_reason(row.get("symbol"))]


def sorted_high_score_ineligible_rows(rows):
    return sorted(
        [row for row in rows if not row.get("eligible") and row.get("score") is not None and row.get("score") > 0],
        key=lambda row: (row.get("score", float("-inf")), row.get("symbol", "")),
        reverse=True,
    )


def select_raw_ranked(rows):
    ranked = sorted_eligible_rows(rows)
    return ranked[0] if ranked else None


def select_ranked_after_premium(rows):
    ranked = sorted_executable_rows(rows)
    return ranked[0] if ranked else None


def reason_text(row):
    reasons = row.get("reasons") or []
    return "、".join(REASON_NAMES.get(item, item) for item in reasons) or "未知原因"


def score_row_text(row, rank=None, top_score=None, include_premium=False):
    prefix = "%d. " % rank if rank is not None else ""
    text = "%s%s | score=%.6f | annual=%.2f%% | R2=%.4f" % (
        prefix,
        display(row.get("symbol")),
        row.get("score", 0.0),
        row.get("annualized", 0.0) * 100,
        row.get("r_squared", 0.0),
    )
    if top_score is not None and rank is not None and rank > 1 and top_score > 0:
        gap = top_score - row.get("score", 0.0)
        text += " | 距第一=%.6f（%.2f%%）" % (gap, gap / top_score * 100)
    if include_premium:
        text += " | %s" % premium_status_text(row.get("symbol"))
    return text


def log_raw_ranking_diagnostics(rows):
    eligible = sorted_eligible_rows(rows)[:RANK_LOG_TOP_N]
    log.info("原始合格Top%d：" % RANK_LOG_TOP_N)
    if not eligible:
        log.info("  无合格候选")
    else:
        top_score = eligible[0].get("score", 0.0)
        for index, row in enumerate(eligible, 1):
            log.info("  " + score_row_text(row, index, top_score, False))
    rejected = sorted_high_score_ineligible_rows(rows)[:RANK_LOG_TOP_N]
    log.info("高分但未合格Top%d：" % RANK_LOG_TOP_N)
    if not rejected:
        log.info("  无")
    else:
        for index, row in enumerate(rejected, 1):
            log.info(
                "  %d. %s | score=%.6f | annual=%.2f%% | R2=%.4f | 原因=%s"
                % (
                    index,
                    display(row.get("symbol")),
                    row.get("score", 0.0),
                    row.get("annualized", 0.0) * 100,
                    row.get("r_squared", 0.0),
                    reason_text(row),
                )
            )


def log_execution_diagnostics(rows):
    raw_rows = sorted_eligible_rows(rows)
    raw_rank = {row.get("symbol"): index for index, row in enumerate(raw_rows, 1)}
    executable = sorted_executable_rows(rows)[:RANK_LOG_TOP_N]
    log.info("执行候选Top%d：" % RANK_LOG_TOP_N)
    if not executable:
        log.info("  无可执行候选")
    else:
        top_score = executable[0].get("score", 0.0)
        for index, row in enumerate(executable, 1):
            log.info("  " + score_row_text(row, index, top_score, True))
    filtered = [row for row in raw_rows if row.get("symbol") in g.premium_blacklist]
    log.info("被溢价过滤：")
    if not filtered:
        log.info("  无")
    else:
        for row in filtered:
            log.warning(
                "  %s | 原始排名第%d | score=%.6f | %s"
                % (
                    display(row.get("symbol")),
                    raw_rank.get(row.get("symbol"), -1),
                    row.get("score", 0.0),
                    premium_status_text(row.get("symbol")),
                )
            )


def execution_top3_html(rows):
    executable = sorted_executable_rows(rows)[:RANK_LOG_TOP_N]
    if not executable:
        return "无可执行候选"
    top_score = executable[0].get("score", 0.0)
    return "<br>".join(score_row_text(row, index, top_score, True) for index, row in enumerate(executable, 1))


def premium_filtered_html(rows):
    raw_rows = sorted_eligible_rows(rows)
    rank_map = {row.get("symbol"): index for index, row in enumerate(raw_rows, 1)}
    filtered = [row for row in raw_rows if row.get("symbol") in g.premium_blacklist]
    if not filtered:
        return "无"
    return "<br>".join(
        "%s｜原始第%d｜score=%.6f｜%s" % (
            display(row.get("symbol")),
            rank_map.get(row.get("symbol"), -1),
            row.get("score", 0.0),
            premium_status_text(row.get("symbol")),
        )
        for row in filtered
    )


def managed_holdings(context):
    return [
        symbol
        for symbol, position in context.portfolio.positions.items()
        if symbol in MANAGED_POOL and position.total_amount > 0
    ]


def holdings_match_target(holdings, target):
    if target is None:
        return len(holdings) == 0
    return len(holdings) == 1 and holdings[0] == target


def current_price(symbol):
    try:
        item = get_current_data()[symbol]
        value = float(item.last_price)
        if not item.paused and np.isfinite(value) and value > 0:
            return value, None
        return None, "停牌或现价无效"
    except Exception as exc:
        return None, str(exc)


def safe_target_value(symbol, value):
    try:
        order = order_target_value(symbol, value)
        return order, None if order is not None else "订单未提交"
    except Exception as exc:
        return None, str(exc)



def m1_clip(value, lower, upper):
    return max(lower, min(upper, value))


def m1_compute_sizing(signal):
    """Apply the frozen M1 + Q90 sizing equations to one validated per-asset signal.

    recent_err is mean(Y - P0) over matured risk signals. The 0.65 multiplier,
    +/-12pp correction cap, 40-observation fallback, 1.10 Q90 baseline ratio,
    and probability multiplier cap 1.8 are frozen research settings.
    """
    if not isinstance(signal, dict):
        return None
    q90 = finite_number(signal.get("q90"))
    normal_risk = finite_number(signal.get("normal_risk"))
    p0 = finite_number(signal.get("p0"))
    p_vol = finite_number(signal.get("p_vol"))
    recent_err = finite_number(signal.get("recent_err"))
    n_recent_value = finite_number(signal.get("n_recent"))
    if any(x is None for x in (q90, normal_risk, p0, p_vol, recent_err, n_recent_value)):
        return None
    if q90 <= 0 or normal_risk < 0:
        return None
    if not (0.0 <= p0 <= 1.0 and 0.0 <= p_vol <= 1.0):
        return None
    if not -1.0 <= recent_err <= 1.0:
        return None
    n_recent = int(round(n_recent_value))
    if n_recent < 0 or abs(n_recent_value - n_recent) > 1e-9:
        return None

    if n_recent < M1_MIN_MATURED_SAMPLES:
        correction = 0.0
    else:
        correction = m1_clip(
            M1_LAMBDA * recent_err,
            -M1_MAX_PROBABILITY_CORRECTION,
            M1_MAX_PROBABILITY_CORRECTION,
        )
    p_m1 = m1_clip(p0 + correction, 0.005, 0.995)
    base_e = m1_clip(1.0 - M1_Q90_BASELINE_MULTIPLIER * normal_risk / q90, 0.0, 1.0)
    probability_multiplier = m1_clip(
        1.0 + M1_PROBABILITY_MULTIPLIER_SLOPE * (p_m1 - p_vol),
        0.0,
        M1_PROBABILITY_MULTIPLIER_MAX,
    )
    e = m1_clip(base_e * probability_multiplier, 0.0, 1.0)
    return {
        "q90": q90,
        "normal_risk": normal_risk,
        "p0": p0,
        "p_vol": p_vol,
        "recent_err": recent_err,
        "n_recent": n_recent,
        "correction": correction,
        "p_m1": p_m1,
        "base_e": base_e,
        "probability_multiplier": probability_multiplier,
        "e": e,
        "target_weight": 1.0 - e,
    }


def m1_validate_signal_for_target(signal_date, target):
    """Accept only a same-date, same-symbol, per-asset final-target prediction.

    Required g.m1_risk_signal contract:
      date, data_asof, symbol, scope='per_asset_final_target', model_version,
      q90, normal_risk, p0, p_vol, recent_err, n_recent.

    No fallback to the raw OLS Top1 prediction is permitted after V1/Void routing.
    """
    data = getattr(g, "m1_risk_signal", None)
    if not isinstance(data, dict) or target not in RISK_POOL:
        return None
    expected_date = str(signal_date)[:10]
    if str(data.get("date", ""))[:10] != expected_date:
        return None
    if str(data.get("data_asof", ""))[:10] != expected_date:
        return None
    if data.get("symbol") != target:
        return None
    if data.get("scope") != "per_asset_final_target":
        return None
    if not isinstance(data.get("model_version"), str) or not data.get("model_version", "").strip():
        return None
    result = m1_compute_sizing(data)
    if result is None:
        return None
    result["model_version"] = data["model_version"]
    return result


def m1_actual_position_weight(context, target):
    if target is None:
        return 0.0
    position = context.portfolio.positions.get(target)
    total = finite_number(context.portfolio.total_value)
    if not position or total is None or total <= 0:
        return 0.0
    value = finite_number(getattr(position, "value", None))
    return max(0.0, min(1.0, value / total)) if value is not None else 0.0


def build_m1_position_plan(context, signal_date, target, holdings):
    """Return (final target, weight, preserve shares, preserve portfolio, note, diagnostics).

    Normal state: use M1 only for a same-day, same-symbol final-target signal.
    Missing signal: preserve an existing same-symbol holding; never open a new
    risk position at 100% by treating missing risk data as zero.
    Void, before a defensive route: freeze the actual account holdings and cash.
    Void route: retain the existing 513500/511220 routing authority; do not apply M1.
    """
    if target is None:
        return (None, 0.0, False, False, "正式策略目标为空仓", None)
    if not M1_POSITION_CONTROL_ENABLED:
        return (target, 1.0, False, False, "M1仓位控制未启用，沿用原全仓执行", None)

    if g.void_in_void and not g.void_routed:
        if len(holdings) == 0:
            return (None, 0.0, True, False, "Void冻结空仓，不自动建立新风险仓位", None)
        if len(holdings) == 1:
            actual_target = holdings[0]
            actual_weight = m1_actual_position_weight(context, actual_target)
            return (
                actual_target, actual_weight, True, False,
                "Void冻结账户实际持仓份额与现金，不运行M1调仓", None
            )
        return (
            target, 0.0, False, True,
            "Void期间发现多个策略持仓，冻结账户现状并停止自动调仓", None
        )

    if g.void_in_void and g.void_routed:
        return (target, 1.0, False, False, "Void防御路由优先，沿用既有路由仓位", None)
    if target not in RISK_POOL:
        return (target, 1.0, False, False, "现金/防御路由不套用风险ETF的M1仓位模型", None)

    diagnostics = m1_validate_signal_for_target(signal_date, target)
    if diagnostics is None:
        if target in holdings:
            current_weight = m1_actual_position_weight(context, target)
            return (
                target, current_weight, True, False,
                "缺少同日同标的有效M1预测，保持现有份额，不加不减", None
            )
        return (
            target, 0.0, False, False,
            "缺少同日同标的有效M1预测，禁止新开风险仓位", None
        )
    return (
        target, diagnostics["target_weight"], False, False,
        "M1动态仓位控制", diagnostics
    )


def m1_diagnostics_text(diagnostics):
    if not isinstance(diagnostics, dict):
        return "无（未应用M1预测）"
    return (
        "Q90=%.2f%% Dnormal=%.2f%% P0=%.2f%% PM1=%.2f%% Pvol=%.2f%% "
        "基础减仓=%.2f%% 概率倍率=%.3f 最终减仓=%.2f%% 模型=%s"
        % (
            diagnostics["q90"] * 100,
            diagnostics["normal_risk"] * 100,
            diagnostics["p0"] * 100,
            diagnostics["p_m1"] * 100,
            diagnostics["p_vol"] * 100,
            diagnostics["base_e"] * 100,
            diagnostics["probability_multiplier"],
            diagnostics["e"] * 100,
            diagnostics.get("model_version", "NA"),
        )
    )


def m1_holding_matches_plan(context, target):
    if getattr(g, "pending_preserve_portfolio", False):
        return True
    holdings = managed_holdings(context)
    if target is None:
        return len(holdings) == 0
    if holdings != [target]:
        return False
    if getattr(g, "pending_preserve_shares", False):
        return True
    actual = m1_actual_position_weight(context, target)
    return abs(actual - g.pending_target_weight) < M1_WEIGHT_TOLERANCE


def m1_target_value(context):
    total = finite_number(context.portfolio.total_value)
    if total is None or total <= 0:
        return None
    return max(0.0, min(total, total * g.pending_target_weight))


def execute_m1_weight_sells_at_1400(context):
    """M1-aware sell leg; order submission is not treated as a confirmed fill."""
    if g.pending_signal_date is None:
        return
    if getattr(g, "pending_preserve_portfolio", False):
        log.warning("M1：Void多持仓异常，冻结账户现状，本日不自动下单")
        clear_pending()
        return
    target = g.pending_target
    holdings = managed_holdings(context)
    if m1_holding_matches_plan(context, target):
        clear_pending()
        return

    if target is not None and target not in holdings and g.pending_target_weight > 0:
        if not g.entry_checked:
            g.entry_blocked = True
            g.entry_reason = "09:31新标的预检查缺失"
        if not g.entry_blocked:
            reason = entry_preflight_reason(context, target, check_drawdown=True)
            if reason:
                g.entry_blocked = True
                g.entry_reason = reason
        if g.entry_blocked:
            target = execution_veto_fallback(context, g.entry_reason or "目标受阻")
            g.pending_target = target
            holdings = managed_holdings(context)
            if target in holdings:
                g.pending_target_weight = m1_actual_position_weight(context, target)
                g.pending_preserve_shares = True
            else:
                g.pending_target_weight = 1.0 if target in (CASH_SIGNAL_SYMBOL, US_CARRIER_SYMBOL) else 0.0
                g.pending_preserve_shares = False
            if target == CASH_SIGNAL_SYMBOL:
                g.entry_blocked = False
            if m1_holding_matches_plan(context, target):
                clear_pending()
                return

    for symbol in holdings:
        if symbol != target:
            _, error = safe_target_value(symbol, 0)
            if error:
                log.warning("M1 14:00旧仓卖出未成功：%s %s" % (display(symbol), error))

    if target is None:
        clear_pending()
        return
    if not g.pending_preserve_shares and target in holdings:
        amount = m1_target_value(context)
        if amount is None:
            log.warning("M1目标资金价值不可用，取消仓位修改")
            clear_pending()
            return
        current = finite_number(context.portfolio.positions[target].value)
        total = finite_number(context.portfolio.total_value)
        if current is not None and total is not None and current > amount + total * M1_WEIGHT_TOLERANCE:
            _, error = safe_target_value(target, amount)
            if error:
                log.warning("M1 14:00部分减仓失败：%s %s" % (display(target), error))
    # The 14:05 leg re-reads actual holdings; an unfilled sell blocks a new ETF buy.
    g.pending_buy_target = target
    g.pending_buy_weight = g.pending_target_weight


def execute_m1_weight_buy_at_1405(context):
    """M1-aware buy/re-entry leg; never assumes the 14:00 sell filled."""
    target = g.pending_buy_target
    if target is None or g.pending_signal_date is None:
        return
    if getattr(g, "pending_preserve_portfolio", False) or g.pending_preserve_shares:
        clear_pending()
        return
    if g.pending_target_weight <= 0:
        log.info("M1目标仓位为0，不提交买单")
        clear_pending()
        return
    blockers = [symbol for symbol in managed_holdings(context) if symbol != target]
    if blockers:
        log.warning("M1 14:05仍有旧仓未清，停止增加持仓：%s" % blockers)
        clear_pending()
        return
    if g.entry_blocked:
        log.warning("M1 09:31买入保护仍有效：%s" % (g.entry_reason or "买入已阻断"))
        clear_pending()
        return
    amount = m1_target_value(context)
    total = finite_number(context.portfolio.total_value)
    if amount is None or total is None or total <= 0:
        log.warning("M1 14:05无效目标金额，不发单")
        clear_pending()
        return
    current = finite_number(getattr(context.portfolio.positions.get(target), "value", 0)) or 0.0
    if current >= amount - total * M1_WEIGHT_TOLERANCE:
        clear_pending()
        return
    reason = entry_preflight_reason(context, target)
    if reason:
        log.warning("M1 14:05只阻止买入，不逆转已完成减仓：%s" % reason)
        clear_pending()
        return
    price, error = current_price(target)
    high = today_high(target, context, price) if price is not None else None
    if high is None or 1.0 - price / high >= INTRADAY_HIGH_DRAWDOWN_LIMIT:
        log.warning("M1 14:05分钟高点保护：%s，取消本次买入" % (error or "回撤触发"))
        clear_pending()
        return
    _, order_error = safe_target_value(target, amount)
    if order_error:
        log.warning("M1 14:05目标仓位买入失败：%s" % order_error)
    else:
        log.info("M1 14:05目标仓位：%s %.2f%%" % (display(target), g.pending_target_weight * 100))
    clear_pending()


def row_for_symbol(rows, symbol):
    for row in rows:
        if row.get("symbol") == symbol:
            return row
    return None


def finite_number(value):
    try:
        value = float(value)
        return value if np.isfinite(value) else None
    except Exception:
        return None


def raw_score_from_row(rows, symbol):
    row = row_for_symbol(rows, symbol)
    return finite_number(row.get("score")) if row else None


def pool_score_from_row(rows, symbol):
    row = row_for_symbol(rows, symbol)
    if not row or not row.get("eligible"):
        return None
    return finite_number(row.get("score"))


def choose_fixv2_challenger(rows):
    risk_rows = [
        row for row in sorted_eligible_rows(rows)
        if row.get("symbol") in RISK_POOL and row.get("symbol") not in g.premium_blacklist
    ]
    best = risk_rows[0] if risk_rows else None
    cash_score = pool_score_from_row(rows, CASH_SIGNAL_SYMBOL)
    cash_cmp = cash_score if cash_score is not None else float("-inf")
    if best is None:
        return None, None, cash_score
    best_score = finite_number(best.get("score"))
    if best_score is None or not (best_score > cash_cmp):
        return None, best, cash_score
    return best.get("symbol"), best, cash_score


def previous_trade_date(signal_date):
    try:
        dates = [normalize_date(item) for item in get_trade_days(end_date=signal_date, count=2)]
    except Exception as exc:
        log.warning("上一交易日读取失败（截至%s）：%s" % (signal_date, exc))
        return None
    dates = [item for item in dates if item is not None]
    if len(dates) < 2 or dates[-1] != signal_date:
        return None
    return dates[-2]


def raw_score_delta_one_day(rows, symbol, signal_date):
    current_score = raw_score_from_row(rows, symbol)
    if current_score is None:
        return None
    prev_date = previous_trade_date(signal_date)
    if prev_date is None:
        return None
    try:
        values = completed_adjusted_closes_on_date(symbol, prev_date)
        prev = score_e_raw(values if values is not None else [])
        prev_score = finite_number(prev.get("score"))
    except Exception as exc:
        log.warning("V1 score增量计算失败%s（%s）：%s" % (display(symbol), prev_date, exc))
        return None
    if prev_score is None:
        return None
    return current_score - prev_score, current_score, prev_score, prev_date


def overlap_amount(low, high, amount, a, b):
    low = np.asarray(low, dtype=float)
    high = np.asarray(high, dtype=float)
    amount = np.asarray(amount, dtype=float)
    valid = np.isfinite(low) & np.isfinite(high) & np.isfinite(amount) & (amount >= 0)
    if not valid.any():
        return None
    lo = np.minimum(low[valid], high[valid])
    hi = np.maximum(low[valid], high[valid])
    amt = amount[valid]
    width = hi - lo
    ov = np.maximum(0.0, np.minimum(hi, b) - np.maximum(lo, a))
    frac = np.zeros_like(ov, dtype=float)
    nz = width > 1e-12
    frac[nz] = ov[nz] / width[nz]
    z = ~nz
    if z.any():
        p = lo[z]
        frac[z] = ((p >= a) & (p <= b)).astype(float)
    return float(np.sum(amt * frac))


def v1_resistance_percentile(symbol, signal_date):
    try:
        frame = get_price(
            symbol,
            end_date=signal_date,
            count=V1_PROFILE_FETCH_BARS,
            frequency="daily",
            fields=["low", "high", "close", "money"],
            skip_paused=False,
            fq="post",
        )
    except Exception as exc:
        log.warning("V1阻力画像读取失败%s：%s" % (display(symbol), exc))
        return None
    if frame is None or frame.empty:
        return None
    if normalize_date(frame.index[-1]) != signal_date:
        return None
    low = np.asarray(frame["low"], dtype=float)
    high = np.asarray(frame["high"], dtype=float)
    close = np.asarray(frame["close"], dtype=float)
    amount = np.asarray(frame["money"], dtype=float)
    n = len(frame)
    upper_share = np.full(n, np.nan, dtype=float)
    for i in range(n):
        p = close[i]
        if not np.isfinite(p) or p <= 0:
            continue
        j0 = max(0, i - V1_RES_LOOKBACK)
        if i <= j0:
            continue
        upper = overlap_amount(low[j0:i], high[j0:i], amount[j0:i], p, p * 1.05)
        total = overlap_amount(low[j0:i], high[j0:i], amount[j0:i], p * 0.95, p * 1.05)
        if upper is not None and total is not None and np.isfinite(upper) and np.isfinite(total) and total > 0:
            upper_share[i] = upper / total
    i = n - 1
    if not np.isfinite(upper_share[i]):
        return None
    k0 = max(0, i - V1_PCT_LOOKBACK)
    hist = upper_share[k0:i]
    hist = hist[np.isfinite(hist)]
    if len(hist) < V1_MIN_PROFILE_HISTORY:
        return None
    return 100.0 * float(np.mean(hist <= upper_share[i]))


def v1_incumbent_valid(rows, symbol):
    if symbol is None or symbol not in RISK_POOL:
        return False
    if symbol in g.premium_blacklist:
        return False
    old_score = pool_score_from_row(rows, symbol)
    if old_score is None:
        return False
    cash_score = pool_score_from_row(rows, CASH_SIGNAL_SYMBOL)
    cash_cmp = cash_score if cash_score is not None else float("-inf")
    return old_score > cash_cmp


def resolve_v1_target(context, signal_date, rows, challenger, holdings):
    if not g.v1_initialized:
        current_risk = [symbol for symbol in holdings if symbol in RISK_POOL]
        g.v1_current_target = current_risk[0] if len(current_risk) == 1 else None
        g.v1_initialized = True
    current = g.v1_current_target
    old = current
    decision = "HOLD"
    note = None
    if challenger == current:
        decision = "HOLD"
    elif challenger is None:
        current = None
        decision = "EXIT_CASH"
        note = "风险Top1未能严格战胜511220，正常V1转现金"
    elif current is None:
        current = challenger
        decision = "ENTER"
        note = "V1当前为空仓，进入%s" % display(challenger)
    else:
        if not v1_incumbent_valid(rows, current):
            current = challenger
            decision = "SWITCH_OLD_INVALID"
            note = "旧V1 incumbent已失效，直接切换到%s" % display(challenger)
        else:
            rp = v1_resistance_percentile(challenger, signal_date)
            sd_info = raw_score_delta_one_day(rows, challenger, signal_date)
            sd = sd_info[0] if sd_info is not None else None
            if rp is not None and rp >= V1_RES_PCT_THRESHOLD and sd is not None and sd <= 0.0:
                decision = "VETO_V1"
                note = (
                    "V1 veto：新Top1%s阻力分位%.1f%% >= %.0f%%，raw score增量%+.6f <= 0；继续%s"
                    % (display(challenger), rp, V1_RES_PCT_THRESHOLD, sd, display(current))
                )
            else:
                current = challenger
                decision = "SWITCH_NORMAL"
                note = (
                    "V1允许换帅%s -> %s；阻力分位=%s，score增量=%s"
                    % (
                        display(old),
                        display(challenger),
                        "NA" if rp is None else "%.1f%%" % rp,
                        "NA" if sd is None else "%+.6f" % sd,
                    )
                )
    g.v1_current_target = current
    g.v1_decision = decision
    g.v1_note = note or decision
    return current


def raw_ols_score_window(values):
    values = np.asarray(values, dtype=float)
    if len(values) != LOOKBACK_DAYS + 1:
        return None
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        return None
    y = np.log(values)
    x = np.arange(len(y), dtype=float)
    q = np.power(0.5, np.arange(len(y) - 1, -1, -1, dtype=float) / NOMINAL_HALF_LIFE)
    try:
        slope, intercept = np.polyfit(x, y, 1, w=q)
    except Exception:
        return None
    fitted = float(intercept) + float(slope) * x
    w = np.square(q)
    mean = float(np.average(y, weights=w))
    ss_res = float(np.sum(w * np.square(y - fitted)))
    ss_tot = float(np.sum(w * np.square(y - mean)))
    r2 = float(np.clip(1.0 - ss_res / ss_tot, 0.0, 1.0)) if ss_tot > 0 else 0.0
    annual = math.exp(float(slope) * ANNUALIZATION) - 1.0
    return float(annual * r2) if annual > 0 and r2 > 0 else 0.0


def raw_score_on_date(symbol, trade_date):
    values = completed_adjusted_closes_on_date(symbol, trade_date)
    if values is None or len(values) < LOOKBACK_DAYS + 1:
        return None
    return raw_ols_score_window(values[-(LOOKBACK_DAYS + 1):])


def bootstrap_map_gap_history(signal_date):
    try:
        trade_dates = [normalize_date(item) for item in get_trade_days(end_date=signal_date, count=MAP_BOOTSTRAP_BARS)]
    except Exception as exc:
        log.warning("State Map交易日bootstrap失败：%s" % exc)
        return []
    trade_dates = [d for d in trade_dates if d is not None]
    if len(trade_dates) < LOOKBACK_DAYS + 1:
        return []
    close_by_symbol = {}
    for symbol in RISK_POOL:
        try:
            frame = get_price(
                symbol,
                end_date=signal_date,
                count=MAP_BOOTSTRAP_BARS,
                frequency="daily",
                fields=["close"],
                skip_paused=False,
                fq="post",
            )
        except Exception as exc:
            log.warning("State Map历史读取失败%s：%s" % (display(symbol), exc))
            continue
        if frame is None or frame.empty:
            continue
        close_by_symbol[symbol] = {
            normalize_date(d): float(v)
            for d, v in frame["close"].items()
            if np.isfinite(v) and float(v) > 0
        }
    hist = []
    for i in range(LOOKBACK_DAYS, len(trade_dates)):
        d = trade_dates[i]
        window_dates = trade_dates[i - LOOKBACK_DAYS:i + 1]
        scores = []
        for symbol in RISK_POOL:
            mapping = close_by_symbol.get(symbol)
            if not mapping:
                continue
            try:
                vals = [mapping[x] for x in window_dates]
            except KeyError:
                continue
            sc = raw_ols_score_window(vals)
            if sc is not None and np.isfinite(sc):
                scores.append(float(sc))
        if len(scores) >= 2:
            scores.sort(reverse=True)
            hist.append((d, max(scores[0] - scores[1], 0.0)))
    hist = hist[-MAP_GAP_LOOKBACK:]
    g.map_gap_history = hist
    g.map_gap_last_date = hist[-1][0] if hist else None
    return hist


def ensure_map_gap_history(signal_date, current_gap):
    hist = list(getattr(g, "map_gap_history", []) or [])
    last_date = normalize_date(getattr(g, "map_gap_last_date", None))
    prev_date = previous_trade_date(signal_date)
    need_bootstrap = (
        not hist
        or last_date is None
        or (last_date != signal_date and prev_date is not None and last_date != prev_date)
    )
    if need_bootstrap:
        hist = bootstrap_map_gap_history(signal_date)
        last_date = normalize_date(getattr(g, "map_gap_last_date", None))
    if current_gap is not None and np.isfinite(current_gap) and last_date != signal_date:
        hist.append((signal_date, float(current_gap)))
        hist = hist[-MAP_GAP_LOOKBACK:]
        g.map_gap_history = hist
        g.map_gap_last_date = signal_date
    return list(getattr(g, "map_gap_history", []) or [])


def state_map_snapshot(signal_date, rows):
    risk_scores = []
    for symbol in RISK_POOL:
        sc = raw_score_from_row(rows, symbol)
        if sc is not None:
            risk_scores.append((symbol, sc))
    cash_score = raw_score_from_row(rows, CASH_SIGNAL_SYMBOL)
    if cash_score is None or len(risk_scores) < 2:
        return None
    ranked = sorted(risk_scores, key=lambda x: (-x[1], x[0]))
    gap_raw = max(ranked[0][1] - ranked[1][1], 0.0)
    breadth_count = sum(1 for _, sc in risk_scores if sc > cash_score)
    breadth_pct = 100.0 * breadth_count / float(len(RISK_POOL))
    hist = ensure_map_gap_history(signal_date, gap_raw)
    gap_values = [float(v) for d, v in hist if d <= signal_date and np.isfinite(v)][-MAP_GAP_LOOKBACK:]
    if not gap_values:
        return None
    gap_percentile = 100.0 * sum(v <= gap_raw for v in gap_values) / float(len(gap_values))
    if breadth_pct >= MAP_BREADTH_THRESHOLD and gap_percentile >= MAP_GAP_THRESHOLD:
        quadrant = "TREND_EXPANSION"
    elif breadth_pct >= MAP_BREADTH_THRESHOLD:
        quadrant = "ROTATION_CROWDING"
    elif gap_percentile >= MAP_GAP_THRESHOLD:
        quadrant = "NARROW_LEADERSHIP"
    else:
        quadrant = "DEFENSIVE_VOID"
    return {
        "date": signal_date,
        "breadth_pct": breadth_pct,
        "breadth_count": breadth_count,
        "gap_raw": gap_raw,
        "gap_percentile": gap_percentile,
        "quadrant": quadrant,
        "top1": ranked[0][0],
        "top2": ranked[1][0],
        "cash_raw_score": cash_score,
    }


def historical_state_map_tail(signal_date):
    try:
        trade_dates = [normalize_date(item) for item in get_trade_days(end_date=signal_date, count=MAP_RESTORE_BARS)]
    except Exception as exc:
        log.warning("Void热恢复交易日读取失败：%s" % exc)
        return []
    trade_dates = [d for d in trade_dates if d is not None]
    if len(trade_dates) < LOOKBACK_DAYS + MAP_GAP_LOOKBACK:
        return []
    symbols = list(RISK_POOL) + [CASH_SIGNAL_SYMBOL]
    close_by_symbol = {}
    for symbol in symbols:
        try:
            frame = get_price(
                symbol,
                end_date=signal_date,
                count=MAP_RESTORE_BARS,
                frequency="daily",
                fields=["close"],
                skip_paused=False,
                fq="post",
            )
        except Exception as exc:
            log.warning("Void热恢复行情读取失败%s：%s" % (display(symbol), exc))
            continue
        if frame is None or frame.empty:
            continue
        close_by_symbol[symbol] = {
            normalize_date(d): float(v)
            for d, v in frame["close"].items()
            if np.isfinite(v) and float(v) > 0
        }
    gap_hist = []
    records = []
    for i in range(LOOKBACK_DAYS, len(trade_dates)):
        d = trade_dates[i]
        window_dates = trade_dates[i - LOOKBACK_DAYS:i + 1]
        risk_scores = []
        for symbol in RISK_POOL:
            mapping = close_by_symbol.get(symbol)
            if not mapping:
                continue
            try:
                vals = [mapping[x] for x in window_dates]
            except KeyError:
                continue
            sc = raw_ols_score_window(vals)
            if sc is not None and np.isfinite(sc):
                risk_scores.append((symbol, float(sc)))
        cash_map = close_by_symbol.get(CASH_SIGNAL_SYMBOL)
        cash_score = None
        if cash_map:
            try:
                cash_vals = [cash_map[x] for x in window_dates]
                cash_score = raw_ols_score_window(cash_vals)
            except KeyError:
                cash_score = None
        if len(risk_scores) < 2 or cash_score is None:
            continue
        ranked = sorted(risk_scores, key=lambda x: (-x[1], x[0]))
        gap_raw = max(ranked[0][1] - ranked[1][1], 0.0)
        gap_hist.append(float(gap_raw))
        gap_hist = gap_hist[-MAP_GAP_LOOKBACK:]
        gap_pct = 100.0 * sum(v <= gap_raw for v in gap_hist) / float(len(gap_hist))
        breadth_count = sum(1 for _, sc in risk_scores if sc > cash_score)
        breadth_pct = 100.0 * breadth_count / float(len(RISK_POOL))
        if breadth_pct >= MAP_BREADTH_THRESHOLD and gap_pct >= MAP_GAP_THRESHOLD:
            quadrant = "TREND_EXPANSION"
        elif breadth_pct >= MAP_BREADTH_THRESHOLD:
            quadrant = "ROTATION_CROWDING"
        elif gap_pct >= MAP_GAP_THRESHOLD:
            quadrant = "NARROW_LEADERSHIP"
        else:
            quadrant = "DEFENSIVE_VOID"
        records.append({
            "date": d,
            "breadth_pct": breadth_pct,
            "gap_percentile": gap_pct,
            "gap_raw": gap_raw,
            "quadrant": quadrant,
        })
    return records[-MAP_RESTORE_TAIL_DAYS:]


def restore_void_episode_on_hot_update(context, signal_date, holdings, snapshot):
    if (
        snapshot is None
        or snapshot.get("quadrant") != "DEFENSIVE_VOID"
        or g.last_output_initialized
        or len(holdings) != 1
    ):
        return False
    records = historical_state_map_tail(signal_date)
    if not records or records[-1].get("date") != signal_date:
        return False
    start = len(records) - 1
    while start > 0 and records[start - 1].get("quadrant") == "DEFENSIVE_VOID":
        start -= 1
    episode = records[start:]
    entry = episode[0]
    current_holding = holdings[0]
    g.last_output_target = current_holding
    g.last_output_initialized = True
    g.void_in_void = True
    g.void_entry_breadth = finite_number(entry.get("breadth_pct"))
    g.void_entry_gap_percentile = finite_number(entry.get("gap_percentile"))
    if current_holding in (US_CARRIER_SYMBOL, CASH_SIGNAL_SYMBOL):
        g.void_incumbent = None
        g.void_routed = True
        g.void_route_target = current_holding
    else:
        g.void_incumbent = current_holding
        g.void_routed = False
        g.void_route_target = None
    streak = 0
    entry_b = g.void_entry_breadth
    entry_g = g.void_entry_gap_percentile
    for rec in episode[1:-1]:
        b = finite_number(rec.get("breadth_pct"))
        gp = finite_number(rec.get("gap_percentile"))
        if b is not None and gp is not None and entry_b is not None and entry_g is not None and b < entry_b and gp < entry_g:
            streak += 1
        else:
            streak = 0
    g.void_deep_streak = streak
    g.void_decision = "VOID_STATE_RESTORED"
    g.void_note = (
        "热更新恢复连续Void：entry=%s，Breadth=%.2f%%，GapPct=%.2f%%，当前持仓=%s，pre-current deep streak=%d"
        % (
            entry.get("date"),
            entry_b if entry_b is not None else float("nan"),
            entry_g if entry_g is not None else float("nan"),
            display(current_holding),
            streak,
        )
    )
    log.info(g.void_note)
    return True


def carrier_age_ok(signal_date):
    try:
        info = get_security_info(US_CARRIER_SYMBOL)
        start = normalize_date(getattr(info, "start_date", None))
        if start is None:
            return False
        return (signal_date - start).days >= CARRIER_MIN_LISTING_DAYS
    except Exception as exc:
        log.warning("513500上市时间读取失败：%s" % exc)
        return False


def reset_void_episode():
    g.void_in_void = False
    g.void_incumbent = None
    g.void_entry_breadth = None
    g.void_entry_gap_percentile = None
    g.void_deep_streak = 0
    g.void_routed = False
    g.void_route_target = None


def resolve_void_target(context, signal_date, rows, base_target, holdings, snapshot):
    if not g.last_output_initialized:
        restored = restore_void_episode_on_hot_update(context, signal_date, holdings, snapshot)
        if not restored:
            g.last_output_target = holdings[0] if len(holdings) == 1 else None
            g.last_output_initialized = True
    if snapshot is None:
        if g.void_in_void:
            target = g.void_route_target if g.void_routed else g.void_incumbent
            g.void_decision = "VOID_MAP_UNAVAILABLE_HOLD"
            g.void_note = "State Map暂不可用；保守保持本次Void既有目标"
        else:
            target = base_target
            g.void_decision = "BASE_MAP_UNAVAILABLE"
            g.void_note = "State Map暂不可用；不新启Void"
        g.last_output_target = target
        return target
    map_is_void = snapshot.get("quadrant") == "DEFENSIVE_VOID"
    breadth = finite_number(snapshot.get("breadth_pct"))
    gap_pct = finite_number(snapshot.get("gap_percentile"))
    raw_leader = snapshot.get("top1")
    exit_blocked_by_premium = (
        g.void_in_void
        and not map_is_void
        and raw_leader is not None
        and raw_leader in g.premium_blacklist
    )
    # State Map继续反映raw市场结构；但如果本次Void退出由不可执行的高溢价raw leader主导，
    # 执行层不允许可执行Top2自动继位，继续沿用既有Void incumbent/route。
    is_void = map_is_void or exit_blocked_by_premium
    if exit_blocked_by_premium:
        log.info(
            "DEFENSIVE_VOID退出被溢价阻止：raw leader=%s处于溢价黑名单；"
            "State Map=%s，继续沿用Void目标"
            % (display(raw_leader), snapshot.get("quadrant"))
        )
    if not is_void:
        if g.void_in_void:
            log.info("DEFENSIVE_VOID退出：恢复后台V1目标%s" % display(base_target))
        reset_void_episode()
        target = base_target
        g.void_decision = "BASE"
        g.void_note = "非Void：执行正常FixV2/V1"
        g.last_output_target = target
        return target
    if not g.void_in_void:
        pre = g.last_output_target
        incumbent = pre if pre is not None else base_target
        g.void_in_void = True
        g.void_incumbent = incumbent
        g.void_entry_breadth = breadth
        g.void_entry_gap_percentile = gap_pct
        g.void_deep_streak = 0
        g.void_routed = False
        g.void_route_target = None
        target = incumbent
        g.void_decision = "VOID_ENTER_FREEZE_PREV"
        g.void_note = (
            "首次进入Void：冻结pre-Void incumbent=%s；entry breadth=%.2f%%，gap pct=%.2f%%"
            % (
                display(incumbent),
                breadth if breadth is not None else float("nan"),
                gap_pct if gap_pct is not None else float("nan"),
            )
        )
        g.last_output_target = target
        return target
    if g.void_routed:
        target = g.void_route_target
        if exit_blocked_by_premium:
            g.void_decision = "VOID_EXIT_BLOCKED_PREMIUM_HOLD_ROUTED"
            g.void_note = (
                "State Map已离开Void，但raw leader=%s因溢价不可执行；"
                "阻止恢复V1，继续已冻结route target=%s"
                % (display(raw_leader), display(target))
            )
        else:
            g.void_decision = "VOID_HOLD_ROUTED"
            g.void_note = "Void尚未退出：继续保持已冻结route target=%s" % display(target)
        g.last_output_target = target
        return target
    entry_b = finite_number(g.void_entry_breadth)
    entry_g = finite_number(g.void_entry_gap_percentile)
    if breadth is not None and gap_pct is not None and entry_b is not None and entry_g is not None and breadth < entry_b and gap_pct < entry_g:
        g.void_deep_streak += 1
    else:
        g.void_deep_streak = 0
    deepened = g.void_deep_streak >= VOID_DEEPEN_STREAK_REQUIRED
    cash_raw = raw_score_from_row(rows, CASH_SIGNAL_SYMBOL)
    incumbent = g.void_incumbent
    if incumbent in ETF_POOL:
        incumbent_raw = raw_score_from_row(rows, incumbent)
    else:
        incumbent_raw = raw_score_on_date(incumbent, signal_date) if incumbent else None
    incumbent_valid = (
        incumbent is not None and incumbent_raw is not None and cash_raw is not None and incumbent_raw > cash_raw
    )
    if incumbent_valid or not deepened:
        target = incumbent
        if exit_blocked_by_premium:
            g.void_decision = "VOID_EXIT_BLOCKED_PREMIUM"
            g.void_note = (
                "State Map已离开Void，但raw leader=%s因溢价不可执行；"
                "不允许可执行Top2继位，继续Void incumbent=%s"
                % (display(raw_leader), display(incumbent))
            )
        elif deepened:
            g.void_decision = "VOID_FREEZE_VALID"
            g.void_note = (
                "Void已深化，但incumbent仍有效：%s raw %.6f > 511220 %.6f，继续冻结"
                % (display(incumbent), incumbent_raw, cash_raw)
            )
        else:
            g.void_decision = "VOID_WAIT_DEEPEN"
            g.void_note = (
                "Void内等待深化：streak=%d/%d；继续%s"
                % (g.void_deep_streak, VOID_DEEPEN_STREAK_REQUIRED, display(incumbent))
            )
        g.last_output_target = target
        return target
    carrier_raw = raw_score_on_date(US_CARRIER_SYMBOL, signal_date)
    carrier_ok = (
        carrier_age_ok(signal_date)
        and carrier_raw is not None
        and cash_raw is not None
        and carrier_raw > cash_raw
        and US_CARRIER_SYMBOL not in g.premium_blacklist
    )
    route_target = US_CARRIER_SYMBOL if carrier_ok else CASH_SIGNAL_SYMBOL
    g.void_routed = True
    g.void_route_target = route_target
    target = route_target
    if carrier_ok:
        g.void_decision = "VOID_DEEP_INVALID_TO_CARRIER"
        g.void_note = (
            "Deepen1 + incumbent失效：%s raw=%s <= 511220 %.6f；513500 raw %.6f > 511220，路由US Carrier"
            % (
                display(incumbent),
                "NA" if incumbent_raw is None else "%.6f" % incumbent_raw,
                cash_raw,
                carrier_raw,
            )
        )
    else:
        g.void_decision = "VOID_DEEP_INVALID_TO_CASH"
        carrier_reason = []
        if not carrier_age_ok(signal_date):
            carrier_reason.append("上市未满365日")
        if carrier_raw is None or cash_raw is None or not (carrier_raw > cash_raw):
            carrier_reason.append("513500 raw score未战胜511220")
        if US_CARRIER_SYMBOL in g.premium_blacklist:
            carrier_reason.append("513500触发10%溢价执行保护")
        g.void_note = "Deepen1 + incumbent失效：转511220；Carrier未通过：%s" % ("；".join(carrier_reason) or "未知原因")
    g.last_output_target = target
    return target


def build_raw_ranking_after_close(context):
    trade_date = normalize_date(context.current_dt)
    rows = rank_on_date(trade_date)
    raw_ranked = select_raw_ranked(rows)
    g.pending_rows = rows
    g.pending_rows_date = trade_date
    g.pending_signal_date = trade_date
    g.pending_target = None
    g.pending_ranked = None
    g.pending_target_actual_close = None
    g.pending_exit_actual_closes = {}
    g.entry_checked = False
    g.entry_blocked = False
    g.entry_reason = None
    g.pending_buy_target = None
    g.pending_target_weight = 1.0
    g.pending_preserve_shares = False
    g.pending_preserve_portfolio = False
    g.pending_m1_diagnostics = None
    try:
        g.pending_map_snapshot = state_map_snapshot(trade_date, rows)
    except Exception as exc:
        g.pending_map_snapshot = None
        log.warning("收盘后State Map计算失败%s：%s" % (trade_date, exc))
    if raw_ranked is None:
        detail = "无raw合格候选"
    else:
        detail = "%s score=%.6f annual=%.2f%% R2=%.4f" % (
            display(raw_ranked["symbol"]),
            raw_ranked["score"],
            raw_ranked["annualized"] * 100,
            raw_ranked["r_squared"],
        )
    if g.pending_map_snapshot:
        m = g.pending_map_snapshot
        map_text = (
            "%s | Breadth %.2f%%(%d/%d) | GapPct %.2f%% | rawTop=%s/%s"
            % (
                m["quadrant"],
                m["breadth_pct"],
                m["breadth_count"],
                len(RISK_POOL),
                m["gap_percentile"],
                display(m["top1"]),
                display(m["top2"]),
            )
        )
    else:
        map_text = "State Map暂不可用"
    log.info("%s | 已冻结%s评分；%s；次日开盘前补查净值并执行V1+Void状态机" % (detail, trade_date, map_text))
    log_raw_ranking_diagnostics(rows)


def finalize_next_day_plan_before_open(context):
    signal_date = normalize_date(getattr(context, "previous_date", None))
    if signal_date is None:
        log.warning("开盘前无法取得上一交易日，取消生成当日计划")
        return
    rebuilt = False
    if g.pending_rows_date != signal_date or not g.pending_rows:
        log.warning("未找到%s冻结评分，开盘前重新计算" % signal_date)
        rows = rank_on_date(signal_date)
        g.pending_rows = rows
        g.pending_rows_date = signal_date
        rebuilt = True
    else:
        rows = g.pending_rows
    if rebuilt:
        log_raw_ranking_diagnostics(rows)
    g.pending_signal_date = signal_date
    refresh_premium_blacklist_for_date(signal_date)
    holdings = managed_holdings(context)
    if not g.void_in_void:
        g.v1_current_target = holdings[0] if len(holdings) == 1 and holdings[0] in RISK_POOL else None
        g.v1_initialized = True
    challenger, challenger_row, cash_pool_score = choose_fixv2_challenger(rows)
    base_target = resolve_v1_target(context, signal_date, rows, challenger, holdings)
    snapshot = getattr(g, "pending_map_snapshot", None)
    if not snapshot or normalize_date(snapshot.get("date")) != signal_date:
        try:
            snapshot = state_map_snapshot(signal_date, rows)
        except Exception as exc:
            snapshot = None
            log.warning("开盘前State Map重建失败%s：%s" % (signal_date, exc))
    g.pending_map_snapshot = snapshot
    target = resolve_void_target(context, signal_date, rows, base_target, holdings, snapshot)
    if target not in holdings:
        reason = premium_entry_block_reason(target)
        if reason:
            target = execution_veto_fallback(context, reason)
    if challenger is not None:
        ranked_symbol = challenger
    else:
        cash_raw = raw_score_from_row(rows, CASH_SIGNAL_SYMBOL)
        ranked_symbol = CASH_SIGNAL_SYMBOL if cash_raw is not None else None
    g.pending_target = target
    (
        target,
        g.pending_target_weight,
        g.pending_preserve_shares,
        g.pending_preserve_portfolio,
        m1_weight_note,
        g.pending_m1_diagnostics,
    ) = build_m1_position_plan(context, signal_date, target, holdings)
    g.pending_target = target
    g.pending_buy_weight = None
    g.pending_ranked = ranked_symbol
    g.pending_target_actual_close = actual_daily_close_on_date(target, signal_date) if target else None
    g.pending_exit_actual_closes = {
        symbol: actual_daily_close_on_date(symbol, signal_date)
        for symbol in holdings
    }
    g.entry_checked = False
    g.entry_blocked = False
    g.entry_reason = None
    g.pending_buy_target = None
    if challenger_row is None:
        best_risk_text = "无可执行风险候选"
    else:
        best_risk_text = "%s score=%.6f annual=%.2f%% R2=%.4f" % (
            display(challenger_row["symbol"]),
            challenger_row["score"],
            challenger_row["annualized"] * 100,
            challenger_row["r_squared"],
        )
    cash_text = "NA" if cash_pool_score is None else "%.6f" % cash_pool_score
    if snapshot:
        map_text = (
            "%s｜Breadth %.2f%%(%d/%d)｜Gap %.6f｜GapPct %.2f%%"
            % (
                snapshot["quadrant"],
                snapshot["breadth_pct"],
                snapshot["breadth_count"],
                len(RISK_POOL),
                snapshot["gap_raw"],
                snapshot["gap_percentile"],
            )
        )
    else:
        map_text = "State Map不可用"
    plan = "现金" if target is None else display(target)
    premium_blocked = "、".join(display(symbol) for symbol in sorted(g.premium_blacklist)) or "无"
    premium_pending = "、".join(display(symbol) for symbol in sorted(g.premium_nav_pending)) or "无"
    log.info("使用%s评分；溢价阈值%.0f%%，恢复需连续%d个已确认净值日" % (signal_date, premium_limit_pct(), PREMIUM_RECOVERY_DAYS))
    log_execution_diagnostics(rows)
    log.info("FixV2 challenger=%s；511220 pool score=%s；V1=%s；base=%s" % (display(challenger), cash_text, g.v1_decision, display(base_target)))
    if g.v1_note:
        log.info("V1说明：%s" % g.v1_note)
    log.info("State Map：%s" % map_text)
    log.info("Void Route：%s | %s" % (g.void_decision, g.void_note))
    m1_detail = m1_diagnostics_text(g.pending_m1_diagnostics)
    log.info(
        "最终目标：%s；目标仓位 %.2f%%（%s）；M1诊断：%s | 当前溢价剔除：%s | 净值待发布/滞后：%s"
        % (plan, g.pending_target_weight * 100, m1_weight_note, m1_detail, premium_blocked, premium_pending)
    )
    notify(
        context,
        "FixV2/V1 + Void Route：当日执行计划",
        "<b>信号日期：</b>%s"
        "<br><b>风险Challenger：</b>%s"
        "<br><b>511220 pool score：</b>%s"
        "<br><b>V1：</b>%s｜%s"
        "<br><b>State Map：</b>%s"
        "<br><b>Void Route：</b>%s｜%s"
        "<br><b>最终目标：</b>%s"
        "<br><b>目标仓位：</b>%.2f%%（%s）"
        "<br><b>M1诊断：</b>%s"
        "<br><b>执行候选Top%d：</b><br>%s"
        "<br><b>确认溢价&gt;%.0f%%的过滤项：</b><br>%s"
        "<br><b>净值待发布/滞后：</b>%s"
        "<br>09:31跳空/计划退出仓急跌检查；14:00卖出；14:05回撤检查后买入。"
        % (
            signal_date,
            best_risk_text,
            cash_text,
            g.v1_decision,
            g.v1_note or "",
            map_text,
            g.void_decision,
            g.void_note or "",
            plan,
            g.pending_target_weight * 100,
            m1_weight_note,
            m1_detail,
            RANK_LOG_TOP_N,
            execution_top3_html(rows),
            premium_limit_pct(),
            premium_filtered_html(rows),
            premium_pending,
        ),
    )



def execution_incumbent_valid(symbol, rows):
    if symbol == CASH_SIGNAL_SYMBOL:
        return True
    if symbol in g.premium_blacklist:
        return False
    if symbol == US_CARRIER_SYMBOL:
        raw = raw_score_on_date(symbol, g.pending_signal_date)
        cash = raw_score_from_row(rows, CASH_SIGNAL_SYMBOL)
        return raw is not None and cash is not None and raw > cash
    return v1_incumbent_valid(rows, symbol)


def execution_veto_fallback(context, reason):
    """只保留实际持有且仍有效的旧仓；不凭虚拟V1目标假定已成交。"""
    holdings = managed_holdings(context)
    target = CASH_SIGNAL_SYMBOL if g.void_in_void and g.void_routed else None
    if len(holdings) == 1 and execution_incumbent_valid(holdings[0], g.pending_rows):
        symbol = holdings[0]
        close = actual_daily_close_on_date(symbol, g.pending_signal_date)
        price, error = current_price(symbol)
        # 旧仓独立急跌保护优先；停牌时保留既有有效仓位，不制造卖出成功。
        if not (close and price and price / close < NEXT_DAY_PRICE_FLOOR):
            target = symbol
    g.v1_current_target = target if target in RISK_POOL else None
    g.v1_initialized = True
    g.v1_decision = "EXECUTION_VETO_HOLD" if target in holdings else "EXECUTION_VETO_DEFENSIVE"
    g.v1_note = "%s；执行目标=%s" % (reason, display(target))
    g.last_output_target = target
    g.last_output_initialized = True
    if g.void_in_void and g.void_routed:
        g.void_route_target = target
    log.warning(g.v1_note)
    return target


def entry_preflight_reason(context, target, check_drawdown=False):
    reason = premium_entry_block_reason(target)
    if reason:
        return reason
    price, error = current_price(target)
    if price is None:
        return error or "目标不可交易"
    try:
        item = get_current_data()[target]
        limit = finite_number(getattr(item, "high_limit", None))
        if limit is not None and price >= limit:
            return "目标涨停，无法可靠买入"
    except Exception as exc:
        return "目标交易状态读取失败：%s" % exc
    if check_drawdown:
        high = today_high(target, context, price)
        if high is None:
            return "分钟高点不可用"
        if 1.0 - price / high >= INTRADAY_HIGH_DRAWDOWN_LIMIT:
            return "卖出前目标日内高点回撤已超限"
    return None


def check_gap_at_0931(context):
    if g.pending_signal_date is None:
        return
    if M1_POSITION_CONTROL_ENABLED and getattr(g, "pending_preserve_portfolio", False):
        g.entry_checked = True
        g.entry_reason = "Void多持仓异常：冻结账户现状，不执行09:31自动交易"
        log.warning(g.entry_reason)
        return
    target = g.pending_target
    holdings = managed_holdings(context)
    for symbol in [item for item in holdings if item != target]:
        close = (g.pending_exit_actual_closes or {}).get(symbol)
        price, error = current_price(symbol)
        if close and price and price / close < NEXT_DAY_PRICE_FLOOR:
            safe_target_value(symbol, 0)
            log.warning("09:31计划退出仓急跌卖出%s：%.4f/%.4f < %.2f" % (display(symbol), price, close, NEXT_DAY_PRICE_FLOOR))
        elif error:
            log.warning("09:31旧仓价格不可用%s：%s" % (display(symbol), error))
    if M1_POSITION_CONTROL_ENABLED and g.pending_target_weight <= 0:
        g.entry_checked = True
        g.entry_reason = "M1目标仓位为0：不执行买入预检查"
        log.info(g.entry_reason)
        return
    if (m1_holding_matches_plan(context, target) if M1_POSITION_CONTROL_ENABLED
            else holdings_match_target(holdings, target)):
        g.entry_checked = True
        g.entry_reason = "当前持仓已等于最终目标，无需调仓"
        log.info(g.entry_reason)
        return
    if target is None:
        g.entry_checked = True
        g.entry_reason = "最终目标为普通现金，不需要买入检查"
        log.info(g.entry_reason)
        return
    g.entry_checked = True
    reason = entry_preflight_reason(context, target)
    if reason:
        g.entry_blocked = True
        g.entry_reason = reason
        log.warning(reason)
        return
    close = g.pending_target_actual_close
    if close:
        price, error = current_price(target)
    else:
        price, error = None, "信号日实际收盘价不可用"
    if price is None:
        g.entry_blocked = True
        g.entry_reason = "%s，取消今日买入" % error
    elif price / close < NEXT_DAY_PRICE_FLOOR:
        g.entry_blocked = True
        g.entry_reason = "09:31跳空%.4f/%.4f < %.2f，取消今日买入" % (price, close, NEXT_DAY_PRICE_FLOOR)
    else:
        g.entry_reason = "09:31跳空检查通过 %.4f/%.4f" % (price, close)
    log.info(g.entry_reason)


def execute_sells_at_1400(context):
    if M1_POSITION_CONTROL_ENABLED:
        execute_m1_weight_sells_at_1400(context)
        return
    if g.pending_signal_date is None:
        return
    target = g.pending_target
    holdings = managed_holdings(context)
    if holdings_match_target(holdings, target):
        clear_pending()
        return
    if target is not None and not g.entry_checked:
        g.entry_blocked = True
        g.entry_reason = "09:31检查缺失"
    if target is not None and not g.entry_blocked:
        reason = entry_preflight_reason(context, target, check_drawdown=True)
        if reason:
            g.entry_blocked = True
            g.entry_reason = reason
    effective_target = target
    if target is not None and g.entry_blocked:
        effective_target = execution_veto_fallback(context, g.entry_reason or "候选受阻")
        g.pending_target = effective_target
        if holdings_match_target(holdings, effective_target):
            clear_pending()
            return
    for symbol in holdings:
        if symbol != effective_target:
            order, error = safe_target_value(symbol, 0)
            if error:
                log.warning("14:00卖出%s失败：%s" % (display(symbol), error))
    if effective_target is None:
        log.info("14:00转现金：%s" % (g.entry_reason or "策略目标为现金"))
        clear_pending()
    else:
        g.pending_buy_target = effective_target


def today_high(symbol, context, observed_price):
    try:
        bars = get_bars(
            symbol,
            count=INTRADAY_MINUTE_BAR_COUNT,
            unit="1m",
            fields=["date", "high"],
            include_now=True,
        )
        today = normalize_date(context.current_dt)
        highs = [
            float(high)
            for date, high in zip(bars["date"], bars["high"])
            if str(date)[:10] == str(today) and np.isfinite(high) and high > 0
        ]
        return max(highs + [observed_price]) if highs else None
    except Exception:
        return None


def execute_buy_at_1405(context):
    if M1_POSITION_CONTROL_ENABLED:
        execute_m1_weight_buy_at_1405(context)
        return
    target = g.pending_buy_target
    if target is None or g.pending_signal_date is None:
        return
    blockers = [symbol for symbol in managed_holdings(context) if symbol != target]
    if blockers:
        execution_veto_fallback(context, "14:05旧仓未清：%s" % blockers)
        clear_pending()
        return
    reason = entry_preflight_reason(context, target)
    if reason:
        execution_veto_fallback(context, "14:05取消买入：%s" % reason)
        clear_pending()
        return
    price, error = current_price(target)
    high = today_high(target, context, price) if price else None
    if high is None:
        execution_veto_fallback(context, "14:05分钟高点或现价不可用：%s" % (error or "无高点"))
        clear_pending()
        return
    drawdown = 1.0 - price / high
    if drawdown >= INTRADAY_HIGH_DRAWDOWN_LIMIT:
        log.warning(
            "14:05取消买入%s：日内高点回撤%.2f%% >= %.2f%%"
            % (display(target), drawdown * 100, INTRADAY_HIGH_DRAWDOWN_LIMIT * 100)
        )
        execution_veto_fallback(context, "14:05回撤超限")
        clear_pending()
        return
    order, order_error = safe_target_value(target, context.portfolio.total_value)
    if order_error:
        execution_veto_fallback(context, "14:05买入%s失败：%s" % (display(target), order_error))
    else:
        log.info("14:05提交买入%s；日内回撤%.2f%%；Void=%s" % (display(target), drawdown * 100, g.void_decision))
    clear_pending()


def clear_pending():
    g.pending_target = None
    g.pending_ranked = None
    g.pending_signal_date = None
    g.pending_target_actual_close = None
    g.pending_exit_actual_closes = {}
    g.pending_map_snapshot = None
    g.entry_checked = False
    g.entry_blocked = False
    g.entry_reason = None
    g.pending_buy_target = None
    g.pending_buy_weight = None
    g.pending_target_weight = 1.0
    g.pending_preserve_shares = False
    g.pending_preserve_portfolio = False
    g.pending_m1_diagnostics = None

