# -*- coding: utf-8 -*-
"""
SEVEN_STAR_F1_CASH_DEFENSE_FROZEN_V1 —— 聚宽回测/模拟盘版

冻结规则：
1. 固定7只候选池，每日收盘使用26个收盘价计算名义h=10直接权重回归；
2. 保留历史legacy混合R²以及显式趋势/双负反转分支；
3. D2过滤最近3个交易日中严格低于-3%的单日跌幅；
4. 反转分支要求最近一次严格低于-3%的冲击距今3至20个交易日；
5. 每日Top1；若511220成为Top1，实际目标映射为现金；无合格候选也持有现金；
6. 收盘后生成信号，下一交易日开盘卖出，09:31/09:35尝试买入。

PushPlus：
- 仓库版本不保存Token；部署到聚宽时请在运行副本中填写PUSHPLUS_TOKEN；
- 默认仅模拟盘发送，历史回测绝不发送；
- 每日收盘发送下一交易日计划，发生调仓时发送订单提交/失败通知；
- 通知失败只记日志，不中断信号和交易。

注意：聚宽卖出成交后现金才可用于新买单，因此跨ETF切换采用开盘卖出、
09:31首次买入、09:35最后重试。它比本地VectorBT“同一开盘价卖出并买入”
多出最多5分钟执行差异，必须用聚宽回测单独核验。
"""

import datetime
import json
import math

import numpy as np
import requests
from jqdata import *


STRATEGY_ID = "SEVEN_STAR_F1_CASH_DEFENSE_FROZEN_V1"
PUSHPLUS_TOKEN = ""
PUSHPLUS_URL = "https://www.pushplus.plus/send"
PUSHPLUS_NOTIFY_DAILY_SIGNAL = True
PUSHPLUS_SEND_IN_BACKTEST = False

LOOKBACK_DAYS = 25
HALF_LIFE = 10.0
DAILY_DROP_FLOOR = 0.97
REVERSAL_DROP_THRESHOLD = -0.03
REVERSAL_SHOCK_AGE_MIN = 3
REVERSAL_SHOCK_AGE_MAX = 20
HISTORY_COUNT = 80

ETF_POOL = [
    "518880.XSHG",
    "159985.XSHE",
    "501018.XSHG",
    "161226.XSHE",
    "513100.XSHG",
    "159915.XSHE",
    "511220.XSHG",
]
ETF_NAMES = {
    "518880.XSHG": "黄金ETF",
    "159985.XSHE": "豆粕ETF",
    "501018.XSHG": "南方原油",
    "161226.XSHE": "白银LOF",
    "513100.XSHG": "纳指ETF",
    "159915.XSHE": "创业板ETF",
    "511220.XSHG": "城投债ETF（现金信号）",
}
CASH_SIGNAL_SYMBOL = "511220.XSHG"


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
    reset_persistent_state()
    register_schedules()
    log.info("%s 聚宽版启动；PushPlus仅模拟盘发送" % STRATEGY_ID)


def process_initialize(context):
    """模拟盘每日进程恢复时重新装载不持久化的Token变量。"""
    ensure_persistent_state()
    load_pushplus_token()


def after_code_changed(context):
    """模拟盘替换代码后重新注册任务，同时保留尚未执行的隔夜信号。"""
    ensure_persistent_state()
    load_pushplus_token()
    unschedule_all()
    register_schedules()
    log.info("策略代码已更新，定时任务已重新注册")


def reset_persistent_state():
    g.pending_target = None
    g.pending_ranked_symbol = None
    g.pending_signal_date = None
    g.pending_buy_target = None
    g.pending_action_text = None
    g.last_signal_notice_key = None
    g.last_execution_notice_key = None


def ensure_persistent_state():
    defaults = {
        "pending_target": None,
        "pending_ranked_symbol": None,
        "pending_signal_date": None,
        "pending_buy_target": None,
        "pending_action_text": None,
        "last_signal_notice_key": None,
        "last_execution_notice_key": None,
    }
    for key, value in defaults.items():
        if not hasattr(g, key):
            setattr(g, key, value)


def register_schedules():
    run_daily(execute_pending_sell_at_open, time="open")
    run_daily(execute_pending_buy_first, time="09:31")
    run_daily(execute_pending_buy_final, time="09:35")
    run_daily(build_pending_target_after_close, time="after_close")
    run_daily(daily_summary, time="15:05")


def load_pushplus_token():
    g.__pushplus_token = str(PUSHPLUS_TOKEN).strip()
    if g.__pushplus_token:
        log.info("PushPlus Token已从策略配置加载")
    else:
        log.warning("PushPlus未启用：策略中的PUSHPLUS_TOKEN为空")


def is_sim_trade(context):
    run_params = getattr(context, "run_params", None)
    return str(getattr(run_params, "type", "")) == "sim_trade"


def pushplus_allowed(context):
    if is_sim_trade(context):
        return True
    return bool(PUSHPLUS_SEND_IN_BACKTEST)


def send_pushplus(context, title, content, notice_key):
    if not pushplus_allowed(context):
        return False
    token = getattr(g, "__pushplus_token", "")
    if not token:
        load_pushplus_token()
        token = getattr(g, "__pushplus_token", "")
    if not token:
        return False
    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html",
        "channel": "wechat",
    }
    try:
        response = requests.post(
            PUSHPLUS_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        result = response.json()
        if int(result.get("code", -1)) != 200:
            raise RuntimeError("code=%s msg=%s" % (result.get("code"), result.get("msg")))
        log.info("PushPlus发送成功：%s" % notice_key)
        return True
    except Exception as exc:
        log.warning("PushPlus发送失败（不影响交易）：%s" % exc)
        return False


def clean_price_values(values):
    array = np.asarray(values, dtype=float)
    return array[np.isfinite(array) & (array > 0)]


def trading_days_since_last_drop(values):
    values = clean_price_values(values)
    if len(values) < 2:
        return None
    ratios = values[1:] / values[:-1]
    positions = np.flatnonzero(ratios < 1.0 + REVERSAL_DROP_THRESHOLD)
    if len(positions) == 0:
        return None
    # ratios位置0对应价格位置1，因此当前价格位置减去冲击价格位置。
    shock_price_position = int(positions[-1]) + 1
    return int(len(values) - 1 - shock_price_position)


def evaluate_price_values(values):
    """纯计算函数；与本地冻结F1评分契约逐项一致。"""
    values = clean_price_values(values)
    result = {
        "eligible": False,
        "score": None,
        "raw_score": None,
        "annualized": None,
        "r_squared": None,
        "signal_branch": "invalid",
        "reversal_shock_age": None,
        "reasons": [],
    }
    if len(values) < LOOKBACK_DAYS + 1:
        result["reasons"].append("insufficient_history")
        return result

    recent = values[-(LOOKBACK_DAYS + 1):]
    y = np.log(recent)
    x = np.arange(len(y), dtype=float)
    ages = np.arange(len(y) - 1, -1, -1, dtype=float)
    weights = np.power(0.5, ages / HALF_LIFE)
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    fitted = float(slope) * x + float(intercept)

    # 冻结legacy混合R²：残差用名义权重q，而拟合目标实际使用q²；中心为非加权均值。
    ss_res = float(np.sum(weights * np.square(y - fitted)))
    ss_tot = float(np.sum(weights * np.square(y - np.mean(y))))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot else 0.0
    annualized = math.exp(float(slope) * 250.0) - 1.0
    raw_score = annualized * r_squared

    if annualized > 0.0 and r_squared > 0.0:
        branch = "trend"
        score = abs(annualized) * abs(r_squared)
    elif annualized < 0.0 and r_squared < 0.0:
        branch = "reversal"
        score = abs(annualized) * abs(r_squared)
    else:
        branch = "sign_mismatch"
        score = 0.0

    result.update({
        "score": float(score),
        "raw_score": float(raw_score),
        "annualized": float(annualized),
        "r_squared": float(r_squared),
        "signal_branch": branch,
    })
    if not np.isfinite(score) or score <= 0.0:
        result["reasons"].append("score_not_positive")

    if branch == "reversal":
        shock_age = trading_days_since_last_drop(values)
        result["reversal_shock_age"] = shock_age
        if shock_age is None:
            result["reasons"].append("reversal_no_prior_shock")
        elif shock_age < REVERSAL_SHOCK_AGE_MIN:
            result["reasons"].append("reversal_shock_too_recent")
        elif shock_age > REVERSAL_SHOCK_AGE_MAX:
            result["reasons"].append("reversal_shock_too_old")

    daily_ratios = values[-3:] / values[-4:-1]
    if len(daily_ratios) == 3 and float(np.min(daily_ratios)) < DAILY_DROP_FLOOR:
        result["reasons"].append("recent_daily_drop")

    result["eligible"] = len(result["reasons"]) == 0
    return result


def get_completed_daily_prices(symbol, context):
    frame = get_price(
        symbol,
        end_date=context.current_dt,
        count=HISTORY_COUNT,
        frequency="daily",
        fields=["close", "paused"],
        skip_paused=False,
        fq="post",
    )
    if frame is None or frame.empty or "close" not in frame:
        return None
    frame = frame.dropna(subset=["close"])
    if frame.empty:
        return None
    last_date = frame.index[-1]
    last_date = last_date.date() if hasattr(last_date, "date") else last_date
    if last_date != context.current_dt.date():
        return None
    if "paused" in frame and bool(frame["paused"].iloc[-1]):
        return None
    return frame["close"].values


def rank_etfs_after_close(context):
    rows = []
    for symbol in ETF_POOL:
        try:
            values = get_completed_daily_prices(symbol, context)
            if values is None:
                result = {"eligible": False, "reasons": ["missing_completed_bar"]}
            else:
                result = evaluate_price_values(values)
            result["symbol"] = symbol
            rows.append(result)
        except Exception as exc:
            rows.append({"symbol": symbol, "eligible": False, "reasons": ["data_error:%s" % exc]})
            log.warning("计算%s失败：%s" % (symbol, exc))
    eligible = [row for row in rows if row.get("eligible")]
    # 本地冻结规则：分数相同时选择代码字典序较大的标的。
    ranked = max(eligible, key=lambda row: (row["score"], row["symbol"])) if eligible else None
    return ranked, rows


def model_target_from_ranked(ranked_symbol):
    if ranked_symbol is None or ranked_symbol == CASH_SIGNAL_SYMBOL:
        return None
    return ranked_symbol


def managed_holdings(context):
    holdings = []
    # 聚宽positions不是普通dict，逐个查询不存在的代码会产生大量兼容性警告。
    for symbol, position in context.portfolio.positions.items():
        if symbol in ETF_POOL and position.total_amount > 0:
            holdings.append(symbol)
    return holdings


def display_symbol(symbol):
    if symbol is None:
        return "现金"
    return "%s %s" % (symbol.split(".")[0], ETF_NAMES.get(symbol, ""))


def describe_action(current_holdings, target):
    if len(current_holdings) == 1 and current_holdings[0] == target:
        return "继续持有%s，不调仓" % display_symbol(target)
    current_text = "、".join(display_symbol(symbol) for symbol in current_holdings) if current_holdings else "现金"
    if target is None:
        return "下一交易日开盘卖出%s，目标转为现金" % current_text if current_holdings else "继续持有现金"
    if current_holdings:
        return "下一交易日开盘卖出%s，随后买入%s" % (current_text, display_symbol(target))
    return "下一交易日开盘买入%s" % display_symbol(target)


def build_pending_target_after_close(context):
    ranked, audits = rank_etfs_after_close(context)
    ranked_symbol = ranked["symbol"] if ranked is not None else None
    target = model_target_from_ranked(ranked_symbol)
    signal_date = context.current_dt.date()
    current_holdings = managed_holdings(context)
    action_text = describe_action(current_holdings, target)

    g.pending_ranked_symbol = ranked_symbol
    g.pending_target = target
    g.pending_signal_date = signal_date
    g.pending_buy_target = None
    g.pending_action_text = action_text

    if ranked is None:
        detail = "无合格候选"
    else:
        detail = "%s | branch=%s | score=%.6f | annual=%.2f%% | R2=%.6f" % (
            display_symbol(ranked_symbol),
            ranked["signal_branch"],
            ranked["score"],
            ranked["annualized"] * 100.0,
            ranked["r_squared"],
        )
        if ranked.get("reversal_shock_age") is not None:
            detail += " | shock_age=%d" % ranked["reversal_shock_age"]

    log.info("收盘信号 %s | ranked=%s | target=%s | %s" % (
        signal_date, ranked_symbol or "NONE", target or "CASH", action_text
    ))
    notice_key = "signal:%s:%s" % (signal_date, target or "CASH")
    if PUSHPLUS_NOTIFY_DAILY_SIGNAL and g.last_signal_notice_key != notice_key:
        content = (
            "<b>策略：</b>%s<br>"
            "<b>信号日：</b>%s<br>"
            "<b>排名结果：</b>%s<br>"
            "<b>实际目标：</b>%s<br>"
            "<b>模拟盘当前持仓：</b>%s<br>"
            "<b>下单计划：</b>%s<br><br>"
            "通知仅供人工核对；真实下单前请确认模拟盘成交、价格、可用资金和ETF状态。"
        ) % (
            STRATEGY_ID,
            signal_date,
            detail,
            display_symbol(target),
            "、".join(display_symbol(symbol) for symbol in current_holdings) if current_holdings else "现金",
            action_text,
        )
        if send_pushplus(context, "F1现金防守：次日计划", content, notice_key):
            g.last_signal_notice_key = notice_key


def safe_order_target_value(symbol, target_value):
    try:
        current = get_current_data()[symbol]
        price = float(current.last_price)
        if current.paused or not np.isfinite(price) or price <= 0:
            return None, "%s停牌或价格无效" % symbol
        position = context_position = None
        # 下方涨跌停判断仅在聚宽返回有效边界时启用；部分跨境ETF边界可能为NaN或0。
        high_limit = float(current.high_limit) if current.high_limit is not None else np.nan
        low_limit = float(current.low_limit) if current.low_limit is not None else np.nan
        if target_value > 0 and np.isfinite(high_limit) and high_limit > 0 and price >= high_limit:
            return None, "%s处于涨停/买入受限" % symbol
        if target_value <= 0 and np.isfinite(low_limit) and low_limit > 0 and price <= low_limit:
            return None, "%s处于跌停/卖出受限" % symbol
        order = order_target_value(symbol, target_value)
        if order is None:
            return None, "%s订单未创建" % symbol
        return order, None
    except Exception as exc:
        return None, "%s下单异常：%s" % (symbol, exc)


def notify_execution(context, status, detail):
    signal_date = g.pending_signal_date
    notice_key = "execution:%s:%s:%s" % (signal_date, g.pending_target or "CASH", status)
    if g.last_execution_notice_key == notice_key:
        return
    content = (
        "<b>策略：</b>%s<br>"
        "<b>原信号日：</b>%s<br>"
        "<b>模拟盘执行状态：</b>%s<br>"
        "<b>详情：</b>%s<br>"
        "<b>模型目标：</b>%s<br><br>"
        "请以聚宽订单与成交回报为准，再决定是否进行真实下单。"
    ) % (STRATEGY_ID, signal_date, status, detail, display_symbol(g.pending_target))
    if send_pushplus(context, "F1现金防守：模拟盘执行", content, notice_key):
        g.last_execution_notice_key = notice_key


def execute_pending_sell_at_open(context):
    if g.pending_signal_date is None:
        return
    target = g.pending_target
    holdings = managed_holdings(context)
    if len(holdings) == 1 and holdings[0] == target:
        log.info("执行信号 %s：目标未变，继续持有%s" % (g.pending_signal_date, target))
        clear_pending_execution()
        return

    submitted = []
    errors = []
    for symbol in holdings:
        if symbol == target:
            continue
        order, error = safe_order_target_value(symbol, 0)
        if order is not None:
            submitted.append("卖出%s" % display_symbol(symbol))
        if error:
            errors.append(error)

    if target is None:
        detail = "；".join(submitted + errors) if submitted or errors else "当前已经是现金"
        notify_execution(context, "已提交转现金订单" if not errors else "转现金订单存在异常", detail)
        clear_pending_execution()
        return

    g.pending_buy_target = target
    if submitted or errors:
        log.info("开盘卖出阶段：%s" % "；".join(submitted + errors))


def execute_pending_buy_first(context):
    attempt_pending_buy(context, final_attempt=False)


def execute_pending_buy_final(context):
    attempt_pending_buy(context, final_attempt=True)


def attempt_pending_buy(context, final_attempt):
    target = g.pending_buy_target
    if target is None or g.pending_signal_date is None:
        return
    blocking = [symbol for symbol in managed_holdings(context) if symbol != target]
    if blocking:
        detail = "卖单尚未完全成交，仍持有：%s" % "、".join(display_symbol(symbol) for symbol in blocking)
        if final_attempt:
            log.warning(detail)
            notify_execution(context, "买入已取消，需要人工检查", detail)
            clear_pending_execution()
        else:
            log.info("09:31暂缓买入：%s" % detail)
        return

    order, error = safe_order_target_value(target, context.portfolio.total_value)
    if order is not None:
        detail = "已提交买入%s；请查看聚宽成交回报" % display_symbol(target)
        log.info(detail)
        notify_execution(context, "买入订单已提交", detail)
        clear_pending_execution()
    elif final_attempt:
        detail = error or "未知买入失败"
        log.warning(detail)
        notify_execution(context, "买入失败，需要人工检查", detail)
        clear_pending_execution()
    else:
        log.info("09:31买入未提交，09:35重试：%s" % (error or "未知原因"))


def clear_pending_execution():
    g.pending_target = None
    g.pending_ranked_symbol = None
    g.pending_signal_date = None
    g.pending_buy_target = None
    g.pending_action_text = None


def daily_summary(context):
    holdings = []
    for symbol in managed_holdings(context):
        position = context.portfolio.positions[symbol]
        holdings.append("%s:%d" % (display_symbol(symbol), position.total_amount))
    log.info("日终 | value=%.2f cash=%.2f holdings=%s pending=%s" % (
        context.portfolio.total_value,
        context.portfolio.available_cash,
        holdings or ["CASH"],
        g.pending_target or "CASH" if g.pending_signal_date is not None else "NONE",
    ))
