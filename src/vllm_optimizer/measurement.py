"""Small, dependency-free summaries for repeated benchmark measurements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import fmean, median

_T_95 = (
    0.0,
    12.706,
    4.303,
    3.182,
    2.776,
    2.571,
    2.447,
    2.365,
    2.306,
    2.262,
    2.228,
    2.201,
    2.179,
    2.160,
    2.145,
    2.131,
    2.120,
    2.110,
    2.101,
    2.093,
    2.086,
    2.080,
    2.074,
    2.069,
    2.064,
    2.060,
    2.056,
    2.052,
    2.048,
    2.045,
    2.042,
)


@dataclass(frozen=True, slots=True)
class MeasurementSummary:
    count: int
    mean: float
    median: float
    variance: float | None
    confidence_low: float | None
    confidence_high: float | None
    minimum_repeats_met: bool


def summarize(values: Iterable[float], minimum_repeats: int = 2) -> MeasurementSummary:
    samples = tuple(float(value) for value in values)
    if minimum_repeats < 1 or not samples:
        raise ValueError("measurements and minimum_repeats must be positive")
    average = fmean(samples)
    if len(samples) < 2:
        return MeasurementSummary(
            len(samples), average, median(samples), None, None, None, len(samples) >= minimum_repeats
        )
    variance = fmean((value - average) ** 2 for value in samples) * len(samples) / (len(samples) - 1)
    degrees = len(samples) - 1
    critical = _T_95[degrees] if degrees < len(_T_95) else _student_t_critical(degrees)
    margin = critical * sqrt(variance / len(samples))
    return MeasurementSummary(
        len(samples),
        average,
        median(samples),
        variance,
        average - margin,
        average + margin,
        len(samples) >= minimum_repeats,
    )


def _student_t_critical(degrees: int) -> float:
    """Approximate the two-sided 95% Student's t quantile for large degrees of freedom."""
    z = 1.959963984540054
    inverse = 1.0 / degrees
    return (
        z
        + (z**3 + z) * inverse / 4
        + (5 * z**5 + 16 * z**3 + 3 * z) * inverse**2 / 96
        + (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) * inverse**3 / 384
    )


def drifted(before: float, after: float, threshold: float = 0.05) -> bool:
    """Return true when sequential measurements differ by the relative threshold."""
    validate_drift_threshold(threshold)
    scale = max(abs(before), 1e-12)
    return abs(after - before) / scale > threshold


def sequentially_drifted(values: Iterable[float], threshold: float = 0.05) -> bool:
    validate_drift_threshold(threshold)
    drift = sequential_drift(values)
    if drift is None:
        return False
    return abs(drift) > threshold


def validate_drift_threshold(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value) or value < 0:
        raise ValueError("drift_threshold must be finite and non-negative")
    return float(value)


def sequential_drift(values: Iterable[float]) -> float | None:
    """Return signed relative change from the first half mean to the second."""
    samples = tuple(float(value) for value in values)
    if len(samples) < 4:
        return None
    midpoint = len(samples) // 2
    before, after = fmean(samples[:midpoint]), fmean(samples[midpoint:])
    return (after - before) / max(abs(before), 1e-12)


def benchmark_samples(benchmarks: Iterable[Mapping[str, object]], metric: str) -> dict[str, tuple[float, ...]]:
    grouped: dict[str, list[float]] = {}
    for benchmark in benchmarks:
        raw_workloads = benchmark.get("workloads", ())
        if not isinstance(raw_workloads, Iterable):
            continue
        values = [
            _metric(workload.get("metrics", {}), metric) for workload in raw_workloads if isinstance(workload, Mapping)
        ]
        scores = [value for value in values if value is not None]
        if scores:
            grouped.setdefault(str(benchmark.get("name", "unknown")), []).append(fmean(scores))
    return {name: tuple(values) for name, values in grouped.items()}


def _metric(metrics: object, name: str) -> float | None:
    if not isinstance(metrics, Mapping):
        return None
    value = metrics.get(name)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, Mapping):
        average = value.get("average", value.get("mean"))
        if isinstance(average, int | float) and not isinstance(average, bool):
            return float(average)
    return None
