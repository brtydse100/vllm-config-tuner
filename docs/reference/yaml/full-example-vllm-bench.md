# vLLM Bench Serve alternative

Replace the `benchmark` section from the main example with this section to use
vLLM's native benchmark. The `vllm-opt` CLI supplies the model, server address,
and result paths:

```yaml
benchmark:
  engine: vllm
  repeats: 4
  runs:
    - name: random-throughput
      args:
        temperature: 0  # Default; explicitly supported by vLLM 0.30.
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

The [benchmark guide](../../guides/benchmarks/benchmarking.md) includes ShareGPT, Hugging Face,
custom, and prefix-repetition examples plus arbitrary argument rules.

## Important boundaries

- A GuideLLM run allows one dataset item. Use multiple named runs for several
  workloads; multi-dataset GuideLLM runs are a roadmap item.
- Warmups are disabled by default. Add `warmup_repeats` to the benchmark section
  only when the experiment needs discarded warmup measurements.
- `analysis.llm_summary` is optional and sends only the top-ranked,
  name-redacted trial values to the configured OpenAI-compatible endpoint.
- Console progress is shown at the selected logging level. Raw benchmark JSON
  and `benchmark.log` are always preserved for scoring and debugging.
- Random and TPE trial requests larger than the unique search space are capped
  with a warning. Duplicate resolved configurations are never executed.

See [benchmarking](../../guides/benchmarks/benchmarking.md) for smaller examples and upstream links,
and [configuration](../../guides/configuration.md) for rendering rules.
