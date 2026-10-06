# Benchmarks, optimization, and timeouts

```yaml
benchmark:
  engine: guidellm  # guidellm (default) or vllm
  repeats: 4  # Default: 4. Report comparisons use the mean across repeated runs.
  min_repeats: 2  # Measure every trial at least twice before adapting.
  adaptive_repeats:
    minimum_relative_score: 0.7  # Skip the remaining repeats for weak trials.
  # warmup_repeats: 1  # Optional; omitted means no warmup.
  runs:
    # Each named run is one GuideLLM invocation against the same server.
    # A run must contain exactly one data item.
    - name: concurrent-chat
      request_format: /v1/chat/completions  # Default: /v1/completions.
      temperature: 0  # Default for generation; nonzero values warn at startup.
      profile:
        kind: concurrent
        streams: [4, 16, 32]
        max_concurrency: 32
      constraints:
        - kind: max_requests
          count: 500
        - kind: max_duration
          seconds: 2m  # Duration strings and numeric seconds are accepted.
      data:
        - kind: synthetic_text
          prompt_tokens: 512
          prompt_tokens_stdev: 32
          prompt_tokens_min: 128
          prompt_tokens_max: 1024
          output_tokens: 128
          output_tokens_stdev: 16
          output_tokens_min: 32
          output_tokens_max: 256
          turns: 1

    - name: maximum-throughput
      request_format: /v1/completions
      profile:
        kind: throughput
        max_concurrency: 32
        rampup_duration: 10
      constraints: [{kind: max_requests, count: 500}]
      data:
        - kind: json_file
          path: /benchmarks/prompts.jsonl  # JSON and JSONL use json_file.

    # Profile alternatives: copy one profile into a run; do not combine kinds.
    # - name: synchronous
    #   profile: {kind: synchronous}
    #   constraints: [{kind: max_requests, count: 100}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: constant-rate
    #   profile: {kind: constant, rate: 10}
    #   constraints: [{kind: max_duration, seconds: 2m}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: poisson-rate
    #   profile: {kind: poisson, rate: 10}
    #   constraints: [{kind: max_duration, seconds: 2m}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: sweep
    #   profile: {kind: sweep, sweep_size: 10, strategy_type: constant}
    #   constraints: [{kind: max_requests, count: 500}]
    #   data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
    # - name: trace-replay
    #   profile: {kind: replay, time_scale: 1.0}
    #   constraints: [{kind: max_requests, count: 500}]
    #   data:
    #     - kind: trace_synthetic
    #       path: /benchmarks/trace.jsonl
    #       timestamp_column: timestamp
    #       prompt_tokens_column: input_length
    #       output_tokens_column: output_length

    # Other request routes supported by the model and GuideLLM:
    # request_format: /v1/completions
    # request_format: /v1/chat/completions
    # request_format: /v1/responses
    # request_format: /v1/embeddings

    # Dataset alternatives: every run must select exactly one data item.
    # data: [{kind: huggingface, source: garage-bAInd/Open-Platypus,
    #         load_kwargs: {split: train}}]
    # data: [{kind: hf, source: /local/dataset, load_kwargs: {split: train}}]
    # data: [{kind: csv_file, path: /benchmarks/prompts.csv}]
    # data: [{kind: text_file, path: /benchmarks/prompts.txt}]
    # data: [{kind: parquet_file, path: /benchmarks/prompts.parquet}]
    # data: [{kind: arrow_file, path: /benchmarks/prompts.arrow}]
    # data: [{kind: hdf5_file, path: /benchmarks/prompts.hdf5}]
    # data: [{kind: db_file, path: /benchmarks/prompts.db}]
    # data: [{kind: tar_file, path: /benchmarks/prompts.tar}]
    # GuideLLM also provides synthetic_image, synthetic_video, mooncake, and
    # weka data kinds. Their fields are version-specific and pass through.

baseline:
  enabled: true  # Default: true. Tests the fixed configuration first.

optimization:
  maximize: output_tokens_per_second  # Required metric from the selected backend.
  sampler: tpe                        # grid, random, or tpe. Default: grid.
  trials: 20                          # Required for random/tpe; invalid for grid.
  # For exhaustive Grid search, replace the two lines above with:
  # sampler: grid
  # Do not set trials for Grid; it evaluates every unique combination.
  # For Random search, use sampler: random together with trials.

timeouts:
  startup: 15m    # Default: 15 minutes. Numeric seconds also work.
  benchmark: 20m  # Explicit limit; request-only runs otherwise use a 1h cap.
  # Omit benchmark when GuideLLM duration is bounded or the 1h cap is enough.
  # vLLM keeps its 180-second default.
  # The old literal value `auto` is intentionally invalid.

```
