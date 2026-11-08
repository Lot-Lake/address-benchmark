# Local changed-output review

Draw a bounded diagnostic queue from two retained native benchmark runs, or two
engines in one run. This source-checkout tool reads existing artifacts only; it
never invokes adapters, requests labels, fits models, changes scoring, or affects
experiment gates. It adds no package source, so retained scorer source pins stay
unchanged.

```sh
PYTHONPATH=src python3 tools/changed_review_queue.py \
  /absolute/path/before-run /absolute/path/after-run \
  --baseline incumbent --candidate candidate \
  --n 150 --seed 1 --out "$PWD/work/changed-review/example"
```

Both positional arguments accept a run directory or its `run.json`. Select the
saved engine names with `--baseline` and `--candidate`; plan directories are not
accepted. The run must be finalized (`complete` or `gated`) and each selected
engine must have a successful retained accuracy stream. A gated run remains
gated. To compare engines within one run, supply that run twice.

`--out` is explicit and must name a fresh directory under this checkout's ignored
`work/` tree. Relative paths are resolved from the working directory. Paths that
escape through symlinks or overlap either source directory in either direction
are rejected. Existing outputs are never overwritten. Output directories use
mode `0700` and files `0600`; keep the entire result local. Output contains real
input text and native outputs, including failure messages. Do not upload it to
GitHub. Stdout contains fixed aggregate count fields only, with no IDs, source
names, paths, native messages or text. Failures emit a fixed error code without
interpolating exception text.

## Identity and validation contract

The join key is the native `(corpus.id, row.id)`, with each request's native
`input_sha256` checked against its text/pair/payload. Row positions are never join
keys. Inputs, references and predictions may be independently reordered. Every
stream must have unique IDs; within each run all three identity sets must be
equal. Missing predictions or references within a successful saved run are an
error, not a review category.

The two runs must have the same corpus ID, country, locale, task, profile and
ontology. Shared IDs must retain exactly the same request and ownership
(`source`, `family`, `origin`, `split`); changed text under an existing ID is
rejected even when its new hash is internally valid. Source uses the saved
`source` field, with the benchmark's `origin/split/all` fallback. Rows present in
only one run are counted explicitly as `before_only` or `after_only`, enter the
changed population as `missing_after` or `missing_before`, and retain a null
prediction for the absent side. These are panel changes, not model regressions.

The tool checks the original run envelope content identity, hashes of consumed
artifacts, retained execution/runtime identity, and the native request/prediction
protocol. Consumed files are `corpus.json`, `inputs.jsonl`, `references.jsonl`, and
the selected engine's `predictions.jsonl`, `identity.json`, and `execution.json`.
Recorded source pins and run content IDs are retained in the local receipt;
they need not match the currently installed scorer. This is a narrow diagnostic
integrity check, **not full benchmark verification, rescoring, admission approval,
or proof of authentic authorship**. Use the original benchmark framework's
`verify` operation when full run verification is required. No source envelope or
artifact is modified.

Gold reference fields and partial-label masks remain in their original retained
artifact. Cards contain only input, ownership and raw predictions. No judged
correctness, inferred gold, or new reference is produced.

## Changes, sampling and output

Prediction fields are compared literally as canonical JSON, preserving JSON
types, list order and absent-versus-null distinctions. Every changed top-level
field is retained in `changed_fields`. Categories include `status`, `evidence`,
`tokens`, `inferred`, `normalized`, `keys`, `result`, `profile`, `message`, and
`native`; extension fields use `other`. Combined changes retain every applicable
category, rather than choosing a single winning category. Identity fields are
validated separately. Adapter metadata and scoring interpretations are not
output-change categories; unchanged raw predictions do not establish unchanged
scored behavior across different adapters or framework versions.

Sampling visits sources in turns, then cycles complete change-category
combinations within each source. SHA-256 ranks seeded with `--seed` order sources,
combinations and native row identities deterministically. The queue fills up to
`--n` while any changed rows remain; an exhausted source contributes no further
turns. There is no hard source-share cap. The same artifacts, seed and size yield
the same queue regardless of stream order.

The fresh output has two files:

- `queue.jsonl`: selected cards with native corpus/row IDs, input hashes,
  input-only requests, ownership, all change categories and raw before/after
  predictions. Error and refusal outputs remain visible locally.
- `review.json`: input/run receipts, sampling parameters, resource limits,
  unchanged/changed/missing population counts, and population/selected counts
  for every `(source, complete change-category combination)` stratum.

Unchanged rows are counted but never selected. If nothing changed, the queue is
empty and its receipt still records the population. This intentionally balanced,
changed-only sample is **not representative accuracy evidence or a gold dataset**.
Its counts must not be substituted for benchmark denominators or promotion gates.

First-version limits are 1–1,000 requested cards (default 150), 100,000 combined
input rows across both reads, 64 MiB total consumed artifact bytes including the
two envelopes, and the existing 4 MiB physical JSONL-line limit. Inputs are held
in memory within those explicit admission bounds; exceeding a bound fails before
output is created. These bounds were tested with synthetic controls, not measured
against private DEV panels. There is no renderer, judgment importer, corpus
conversion or automatic labeling step.
