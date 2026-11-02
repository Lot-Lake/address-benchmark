# Real corpus intake and production comparison policy

The production parsing plan uses GeoSearch DEV/TEST, Doorplate suite v1 and the
existing expanded US50/Senzing/libpostal fixture panel. Raw data remains at its
explicit existing path; only hash-pinned local manifests and necessary derived
evaluation artifacts are created. Asset redistribution is `local-only` until its
specific provenance/terms authorize publication. The benchmark's MIT license
does not relicense any of these assets. See the research inventories for sources.

GeoSearch intake preserves publisher tokens/tags and existing original byte
offsets into its **constructed single-space input**. This is synthetic/source-
field-supervised data, not original keystroke evidence. Doorplate preserves its
original input and ordered compatibility labels; `natural` and `hard` are
publisher source-field-rendered strata. Its hand-authored cases remain a distinct
publisher-fixture origin. Its subsets are views of the all population.

Expanded records retain **2,920 partial and 53 complete** references and their
source/license/revision locators. Positive coarse assertions remain positive;
missing roles are not asserted absent. No fine spans are invented for coarse-
only references. Its shared headline must not be called whole-address accuracy.

Upstream independent source-family IDs are unavailable for these intakes.
`family` is therefore an explicitly named **exact-input proxy**, not evidence of
independent sampling. Rendered siblings and geographic overlap may remain. Do
not bootstrap row counts as independent families or claim unseen training
exposure from a publisher split. Cross-split exact overlap is audited separately.

## Ontology and metrics

`address-benchmark.us-roles/v2` adds named `us:NativeLabel` fine roles to preserve
prefix/suffix/directional/type distinctions that the v1 demonstration crosswalk
folded. Public native output remains intact. Coarse aliases (such as libpostal
`house`→`building`) are explicit in `ontologies.py`; they are interoperability
policies, not proofs that every source convention has the same semantics.
The default source API's generic `name` stays `name`; it is not promoted to a
recipient or building. `active_roles` separately records the loaded model/API
inventory where known, so a broad crosswalk does not imply that a particular
model supports every mapped role. Unsupported coarse/fine reference roles remain
explicit diagnostics and are not removed from eligible denominators.

The original punctuation-preserving `casefold-whitespace/v1` result remains the
primary strict field score. An additional, uniformly applied
`casefold-whitespace-edge-delimiters/v1` diagnostic strips component-edge commas,
semicolons and colons only. This permits comparison with the prior local
coarse-value policy while preserving periods, accents, abbreviations, ZIP widths
and internal punctuation. Both scores derive from the same untouched native
predictions. There are no engine-specific answer repairs.

Fine token/span-role scores use original native tokens with conservative exact
sequential **input-only** source alignment where an API has no offsets. These
are explicitly adapter-derived spans. Unresolved pieces stay unresolved and
retain missing-span diagnostics. Coarse-only APIs (libpostal, BoundaryBoys,
and default semantic components) cannot acquire
fine role support by consulting gold; their fine token scores are unmeasured.

The retained learned Rust model and the default deterministic source parser are
separate columns. Models, native extensions, executables, shared library/model
files, installed dependency assets, public API options and actual exits are
pinned. Existing predictions/scores are not reused as fresh measurements.
BoundaryBoys is an authorized local private runtime with no established public
code redistribution grant; only the generic executable bridge is published.

Production timing needs a separately frozen input-only panel and matched API
work. Accuracy execution wall time includes hashing/loading/I/O and is not parse
throughput. The first full plan is accuracy-only; do not rank its process wall
times as implementation speed.
