# GuideLLM benchmark options


A GuideLLM run accepts `name`, `request_format`, `temperature`, `profile`, `constraints`, and
exactly one `data` item.

For completions, chat completions, and responses, `temperature` defaults to `0`
and is sent as `extras.body.temperature` to the GuideLLM backend. Set it on the
named run to override it:

```yaml
name: sampled-generation
temperature: 0.7  # Preserved, with a startup warning recommending 0.
profile: {kind: synchronous}
constraints: [{kind: max_requests, count: 100}]
data: [{kind: synthetic_text, prompt_tokens: 256, output_tokens: 64}]
```

Non-generation routes, including embeddings and pooling, receive no temperature
setting. Explicit temperature settings on those routes are rejected.

## Profiles

Use one profile per named run:

```yaml
profile: {kind: synchronous}
```

```yaml
profile: {kind: throughput, max_concurrency: 32, rampup_duration: 10}
```

```yaml
profile: {kind: concurrent, streams: [1, 8, 32], max_concurrency: 32}
```

```yaml
profile: {kind: constant, rate: 10}
```

```yaml
profile: {kind: poisson, rate: 10}
```

```yaml
profile: {kind: sweep, sweep_size: 10, strategy_type: constant}
```

```yaml
profile: {kind: replay, time_scale: 1.0}
```

GuideLLM may add profiles without requiring a vLLM Optimizer release because profile
fields are passed through. Consult its
[benchmark guide](https://github.com/vllm-project/guidellm/blob/main/docs/getting-started/benchmark.md)
for version-specific fields.

## Constraints

Stop after a request count:

```yaml
constraints:
  - kind: max_requests
    count: 1000
```

Stop after a duration for each profile strategy:

```yaml
constraints:
  - kind: max_duration
    seconds: 2m
```

Constraints can be combined and are passed through to GuideLLM.

A GuideLLM run constrained only by `max_requests` uses a one-hour hard cap when
`timeouts.benchmark` is omitted. Set it explicitly for longer workloads. A
request count does not provide a safe workload-duration estimate;
duration-constrained runs can use the derived timeout instead.

`max_requests` is a stopping condition, not a request-serialization setting.
Throughput, constant, and poisson profiles may issue requests concurrently;
GuideLLM drains in-flight requests before it finishes. Use
`profile: {kind: synchronous}` when each request must wait for the previous
response, or set `max_concurrency: 1` where the selected profile supports it.
The `vllm-opt` CLI preserves GuideLLM's normal console and request-draining lifecycle.

## Request formats

Choose the vLLM-compatible route required by the dataset and model:

```yaml
request_format: /v1/completions
```

```yaml
request_format: /v1/chat/completions
```

```yaml
request_format: /v1/responses
```

```yaml
request_format: /v1/embeddings
```

The default is `/v1/completions`.
