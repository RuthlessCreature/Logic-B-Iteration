"""Incremental Xuangubao event + BaoStock unadjusted OHLC/5-minute collector.

Deliberately caches raw provider responses locally; no data redistributing Git
commits and no dependency on Tushare. CLI supports bounded pilots first.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .identity import canonical_code
from .strategy import select_core

FIRST = "2020-01-01"
LAST = "2026-06-30"
POOL_NAMES = ("limit_up", "limit_down", "limit_up_broken")


def _check_dates(start: str, end: str):
    if not (FIRST <= start <= end <= LAST):
        raise ValueError("only 2020-01-01..2026-06-30 allowed")


def _atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)


def _cached(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _request_json(url: str, *, opener=urlopen):
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "Logic-B-Research/0.1"})
    with opener(req, timeout=25) as response:
        raw = response.read()
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict) or result.get("code", 0) not in (0, 200, 20000, None):
        raise RuntimeError("Xuangubao malformed or error response")
    return result, hashlib.sha256(raw).hexdigest()


def fetch_xgb_day(day: str, root: Path, *, request=_request_json):
    _check_dates(day, day)
    path = root / "events" / (day + ".json")
    existing = _cached(path)
    if existing is not None:
        return existing
    pools = {}
    hashes = {}
    for name in POOL_NAMES:
        url = ("https://flash-api.xuangubao.com.cn/api/pool/detail?"
               + urlencode({"date": day, "pool_name": name}))
        response, digest = request(url)
        data = response.get("data")
        if not isinstance(data, list):
            raise ValueError("unexpected Xuangubao pool payload")
        clean = []
        seen = set()
        for row in data:
            try:
                code = canonical_code(row["symbol"])
            except (KeyError, ValueError, TypeError):
                continue
            if code in seen:
                raise ValueError("duplicate stock in vendor event pool")
            seen.add(code)
            clean.append({
                "symbol": code,
                "limit_up_days": int(row.get("limit_up_days") or 1),
                "break_limit_up_times": int(row.get("break_limit_up_times") or 0),
                "name": row.get("stock_chi_name"),
            })
        pools[name] = clean
        hashes[name] = digest
    # Market indicator is optional; no made-up intraday gate if missing.
    response, digest = request("https://flash-api.xuangubao.com.cn/api/market_indicator/line?"
                               + urlencode({"date": day, "fields": "market_temperature,limit_up_count,limit_down_count"}))
    records = response.get("data") or []
    market = records[-1] if isinstance(records, list) and records else {}
    market = {"market_temperature": market.get("market_temperature")} if isinstance(market, dict) else {}
    out = {"date": day, "limit_up": pools["limit_up"], "limit_down": pools["limit_down"],
           "limit_broken": pools["limit_up_broken"], "market": market,
           "provenance": {"provider": "xuangubao", "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                          "sha256_by_endpoint": dict(hashes, market_indicator=digest)}}
    _atomic_json(path, out)
    return out


def _bs_code(code: str):
    symbol = canonical_code(code)
    market = symbol[-2:].lower()
    if market not in ("sh", "sz", "bj"):
        raise ValueError("unsupported BaoStock exchange")
    return market + "." + symbol[:6]


def _bs_rows(result):
    if result.error_code != "0":
        raise RuntimeError(f"BaoStock query error: {result.error_code}")
    values = []
    while result.next():
        values.append(dict(zip(result.fields, result.get_row_data())))
    return values


class BaoStockClient:
    def __enter__(self):
        try:
            import baostock as bs
        except ImportError as exc:
            raise RuntimeError("Install data extras: pip install -e '.[data]'") from exc
        self.bs = bs
        response = bs.login()
        if response.error_code != "0":
            raise RuntimeError("BaoStock login failed")
        return self

    def __exit__(self, _type, _value, _tb):
        self.bs.logout()

    def trade_calendar(self, start: str, end: str):
        _check_dates(start, end)
        result = _bs_rows(self.bs.query_trade_dates(start_date=start, end_date=end))
        return [r["calendar_date"] for r in result if r.get("is_trading_day") == "1"]

    def historical(self, code: str, start: str, end: str, *, freq: str):
        _check_dates(start, end)
        if freq not in ("d", "5"):
            raise ValueError("only daily or completed 5min supported")
        fields = ("date,code,open,high,low,close,preclose,volume,tradestatus,isST" if freq == "d"
                  else "date,time,code,open,high,low,close,volume")
        return _bs_rows(self.bs.query_history_k_data_plus(
            _bs_code(code), fields, start_date=start, end_date=end, frequency=freq, adjustflag="3"))


def fetch_daily(code: str, root: Path, client: BaoStockClient, *, start=FIRST, end=LAST):
    canon = canonical_code(code)
    path = root / "daily" / (canon + ".json")
    old = _cached(path)
    if old is not None and old.get("range") == [start, end]:
        return old
    records = client.historical(canon, start, end, freq="d")
    by_day = {}
    for r in records:
        ds = r["date"]
        if not (start <= ds <= end):
            raise ValueError("provider daily date out of range")
        if ds in by_day:
            raise ValueError("duplicate daily date")
        # BaoStock flags are 1/0 as strings. Never substitute a name-based
        # ST identity or infer a future status from an observed price.
        st = r.get("isST")
        by_day[ds] = {
            "open": float(r["open"]) if r["open"] else None,
            "high": float(r["high"]) if r["high"] else None,
            "low": float(r["low"]) if r["low"] else None,
            "close": float(r["close"]) if r["close"] else None,
            "is_st": (st == "1") if st in ("0", "1") else None,
            "tradestatus": int(r["tradestatus"]) if r.get("tradestatus") in ("0", "1") else None,
        }
    value = {"code": canon, "range": [start, end], "adjustflag": "3", "frequency": "d",
             "provider": "baostock", "records": by_day}
    _atomic_json(path, value)
    return value


def fetch_5m(code: str, day: str, root: Path, client: BaoStockClient):
    _check_dates(day, day)
    canon = canonical_code(code)
    path = root / "minute" / canon / (day + ".json")
    old = _cached(path)
    if old is not None:
        return old
    rows = client.historical(canon, day, day, freq="5")
    bars = []
    for r in rows:
        # BaoStock encodes completed bar end as YYYYMMDDHHmmssSSS.
        timestamp = str(r.get("time", ""))
        if r.get("date") != day or len(timestamp) < 12 or timestamp[:8] != day.replace("-", ""):
            raise ValueError("minute timestamp does not match requested date")
        bars.append({"time": timestamp[8:10] + ":" + timestamp[10:12],
                     "open": float(r["open"]), "high": float(r["high"]),
                     "low": float(r["low"]), "close": float(r["close"]),
                     "volume": float(r.get("volume") or 0)})
    value = {"code": canon, "day": day, "frequency": "5", "bars": bars,
             "provider": "baostock", "bar_timestamp": "END"}
    _atomic_json(path, value)
    return value


def make_dataset(root: Path, calendar: list[str], *, save_to: Path):
    if calendar != sorted(set(calendar)):
        raise ValueError("calendar not sorted/unique")
    if calendar:
        _check_dates(calendar[0], calendar[-1])
    raw = []
    selection = set()
    prior = None
    for day in calendar:
        event = _cached(root / "events" / (day + ".json"))
        if event is None:
            raise FileNotFoundError(f"missing Xuangubao date partition: {day}")
        chosen, _ = select_core(prior, {}) if prior is not None else (None, "WARMUP")
        if chosen:
            selection.add(chosen)
        raw.append(dict(event))
        prior = event
    daily = {code: _cached(root / "daily" / (code + ".json")) for code in selection}
    for day in raw:
        d = day["date"]
        day["daily"] = {
            code: value["records"][d] for code, value in daily.items()
            if value is not None and d in value.get("records", {})
        }
        day["bars_5m"] = {
            code: data["bars"] for code in selection
            if (data := _cached(root / "minute" / code / (d + ".json"))) is not None
        }
    out = {"classification": "REAL_PROVIDER_PARTIAL_REPLAY_INPUT",
           "coverage_complete": False,
           "coverage": {"calendar_sessions": len(calendar),
                        "event_sessions": len(raw),
                        "distinct_baseline_selections": len(selection),
                        "codes_with_daily_cache": sum(x is not None for x in daily.values()),
                        "symbol_day_5m_cached": sum(len(day["bars_5m"]) for day in raw)},
           "days": raw}
    _atomic_json(save_to, out)
    return out


def main():
    p = argparse.ArgumentParser(description="Bounded data ingest; writes ignored local cache only.")
    p.add_argument("action", choices=["calendar", "events", "daily", "minute", "dataset"])
    p.add_argument("--start", default=FIRST)
    p.add_argument("--end", default=LAST)
    p.add_argument("--cache", type=Path, default=Path("data/raw"))
    p.add_argument("--out", type=Path, default=Path("data/replay_dataset.json"))
    p.add_argument("--max-days", type=int, default=5, help="bounded first pilot")
    p.add_argument("--max-codes", type=int, default=20)
    args = p.parse_args()
    _check_dates(args.start, args.end)
    if args.max_days < 1 or args.max_codes < 1:
        raise ValueError("limits must be >= 1")
    calendar_file = args.cache / "calendar.json"
    if args.action == "calendar":
        with BaoStockClient() as client:
            days = client.trade_calendar(args.start, args.end)
        _atomic_json(calendar_file, {"days": days, "range": [args.start, args.end]})
        print(f"calendar sessions={len(days)}")
        return
    cal = _cached(calendar_file)
    if cal is None:
        raise FileNotFoundError("fetch calendar first")
    days = [day for day in cal["days"] if args.start <= day <= args.end]
    if args.action == "events":
        for day in days[:args.max_days]:
            fetch_xgb_day(day, args.cache)
            print("cached event", day)
            time.sleep(.25)
        return
    if args.action == "dataset":
        d = make_dataset(args.cache, days[:args.max_days], save_to=args.out)
        print(json.dumps(d["coverage"], indent=2))
        return
    codes = set()
    prior = None
    chosen_by_date = {}
    for day in days[:args.max_days]:
        event = _cached(args.cache / "events" / (day + ".json"))
        if event is None:
            raise FileNotFoundError("event partitions missing; run events action first")
        if prior is not None:
            core, _ = select_core(prior, {})
            if core:
                chosen_by_date[day] = core
                codes.add(core)
        prior = event
    with BaoStockClient() as client:
        if args.action == "daily":
            for code in sorted(codes)[:args.max_codes]:
                fetch_daily(code, args.cache, client, start=args.start, end=args.end)
                print("cached daily", code)
        else:
            for day, code in list(chosen_by_date.items())[:args.max_codes]:
                fetch_5m(code, day, args.cache, client)
                print("cached five minute", day, code)

if __name__ == "__main__":
    main()
