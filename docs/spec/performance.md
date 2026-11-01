# Performance contract v1

The same frozen input-only panel, order and task/profile go to every engine.
The default exploratory panel is the entire selected corpus, shuffled with the
recorded seed. A failure/refusal invalidates its timing cell; there is no
gold-conditioned input filtering. Real studies should freeze a representative
input-only performance corpus separately from accuracy annotations.

Each process loads the adapter/model and runtime fingerprint outside timing,
warms on full panels, then records repeated samples until each sample accumulates
the requested minimum **timed work**. A sample sums full-panel parse/materialized
output allocations. Validation, output destruction, checksum, disk I/O and audit
serialization are outside that timer. A command adapter's own pipe/JSON overhead
is part of its public call. Warmup counts, actual loops/counts/times, native output
checksum and load observation remain available. This is amortized serial API
throughput, not request-latency percentiles or isolated decoder time.

One engine process executes at a time. One caller is used; dependency helper
threads are declared, not assumed absent. Ownership/retention and metadata are
engine-specific. Do not compare jobs with different required output work as if
the difference were implementation speed. Scalar/batch/streaming/concurrency
are separate operating points.

Trials launch independent processes for every engine. On each even trial, a
seeded shuffled engine order is chosen; the next trial reverses that order.
Every cohort has an even number of trials. Trial medians use **all** within-process
samples. A paired throughput ratio uses the pair's process medians, then reports
the median ratio across complete trials. Any missing/failed process makes the
full-cohort comparison incomplete with a null central estimate; observed ratios
remain available as diagnostics. No fastest-run selection or failure exclusion.

For >=4 complete pairs the pilot reports a deterministic 2,000-resample
process-pair bootstrap percentile interval. It is conditional on independent
pairs and not calibrated as a universal confidence guarantee. Shared-host load,
autocorrelation and thermal effects can violate this assumption. Individual
samples inside a process are not independent processes. Within-process max/min
spread exceeding 10% of the median is flagged. Do not suppress noisy trials.

Use optional **pyperf** for calibrated Python callable measurements, preserving
its native JSON and runtime/panel pins. Its helper callable includes output
destruction, so it is a different contract from the pilot. The provided helper
validates the panel before timing; a publication-quality long-running study
also needs post-run error/determinism checks and paired cross-engine scheduling.
Never call pyperf's calibration evidence an address-specific accuracy check.

Use **hyperfine** for whole-command startup/model-load/stream jobs, **Criterion**
for native Rust investigations and **ASV** for environment/revision histories.
These optional backends are documented integrations, not all implemented output
translators. Do not compare a whole process to warmed parsing or combine their
raw samples. No automatic host tuning runs here.

Run artifacts record interpreter hash, imported module files, installed
distribution assets, declared external model/data files, platform/architecture,
CPU counts, clock, selected thread environment, commands, actual exits/logs,
timeouts, source/adapter/scorer hashes and settings. Coverage is bounded: OS and
undeclared system dynamic libraries, compiler/build flags of prebuilt artifacts,
remote services and effective thread counts cannot be inferred reliably.
Publication requires an explicit hardware/build/environment supplement when
those are missing. Process wall duration and adapter load duration are audit
observations, not separate startup benchmarks. Memory, allocations, latency and
native batch/streaming timing remain future backends; unmeasured is null/absent,
never zero. v0.1 has no result-cache reuse.

Production accuracy may use explicitly declared independent native shards (the
Mailwoman comparison uses four one-intra-op-thread processes, matching its prior
accuracy setup). Each shard retains actual exit, input/output and logs; outputs
are validated and concatenated in original input order. This is accuracy
parallelism, not a throughput measurement. The top-level scheduler still selects
one engine configuration at a time. All shard/concurrency details override any
legacy shorthand about a single top-level adapter worker.
