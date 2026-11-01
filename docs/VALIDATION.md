# Local validation record — 0.1.0

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
