# Benchmark machinery: reuse assessment

Research date: **2026-11-01**. Sources below are upstream documentation, source repositories, licenses, and release notes. Versions are observations for this assessment, not automatic dependency pins. No upstream implementation has been copied. The recommendations are this project's design judgments.

## Decision

Use **Python 3.11+ for the control plane**, with a standard-library accuracy runner and a small process scheduler. Define a language-neutral JSON adapter contract so Rust, Go, C, Node, Python, and other engines can participate without rewriting their algorithms. Keep scorer policy, corpus validation, and artifact identity independent of the timing backend. Make **pyperf an optional calibrated in-process timing backend**, **hyperfine an optional whole-command backend**, and accept native Criterion/ASV artifacts as separately scoped evidence.

These tools supply useful measurement mechanics. None of the reviewed interfaces supplies address annotation coverage, semantic ontology mappings, provenance/license decisions, family overlap, training exposure, or adjudication of partial references. That remains the benchmark product's responsibility. A single timing number from any tool cannot establish that engines did equivalent work.

## Comparison

| Tool and maintenance evidence | Reusable machinery and measurement boundary | Artifacts/statistics | Fit and limits for this project |
| --- | --- | --- | --- |
| **[pyperf](https://pyperf.readthedocs.io/en/latest/index.html)**; upstream [2.10.0, 2026-02-07](https://pyperf.readthedocs.io/en/latest/changelog.html) | Python callables inside multiple worker processes; automatic loop calibration and warmups; also a separate command benchmark API. A callable can invoke a native binding. | Native JSON retains runs, values, warmups, and metadata; distribution tools, stability checks, and comparisons. | Preferred optional Python API timing backend. Does not make arbitrary adapters equally scoped or automatically alternate engines in paired trials. Keep independent process identifiers and original JSON. |
| **[ASV](https://asv.readthedocs.io/en/stable/)**; upstream [0.6.6, 2026-06-27](https://asv.readthedocs.io/en/stable/changelog.html) | Environment/build management and historical Python-package benchmarks over commits; runtime, memory, and custom measurements. | Persistent results and static interactive history reports. | Strong choice for one parser's regression dashboard after the shared contract exists. A heterogeneous competitor matrix with distinct model bundles is a less natural primary abstraction. Its environments do not replace corpus/model content hashes. |
| **[hyperfine](https://github.com/sharkdp/hyperfine)**; upstream [2.0.0, 2026-10-07](https://github.com/sharkdp/hyperfine/releases/tag/v2.0.0) | Repeated command execution, warmups and setup/prepare hooks. Measures complete processes unless a deliberately designed command changes the scope. | JSON v2 contains per-run measurements, exit codes, metadata, and summaries; additional memory/hardware metrics depend on platform availability. | Good for startup plus model load plus command/stream processing. Do not label its whole-command result as parser-only latency. Pin its JSON schema: 2.0 changed the format and default shell behavior. |
| **[Criterion.rs](https://bheisler.github.io/criterion.rs/book/)**; upstream changelog lists [0.7.0, 2025-07-25](https://github.com/bheisler/criterion.rs/blob/master/CHANGELOG.md) | Rust callable microbenchmarks; tunable loops and explicit input/setup/drop policies. | Statistical baselines, plots, bootstrap analysis, regression detection; preserve native output and measurement settings. | Preferred native Rust investigation tool. Cross-language comparison still needs matched contracts and independent process replication. The release evidence is older than the other tools; verify the chosen revision when integrating. |
| **[pytest-benchmark](https://pytest-benchmark.readthedocs.io/en/latest/)**; upstream [5.3.0, 2026-08-23](https://pytest-benchmark.readthedocs.io/en/latest/changelog.html) | A pytest fixture for timing Python functions, with calibration; pedantic mode explicitly controls rounds, iterations, setup, and warmups. | JSON export, comparison/regression support, statistical summaries. | Convenient for parser maintainers already using pytest. Keep correctness assertions outside timed work. Normal fixture use does not supply a fresh independent process per round; process isolation needs separate orchestration. |

The maintenance evidence above establishes documented releases, not a promise of future support. Avoid choosing by star count or by one project's headline speed claim.

## License observations

The reviewed upstream license texts identify **pyperf as MIT**, **ASV as BSD-3-Clause**, **hyperfine as MIT OR Apache-2.0**, **Criterion.rs as MIT OR Apache-2.0**, and **pytest-benchmark as BSD-2-Clause**. These are tool licenses; they grant no rights to an adapter's model or a corpus. Keep notices if redistributing covered material. This project can call optional installed tools without copying their implementations. Sources: [pyperf COPYING](https://github.com/psf/pyperf/blob/main/COPYING), [ASV license statement](https://asv.readthedocs.io/en/stable/), [hyperfine license files](https://github.com/sharkdp/hyperfine), [Criterion license statement](https://bheisler.github.io/criterion.rs/book/), [pytest-benchmark LICENSE](https://github.com/ionelmc/pytest-benchmark/blob/master/LICENSE).

## Exact measurement boundaries

**pyperf API timing.** Load a fixed input-only panel and instantiate the adapter in each worker before entering the timed function. Time the full adapter call and output materialization. Record whether returned results are retained or destroyed inside the callable, whether output conversion is included, and whether any model work is lazy. A Python wrapper is part of this API's cost. A panel callable is preferable to individually timing a very fast address: pyperf's own API notes Python call overhead for functions below one millisecond. `bench_command` instead measures process execution and redirects standard streams, so it is not a replacement for accuracy/audit execution. [pyperf API](https://pyperf.readthedocs.io/en/latest/api.html)

**Rust API timing.** Criterion's ordinary `iter` includes destruction of returned values. Its batched/large-drop variants move some setup or destruction outside timing and can use substantially more memory. Such settings change the work contract; do not compare two differently configured loops under one throughput heading. `iter_custom` permits a custom boundary, but then that boundary must be independently explained. [Criterion timing loops](https://bheisler.github.io/criterion.rs/book/user_guide/timing_loops.html)

**Whole-command timing.** hyperfine 2.0 runs the measured command directly by default, while setup/prepare/cleanup hooks still use a shell. It exports unavailable memory/counter observations by omission, not as zero. Preserve backend version and complete JSON; a translation into this project's artifact envelope must not drop exits or replace missing observations. [hyperfine 2.0 release notes](https://github.com/sharkdp/hyperfine/releases/tag/v2.0.0)

**Repeated samples versus independent processes.** Samples within one warmed process share allocator, caches, runtime specialization, and thermal history. Keep process and trial grouping. Do not present individual address calls, internal loops, or overlapping source rows as independent experiments. ASV explicitly documents tuning repeats/processes, and Criterion explains its sampling/bootstrap analysis; neither proves that an address corpus consists of independent families. [ASV tuning](https://asv.readthedocs.io/en/stable/tuning.html), [Criterion analysis](https://bheisler.github.io/criterion.rs/book/analysis.html)

## Implementation-ready pyperf integration

The upstream callback is `add_cmdline_args(cmd, args)`; it modifies the worker command list in place. Register project arguments on `runner.argparser`, call `runner.parse_args()` once, and forward those arguments to every worker. Create exactly one Runner in the script. Use an absolute panel path and a stable adapter specification. Load only an exported input panel; never load reference labels in the timing worker. [pyperf Runner API](https://pyperf.readthedocs.io/en/latest/api.html)

A project integration should follow this shape (pseudocode for project-specific loading):

```python
import pyperf

def forward(cmd, args):
    cmd.extend(["--adapter", args.adapter, "--panel", args.panel])

runner = pyperf.Runner(add_cmdline_args=forward)
runner.argparser.add_argument("--adapter", required=True)
runner.argparser.add_argument("--panel", required=True)
args = runner.parse_args()
adapter, panel = load_input_only_objects(args.adapter, args.panel)

def parse_panel():
    for item in panel:
        adapter.parse(item)  # materialized result is discarded inside this scope

runner.bench_func("parse-panel", parse_panel)
```

Keep pyperf's raw file and use `python -m pyperf check FILE`, `stats FILE`, and `compare_to A B` for its native analysis. Its checks flag several instability conditions; a clean check is still not proof that model identities or task scopes match. System tuning can change the host: document recommendations and never automatically alter a shared machine. [pyperf CLI](https://pyperf.readthedocs.io/en/latest/cli.html), [system tuning](https://pyperf.readthedocs.io/en/latest/system.html)

## MVP versus defensible publication measurements

The zero-dependency runner should perform contract validation, independent process launches, explicit warmups, a fixed panel, recorded engine order, reversed order on alternating trials, raw durations/exits/logs, and deterministic artifact hashes. That scheduler exists because the shared domain experiment requires it. It should call its timings **exploratory**, with no calibrated-regression or publication-grade claim.

For a performance paper or leaderboard, use the optional calibrated backend or engine-native tool; predeclare API scope, process repetitions, warmup policy, host conditions, uncertainty method, and missing/failing runtime policy. Compare contemporaneous paired runs, retain every measured run, and report how failures affect useful work. Use paired process-level deltas/ratios; more labels are not more timing replications. Keep startup, steady-state throughput, request latency, memory, and parallel batch execution as separate experiments. An optional backend attachment must include its raw file hash and contract/panel/runtime pins. Preserve the domain artifact format even when the measurement backend changes.

The implementation recommendation is intentionally small: do not rebuild pyperf's calibration or Criterion's statistical engine, and do not impose ASV's environment manager on every user. Add richer backends incrementally after their protocol and artifact translations have contract tests.

## Future task extensions, outside the current utility tracks

The implemented product has independently versioned parsing and address-utility tracks. A future standard may add geocoding/search modules; a shared run envelope does not make their gold references or metrics interchangeable. The following reuse candidates are research only, not implemented geocoding/search support or automatic provider calls.

| Future task | Reuse candidate | Address-specific work that remains |
| --- | --- | --- |
| Geocoding coordinate error | **GeographicLib** for WGS84 ellipsoidal geodesic distance; pyproj.Geod where vectorized geospatial tooling already exists. | Reference CRS/axis order, coordinate provenance and uncertainty, address-point versus street/locality-centroid precision, top-1 versus top-k policy, abstentions, coverage and threshold definitions. A spherical approximation needs a distinct scorer name and cannot silently replace an ellipsoid metric near thresholds. |
| Matching/search/retrieval | **ir_measures** as a common interface to established IR metrics; **ranx** for ranking evaluation/comparisons; **trec_eval** as an interoperability reference. | Separate query/candidate IDs and relevance judgments, immutable candidate universe, entity-level duplicate policy, partial judgment handling and judged-at-k reporting. Parse token labels do not constitute search relevance gold. |
| Metric distribution/integration | **Hugging Face Evaluate** can package a custom versioned metric module. | Its module API still requires implementing and documenting address-specific semantics, coverage and mappings. It is optional distribution plumbing, not evidence that generic exact match answers the parsing problem. |

GeographicLib's [official Python API](https://geographiclib.sourceforge.io/html/python/code.html) accepts latitude/longitude in degrees and returns `s12` in meters:

```python
from geographiclib.geodesic import Geodesic
meters = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)["s12"]
```

The [project license is MIT/X11](https://github.com/geographiclib/geographiclib-python). Reviewed release `geographiclib==2.1` is a suitable explicit candidate pin; any future integration must record the actual installed version and package hash. The alternative [pyproj Geod API](https://pyproj4.github.io/pyproj/stable/api/geod.html) uses `Geod(ellps="WGS84").inv(lon1, lat1, lon2, lat2)` and returns forward azimuth, back azimuth and distance: its axis order differs. Choose one canonical scorer implementation/version for a run. Neither library can decide whether the reference represents a rooftop or a centroid.

[ir_measures](https://ir-measur.es/en/latest/getting-started.html) accepts qrels and scored runs and provides per-query and aggregate results, including `Judged@k`. Pin the selected provider as well as its wrapper because provider fallback is configurable. Its [license is Apache-2.0](https://github.com/terrierteam/ir_measures/blob/main/LICENSE.txt); [ranx is MIT](https://github.com/amenra/ranx/blob/master/LICENSE). Their ranking metrics are candidates for future retrieval tasks, not substitutes for span-role precision/recall. [trec_eval](https://github.com/usnistgov/trec_eval) documents the established evaluation interface; inspect its own notices and any backend's transitive licenses before redistribution.

Evaluate's [custom-module documentation](https://huggingface.co/docs/evaluate/creating_and_sharing) exposes typed prediction/reference inputs and a custom computation method; [its code license is Apache-2.0](https://github.com/huggingface/evaluate/blob/main/LICENSE). Publishing such a module can follow a stable address-scoring contract later. The current product does not require Hub access or automatic dataset/metric downloads.
