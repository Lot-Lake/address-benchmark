# Production utility tracks

These tracks are separate from the nine-engine parsing comparison. Only native
APIs supporting the requested work are selected. Unsupported capabilities are
documented, not replaced with another parser or assigned a fabricated zero.

**Classification** uses the 19,586 Doorplate publisher generator type assertions.
The frozen common taxonomy maps native `standard`→`street` and
`rural_route`→`rural`; all other native values remain visible. Doorplate's native
street enum includes highways, so disagreement with the publisher's finer
highway label is an explicit granularity limitation requiring review. No gold-
selected structural subtyping is added to make a library fit.

**Normalization** selects only complete default-profile free-text assertions
from the existing 15-case scourgify intake. Structured inputs, partial line-only
assertions and custom long-hand profiles stay in an explicit exclusion inventory.
There is no claim that a partial target is an exhaustive five-field record.
The included scope is a small exposed conformance panel, not a population
accuracy estimate.

The normalization profile requests a canonical JSON representation of five
normalized component fields. Adapters project native normalized components
through a common renderer: join native line parts, uppercase and collapse line
whitespace; preserve native ZIP strings and absence/null values. Doorplate's
separate native ZIP+4 values use a declared hyphen join. No native abbreviations,
digits, ZIP width, unit IDs or geographic facts are repaired. Native records
remain in audit output. This is **component-projection compatibility**, distinct
from accuracy of each engine's own full formatted string. JSON encoding is
canonical and reversible; it introduces no reference-derived values.

**Identity keys** use the original independent authored delivery-unit pair
controls. They are conformance evidence, not a real entity-matching population.
Doorplate is explicitly called with `unit=True`; our library uses its public
comparison-key API. Equality of those keys is judged against independently
authored same/distinct labels, never used to generate them.

**Stability** retains actual scalar, repeated, public batch, re-normalized and
(where supported) streaming/chunk outputs on the same frozen 1,024-string public
input-only panel. Common checks are repeat determinism, scalar/batch parity and
idempotence. The source library's streaming/chunk checks are a separate supported
arm. No missing native streaming API is emulated for a competitor. Stability
does not establish accuracy; null outputs and concrete changed indices remain
diagnostics to review.

Run preparation is `tools/prepare_utility_comparison.py`; source-checkout plugin
implementations are in `adapters/utilities.py`. Each track has its own JSON plan,
profiles, engine configuration, original provenance and hash-pinned derived
references. Classification and parsing views overlap the same publisher inputs
and must not be summed into an independent sample count.
