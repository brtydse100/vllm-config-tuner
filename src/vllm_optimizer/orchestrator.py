from collections.abc import Mapping
from pathlib import Path

from vllm_optimizer.benchmarks.configuration import configured_runs
from vllm_optimizer.benchmarks.policy import effective_policy
from vllm_optimizer.benchmarks.temperature import temperature_warnings
from vllm_optimizer.config.adaptive_repeats import adaptive_repeat_policy
from vllm_optimizer.config.finalist_validation import finalist_policy
from vllm_optimizer.config.models import VTuneConfig
from vllm_optimizer.config.preflight import validate_config
from vllm_optimizer.config.runtime import baseline_enabled, logging_level, maximize_metric
from vllm_optimizer.domain.results import WorkerStatus
from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.execution import TrialExecutor, WorkerSlot, execution_mode, worker_slots
from vllm_optimizer.execution.finalist_validation import validate_drifted_finalists
from vllm_optimizer.managers.run_finalization import RunFinalizer, RunOutcome
from vllm_optimizer.managers.run_results import RunResultsManager
from vllm_optimizer.managers.run_session import RunAccumulator
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.orchestrator_messages import experiment_details
from vllm_optimizer.orchestrator_search import run_search
from vllm_optimizer.orchestrator_setup import run_identity, scoring
from vllm_optimizer.reproduction.manifest import ManifestWriter
from vllm_optimizer.reproduction.metadata import collect_metadata
from vllm_optimizer.search import TrialParameters, create_search, search_warning
from vllm_optimizer.search.fixed_session import FixedSearchSession
from vllm_optimizer.terminal import TerminalLogger


class Orchestrator:
    def __init__(
        self,
        config: VTuneConfig,
        trials: tuple[TrialParameters, ...] | None = None,
        source_run_id: str | None = None,
        sources: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        validate_config(config, trials)
        self._config = config
        self._metric = maximize_metric(config)
        run_names = tuple(str(run["name"]) for run in configured_runs(config))
        self._scoring = scoring(config, self._metric, run_names)
        self._manifest = ManifestWriter({})
        self._trial_executor: TrialExecutor | None = None
        self._retry_trials = trials
        self._source_run_id = source_run_id
        self._sources = dict(sources or {})
        self._terminal = TerminalLogger(logging_level(config))
        self._finalizer = RunFinalizer(config, self._metric, self._terminal)

    def validate(self) -> None:
        validate_config(self._config, self._retry_trials)

    async def run(self) -> RunOutcome:
        try:
            return await self._run_unprotected()
        except BaseException as error:
            self._finalizer.fail(error, self._source_run_id, self._sources)
            raise

    async def _run_unprotected(self) -> RunOutcome:
        identity = run_identity(self._config)
        run_id, started_at, directory = identity.run_id, identity.started_at, identity.directory
        directory.mkdir(parents=True, exist_ok=True)
        mode = execution_mode(self._config)
        results = RunResultsManager(directory / "result.json", mode, effective_policy(self._config).to_dict())
        names = tuple(str(run["name"]) for run in configured_runs(self._config))
        session = RunAccumulator(names, self._scoring)
        policy = finalist_policy(self._config)
        if policy:
            session.validation = {"status": "pending", "selected_trials": [], "repeats": policy.repeats}
        self._finalizer.start(results, session, run_id, started_at)
        session.persist(results, run_id, self._metric, "running", started_at, None, self._source_run_id, self._sources)
        self._terminal.info(f"Run: {run_id}\nDirectory: {directory.resolve()}")
        for temperature_warning in temperature_warnings(self._config):
            self._terminal.warning(f"WARNING: {temperature_warning}")
        if self._retry_trials is None and (warning := search_warning(self._config)):
            self._terminal.warning(f"WARNING: {warning}")
        self._manifest = ManifestWriter(collect_metadata())
        self._trial_executor = TrialExecutor(self._config, self._scoring, self._terminal, self._manifest, self._sources)
        slots = worker_slots(self._config)
        search = (
            FixedSearchSession(self._retry_trials)
            if self._retry_trials is not None
            else create_search(self._config, directory)
        )
        self._terminal.experiment(
            experiment_details(
                self._config, search.total, mode, slots, self._retry_trials is not None, self._metric, directory
            )
        )
        interrupted = False
        parameters_by_id: dict[str, TrialParameters] = {}
        slots_by_id: dict[str, WorkerSlot | None] = {}
        if self._retry_trials is None and baseline_enabled(self._config):
            self._terminal.baseline()
            parameters = TrialParameters("baseline", {}, {})
            baseline_slot = next((slot for slot in slots if slot.supports({}, self._config.server)), None)
            parameters_by_id["baseline"], slots_by_id["baseline"] = parameters, baseline_slot
            report, score, by_benchmark = await self._run_trial(directory, parameters, baseline_slot)
            session.record(parameters, report, score, by_benchmark, baseline=True)
            session.persist(
                results, run_id, self._metric, "running", started_at, None, self._source_run_id, self._sources
            )
            if score:
                self._terminal.info(f"OK Baseline completed — score={score.value:.4f}")
            else:
                detail = f"{report.failure.code}: {report.failure.message}" if report.failure else report.status.value
                self._terminal.warning(f"Baseline {report.status.value}: {detail}")
            interrupted = report.status is WorkerStatus.INTERRUPTED

        async def execute(parameters: TrialParameters, slot: WorkerSlot | None):
            baseline_mean = (
                session.baseline.value if adaptive_repeat_policy(self._config) and session.baseline else None
            )
            return await self._run_trial(directory, parameters, slot, baseline_mean_score=baseline_mean)

        searched = await run_search(
            search,
            slots,
            dict(self._config.server),
            execute,
            self._terminal,
            session,
            results,
            run_id,
            self._metric,
            started_at,
            interrupted,
            self._source_run_id,
            self._sources,
        )
        parameters_by_id.update(searched.parameters)
        slots_by_id.update(searched.slots)
        interrupted = searched.interrupted
        if not interrupted:
            await validate_drifted_finalists(
                directory,
                session,
                results,
                run_id,
                started_at,
                self._metric,
                float(self._config.analysis.get("drift_threshold", 0.05)),
                parameters_by_id,
                slots_by_id,
                self._run_trial,
                self._terminal.warning,
                self._source_run_id,
                self._sources,
                finalist_policy(self._config),
            )
        finalized = await self._finalizer.complete(self._source_run_id, self._sources, names, mode)
        return RunOutcome(run_id, directory, finalized.reports, finalized.ranking, finalized.summary, finalized.status)

    async def _run_trial(
        self,
        directory: Path,
        parameters: TrialParameters,
        slot: WorkerSlot | None = None,
        artifact_subdirectory: str | None = None,
        baseline_mean_score: float | None = None,
    ) -> tuple[TrialReport, TrialScore | None, dict[str, float]]:
        if self._trial_executor is None:
            raise RuntimeError("trial executor is not initialized")
        if baseline_mean_score is None:
            return await self._trial_executor.execute(directory, parameters, slot, artifact_subdirectory)
        return await self._trial_executor.execute(
            directory, parameters, slot, artifact_subdirectory, baseline_mean_score
        )
