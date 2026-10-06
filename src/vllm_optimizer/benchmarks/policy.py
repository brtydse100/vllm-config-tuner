"""Effective benchmark policy persisted with run results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace

from vllm_optimizer.benchmarks.configuration import (
    configured_failure_percentage,
    configured_min_repeats,
    configured_repeats,
    configured_warmup_repeats,
)
from vllm_optimizer.config.adaptive_repeats import adaptive_repeat_policy
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.measurement import validate_drift_threshold


@dataclass(frozen=True, slots=True)
class BenchmarkPolicy:
    repeats: int = 4
    minimum_repeats: int = 4
    warmup_repeats: int = 0
    drift_threshold: float = 0.05
    maximum_failure_percentage: float = 0.0
    repeat_aggregation: str = "mean"
    adaptive_minimum_relative_score: float | None = None

    def __post_init__(self) -> None:
        validate_drift_threshold(self.drift_threshold)

    def to_dict(self) -> dict[str, int | float | str]:
        return {name: value for name, value in asdict(self).items() if value is not None}

    def with_maximum(self, maximum: float) -> BenchmarkPolicy:
        return replace(self, maximum_failure_percentage=maximum)


def effective_policy(config: VTuneConfig) -> BenchmarkPolicy:
    drift = validate_drift_threshold(config.analysis.get("drift_threshold", 0.05))
    adaptive = adaptive_repeat_policy(config)
    return BenchmarkPolicy(
        configured_repeats(config),
        configured_min_repeats(config),
        configured_warmup_repeats(config),
        float(drift),
        configured_failure_percentage(config),
        "mean",
        adaptive.minimum_relative_score if adaptive else None,
    )


def stored_policy(document: Mapping[str, object], benchmark: Mapping[str, object]) -> BenchmarkPolicy:
    stored = document.get("benchmark_policy")
    values = stored if isinstance(stored, Mapping) else benchmark
    repeats = _integer(values.get("repeats"), 4)
    adaptive = values.get("adaptive_minimum_relative_score")
    minimum = _integer(
        values.get("minimum_repeats", values.get("min_repeats")), min(2 if adaptive is not None else 4, repeats)
    )
    warmups = _integer(values.get("warmup_repeats"), 0, allow_zero=True)
    drift = _number(values.get("drift_threshold"), 0.05)
    if values is benchmark and benchmark.get("accept_any_request_failures") is True:
        maximum = 100.0
    else:
        maximum = _number(values.get("maximum_failure_percentage", values.get("max_failure_percentage")), 0.0)
    aggregation = values.get("repeat_aggregation", "median")
    if aggregation not in ("mean", "median"):
        raise ValueError("stored repeat aggregation must be mean or median")
    if adaptive is not None and (
        isinstance(adaptive, bool) or not isinstance(adaptive, int | float) or not 0 < adaptive <= 1
    ):
        raise ValueError("stored adaptive repeat threshold must be between 0 and 1")
    return BenchmarkPolicy(
        repeats, minimum, warmups, drift, maximum, str(aggregation), float(adaptive) if adaptive is not None else None
    )


def _integer(value: object, default: int, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= minimum else default


def _number(value: object, default: float) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
