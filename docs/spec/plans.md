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

Completed execution also writes `scores.txt`, `scores.md`, `scores.csv`,
`scores.json` and `scores.html` beside the plan. Individual run score exports
are included in their immutable artifact index. The console defaults to the
table; `run-plan --json` retains the machine-readable completion envelope, with
progress on stderr. `address-benchmark report PLAN --metric delimiter
--subsets natural hard hand --format html --out FILE` renders another view of
the recorded results without engine execution or changed scoring.

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

## Frozen local plans and accuracy gates

Local-only plans must first run `address-benchmark freeze-plan PLAN`. This
validates every local corpus and writes pins into the existing plan: experiment
configuration, framework source, engine manifest, corpus manifests, interpreters,
command executables and declared `config.artifact_files` (including models).
The matching Python framework is copied to `framework-source/address_benchmark`
beside the plan. Retain that directory and the input-only adapter code/assets for
later verification. This is a content-integrity contract, not a signed timestamp
or proof of private data custody. It performs no training or source acquisition.

Frozen assets are checked before launching adapters and again at completion.
Frozen plans cannot be refrozen in place. A policy, corpus, limit, engine, model
or runtime change requires a new experiment directory. Worker identities still
record imported packages/modules, native metadata, declared model files, actual
exits and runtime hashes. Undeclared dynamic libraries/build flags remain subject
to the existing performance supplement limits.

An optional `execution.gate` object specifies `candidate`, `max_losses`,
`min_correct`, `min_preservation` (a fraction in [0,1]); `execution.baseline` names
the incumbent. Accuracy executes fresh through the ordinary runner. The gate
requires paired judgments, no mismatched judgment eligibility, a maximum number
of incumbent-only correct cases, the candidate correct-count floor and the
candidate's correctness on every supplied preservation cohort divided by that
cohort's fixed supplied membership. A positive preservation threshold without a
supplied cohort fails. Engine failures cannot pass a gate.

A failed gate records the run as `gated`, skips timing and stops the plan before
all subsequent tracks, including any intended public evaluation. Those tracks
have `not-executed` receipts and cells; their output directories are not created.
A gated plan is incomplete (CLI exit 2), while its executed private audit can
still verify. Public evaluation must be an explicit later track; there is no
implicit public suite. Timing, public-evaluation scheduling, memory and latency
execution status are explicit; absence of a measurement is never a zero.

Paired speed uses the existing full input-only panel, independent processes,
alternating reversed orders, all trials and conditional process-pair bootstrap.
Failures/refusals invalidate timing rather than selecting an easier panel.
Native-batch adapters do not acquire warmed per-address timing support from this
feature. Comparisons default to fresh execution. The opt-in verified accuracy-reuse
contract below never reuses timing trials.

## Verified accuracy reuse

`run-plan NEW_PLAN --reuse PRIOR_PLAN` opts into
`address-benchmark.accuracy-reuse/v1`. `PRIOR_PLAN` may be its original plan JSON,
`plan-results.json`, or execution directory. The new plan still needs fresh,
distinct output directories; the old plan and all its outputs remain untouched.
Default execution remains fresh. The receipt pins the selected prior plan/receipt
files and identifies each track engine as `fresh` or `reused`.

For each matching track, the existing `verify` must first validate the prior
run's artifact hashes, envelope identity, accuracy rescore and policy/source pins.
Verification also checks that envelope runtime identities match their retained
identity files and that panel/configuration header hashes match their snapshots.
Engine configuration snapshots preserve the exact original JSON bytes.
A selected engine qualifies only when its entire engine configuration matches,
its source process succeeded, corpus manifest and ordered input/reference panel
hashes match, and a fresh input-only identity worker establishes the identical
adapter/interpreter/imported-file/distribution/model/environment fingerprint.
The worker loads the adapter and closes it normally without invoking inference;
its timeout, actual exit, stderr and identity stay in the new audit. Command
executables must be among the declared artifact pins. The full process environment
is hashed privately, without copying its potentially secret values into the
identity. A changed environment, model or dependency therefore forces fresh work.

Lazy imports that prevent a pre-inference identity match deliberately fall back
to fresh accuracy. Legacy fingerprints without the environment contract also
fall back. An invalid artifact, stale runtime, missing track, changed corpus,
changed config, unsupported external command identity or failed prior cell never
produces reuse. Decisions retain fixed diagnostic reasons privately. A missing or
changed explicitly selected source plan is rejected before execution. The source
and target run directories cannot nest.

Successful reuse copies only the selected engine's verified native artifacts,
including outputs, errors/refusals and logs. It retains the source envelope,
selected execution/case records, engine configuration and verification receipt;
copies are rehashed against the source index before acceptance. Cases, aggregates,
paired deltas, preservation counts and gate decisions use the existing scorer.
The new accuracy cell has no new inference command/exit/wall duration: the source
exit remains explicitly source provenance. `verify` checks the retained source
identity, configuration, probe, copied artifacts and rescored cases even after
the original directory is unavailable. These are integrity checks, not a signed
author attestation or a runtime reenactment. Undeclared services/shared-library
state remains outside the existing adapter identity contract.

Reports mark reused accuracy in every format, including aggregate-only private
exports. Original local paths and source content identities remain in the
private audit and are excluded from publication. Timing processes, paired engine
orders, samples and uncertainty always execute fresh for the entire selected
cohort; timing results are never copied or relabeled as contemporaneous. A
throughput cell is therefore never marked reused merely because accuracy was.

## Review additions: gate policy v2 and command inventory

Freeze and `CommandAdapter` now share the same file inventory: the resolved
executable, existing files in `command[1:]`, and `metadata.artifact_files` for a
command adapter, plus ordinary `config.artifact_files` for adapters that support
it. A bridge or model changed after freezing fails the asset check before any
worker starts. Command adapters keep their existing two-key config contract.

Imports inside a bridge are not discovered by following its import graph. Declare
each imported module or other asset that must be frozen in
`config.metadata.artifact_files`, using resolved absolute paths. For example,
this engine-manifest excerpt lists the bridge and model passed as arguments, plus
the helper imported by the bridge. Keep the other required protocol metadata
alongside `artifact_files`:

```json
{
  "name": "external-parser",
  "adapter": "command",
  "config": {
    "command": ["/usr/bin/node", "/opt/parser/bridge.mjs", "/opt/parser/model.bin"],
    "metadata": {
      "artifact_files": ["/opt/parser/lib/parse.mjs"]
    }
  }
}
```

The paths are illustrative; use installed files. Declare transitive imports too;
changing an undeclared imported file is outside the freeze contract.

The original four-key gate shape retains `address-benchmark.gate/v1` semantics.
New selectors/rates use `address-benchmark.gate/v2` and reuse existing scored
judgments. `metric` accepts `strict`, `delimiter`, `strict-streetline/v1` or
`strict-streetline/v2`; profile metrics must be declared by the corpus. Unsupported
or missing judgments never become a passing gate.

Unit ownership has its own metrics, read from each case's `unit_ownership`
record (`legacy-unit-roles-exact/v1`: the unit and subaddress coarse families,
that is Occupancy and Subaddress type/identifier; level and PO box are outside):

- `unit-span/v1`: the exact multiset of (fine role, byte span) unit tokens equals
  the reference's. Judged only with complete token references and adapter token
  support; a refusal or a unit token without spans is wrong.
- `unit-negative/v1`: the same judgment, restricted to rows whose complete token
  reference has no unit. `correct` is clean rows; false-unit rows are
  `judged_pairs - correct`.
- `unit-field/v1`: normalized unit and subaddress field values equal the
  reference's. Judged on complete references and on partial references that
  assert a unit-family field, so it works on field-only corpora.

`fine-exact/v1` judges the whole row on fine roles. Every reference token's fine
role and byte span must be predicted, with no extra or unplaced tokens. It is
judged only on complete token references, and a refusal is wrong. Summaries add
`fine_exact`.

Run summaries add `unit_ownership` with the unit-span and unit-field rates,
false-unit rows over judged negatives, and false-positive unit tokens (reference
non-unit tokens whose exact span the prediction owns as a unit) over judged
negative tokens. `strict` stays whole-address. Example:

```json
{
  "baseline": "incumbent",
  "gate": {
    "candidate": "candidate",
    "metric": "delimiter",
    "splits": ["test"],
    "requirements": [
      {"subset": "unit", "max_loss_rate": 0.0005, "min_correct_rate": 0.99},
      {"cohort": "preserve", "min_preservation": 1}
    ]
  }
}
```

Count thresholds (`max_losses`, `min_correct`) and rates can be combined. Loss
and correct rates use the matching judged-pair denominator after split/selector
filtering. Excluded splits contribute neither judgments nor preservation members.
Unknown selectors, empty judged sets and mismatched eligibility fail closed.
Preservation uses the filtered fixed cohort membership, never candidate-selected
successes. Each requirement records its metric, filter, denominator and decision
privately. A track may provide `execution` overrides over the global settings,
including its own gate thresholds. Freeze pins these overrides.

A plan-wide subset requirement applies to every executed track. It fails closed
on a track that does not declare that subset; the track is not silently excluded.
For subset requirements that belong to only some tracks, put the gate in those
tracks' `execution.gate` overrides instead of the plan-wide gate. A track override
replaces the whole gate object, so include every requirement for that track.

`verify` accepts a run, plan JSON, executed plan directory or `plan-results.json`.
New receipts retain the source plan filename, export hashes and receipt identity;
verification checks track links, executed audits and explicit skipped tracks.
`verify` and `compare` refuse runs made with different scorer/runner source using
the safe reason code `framework-differs`. Use the run's recorded framework
snapshot or original framework version to verify it; the current version does
not silently rescore it under a changed policy.
Mixed private/public plans intentionally alias every track in publication output;
a fixed progress notice explains that choice without exposing labels. All text
export formats include one gate-status line per panel.

`compare LEFT RIGHT --baseline ENGINE --candidate ENGINE --out PRIVATE_DIR`
compares existing verified runs or plans without model execution. Use `--track`
to select one matching executed track and `--metric` for a declared gate metric.
Input/reference panels and scorer/framework policies must match. The fresh private
directory retains source envelopes/cases and paired identities; `verify` checks
these paired judgments. Original native rescoring still requires the original
source audits. Console output is aggregate-only and uses the same default minimum
20; no source paths, case identities or failure examples are printed.
