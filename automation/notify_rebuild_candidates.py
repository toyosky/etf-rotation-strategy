#!/usr/bin/env python3
"""Send one daily PushPlus report: next-day OLS target and ALL current-market rebuild candidates.

The independent full-market scan is required. Do not fall back silently to the
fixed production pool if coverage is missing or data timestamps disagree.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen


def validate_and_sort(current: dict, market: dict) -> list[dict]:
    day = str(current.get("market_data_date") or "")
    target = current.get("next_strategy_target") or {}
    if not day or day != str(market.get("as_of") or ""):
        raise ValueError("Production and full-market dates differ")
    if str(target.get("signal_date")) != day:
        raise ValueError("Next-day OLS signal is stale; no notification")
    if market.get("data_quality_gate") != "PASS":
        raise ValueError("Full-market quality gate failed; no partial-as-complete notification")
    if market.get("listed_requested", 0) < 1200:
        raise ValueError("Full-market universe unexpectedly small")
    if market.get("asof_coverage", 0) < 0.90:
        raise ValueError("Full-market coverage below 90%")
    rows = market.get("qualified_candidates")
    if not isinstance(rows, list):
        raise ValueError("Missing full-market qualified rows (no limited-pool fallback)")
    if len(rows) != market.get("raw_qualified"):
        raise ValueError("Candidate count and serialized rows disagree")
    if len({r.get("symbol") for r in rows}) != len(rows):
        raise ValueError("Duplicate ETF codes in qualified list")
    for r in rows:
        if r.get("stage") != "REBUILDING_QUALIFIED":
            raise ValueError("Nonqualified row in qualified candidates")
        if not r.get("cross_date") or not r.get("first_qualified_date"):
            raise ValueError("Candidate missing event dates")
        if str(r.get("first_qualified_date")) > day:
            raise ValueError("Future first-qualification date")
    return sorted(
        rows,
        key=lambda r: (str(r.get("first_qualified_date")), str(r.get("cross_date")),
                       float(r.get("r2") or 0), str(r.get("symbol"))),
        reverse=True,
    )


def build_report(previous: dict, current: dict, market: dict, test: bool = False, premium: dict | None = None) -> tuple[str, str]:
    rows = validate_and_sort(current, market)
    day = current["market_data_date"]
    tgt = current.get("next_strategy_target") or {}
    model = tgt.get("model_target")
    execution = tgt.get("symbol")
    model_name = tgt.get("model_target_name") or ""
    execution_name = tgt.get("name") or ""
    coverage = float(market["asof_coverage"])
    count = int(market["symbols_with_asof_close"])
    listed = int(market["listed_requested"])
    extra = "【测试】" if test else ""
    premium = premium or {}
    pct = premium.get("premium_pct")
    matched = premium.get("symbol") == model and premium.get("signal_date") == day
    if not matched:
        premium_line = "- Premium10：未核实（标的或日期不匹配）"
    elif pct is None:
        premium_line = f"- Premium10：无法计算；原因 {premium.get('reason', '数据缺失')}"
    else:
        label = "同日历史配对" if premium.get("status") == "MATCHED_HISTORY" else "过期历史配对"
        premium_line = (f"- Premium10：{float(pct):+.2f}%（{label}；"
                        f"净值及价格日期 {premium.get('nav_date', '未知')}；"
                        f"阈值 10%，非实时买入许可）")
    body = [
        f"# {extra}ETF 收盘策略日报",
        f"数据日期：{day}（A股交易日收盘）",
        f"全市场有效行情：{count}/{listed}，覆盖率 {coverage:.1%}",
        f"未取得当日行情：{listed-count} 只，不视为无重建信号。",
        "",
        "## 固定候选池 OLS Top1（下一交易日）",
        f"- 模型首选：**{model+' '+model_name if model else '现金/无模型首选'}**",
        f"- 执行层目标：**{execution+' '+execution_name if execution else '现金/无执行目标'}**",
        f"- 决策：{tgt.get('decision') or '未提供'}；执行状态：{tgt.get('execution_status') or '未提供'}",
        premium_line,
        "- 两项可能不同：模型首选未经全部溢价和执行层过滤；均不代表用户实际持仓。",
        "",
        "## 全市场 R² 趋势重建合格候选（按首次合格日期由新到旧）",
        f"- 当前合格：**{len(rows)} 只**；不以成交额、上市年限过滤，仅保留风险提示。",
        f"- 本交易日首次合格：{sum(r['first_qualified_date']==day for r in rows)} 只；若为 0 则今日无新增。",
        "- 重建候选来自独立全市场扫描，不限于固定 OLS 池。首次合格日期 ≠ annual 翻正日期；以下均为研究信号，不能替代 Premium10 和基本面审计。",
        "",
    ]
    if not rows:
        body.append("今日没有满足条件的重建标的。")
    for i, row in enumerate(rows, 1):
        r2 = row.get("r2")
        annual = row.get("annual")
        r2txt = f"{float(r2):.3f}" if r2 is not None else "未知"
        annualtxt = f"{float(annual)*100:+.1f}%" if annual is not None else "未知"
        warnings = []
        if not row.get("strict_eligible"):
            warnings.append("低流动性/短历史需检查")
        if row.get("shock10_8"):
            warnings.append("短期急涨")
        caveat = f"；{'、'.join(warnings)}" if warnings else ""
        body.append(
            f"{i}. **{row['first_qualified_date']}** | {row['symbol']} {row.get('name','')} | "
            f"R² {r2txt} | annual {annualtxt} | 翻正 {row['cross_date']}{caveat}"
        )
    body.extend(["", "重建仅为研究候选；交易前检查交易所盘口、基金净值时点、溢价、消息与真实底层资产。"])
    title = f"{extra}ETF日报 {day}｜OLS {model or '现金'}｜全市场重建 {len(rows)}"
    return title, "\n".join(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous", required=True)
    ap.add_argument("--current", required=True)
    ap.add_argument("--previous-market", default="")
    ap.add_argument("--market-report", required=True)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="Validate + render but do not send PushPlus")
    ap.add_argument("--output-markdown", default="")
    ap.add_argument("--premium-snapshot", default="")
    args = ap.parse_args()

    previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    market = json.loads(Path(args.market_report).read_text(encoding="utf-8"))
    older_market = json.loads(Path(args.previous_market).read_text(encoding="utf-8")) if args.previous_market else {}
    premium = json.loads(Path(args.premium_snapshot).read_text(encoding="utf-8")) if args.premium_snapshot else {}
    title, content = build_report(previous, current, market, args.test, premium)

    if args.output_markdown:
        Path(args.output_markdown).write_text(content, encoding="utf-8")
    if args.dry_run:
        print(json.dumps({"status":"DRY_RUN","title":title,
                          "market_data_date":market["as_of"],
                          "candidates":market["raw_qualified"],
                          "characters":len(content)}, ensure_ascii=False))
        return
    date = current.get("market_data_date")
    if (not args.test and older_market.get("notification_format")=="ols_full_market_v2"
        and older_market.get("as_of")==date
        and [(r["symbol"],r["first_qualified_date"]) for r in older_market.get("qualified_candidates",[])]
            == [(r["symbol"],r["first_qualified_date"]) for r in market.get("qualified_candidates",[])]
        and (previous.get("next_strategy_target") or {}) == (current.get("next_strategy_target") or {})):
        print("Already sent this OLS + full-market report; skip duplicate PushPlus")
        return
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not token:
        raise SystemExit("PUSHPLUS_TOKEN missing; refusing to mark daily notification delivered")
    encoded=json.dumps({"token":token,"title":title,"content":content,"template":"markdown"},
                       ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        try:
            request=Request("https://www.pushplus.plus/send",data=encoded,
                            headers={"Content-Type":"application/json; charset=utf-8"},method="POST")
            with urlopen(request,timeout=20) as resp:
                payload=json.loads(resp.read().decode("utf-8"))
            if int(payload.get("code",0))!=200:
                raise RuntimeError(f"PushPlus API returned {payload.get('code')}: {payload.get('msg')}")
            print(f"PushPlus daily sent; market={date}; all-qualified={market['raw_qualified']}; test={args.test}")
            return
        except Exception as e:
            if attempt==2:raise RuntimeError("PushPlus notification failed after three attempts") from e
            time.sleep(2**attempt)


if __name__=="__main__":
    main()
