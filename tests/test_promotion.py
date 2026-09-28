from logic_b.promotion import evaluate_promotion


CFG={
    "require_positive_expectancy_conservative_fill":True,
    "min_conservative_expectancy":0.0,
    "min_conservative_closed_trades":30,
    "max_conservative_drawdown_abs":0.25,
    "require_multi_fold_stability":True,
    "min_walk_forward_folds":4,
    "min_positive_return_fold_rate":0.60,
    "min_positive_expectancy_fold_rate":0.60,
    "min_walk_forward_closed_trades":20,
    "require_human_alignment":True,
    "min_human_labels":80,
    "min_action_agreement":0.80,
    "min_selection_agreement":0.70,
    "min_core_type_agreement":0.75,
    "require_parameter_neighborhood_stability":True,
    "min_tested_parameter_neighbors":8,
    "complexity_penalty":True,
    "max_primary_rule_changes":1,
    "max_new_free_parameters":2,
}


GOOD_CONSERVATIVE={
    "closed_trades":50,
    "expectancy":0.012,
    "max_drawdown":-0.18,
}

GOOD_WF={
    "folds":6,
    "positive_return_fold_rate":0.67,
    "positive_expectancy_fold_rate":0.67,
    "closed_trades":42,
}

GOOD_ALIGNMENT={
    "matched_labels":120,
    "action_agreement":0.88,
    "selection_agreement":0.76,
    "core_type_agreement":0.81,
}

GOOD_STABILITY={
    "stable":True,
    "tested_neighbors":12,
}

GOOD_META={
    "primary_rule_changes":1,
    "new_free_parameters":1,
}


def test_promotion_passes_only_when_all_critical_gates_pass():
    result=evaluate_promotion(
        promotion_config=CFG,
        conservative_metrics=GOOD_CONSERVATIVE,
        walk_forward_summary=GOOD_WF,
        alignment_metrics=GOOD_ALIGNMENT,
        neighborhood_stability=GOOD_STABILITY,
        candidate_meta=GOOD_META,
    )
    assert result["status"]=="PASS"
    assert result["fail_count"]==0
    assert result["blocked_count"]==0


def test_missing_alignment_and_stability_blocks_promotion():
    result=evaluate_promotion(
        promotion_config=CFG,
        conservative_metrics=GOOD_CONSERVATIVE,
        walk_forward_summary=GOOD_WF,
        alignment_metrics=None,
        neighborhood_stability=None,
        candidate_meta=GOOD_META,
    )
    assert result["status"]=="BLOCKED"
    assert result["blocked_count"]>0
    assert result["fail_count"]==0


def test_bad_conservative_expectancy_fails_even_when_other_gates_pass():
    bad=dict(GOOD_CONSERVATIVE)
    bad["expectancy"]=-0.001

    result=evaluate_promotion(
        promotion_config=CFG,
        conservative_metrics=bad,
        walk_forward_summary=GOOD_WF,
        alignment_metrics=GOOD_ALIGNMENT,
        neighborhood_stability=GOOD_STABILITY,
        candidate_meta=GOOD_META,
    )
    assert result["status"]=="FAIL"
    gates={
        item["name"]:item
        for item in result["gates"]
    }
    assert (
        gates["conservative_expectancy"]["status"]
        =="FAIL"
    )


def test_complexity_cannot_be_compensated_by_good_returns():
    meta={
        "primary_rule_changes":3,
        "new_free_parameters":5,
    }
    result=evaluate_promotion(
        promotion_config=CFG,
        conservative_metrics=GOOD_CONSERVATIVE,
        walk_forward_summary=GOOD_WF,
        alignment_metrics=GOOD_ALIGNMENT,
        neighborhood_stability=GOOD_STABILITY,
        candidate_meta=meta,
    )
    assert result["status"]=="FAIL"
    assert result["fail_count"]>=2
