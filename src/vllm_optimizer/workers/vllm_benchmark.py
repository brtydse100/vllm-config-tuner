"""Production vLLM Bench Serve worker."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from time import monotonic

from vllm_optimizer.benchmarks.configuration import configured_failure_percentage
from vllm_optimizer.benchmarks.failures import save_failed_requests
from vllm_optimizer.benchmarks.vllm import build_plan, parse_result
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.domain.results import WorkerResult
from vllm_optimizer.reproduction.models import CommandRecord
from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.benchmark_state import (
    artifact_directory,
    artifact_prefix,
    failed,
    ownership_key,
    remember_result,
    worker_name,
)
from vllm_optimizer.workers.completion import observed_requests, reported_request_total, request_count_failure
from vllm_optimizer.workers.failure_details import classified_failure
from vllm_optimizer.workers.process import ManagedProcess, ProcessRunner, ProcessSpec
from vllm_optimizer.workers.progress import BenchmarkProgress, ProgressCallback


class VLLMBenchmarkWorker:
    def __init__(
        self,
        config: VTuneConfig,
        run: Mapping[str, object],
        runner: ProcessRunner,
        artifacts: Path,
        timeout: float = 180,
        shutdown_grace: float = 5,
        repeat_index: int | None = None,
        warmup_index: int | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        if timeout <= 0 or shutdown_grace < 0:
            raise ValueError("benchmark timeout must be positive and grace non-negative")
        if repeat_index is not None and warmup_index is not None:
            raise ValueError("benchmark repeat and warmup cannot both be set")
        self._config, self._run, self._runner = config, run, runner
        self._artifacts, self._timeout = Path(artifacts), timeout
        self._shutdown_grace = shutdown_grace
        self._run_name = str(run.get("name", "invalid"))
        self._repeat_index = repeat_index
        self._warmup_index = warmup_index
        self._progress = progress

    @property
    def name(self) -> str:
        return worker_name("vllm", self._run_name, self._repeat_index, self._warmup_index)

    @property
    def _ownership_key(self) -> str:
        return ownership_key("vllm", self._run_name, self._repeat_index, self._warmup_index)

    async def execute(self, context: TrialContext) -> WorkerResult[None]:
        endpoint = context.values.get("server_endpoint")
        if not isinstance(endpoint, str):
            return failed("benchmark_endpoint_missing", "Missing server endpoint")
        try:
            artifacts = artifact_directory(self._artifacts, context, self._repeat_index, self._warmup_index)
            plan = build_plan(self._config, self._run, endpoint, artifacts)
            plan.directory.mkdir(parents=True, exist_ok=True)
            attempt = context.values.get("attempt_index", 1)
            if not isinstance(attempt, int) or isinstance(attempt, bool):
                raise ValueError("attempt index must be an integer")
            context.commands.append(
                CommandRecord(
                    "vllm_bench_serve", plan.argv, attempt, self._environment(), plan.run_name, self._repeat_index
                )
            )
            started = monotonic()
            progress = BenchmarkProgress("vllm", self._run, self.name, self._progress)
            await progress.prepare(endpoint)
            process = await self._runner.start(ProcessSpec(plan.argv, env=self._environment()), plan.log_path)
        except FileNotFoundError:
            return failed(
                "vllm_not_found",
                "The 'vllm' command was not found. On Linux or WSL, "
                "install runtime tools with: pip install 'vllm-optimizer[runtime]'",
            )
        except Exception as error:
            return failed("benchmark_launch_failed", f"vLLM benchmark '{self._run_name}' could not start: {error}")
        context.values[self._ownership_key] = process
        progress.start(process)
        prefix = artifact_prefix(plan.run_name, self._repeat_index, self._warmup_index)
        context.artifacts[f"{prefix}_log"] = str(plan.log_path)
        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=self._timeout)
        except TimeoutError:
            await process.stop(self._shutdown_grace)
            return WorkerResult.failed(
                classified_failure(
                    plan.log_path,
                    "benchmark_timeout",
                    f"vLLM benchmark '{plan.run_name}' timed out after {self._timeout:g}s "
                    f"and was stopped; full log: {plan.log_path}",
                    True,
                )
            )
        finally:
            await progress.stop()
        if returncode:
            return WorkerResult.failed(
                classified_failure(
                    plan.log_path,
                    "benchmark_failed",
                    f"vLLM benchmark '{plan.run_name}' exited with code {returncode}; full log: {plan.log_path}",
                )
            )
        try:
            result = replace(
                parse_result(plan.json_path, plan.run_name),
                repeat_index=self._repeat_index,
                elapsed_seconds=monotonic() - started,
            )
        except ValueError as error:
            return WorkerResult.failed(
                classified_failure(
                    plan.log_path,
                    "benchmark_result_invalid",
                    f"vLLM benchmark '{plan.run_name}' returned an invalid result: {error}; full log: {plan.log_path}",
                )
            )
        progress.complete(process, observed_requests(result))
        failed_path = plan.directory / "failed_requests.json"
        if save_failed_requests(plan.json_path, "vllm", failed_path):
            context.artifacts[f"{prefix}_failed_requests"] = str(failed_path)
        context.artifacts[f"{prefix}_json"] = str(plan.json_path)
        failure = request_count_failure(
            result, reported_request_total(result), "vLLM Bench Serve", configured_failure_percentage(self._config)
        )
        if failure is not None:
            if self._warmup_index is None:
                remember_result(context, result, observed=True)
            return WorkerResult.failed(
                classified_failure(
                    plan.log_path,
                    failure.code,
                    f"vLLM benchmark '{plan.run_name}': {failure.message}; full log: {plan.log_path}",
                    failure.retryable,
                )
            )
        if self._warmup_index is None:
            remember_result(context, result)
        return WorkerResult.completed()

    async def cleanup(self, context: TrialContext) -> None:
        process = context.values.pop(self._ownership_key, None)
        if isinstance(process, ManagedProcess):
            await process.stop(self._shutdown_grace)

    def _environment(self) -> dict[str, str]:
        return {**{key: str(value) for key, value in self._config.env.items()}, "PYTHONUNBUFFERED": "1"}
