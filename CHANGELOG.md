# Release notes

## Unreleased

## v0.1.0a20 — vLLM 0.30 sampling and trustworthy benchmark feedback

_October 6, 2026_

- Updated the runtime extra to vLLM 0.30.x; GuideLLM remains compatible with 0.7.x.
- Defaulted generation benchmarks to temperature zero and added startup warnings for explicit nonzero sampling.
- Validated temperature bounds, effective extra-body overrides, and multiple-completion sampling before execution.
- Normalized prefixed, inline, and dotted benchmark arguments while preserving JSON field names and detecting duplicate aliases.
- Preserved request-completion failure codes for offline reclassification while adding benchmark log diagnostics.
- Retained confidence warnings for insufficient repeats and drifting baselines, and rejected non-finite drift thresholds.
- Matched progress tracking to CLI arguments and vLLM's disabled-by-default readiness check; omitted disabled extra-body flags.
- Bumped package and runtime versions to `0.1.0a20`. The release attaches the universal wheel, source distribution, and SBOM;
  install with `pip install "vllm-optimizer==0.1.0a20"` or `pip install "vllm-optimizer[runtime]==0.1.0a20"` on Linux/WSL.

## v0.1.0a19 — Audited runtime and reporting correctness

_September 22, 2026_

- Revalidated request completion during offline reclassification for GuideLLM and vLLM, including normalized totals and accounted requests.
- Normalized configuration layers before merging, preserved inherited external YAML values when overrides are omitted, bracketed IPv6 literals,
  and rejected embedded redaction placeholders during retries.
- Awaited parallel scheduler cleanup before finalization and rejected non-finite search bounds before range expansion.
- Preserved legacy median aggregation order while retaining workload-identity validation.
- Made winner selection and baseline comparisons consistent across terminal, JSON, and HTML output, and included baseline data in CSV exports.
- Added a real GPU smoke workflow that serves OPT-125M, runs a request through vLLM Bench Serve, verifies reports, and checks cleanup.
- Made cleanup cancellation-resistant so owned processes reach forced termination, bounded retry preflight to selected trials, rejected inline
  redaction placeholders, and aligned resolved YAML alias/null handling with launched commands.

## v0.1.0a18 — Reliable results and reproducible runs

_September 19, 2026_

- Made workload matching dataset- and configuration-aware, preserved failed-repeat evidence, rejected non-finite scores, and retained
  baseline identity during reclassification.
- Snapshotted external vLLM YAML before execution and made retries use accepted finalist-validation manifests and repeat budgets.
- Fixed CLI alias precedence and preserved every value in list arguments.
- Unified launch and readiness endpoints, verified listener ownership by process and address, and validated every GPU requirement against
  configured workers for Random and TPE searches.
- Retries containing redacted external YAML secrets are rejected with an error naming the unavailable setting instead of launching with a
  placeholder value.

## v0.1.0a17 — Documentation and report usability

_September 18, 2026_

- Corrected documentation for scoring order, repeat aggregation, warmups, CLI workflows, local parallel validation, and supported Python
  versions.
- Fixed stale guide links, simplified first-run setup, and distinguished published hardware evidence from pending validation and roadmap
  proposals.
- Simplified the HTML report with a coverage-checked throughput/duration summary, visible confidence, compact settings, and expandable
  supporting evidence.
- Preserved every trial and its average benchmark duration, with complete recorded trial data available in details. Refreshed example
  reports and screenshots.

## v0.1.0a16 — Adaptive benchmark repeats and evidence-safe reporting

_September 15, 2026_

- Added adaptive benchmark repeat policies that spend additional repeats when measured variance or evidence quality requires them.
- Added configuration and worker support for adaptive repeats, including preflight validation and clearer repeat-budget handling.
- Rank repeated experiments by arithmetic mean while preserving repeat-level evidence for reports and comparisons.
- Hardened comparisons against incomplete or mismatched workload and repeat coverage, reporting unavailable aggregates instead of misleading
  results.
- Added evidence-aware report comparison helpers, leaderboard support, and refreshed RTX 3080 report examples and provenance.
- Added retry-safe PyPI publishing for releases that partially upload files.
- Expanded benchmark-repeat, configuration, reporting, and results guidance.
- Kept large TPE preflight validation lazy and bounded to the requested trials.
- Snapshotted native vLLM YAML settings into manifests and resolved report exports.
- Made workload headings readable while retaining full redacted configuration JSON in expandable report details.
- Moved the real report screenshot and example links near the top of the README.

## v0.1.0a15 — Fresh finalist validation and conservative decisions

_September 15, 2026_

- Added opt-in fixed-budget finalist validation after search, with configurable `top_k` and measured repeat counts.
- Re-run the baseline and selected candidates with fresh servers and separate `finalist-validation` artifacts; search-only scores remain
  distinct.
- Require complete, eligible, workload-matched evidence before declaring a winner, and report **No clear winner** when uncertainty, drift,
  or failures prevent a defensible conclusion.
- Persist finalist selection, validation status, budgets, search ranking, and selection decisions for reports, offline regeneration, and
  reclassification.
- Mark provisional recommendations clearly and make LLM summaries avoid causal parameter claims, invented ablations, and unsupported winner
  claims.
- Expanded benchmark-repeat, reporting, and search/scoring documentation.

## v0.1.0a14 — Decision-focused reports and H100 validation examples

_September 14, 2026_

- Added native vLLM server configuration support, including YAML loading and validation coverage.
- Made reports decision-focused with clearer comparisons, recommendations, confidence intervals, accepted scores, and independent winner
  validation.
- Added configurable H100 scenarios for large-model, multi-GPU, and parallel trial experiments.
- Added H100 preparation and validation workflows plus real GPU benchmark examples and published RTX 3080 evidence.
- Fixed configuration preservation, offline reporting, cleanup, search, and runtime correctness issues.
- Reorganized experiment and guide documentation and recorded LMCache runtime verification.

## v0.1.0a13 — Software trust gates; hardware validation pending

_September 3, 2026_

- Make the configured maximize metric the primary objective after the request failure eligibility gate.
- Default to one warmup and three required measured repeats, use Student's t intervals, and label insufficient evidence explicitly.
- Recursively redact conventional credentials from display and artifacts.
- Atomically finalize coordinator failures and preserve completed trial data.
- Add repository-owned lint, type, coverage, package, audit, SBOM, and release gates for Python 3.11 and 3.12.
- Hardware and real-backend validation remain pending and are not claimed.

## v0.1.0a12 — Live benchmark observability and failure policy

_September 2, 2026_

- Stream subprocess output into benchmark logs while commands are running and show live request counters or duration timers with clearer
  trial headings.
- Add configurable request-failure tolerance, an accept-any policy, and separate failed-request artifacts for GuideLLM and vLLM Bench Serve.
- Persist successful, failed, errored, and incomplete request counts plus the failure percentage for every benchmark repeat in JSON, CSV,
  and HTML.
- Add offline reclassification of immutable run data under a new request-error policy without relaunching vLLM or GuideLLM.
- Fix repeated benchmark drain paths, fast-benchmark final counters, and repeat score messaging; verify canonical normalization for both
  backends.

## v0.1.0a11 — vLLM Optimizer rebrand

_September 2, 2026_

- Renamed the project and distribution to **vLLM Optimizer** and `vllm-optimizer`.
- Added the `vllm_optimizer` import namespace and `vllm-opt` CLI.
- Retained deprecated `vtune` import and CLI compatibility aliases for one release cycle.

## v0.1.0a10 — Benchmark trust and release safeguards

_September 2, 2026_

- Reject incomplete GuideLLM request-count and vLLM Bench Serve results before they can enter scoring, and require clean normalized request
  totals.
- Increased the default request-count timeout to one hour and added a vLLM drain gate with persisted evidence after warmups and measured
  repeats.
- Added warmups, minimum-repeat enforcement, uncertainty summaries, drift detection, and sequential finalist validation.
- Added public behavioral tests, dependency review, SBOM generation, immutable provenance action pinning, and built-wheel tests in the
  publish workflow.

## v0.1.0a9 — Comparable benchmark evidence

_September 1, 2026_

- Renamed the public product to **vLLM Config Tuner** while preserving the `vtune` package, import namespace, and CLI command.
- Added ANSI terminal colors with `NO_COLOR` support and always pass the validated server port to vLLM.
- Validate complete YAML-derived commands before creating a run or launching a process.
- Normalize GuideLLM and vLLM throughput, request totals, and latency statistics into one schema without inventing missing percentiles.
- Persist benchmark repeat and wall-clock elapsed time and show per-benchmark average, median, and P99 evidence with metric definitions in
  HTML.
- Documented the GuideLLM request-count timeout and completion-integrity risk; long-generation workloads remain an alpha limitation until
  strict request completion and server-drain checks are implemented.

## v0.1.0a8 — Python 3.11 compatibility

- Fixed `TrialReport.execution` to use a dataclass default factory, restoring Python 3.11 package imports. The public Python 3.11 and 3.12
  package checks now pass.

## v0.1.0a7 — Correctness and trust

- Persisted typed per-trial execution assignments separately from artifacts.
- Stopped deriving median and P99 values when a backend supplied only an average.
- Offline regeneration recomputes derived metric summaries without changing its source run.
- Hardened optional LLM endpoints and made integrity warnings precise.

## v0.1.0a6 — Trustworthy progress and GuideLLM completion

_August 31, 2026_

### Progress and diagnostics

- Added timestamped live terminal stages, TTY loading animation, trial progress, per-repeat scores, and final session duration.
- Removed repeated artifact folders for `benchmark.repeats: 1` and added a clear warning when every benchmark request fails or is
  ineligible.

### Reports and configuration

- Made `schema_version` optional while retaining version-1 compatibility.
- Added ordered benchmark tables, labelled chart axes, standard metric tables, scoring/importance explanations, run duration, and persisted
  metric summaries.
- Added optional secret-safe OpenAI-compatible report summaries configured with `analysis.llm_summary` and an environment-variable API key.
- Expanded CLI help and documented GuideLLM throughput completion behavior.

### GuideLLM reliability

- Removed vTune's interactive-console override so GuideLLM retains its normal request-draining lifecycle.
- Mark a benchmark as failed with a targeted diagnostic when GuideLLM exits without any completed requests.

## v0.1.0a5 — Native benchmarks and explicit parallel trials

_August 31, 2026_

### vLLM Bench Serve

- Added `benchmark.engine: vllm` as an alternative to the default GuideLLM backend, with forward-compatible `vllm bench serve` argument
  pass-through.
- Made `--backend vllm` automatic instead of requiring it in every run.
- Added canonical throughput aliases, request-failure accounting, raw JSON and log preservation, exact command capture, retries, repeats,
  and timeouts.
- Added random, ShareGPT, Hugging Face, custom, and prefix-repetition examples.

### Parallel trials

- Added opt-in local parallel execution with explicit, exclusive GPU workers and deterministic per-worker ports.
- Kept search suggestions, Optuna updates, ranking, and persistence under one coordinator while trial process groups execute concurrently.
- Recorded resolved worker, device, port, and execution mode in artifacts and labeled parallel reports with a hardware-contention warning.
- Added failure isolation and cancellation cleanup across active workers.

## v0.1.0a4 — Easier setup and actionable diagnostics

_August 30, 2026_

### Installation

- Added the optional `runtime` installation extra for vLLM and GuideLLM.
- Added actionable errors when either runtime executable is unavailable.
- Clarified the difference between experiment and inspection installations.

### Runtime diagnostics

- Reworked progress so each stage resolves on one line and baseline failures show their complete diagnostic immediately.
- Preserved root-cause exception lines in failure excerpts instead of showing only the end of long tracebacks.

### Documentation

- Added a complete commented YAML reference covering every vTune section, tuning syntax, benchmark profile, request route, and dataset
  family.
- Added a dedicated installation guide for core-only and experiment-runtime environments, including native Windows and WSL differences.

Earlier entries are preserved in the [changelog archive](docs/project/releases/CHANGELOG_ARCHIVE.md).
