"""vLLM Bench Serve command construction and result normalization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlsplit

from vllm_optimizer.benchmarks.metrics import normalize_vllm_metrics
from vllm_optimizer.benchmarks.temperature import vllm_arguments
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import model_path
from vllm_optimizer.domain.benchmark import BenchmarkResult, WorkloadResult

_RESERVED = {
    "backend",
    "model",
    "host",
    "port",
    "base-url",
    "save-result",
    "append-result",
    "result-dir",
    "result-filename",
    "save-detailed",
}


@dataclass(frozen=True, slots=True)
class VLLMBenchPlan:
    run_name: str
    argv: tuple[str, ...]
    directory: Path
    json_path: Path
    log_path: Path


def build_plan(config: VTuneConfig, run: Mapping[str, object], endpoint: str, artifacts: Path) -> VLLMBenchPlan:
    name = str(run["name"])
    normalized = vllm_arguments(run)
    if protected := _RESERVED.intersection(normalized):
        raise ValueError(f"vLLM Optimizer controls vLLM benchmark argument(s): {', '.join(sorted(protected))}")
    parsed = urlsplit(endpoint)
    directory = Path(artifacts) / name
    result = directory / "results.json"
    argv = [
        "vllm",
        "bench",
        "serve",
        "--backend",
        "vllm",
        "--model",
        model_path(config),
        "--host",
        parsed.hostname or "127.0.0.1",
        "--port",
        str(parsed.port or 8000),
    ]
    for key, value in normalized.items():
        argv.extend(_argument(key, value))
    argv.extend(
        (
            "--save-result",
            "--save-detailed",
            "--result-dir",
            str(directory),
            "--result-filename",
            result.name,
            "--disable-tqdm",
        )
    )
    return VLLMBenchPlan(name, tuple(argv), directory, result, directory / "benchmark.log")


def parse_result(path: Path, run_name: str) -> BenchmarkResult:
    source = Path(path)
    try:
        document = _mapping(json.loads(source.read_text(encoding="utf-8")), "result")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read vLLM benchmark JSON result: {error}") from error
    metrics = normalize_vllm_metrics(document)
    if isinstance(document.get("num_prompts"), int) and not isinstance(document.get("num_prompts"), bool):
        metrics["request_total"] = document["num_prompts"]
    configuration = {
        key: document[key]
        for key in (
            "backend",
            "model_id",
            "num_prompts",
            "request_rate",
            "burstiness",
            "max_concurrency",
            "dataset_name",
        )
        if key in document
    }
    return BenchmarkResult(run_name, "vllm", _version(), (WorkloadResult(0, configuration, metrics),), source)


def _argument(name: str, value: object) -> tuple[str, ...]:
    flag = f"--{name}"
    if isinstance(value, bool):
        return (flag,) if value else ()
    if isinstance(value, list):
        return (flag, *(str(entry) for entry in value)) if value else ()
    if value is None or not isinstance(value, str | int | float):
        raise ValueError(f"Unsupported vLLM benchmark value for '{name}'")
    return flag, str(value)


def _version() -> str:
    try:
        return version("vllm")
    except PackageNotFoundError:
        return "unknown"


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return value
