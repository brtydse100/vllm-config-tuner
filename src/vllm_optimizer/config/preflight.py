"""Complete, side-effect-free validation for a runnable configuration."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import islice
from pathlib import Path

from vllm_optimizer.benchmarks.configuration import (
    configured_engine,
    configured_failure_percentage,
    configured_min_repeats,
    configured_repeats,
    configured_runs,
    configured_warmup_repeats,
)
from vllm_optimizer.benchmarks.guidellm import build_plan as build_guidellm_plan
from vllm_optimizer.benchmarks.timing import timeout_for_run
from vllm_optimizer.benchmarks.vllm import build_plan as build_vllm_plan
from vllm_optimizer.config.adaptive_repeats import adaptive_repeat_policy
from vllm_optimizer.config.arguments import canonical_argument_name, normalized_arguments
from vllm_optimizer.config.endpoints import http_endpoint
from vllm_optimizer.config.errors import ConfigValidationError
from vllm_optimizer.config.finalist_validation import finalist_policy
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.runtime import (
    baseline_enabled,
    duration,
    max_attempts,
    maximize_metric,
    positive,
    server_port,
)
from vllm_optimizer.execution.slots import WorkerSlot, worker_slots
from vllm_optimizer.measurement import validate_drift_threshold
from vllm_optimizer.reporting.llm_summary import settings as llm_settings
from vllm_optimizer.search.factory import validate_search
from vllm_optimizer.search.grid import TrialParameters, definition_values, iter_grid
from vllm_optimizer.workers.configuration import build_process_spec

_EXECUTION_KEYS = {
    "mode",
    "max_parallel_trials",
    "gpu_allocation",
    "ports",
    "host",
    "health_path",
    "shutdown_grace",
    "drain_grace",
    "retry",
}


def validate_config(config: VTuneConfig, selected_trials: Sequence[TrialParameters] | None = None) -> None:
    """Validate every value that can be checked before a run starts."""
    try:
        _validate(config, selected_trials)
    except ConfigValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise ConfigValidationError(f"Invalid configuration: {error}") from error


def _validate(config: VTuneConfig, selected_trials: Sequence[TrialParameters] | None) -> None:
    unknown = set(config.execution) - _EXECUTION_KEYS
    if unknown:
        raise ValueError(f"unknown execution setting(s): {', '.join(sorted(unknown))}")
    if set(config.timeouts) - {"startup", "benchmark"}:
        raise ValueError("timeouts supports only startup and benchmark")
    host = config.execution.get("host", "127.0.0.1")
    path = config.execution.get("health_path", "/health")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("execution.host must be a non-empty string")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("execution.health_path must be a non-empty string")

    runs = configured_runs(config)
    configured_repeats(config)
    configured_min_repeats(config)
    configured_failure_percentage(config)
    configured_warmup_repeats(config)
    adaptive_repeat_policy(config)
    validate_drift_threshold(config.analysis.get("drift_threshold", 0.05))
    finalist_policy(config)
    maximize_metric(config)
    sampler, trial_count = validate_search(config)
    port = server_port(config)
    has_baseline = baseline_enabled(config)
    llm_settings(config)
    max_attempts(config)
    duration(config.timeouts, "startup", 900)
    positive(config.execution, "shutdown_grace", 15)
    positive(config.execution, "drain_grace", 15)

    slots = worker_slots(config)
    if selected_trials is None:
        _validate_worker_search_space(config, slots)
        trials = iter_grid(config)
        if sampler != "grid":
            trials = islice(trials, trial_count)
    else:
        trials = iter(selected_trials)
    if has_baseline:
        _validate_process(config, TrialParameters("baseline", {}, {}), slots)
    for trial in trials:
        _validate_process(config, trial, slots)

    endpoint_port = slots[0].port if slots else port
    endpoint = http_endpoint(host, endpoint_port)
    builder = build_guidellm_plan if configured_engine(config) == "guidellm" else build_vllm_plan
    for run in runs:
        timeout_for_run(run, config.timeouts.get("benchmark"))
        builder(config, run, endpoint, Path("."))


def _validate_worker_search_space(config: VTuneConfig, slots: tuple[WorkerSlot, ...]) -> None:
    if not slots:
        return
    definitions = normalized_arguments(config.tune, "tunable arguments")
    if "tensor-parallel-size" not in definitions:
        return
    name, definition = next(
        (name, definition)
        for name, definition in config.tune.items()
        if canonical_argument_name(name) == "tensor-parallel-size"
    )
    values = definition_values(definition, "tune.tensor-parallel-size")
    for value in values:
        _validate_process(config, TrialParameters("preflight", {name: value}, {}), slots)


def _validate_process(config: VTuneConfig, trial: TrialParameters, slots: tuple[WorkerSlot, ...]) -> None:
    slot = next((candidate for candidate in slots if candidate.supports(trial.server_args, config.server)), None)
    if slots and slot is None:
        raise ValueError("a trial tensor-parallel-size exceeds every parallel worker")
    runtime_args = {"port": slot.port} if slot else None
    runtime_env = {"CUDA_VISIBLE_DEVICES": ",".join(map(str, slot.devices))} if slot else None
    build_process_spec(config, trial.server_args, trial.server_env, runtime_args, runtime_env)
