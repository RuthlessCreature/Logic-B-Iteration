"""Human-readable FOLLOW review plan; never sends broker orders or invents live prices."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .strategy import select_core
from .identity import canonical_code


def build_review(dataset: dict, config: dict, research_report: dict | None = None) -> dict:
    days = dataset.get("days", [])
    if not days:
        return {"status": "NO_FOLLOW", "reason": "NO_COMPLETED_MARKET_SESSION"}
    last = days[-1]
    qualified = (research_report is not None and
                 research_report.get("verdict") == "CANDIDATE_FOR_MANUAL_REVIEW")
    candidate, reason = select_core(last, config.get("baseline", {}))
    status = "MANUAL_REVIEW_ONLY" if candidate is not None and qualified else "NO_FOLLOW"
    matched = next((x for x in last.get("limit_up", [])
                    if canonical_code(x["symbol"]) == candidate), {}) if candidate else {}
    return {"classification": "MANUAL_RESEARCH_WATCHLIST_NO_AUTO_ORDER",
            "asof_last_completed_session": last["date"],
            "target_session": "NEXT_TRADING_SESSION_UNRESOLVED",
            "status": status, "reason": (reason if candidate is not None else reason)
                 if qualified else "NO_VALIDATED_STRATEGY_APPROVAL",
            "candidate": {"symbol": candidate, "historical_name": matched.get("name"),
                          "prior_event_streak": matched.get("limit_up_days"),
                          "prior_break_events": matched.get("break_limit_up_times")} if candidate else None,
            "account_initial_cash": float(config["initial_cash"]),
            "target": "at most one share lot multiple, bounded by available cash and fees",
            "decision_checkpoint": config["decision_time"],
            "execution": "Review only after completed 09:35 signal; do not buy at upper limit; no fills without bar evidence.",
            "manual_checks": ["Actual broker account holdings and cash",
                              "Real market and ST status at decision time",
                              "Live order book liquidity and price-band",
                              "T+1 / locked holding or suspension constraints"],
            "orders_transmitted": 0}


def main():
    p=argparse.ArgumentParser(description="Manual human review, never broker execution.")
    p.add_argument("--dataset",type=Path,required=True)
    p.add_argument("--config",type=Path,default=Path("config/research.json"))
    p.add_argument("--research-report",type=Path)
    p.add_argument("--out",type=Path,default=Path("runs/follow-review.json"))
    a=p.parse_args()
    ds=json.loads(a.dataset.read_text(encoding="utf-8"))
    cfg=json.loads(a.config.read_text(encoding="utf-8"))
    prior=json.loads(a.research_report.read_text(encoding="utf-8")) if a.research_report else None
    value=build_review(ds,cfg,prior)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
