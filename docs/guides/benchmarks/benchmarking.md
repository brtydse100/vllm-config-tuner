# Benchmark configuration

Set `benchmark.engine` to `guidellm` (the default) or `vllm`. Each run invokes
the selected engine against the same vLLM trial. vLLM Optimizer saves raw
JSON and `benchmark.log`, then normalizes the result for scoring and reporting.

Generation benchmarks default to `temperature: 0`. Explicit nonzero temperatures
are preserved and produce a startup warning for each affected named run. Zero
temperature uses greedy sampling to reduce output variation; timing measurements can still vary.
Use `args.temperature` for vLLM or a run-level `temperature` for GuideLLM.

Use `benchmark.warmup_repeats` for discarded benchmark executions. Each named
benchmark receives these warmups once per trial attempt, before measured repeats. Set `benchmark.repeats` to at least `benchmark.min_repeats`
for a ranking with the configured confidence policy. Warmups default to zero;
the default repeat count and minimum are both 4 for fixed-repeat runs.
Reports show sample standard deviation, a 95% Student's t confidence
interval, and flag sequential drift above `analysis.drift_threshold` (5% by
default). Without `analysis.finalist_validation`, the top two affected finalists are
rerun sequentially when drift is detected; artifacts are stored under
`validation-001`. Optional [fresh finalist validation](benchmark-repeats.md#fresh-finalist-validation)
uses a fixed budget even without drift and stores evidence under
`finalist-validation`. Neither path guarantees a conclusive winner.

Both adapters expose the same canonical fields: requests/s, output and total
tokens/s, TTFT, TPOT, ITL, end-to-end latency, and successful/errored/incomplete
request totals. Statistical metrics use `average`, `median`, `p95`, and `p99`. Values
remain absent when the backend did not supply them; vLLM Optimizer never
relabels an average as a percentile. GuideLLM request latency is converted from
seconds to milliseconds. The raw backend JSON remains available unchanged.

Benchmark output is flushed to `benchmark.log` while it runs. A request limit
adds a live completed/total counter; a duration-only GuideLLM run adds an
elapsed/limit timer. Set `benchmark.max_failure_percentage` to accept a bounded
percentage of explicit errors or incomplete requests. Their backend-provided
details are saved separately in `failed_requests.json`.
vLLM progress uses the same argument spellings as command construction. Its
`num-warmups` and enabled readiness request are excluded from measured progress;
`ready-check-timeout-sec` defaults to `0`, so readiness is disabled by default.

## vLLM Bench Serve

Use `args` exactly as flags following `vllm bench serve`:

```yaml
benchmark:
  engine: vllm
  repeats: 2
  runs:
    - name: random-throughput
      args:
        dataset-name: random
        random-input-len: 512
        random-output-len: 128
        random-prefix-len: 0
        num-prompts: 1000
        request-rate: inf
        max-concurrency: 32
        percentile-metrics: ttft,tpot,itl,e2el
        metric-percentiles: 50,90,95,99
        ignore-eos: true
```

When `min_repeats` is omitted, it is `min(4, repeats)` for fixed-repeat runs.
Adaptive repeats use `min(2, repeats)`. Thus this explicit
two-repeat smoke workload requires both measurements; setting only `repeats: 1`
is also valid and is labeled exploratory in reports.

The `vllm-opt` CLI automatically uses `--backend vllm` and also owns `model`, `host`,
`port`, `base-url`, `save-result`, `append-result`, `result-dir`, and
`result-filename`; do not put them under `args`. Underscores
and hyphens are both accepted in keys; an optional leading `--` is stripped.
Duplicate spellings of the same flag are rejected. `true` adds a flag and `false` omits it.
Inline forms such as `args: {"--temperature=0.7": true}` are supported and use
the same validation and duplicate checks as separate key/value forms.
A list emits one flag followed by every item. Other scalar values are passed as
strings, so new vLLM options do not require a vLLM Optimizer release.

Temperature must be a finite number in `[0, 2]`, including both boundaries.
For example, `args: {temperature: 0}` emits `--temperature 0.0`.
An `extra-body` JSON string can override the request temperature, following
vLLM's precedence; startup warnings use that effective value. Invalid
temperatures or JSON bodies fail configuration validation before execution.
Dotted JSON fields such as `args: {extra-body.temperature: 0.7}` are also
supported; JSON field names retain their underscores. When dotted fields and
a whole `extra-body` JSON string are supplied together, the dotted object
replaces the whole JSON body, matching vLLM's parser precedence.
Multiple completions, such as `extra-body: '{"n":2}'`, require an explicit
nonzero temperature in `args.temperature` or the effective request body.
The default `0` and explicit zero values fail preflight for `n > 1`.
When a benchmark process exits unsuccessfully, the diagnostic includes the run
name, exit code, and full `benchmark.log` path, plus available log output.
Request-completion failures and invalid results also include the log path.

Common dataset forms:

```yaml
# ShareGPT JSON
args:
  dataset-name: sharegpt
  dataset-path: /benchmarks/ShareGPT_V3.json
  num-prompts: 500
```

```yaml
# Hugging Face dataset
args:
  dataset-name: hf
  dataset-path: organization/dataset
  hf-split: test
  num-prompts: 500
```

```yaml
# Custom JSON or JSONL supported by the installed vLLM
args:
  dataset-name: custom
  dataset-path: /benchmarks/requests.jsonl
  custom-output-len: 128
  num-prompts: 500
```

```yaml
# Prefix-repetition workload
args:
  dataset-name: prefix_repetition
  prefix-repetition-prefix-len: 1024
  prefix-repetition-suffix-len: 128
  prefix-repetition-num-prefixes: 16
  prefix-repetition-output-len: 64
  num-prompts: 512
```

Other upstream datasets include `burstgpt`, `sonnet`, `random-mm`,
`random-rerank`, `custom_audio`, `custom_image`, `spec_bench`, `speed_bench`,
and `timed_trace`. Their arguments can change with vLLM; use the
[official reference](https://docs.vllm.ai/en/latest/cli/bench/serve/) and place
its flags under `args`.

The adapter maps `output_throughput`, `request_throughput`, and
`total_token_throughput` to `output_tokens_per_second`,
`requests_per_second`, and `total_tokens_per_second`. Flat mean, median, P95, and
P99 latency fields are combined into the canonical statistical objects.
Completed, failed, and missing requests use the same error-aware ranking as
GuideLLM.

## More benchmark options

- [GuideLLM profiles, constraints, and request formats](benchmark-guidellm.md)
- [Synthetic, Hugging Face, local-file, and trace datasets](benchmark-data.md)
- [Repeats and error handling](benchmark-repeats.md)
