# Scorecards and clean exports

`address-benchmark.scorecard/v1` is a presentation model over recorded run
aggregates. It has one ordered engine list and dataset/view rows with cells
keyed by engine ID. Missing engines never shift columns. Display aliases change
labels only; original panel/view IDs remain in JSON. No raw input, reference,
native output, runtime file inventory or host path is copied into this model.

Each cell retains status, score, correct/denominator, reference row count,
errors/refusals and actual engine exit when available. Fine F1 additionally
retains TP/FP/FN. Score units are fractions for agreement/F1 and addresses per
second for throughput. JSON retains full precision; display percentages round
to two decimals. A measured zero is distinct from unavailable, failed, invalid,
timeout, incomplete and unmeasured cells.

Only disjoint origin/split `/all` aggregates are combined for a dataset row.
Requested subset views are separate rows, never added to the dataset total.
Unknown/duplicate subset names are rejected. Partial field references use the
original supplied-field denominator. Complete-address scores use only complete
references. Non-parsing tasks default to their own exact profile agreement.
Fine F1 pools complete-reference TP/FP/FN; unsupported/partial-only fine output
does not acquire a fabricated F1.

Bold/color row leaders require at least two measured cells with matching
denominators. Display-rounded ties are all highlighted. This is a per-row
visual aid, not a combined winner or an engine-selection strategy.

`throughput` requires at least two recorded successful timing trials for each
measured engine and uses `1e9 / median(trial median ns/address)`. Missing or
failing trials produce an incomplete cell. Accuracy-process wall time is never
used. A dagger marks a recorded sample spread above 10%. Whole-panel timings
cannot be attributed to subset rows. These exploratory rates inherit the
recorded public API/measurement scope; exports add no calibration claim.

The console renderer groups columns to fit terminal width, supports ASCII,
sanitizes labels and disables automatic ANSI color in redirected output,
`NO_COLOR` and dumb terminals. Markdown and HTML highlight the same leaders;
HTML includes counts and a scrollable table with sticky labels. CSV is a readable
matrix with count-bearing cells; JSON is the precise structured alternative.

New runs export `scores.txt`, `scores.md`, `scores.csv`, `scores.json` and
`scores.html` before hashing the immutable artifact envelope. Their source
content ID is null because the containing envelope does not yet exist; the
containing `run.json` supplies it. Plan exports can include completed child run
IDs. The `report` command checks recorded envelope identities and plan links,
then renders aggregates without execution or rescoring. Full verification of
older predictions requires their original frozen framework version.

The report command accepts multiple explicit run/plan sources and includes
their dataset rows without pooling them. Dataset IDs must be unique and tasks /
scorer policies must match. Named subsets are checked against the combined
population inventory. `--all-views` selects every recorded subset except the
redundant `all` subset; it is mutually exclusive with named subset selection.
Source content identities and creation timestamps stay separate in JSON.
Composition never supplies a missing execution result or establishes a single
contemporaneous cohort. Unsupported or absent engine cells remain explicit.

## Aggregate-only publication boundary

`report SOURCE --publishable --format json --out PUBLIC.json` explicitly selects
the publication allowlist. It retains the normal scorecard plus `aggregates`:
per-source whole/field/fine/token counts and denominators, unit/building/recipient/
road-city effects, paired gains/losses, supplied-cohort preservation counts,
paired speed uncertainty and explicit unexecuted statuses. Equal-sized v2
judgment sets with different membership are marked noncomparable and cannot
produce a highlighted row leader; private membership pins are not exported. Other formats render
the corresponding safe scorecard; JSON carries the detailed aggregates.

The projection reconstructs numeric metrics, fixed status/policy enums and
positional aliases. It does not copy free-text engine, corpus, source, subset,
cohort or plan names, user titles, provenance, runtime inventories, error messages,
raw inputs/references/native output, private row/family identifiers, input hashes,
local paths, or token-level examples. This also applies to publication console
output and its failure diagnostics. Aliases are positional within each export;
only the private audit provides their mapping. This is aggregate publication,
not differential privacy or a statistical disclosure guarantee for tiny groups.

Local-only runs/plans automatically apply this boundary to all `scores.*` files,
`report` formats and default console output. Their `--json` completion output
contains status only; progress uses fixed track aliases. Full `run.json`,
`report.md`, references, inputs, native outputs/errors/refusals, model/runtime
identities, logs and paired identities remain private. Do not publish that
execution directory. Local-only execution directories are created with mode
0700. `verify` independently rescores cases, source metrics, paired gains/losses,
cohort counts and gate decisions with the pinned framework, besides checking
artifact hashes. Integrity is not a cryptographic author signature.

## Publication policy v2

Aggregate-only exports now default to `min_denominator: 20`, recorded in
`publication_policy`. A measured cell below that threshold becomes `suppressed`
with no score, numerator, denominator, row/error/refusal counts or fine metrics.
Detailed source, fine-layer/role, effect and preservation-cohort summaries apply
the same rule; fine-layer thresholds use annotated reference rows rather than
letting many tokens in a tiny input set bypass suppression. Small gate scopes
publish no numeric decision details. Gate pass/fail remains an explicit status.
Unavailable and unmeasured results remain distinct and expose no numeric counts.

`report --min-denominator N` selects another positive threshold and records it.
Use an explicit threshold of 1 only when publishing authored synthetic controls
or when your publication policy permits it. Private full audits are unchanged.
This threshold is not differential privacy or protection against arbitrary
repeated-query differencing, and does not establish independently held-out data.

Panel/source/view/cohort aliases now share one registry. Panels number once;
views number within each panel; resource sources follow frozen declaration/first
occurrence order; cohorts follow declaration order, never sorted private IDs.
Detailed aggregates use the same panel namespace as the scorecard. All formats
include gate-status notes. CLI failures use fixed reason codes such as
`output-exists`, `asset-unavailable`, `frozen-assets-differ` and
`cohort-baseline-pin-mismatch`; even `verify` never prints exception filenames.
