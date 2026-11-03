# Private local evaluation integration checks

Issue #11 extends the existing corpus, plan, scorer, runner and scorecard APIs.
These observations are synthetic integration evidence, not natural-population,
blind accuracy, model selection or production speed evidence.

- All 166 offline regression tests passed locally on Python 3.12.8. They include
  source scope, independent field/token/span coverage, inactive-role and absence
  eligibility, private native errors/refusals, paired identities, supplied-cohort
  denominators, privacy across every export format and publication console,
  frozen asset drift, accuracy gates, and four-pair speed uncertainty.
- All 14 authored corpus manifests validated; demo adapter conformance and the
  existing two-track authored example plan passed.
- The new synthetic local-only plan completed and its private audit verified:
  two complete and two partial field references, a refusal, one paired gain and
  one paired loss, two independently supplied preservation members, separate
  source metrics and positive-only partial fine recall.
- A fresh frozen plan evaluated the already completed external learned parser
  supplied for [us-address-normalizer commit
  0368c8427686d4a691eac3c4c3487b723b3466dc](https://github.com/Lot-Lake/us-address-normalizer/commit/0368c8427686d4a691eac3c4c3487b723b3466dc)
  on four synthetic inputs. The supplied binary/model hashes matched the local
  package validation, execution completed, and the native-output/private audit
  verified. No training, source acquisition, checkpoint selection, prior-output
  reuse or score tuning occurred. No private runtime/model assets are published.
- An isolated package installation and installed CLI conformance/corpus smoke
  checks passed. CI additionally runs the synthetic frozen-plan CLI workflow on
  Python 3.11, 3.12 and 3.13 alongside the full offline suite.

The completed candidate's native-batch interface does not implement warmed
scalar timing. Speed was not requested for that integration check. Existing
paired performance facilities were exercised by synthetic input-only controls;
all process trials, reversed orders and the conditional bootstrap were retained.
A failed accuracy gate was separately shown to launch neither timing processes
nor the subsequent public track. Skipped measurements remain explicitly
unexecuted.

The full frozen plans, input/native/error records, runtime/model pins, paired
identities and audit envelopes stay local. Only allowlisted aggregates may be
published. Scorer v1 and historical results keep their original interpretation;
source-scoped semantics require explicit scorer v2. Doorplate delimiter policy,
verified result reuse and retired integrations are outside this change.
