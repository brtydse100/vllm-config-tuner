"""Generation sampling defaults and startup warnings shared by benchmark adapters."""

import json
from collections.abc import Mapping
from math import isfinite

from vllm_optimizer.benchmarks.configuration import configured_engine, configured_runs
from vllm_optimizer.config.arguments import normalized_arguments
from vllm_optimizer.config.models import VTuneConfig

_GENERATION_ROUTES = {"/v1/completions", "/v1/chat/completions", "/v1/responses"}


def generation_temperature(run: Mapping[str, object]) -> float | None:
    if run.get("request_format", "/v1/completions") not in _GENERATION_ROUTES:
        if "temperature" in run:
            raise ValueError("benchmark temperature is supported only for generation request formats")
        return None
    return _temperature(run.get("temperature", 0))


def vllm_arguments(run: Mapping[str, object]) -> dict[str, object]:
    raw = run.get("args", {})
    if not isinstance(raw, Mapping):
        raise ValueError("vLLM benchmark args must be an object")
    args = normalized_arguments(raw, "vLLM benchmark arguments")
    args["temperature"] = _temperature(args.get("temperature", 0))
    body = _extra_body(args)
    if "temperature" in body:
        _temperature(body["temperature"])
    return args


def temperature_warnings(config: VTuneConfig) -> tuple[str, ...]:
    warnings = []
    for run in configured_runs(config):
        value: float | None
        if configured_engine(config) == "vllm":
            args = vllm_arguments(run)
            value = _temperature(_extra_body(args).get("temperature", args["temperature"]))
        else:
            value = generation_temperature(run)
        if value is not None and value != 0:
            warnings.append(
                f"Benchmark '{run['name']}' uses temperature={value:g}; use temperature=0 for repeatable generation. "
                "Sampling can change generated tokens and benchmark results."
            )
    return tuple(warnings)


def _temperature(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise ValueError("benchmark temperature must be a finite, non-negative number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("benchmark temperature must be a finite, non-negative number") from error
    if not isfinite(number) or number < 0:
        raise ValueError("benchmark temperature must be a finite, non-negative number")
    return number


def _extra_body(args: Mapping[str, object]) -> Mapping[str, object]:
    if "extra-body" not in args:
        return {}
    try:
        value = args["extra-body"]
        body = json.loads(value) if isinstance(value, str) else None
    except (ValueError, TypeError) as error:
        raise ValueError("vLLM benchmark extra-body must be a JSON object string") from error
    if not isinstance(body, dict):
        raise ValueError("vLLM benchmark extra-body must be a JSON object string")
    return body
