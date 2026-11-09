# Investigate performance

Select one user-visible scenario and metric before recommending changes: interaction latency, frame time, startup, memory, request count, payload size, throughput or query time. Record device/runtime, build mode, data size, cache state and reproduction steps when available.

Trace the critical path and choose the available profiler or trace for the actual stack. Client examples include Flutter DevTools frame/rebuild timelines and browser Performance/Network traces. Backend examples include request spans, query plans and worker/queue timings. Do not install tools or run production load tests merely because this route is active.

Inspect likely causes in the affected code: repeated effects or requests, sequential independent I/O, unnecessary rebuilds/renders, expensive synchronous computation, oversized payloads, duplicate state, cache invalidation, query amplification, unbounded lists or allocations. These are hypotheses until supported by measurements. Preserve correctness when considering caching, batching or concurrency.

Report evidence as measured, observed in source, inferred, or unverified. Explain where time or memory goes only as far as evidence supports. If profiling is unavailable, give the most useful bounded measurement plan and a conditional recommendation; never invent timings or speedup percentages.

Use a sequence or critical-path diagram when it clarifies the bottleneck, with measured durations only where available. Label speculative bottlenecks. Compare before/after under the same scenario, environment and instrumentation when an implementation and measurement are authorized. Record regressions and tradeoffs, not only the best sample. Structural improvements and measured performance gains are distinct outcomes.
