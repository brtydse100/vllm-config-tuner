"""Generation sampling defaults and startup warnings shared by benchmark adapters."""

from collections.abc import Mapping
from math import isfinite

from vllm_optimizer.benchmarks.configuration import configured_engine, configured_runs
from vllm_optimizer.benchmarks.vllm_arguments import extra_body, normalized_benchmark_arguments
from vllm_optimizer.config.models import VTuneConfig

_GENERATION_ROUTES = {"/v1/completions", "/v1/chat/completions", "/v1/responses"}


def generation_temperature(run: Mapping[str, object]) -> float | None:
    if run.get("request_format", "/v1/completions") not in _GENERATION_ROUTES:
        if "temperature" in run:
            raise ValueError("benchmark temperature is supported only for generation request formats")
        return None
    return _temperature(run.get("temperature", 0))


def vllm_arguments(run: Mapping[str, object]) -> dict[str, object]:
    args = normalized_benchmark_arguments(run)
    args["temperature"] = _temperature(args.get("temperature", 0))
    body = extra_body(args)
    effective = _temperature(body.get("temperature", args["temperature"]))
    _completion_count(body.get("n", 1), effective)
    return args


def temperature_warnings(config: VTuneConfig) -> tuple[str, ...]:
    warnings = []
    for run in configured_runs(config):
        value: float | None
        if configured_engine(config) == "vllm":
            args = vllm_arguments(run)
            value = _temperature(extra_body(args).get("temperature", args["temperature"]))
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
        raise ValueError("benchmark temperature must be a finite number in [0, 2]")
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("benchmark temperature must be a finite number in [0, 2]") from error
    if not isfinite(number) or not 0 <= number <= 2:
        raise ValueError("benchmark temperature must be a finite number in [0, 2]")
    return number


def _completion_count(value: object, temperature: float) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise ValueError("vLLM benchmark extra-body n must be a positive integer")
    try:
        count = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("vLLM benchmark extra-body n must be a positive integer") from error
    if not isfinite(count) or not count.is_integer() or count < 1:
        raise ValueError("vLLM benchmark extra-body n must be a positive integer")
    if count > 1 and temperature == 0:
        raise ValueError("vLLM benchmark extra-body n > 1 requires an explicit nonzero temperature")
