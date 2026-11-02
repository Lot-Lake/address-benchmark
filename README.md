# address-benchmark

An independent, open-source benchmark framework for address utility libraries.
Version **0.3.0** is an executable proposal for a shared standard, not an established industry standard or a leaderboard.

Evaluate **parsing, normalization, formatting, identity keys, classification, extraction, ZIP/state inference, variants, diagnostics, stability and performance** as separate capabilities. Bring any library and interchangeable corpora. Keep the original inputs, native outputs, labels, task rules, failures and runtime identities available for audit. There is no weighted overall winner.

## Quick start

Python 3.11+; the core has **no runtime dependencies**. From a source checkout:

```sh
export PYTHONPATH="$PWD/src"
python3 -m address_benchmark validate examples/corpora/us-core/manifest.json
python3 -m address_benchmark conform demo
python3 -m address_benchmark run examples/corpora/us-core/manifest.json \
  --engines examples/adapters/engines.json --out runs/parsing-001
python3 -m address_benchmark verify runs/parsing-001
python3 -m unittest discover -s tests -v
```

Or install into your virtual environment with `python3 -m pip install -e .`, then use `address-benchmark`. Use fresh output directories. On a machine with a workload coordinator, follow its local policy before running evaluations or installing/building optional runtimes.

## Declare an experiment in JSON

Use a versioned [benchmark plan](docs/spec/plans.md) to select corpus manifests, engine configurations, execution settings and fresh result directories:

```sh
address-benchmark run-plan /absolute/path/plan.json
```

The [runnable example plan](examples/plan.json) compares demo/refusal controls on
two original corpora. Copy `examples/` to a fresh work directory before running
it; the plan writes one result index beside itself and refuses to overwrite it.

The [plan schema](schemas/plan-v1.schema.json) and semantic validator reject unknown options, unsafe paths, implicit value types and duplicate/nested outputs. Adapters and scorers remain ordinary versioned plugins; JSON describes the experiment rather than embedding a programming language.

## Clean console tables and exports

Examples from the verified production cohort: [comparison table](docs/results/2026-11-01/tables/delimiter/scores.md),
[console export](docs/results/2026-11-01/tables/delimiter/scores.txt),
and [standalone HTML](docs/results/2026-11-01/tables/delimiter/scores.html).
The [strict-policy table](docs/results/2026-11-01/tables/strict/scores.md) is a separate view of the same recorded predictions.

`run` and `run-plan` print a comparison table and automatically save
`scores.txt`, `scores.md`, `scores.csv`, `scores.json` and `scores.html`.
Datasets/views are rows; library configurations are columns. Wider console tables
split into readable column groups. Color is automatic on supported terminals and
disabled for redirected output or `NO_COLOR`. Use `--json` on the run commands
for their original machine-readable completion records; progress goes to stderr.

Reformat an existing run or executed plan without rerunning any parser:

```sh
address-benchmark report work/my-fresh-comparison/plan.json
address-benchmark report work/my-fresh-comparison/plan.json \
  --metric delimiter --subsets natural hard hand --width 200
address-benchmark report work/my-fresh-comparison/plan.json \
  --metric delimiter --subsets natural hard hand --counts --format markdown --out comparison.md
address-benchmark report work/my-fresh-comparison/plan.json \
  --metric delimiter --subsets natural hard hand --format html --out comparison.html
```

Formats: `console`, `markdown`, `csv`, `json`, `html`. Metrics: `strict`
(default), `delimiter`, `complete`, `fine-f1`, `exact` (utility tasks),
`streetline` (the [strict-streetline/v1 profile](docs/spec/profiles.md), when the corpus declares it)
and `throughput` (recorded exploratory timing only). `--counts` adds exact
numerators/denominators; fine F1 uses TP/FP/FN. JSON retains full numeric precision,
statuses and denominators. CSV contains the readable comparison matrix.
HTML is a standalone dark report with counts, row leaders, sticky labels and
horizontal scrolling. No external fonts, scripts or network requests are needed.

Missing/unsupported cells stay explicitly unmeasured. Zero remains a measured
zero. Row leaders require matching measured denominators; all displayed ties
are highlighted. Partial references, native failures and overlapping subsets
retain their original meaning. Table generation checks recorded envelope
identities and does not rescore or replace the original scoring policy. Use the
original frozen framework version for full `verify` rescoring of older runs.
The [scorecard contract](docs/spec/scorecards.md) documents the export semantics.

## Production parsing cohort

The first complete run is available in the [findings and improvement priorities](docs/results/2026-11-01/findings.md),
[nine-configuration parsing comparison](docs/results/2026-11-01/comparison.md),
and [separate utility observations](docs/results/2026-11-01/utilities.md).
It contains 1,023,327 fresh parsing predictions, with all 36 cells verified.

Real adapters support ordered Python token APIs (usaddress, fastaddress, Doorplate), direct libpostal C parsing with separately pinned default/Senzing models, the default address-normalizer source-evidence API, a persistent Mailwoman neural bridge, and generic batch executables for the retained learned model and private local BoundaryBoys runtime. Native tokens, unplaced outputs, errors and model identities remain visible. Source byte alignment derived by an adapter is explicitly distinguished from native offsets.

The [real-corpus policy](docs/spec/real-corpora.md) covers GeoSearch DEV/TEST, Doorplate v1, and expanded US50/Senzing/libpostal references. The existing source assets can be read in place without copying their caches or bundling data. To create and execute a fresh local production plan:

```sh
python3 tools/prepare_local_matrix.py \
  --source /path/to/existing/address-normalizer \
  --doorplate /path/to/doorplate --out work/my-fresh-comparison
python3 -m address_benchmark run-plan work/my-fresh-comparison/plan.json
python3 tools/report_comparison.py work/my-fresh-comparison/plan.json --out outputs/comparison
```

Use your host workload coordinator for the outer execution. `tools/execute_local_matrix.py` combines contract tests, fresh preparation and the full plan in one finite command. The source-library checkout, models and other owners' processes remain read-only. Private runtime code and corpus assets stay out of Git. `--smoke N` on preparation is a first-N integration preflight, explicitly unsuitable as population evidence.

Add `--utilities --report-out outputs/comparison` to the combined driver to run
the [separate production utility profiles](docs/spec/utility-production.md) and
write parsing and utility reports together. Normalization and matching references
are currently small conformance panels; unmeasured production APIs remain explicit
in the [coverage inventory](docs/COVERAGE.md).

The real-corpus v2 ontology preserves fine publisher role distinctions; the original strict metric remains alongside an explicit edge-delimiter diagnostic. These comparisons remain public/development-exposed evidence. Exact-text family proxies are not independent source families. Accuracy process wall durations include hashing/loading/I/O and must not be ranked as parse throughput.

The demo parser is deliberately limited. The refusal adapter is a denominator/error control. Their scores test the benchmark, not the quality of production address software. Example corpora contain fictional authored cases and separate generated views; they are public conformance evidence, not naturally sampled or unseen accuracy evidence.

## Task tracks

| Track | Implemented measurement | Runnable example |
| --- | --- | --- |
| Parsing | Coarse ordered field/value agreement; exact fine span/token/role P/R/F1; complete-address agreement on complete references; partial scope and unsupported roles | `us-core`, `us-challenge`, `us-rendered`, `us-units-adversarial` + `engines.json` |
| Normalization | Exact ordered strings under a frozen named rules profile | `us-normalization` + `normalize.json` |
| Formatting | Exact output from explicit ordered fields; no hidden parsing | `us-format` + `format.json` |
| Identity/matching keys | Independent same/distinct delivery-unit pairs; key equality, P/R/F1, collisions and missing-key coverage | `us-identity` + `identity.json` |
| Classification | Exact typed class under a named taxonomy | `us-classify` + `classify.json` |
| Component extraction | Exact typed extraction, with absent values and leading zeros | `us-extract` + `extract.json` |
| Inference | Exact typed inferred output, distinct from parsed evidence | `us-infer` + `infer.json` |
| Variants/suggestions | Required coverage, disallowed outputs, duplicates against an explicitly closed authored inventory | `us-variants` + `variants.json` |
| Diagnostics | Exact named diagnostic assertions; deliverability remains `not_checked` | `us-diagnostics` + `diagnostics.json` |
| Stability | Compare actual repeated/scalar/batch/stream/chunk/re-normalized observations; determinism, order/parity, idempotence | `us-stability` + `stability.json` |
| Performance | Same input panel, repeated independent processes, paired/reversed order, raw distributions and conditional uncertainty; optional calibrated pyperf | Any successful task adapter; `timing.json` is a same-parser control |

All corpus names above refer to `examples/corpora/NAME/manifest.json`; adapter files live in `examples/adapters/`. For example:

```sh
python3 -m address_benchmark run examples/corpora/us-identity/manifest.json \
  --engines examples/adapters/identity.json --out runs/identity-001
python3 -m address_benchmark run examples/corpora/us-stability/manifest.json \
  --engines examples/adapters/stability.json --out runs/stability-001
```

Parsing supports partial references. Other v1 tracks intentionally require complete references or unlabeled inputs; they reject partial claims they cannot yet score honestly. Identity fixtures define delivery-unit identity; a property-level key needs a different profile and references. The variant inventory is a tiny closed control, not an exhaustive inventory of valid postal renderings. Diagnostic conformance is not postal validation.

## Plug in a library

1. Implement a Python `Factory(config)` with `metadata` and `parse(Request)`, publish an `address_benchmark.adapters` entry point, or use the persistent **JSONL command adapter** for Rust, Go, C, Node and other runtimes.
2. Preserve native values/roles, repeated occurrences, byte spans when available, native audit output, and errors/refusals. Keep evidence, inference, normalized output and keys separate.
3. Declare a task, ontology/profile, complete native-role mapping, unsupported roles, output ownership, dependency/model identity, threading and additional artifact files. No adapter receives reference labels.
4. Run conformance probes, then a frozen authored corpus, then separately licensed external/private populations.

See the [adapter protocol](docs/spec/adapter.md), [task/scoring specification](docs/spec/tasks.md), and [public Python callable examples](examples/adapters/README.md). The original usaddress `parse()` wrapper preserves token tuples and declares byte spans unavailable; the v2 `python-tokens` adapter additionally offers explicitly derived exact source alignment. Install with `python3 -m pip install -e '.[usaddress]'`. Missing packages are **unavailable**, not fabricated zero scores. Production interfaces and licensing limits are in the [production integration inventory](docs/research/production-integration.md).

## Our corpora, and other evidence

The included suite is original: authored basic/challenge cases, separate source-field-supervised renderings, and utility task controls. It borrows evaluation *concepts* from Doorplate, usaddress, GeoSearch, libpostal/Senzing and other projects; it copies none of their case strings. See [annotation policy](docs/spec/annotations.md) and the [primary-source corpus research](docs/research/corpora.md).

Add a corpus by writing a versioned manifest plus JSONL in the public schema. Manifests pin provenance, revision/content hashes, asset license/redistribution, construction, country/locale/task, ontology, annotation coverage, family/split IDs and exposure history. A corpus plugin is a manifest/data package, not mandatory executable code. Optional HTTPS resources can be fetched explicitly with `address-benchmark fetch MANIFEST`; hashes are checked before installation. Private corpora use local paths and `local-only` policy. No raw external corpus, model, private listing extract or parent-project cache is bundled.

```sh
python3 -m address_benchmark audit examples/corpora/us-core/manifest.json \
  examples/corpora/us-challenge/manifest.json examples/corpora/us-rendered/manifest.json
```

Exact UTF-8 duplicates, declared source families, cross-split leakage and overlapping subsets are audited. This is not a fuzzy/geographic/training-overlap clearance. Renderings are not independent families; subsets are views, not additive totals. Natural-entry inputs require their own provenance and sampling. Public regression suites cannot establish universal non-exposure.

## Reuse measurement tools

The standard-library runner handles domain contracts and the experiment schedule. It does not reimplement calibrated timing frameworks. [Research and rationale](docs/research/frameworks.md) compare pyperf, ASV, hyperfine, Criterion.rs and pytest-benchmark using primary documentation. The [architecture decision](docs/ARCHITECTURE.md) explains the separation.

```sh
python3 -m address_benchmark run examples/corpora/us-core/manifest.json \
  --engines examples/adapters/timing.json --out runs/timing-001 \
  --timing --trials 4 --samples 5 --min-seconds 0.1 --warmup 1

# Optional, separate calibrated Python API experiment:
python3 -m pip install -e '.[timing]'
python3 -m address_benchmark export-inputs examples/corpora/us-core/manifest.json \
  --out /absolute/path/panel.jsonl
python3 tools/bench_pyperf.py --adapter demo --panel /absolute/path/panel.jsonl \
  --pins-directory /absolute/path/runtime-pins \
  -o runs/pyperf-demo.json
python3 -m pyperf check runs/pyperf-demo.json
```

The built-in paired timings are **exploratory**. pyperf supplies calibration and process-level measurements; keep its native JSON. The pyperf callable includes output destruction, whereas the exploratory runner excludes it. Those are separate contracts and must not be pooled. hyperfine suits whole-command startup/end-to-end work; Criterion native Rust investigations and ASV revision history remain separately scoped tools. Do not retime only a favored engine, reuse old competitor timings as fresh observations, discard slow samples or ignore failures. See [performance protocol](docs/spec/performance.md).

## Reproducibility

Each run freezes input-only requests, references, manifests, predictions, per-case/role outcomes, pair deltas, logs, actual exits, runtime/module/package/model hashes, scorer/source identities and raw trial measurements. `run.json` indexes hashed artifacts and has a content identity. `verify` rehashes and rescores accuracy with the original source version. It is an integrity check, not an author signature or proof that declared runtime metadata is truthful. Cache reuse is deliberately absent in v0.1: every engine cell runs fresh.

Run directories contain inputs and references, including private addresses when used. They are ignored by Git. Publish a deliberately reviewed export, not a private run folder. The published production reports contain aggregates only. Detailed overlap membership and local failure reproductions are excluded. License details are independent for benchmark code, corpus, runtime and model.

## Status and contribution

MIT for this new implementation, specification and original examples. Optional dependencies, models and external datasets retain their own licenses; see [NOTICE](NOTICE). Python source/JSONL are chosen for transparent review, low setup cost and cross-language interoperability; native compute remains in each library. A standards proposal needs independent annotation review, multiple implementers, larger licensed natural populations, and governance. [Roadmap and coverage](docs/COVERAGE.md) distinguish runnable contracts from production evidence. Geocoding, ranked search, clustering, postal verification, latency/memory/startup backends and cross-binding parity are future separate modules.

Contributions should bring a capability declaration, primary-source provenance/license evidence and contract tests. No library gets special reference repairs, private scoring exceptions or a gold-selected ensemble. See [CONTRIBUTING.md](CONTRIBUTING.md).
