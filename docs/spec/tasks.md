# Task and scoring contracts v1

There is no combined “best address library” number. Choose the required
capabilities/population first, compare their independently measured cells, and
keep unavailable/unsupported cells visible. New task/rule/profile meanings need
new versions. Geocoding, deliverability, ranked search and clustering are outside
this executable release.

## Parsing

`address-benchmark.scorer/v1`, normalization `casefold-whitespace/v1`.
The one shared policy case-folds and collapses whitespace only. Punctuation,
diacritics, abbreviations, leading zeros, unit markers and identifier widths are
significant. No USPS repair, ZIP padding, geographic lookup or engine-specific
substitution occurs. Evidence is projected through the declared native→fine→
coarse mapping. Adjacent same-coarse-role items join with a space; nonadjacent
occurrences stay separate and ordered. Unsupported roles remain visible.

Supplied-field agreement judges all and only supplied coarse roles on partial
references. Complete-address agreement judges both reference and prediction
roles only when annotations are complete. Errors/refusals fail eligible rows.
Extra roles on partial rows remain unadjudicated diagnostics. Unlabeled rows
have null agreement, not a fabricated failure or success.

Fine span/token metrics count exact `(fine_role,start_byte,end_byte)` multisets.
Role errors and segmentation differences create FP/FN. Component segments may
have multiple source spans; each segment is one scoring atom. Token predictions
must retain the native token segmentation and one source span. Complete fine
annotations support micro precision/recall/F1 and per-role counts. Partial fine
annotations support positive-label recall only; precision/F1/FP are null and
extra observations are unadjudicated. No-span/token capability is unmeasured,
with explicit unsupported-row counts; it is not a score of zero. Supported
capabilities with missing spans incur missed reference labels and diagnostics.
Zero denominators produce null. Coarse success never implies fine-role success.

## Normalization and formatting

`normalized-text-exact/v1` compares ordered output strings exactly under the
named corpus profile. There is **no scorer normalization of canonical output**.
The bundled uppercase/whitespace profile and field-line profile are intentionally
small controls, not postal standards. Structured formatting uses literal ordered
input fields; a scalar parser cannot silently stand in for field formatting.
Free-text end-to-end normalization includes parsing if the public API does it;
record that in its work contract. Field-level normalizers can use the same
normalization task with a different named profile and corpus.

## Identity/matching keys

`identity-key-equality/v1` evaluates exactly two native keys against independent
same/distinct delivery-unit labels. Same-pair recall measures stability; distinct
key collisions are false positives. P/R/F1 describe this authored pair population,
not deployment prevalence. Missing/refused/error keys fail exact agreement and
same-entity recall; undecided negative pairs are counted separately and cannot
become true negatives. Report key coverage. No threshold tuning or property/unit
level switching after seeing gold. This is not ranked matching/search or entity
clustering. Those require separately labeled candidate populations/relevance.

Property-level identity (`entity_level: "property"`, profile
`address-benchmark.property-key-equality/v1`) labels pairs at the property
(building/parcel) level: units of one building are the same property. Each pair
names both entity identifiers (`entities`), which must agree with the label. The
same pair rule applies, and the match summary adds `property_keys`: properties,
distinct keys per property (1 is ideal; `fragmented_properties` counts the rest),
`false_merge_pairs` (distinct-property pairs with equal keys), `colliding_keys`
(keys any two different properties received anywhere in the population) and
missing key sides. It describes the labeled pairs, not deployment prevalence.
Delivery-unit corpora and their results are unchanged. Example:
`examples/corpora/us-identity-property`.

## Utility tracks

- **Classification/extraction/inference/diagnostics** use `typed-json-exact/v1`: compare
  exact typed task output under a frozen taxonomy/profile. JSON `false` differs
  from numeric `0`. Inference never becomes parsing evidence. Diagnostic controls
  keep deliverability `not_checked`; an engine's internal validity flag is not
  postal authority. New neutral code mappings require versioned adapter policy.
- **Variants/suggestions** use `variant-inventory/v1`: required coverage,
  proposals outside a declared closed permitted set, and duplicate counts.
  Ordering is not judged in this track. A genuinely partial/open inventory needs
  a future positive-only scorer; v1 rejects partial utility references.
- **Stability** uses `stability-observations/v1`: independently compare retained
  scalar/repeated/native-batch/stream/flattened-chunk/normalized-twice arrays for
  equality, order and length. Freeze required checks before execution: repeat
  determinism, scalar/batch parity, scalar/stream parity, scalar/chunk parity and
  idempotence are supported. Record actual outputs rather than adapter-reported pass flags.
  No gold accuracy follows from stable wrong outputs. Cross-binding and
  cross-version parity require separate native configurations and are not
  implemented in this track yet.

Every task keeps source-family counts distinct from row/label counts. Reports
split by input origin and split, expose overlapping subset views, retain all
statuses, and publish per-case comparative deltas. There is no gold-selected
“best engine per row” ensemble claim.
