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
