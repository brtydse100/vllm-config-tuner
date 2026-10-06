from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vllm_optimizer.benchmarks.guidellm import parse_result
from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.domain.benchmark import BenchmarkResult, WorkloadResult
from vllm_optimizer.domain.results import WorkerResult
from vllm_optimizer.managers.results import ResultsManager
from vllm_optimizer.reproduction.redaction import REDACTED
from vllm_optimizer.workers.base import TrialContext
from vllm_optimizer.workers.benchmark import GuideLLMBenchmarkWorker
from vllm_optimizer.workers.benchmark_state import (
    artifact_directory,
    artifact_prefix,
    benchmark_environment,
    ownership_key,
    remember_result,
    worker_name,
)
from vllm_optimizer.workers.guidellm_completion import completion_failure
from vllm_optimizer.workers.progress_policy import progress_limit, request_count, request_path, setup_requests


class _Process:
    async def wait(self) -> int:
        return 0

    async def stop(self, grace: float) -> None:
        del grace


class _Runner:
    async def start(self, spec: object, log_path: Path) -> _Process:
        del spec
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
        return _Process()


def _write_result(path: Path, successful: int, incomplete: int = 0) -> None:
    path.write_text(
        json.dumps(
            {
                "metadata": {"guidellm_version": "synthetic"},
                "benchmarks": [
                    {
                        "config": {},
                        "metrics": {
                            "request_totals": {
                                "successful": successful,
                                "errored": 0,
                                "incomplete": incomplete,
                                "total": successful + incomplete,
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_progress_policy_parses_metrics_and_limits() -> None:
    metrics = 'http_requests_total{handler="/v1/completions",method="POST"} 3\nvllm:request_success_total 9'
    assert request_count(metrics, "/v1/completions") == 3
    assert request_count("vllm:request_success_total 4", "/missing") == 4
    assert request_count("invalid", "/missing") is None
    assert progress_limit("vllm", {"args": {"num-prompts": 7}}) == ("requests", 7.0)
    run = {"profile": {"streams": [1, 2]}, "constraints": [{"kind": "max_requests", "count": 5}]}
    assert progress_limit("guidellm", run) == ("requests", 10.0)
    assert progress_limit("guidellm", {"constraints": [{"kind": "max_duration", "seconds": ["2s"]}]}) == ("time", 2.0)
    assert request_path("guidellm", {"request_format": "/chat"}) == "/chat"
    assert setup_requests("vllm", {"args": {"num-warmups": 2}}) == 2


def test_benchmark_state_helpers(tmp_path: Path) -> None:
    context = TrialContext("trial", values={"attempt_index": 2})
    assert artifact_directory(tmp_path, context, 3, None).parts[-2:] == ("repeats", "003")
    assert artifact_prefix("run", None, 2) == "benchmark_run_warmup_2"
    assert worker_name("vllm", "run", 2, None).endswith(":repeat-2")
    assert "warmup-1" in ownership_key("guidellm", "run", None, 1)
    remember_result(context, "ignored", warmup=1)
    remember_result(context, "kept")
    assert context.values["benchmark_results"] == ("kept",)
    config = VTuneConfig(1, ExperimentConfig("test"), {"model": "/model"}, env={"VISIBLE": 1})
    assert benchmark_environment(config, guidellm=True)["GUIDELLM__LOGGING__CONSOLE_LOG_LEVEL"] == "INFO"


def test_guidellm_worker_rejects_incomplete_result(tmp_path: Path) -> None:
    run = {
        "name": "requests",
        "profile": {"kind": "synchronous"},
        "constraints": [{"kind": "max_requests", "count": 2}],
        "data": [{"kind": "synthetic_text", "prompt_tokens": 4}],
    }
    result_path = tmp_path / "attempts" / "001" / "requests" / "results.json"
    result_path.parent.mkdir(parents=True)
    _write_result(result_path, 1, 1)
    config = VTuneConfig(1, ExperimentConfig("test"), {"model": "/model"})
    worker = GuideLLMBenchmarkWorker(config, run, _Runner(), tmp_path)
    context = TrialContext("trial", values={"server_endpoint": "http://127.0.0.1:1"})
    outcome = asyncio.run(worker.execute(context))
    assert outcome.failure and outcome.failure.code == "benchmark_requests_incomplete"
    parsed = parse_result(result_path, "requests")
    assert completion_failure(config, run, parsed, "requests", tmp_path / "log") is not None
    assert completion_failure(config, {}, parsed, "requests", tmp_path / "log") is None
    _write_result(result_path, 0, 1)
    incomplete = parse_result(result_path, "requests")
    assert completion_failure(config, {}, incomplete, "requests", tmp_path / "log").code == (
        "benchmark_no_completed_requests"
    )


def test_guidellm_worker_accepts_complete_result_and_cleans_up(tmp_path: Path) -> None:
    run = {
        "name": "requests",
        "profile": {"kind": "synchronous"},
        "constraints": [{"kind": "max_requests", "count": 2}],
        "data": [{"kind": "synthetic_text", "prompt_tokens": 4}],
    }
    result_path = tmp_path / "attempts" / "001" / "repeats" / "001" / "requests" / "results.json"
    result_path.parent.mkdir(parents=True)
    _write_result(result_path, 2)
    config = VTuneConfig(1, ExperimentConfig("test"), {"model": "/model"})
    worker = GuideLLMBenchmarkWorker(config, run, _Runner(), tmp_path, repeat_index=1)
    context = TrialContext("trial", values={"server_endpoint": "http://127.0.0.1:1"})
    assert worker.name.endswith(":repeat-1")
    assert asyncio.run(worker.execute(context)).failure is None
    assert len(context.values["benchmark_results"]) == 1
    asyncio.run(worker.cleanup(context))


def test_guidellm_worker_validates_inputs(tmp_path: Path) -> None:
    config = VTuneConfig(1, ExperimentConfig("test"), {"model": "/model"})
    run = {"name": "requests"}
    worker = GuideLLMBenchmarkWorker(config, run, _Runner(), tmp_path)
    outcome = asyncio.run(worker.execute(TrialContext("trial")))
    assert outcome.failure and outcome.failure.code == "benchmark_endpoint_missing"
    try:
        GuideLLMBenchmarkWorker(config, run, _Runner(), tmp_path, timeout=0)
    except ValueError as error:
        assert "timeout" in str(error)
    else:
        raise AssertionError("invalid timeout was accepted")


def test_normalized_trial_result_recursively_redacts_configuration(tmp_path: Path) -> None:
    result = BenchmarkResult(
        "run",
        "synthetic",
        "1",
        (
            WorkloadResult(
                0,
                {"headers": {"Authorization": "Bearer sentinel"}, "nested": [{"API_KEY": "sentinel"}]},
                {"request_totals": {"successful": 1, "errored": 0, "incomplete": 0}},
            ),
        ),
        tmp_path / "raw.json",
    )
    context = TrialContext("trial", values={"benchmark_results": (result,)})
    ResultsManager(tmp_path / "result.json").save(context, WorkerResult.completed(context))
    persisted = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    configuration = persisted["benchmarks"][0]["workloads"][0]["configuration"]
    assert configuration["headers"]["Authorization"] == REDACTED
    assert configuration["nested"][0]["API_KEY"] == REDACTED
