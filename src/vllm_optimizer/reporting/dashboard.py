"""Compose the self-contained HTML decision report from accepted trial evidence."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting.charts import comparison_chart, effect_charts, history_chart
from vllm_optimizer.reporting.comparison import comparison
from vllm_optimizer.reporting.confidence import conclusion_class, confidence, verdict
from vllm_optimizer.reporting.context import ReportContext
from vllm_optimizer.reporting.dashboard_selection import best_observed, improvement
from vllm_optimizer.reporting.finalist_decision import decide
from vllm_optimizer.reporting.importance import importance_section
from vllm_optimizer.reporting.interactions import report_script
from vllm_optimizer.reporting.leaderboard import leaderboard
from vllm_optimizer.reporting.methodology import metric_methodology
from vllm_optimizer.reporting.overview import result_summary
from vllm_optimizer.reporting.recommendation import recommendation
from vllm_optimizer.reporting.styles import dashboard_css
from vllm_optimizer.reporting.tables import evidence_table, failures


def render_dashboard(
    directory: Path,
    metric: str,
    trials: tuple[TrialReport, ...],
    ranking: tuple[TrialScore, ...],
    baseline: TrialScore | None,
    context: ReportContext,
) -> str:
    best = best_observed(ranking[0] if ranking else None, baseline)
    reports = {report.trial_id: report for report in trials}
    selected = reports.get(best.trial_id) if best else None
    base_report = reports.get(baseline.trial_id) if baseline else None
    finalist = reports.get(ranking[0].trial_id) if ranking else selected
    change = improvement(best, baseline)
    conclusion = verdict(base_report, finalist, metric, context)
    decision = decide(trials, ranking, baseline, metric, context.finalist_validation)
    validation_reports = tuple(
        item for item in trials if item.execution.get("artifact_subdirectory") == "finalist-validation"
    )
    outcome = "Best observed configuration; baseline comparison unavailable"
    if best is None:
        outcome = "No eligible configuration"
    elif baseline and best.trial_id == baseline.trial_id:
        outcome = "Baseline wins — keep the baseline"
    elif change is not None:
        outcome = (
            "Higher optimization score observed"
            if change > 0
            else "Score tied with baseline; recommendation selected by request quality"
        )
    if context.finalist_validation:
        conclusion = decision.reason
        outcome = f"Validation favors {decision.winner_trial_id}" if decision.winner_trial_id else "No clear winner"
    conclusion_style = "confidence-note" if conclusion_class(conclusion) == "warning" else "note"
    counts = {
        state: sum(item.status.value == state for item in trials) for state in ("completed", "failed", "interrupted")
    }
    contention = (
        "<p class='warning'>Parallel search can introduce shared-resource contention. "
        "Finalist validation is identified separately below when available.</p>"
        if context.execution_mode == "local_parallel"
        else ""
    )
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>vLLM Optimizer · {escape(context.run_id)}</title><style>{dashboard_css()}</style></head><body>
<header><div><p class='eyebrow'>vLLM Optimizer decision report</p><h1>{escape(context.run_id)}</h1>
<p>Maximize <code>{escape(metric)}</code> · Mode {escape(context.execution_mode)}</p>
<nav aria-label='Report sections'><a href='#overview'>Overview</a> · <a href='#recommendation'>Configuration</a> ·
<a href='#comparison'>Comparison</a> · <a href='#confidence'>Confidence</a> · <a href='#leaderboard'>All trials</a></nav>
</div></header><main><section id='overview'><h2>{escape(outcome)}</h2>
<p class='{conclusion_style}'>{escape(conclusion)}</p>{result_summary(base_report, selected)}
<p class='run-meta'>{_duration(context)} elapsed &middot; {counts["completed"]} completed &middot; {counts["failed"]} failed &middot;
{counts["interrupted"]} interrupted &middot; {escape(context.status)}</p>{contention}</section>
{recommendation(directory, best, baseline, selected, bool(context.finalist_validation) and not decision.winner_trial_id)}
<details class='report-panel'><summary>Performance breakdown</summary>{comparison(base_report, selected)}</details>
<details class='report-panel'><summary>Confidence and validation</summary>
{confidence(directory, base_report, finalist, metric, context, conclusion, validation_reports)}</details>
{leaderboard(trials, ranking, baseline, metric, directory)}{_diagnostics(trials, ranking, baseline, context)}
</main><footer>Generated from stored experiment artifacts. Missing evidence is shown as unavailable.</footer>
{report_script()}</body></html>"""


def _diagnostics(
    trials: tuple[TrialReport, ...],
    ranking: tuple[TrialScore, ...],
    baseline: TrialScore | None,
    context: ReportContext,
) -> str:
    llm = context.llm_summary or context.llm_summary_error
    return (
        "<details class='report-panel'><summary>Diagnostics and methodology</summary>"
        "<section><h2>Accepted score comparison</h2>"
        + comparison_chart(ranking, baseline)
        + "<h3>Accepted scores in recorded trial order</h3>"
        + history_chart(trials, ranking)
        + "<p>This is trial order, not elapsed time. Superseded search executions are excluded.</p></section>"
        "<section><h2>Parameter associations</h2>"
        + importance_section(ranking)
        + "<p>Observed score means by tested value, with sample counts; associations, not controlled ablations.</p>"
        + effect_charts(ranking)
        + "</section><section><h2>Failures and interruptions</h2>"
        + failures(trials)
        + "</section>"
        + metric_methodology(context.repeat_aggregation)
        + "<section><h2>Scoring evidence</h2>"
        + evidence_table(ranking, trials, baseline)
        + f"<p>A workload is excluded when failed/incomplete requests exceed\n{context.maximum_failure_percentage:g}% of all requests. "
        f"Eligible workload metrics use their mean per named run, the {escape(context.repeat_aggregation)} across repeats, then the mean of named runs. "
        "This configured objective is separate from the workload comparisons above.</p></section>"
        + (f"<section><h2>Optional LLM summary</h2><p>{escape(llm)}</p></section>" if llm else "")
        + "</details>"
    )


def _duration(context: ReportContext) -> str:
    if not context.started_at or not context.completed_at:
        return "Unavailable"
    try:
        elapsed = (
            datetime.fromisoformat(context.completed_at) - datetime.fromisoformat(context.started_at)
        ).total_seconds()
        if elapsed < 0:
            return "Unavailable"
        total = int(elapsed)
        days, remainder = divmod(total, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError):
        return "Unavailable"
