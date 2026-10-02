#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PUSHPLUS_URL = "https://www.pushplus.plus/send"
ABNORMAL_STATUSES = {"WATCH", "WARNING"}


def load_rows(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"{path} must contain a JSON list")
    return data


def fmt_pct(value):
    return "—" if value is None else f"{float(value)*100:.2f}%"


def should_notify(old: str, new: str) -> bool:
    return old != new and (old in ABNORMAL_STATUSES or new in ABNORMAL_STATUSES)


def detect(previous: list[dict], current: list[dict]) -> list[dict]:
    p = {str(r["symbol"]): r for r in previous}
    c = {str(r["symbol"]): r for r in current}
    out = []
    for symbol in sorted(set(p) & set(c)):
        old, new = str(p[symbol]["status"]), str(c[symbol]["status"])
        if should_notify(old, new):
            out.append({"symbol": symbol, "old": old, "new": new, "row": c[symbol]})
    return out


def send(token: str, title: str, content: str, attempts: int = 3) -> None:
    payload = json.dumps(
        {"token": token, "title": title, "content": content, "template": "markdown"},
        ensure_ascii=False,
    ).encode("utf-8")
    last = None
    for i in range(attempts):
        try:
            req = Request(
                PUSHPLUS_URL,
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if int(body.get("code", 0)) != 200:
                raise RuntimeError(f"PushPlus rejected request: {body}")
            print("PushPlus sent successfully")
            return
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
            last = exc
            print(f"PushPlus attempt {i+1}/{attempts} failed: {exc}")
            if i + 1 < attempts:
                time.sleep(2 ** i)
    raise RuntimeError(f"PushPlus failed after {attempts} attempts: {last}")


def render_changes(changes: list[dict], snapshot_date: str) -> str:
    lines = ["# ETF Asset Health 状态变化", "", f"当前快照：**{snapshot_date}**", ""]
    for ch in changes:
        row = ch["row"]
        lines += [
            f"- **{ch['symbol']}**：{ch['old']} → {ch['new']}",
            f"  - 最近2年近高点样本：{row.get('recent_2y_near_high_count', 0)}",
            f"  - 后10日平均：{fmt_pct(row.get('recent_2y_near_high_fwd10_mean'))}",
            f"  - 后10日胜率：{fmt_pct(row.get('recent_2y_near_high_fwd10_win_rate'))}",
        ]
    lines += ["", "> 仅为诊断，不会自动修改策略或下单。"]
    return "\n".join(lines)


def render_test(current: list[dict], snapshot_date: str) -> str:
    abnormal = [r for r in current if r.get("status") in ABNORMAL_STATUSES]
    lines = ["# Asset Health PushPlus 测试", "", f"当前快照：**{snapshot_date}**", ""]
    if abnormal:
        for r in abnormal:
            lines.append(f"- **{r['symbol']} — {r['status']}**")
    else:
        lines.append("- 当前无 WATCH / WARNING")
    lines += ["", "> 测试消息不代表发生新的健康状态变化。"]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--current", required=True)
    p.add_argument("--previous", required=True)
    p.add_argument("--test", action="store_true")
    args = p.parse_args()

    token = os.getenv("PUSHPLUS_TOKEN")
    if not token:
        print("PUSHPLUS_TOKEN is not set; notification step skipped.")
        return 0

    current = load_rows(args.current)
    previous = load_rows(args.previous)
    if not current:
        raise RuntimeError("current Asset Health snapshot is empty")
    snapshot_date = str(current[0].get("snapshot_date", "unknown"))

    if args.test:
        send(token, f"Asset Health 通知测试 {snapshot_date}", render_test(current, snapshot_date))
        return 0

    if not previous:
        print("No previous GitHub snapshot; current run becomes baseline. No notification sent.")
        return 0

    changes = detect(previous, current)
    if not changes:
        print("No meaningful health-status changes.")
        return 0

    send(token, f"ETF Asset Health 状态变化 {snapshot_date}", render_changes(changes, snapshot_date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
