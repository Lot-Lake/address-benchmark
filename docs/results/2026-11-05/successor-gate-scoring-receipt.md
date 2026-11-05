# Successor-e429 gate scoring validation receipt

**TLDR:** At `6be223fd`, every gate read whole-address `strict`, and nothing could
score unit ownership or exact fine roles. This branch adds unit-ownership
judgments (`unit-span/v1`, `unit-negative/v1`, `unit-field/v1`) and a whole-row
fine-role judgment (`fine-exact/v1`). Synthetic `run-plan` controls show that each
perturbation moves only its intended gates. The frozen scorer reproduces every
e429 count recorded on Doorplate v1 exactly. The whole-address count reproduces
under `delimiter`, not `strict`, so the whole-address gates move to `delimiter`.
geo-dev and the original unit-target rows are PENDING: their corpora are not in
the retained-baseline archive.

Plan: `experiments/us_parser/rounds/successor_e429/PLAN.md` (Lot-Lake/us-address-normalizer
PR #18), sections 6 and 7, the "Gate scoring validation" row.

## Rulings applied

1. **Framework pin.** The freeze pins this branch's merge commit, not `6be223fd`.
   `6be223fd` cannot express the unit or fine gates. The plan's `framework-source/`
   snapshot must come from the merge commit.
2. **us-units-adversarial reads `unit-field/v1`.** The corpus has no token annotations.
   `unit-span/v1` judges 0 of its rows, and a v2 gate with 0 judged pairs fails closed.
   `unit-field/v1` judges 103 rows (62 with a unit, 41 without). The one partial row
   asserts no unit field, so it is unjudged.
3. **Whole-address metric: decided by the data.** `delimiter` reproduces e429's recorded
   Doorplate whole count exactly; `strict` does not (section 5). These gates change
   metric from `strict` to `delimiter`: A1 whole cohorts, A2, A3 whole, and C3's tracked
   hard whole gains. geo-dev has not been reproduced yet, so the change is confirmed on
   Doorplate only.
4. **C3 hard fine gains read `fine-exact/v1`,** added here with the same controls.

The whole-address judgments are unchanged. The only additions are the
`unit_ownership` case field and the `unit_ownership` and `fine_exact` summary
entries.

## 1. Scorer field per gate

| Gate | Metric (gate/compare `metric`) | Case field read | Population |
| --- | --- | --- | --- |
| A1 whole cohorts | `delimiter` | `delimiter_fields_agree` | cohort `dev-preservation`, basis `baseline-correct`, metric `delimiter`, on each DEV track |
| A1 unit cohort | `unit-span/v1` | `unit_ownership.span_agrees` | cohort basis `baseline-correct`, metric `unit-span/v1`, subset of the 688 original unit-target rows |
| A2 | `delimiter` | `delimiter_fields_agree` | each DEV track, `max_losses` 6 / 1 / 0 / 0 |
| A3 whole | `delimiter`, via `compare` | `delimiter_fields_agree` | pooled DEV; net = `right_only - left_only` |
| A3 unit | `unit-span/v1`, via `compare` | `unit_ownership.span_agrees` | the 688 original unit-target rows; net ≥ +3 |
| A4 | `unit-negative/v1`, via `compare` | `unit_ownership.span_agrees` where `gold_unit` is false | DEV rows with complete token references and no unit; false-unit rows = judged − correct |
| C3 tracked hard whole gains | `delimiter` | `delimiter_fields_agree` | pinned cohort file, `min_preservation: 1` |
| C3 tracked hard fine gains | `fine-exact/v1` | `tokens` fine score: `status == ok`, `metrics.fp == 0`, `metrics.fn == 0`, no unplaced tokens | pinned cohort file, `min_preservation: 1` |
| C3 Doorplate false-unit rows | `unit-negative/v1` | as A4 | Doorplate rows labeled without a unit; `min_correct` = judged − 54 |
| C3 Doorplate false-positive unit tokens | run summary, not a gate | `unit_ownership.false_positive_tokens` / `negative_tokens`, in `summary.unit_ownership.false_positive_tokens` | ≤ 93 tokens |
| C3 us-units-adversarial | `unit-field/v1` | `unit_ownership.field_agrees` | the 103 rows that assert unit-family fields |

The unit family is the legacy one (`UNIT_ROLES` in
`experiments/us_parser/rounds/boundary_plasticity_round_20261101/unit_components.py`):
OccupancyType, OccupancyIdentifier, SubaddressType and SubaddressIdentifier, so
the coarse `unit` and `subaddress` roles. Level and PO box are outside it.

## 2. Denominators

| Corpus | Metric | Judged denominator | Source |
| --- | --- | ---: | --- |
| geo-dev | whole | 60,522 | PLAN section 5; DEV is full-scope |
| municipal-dev / seed-dev / wisconsin-dev | whole | 823 / 280 / 128 | PLAN section 5 |
| pooled DEV (A3) | whole | 61,753 | sum of the four; equals the 61,753 rows in the e429 report |
| original unit-target (A1 unit, A3 unit) | `unit-span/v1` | 688 (cohort 662 if e429 reproduces) | `retained_model.json` `original_unit_positive` |
| original fine DEV negatives (A4) | `unit-negative/v1` | 543 | `unit_event_risk_20261102/DESIGN.md` |
| Doorplate v1 | whole (`delimiter`) | **19,586** (measured) | section 5 |
| Doorplate v1 | `unit-negative/v1` | **16,465** (measured) | section 5 |
| Doorplate v1 | negative unit tokens | **133,047** (measured; the record has 132,399) | section 5 |
| Doorplate v1 | `unit-span/v1` | **3,121** (measured; the record has 3,060) | section 5 |
| Doorplate v1 | `fine-exact/v1` | **19,586** (measured; the record has 19,488 aligned) | section 5 |
| us-units-adversarial | `strict` / `delimiter` | **104** (measured) | `examples/corpora/us-units-adversarial` |
| us-units-adversarial | `unit-field/v1` | **103** (62 unit, 41 no unit; measured) | ruling 2 |
| us-units-adversarial | `unit-span/v1`, `unit-negative/v1`, `fine-exact/v1` | **0** (measured) | no token annotations |

## 3. Mapping from `legacy-coarse-role-value-exact/v1`

| Legacy field | Frozen scorer | Evidence |
| --- | --- | --- |
| whole correct (coarse role values exact; edge delimiters kept from the old matrix) | `delimiter` → `delimiter_fields_agree`: casefold-whitespace values with edge `,;:` stripped, coarse projection through `role_map`; complete scope = reference ∪ predicted roles, partial = supplied roles | Doorplate 17,316 exact. `strict` gives 17,311: the 5-row gap is the handwritten stratum, where publisher references carry edge delimiters. |
| partial "outside" rows (extra predicted fields) | unadjudicated, not errors | by construction |
| error / refusal | `status != ok`, so wrong on every judged metric | by construction |
| exact unit ownership (`unit_components.score_row` `correct`) | `unit-span/v1`: multiset of (fine role, byte span) unit tokens | Doorplate 1,925 exact |
| false unit rows | `unit-negative/v1`: judged − correct | Doorplate 54 / 16,465 exact |
| `false_positive_tokens` | `unit_ownership.false_positive_tokens`: reference non-unit tokens whose exact span is predicted with a unit-family role | Doorplate 93 exact |
| fine exact (`fine_exact` rows) | `fine-exact/v1`: every fine role and span, whole row | Doorplate 16,441 / hard 1,221 / natural 14,537 / hand 683, all exact |

The numerators all reproduce. The legacy denominators were over the 19,488
token-aligned rows: the legacy run fixed 98 baseline-unaligned rows as
exclusions. The frozen scorer places tokens by byte span and judges all 19,586
rows. That is why the unit-span, negative-token and fine-exact denominators are
larger. This is inferred from the record's `aligned_rows` and was not traced row
by row. A gate threshold is therefore stated as a count (for example ≤ 54 rows,
≤ 93 tokens), never as a rate carried over from the legacy denominators.

## 4. Synthetic controls (run through `run-plan`)

The fixture is `tests/unit_controls.py`: 4 authored rows (2 unit-target, 2
unit-negative; complete fields, spans and tokens) and an input-only synthetic
parser. The incumbent `e429` has one shared whole-address error, on a negative
row, so a unit bug there cannot move whole-address. Each variant is a
single-track plan whose gate holds one requirement per PLAN gate. Every
requirement uses a zero-loss threshold, so any loss shows as movement. All four
plans were run with `run-plan` and passed `address-benchmark verify`.

Losses per gate (judged pairs for the identity run in parentheses):

| Gate | Metric | identity | (a) unit kept, state regressed | (b) unit type/ID swapped + false unit on a whole-wrong negative | (c) road type read as road name |
| --- | --- | ---: | ---: | ---: | ---: |
| A1 whole | `strict`, cohort | 0 (3) | **3** | 0 | 0 |
| A1 unit | `unit-span/v1`, cohort | 0 (2) | 0 | **2** | 0 |
| A2 | `strict` | 0 (4) | **3** | 0 | 0 |
| A3 whole | `strict` | 0 (4) | **3** | 0 | 0 |
| A3 unit | `unit-span/v1` | 0 (2) | 0 | **2** | 0 |
| A4 | `unit-negative/v1` | 0 (2) | 0 | **1** | 0 |
| C3 false-unit rows | `unit-negative/v1` | 0 (2) | 0 | **1** | 0 |
| C3 unit field | `unit-field/v1` | 0 (4) | 0 | **1** | 0 |
| C3 hard fine | `fine-exact/v1`, cohort | 0 (3) | **3** | **2** | **3** |

- Control (a) moves only the whole-address gates.
- Control (b) moves only the unit gates.
- Control (c) keeps the whole-address value and the unit, and moves only the
  fine gate.
- The fine gate also moves under (a) and (b). That is by design: an exact fine
  row implies a correct whole address and unit, so any whole or unit error is
  also a fine error.
- The fixture has no edge delimiters, so `strict` and `delimiter` judge it
  identically. The whole-address rows stand for both.

`plan-results.json` SHA-256: identity `51257332…8b61ffcb`, (a) `9a64ad87…daa024e4b`,
(b) `f9f7770e…b1f29f1df4`, (c) `b91e94c0…a9f056b3f`. They are regenerated by
`python -E -s -m tests.unit_controls DIR`. `tests/test_unit_ownership.py`
asserts these movements and the case-level judgments. The full suite passed:
238 tests OK.

## 5. e429 baseline reproduced by the frozen scorer

**Doorplate v1: reproduced exactly.** **geo-dev and the original unit-target rows: PENDING.**

- **Engine:** `learned-parser --batch`, built from us-address-normalizer
  `packages/rust-core` (`--features learned-model`). Its `--metadata` reports model
  SHA-256 `e429c2cf…a889fe965`, which equals the archive's `model/model.bin`.
- **Corpus:** Doorplate suite v1 `compare.jsonl.gz` at upstream `3fc5ec4fd79c`.
  Its SHA-256 `2336f099…f006b430` matches the catalog pin, and it has 19,586 rows.
- **Run:** a local-only `freeze-plan` → `run-plan` → `verify` (status `verified`), at
  framework commit `a4dba9a`.
- **Populations:** the framework reports the two Doorplate origins as separate
  populations; the counts below add them. Aggregates only.

| Measure | Frozen scorer | e429 record | Result |
| --- | ---: | ---: | --- |
| whole, `delimiter` | **17,316** / 19,586 (816 hand + 16,500) | 17,316 / 19,586 | exact |
| whole, `strict` | 17,311 / 19,586 (811 + 16,500) | 17,316 | off by 5; not used |
| natural / hard / hand, whole | 15,098 / 1,402 / 816 | 15,098 / 1,402 / 816 | exact |
| fine exact, all | **16,441** / 19,586 | 16,441 / 19,488 aligned | exact |
| fine exact, natural / hard / hand | 14,537 / 1,221 / 683 | 14,537 / 1,221 / 683 | exact |
| false-unit rows | **54** / 16,465 | 54 / 16,465 | exact |
| false-positive unit tokens | **93** / 133,047 | 93 / 132,399 | count exact |
| exact unit ownership | **1,925** / 3,121 | 1,925 / 3,060 | count exact |

**Still pending:**
- **geo-dev 59,845/60,522:** this needs the GeoSearch references in the
  framework's `geosearch-reference` intake format, Alex's
  `.cache/us-geosearch-fine-evaluation-20261029/execution-v1/dev/references.jsonl`.
- **Original unit-target 662/688 and the 543 DEV negatives:** these need Alex's
  private DEV bundle.

Neither is in `retained-baseline-v1` (its helper never reads protected
DEV/TEST references) or on this machine. When either is present, add it as a
track to the same plan, then read `delimiter_fields`, `fine_exact` and
`unit_ownership` from the run's populations.

## Per-gate status

| Gate | Field | Controls | e429 reproduced |
| --- | --- | --- | --- |
| A1 whole | pass (`delimiter`; metric changed) | pass | Doorplate exact; geo-dev and DEV pending |
| A1 unit | pass (`unit-span/v1`) | pass | Doorplate unit ownership exact; DEV 662/688 pending |
| A2 | pass (`delimiter`; metric changed) | pass | geo-dev and DEV pending |
| A3 | pass (`delimiter` + `unit-span/v1`, via compare) | pass | DEV pending |
| A4 | pass (`unit-negative/v1`) | pass | Doorplate exact; DEV 543 pending |
| C3 hard whole gains | pass (`delimiter`; metric changed) | pass | Doorplate hard 1,402 exact |
| C3 hard fine gains | pass (`fine-exact/v1`, new) | pass | Doorplate hard 1,221 exact |
| C3 false-unit rows and tokens | pass | pass | 54 rows and 93 tokens exact |
| C3 us-units-adversarial | pass (`unit-field/v1`, 103 judged) | pass | no e429 record; it is new in the paired run |
