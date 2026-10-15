from __future__ import annotations

from dataclasses import asdict,dataclass
from enum import StrEnum
import math
from typing import Any


class GateStatus(StrEnum):
    PASS="PASS"
    FAIL="FAIL"
    BLOCKED="BLOCKED"


@dataclass(frozen=True)
class GateResult:
    name: str
    status: GateStatus
    observed: Any
    requirement: Any
    reason: str

    def as_dict(self) -> dict:
        out=asdict(self)
        out["status"]=self.status.value
        return out


def _number(
    mapping: dict | None,
    key: str,
) -> float | None:
    if not mapping:
        return None
    value=mapping.get(key)
    if value is None:
        return None
    try:
        number=float(value)
    except (TypeError,ValueError):
        return None
    return (
        number
        if math.isfinite(number)
        else None
    )


def _gate_min(
    *,
    name: str,
    observed: float | None,
    minimum: float,
    missing_reason: str,
) -> GateResult:
    if observed is None:
        return GateResult(
            name,
            GateStatus.BLOCKED,
            None,
            {"min":minimum},
            missing_reason,
        )
    return GateResult(
        name,
        (
            GateStatus.PASS
            if observed>=minimum
            else GateStatus.FAIL
        ),
        observed,
        {"min":minimum},
        (
            "meets minimum"
            if observed>=minimum
            else "below minimum"
        ),
    )


def _gate_gt(
    *,
    name: str,
    observed: float | None,
    minimum_exclusive: float,
    missing_reason: str,
) -> GateResult:
    if observed is None:
        return GateResult(
            name,
            GateStatus.BLOCKED,
            None,
            {"gt":minimum_exclusive},
            missing_reason,
        )
    passed=observed>minimum_exclusive
    return GateResult(
        name,
        (
            GateStatus.PASS
            if passed
            else GateStatus.FAIL
        ),
        observed,
        {"gt":minimum_exclusive},
        (
            "strictly above threshold"
            if passed
            else "not strictly above threshold"
        ),
    )


def _gate_max_abs_drawdown(
    *,
    observed: float | None,
    maximum_abs: float,
) -> GateResult:
    if observed is None:
        return GateResult(
            "conservative_max_drawdown",
            GateStatus.BLOCKED,
            None,
            {"max_abs":maximum_abs},
            "conservative max_drawdown missing",
        )
    abs_dd=abs(float(observed))
    return GateResult(
        "conservative_max_drawdown",
        (
            GateStatus.PASS
            if abs_dd<=maximum_abs
            else GateStatus.FAIL
        ),
        observed,
        {"max_abs":maximum_abs},
        (
            "drawdown within limit"
            if abs_dd<=maximum_abs
            else "drawdown exceeds limit"
        ),
    )


def evaluate_promotion(
    *,
    promotion_config: dict,
    conservative_metrics: dict | None,
    walk_forward_summary: dict | None,
    alignment_metrics: dict | None=None,
    neighborhood_stability: dict | None=None,
    candidate_meta: dict | None=None,
) -> dict:
    """Evaluate a candidate version without producing a compensating score.

    Critical gates are conjunctive. A strong return cannot cancel a missing
    semantic-alignment or robustness check.
    """
    cfg=promotion_config
    gates: list[GateResult]=[]

    gates.append(
        _gate_min(
            name="conservative_closed_trades",
            observed=_number(
                conservative_metrics,
                "closed_trades",
            ),
            minimum=float(
                cfg.get(
                    "min_conservative_closed_trades",
                    30,
                )
            ),
            missing_reason=
                "conservative trade count missing",
        )
    )

    if cfg.get(
        "require_positive_expectancy_conservative_fill",
        True,
    ):
        gates.append(
            _gate_gt(
                name="conservative_expectancy",
                observed=_number(
                    conservative_metrics,
                    "expectancy",
                ),
                minimum_exclusive=float(
                    cfg.get(
                        "min_conservative_expectancy",
                        0.0,
                    )
                ),
                missing_reason=
                    "conservative expectancy missing or non-finite",
            )
        )

    gates.append(
        _gate_max_abs_drawdown(
            observed=_number(
                conservative_metrics,
                "max_drawdown",
            ),
            maximum_abs=float(
                cfg.get(
                    "max_conservative_drawdown_abs",
                    0.25,
                )
            ),
        )
    )

    if cfg.get(
        "require_multi_fold_stability",
        True,
    ):
        gates.extend([
            _gate_min(
                name="walk_forward_folds",
                observed=_number(
                    walk_forward_summary,
                    "folds",
                ),
                minimum=float(
                    cfg.get(
                        "min_walk_forward_folds",
                        4,
                    )
                ),
                missing_reason=
                    "walk-forward summary missing",
            ),
            _gate_min(
                name="positive_return_fold_rate",
                observed=_number(
                    walk_forward_summary,
                    "positive_return_fold_rate",
                ),
                minimum=float(
                    cfg.get(
                        "min_positive_return_fold_rate",
                        0.60,
                    )
                ),
                missing_reason=
                    "positive-return fold rate missing",
            ),
            _gate_min(
                name="positive_expectancy_fold_rate",
                observed=_number(
                    walk_forward_summary,
                    "positive_expectancy_fold_rate",
                ),
                minimum=float(
                    cfg.get(
                        "min_positive_expectancy_fold_rate",
                        0.60,
                    )
                ),
                missing_reason=
                    "positive-expectancy fold rate missing",
            ),
            _gate_min(
                name="walk_forward_closed_trades",
                observed=_number(
                    walk_forward_summary,
                    "closed_trades",
                ),
                minimum=float(
                    cfg.get(
                        "min_walk_forward_closed_trades",
                        20,
                    )
                ),
                missing_reason=
                    "walk-forward trade count missing",
            ),
        ])

    if cfg.get(
        "require_human_alignment",
        True,
    ):
        gates.extend([
            _gate_min(
                name="human_labels",
                observed=_number(
                    alignment_metrics,
                    "matched_labels",
                ),
                minimum=float(
                    cfg.get(
                        "min_human_labels",
                        80,
                    )
                ),
                missing_reason=
                    "B0-H alignment has not been supplied",
            ),
            _gate_min(
                name="action_agreement",
                observed=_number(
                    alignment_metrics,
                    "action_agreement",
                ),
                minimum=float(
                    cfg.get(
                        "min_action_agreement",
                        0.80,
                    )
                ),
                missing_reason=
                    "B0-H action agreement missing",
            ),
            _gate_min(
                name="selection_agreement",
                observed=_number(
                    alignment_metrics,
                    "selection_agreement",
                ),
                minimum=float(
                    cfg.get(
                        "min_selection_agreement",
                        0.70,
                    )
                ),
                missing_reason=
                    "B0-H selection agreement missing",
            ),
            _gate_min(
                name="core_type_agreement",
                observed=_number(
                    alignment_metrics,
                    "core_type_agreement",
                ),
                minimum=float(
                    cfg.get(
                        "min_core_type_agreement",
                        0.75,
                    )
                ),
                missing_reason=
                    "B0-H core-type agreement missing",
            ),
        ])

    if cfg.get(
        "require_parameter_neighborhood_stability",
        True,
    ):
        stable=(
            neighborhood_stability.get("stable")
            if neighborhood_stability
            else None
        )
        neighbors=_number(
            neighborhood_stability,
            "tested_neighbors",
        )
        min_neighbors=float(
            cfg.get(
                "min_tested_parameter_neighbors",
                8,
            )
        )

        if stable is None:
            gates.append(
                GateResult(
                    "parameter_neighborhood_stable",
                    GateStatus.BLOCKED,
                    None,
                    True,
                    "parameter-neighborhood study missing",
                )
            )
        else:
            gates.append(
                GateResult(
                    "parameter_neighborhood_stable",
                    (
                        GateStatus.PASS
                        if bool(stable)
                        else GateStatus.FAIL
                    ),
                    bool(stable),
                    True,
                    (
                        "neighborhood marked stable"
                        if bool(stable)
                        else "neighborhood marked unstable"
                    ),
                )
            )

        gates.append(
            _gate_min(
                name="tested_parameter_neighbors",
                observed=neighbors,
                minimum=min_neighbors,
                missing_reason=
                    "tested-neighbor count missing",
            )
        )

    if cfg.get(
        "complexity_penalty",
        True,
    ):
        rule_changes=_number(
            candidate_meta,
            "primary_rule_changes",
        )
        free_parameters=_number(
            candidate_meta,
            "new_free_parameters",
        )

        max_rule_changes=float(
            cfg.get(
                "max_primary_rule_changes",
                1,
            )
        )
        max_free_parameters=float(
            cfg.get(
                "max_new_free_parameters",
                2,
            )
        )

        if rule_changes is None:
            gates.append(
                GateResult(
                    "primary_rule_changes",
                    GateStatus.BLOCKED,
                    None,
                    {"max":max_rule_changes},
                    "candidate complexity metadata missing",
                )
            )
        else:
            gates.append(
                GateResult(
                    "primary_rule_changes",
                    (
                        GateStatus.PASS
                        if rule_changes<=max_rule_changes
                        else GateStatus.FAIL
                    ),
                    rule_changes,
                    {"max":max_rule_changes},
                    (
                        "rule-change count within limit"
                        if rule_changes<=max_rule_changes
                        else "too many primary rule changes"
                    ),
                )
            )

        if free_parameters is None:
            gates.append(
                GateResult(
                    "new_free_parameters",
                    GateStatus.BLOCKED,
                    None,
                    {"max":max_free_parameters},
                    "candidate free-parameter metadata missing",
                )
            )
        else:
            gates.append(
                GateResult(
                    "new_free_parameters",
                    (
                        GateStatus.PASS
                        if free_parameters<=max_free_parameters
                        else GateStatus.FAIL
                    ),
                    free_parameters,
                    {"max":max_free_parameters},
                    (
                        "free-parameter count within limit"
                        if free_parameters<=max_free_parameters
                        else "too many new free parameters"
                    ),
                )
            )

    statuses=[
        gate.status
        for gate in gates
    ]
    overall=(
        GateStatus.FAIL
        if GateStatus.FAIL in statuses
        else (
            GateStatus.BLOCKED
            if GateStatus.BLOCKED in statuses
            else GateStatus.PASS
        )
    )

    return {
        "status":overall.value,
        "pass_count":sum(
            status==GateStatus.PASS
            for status in statuses
        ),
        "fail_count":sum(
            status==GateStatus.FAIL
            for status in statuses
        ),
        "blocked_count":sum(
            status==GateStatus.BLOCKED
            for status in statuses
        ),
        "gates":[
            gate.as_dict()
            for gate in gates
        ],
    }
