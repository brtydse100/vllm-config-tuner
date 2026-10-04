"""Conservative descriptive evidence, with historical search results kept separate."""

from __future__ import annotations

from html import escape
from pathlib import Path

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.measurement import sequential_drift, sequentially_drifted, summarize
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.offline_loading import load_trial, read_object
from vllm_optimizer.reporting.tables import _table
from vllm_optimizer.reporting.workloads import formatted, samples, scenarios


def verdict(baseline: TrialReport | None, best: TrialReport | None, metric: str, context: ReportContext) -> str:
    if baseline is None or best is None:
        return "Inconclusive: baseline or candidate evidence is unavailable."
    if baseline.trial_id == best.trial_id:
        return "Baseline retained: no tuned configuration beat it under the scoring policy."
    before, after = scenarios(baseline), scenarios(best)
    if not before or before.keys() != after.keys():
        return "Inconclusive: workload coverage differs or is unavailable."
    regressions = 0
    for key in before:
        a, b = samples(before[key], (metric,)), samples(after[key], (metric,))
        if min(len(a), len(b)) < max(2, context.minimum_repeats):
            return "Inconclusive: too few repeats to assess variability."
        if any(sequentially_drifted(values, context.drift_threshold) for values in (a, b)):
            return "Inconclusive: repeat measurements show drift."
        if max(min(a), min(b)) <= min(max(a), max(b)):
            return "Inconclusive: repeat ranges overlap; the observed difference may be noise."
        regressions += max(b) < min(a)
    if regressions == len(before):
        return "Repeat ranges favor the baseline in every matched workload; independent validation is still limited."
    if regressions:
        return "Workload tradeoff: the highest aggregate score includes workload regressions."
    return "Repeat ranges favor the recommendation in every matched workload; independent validation is still limited."


def conclusion_class(conclusion: str) -> str:
    return "warning" if conclusion.startswith(("Inconclusive:", "No clear winner:")) else "note"


def confidence(
    directory: Path,
    baseline: TrialReport | None,
    best: TrialReport | None,
    metric: str,
    context: ReportContext,
    conclusion: str | None = None,
    finalists: tuple[TrialReport, ...] = (),
) -> str:
    rows = []
    historical = []
    seen = set()
    for report in (baseline, best, *finalists):
        if report is None or report.trial_id in seen:
            continue
        seen.add(report.trial_id)
        phase = (
            "Finalist validation (accepted)"
            if report.execution.get("artifact_subdirectory")
            else "Initial search (accepted)"
        )
        rows.extend(_rows(report, phase, metric, context))
        if report.execution.get("artifact_subdirectory"):
            try:
                raw = read_object(directory / "trials" / report.trial_id / "result.json", "initial search result")
                initial = load_trial(directory, raw, [])
                historical.extend(_rows(initial, "Initial search (superseded)", metric, context))
            except ValueError:
                historical.append("<tr><td colspan='8'>Initial search evidence unavailable.</td></tr>")
    heading = ("Trial / phase", "Workload", "Individual repeats", "n", "Mean", "Sample SD", "Range", "Drift")
    message = conclusion or verdict(baseline, best, metric, context)
    return (
        f"<section id='confidence'><h2>Confidence in the result</h2><p class='{conclusion_class(message)}'>"
        + escape(message)
        + "</p>"
        "<p>Descriptive repeat evidence for the optimization metric, per workload. Range overlap is a conservative "
        "inconclusive flag, not a statistical significance test. These measurements are not independent proof "
        "of production performance. Repeated timings need not be identical, even with temperature=0. "
        "Drift compares the first and second halves of repeats within the same trial and workload when at least "
        "four repeats exist; performance differences between tuned configurations are not drift.</p>"
        + (
            f"<p>Fixed validation budget: {escape(str(context.finalist_validation.get('repeats')))} fresh repeats per named run "
            "for each selected candidate. Search repeats do not count. A favorable decision requires separation "
            "of observed ranges and 95% Student's t intervals of workload means against every selected rival. "
            "These intervals are a per-workload uncertainty guard, not a significance test for the aggregate scoring objective. "
            "Candidates run sequentially in fixed order; between-candidate drift can remain undetected.</p>"
            if context.finalist_validation
            else f"<p>At least {context.minimum_repeats} measured repeats are required by the configured confidence policy. "
            f"Sequential drift of more than {context.drift_threshold:.0%} triggers finalist validation.</p>"
        )
        + _table(heading, "".join(rows))
        + (
            "<details><summary>Initial search evidence (excluded from accepted ranking)</summary>"
            + _table(heading, "".join(historical))
            + "</details>"
            if historical
            else ""
        )
        + "</section>"
    )


def _rows(report: TrialReport, phase: str, metric: str, context: ReportContext) -> list[str]:
    rows = []
    for key, observations in scenarios(report).items():
        values = samples(observations, (metric,))
        if not values:
            continue
        summary = summarize(values, context.minimum_repeats)
        individual = "; ".join(
            f"{item.repeat}: {formatted(next(iter(samples([item], (metric,))), None))}" for item in observations
        )
        drift_value = sequential_drift(values)
        drift = _drift_label(drift_value, context.drift_threshold)
        cells = (
            f"{report.trial_id} / {phase}",
            str(key),
            individual,
            str(summary.count),
            formatted(summary.mean),
            formatted(summary.variance**0.5 if summary.variance is not None else None),
            f"{formatted(min(values))} – {formatted(max(values))}",
            drift,
        )
        rows.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in cells) + "</tr>")
    return rows


def _drift_label(value: float | None, threshold: float) -> str:
    if value is None:
        return "Unavailable (<4 repeats)"
    status = "Drift detected" if abs(value) > threshold else "Within threshold"
    return f"{value:+.2%} ({status})"
