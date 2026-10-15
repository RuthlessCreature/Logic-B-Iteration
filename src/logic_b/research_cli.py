"""Proposal generation and locked chronological strategy comparison."""
import argparse
import json
from pathlib import Path
from .research import training_summary, ask_llm_for_hypothesis, compare_candidate, save_result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("config/research.json"))
    p.add_argument("--out", type=Path, default=Path("runs/research"))
    p.add_argument("--proposal", type=Path, help="previously frozen JSON proposal")
    p.add_argument("--llm-model", help="generate ONE proposal with OpenAI API using TRAIN metrics ONLY")
    args = p.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    ds = json.loads(args.dataset.read_text(encoding="utf-8"))
    train = training_summary(ds, cfg)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "training_summary.json").write_text(json.dumps(train, ensure_ascii=False, indent=2), encoding="utf-8")
    if bool(args.proposal) == bool(args.llm_model):
        print("Training summary saved. To evaluate, provide --proposal <frozen.json> OR --llm-model <model>.")
        return
    prop = json.loads(args.proposal.read_text(encoding="utf-8")) if args.proposal else ask_llm_for_hypothesis(train, model=args.llm_model)
    from .research import proposal_digest
    digest = proposal_digest(prop)
    prop_path = args.out / f"proposal-{digest}.json"
    if prop_path.exists():
        if json.loads(prop_path.read_text(encoding="utf-8")) != prop:
            raise ValueError("proposal version collision")
    else:
        prop_path.write_text(json.dumps(prop, ensure_ascii=False, indent=2), encoding="utf-8")
    report = compare_candidate(ds, cfg, prop)
    out = args.out / f"evaluation-{digest}.json"
    save_result(report, out)
    print(json.dumps({"version": digest, "verdict": report["verdict"], "saved": str(out)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
