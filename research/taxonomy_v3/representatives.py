"""Pre-signal selector. Input schema intentionally has no score/return fields.

Decision date means start of that exchange session. Calendar is supplied by
caller; never infer yesterday from a fund's sparse/filtered quote dates.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import pandas as pd
from .model import classifications_at


@dataclass(frozen=True)
class Policy:
    window: int = 60
    min_history: int = 200
    min_mean_amount: float = 3_000_000.0
    recent_sessions: int = 10
    max_abs_premium: float = 0.03
    max_tracking_error: float | None = None


def select_representatives(classifications: list[dict], bars: pd.DataFrame,
                           calendar: list[str], date: str,
                           policy: Policy = Policy(),
                           risk_observations: list[dict] | None = None,
                           group_field: str = "exposure_id") -> dict:
    if group_field not in {"exposure_id", "exact_index_key"}:
        raise ValueError("only exact-index or approved fine-exposure selection is allowed")
    if calendar != sorted(set(calendar)) or date not in calendar:
        raise ValueError("explicit sorted unique exchange calendar must include decision date")
    if policy.window < 1 or policy.min_history < 1 or not 1 <= policy.recent_sessions <= policy.window:
        raise ValueError("invalid selector policy")
    active, excluded = classifications_at(classifications, date)
    group_members = {}
    for r in active:
        identity = (r['exact_index_key'], r['tracking_mode'], r.get('region_primary'), r.get('exposure_type'))
        previous = group_members.setdefault(r.get(group_field), identity)
        if previous != identity:
            raise ValueError('unapproved cross-index/strategy/region/asset exposure merge')
    i = calendar.index(date)
    if i < policy.window:
        return dict(date=date, representatives=[], eligible=[], excluded=excluded + [
            dict(symbol=r['symbol'], date=date, reason="INSUFFICIENT_CALENDAR") for r in active])
    prior = calendar[i-1]
    window = calendar[i-policy.window:i]
    # Drop all current/future rows BEFORE inspection, including malformed future
    # duplicates. Future source data cannot change a past selection or its errors.
    b = bars.loc[bars["date"].astype(str).str[:10] < date].copy()
    b["date"] = b["date"].astype(str).str[:10]
    b["symbol"] = b["symbol"].astype(str).str.zfill(6)
    if b.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate historical bar; resolve source conflict explicitly")
    if not set(b.date).issubset(set(calendar[:i])):
        raise ValueError("historical bars contain dates absent from supplied calendar")
    groups = {s: g.set_index("date").sort_index() for s, g in b.groupby("symbol")}
    eligible = []
    for r in active:
        symbol = r["symbol"]
        reason = None
        g = groups.get(symbol)
        if g is not None:
            # Conversion predecessor histories cannot satisfy the current
            # listed product's minimum history requirement.
            g = g.loc[g.index >= r['listing_date']]
        if not r.get(group_field):
            reason = "GROUP_UNVERIFIED"
        elif not r.get('execution_attributes_verified'):
            reason = 'EXECUTION_ATTRIBUTES_UNVERIFIED'
        elif g is None or prior not in g.index:
            reason = "MISSING_PREVIOUS_SESSION_BAR"
        else:
            w = g.reindex(window)
            ohlc = g[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
            good = (ohlc > 0).all(axis=1) & ohlc.apply(lambda c: c.map(math.isfinite)).all(axis=1)
            good &= (ohlc.high >= ohlc[["open", "close", "low"]].max(axis=1))
            good &= (ohlc.low <= ohlc[["open", "close", "high"]].min(axis=1))
            amount = pd.to_numeric(w.amount, errors="coerce")
            recent_good = good.reindex(window, fill_value=False).iloc[-policy.recent_sessions:]
            if int(good.sum()) < policy.min_history:
                reason = "INSUFFICIENT_PAST_VALID_HISTORY"
            elif not recent_good.all() or not (amount.iloc[-policy.recent_sessions:] > 0).all():
                reason = "RECENT_SUSPENSION_MISSING_OR_ABNORMAL_BAR"
            elif not amount.map(lambda x: pd.notna(x) and math.isfinite(x) and x >= 0).all():
                reason = "INCOMPLETE_AMOUNT_WINDOW"
            elif float(amount.mean()) < policy.min_mean_amount:
                reason = "ILLIQUID_PRIOR_WINDOW"
            elif "available_on" in g and (g.available_on.astype(str) >= date).any():
                reason = "PRICE_HISTORY_NOT_YET_AVAILABLE"
            # Suspension/trading notices are OPTIONAL dated input, never derived
            # from date-t price. A notice can block an otherwise liquid carrier.
            notices = [x for x in (risk_observations or []) if x["symbol"] == symbol
                       and x.get("known_from", "9999") <= date
                       and x.get("observation_date", "9999") <= date]
            notices.sort(key=lambda x: (x["observation_date"], x["known_from"]))
            suspension_notices = [x for x in notices if 'suspended' in x]
            price_risks = [x for x in notices if x['observation_date'] < date]
            risk = price_risks[-1] if price_risks else {}
            if not reason and suspension_notices and suspension_notices[-1]['suspended']:
                reason = "KNOWN_SUSPENSION"
            if not reason and r.get("premium_sensitive"):
                premium = risk.get("premium")
                # NAV date alone does NOT prove disclosure availability.
                if risk.get("observation_date") != prior or premium is None or not math.isfinite(float(premium)):
                    reason = "PIT_PREMIUM_UNAVAILABLE"
                elif abs(float(premium)) > policy.max_abs_premium:
                    reason = "PREMIUM_LIMIT"
            te = risk.get("tracking_error")
            if not reason and policy.max_tracking_error is not None:
                if te is None or not math.isfinite(float(te)):
                    reason = "PIT_TRACKING_ERROR_UNAVAILABLE"
                elif float(te) > policy.max_tracking_error:
                    reason = "TRACKING_ERROR_LIMIT"
            if not reason:
                eligible.append(dict(symbol=symbol, date=date, group_id=r[group_field],
                    exact_index_key=r["exact_index_key"], exposure_id=r["exposure_id"],
                    mean_amount_prior=float(amount.mean()), history_count=int(good.sum()),
                    data_through=prior, selection_policy="V3_PRIOR_AMOUNT_V1",
                    premium_checked=bool(r.get("premium_sensitive")),
                    tracking_error=te, tracking_error_checked=te is not None))
        if reason:
            excluded.append(dict(symbol=symbol, date=date, reason=reason))
    # Reliable tracking error is a policy guardrail above. Missing TE is not
    # assigned an invented zero. Liquidity then length then symbol break ties.
    eligible.sort(key=lambda r: (r["group_id"], -r["mean_amount_prior"], -r["history_count"], r["symbol"]))
    representatives, seen = [], set()
    for r in eligible:
        if r["group_id"] not in seen:
            representatives.append(r)
            seen.add(r["group_id"])
        else:
            excluded.append(dict(symbol=r["symbol"], date=date, reason="NON_REPRESENTATIVE"))
    assert len(representatives) == len({r["group_id"] for r in representatives})
    return dict(date=date, data_through=prior, representatives=representatives,
                eligible=eligible, excluded=sorted(excluded, key=lambda r: r["symbol"]))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser()
    ap.add_argument("--classifications", type=Path, required=True)
    ap.add_argument("--bars", type=Path, required=True)
    ap.add_argument("--calendar", type=Path, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--risks", type=Path)
    args = ap.parse_args()
    result = select_representatives(json.loads(args.classifications.read_text()),
        pd.read_parquet(args.bars), json.loads(args.calendar.read_text()), args.date,
        risk_observations=json.loads(args.risks.read_text()) if args.risks else None)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
