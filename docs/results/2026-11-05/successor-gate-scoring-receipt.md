# Successor-e429 gate scoring validation receipt

**TLDR:** At `6be223fd` the framework had no unit-ownership judgment: every gate,
cohort and `compare` read `strict` (whole-address `primary_agrees`), so A1's unit
cohort, A3's unit arm, A4 and C3's unit vetoes could not be scored as specified.
This branch adds `legacy-unit-roles-exact/v1` judgments and three gate metrics
(`unit-span/v1`, `unit-negative/v1`, `unit-field/v1`). Synthetic `run-plan`
controls show that each perturbation moves only its intended gates. The e429
baseline reproduction (item 5) is **PENDING**: no e429 prediction ledger is
available locally yet.

Plan: `experiments/us_parser/rounds/successor_e429/PLAN.md` (Lot-Lake/us-address-normalizer
PR #18), sections 6 and 7, the "Gate scoring validation" row.

## Consequence for the frozen plan

The PLAN pins the framework at `6be223fd` (v0.3.0). That commit cannot express
the unit gates. The freeze must pin the merge commit of this branch, and the
plan's `framework-source/` snapshot must come from it. Everything `strict` reads
is unchanged: the new judgment is an added case field, and whole-address
judgments, summaries and gates are unchanged apart from the added `unit_ownership` case field and summary entry.

## 1. Scorer field per gate

| Gate | Metric (gate/compare `metric`) | Case field read | Population |
| --- | --- | --- | --- |
| A1 whole cohorts | `strict` | `primary_agrees` | cohort `dev-preservation`, basis `baseline-correct`, metric `strict`, on each DEV track |
| A1 unit cohort | `unit-span/v1` | `unit_ownership.span_agrees` | cohort basis `baseline-correct`, metric `unit-span/v1`, subset of the 688 original unit-target rows |
| A2 | `strict` | `primary_agrees` | each DEV track, `max_losses` 6 / 1 / 0 / 0 |
| A3 whole | `strict`, via `compare` | `primary_agrees` | pooled DEV; net = `right_only - left_only` |
| A3 unit | `unit-span/v1`, via `compare` | `unit_ownership.span_agrees` | the 688 original unit-target rows; net ≥ +3 |
| A4 | `unit-negative/v1`, via `compare` | `unit_ownership.span_agrees` where `gold_unit` is false | DEV rows with complete token references and no unit; false-unit rows = judged − correct |
| C3 Doorplate false-unit rows | `unit-negative/v1` | as A4 | Doorplate rows labeled without a unit; `min_correct` = judged − 54 |
| C3 Doorplate false-positive unit tokens | run summary, not a gate | `unit_ownership.false_positive_tokens` / `negative_tokens`, summed in `summary.unit_ownership.false_positive_tokens` | ≤ 93 tokens |
| C3 us-units-adversarial | `unit-field/v1` | `unit_ownership.field_agrees` | rows asserting unit-family fields |

The unit family is the legacy one (`UNIT_ROLES` in
`experiments/us_parser/rounds/boundary_plasticity_round_20261101/unit_components.py`):
OccupancyType, OccupancyIdentifier, SubaddressType and SubaddressIdentifier, so
the coarse `unit` and `subaddress` roles. Level and PO box are outside it.

## 2. Denominators

| Corpus | Metric | Judged denominator | Source |
| --- | --- | ---: | --- |
| geo-dev | `strict` | 60,522 | PLAN section 5; DEV is full-scope |
| municipal-dev / seed-dev / wisconsin-dev | `strict` | 823 / 280 / 128 | PLAN section 5 |
| pooled DEV (A3) | `strict` | 61,753 | sum of the four; equals the 61,753 rows in the e429 report |
| original unit-target (A1 unit, A3 unit) | `unit-span/v1` | 688 (cohort 662 if e429 reproduces) | `retained_model.json` `original_unit_positive` |
| original fine DEV negatives (A4) | `unit-negative/v1` | 543 | `unit_event_risk_20261102/DESIGN.md` ("543 gold-no-unit rows") |
| Doorplate v1 | `strict` | 19,586 | `retained_model.json` |
| Doorplate v1 | `unit-negative/v1` | 16,465 | e429 record |
| Doorplate v1 | negative unit tokens | 132,399 | e429 record |
| us-units-adversarial (104 rows) | `strict` | **104** (measured) | this branch, `examples/corpora/us-units-adversarial` |
| us-units-adversarial | `unit-field/v1` | **103** (62 unit, 41 no unit; measured) | the one partial row asserts no unit field and is unjudged |
| us-units-adversarial | `unit-span/v1`, `unit-negative/v1` | **0** (measured) | the corpus has no token annotations |

Only us-units-adversarial is available here; the DEV bundle and Doorplate are
not. Their denominators above are the recorded ones, and the item 5 run
measures them under the frozen scorer.

**Finding:** C3's us-units-adversarial check cannot read `unit-span/v1`. With
no token references it judges 0 rows, and a v2 gate with 0 judged pairs fails
closed. It must read `unit-field/v1` (coarse unit and subaddress values) or
`strict`. This receipt uses `unit-field/v1`. Andrei should rule on it before the
freeze.

## 3. Mapping from `legacy-coarse-role-value-exact/v1`

| Legacy field | Frozen scorer | Same when | Difference |
| --- | --- | --- | --- |
| whole correct (coarse role values exact) | `strict` → `primary_agrees`: casefold-whitespace values, coarse projection through `role_map`; complete scope = reference ∪ predicted roles, partial = supplied roles | always, apart from edge delimiters | The migration note says the legacy matrix "keeps its original edge delimiter" behavior. If that means stripping edge `,;:`, the legacy count matches `delimiter` (`delimiter_fields_agree`), not `strict`. Item 5 computes both. If only `delimiter` reproduces 59,845, A1/A2/A3 must use `metric: "delimiter"`. |
| partial "outside" rows (extra predicted fields) | unadjudicated, not errors | always | none |
| error / refusal | `status != ok`, so wrong on every judged metric | always | none |
| exact unit ownership (`unit_components.score_row` `correct`) | `unit-span/v1`: multiset of (fine role, byte span) unit tokens | the prediction's tokens align to the reference tokens | Legacy compares token index and value after alignment and marks a misaligned prediction wrong even with no unit. The frozen scorer places tokens by byte span, so a misaligned prediction without unit tokens counts as clean. |
| false unit rows (negatives not `correct`) | `unit-negative/v1`: judged − correct | aligned rows | as above |
| `false_positive_tokens` | `unit_ownership.false_positive_tokens`: reference non-unit tokens whose exact span is predicted with a unit-family role | aligned rows | Legacy excludes misaligned rows' tokens from the denominator (`unscorable_negative_tokens`); the frozen scorer counts every token-annotated row. The e429 record has 0 candidate-unaligned Doorplate rows, so the denominators agree for e429. |
| fine exact (`fine_exact`) | no gate metric; token P/R/F1 summary only | — | C3's "tracked hard fine gains" bullet has no frozen judgment. Out of this receipt's scope; it is open. |

## 4. Synthetic controls (run through `run-plan`)

The fixture is `tests/unit_controls.py`: 4 authored rows (2 unit-target, 2
unit-negative; complete fields, spans and tokens) and an input-only synthetic
parser. The incumbent `e429` has one shared whole-address error, on a negative
row, so a unit bug there cannot move `strict`. Each variant is a single-track
plan whose gate holds one requirement per PLAN gate. Every requirement uses a
zero-loss threshold, so any loss shows as movement. All three plans were run
with `run-plan` and passed `address-benchmark verify`.

Losses per gate (judged pairs in parentheses):

| Gate | Metric | identity (`e429`) | (a) unit kept, state field regressed | (b) unit type/identifier swapped + false unit on a whole-wrong negative |
| --- | --- | ---: | ---: | ---: |
| A1 whole | `strict`, cohort | 0 (3) | **3** | 0 |
| A1 unit | `unit-span/v1`, cohort | 0 (2) | 0 | **2** |
| A2 | `strict` | 0 (4) | **3** | 0 |
| A3 whole | `strict` | 0 (4) | **3** | 0 |
| A3 unit | `unit-span/v1`, unit-target | 0 (2) | 0 | **2** |
| A4 | `unit-negative/v1` | 0 (2) | 0 | **1** |
| C3 false-unit rows | `unit-negative/v1` | 0 (2) | 0 | **1** |
| C3 unit field | `unit-field/v1` | 0 (4) | 0 | **1** |

Control (a) moves only the whole-address gates. Control (b) moves only the unit
gates. Under `strict`, the type/identifier swap keeps the same coarse `unit`
value, so only the fine-role span judgment sees it. The identity control moves
nothing. `plan-results.json` SHA-256: identity `d98369ad…f0da644`, (a)
`5c71d7f7…a5223d8`, (b) `ffa75531…b110ef0`. They are regenerated by
`python -E -s -m tests.unit_controls DIR`. `tests/test_unit_ownership.py`
asserts these movements and the case-level judgments. The full suite passed:
234 tests OK.

## 5. e429 baseline under the frozen scorer: PENDING

Checked: `~/Downloads/intake-handoff-core-v1.tar.gz` (a protected input index
and intake tooling) and `legacy-exclusion-index-v1.tar.gz` (a hash-only index).
Their manifests were extracted, read-only, under `~/data/lotlake-archives/`.
Neither contains e429 predictions, report `06ada057…` or a case ledger.
`retained-baseline-v1.tar.gz` is not present yet.

When it lands:

```sh
D=~/data/lotlake-archives/retained-baseline-v1
mkdir "$D" && tar -xzf ~/Downloads/retained-baseline-v1.tar.gz -C "$D" && tar -tzf ~/Downloads/retained-baseline-v1.tar.gz
# P = a fresh plan directory: engines.json holds e429 (native-batch, model sha256 e429c2cf…),
# tracks are geo-dev, the original fine DEV (unit-target subset) and Doorplate v1
.venv/bin/address-benchmark freeze-plan P/plan.json
.venv/bin/address-benchmark run-plan P/plan.json && .venv/bin/address-benchmark verify P/plan.json
.venv/bin/python -E -s -c "import json,sys; r=json.load(open(sys.argv[1])); [print(k, v['supplied_fields'], v['delimiter_fields'], v.get('unit_ownership')) for k, v in r['accuracy']['e429']['populations'].items()]" P/runs/TRACK/run.json
```

Expected values: geo-dev 59,845/60,522; original unit-target 662/688
(`unit_span`); Doorplate whole 17,316/19,586; false-unit rows 54/16,465; and
false-positive unit tokens 93/132,399. Aggregate counts only. No rows are
printed.

## Per-gate status

| Gate | Field defined | Controls | Baseline reproduced |
| --- | --- | --- | --- |
| A1 whole | pass | pass | pending (and the strict-vs-delimiter question) |
| A1 unit | pass (new `unit-span/v1`) | pass | pending; needs complete token references and a `unit-target` subset in the DEV bundle |
| A2 | pass | pass | pending |
| A3 | pass (via `compare`) | pass | pending |
| A4 | pass (new `unit-negative/v1`) | pass | pending |
| C3 false-unit rows and tokens | pass | pass | pending |
| C3 us-units-adversarial | pass with `unit-field/v1` (needs a ruling) | pass | pending |
| C3 hard fine gains | **open**: no fine-exact gate metric | — | — |
