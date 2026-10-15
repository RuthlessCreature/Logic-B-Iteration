"""LLM-proposed, deterministic and chronologically evaluated candidate strategy versions.

No model can write to price history, alter execution constraints, or execute orders.
Input to LLM contains TRAIN-only aggregated account statistics. The candidate is
frozen BEFORE validation results are computed, which remain audit-only.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from .replay import replay

TRAIN_END = "2024-12-31"
VALIDATION_START = "2025-01-01"

def validate_proposal(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {"hypothesis", "params", "risk", "name"}:
        raise ValueError("proposal needs exactly name, hypothesis, risk, params")
    if not all(isinstance(value[k], str) and 5 <= len(value[k]) <= 500 for k in ("name", "hypothesis", "risk")):
        raise ValueError("invalid hypothesis text")
    p = value["params"]
    if not isinstance(p, dict) or set(p) != {"min_streak", "max_breaks", "min_market_temperature"}:
        raise ValueError("only three permitted v0 strategy parameters")
    if type(p["min_streak"]) is not int or not 1 <= p["min_streak"] <= 4:
        raise ValueError("min_streak out of range")
    if type(p["max_breaks"]) is not int or not 0 <= p["max_breaks"] <= 5:
        raise ValueError("max_breaks out of range")
    t = p["min_market_temperature"]
    if t is not None and (type(t) not in (int, float) or not 0 <= t <= 90):
        raise ValueError("market gate out of range")
    return value


def proposal_digest(proposal: dict) -> str:
    return hashlib.sha256(json.dumps(proposal, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def training_summary(dataset: dict, config: dict) -> dict:
    scoped = dict(dataset, days=[day for day in dataset.get("days", []) if day["date"] <= TRAIN_END])
    result = replay(scoped, config)
    return {k: result[k] for k in ("classification", "status", "initial_cash", "final_equity",
                                    "return_pct", "max_drawdown_pct") } | {
        "training_end": TRAIN_END, "sessions": len(scoped["days"]),
        "closed_trades": len(result["closed_trades"]),
        "reason_counts": {r: sum(x.get("reason")==r for x in result["orders"])
                          for r in sorted(set(x.get("reason") for x in result["orders"]))},
    }


def ask_llm_for_hypothesis(train_summary: dict, *, model: str, api_key: str | None = None,
                           opener=urlopen) -> dict:
    """Optional OpenAI Responses API. Never transmit validation/holdout data."""
    token = api_key or os.environ.get("OPENAI_API_KEY")
    if not token:
        raise RuntimeError("OPENAI_API_KEY missing: save training summary and provide an offline proposal instead")
    schema = {"type": "object", "properties": {
        "name": {"type": "string"},
        "hypothesis": {"type": "string"},
        "risk": {"type": "string"},
        "params": {"type": "object", "properties": {
            "min_streak": {"type": "integer", "minimum": 1, "maximum": 4},
            "max_breaks": {"type": "integer", "minimum": 0, "maximum": 5},
            "min_market_temperature": {"type": ["number", "null"]},
        }, "additionalProperties": False, "required": ["min_streak", "max_breaks", "min_market_temperature"]},
    }, "additionalProperties": False, "required": ["name", "hypothesis", "risk", "params"]}
    prompt = ("You are a skeptical quant research hypothesis generator for a CNY 10,000 A-share "
              "T+1 model. Using ONLY TRAINING-period metrics, suggest ONE falsifiable change "
              "within the schema. Do not claim guaranteed returns or request future data. "
              "No trading API access; you are writing a hypothesis, not an order.\n"
              + json.dumps(train_summary, ensure_ascii=False, allow_nan=False))
    body = {"model": model, "input": prompt,
            "text": {"format": {"type": "json_schema", "name": "logic_b_proposal",
                                "schema": schema, "strict": True}}}
    request = Request("https://api.openai.com/v1/responses",
                      data=json.dumps(body).encode("utf-8"),
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with opener(request, timeout=90) as response:
        raw = json.loads(response.read().decode("utf-8"))
    if raw.get("status") != "completed":
        raise RuntimeError("LLM proposal response incomplete")
    texts = [block["text"] for item in raw.get("output", [])
             for block in item.get("content", []) if block.get("type") == "output_text"]
    if len(texts) != 1:
        raise RuntimeError("LLM did not supply exactly one structured proposal")
    return validate_proposal(json.loads(texts[0]))


def compare_candidate(dataset: dict, config: dict, proposal: dict) -> dict:
    proposal = validate_proposal(proposal)
    train_days = [x for x in dataset["days"] if x["date"] <= TRAIN_END]
    valid_days = [x for x in dataset["days"] if x["date"] >= VALIDATION_START]
    config_new = copy.deepcopy(config)
    config_new["baseline"] = copy.deepcopy(proposal["params"])
    rows = {}
    for part, days in (("train", train_days), ("validation", valid_days)):
        if not days:
            raise ValueError(f"no {part} days available")
        ds = {"days": days, "coverage_complete": bool(dataset.get("coverage_complete"))}
        rows[part] = {}
        for name, conf in (("baseline", config), ("proposal", config_new)):
            res = replay(ds, conf)
            rows[part][name] = {k: res[k] for k in
                                  ("status", "initial_cash", "final_equity", "return_pct", "max_drawdown_pct")} | {
                "closed_trades": len(res["closed_trades"]), "sessions": len(days),
                "unfilled": sum(x.get("reason", "").startswith(("NO_FILL", "LIMIT_BAND", "MISSING"))
                                for x in res["orders"])}
    valid = rows["validation"]
    reconciled = (all(r["return_pct"] is not None and r["max_drawdown_pct"] is not None
                      for period in rows.values() for r in period.values()))
    credible = (reconciled and dataset.get("coverage_complete") is True and
                len(valid_days) >= 100 and len(rows["train"] and train_days) >= 100 and
                valid["proposal"]["closed_trades"] >= 30 and
                valid["proposal"]["return_pct"] > 0 and
                valid["proposal"]["return_pct"] >= valid["baseline"]["return_pct"] + 1 and
                valid["proposal"]["max_drawdown_pct"] >= -25)
    verdict = "CANDIDATE_FOR_MANUAL_REVIEW" if credible else "NO_FOLLOW"
    return {"classification": "RESEARCH_SIMULATED_BAR_FILLS_NOT_FINANCIAL_ADVICE",
            "version": proposal_digest(proposal), "proposal": proposal,
            "time_split": {"train_end": TRAIN_END, "validation_start": VALIDATION_START},
            "results": rows, "verdict": verdict,
            "follow_instruction": "Never auto-execute; human approval, live data and broker checks required",
            "notes": "Validation is only a chronologically later development segment; repeated optimization contaminates it."}


def save_result(report: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError("immutable research result already exists")
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
