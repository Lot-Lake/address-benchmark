# Validation records

## Active parsing cohort — 2026-11-02

The retired integration, native role mapping, bridges and setup requirements
were removed. The guarded suite passed **152 tests** (exit 0). Demo conformance
and all 14 authored corpus manifests passed. Production preparation generated the
eight retained configurations with the retired command absent from its input
runtime ledger. The latest eight-column exports preserve every displayed cell
score and denominator from the original recorded scorecards. No parser rerun or
rescore was performed for cohort selection. Historical reports and their original
cohort counts remain unchanged. See the [active cohort](results/2026-11-02/active-cohort/README.md)
and its presentation/validation records.

## 0.3.0 — console tables and scorecard exports

GitHub CI [run 41355268079](https://github.com/Lot-Lake/address-benchmark/actions/runs/41355268079)
passed **94 tests** on each of Python 3.11, 3.12 and 3.13, plus installed-package
smoke checks. Production-code commit: `0db8e37`. The thirteen new tests cover
weighted populations, overlapping subsets, partial eligibility, zero versus
missing scores, denominator-aware row leaders, fine F1 counts, narrow/Unicode
terminal output, control characters, HTML escaping, CSV quoting, source-data
exclusion, incomplete timing, changed envelope identities, path traversal,
column stability, CLI export behavior, automatic hashed exports and clean JSON
stdout for plan execution.

The first CI attempt exposed an incorrectly constructed test fixture: two
denominators intended to differ were equal. The fixture was corrected and all
three CI jobs passed. The local guarded suite never acquired the shared slot;
only our queued guard was interrupted (actual exit 130, no test child launched).
Other owners' workloads were preserved. No local test-pass claim follows.

Strict and edge-delimiter tables were generated separately from the complete
v0.2 production plan's recorded aggregates. No parser/model was rerun and no
prediction or score policy was changed. Original run envelope identities were
checked; full artifact rehash/rescoring remains the original framework's `verify`
operation. The [published table samples](results/2026-11-01/tables/delimiter/scores.md)
contain aggregate scores only.

Standalone HTML markup, data and escaping were exercised by tests. An attempted
browser preview of the local HTML file was rejected by the browser URL policy
(only HTTP/HTTPS permitted); visual browser verification was not completed.

## 0.2.0 — real-corpus production comparison

Executed on 2026-11-01 on macOS through the shared host workload coordinator.
The full driver froze this project's framework/adapter/recipe source before
execution; source, model and corpus assets in the existing library checkouts
were read in place. No other owner's process was stopped.

| Check | Actual result |
| --- | --- |
| Unit, contract and subprocess integration suite | **81 tests passed**, exit 0 |
| Full JSON parsing plan | **36/36 cells complete**, exit 0 |
| Parsing rows / fresh predictions | **113,703 / 1,023,327** |
| Parsing adapter errors / refusals | **0 / 0** |
| Artifact rehash and accuracy rescore | All four tracks verified |
| Separate utility plans | All five complete, actual exits 0; all artifacts verified |
| New runnable JSON example | Both tracks complete and verified, exit 0 |
| Aggregate parsing and utility reports | Generated successfully, exits 0 |
| GitHub CI at production-code commit `59fe82a` | Passed on Python 3.11–3.13, including package smoke checks |

See the [aggregate findings](results/2026-11-01/findings.md),
[parsing comparison](results/2026-11-01/comparison.md), and
[utility observations](results/2026-11-01/utilities.md). Full runtime/file
identities, native outputs, references, actual exits, logs and case decisions
remain in ignored local run folders. No external corpus/model/private runtime
bytes are included in the public repository.

Complete/verified means the benchmark executed and its artifacts rescore; it
does **not** mean a library satisfied every assertion. In particular, our native
normalization changes on a second pass on 4/1,024 input rows (3 distinct strings).
Scalar/repeat/batch/stream/chunk observations agree on the same panel. Real
normalization and matching references are small exposed conformance controls.
These runs do not establish unseen accuracy or calibrated parsing throughput.

Earlier failed/interrupted attempts remain separate local artifacts and are not
pooled into these results. These historical runs used frozen framework source and fresh native execution;
worker details remain in their linked historical reports.
The report generator was also corrected to allow regenerating its aggregate
JSON export; the successful rerender did not change any immutable run artifacts.

## 0.1.0 — initial framework release

Executed on 2026-11-01 with Python 3.12.8 on macOS, through the host workload
coordinator. The existing address-normalizer workspace and other owners' jobs
were not modified or stopped.

| Check | Actual result |
| --- | --- |
| Unit, contract and subprocess integration suite | **62 tests passed**, exit 0 |
| All 12 authored corpus freezes / cross-corpus overlap audit | Validated, exit 0 |
| Every utility track in separate adapter processes | Passed in integration suite |
| Paired independent-process timing / reversed order | Completed, exit 0 |
| Rehash and accuracy rescore of timing run | Verified, exit 0 |
| Optional real usaddress adapter on original challenge suite | Completed, exit 0; native outputs retained |
| Rehash and rescore of optional adapter run | Verified, exit 0 |
| Optional pyperf helper with native JSON and runtime-pin sidecars | Smoke run completed, exit 0; instability warnings retained |
| Installed package, isolated Python import and conformance probes | Passed, exit 0 |
| Public-source-only staged tree / whitespace check | Passed; no run caches/private data included |

The optional environment resolved address-benchmark 0.1.0, pyperf 2.10.0,
usaddress 0.5.16, python-crfsuite 0.9.12, probableparsing 0.0.1 and psutil 7.2.2.
Run artifacts retain installed distribution/model file hashes; these versions
are a validation observation, not a global dependency lock for future users.

The pyperf invocation deliberately used only two processes, two values and one
loop to test integration. Its warning about insufficient samples/short values
was retained. It is **not** a calibrated publication-quality performance result.
No shared-machine system tuning was applied. No production-library leaderboard,
unseen-training claim, population accuracy estimate or 100% utility claim follows
from this record.

Meaningful failure probes include reference leakage through request keys,
UTF-8 boundary corruption, repeated/nonadjacent evidence, partial/unlabeled
denominators, unsupported spans, key collisions, missing negative decisions,
variant unit mutation, stream/chunk tail/order errors, changed model files,
tampered predictions/reports, missing runtimes, malformed/early command exits,
actual timeout exits and incomplete timing pairs. Download tests use authored
bytes/mocked HTTPS and verify hashes, size limits and another owner's temporary
file preservation.

Reproduce the local release checks with:

```sh
python3 tools/validate_release.py --optional --out work/my-fresh-validation
```

Use your host's workload coordinator for that outer command. Optional packages
are installed in the named work directory; authored core CI needs no third-party
parser runtime, dataset or model. The CI matrix covers Linux Python 3.11–3.13;
its remote result is tracked by GitHub Actions separately from this local record.
