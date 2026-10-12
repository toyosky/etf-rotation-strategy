#!/usr/bin/env python3
"""Notify first REBUILDING_QUALIFIED observation for each trend rebuild episode."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen


def episode_keys(data: dict) -> set[tuple[str, str]]:
    return {
        (str(row["symbol"]), str(row["cross_date"]))
        for row in data.get("qualified_candidates", [])
        if row.get("stage") == "REBUILDING_QUALIFIED"
        and row.get("symbol") and row.get("cross_date")
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--test", action="store_true", help="Send an explicitly labelled test notification")
    args = parser.parse_args()

    previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    new_keys = episode_keys(current) - episode_keys(previous)
    new_rows = [
        row for row in current.get("qualified_candidates", [])
        if (str(row.get("symbol")), str(row.get("cross_date"))) in new_keys
    ]
    if not new_rows and not args.test:
        print("No new qualified rebuild episodes; no PushPlus notification.")
        return

    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not token:
        raise SystemExit("New qualified rebuild candidates exist but PUSHPLUS_TOKEN is missing")

    date = current.get("market_data_date", "unknown")
    lines = [
        "# PushPlus 链路测试" if args.test else "# ETF 趋势重建候选",
        "",
        f"信号日期：{date}",
        "此消息仅用于测试通知通道，不代表新增交易信号。" if args.test else "",
        "",
        "以下标的达到 REBUILDING_QUALIFIED；仅提示候选，尚未进行基本面/新闻审计，不构成买入建议。",
        "",
    ]
    for row in new_rows:
        r2 = row.get("r2")
        r2_text = f"{r2:.3f}" if isinstance(r2, (int, float)) else "未知"
        age = row.get("cross_age_sessions")
        age_text = f"{age}个交易日" if isinstance(age, int) else "未知"
        freshness = (
            "较早期确认" if age == 1
            else "延后确认，注意追高风险" if isinstance(age, int) and age >= 2
            else "时间信息不足"
        )
        lines.extend([
            f"- **{row.get('symbol')} {row.get('name', '')}**",
            f"  - 趋势起点（annual 首次翻正）：{row.get('cross_date') or '未知'}",
            f"  - 本次合格信号日期：{date}",
            f"  - 距趋势起点：{age_text}（{freshness}）",
            f"  - R²：{r2_text}",
        ])
    lines.extend(["", "请自行进一步审计基本面、宏观事件、溢价和买入风险。"])
    payload = json.dumps({
        "token": token,
        "title": f"【测试】ETF 重建 PushPlus {date}" if args.test else f"ETF 重建候选 {date}（{len(new_rows)}只）",
        "content": "\n".join(lines),
        "template": "markdown",
    }, ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        try:
            request = Request(
                "https://www.pushplus.plus/send", data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urlopen(request, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if int(body.get("code", 0)) != 200:
                raise RuntimeError(f"PushPlus API rejection code={body.get('code')}; msg={body.get('msg')}")
            print(f"PushPlus sent: test={args.test}; candidates={len(new_rows)}.")
            return
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError("PushPlus send failed after 3 attempts") from exc
            time.sleep(2 ** attempt)


if __name__ == "__main__":
    main()
