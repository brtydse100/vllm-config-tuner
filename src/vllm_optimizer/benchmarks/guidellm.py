"""GuideLLM configuration, command construction, and result normalization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vllm_optimizer.benchmarks.metrics import normalize_guidellm_metrics
from vllm_optimizer.benchmarks.temperature import generation_temperature
from vllm_optimizer.benchmarks.timing import normalize_durations
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import model_path
from vllm_optimizer.domain.benchmark import BenchmarkResult, WorkloadResult


@dataclass(frozen=True, slots=True)
class GuideLLMPlan:
    run_name: str
    argv: tuple[str, ...]
    directory: Path
    json_path: Path
    log_path: Path


def configured_runs(config: VTuneConfig) -> tuple[Mapping[str, object], ...]:
    from vllm_optimizer.benchmarks.configuration import configured_runs as validate

    return validate(config)


def configured_repeats(config: VTuneConfig) -> int:
    from vllm_optimizer.benchmarks.configuration import configured_repeats as validate

    return validate(config)


def build_plan(config: VTuneConfig, run: Mapping[str, object], endpoint: str, artifacts: Path) -> GuideLLMPlan:
    name = run["name"]
    request_format = run.get("request_format", "/v1/completions")
    if not isinstance(request_format, str) or not request_format.strip():
        raise ValueError("benchmark request_format must be a non-empty string")
    backend: dict[str, object] = {
        "kind": "openai_http",
        "target": endpoint,
        "model": model_path(config),
        "request_format": request_format,
    }
    if (temperature := generation_temperature(run)) is not None:
        backend["extras"] = {"body": {"temperature": temperature}}
    directory = Path(artifacts) / str(name)
    json_path = directory / "results.json"
    argv = [
        "guidellm",
        "run",
        "--backend",
        _serialize(backend),
        "--profile",
        _serialize(_mapping(run.get("profile"), "profile")),
    ]
    for option, label in (("constraints", "constraint"), ("data", "data")):
        values = run.get(option, [])
        if not isinstance(values, list):
            raise ValueError(f"benchmark run '{option}' must be a list")
        for value in values:
            if label == "constraint" and isinstance(value, dict) and value.get("kind") == "max_duration":
                value = {**value, "seconds": normalize_durations(value.get("seconds"))}
            argv.extend((f"--{label}", _serialize(_mapping(value, label))))
    argv.extend(("--output", f"kind=json,path={json_path}"))
    return GuideLLMPlan(str(name), tuple(argv), directory, json_path, directory / "benchmark.log")


def parse_result(path: Path, run_name: str) -> BenchmarkResult:
    source = Path(path)
    try:
        root = _mapping(json.loads(source.read_text(encoding="utf-8")), "result")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read GuideLLM JSON result: {error}") from error
    metadata = _mapping(root.get("metadata"), "metadata")
    version = metadata.get("guidellm_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("GuideLLM result is missing its version")
    benchmarks = root.get("benchmarks")
    if not isinstance(benchmarks, list) or not benchmarks:
        raise ValueError("GuideLLM result must contain benchmarks")
    workloads = tuple(
        WorkloadResult(
            index,
            _mapping(item.get("config"), f"benchmark {index} config"),
            _normalized_metrics(_mapping(item.get("metrics"), f"benchmark {index} metrics")),
        )
        for index, value in enumerate(benchmarks)
        for item in (_mapping(value, f"benchmark {index}"),)
    )
    return BenchmarkResult(run_name, "guidellm", version, workloads, source)


def _normalized_metrics(raw: Mapping[str, object]) -> dict[str, object]:
    metrics = normalize_guidellm_metrics(raw)
    totals = raw.get("request_totals")
    if (
        isinstance(totals, Mapping)
        and isinstance(totals.get("total"), int)
        and not isinstance(totals.get("total"), bool)
    ):
        metrics["request_total"] = totals["total"]
    return metrics


def _serialize(values: Mapping[str, object]) -> str:
    kind = values.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("GuideLLM options require a non-empty 'kind'")
    return ",".join(pair for key, value in values.items() for pair in _pairs(key, value))


def _pairs(path: str, value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(pair for key, item in value.items() for pair in _pairs(f"{path}.{key}", item))
    if isinstance(value, list | tuple):
        return tuple(pair for index, item in enumerate(value) for pair in _pairs(f"{path}[{index}]", item))
    if isinstance(value, bool):
        rendered = str(value).lower()
    if isinstance(value, str | int | float) and not isinstance(value, bool):
        rendered = str(value)
    elif value is None:
        rendered = "null"
    elif not isinstance(value, bool):
        raise ValueError(f"Unsupported GuideLLM value at '{path}'")
    if "," in rendered:
        raise ValueError(f"GuideLLM string values cannot contain commas: '{path}'")
    return (f"{path}={rendered}",)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"GuideLLM {label} must be an object")
    return value
