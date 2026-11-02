# Parsing scoring profiles

A scoring profile is a named, versioned field policy that a parsing corpus opts
into with `"scoring_profiles": ["strict-streetline/v1"]` in its manifest. It is
scored **in addition to** `address-benchmark.scorer/v1`; strict, delimiter and
fine scores are unchanged, and a corpus that declares no profile produces the
same records as before. Each case carries `profiles.<name>` (`agrees`,
`scored_fields`, `mismatched_fields`, `inferred_roles`), each population carries
`profiles.<name>` (`correct`, `denominator`, `rate`, `inferred_state_rows`), and
`report --metric streetline` renders it. Changing any rule or table needs a new
version.

## strict-streetline/v2

Opt in with `"scoring_profiles": ["strict-streetline/v2"]` and report with
`report --metric streetline-v2`. Both versions may be declared together.

V2 uses the same six fields, canonicalization, reference coverage and inference
rules as v1. It changes only street-line assembly: road components retain their
source order instead of being grouped into pre-directional/name/suffix/post-directional
slots. This preserves internal directionals and pre-types, such as
`OLD SOUTH PLANK ROAD` and `N AVENUE A`.

Complete fine reference spans are ordered by their input byte offsets. Coarse
reference road values retain their supplied order. Prediction road evidence is
ordered by its own earliest input span when every road item supplies spans;
otherwise its native evidence-list order is used. Spanless adapters must emit
road evidence in source order for this profile. No reference values or spans
repair or reorder a prediction. Other fields retain v1 assembly behavior.

V1 remains available with its published fixed-part assembly. Existing manifests
and recorded v1 scores are unchanged; selecting v2 does not relabel or rescore an
old run. A report without recorded v2 results shows that metric as unmeasured.

## strict-streetline/v1

Six fields, built from parsed **evidence** only, through the native → fine →
coarse mapping the adapter declares:

| Field | Coarse roles |
| --- | --- |
| number | house_number |
| streetline | road |
| unit | unit, subaddress, level, po_box (in source order) |
| city | city |
| state | state |
| zip | postcode |

Other roles (recipient, building, country and so on) are not scored.

**Street line.** The pre-directional, street name (with any pre-type or
modifier), street type and post-directional are compared as **one** string, in
that order. Where an engine draws the boundaries inside the line does not
matter: `N | Main | St` and `N Main St` agree. A neutral `road` role is the whole
line.

**Scope.** A complete reference scores all six fields; a field the reference
lacks must also be absent from the prediction (no invented fields). A partial
reference scores only the fields it supplies; an empty supplied list asserts
that the field is absent. Unlabeled rows and partial references supplying none
of the six profile fields are unmeasured and excluded from its denominator.
Error and refusal rows fail when at least one field is eligible.

**Inference.** A ZIP-derived (or otherwise inferred) state belongs in the
prediction's `inferred` layer. It is never source evidence, so it cannot satisfy
or fail the `state` field. Rows with an inferred state are counted separately
as `inferred_state_rows`.

**Canonical form**, applied identically to references and predictions:

1. Uppercase; drop periods and apostrophes; every other character outside
   `[A-Z0-9/#&]` becomes a space; collapse whitespace (`CR-594` → `CR 594`,
   `M.L.` → `ML`).
2. Per-field USPS Publication 28 folds (`src/address_benchmark/pub28.py`):
   - street line: written route forms first (COUNTY/CNTY/CO ROAD → CR,
     US HIGHWAY/HWY/ROUTE → US, STATE ROUTE/ROAD → SR, STATE HIGHWAY/SH → SH,
     INTERSTATE/IH → I), then token by token SAINT/FORT/MOUNT → ST/FT/MT,
     Appendix B directionals (NORTHWEST → NW) and Appendix C1 suffixes
     (AVENUE → AVE). The token-wise fold also applies to tokens a route fold
     produced, on both sides alike.
   - unit: P O BOX/POST OFFICE BOX/POB → PO BOX; RURAL ROUTE/RFD → RR;
     HIGHWAY CONTRACT/STAR ROUTE/HCR → HC; `#` dropped; Appendix C2 designators
     token by token (APARTMENT → APT).
   - city: SAINT/FORT/MOUNT → ST/FT/MT and Appendix B directionals.
   - state: Appendix B state name → two-letter code.
   - zip: digits only; the first five; a four-digit value is zero-padded
     (the spreadsheet-loss form).
3. Equality compares the canonical tokens joined **without** spaces
   (`W 615` = `W615`, `APT 4 B` = `APT 4B`). Field boundaries between the six
   fields still count.

The tables are Pub 28 Appendices B, C1 and C2 plus the `observed` real-world
spellings recorded in Doorplate's Pub 28 data (for example FLR → FL), so an
engine that normalizes a common non-Pub 28 spelling is not marked wrong against
a reference that kept it. See NOTICE.

This profile is a comparison policy, not postal standardization or validation:
a canonical agreement says two strings name the same parsed field under these
folds, nothing about deliverability.
