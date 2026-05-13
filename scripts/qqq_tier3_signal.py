#!/usr/bin/env python3
"""Compute the QQQ Tier 3 allocation signal from SPY SMA200 and VIX."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
NASDAQ_HISTORY_URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"
CBOE_VIX_HISTORY_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
DEFAULT_STATE_FILE = Path("~/.hermes/state/qqq-tier3-state.json").expanduser()


def request_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            ),
            "Accept": "application/json,text/csv,text/plain,*/*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to fetch {url}: {exc}") from exc


def fetch_chart(symbol: str, range_: str = "2y", interval: str = "1d") -> dict[str, Any]:
    encoded = urllib.parse.quote(symbol, safe="")
    url = YAHOO_CHART_URL.format(symbol=encoded)
    query = urllib.parse.urlencode(
        {
            "range": range_,
            "interval": interval,
            "includePrePost": "false",
            "events": "history",
        }
    )
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to fetch {symbol} chart data: {exc}") from exc

    chart = payload.get("chart", {})
    errors = chart.get("error")
    if errors:
        raise RuntimeError(f"Yahoo Finance returned an error for {symbol}: {errors}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo Finance returned no chart result for {symbol}")
    return results[0]


def clean_yahoo_closes(chart: dict[str, Any]) -> list[tuple[dt.date, float]]:
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    rows: list[tuple[dt.date, float]] = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        value = float(close)
        if not math.isfinite(value):
            continue
        rows.append((dt.datetime.utcfromtimestamp(int(ts)).date(), value))
    if not rows:
        raise RuntimeError("No valid close prices found in chart data")
    return rows


def parse_price(value: Any) -> float:
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned:
        raise ValueError("empty price")
    return float(cleaned)


def fetch_spy_rows() -> list[tuple[dt.date, float]]:
    end = dt.date.today()
    start = end - dt.timedelta(days=900)
    params = urllib.parse.urlencode(
        {
            "assetclass": "etf",
            "fromdate": start.isoformat(),
            "todate": end.isoformat(),
            "limit": 9999,
        }
    )
    url = NASDAQ_HISTORY_URL.format(symbol="SPY") + "?" + params
    errors: list[str] = []

    try:
        payload = json.loads(request_text(url))
        rows = (((payload.get("data") or {}).get("tradesTable") or {}).get("rows")) or []
        parsed: list[tuple[dt.date, float]] = []
        for row in rows:
            try:
                date = dt.datetime.strptime(row["date"], "%m/%d/%Y").date()
                close = parse_price(row["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(close):
                parsed.append((date, close))
        parsed.sort(key=lambda item: item[0])
        if len(parsed) >= 200:
            return parsed
        errors.append(f"Nasdaq returned only {len(parsed)} valid SPY rows")
    except RuntimeError as exc:
        errors.append(str(exc))
    except json.JSONDecodeError as exc:
        errors.append(f"Nasdaq returned invalid JSON: {exc}")

    try:
        return clean_yahoo_closes(fetch_chart("SPY"))
    except RuntimeError as exc:
        errors.append(str(exc))
        raise RuntimeError("Unable to fetch SPY history. " + " | ".join(errors)) from exc


def fetch_vix_rows() -> list[tuple[dt.date, float]]:
    errors: list[str] = []
    try:
        text = request_text(CBOE_VIX_HISTORY_URL)
        reader = csv.DictReader(io.StringIO(text))
        parsed: list[tuple[dt.date, float]] = []
        for row in reader:
            try:
                date = dt.datetime.strptime(row["DATE"], "%m/%d/%Y").date()
                close = parse_price(row["CLOSE"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(close):
                parsed.append((date, close))
        parsed.sort(key=lambda item: item[0])
        if parsed:
            return parsed
        errors.append("Cboe returned no valid VIX rows")
    except RuntimeError as exc:
        errors.append(str(exc))

    try:
        return clean_yahoo_closes(fetch_chart("^VIX"))
    except RuntimeError as exc:
        errors.append(str(exc))
        raise RuntimeError("Unable to fetch VIX history. " + " | ".join(errors)) from exc


def sma(values: list[float], window: int) -> float:
    if len(values) < window:
        raise RuntimeError(f"Need at least {window} closes, got {len(values)}")
    return sum(values[-window:]) / window


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def allocation_for_vix(vix: float) -> tuple[dict[str, int], str]:
    if vix < 40:
        return {"TQQQ": 100, "QQQ": 0, "cash": 0}, "VIX < 40: bull-risk-on, 100% TQQQ"
    if vix < 45:
        return {"TQQQ": 0, "QQQ": 75, "cash": 25}, "40 <= VIX < 45: 75% QQQ + 25% cash"
    if vix < 50:
        return {"TQQQ": 0, "QQQ": 50, "cash": 50}, "45 <= VIX < 50: 50% QQQ + 50% cash"
    if vix < 60:
        return {"TQQQ": 0, "QQQ": 25, "cash": 75}, "50 <= VIX < 60: 25% QQQ + 75% cash"
    return {"TQQQ": 0, "QQQ": 0, "cash": 100}, "VIX >= 60: hard stop, all cash"


def compute_signal(state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or {}

    spy_rows = fetch_spy_rows()
    vix_rows = fetch_vix_rows()

    spy_date, spy_close = spy_rows[-1]
    vix_date, vix_value = vix_rows[-1]
    spy_sma200 = sma([value for _, value in spy_rows], 200)
    ratio = spy_close / spy_sma200
    upper = spy_sma200 * 1.04
    lower = spy_sma200 * 0.97

    previous_regime = state.get("market_regime", "unknown")
    previous_allocation = state.get("allocation") or {"TQQQ": 0, "QQQ": 0, "cash": 100}

    if spy_close > upper:
        market_regime = "bull"
        regime_reason = "SPY > SMA200 * 1.04: bull trigger"
    elif spy_close < lower:
        market_regime = "bear"
        regime_reason = "SPY < SMA200 * 0.97: bear trigger"
    else:
        market_regime = previous_regime if previous_regime in {"bull", "bear"} else "unknown"
        regime_reason = "SPY is inside the buffer band: keep previous regime"

    if vix_value >= 60:
        allocation = {"TQQQ": 0, "QQQ": 0, "cash": 100}
        decision = "ALL_CASH"
        signal_reason = "Priority 1: VIX >= 60 hard stop"
    elif market_regime == "bear":
        allocation = {"TQQQ": 0, "QQQ": 0, "cash": 100}
        decision = "ALL_CASH"
        signal_reason = "Priority 2: SPY bear regime"
    elif market_regime == "bull":
        allocation, signal_reason = allocation_for_vix(vix_value)
        decision = "BUY_TQQQ" if allocation["TQQQ"] else "RISK_REDUCED_QQQ_CASH"
    else:
        allocation = previous_allocation
        decision = "HOLD_PREVIOUS_OR_CASH"
        signal_reason = "Buffer band with no prior bull/bear state; hold prior allocation or wait in cash"

    changed = allocation != previous_allocation or market_regime != previous_regime
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    return {
        "run_timestamp_utc": now,
        "data": {
            "spy_date": spy_date.isoformat(),
            "spy_close": round(spy_close, 4),
            "sma200": round(spy_sma200, 4),
            "spy_sma_ratio": round(ratio, 4),
            "upper_trigger": round(upper, 4),
            "lower_trigger": round(lower, 4),
            "vix_date": vix_date.isoformat(),
            "vix": round(vix_value, 4),
        },
        "previous": {
            "market_regime": previous_regime,
            "allocation": previous_allocation,
        },
        "market_regime": market_regime,
        "allocation": allocation,
        "decision": decision,
        "regime_reason": regime_reason,
        "signal_reason": signal_reason,
        "changed": changed,
    }


def format_allocation(allocation: dict[str, int]) -> str:
    pieces = []
    for key in ("TQQQ", "QQQ", "cash"):
        value = int(allocation.get(key, 0))
        if value:
            label = "现金" if key == "cash" else key
            pieces.append(f"{value}% {label}")
    return " + ".join(pieces) if pieces else "无仓位"


def format_chinese_report(signal: dict[str, Any]) -> str:
    data = signal["data"]
    allocation = format_allocation(signal["allocation"])
    previous_allocation = format_allocation(signal["previous"]["allocation"])
    changed_text = "已变化" if signal["changed"] else "未变化"
    return "\n".join(
        [
            f"📊 QQQ 策略今日信号：{allocation}",
            "",
            f"SPY: {data['spy_close']:.2f} ({data['spy_date']})",
            f"SMA200: {data['sma200']:.2f}",
            f"SPY/SMA200: {data['spy_sma_ratio']:.2%}",
            f"VIX: {data['vix']:.2f} ({data['vix_date']})",
            "",
            f"市场状态: {signal['market_regime']}",
            f"触发逻辑: {signal['regime_reason']}；{signal['signal_reason']}",
            f"上一配置: {previous_allocation}",
            f"状态变化: {changed_text}",
            "",
            "提醒：这是按固定规则生成的交易信号，不构成个性化投资建议。",
        ]
    )


def build_state(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "updated_at_utc": signal["run_timestamp_utc"],
        "market_regime": signal["market_regime"],
        "allocation": signal["allocation"],
        "decision": signal["decision"],
        "regime_reason": signal["regime_reason"],
        "signal_reason": signal["signal_reason"],
        "data": signal["data"],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute the QQQ Tier 3 strategy signal.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--no-update-state", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    state_file = args.state_file.expanduser()
    state = load_state(state_file)

    try:
        signal = compute_signal(state)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.no_update_state:
        save_state(state_file, build_state(signal))

    if args.format == "json":
        print(json.dumps(signal, ensure_ascii=False, indent=2))
    else:
        print(format_chinese_report(signal))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
