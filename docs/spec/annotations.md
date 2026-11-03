# Annotation and corpus policy

## Authored v1

All bundled cases are newly authored, fictional, development-exposed controls.
No input claims a real deliverable location. A lexical case does not establish
population coverage, natural-entry frequency or unseen generalization. Core and
challenge strings are composed and manually assigned token roles; emitted byte
offsets are calculated from those literal annotations, not a parser's output.
Ambiguous constructions use explicit fixture policy and need independent review
before broader accuracy claims.

Commas separating address groups and inter-token whitespace are delimiters and
are not annotated tokens. Periods inside token values are significant. Every
non-delimiter token in a complete case is labeled under the v1 fine inventory.
Spans in this suite are lexical source-role segments, not BIO entity extents.
Tokens use this authored lexical segmentation. The source text retains all
punctuation and whitespace. Coarse fields join adjacent same-coarse-role values
with one space; nonadjacent repeated occurrences remain separate ordered values.
This field projection is not a reconstructed literal source substring.

Partial parsing references enumerate the full ordered occurrence list for each
supplied coarse role. Other roles remain unknown, not absent. Fine partial
references are positive labeled spans only; they cannot establish precision or
F1. Unlabeled rows support workload/error reporting only, never accuracy.

`us-rendered` explicitly contains **24 source-field-supervised views from six
families**, in a separate origin from authored cases. Upper/lower/doubled-space
variants share family identity. These controls are not independent naturally
entered observations. Authored ZIP/state/place combinations are fictional,
except the tiny explicitly named ZIP/state inference controls; no geographic
consistency/deliverability inference is implied by a parsing gold label.

Identity controls independently assert same/distinct delivery units, preserving
units, directional and postcode contrasts. Leading-zero width and accents are
distinguishing properties in this fictional policy. Those rules do not establish
universal real-world entity identity. Never define matching gold by comparing
the submitted keys. Normalization/format profiles specify requested rendering;
they do not claim one universal canonical address representation.

## External and private corpora

Manifest v1 fields: schema/id/version; source provenance/revision/content hashes;
asset-specific license and `allowed`/`local-only` redistribution; construction
history; country/locale/task/ontology/profile; annotation policy/coverage;
split/family policy; exposure status/history; resources with safe relative paths,
SHA-256 and optional byte size/HTTPS URL. See executable checks in `corpus.py`.

Rows require globally unambiguous source-family identifiers, split, explicit
origin (`natural`, `authored`, `generated`, `source-field-supervised`) and subset
membership. Do not call a generator's “natural” style naturally entered without
upstream sampling evidence. Country/locale and profile are corpus-wide in v1.
Additional locales need their own reviewed role/normalization profile; this v1
runner admits US profiles only and rejects unsupported task/ontology pairs.

Resource hashes must match before any execution. Exact text/pair/structured
identity and declared-family overlap are audited; exact/family cross-split
leakage is rejected. Subset intersections are reported, not added into a sample
total. Source-family names are globally namespaced by authoring policy; the tool
cannot prove a contributor chose correct family IDs. Exact matching cannot
clear fuzzy/geographic or unknown competitor-training overlap. Freeze independent
heldouts, membership/exposure logs and annotations before model selection.

`fetch` is opt-in, hash-pinned, HTTPS-only, size-limited and refuses overwriting
existing mismatched resources; it does not execute plugins or extract archives.
Unknown rights mean no bundled/downloadable raw asset. A local-only manifest is
useful without granting public redistribution. Do not publish private run inputs
or labels merely because the benchmark's code has an MIT license.

## Publisher delimiter fidelity

The `doorplate-compare` reader retains publisher token values and exact source
spans, including component-edge delimiters. This is an annotation property, not
an instruction to make parsers copy a comma. The versioned [reporting audit](scorecards.md#publisher-edge-delimiters-and-strict-comparability)
marks affected strict cells non-comparable and points to the existing edge-
delimiter view. Original corpus revisions, scorer policies and historical
artifacts remain intact; no corrected corpus or silent reference repair is added.

## Source-scoped evaluation (scorer v2)

Opt in with `"scorer": "address-benchmark.scorer/v2"`. Omission retains v1;
previous envelopes require their original frozen source for verification. The
v2 policy reuses v1 field normalization, fine matching and delimiter policy. It
adds source scope and capability eligibility, rather than a second scorer.

Every resource declares `source` (optional private name, default resource ordinal)
and `annotation_scope` with `fields`, `tokens`, `spans`. Each layer has:

- `coverage`: `complete`, `partial` or `none`;
- `roles`: coarse roles for fields, fine roles for tokens/spans;
- `absence`: whether the source can assert absence.

A complete source layer enumerates the entire registered role inventory and
supports absence assertions. A partial field layer provides complete ordered
occurrence lists for its supplied roles. Partial fine layers provide positive
labels only and cannot assert absence. A none layer supplies neither roles nor
absence assertions. The semantic validator checks role inventories beyond the
JSON Schema shape. See `tools/prepare_scoped_example.py` for executable examples.

The three layers are independent in v2: token/span annotations can remain measured
when coarse field coverage is none. Use `annotation_scope` rather than the legacy
resource `coverage` override.

Source scope is a ceiling: it downgrades a row's complete layer to partial or
none, never upgrades partial to complete. References outside the source role
inventory and empty field assertions without source absence support are rejected.
The effective scope and source identity stay with the private frozen references;
they are never passed to adapters. Predictions outside partial scope remain
unjudged. Fine partial precision/F1 are null; positive-label recall is separate
from complete fine metrics. Unsupported positive fields remain misses; an
unsupported empty-field assertion is unjudged and cannot establish correctness.
Inactive fine mappings cannot earn true positives. Derived streetline profiles
also remain unjudged when their absence claims exceed adapter capabilities;
the versioned profile transformations themselves are unchanged.

Resources are summarized separately by declared source (equal source names group
resources), including complete/supplied-field denominators and full versus partial
fine/token metrics. Unit, building, recipient and joint road/city agreement have
separate eligible denominators. A joint road/city effect requires both assertions.

`preservation_cohorts` is an optional manifest list of objects with `id`, `row_ids`
and an independently supplied `basis`. Membership is validated before execution
and frozen with the manifest. Reports retain the supplied denominator, each
engine's correct and unjudged counts, and joint retained count. Candidate failures
never create, remove or replace preservation anchors. Exposure status/history
remain private audit evidence: excluding data from training does not establish
blindness when development exposure or custody is unresolved.
