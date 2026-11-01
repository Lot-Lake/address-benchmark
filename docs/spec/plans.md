# Declarative benchmark plans

`address-benchmark.plan/v1` is the experiment configuration, expressed as JSON.
It selects assets and plugin configurations; it does not execute expressions or
embed a new programming language. Corpus manifests define annotation semantics
and input construction; engine manifests define adapters/options/runtime assets;
the plan defines which comparisons to run and how to schedule them.

```json
{
  "schema": "address-benchmark.plan/v1",
  "name": "my-parsing-comparison",
  "engines": "engines.json",
  "tracks": [
    {"id": "publisher-test", "corpus": "corpora/test.json", "output": "results/test"},
    {"id": "challenge", "corpus": "corpora/challenge.json", "output": "results/challenge"}
  ],
  "execution": {
    "baseline": "my-library",
    "timing": false,
    "timeout": 3600,
    "seed": 20261101
  }
}
```

Run `address-benchmark run-plan /absolute/path/plan.json`. Paths resolve within
the plan directory; input assets may separately declare explicit local-only
external locations in corpus manifests. Output directories must be fresh and
distinct. No reference file path is passed to adapters. Every track gets the
ordinary immutable run envelope, hashes, actual exits and accuracy rescore.
`plan-results.json` indexes track status and content IDs. Engine unavailability
remains explicit and makes the plan incomplete; it does not create a score.

Plans have one task/corpus per track. Parsing, normalization and identity need
their own engine configurations/plan because they request different work. There
is no automatic promotion, gold-selected engine selector, total quality weight,
or reference-derived option setting. A future suite manifest may group several
task plans without pooling their metrics.

The JSON Schema describes shape; executable validation also checks safe paths,
unique IDs, fresh/nonnested outputs, settings and asset availability. Unknown
settings are rejected. Scoring/task/ontology/profile versions are pinned by
the referenced corpus and adapter contracts, with scorer source hashes retained
in each run. A custom scorer remains code with a versioned contract rather than
an arbitrary expression in JSON.

For the existing local production cohort, `tools/prepare_local_matrix.py` writes
the plan/manifests from explicit read-only asset locations. The public recipe
contains no private executable, model or corpus bytes. Use `--smoke N` only for
first-N integration preflight; such a plan explicitly disclaims population
evidence. Omit it for the full selected populations.

The local execution driver freezes this project's framework, bridge and recipe
source before testing/running it. `framework-source.json` indexes the copied
MIT-licensed source files; external parser/model/data assets stay installed in
place and separately pinned. This avoids invalidating a long run when report
work continues in the live checkout. To rescore later, use the recorded source
snapshot's Python module path and the original run directory.
