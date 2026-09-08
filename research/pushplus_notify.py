#!/usr/bin/env python3
"""PushPlus notifier for Asset Health status changes.

This script runs after asset_health.py has written the current snapshot. It
compares the latest snapshot with the previous distinct snapshot date and only
pushes meaningful health-state transitions. Re-running the same snapshot date
is idempotent for health logic; --test can be used to verify the PushPlus path.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from supabase import Client, create_client

MONITOR_VERSION = "ASSET_HEALTH_V1"
DEFAULT_STRATEGY_VERSION = "FROZEN_C2@20260903T_fixed_window_v2"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
ABNORMAL_STATUSES = {"WATCH", "WARNING"}


def fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def should_notify_transition(old: str, new: str) -> bool:
    """Notify only if a changed state enters, leaves, or moves within abnormal states."""
    if old == new:
        return False
    return old in ABNORMAL_STATUSES or new in ABNORMAL_STATUSES


def transition_label(old: str, new: str) -> str:
    if old not in ABNORMAL_STATUSES and new in ABNORMAL_STATUSES:
        return "新异常"
    if old == "WATCH" and new == "WARNING":
        return "升级"
    if old == "WARNING" and new == "WATCH":
        return "缓解"
    if old in ABNORMAL_STATUSES and new == "HEALTHY":
        return "恢复"
    if old in ABNORMAL_STATUSES and new == "INSUFFICIENT_DATA":
        return "证据不足"
    return "状态变化"


def detect_changes(
    previous_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prev = {r["symbol"]: r for r in previous_rows}
    curr = {r["symbol"]: r for r in current_rows}
    changes: list[dict[str, Any]] = []
    for symbol in sorted(set(prev) & set(curr)):
        old = str(prev[symbol]["status"])
        new = str(curr[symbol]["status"])
        if should_notify_transition(old, new):
            changes.append(
                {
                    "symbol": symbol,
                    "old_status": old,
                    "new_status": new,
                    "label": transition_label(old, new),
                    "current": curr[symbol],
                }
            )
    return changes


def send_pushplus(token: str, *, title: str, content: str, attempts: int = 3) -> None:
    payload = json.dumps(
        {
            "token": token,
            "title": title,
            "content": content,
            "template": "markdown",
        },
        ensure_ascii=False,
    ).encode("utf-8")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = Request(
            PUSHPLUS_URL,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                body_raw = response.read().decode("utf-8")
            body = json.loads(body_raw)
            if int(body.get("code", 0)) != 200:
                raise RuntimeError(f"PushPlus rejected request: {body}")
            print(f"PushPlus sent successfully: {body.get('msg', 'ok')}")
            return
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
            last_error = exc
            print(f"PushPlus attempt {attempt}/{attempts} failed: {exc}")
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"PushPlus failed after {attempts} attempts: {last_error}")


def fetch_snapshots(client: Client, strategy_version: str) -> list[dict[str, Any]]:
    response = (
        client.table("asset_health_snapshots")
        .select(
            "snapshot_date,symbol,status,data_status,reason,"
            "recent_2y_near_high_count,recent_2y_near_high_fwd10_mean,"
            "recent_2y_near_high_fwd10_win_rate"
        )
        .eq("monitor_version", MONITOR_VERSION)
        .eq("source_strategy_version", strategy_version)
        .order("snapshot_date", desc=True)
        .order("symbol")
        .limit(5000)
        .execute()
    )
    return response.data or []


def render_change_message(
    *, current_date: str, previous_date: str, changes: list[dict[str, Any]]
) -> str:
    lines = [
        "# ETF Asset Health 状态变化",
        "",
        f"对比：**{previous_date} → {current_date}**",
        "",
    ]
    for change in changes:
        row = change["current"]
        lines.extend(
            [
                f"- **{change['symbol']}**：{change['old_status']} → {change['new_status']}（{change['label']}）",
                f"  - 最近2年近高点样本：{row.get('recent_2y_near_high_count', 0)}",
                f"  - 后10日平均：{fmt_pct(row.get('recent_2y_near_high_fwd10_mean'))}",
                f"  - 后10日胜率：{fmt_pct(row.get('recent_2y_near_high_fwd10_win_rate'))}",
            ]
        )
    data_states = sorted({str(c["current"].get("data_status", "UNKNOWN")) for c in changes})
    lines.extend(
        [
            "",
            f"数据状态：{', '.join(data_states)}",
            "",
            "> 仅为资产适配性监控，不会自动修改 ETF_POOL 或下单。",
        ]
    )
    return "\n".join(lines)


def render_test_message(*, current_date: str, rows: list[dict[str, Any]]) -> str:
    abnormal = sorted(
        (r for r in rows if r.get("status") in ABNORMAL_STATUSES),
        key=lambda r: (0 if r.get("status") == "WARNING" else 1, r["symbol"]),
    )
    lines = [
        "# Asset Health PushPlus 测试",
        "",
        f"当前快照：**{current_date}**",
        "",
        "PushPlus 通知链路已成功触发。",
        "",
        "## 当前异常状态",
        "",
    ]
    if not abnormal:
        lines.append("- 无 WATCH / WARNING")
    else:
        for row in abnormal:
            lines.append(
                f"- **{row['symbol']} — {row['status']}**：最近2年10日均值 {fmt_pct(row.get('recent_2y_near_high_fwd10_mean'))}，胜率 {fmt_pct(row.get('recent_2y_near_high_fwd10_win_rate'))}"
            )
    lines.extend(["", "> 测试消息不代表发生了新的健康状态变化。"])
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    token = os.getenv("PUSHPLUS_TOKEN")

    if not supabase_url or not supabase_key:
        raise RuntimeError("missing Supabase backend credentials")
    if args.test and not token:
        raise RuntimeError("--test requires PUSHPLUS_TOKEN")
    if not token:
        print("PUSHPLUS_TOKEN is not set; notification step skipped.")
        return 0

    client = create_client(supabase_url, supabase_key)
    rows = fetch_snapshots(client, args.strategy_version)
    if not rows:
        raise RuntimeError("asset_health_snapshots returned no rows")

    available_dates = sorted({str(r["snapshot_date"]) for r in rows}, reverse=True)
    current_date = args.snapshot_date or available_dates[0]
    current_rows = [r for r in rows if str(r["snapshot_date"]) == current_date]
    if not current_rows:
        raise RuntimeError(f"snapshot not found: {current_date}")

    if args.test:
        send_pushplus(
            token,
            title=f"Asset Health 通知测试 {current_date}",
            content=render_test_message(current_date=current_date, rows=current_rows),
        )
        return 0

    previous_dates = [d for d in available_dates if d < current_date]
    if not previous_dates:
        print("No earlier distinct snapshot date; current snapshot is baseline. No change notification sent.")
        return 0

    previous_date = previous_dates[0]
    previous_rows = [r for r in rows if str(r["snapshot_date"]) == previous_date]
    changes = detect_changes(previous_rows, current_rows)
    if not changes:
        print(f"No meaningful health-status changes: {previous_date} -> {current_date}")
        return 0

    send_pushplus(
        token,
        title=f"ETF Asset Health 状态变化 {current_date}",
        content=render_change_message(
            current_date=current_date,
            previous_date=previous_date,
            changes=changes,
        ),
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Notify meaningful Asset Health status changes through PushPlus")
    parser.add_argument(
        "--strategy-version",
        default=os.getenv("ASSET_HEALTH_STRATEGY_VERSION", DEFAULT_STRATEGY_VERSION),
    )
    parser.add_argument("--snapshot-date", help="snapshot date to inspect; defaults to latest stored date")
    parser.add_argument("--test", action="store_true", help="send a test message regardless of status changes")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
