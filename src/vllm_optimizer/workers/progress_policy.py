"""Benchmark progress limits and metrics parsing."""

from __future__ import annotations

import re
from collections.abc import Mapping

from vllm_optimizer.benchmarks.timing import parse_duration
from vllm_optimizer.benchmarks.vllm_arguments import normalized_benchmark_arguments

_SAMPLE = re.compile(
    r"^(?P<name>[^\s{]+)(?:\{(?P<labels>.*)\})?\s+"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)$"
)


def request_count(text: str, path: str) -> int | None:
    http_total = success_total = 0.0
    found_http = found_success = False
    for line in text.splitlines():
        match = _SAMPLE.match(line)
        if not match:
            continue
        name, labels, value = match.group("name", "labels", "value")
        if (
            name == "http_requests_total"
            and f'handler="{path}"' in (labels or "")
            and 'method="POST"' in (labels or "")
        ):
            http_total, found_http = http_total + float(value), True
        elif name == "vllm:request_success_total":
            success_total, found_success = success_total + float(value), True
    return int(http_total if found_http else success_total) if found_http or found_success else None


def progress_limit(engine: str, run: Mapping[str, object]) -> tuple[str | None, float]:
    if engine == "vllm":
        count = _integer(normalized_benchmark_arguments(run).get("num-prompts"))
        return ("requests", float(count)) if count > 0 else (None, 0)
    constraints = run.get("constraints", [])
    if isinstance(constraints, list):
        for item in constraints:
            if isinstance(item, Mapping) and item.get("kind") == "max_requests":
                value = item.get("count")
                if isinstance(value, int) and value > 0:
                    return "requests", float(value * _strategy_count(run.get("profile")))
        for item in constraints:
            if isinstance(item, Mapping) and item.get("kind") == "max_duration":
                values = item.get("seconds")
                durations = values if isinstance(values, list) else [values]
                return "time", sum(parse_duration(value) for value in durations) * _strategy_count(run.get("profile"))
    return None, 0


def request_path(engine: str, run: Mapping[str, object]) -> str:
    if engine == "guidellm":
        return str(run.get("request_format", "/v1/completions"))
    return str(normalized_benchmark_arguments(run).get("endpoint", "/v1/completions"))


def setup_requests(engine: str, run: Mapping[str, object]) -> int:
    if engine != "vllm":
        return 0
    args = normalized_benchmark_arguments(run)
    warmups = _integer(args.get("num-warmups", 0))
    initial = int(_integer(args.get("ready-check-timeout-sec", 0)) > 0)
    return initial + max(0, warmups)


def _integer(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return 0


def _strategy_count(profile: object) -> int:
    if not isinstance(profile, Mapping):
        return 1
    for key in ("streams", "rates"):
        if isinstance(value := profile.get(key), list):
            return max(1, len(value))
    value = profile.get("sweep_size")
    return value if isinstance(value, int) and value > 0 else 1
