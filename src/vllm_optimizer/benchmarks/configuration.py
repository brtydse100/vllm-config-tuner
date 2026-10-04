"""Shared benchmark configuration validation."""

import re
from collections.abc import Mapping

from vllm_optimizer.config.models import VTuneConfig

_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_ENGINES = {"guidellm", "vllm"}


def configured_engine(config: VTuneConfig) -> str:
    value = config.benchmark.get("engine", "guidellm")
    if not isinstance(value, str) or value not in _ENGINES:
        raise ValueError("benchmark.engine must be 'guidellm' or 'vllm'")
    return value


def configured_repeats(config: VTuneConfig) -> int:
    value = config.benchmark.get("repeats", 4)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("benchmark.repeats must be a positive integer")
    return value


def configured_warmup_repeats(config: VTuneConfig) -> int:
    value = config.benchmark.get("warmup_repeats", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("benchmark.warmup_repeats must be a non-negative integer")
    return value


def configured_min_repeats(config: VTuneConfig) -> int:
    default = 2 if "adaptive_repeats" in config.benchmark else 4
    value = config.benchmark.get("min_repeats", min(default, configured_repeats(config)))
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("benchmark.min_repeats must be a positive integer")
    if value > configured_repeats(config):
        raise ValueError("benchmark.min_repeats cannot exceed benchmark.repeats")
    return value


def configured_failure_percentage(config: VTuneConfig) -> float:
    accept_any = config.benchmark.get("accept_any_request_failures", False)
    if not isinstance(accept_any, bool):
        raise ValueError("benchmark.accept_any_request_failures must be true or false")
    if accept_any:
        return 100.0
    value = config.benchmark.get("max_failure_percentage", 0)
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
        raise ValueError("benchmark.max_failure_percentage must be between 0 and 100")
    return float(value)


def configured_runs(config: VTuneConfig) -> tuple[Mapping[str, object], ...]:
    unknown = set(config.benchmark) - {
        "engine",
        "runs",
        "repeats",
        "warmup_repeats",
        "min_repeats",
        "max_failure_percentage",
        "accept_any_request_failures",
        "adaptive_repeats",
    }
    if unknown:
        raise ValueError(f"Unsupported benchmark setting(s): {', '.join(sorted(unknown))}")
    values = config.benchmark.get("runs")
    if not isinstance(values, list) or not values:
        raise ValueError("'benchmark.runs' must be a non-empty list")
    engine, names = configured_engine(config), set()
    runs: list[Mapping[str, object]] = []
    for index, value in enumerate(values):
        run = _mapping(value, f"run {index}")
        name = run.get("name")
        if not isinstance(name, str) or not _RUN_NAME.fullmatch(name):
            raise ValueError("benchmark run names must use letters, numbers, '_' or '-'")
        if name in names:
            raise ValueError(f"duplicate benchmark run name: {name}")
        names.add(name)
        _validate_run(engine, run, index, name)
        runs.append(run)
    return tuple(runs)


def _validate_run(engine: str, run: Mapping[str, object], index: int, name: str) -> None:
    allowed = (
        {"name", "request_format", "temperature", "profile", "constraints", "data"}
        if engine == "guidellm"
        else {"name", "args"}
    )
    if unknown := set(run) - allowed:
        raise ValueError(f"Unsupported setting(s) in benchmark run {index}: {', '.join(sorted(unknown))}")
    if engine == "guidellm":
        data = run.get("data")
        if not isinstance(data, list) or len(data) != 1:
            raise ValueError(f"benchmark run '{name}' must configure exactly one dataset")
    else:
        _mapping(run.get("args", {}), f"vllm benchmark run '{name}' args")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return value
