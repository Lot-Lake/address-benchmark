# Successor-e429 gate scoring validation receipt

**TLDR:** At `6be223fd`, every gate read whole-address `strict`, and nothing could
score unit ownership or exact fine roles. This branch adds unit-ownership
judgments (`unit-span/v1`, `unit-negative/v1`, `unit-field/v1`) and a whole-row
fine-role judgment (`fine-exact/v1`). Synthetic `run-plan` controls show that each
perturbation moves only its intended gates. The frozen scorer reproduces every
recorded e429 baseline count exactly:
- geo-dev 59,845/60,522;
- the original unit-target rows, 662/688;
- the original negatives, 537/543 exact, with 10 false-positive unit tokens;
- Doorplate whole 17,316, fine-exact 16,441, false-unit rows 54 and
  false-positive unit tokens 93.

Numerators are reproduced; the Doorplate denominators are mapped by a traced row
set. Whole-address reproduces under `delimiter`, not `strict`, so the
whole-address gates move to `delimiter`.

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
   hard whole gains. On the original DEV and geo-dev, `strict` and `delimiter` give
   identical counts. The switch changes only Doorplate's handwritten rows, which carry
   edge delimiters.
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
| A4 | `unit-negative/v1`, via `compare` | `unit_ownership.span_agrees` where `gold_unit` is false | **subset `no-unit` only** (the 543 gold-defined negatives); false-unit rows = judged − correct |
| C3 tracked hard whole gains | `delimiter` | `delimiter_fields_agree` | pinned cohort file, `min_preservation: 1` |
| C3 tracked hard fine gains | `fine-exact/v1` | `tokens` fine score: `status == ok`, `metrics.fp == 0`, `metrics.fn == 0`, no unplaced tokens | pinned cohort file, `min_preservation: 1` |
| C3 Doorplate false-unit rows | `unit-negative/v1` | as A4 | Doorplate rows labeled without a unit; `min_correct` = judged − 54 |
| C3 Doorplate false-positive unit tokens | run summary, not a gate | `unit_ownership.false_positive_tokens` / `negative_tokens`, in `summary.unit_ownership.false_positive_tokens` | ≤ 93 tokens |
| C3 us-units-adversarial | `unit-field/v1` | `unit_ownership.field_agrees` | the 103 rows that assert unit-family fields |

The unit family is the legacy one (`UNIT_ROLES` in
`experiments/us_parser/rounds/boundary_plasticity_round_20261101/unit_components.py`):
OccupancyType, OccupancyIdentifier, SubaddressType and SubaddressIdentifier, so
the coarse `unit` and `subaddress` roles. Level and PO box are outside it.

**A4 must select the `no-unit` subset.** GeoSearch's publisher ontology has no
unit roles, so `unit-negative/v1` treats every geo-dev row as a judged negative.
On e429 that gives 20 false-unit rows and 22 tokens over 60,522 rows. The legacy
cohorts exclude GeoSearch from both unit cohorts. A pooled DEV A4 would therefore
mix in a population the legacy gate never judged.

## 2. Denominators

| Corpus | Metric | Judged denominator | Source |
| --- | --- | ---: | --- |
| geo-dev | whole | 60,522 | PLAN section 5; DEV is full-scope |
| municipal-dev / seed-dev / wisconsin-dev | whole | 823 / 280 / 128 | PLAN section 5 |
| pooled DEV (A3) | whole | 61,753 | sum of the four; equals the 61,753 rows in the e429 report |
| geo-dev | whole, measured | **60,522** | regenerated references `15e9e622…0961` |
| seed / municipal / wisconsin | whole, measured | **280 / 823 / 128** | original DEV package |
| original unit-target (A1 unit, A3 unit) | `unit-span/v1`, measured | **688** (139 / 537 / 12); A1 cohort 662 | package membership |
| original DEV negatives (A4) | `unit-negative/v1`, measured | **543** (141 / 286 / 116); negative tokens 4,025 | package membership |
| Doorplate v1 | whole (`delimiter`) | **19,586** (measured) | section 5 |
| Doorplate v1 | `unit-negative/v1` | **16,465** (measured) | section 5 |
| Doorplate v1 | negative unit tokens | **133,047** (measured); 132,399 on the kept rows | section 3 |
| Doorplate v1 | `unit-span/v1` | **3,121** (measured); 3,060 on the kept rows | section 3 |
| Doorplate v1 | `fine-exact/v1` | **19,586** (measured); 19,488 on the kept rows | section 3 |
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

### Denominator mapping (traced by row, not inferred)

The numerators reproduce exactly. The denominators map onto the legacy ones through
one explicit row set:

- **The excluded set.** Doorplate rows whose gold token values differ from the
  input's whitespace tokens (`[value for value, _ in tokens] != input.split()`).
- **Size.** There are 98 such rows: 93 hand, 4 natural and 1 hard. That equals
  the legacy record's per-stratum `baseline_unaligned_rows`.
- **Same set as the e429 mismatch.** These are exactly the rows where the e429
  output token values differ from the gold token values.
- **Pinned ID set.** The SHA-256 of the sorted Doorplate IDs is
  `578da8ca375b2c76a2b425614c45dd5089e05cda399df977602b43cdd907df9a`. The IDs
  are kept privately under
  `~/data/lotlake-archives/doorplate-legacy-unaligned-v1/`.

`tools/doorplate_alignment_map.py COMPARE CASES` reproduces the split below from
the e429 run's `cases.jsonl`, printing aggregates only:

| Measure | All 19,586 rows | Excluded 98 | Kept 19,488 | e429 record |
| --- | ---: | ---: | ---: | --- |
| fine-exact rows (correct / judged) | 16,441 / 19,586 | 0 / 98 | **16,441 / 19,488** | 16,441 / 19,488 aligned |
| unit-positive rows (correct / judged) | 1,925 / 3,121 | 0 / 61 | **1,925 / 3,060** | 1,925 / 3,060 |
| negative unit tokens (false positive / judged) | 93 / 133,047 | 0 / 648 | **93 / 132,399** | 93 / 132,399 |
| false-unit rows (false / judged negatives) | **54 / 16,465** | 7 / 37 | 47 / 16,428 | 54 / 16,465 |
| whole, `delimiter` | **17,316** | 5 | 17,311 | 17,316 |
| whole, `strict` | 17,311 | 0 | 17,311 | (17,316) |

**The mapping, stated exactly:**
- **Kept rows only:** the legacy fine-exact, unit-ownership and negative-token
  measures were taken over the 19,488 kept rows. Each frozen denominator minus
  the excluded rows' contribution equals the legacy denominator: 19,586 − 98,
  3,121 − 61 and 133,047 − 648. The excluded rows contribute 0 to each
  numerator.
- **All rows:** the legacy false-unit-row measure and the whole-address measure
  were taken over all 19,586 rows. Their frozen counts match on all rows:
  54/16,465 and 17,316.
- **Why `strict` falls short:** the `strict` shortfall is 5 rows, and all 5 are
  in the excluded set. `delimiter` judges them correct.

**Consequence.** The frozen scorer judges by byte span, so it scores the 98
excluded rows instead of dropping them. On the full population the gate counts
(≤ 54 false-unit rows, ≤ 93 false-positive tokens) are unchanged. A C3 cohort
pinned from legacy ledgers must use the frozen membership. Thresholds are stated
as counts.

The exclusion rule is reconstructed from the data, not from legacy source,
which is not available here. It reproduces every legacy denominator and the
per-stratum unaligned counts exactly.

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

**Doorplate v1, geo-dev and the original DEV unit cohorts: reproduced exactly.**

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
| fine exact, all | **16,441** / 19,586 | 16,441 / 19,488 aligned | count exact; denominator mapped exactly (section 3) |
| fine exact, natural / hard / hand | 14,537 / 1,221 / 683 | 14,537 / 1,221 / 683 | exact |
| false-unit rows | **54** / 16,465 | 54 / 16,465 | exact |
| false-positive unit tokens | **93** / 133,047 | 93 / 132,399 | count exact; denominator mapped exactly (section 3) |
| exact unit ownership | **1,925** / 3,121 | 1,925 / 3,060 | count exact; denominator mapped exactly (section 3) |

### Original DEV and geo-dev: reproduced exactly

**Inputs:**
- **Original DEV:** `e429-original-dev-private.tar.gz`, SHA-256 `e6dd460d…4ba5`, 11
  members.
- **geo-dev:** GeoSearch references regenerated with the package's DEV-only
  script from the public pinned `dev.txt` (SHA-256 `a3276155…`). The script's
  helpers are us-address-normalizer `f694775` (`tests/corpora/geosearch_benchmark.py`,
  `tests/benchmark/{geosearch_bridge,fine_roles}.py`), and they match the script's
  three pins. The output is SHA-256 `15e9e622…0961`, 60,522 rows and 396,980
  tokens, all equal to the pins. The TEST split was never fetched.
- **Install:** `tools/original_dev_intake.py` installs the package as local-only
  corpora. Subsets `unit-target` and `no-unit` come from the package's
  gold-defined membership files, and every one of the 1,231 rows matched its
  membership input hash.

**Run:** one frozen 4-track plan → `run-plan` → `verify` (all 4 tracks
`verified`) with the same e429 learned-parser. Aggregates only:

| Measure | Frozen scorer | e429 record |
| --- | ---: | ---: |
| geo-dev whole (`strict` = `delimiter`) | **59,845 / 60,522** | 59,845 / 60,522 |
| unit-target exact unit ownership (seed 115/139, municipal 535/537, Wisconsin 12/12) | **662 / 688** | 662 / 688 |
| no-unit exact rows (false-unit rows 4 + 0 + 2) | **537 / 543** | 537 / 543 |
| no-unit false-positive unit tokens (8 + 0 + 2) | **10** / 4,025 | 10 |
| seed / municipal / Wisconsin whole (`strict` = `delimiter`) | 210/280, 818/823, 126/128 | not in the record; e429 is rerun paired |
| geo-dev fine exact | 59,441 / 60,522 | not in the record |

## Per-gate status

| Gate | Field | Controls | e429 reproduced |
| --- | --- | --- | --- |
| A1 whole | pass (`delimiter`; metric changed) | pass | geo-dev 59,845 and Doorplate 17,316 exact |
| A1 unit | pass (`unit-span/v1`) | pass | 662/688 exact |
| A2 | pass (`delimiter`; metric changed) | pass | geo-dev exact; seed/municipal/Wisconsin measured |
| A3 | pass (`delimiter` + `unit-span/v1`, via compare) | pass | whole and unit baselines exact |
| A4 | pass (`unit-negative/v1`, subset `no-unit`) | pass | 537/543 and 10 tokens exact |
| C3 hard whole gains | pass (`delimiter`; metric changed) | pass | Doorplate hard 1,402 exact |
| C3 hard fine gains | pass (`fine-exact/v1`, new) | pass | Doorplate hard 1,221 exact |
| C3 false-unit rows and tokens | pass | pass | 54 rows and 93 tokens exact |
| C3 us-units-adversarial | pass (`unit-field/v1`, 103 judged) | pass | no e429 record; it is new in the paired run |
