# Reports

Every completed run writes a self-contained `report.html` alongside machine-
readable `result.json` and `results.csv` exports. `results.json` is reserved
for raw benchmark output where a backend writes one.

The report is designed to answer, at a glance:

1. Did tuning help?
2. Which configuration should I use?
3. How much should I trust it?

The default view shows a one-line result summary, a visible confidence verdict,
baseline and best-observed measurements, changed settings, and every trial.
The summary reports the percentage change in **mean output throughput** and
**average benchmark duration** against the baseline. For example: "Results show
20% higher output throughput and 10% shorter average benchmark duration versus
baseline." Regressions are labeled lower throughput or longer duration; ties
are unchanged. Baseline retention does not claim an improvement.

Duration reduction is `(baseline - selected) / baseline * 100`; throughput
increase is `(selected - baseline) / baseline * 100`. These are arithmetic
means of recorded measurements, separate from the configured optimization
score (including historical median-based scores). Percentages require matching
workloads, repeat counts, complete measurements, and a nonzero baseline.
Unavailable comparisons are identified explicitly.

The settings section shows changed arguments and environment values with a
**Copy launch command** button. Expand **Full configuration and launch command**
for resolved explicit vLLM YAML, selected environment variables, and the POSIX
command. Unspecified vLLM internal defaults are not captured. Replace redacted
values before launching. When `server.config` points to an external vLLM YAML,
the command uses the immutable copy stored in the accepted trial directory,
not the original file.

**Performance breakdown**, **Confidence and validation**, and **Diagnostics and
methodology** start collapsed. Open them for detailed comparisons, repeat
statistics, charts, failures, and metric definitions. The confidence verdict
remains visible in the overview even when its supporting details are collapsed.

Comparisons preserve each workload's recorded configuration. They show output
and request throughput, TTFT, TPOT, end-to-end latency, and request failures,
with units and percentage changes. An overall summary and per-benchmark rows
also compare mean benchmark execution duration regardless of the optimization
objective. Values are arithmetic means across available
repeats; P50/P95/P99 columns are means of supplied backend percentiles, **not pooled
request percentiles**. Missing measurements and zero-denominator percentage
changes are unavailable. Different workload configurations and datasets are
not paired or combined to satisfy a repeat budget.

The baseline comparison is inside Performance breakdown. Overall percentage changes
require matching workload configurations and repeat counts on both sides.
Missing metric samples or benchmark durations make the affected change
unavailable; recorded absolute values and per-workload details remain visible.
Mean-to-mean comparisons are retained when the evidence has matching coverage.

Confidence shows individual repeats, mean, sample standard deviation, range,
repeat count, and signed drift percentage per workload. The drift value compares
the means of the first and second repeat halves and shows whether it exceeds the
configured threshold. Too few repeats, mismatched workloads,
drift, or overlapping repeat ranges make a comparison inconclusive. Range
overlap is a descriptive heuristic, not a significance test. Independent
production validation remains necessary. Initial search measurements are kept
separate from accepted finalist validation.

The sortable **All trials** table keeps every trial, including duplicate configurations,
failures, and interruptions. It shows each trial's mean recorded benchmark
duration. Open **Full details** for the duration difference from baseline,
individual repeat durations, variability, request failures, and settings. Lower
duration is labeled better. **All recorded trial data (JSON)** includes every
stored benchmark/workload metric, execution metadata, artifacts, attempts, and
errors, with secret-name redaction and HTML escaping. Missing timings remain
unavailable rather than inferred. Average benchmark duration excludes server
startup and is not total trial wall time. Raw log and benchmark file contents
remain in the run artifacts.
For adaptive runs, expanded trial details show whether extra repeats continued
or stopped, the reason, and actual repeat counts for each workload. The same
structured evidence is stored under `trials[].execution.adaptive_repeats` in the
run JSON.

Detailed diagnostics and exploratory parameter associations are expandable.
Parameter importance describes associations across tested values, not causation.
The score-history chart uses recorded trial order, not elapsed time.
Scoring evidence includes each ranked trial's mean benchmark duration and its
percentage difference from the baseline; duration remains informational and does
not alter the configured optimization score.

## Metric calculations

- **Requests/s** is completed requests divided by benchmark measurement time.
- **Output tokens/s** is generated tokens divided by measurement time; total
  tokens/s includes prompt and output tokens.
- **TTFT** measures request start to first generated token.
- **TPOT** measures average time per output token after the first token.
- **ITL** measures delay between consecutive streamed tokens.
- **End-to-end latency** measures request start through complete response.
- **Median** is P50; **P99** means 99% of observations are at or below the value.
- **Elapsed** is measured by the `vllm-opt` CLI from benchmark subprocess launch through
  JSON parsing and excludes vLLM server startup.

Backends calculate request distributions and percentiles. vLLM Optimizer normalizes
names and units but does not derive missing percentiles. Eligible workloads are
averaged within an execution, repeated executions use the arithmetic mean score, and
named benchmark scores are averaged into the trial score.

Without `analysis.finalist_validation`, when a finalist's sequential repeat means drift beyond `analysis.drift_threshold`
(5% by default), the top two affected finalists are rerun sequentially before
the recommendation is finalized. Their validation artifacts are kept under
`validation-001`; a failed validation removes that candidate from the ranking.

Drift compares the first and second halves of at least four repeats within the
same trial and workload. Different tuned configurations are expected to perform
differently, and repeated timings need not be identical even with temperature
`0`. The drift column labels changes within the configured threshold separately
from detected drift. Conclusive comparisons use normal styling; inconclusive
evidence retains a warning. Retained baselines are also checked for too few
repeats and drift before the report uses normal styling. Drift thresholds must
be finite and non-negative, including when regenerating stored reports.
A threshold of `0` flags any change and is intended
for demonstrations such as the archived report showcase, not normal use.

With [fixed-budget finalist validation](benchmarks/benchmark-repeats.md#fresh-finalist-validation),
the baseline and selected candidates receive fresh measurements even without
detected drift. Artifacts live under `finalist-validation`. The overview and
terminal show **No clear winner** unless the highest validated score also has
separated repeat ranges and 95% Student's t intervals of workload means against
every selected rival. Missing, failed, drifting, or mismatched evidence blocks
that conclusion. These intervals are a descriptive uncertainty guard, not a
significance test for the aggregate scoring objective. An inconclusive report shows
the best observed candidate's settings without declaring it the winner.

The run JSON stores `finalist_validation` (selection, repeat budget, status,
original `search_ranking`, and `search_baseline`) and `selection_decision`
(`status`, nullable `winner_trial_id`, and `reason`). `best` remains the highest
observed tuned score; consumers must use `selection_decision` for the conclusion.
After validation starts, rankings and CSV scores exclude search-only candidates.
Offline regeneration recomputes the conclusion from accepted measurements;
reclassification preserves the validation budget and selected-candidate boundary.
Manual retries also use the accepted execution manifest. After finalist
validation, this preserves its fixed repeat budget instead of reverting to the
initial search budget.

If `analysis.llm_summary` is configured, the report also includes a short
OpenAI-compatible summary. Its API key is read only from the named environment
variable and is never persisted. It requires HTTPS except for loopback HTTP.
Name-based redaction reduces accidental disclosure but cannot guarantee that
arbitrary user-provided values contain no secrets. An unavailable endpoint
becomes a report warning and never invalidates the experiment.
The summary prompt explicitly prohibits causal parameter claims, invented
ablations, and treating ranked observations as proof of a winner.

Each trial directory also contains its resolved configuration, normalized
result, reproduction manifest, `vllm.log`, and `benchmark.log`. Normalized
results omit token timings, request start times, and generated text. Input and
output lengths plus a sparse error map are retained in one compact `requests`
object. Raw
backend JSON remains available unchanged. Persistent values are secret-redacted.

## Offline regeneration

Regenerate `report.html`, `results.csv`, and a validated copy of `result.json`
from stored artifacts alone:

```bash
vllm-opt report --run runs/NAME/RUN_ID
```

The report uses reproduction manifests from the source run while writing all
new output to a separate directory. Required structured data (the run and
trial results and manifests) is validated and stops regeneration when invalid.
Rankings, displayed measurements, charts, YAML, and command export refer to the
accepted execution. A missing validation manifest never falls back to the
superseded search manifest. For runs retaining a scoring policy, regeneration
rejects ranking scores that disagree with accepted measurements. Legacy runs
without that policy cannot receive this additional score consistency check.

New runs record `benchmark_policy.repeat_aggregation: mean` and rank by the
arithmetic mean across repeats. Older runs without this field retain median
scoring when regenerated or reclassified, preserving their historical rankings.
This does not change backend P50/P95/P99 request percentiles.

To apply a different request-failure policy without starting vLLM or GuideLLM:

```bash
vllm-opt reclassify --run runs/RUN --max-failure-percentage 5
vllm-opt reclassify --run runs/RUN --accept-any-request-failures
```

This reads the stored benchmark measurements, evaluates request failures only
after each stored repeat is complete, recalculates eligibility and rankings, and
writes a new `result.json`, `results.csv`, and `report.html` below the source
run's `reclassified` directory (or `--output`). The source run is not modified.
Measurements from a failed repeat remain part of this evidence and must satisfy
the selected failure policy before that trial can become eligible. A trial named
`baseline` remains the baseline if reclassification makes it eligible; it is
never moved into the tuned ranking.
Missing or changed optional logs and raw artifacts generate visible integrity
warnings. a5/a6 reports may have no execution assignment; a7 recomputes their
derived summaries from normalized trial data without changing the source run.
