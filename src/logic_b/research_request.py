from __future__ import annotations

from dataclasses import asdict,dataclass
from datetime import date,datetime
import json
from pathlib import Path
from typing import Any


ALLOWED_FILLS={
    "optimistic",
    "realistic",
    "conservative",
    "all",
}


def _day(value: str) -> date:
    return datetime.strptime(
        value,
        "%Y-%m-%d",
    ).date()


@dataclass(frozen=True)
class ResearchRequest:
    request_id: str
    request_file: str
    start: str
    end: str
    preflight_date: str
    fill: str
    development_end: str
    promotion_relevance: str
    blind_holdout: bool

    def as_dict(self) -> dict[str,Any]:
        return asdict(self)

    def env(self) -> dict[str,str]:
        return {
            "REQUEST_ID":self.request_id,
            "REQUEST_FILE":self.request_file,
            "RUN_START":self.start,
            "RUN_END":self.end,
            "PREFLIGHT_DATE":self.preflight_date,
            "FILL_MODEL":self.fill,
        }


def load_research_request(
    request_path: str | Path,
    *,
    config: dict,
) -> ResearchRequest:
    path=Path(request_path)
    if not path.exists():
        raise ValueError(
            f"research request does not exist: {path}"
        )

    payload=json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(payload,dict):
        raise ValueError(
            "research request must be a JSON object"
        )

    window=payload.get("window")
    if not isinstance(window,dict):
        raise ValueError(
            "research request.window must be an object"
        )

    start=str(
        window.get("start") or ""
    )
    end=str(
        window.get("end") or ""
    )
    if not start or not end:
        raise ValueError(
            "request.window.start/end are required"
        )

    start_day=_day(start)
    end_day=_day(end)
    if start_day>end_day:
        raise ValueError(
            "request start must be <= end"
        )

    research=config.get(
        "research",
        {},
    )
    development_end=str(
        research.get(
            "development_end",
            "",
        )
    )
    if not development_end:
        raise ValueError(
            "config research.development_end is required"
        )
    development_end_day=_day(
        development_end
    )

    if end_day>development_end_day:
        raise ValueError(
            f"request end {end} exceeds frozen "
            f"development_end {development_end}"
        )

    preflight=str(
        payload.get(
            "preflight_date"
        )
        or end
    )
    preflight_day=_day(
        preflight
    )
    if not (
        start_day
        <=preflight_day
        <=end_day
    ):
        raise ValueError(
            "preflight_date must fall within "
            "the request window"
        )

    fill=str(
        payload.get(
            "fill"
        )
        or "all"
    )
    if fill not in ALLOWED_FILLS:
        raise ValueError(
            f"unsupported fill={fill}"
        )

    blind_holdout=bool(
        payload.get(
            "blind_holdout",
            False,
        )
    )
    if blind_holdout:
        raise ValueError(
            "request workflow cannot unlock or "
            "run blind holdout"
        )

    request_id=str(
        payload.get(
            "request_id"
        )
        or path.stem
    ).strip()
    if not request_id:
        raise ValueError(
            "request_id cannot be empty"
        )

    return ResearchRequest(
        request_id=request_id,
        request_file=str(path),
        start=start,
        end=end,
        preflight_date=preflight,
        fill=fill,
        development_end=
            development_end,
        promotion_relevance=str(
            payload.get(
                "promotion_relevance",
                "unspecified",
            )
        ),
        blind_holdout=False,
    )


def append_github_env(
    spec: ResearchRequest,
    env_path: str | Path,
) -> None:
    path=Path(env_path)
    with path.open(
        "a",
        encoding="utf-8",
    ) as fh:
        for name,value in spec.env().items():
            if "\n" in value or "\r" in value:
                raise ValueError(
                    f"invalid newline in env value {name}"
                )
            fh.write(
                f"{name}={value}\n"
            )
