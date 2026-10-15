"""Luna Goal experiment dashboard: train iterations 2025, single frozen 2026H1 review.

No network, broker access, model calling or vendor data redistribution. The
experimental dashboard consumes an *already cached* dataset, tracks physical
storage bytes, and refuses 2020/2024 data in the active Goal. Validation is
examined ONCE only after a training-selected candidate is frozen.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import argparse
import csv
import json
from pathlib import Path

from .replay import replay
from .research import validate_proposal, proposal_digest, study_boundaries

def digest(v):
    return sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()

def split_days(dataset, cfg):
    train_start,train_end,valid_start,valid_end=study_boundaries(cfg)
    if (train_start,train_end,valid_start,valid_end)!=(
        "2025-01-01","2025-12-31","2026-01-01","2026-06-30"):
        raise ValueError("This Luna Goal requires 2025 training / 2026H1 validation")
    days=dataset.get("days")
    if not isinstance(days,list):
        raise ValueError("dataset.days must be array")
    dates=[d["date"] for d in days]
    if dates != sorted(set(dates)):
        raise ValueError("dates out of order or repeated")
    if any(not ("2025-01-01" <= d <= "2026-06-30") for d in dates):
        raise ValueError("date out of active Goal range")
    tr=[d for d in days if train_start <= d["date"] <= train_end]
    va=[d for d in days if valid_start <= d["date"] <= valid_end]
    if not tr or not va:
        raise ValueError("both 2025 training and 2026H1 validation source partitions are required")
    return tr,va

def physical_storage_inventory(root: Path):
    """Actual local filesystem bytes only, NEVER an invented R2 size."""
    if not root.exists():
        return {"local_root":str(root),"exists":False,"total_files":0,"total_bytes":0,
                "by_provider_year":[],"r2_actual_bytes":None,"r2_status":"NOT_CONNECTED"}
    counts=defaultdict(lambda:{"files":0,"bytes":0})
    total=0
    files=0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative=path.relative_to(root)
        parts=relative.parts
        provider=parts[0] if parts else "unknown"
        if provider=="raw" and len(parts)>1:
            provider=parts[1]
        # Date-partitioned events/minute files: read the *path*; daily
        # caches named by symbol are explicitly UNPARTITIONED.
        year="UNPARTITIONED"
        for part in parts:
            if len(part)>=4 and part[:4].isdigit() and part[:4] in ("2025","2026"):
                if (len(part)==4 or part[4] in "-_./"):
                    year=part[:4]
                    break
        size=path.stat().st_size
        counts[provider,year]["files"]+=1
        counts[provider,year]["bytes"]+=size
        total+=size
        files+=1
    return {"local_root":str(root),"exists":True,"total_files":files,
            "total_bytes":total,"total_mib":round(total/1048576,6),
            "by_provider_year":[{"provider":p,"year":y,**v}
                    for (p,y),v in sorted(counts.items())],
            "r2_actual_bytes":None,"r2_status":"NOT_CONNECTED",
            "storage_note":"Local physical file sizes, not estimated compression or R2 billable bytes"}

def _curve(outcome):
    return [{"date":r["day"],"equity":r["equity"],
             "reconciled":r.get("economically_reconciled",True)}
            for r in outcome["daily_equity"]]

def _stats(outcome):
    return {"sessions":len(outcome["daily_equity"]),
            "initial_cash":outcome["initial_cash"],
            "final_equity":outcome["final_equity"],
            "return_pct":outcome["return_pct"],
            "max_drawdown_pct":outcome["max_drawdown_pct"],
            "economic_reconciliation":outcome.get("economically_reconciled",False),
            "coverage_status":outcome["status"],
            "buy_fills":sum(x["side"]=="BUY" for x in outcome["fills"]),
            "sell_fills":sum(x["side"]=="SELL" for x in outcome["fills"]),
            "completed_trades":len(outcome["closed_trades"]),
            "order_reasons":dict(Counter(x["reason"] for x in outcome["orders"]))}

def _score(stats):
    # Fixed BEFORE any validation calls; insufficient historical coverage
    # means a candidate must not be promoted from a numeric point estimate.
    if stats["return_pct"] is None or stats["max_drawdown_pct"] is None:
        return None
    return round(stats["return_pct"] + 0.5*stats["max_drawdown_pct"],6)

def _write_csv(path,rows,columns):
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=columns)
        w.writeheader()
        w.writerows(rows)

def _svg(curves,title):
    """Portable standalone SVG line plot; no matplotlib/cloud dependencies."""
    width,height=1100,360
    left,right,top,bottom=72,22,55,50
    plot_w,plot_h=width-left-right,height-top-bottom
    entries=[(name,points) for name,points in curves if points]
    all_y=[p["equity"] for _,rows in entries for p in rows]
    if not all_y:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="180"><text x="30" y="50">NO EQUITY DATA</text></svg>'
    mi,ma=min(all_y),max(all_y)
    extra=max((ma-mi)*.07,1.)
    mi-=extra;ma+=extra
    max_n=max(len(rows) for _,rows in entries)
    colors=["#2563eb","#d97706","#059669","#be185d","#64748b"]
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}" style="max-width:100%;background:#fff">',
       f'<text x="{left}" y="28" font-size="19" font-family="sans-serif" font-weight="bold">{escape(title)}</text>']
    for n in range(5):
        value=mi+(ma-mi)*n/4
        y=top+plot_h*(1-n/4)
        s.append(f'<line x1="{left}" x2="{width-right}" y1="{y:.2f}" y2="{y:.2f}" stroke="#e5e7eb"/>')
        s.append(f'<text x="{left-8}" y="{y+4:.2f}" text-anchor="end" font-size="12" font-family="sans-serif">{value:,.0f}</text>')
    for i,(name,rows) in enumerate(entries):
        poly=[]
        for j,point in enumerate(rows):
            x=left+plot_w*(j/max(len(rows)-1,1))
            y=top+plot_h*(1-(point["equity"]-mi)/(ma-mi))
            poly.append(f'{x:.2f},{y:.2f}')
        color=colors[i%len(colors)]
        s.append(f'<polyline points="{" ".join(poly)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        s.append(f'<text x="{left+i*240}" y="{height-16}" font-size="12" font-family="sans-serif" fill="{color}">{escape(name)}</text>')
    s.append("</svg>")
    return "\n".join(s)

def execute_goal(dataset, config, proposals, out_dir:Path, storage_root:Path):
    tr,va=split_days(dataset,config)
    out_dir.mkdir(parents=True,exist_ok=True)
    data_fingerprint=digest({"dates":[d["date"] for d in dataset["days"]],"data":dataset["days"]})
    config_hash=digest(config)
    market_kind=dataset.get("classification","UNVERIFIED_SOURCE")
    synthetic=("SYNTHETIC" in market_kind.upper())
    # Training all iterations first. No validation replay until the candidate
    # is selected and its version hash is sealed.
    train_rows=[]
    snapshots=[]
    baseline=None
    conf_by_version={}
    seen=set()
    candidates=[("V0_BASELINE",None)] + [
        ("V"+str(i).zfill(2)+"_"+proposal_digest(p),validate_proposal(p))
        for i,p in enumerate(proposals,1)]
    for version,proposal in candidates:
        if version in seen:
            raise ValueError("duplicate version")
        seen.add(version)
        chosen_config=json.loads(json.dumps(config))
        if proposal is not None:
            chosen_config["baseline"]=proposal["params"]
        result=replay({"days":tr,"coverage_complete":dataset.get("coverage_complete") is True},chosen_config)
        stats=_stats(result)
        row={"iteration":len(train_rows),"version":version,
             "hypothesis":proposal["hypothesis"] if proposal else "Frozen original baseline",
             "parameters":chosen_config["baseline"],"train":stats,
             "train_score":_score(stats),"train_evidence":"SYNTHETIC" if synthetic else "HISTORICAL_PRICE_BAR_SIMULATION"}
        train_rows.append(row)
        conf_by_version[version]=chosen_config
        snapshots.append((version,_curve(result)))
        if baseline is None:
            baseline=row
    # Select from training only; invalid/unreconciled output cannot be trusted.
    valid_candidates=[r for r in train_rows if r["train_score"] is not None]
    valid_candidates.sort(key=lambda row:(-row["train_score"],row["iteration"]))
    selected=valid_candidates[0]["version"] if valid_candidates else None
    sealed={"selected_from_training_only":selected,
            "train_input_sha256":digest(tr),"config_sha256":config_hash,
            "version_digest":digest({"selected":selected,"training":train_rows})}
    (out_dir/"frozen_selection.json").write_text(json.dumps(sealed,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # Validation is opened once, only after selection. Baseline is included as
    # a comparison, even if it is itself the selected candidate.
    val_rows=[]
    val_curves=[]
    for version in dict.fromkeys(["V0_BASELINE",selected] if selected else ["V0_BASELINE"]):
        result=replay({"days":va,"coverage_complete":dataset.get("coverage_complete") is True},
                      conf_by_version[version])
        val_rows.append({"version":version,"validation":_stats(result)})
        val_curves.append((version,_curve(result)))
    inventory=physical_storage_inventory(storage_root)
    inventory["snapshot_bytes"]=len(json.dumps(dataset,ensure_ascii=False).encode("utf-8"))
    inventory["snapshot_bytes_type"]="uncompressed_input_JSON_UTF8_not_R2_actual_storage"
    (out_dir/"storage_inventory.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report={"classification":"SYNTHETIC_FIXTURE_NOT_TRADING_PROOF" if synthetic
                             else "EXPLORATORY_HISTORICAL_BAR_PRICE_SIMULATION",
            "goal_window":{"train_start":"2025-01-01","train_end":"2025-12-31",
                           "validation_start":"2026-01-01","validation_end":"2026-06-30"},
            "observed_sessions":{"train":len(tr),"validation":len(va)},
            "full_period_data_coverage":dataset.get("coverage_complete") is True,
            "data_sha256":data_fingerprint,"config_sha256":config_hash,
            "train_iterations":train_rows,
            "frozen_selection":sealed,"validation_once":val_rows,
            "storage":inventory,
            "status":"NOT_FULLY_VALIDATED" if synthetic or dataset.get("coverage_complete") is not True or
                      not selected else "DEVELOPMENT_VALIDATION_ONLY",
            "follow":"NO_FOLLOW",
            "notes":[
                "Train candidate selection cannot consult 2026 validation outcomes.",
                "The validation segment is development-exposed if repeatedly inspected across Goal cycles.",
                "Validation starts a separate CNY10000 research account, not one spliced continuous portfolio.",
                "Data coverage and corporate actions must be reconciled before inferring economic edge.",
                "This report never authorizes live orders or paid model API calls."]}
    (out_dir/"goal_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out_dir/"iteration_history.json").write_text(json.dumps(train_rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    _write_csv(out_dir/"iteration_history.csv",[
        {"iteration":r["iteration"],"version":r["version"],"train_return_pct":r["train"]["return_pct"],
         "train_mdd_pct":r["train"]["max_drawdown_pct"],"train_score":r["train_score"],
         "closed_trades":r["train"]["completed_trades"]} for r in train_rows],
        ["iteration","version","train_return_pct","train_mdd_pct","train_score","closed_trades"])
    _write_csv(out_dir/"training_equity.csv",[
        {"version":name,"date":v["date"],"equity":v["equity"],"reconciled":v["reconciled"]}
        for name,pts in snapshots for v in pts],["version","date","equity","reconciled"])
    _write_csv(out_dir/"validation_equity.csv",[
        {"version":name,"date":v["date"],"equity":v["equity"],"reconciled":v["reconciled"]}
        for name,pts in val_curves for v in pts],["version","date","equity","reconciled"])
    train_plot=_svg(snapshots,"2025 训练集 · 各迭代版本资金曲线")
    val_plot=_svg(val_curves,"2026上半年验证集 · 冻结冠军 vs V0")
    (out_dir/"training_equity.svg").write_text(train_plot,encoding="utf-8")
    (out_dir/"validation_equity.svg").write_text(val_plot,encoding="utf-8")
    rows_html="".join(
        "<tr>"+"".join(f"<td>{escape(str(v))}</td>" for v in (
            r["iteration"],r["version"],r["train"]["return_pct"],
            r["train"]["max_drawdown_pct"],r["train_score"],r["train"]["completed_trades"]
        ))+"</tr>" for r in train_rows)
    storage_html="".join(
        "<tr>"+"".join(f"<td>{escape(str(v))}</td>" for v in (
            x["provider"],x["year"],x["files"],x["bytes"]
        ))+"</tr>" for x in inventory["by_provider_year"])
    html=f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>Logic-B Luna Goal · 实验仪表板</title>
<style>body{{font:15px system-ui,sans-serif;max-width:1200px;margin:30px auto;padding:0 20px;color:#1f2937}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}.warn{{background:#fff7ed;padding:15px;border-radius:8px}}.meta{{color:#64748b}}h1{{font-size:26px}}</style>
<h1>Logic-B · Luna Goal 迭代仪表板</h1><p class=warn>此看板{"只含合成演示数据，没有真实市场收益。" if synthetic else "含历史价格Bar模拟，并非实盘成交记录。"} 当前状态：{escape(report["status"])}，不可据此自动Follow。</p>
<p>训练：2025-01-01 ~ 2025-12-31；验证：2026-01-01 ~ 2026-06-30；初始资金均为 ¥10,000（两个独立评估账户）。</p>
<p class=meta>数据SHA256：{data_fingerprint}；配置SHA256：{config_hash}</p>
<h2>训练期：迭代资金曲线</h2>{train_plot}
<h2>训练期：版本变更结果</h2><table><thead><tr><th>轮次</th><th>版本</th><th>收益%</th><th>最大回撤%</th><th>固定训练评分</th><th>平仓笔数</th></tr></thead><tbody>{rows_html}</tbody></table>
<p>训练期优选：{escape(str(selected))}；版本在查看验证结果前冻结。无法可靠估值时收益/评分为null，不可据此认定改善。</p>
<h2>验证期：冻结版本 vs 原始V0</h2>{val_plot}
<h2>数据真实物理存储（本地/工作机）</h2>
<p>扫描根目录：{escape(str(storage_root))}；文件：{inventory["total_files"]}；合计：{inventory["total_bytes"]:,} bytes（{inventory.get("total_mib",0)} MiB）。R2当前：{escape(inventory["r2_status"])}。</p>
<table><thead><tr><th>分区/来源</th><th>年份</th><th>文件</th><th>实际字节</th></tr></thead><tbody>{storage_html}</tbody></table>
<p>输入数据序列化长度：{inventory["snapshot_bytes"]:,} bytes，非真实存储收费容量。原始数据及详细账本不应直接提交公开GitHub。</p>
</html>"""
    (out_dir/"dashboard.html").write_text(html,encoding="utf-8")
    return report

def main():
    parser=argparse.ArgumentParser(description="2025 train/2026H1 validation Goal dashboard")
    parser.add_argument("--dataset",type=Path,required=True)
    parser.add_argument("--config",type=Path,default=Path("config/goal_2025_2026.json"))
    parser.add_argument("--proposals",type=Path,nargs="*",default=[])
    parser.add_argument("--data-root",type=Path,default=Path("data"))
    parser.add_argument("--out",type=Path,default=Path("runs/goal_2025_2026"))
    arg=parser.parse_args()
    dataset=json.loads(arg.dataset.read_text(encoding="utf-8"))
    config=json.loads(arg.config.read_text(encoding="utf-8"))
    props=[json.loads(p.read_text(encoding="utf-8")) for p in arg.proposals]
    result=execute_goal(dataset,config,props,arg.out,arg.data_root)
    print(json.dumps({"status":result["status"],"train_sessions":result["observed_sessions"]["train"],
                      "validation_sessions":result["observed_sessions"]["validation"],
                      "selected":result["frozen_selection"]["selected_from_training_only"],
                      "iterations":len(result["train_iterations"]),
                      "stored_files":result["storage"]["total_files"],
                      "physical_bytes":result["storage"]["total_bytes"],
                      "dashboard":str(arg.out/"dashboard.html")},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
