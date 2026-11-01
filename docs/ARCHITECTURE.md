# Architecture decision: small domain core, reusable measurement backends

Decision date: 2026-11-01. Status: implementation proposal v0.1.0.

Python 3.11+ is the orchestration language. JSON/JSONL are the cross-language
wire and artifact formats. The core has no runtime dependencies; optional
pyperf supplies calibrated Python callable timing, and optional installed parser
packages supply actual algorithms. Native code remains in its own runtime.

Python makes corpus/annotation review, optional package integration and artifact
inspection straightforward without forcing one compiler, dataframe framework,
test runner or cloud service. The tradeoff is Python allocation/binding overhead
in Python API timings; native decoder studies need separate Criterion/native
work contracts. A persistent JSONL command bridge supports other languages
while declaring its own serialization/pipe cost. A subprocess is not a legal
license exemption or adversarial security sandbox.

The independent layers are:

1. **Corpus admission** (`corpus.py`): manifests, asset hashes, provenance, task/
   ontology/profile compatibility, annotation coverage, family/split/exact
   overlap and input construction. Data/model rights remain independent.
2. **Input-only adapter wire** (`protocol.py`, `adapters.py`, `worker.py`): strict
   requests, native outputs and explicit capability/error states. References do
   not enter worker arguments. Rich parsing evidence stays distinct from
   inference, normalized output and identity keys.
3. **Task semantics** (`scoring.py`, `tasks.py`): address-specific field/span/
   token rules, complete/partial scope, named canonical profiles and identity/
   utility assertions. These cannot be delegated to a generic timing framework.
4. **Experiment orchestration** (`runner.py`): fresh processes, identical frozen
   panels, balanced/reversed paired orders, exits/logs, raw artifacts and hashes.
   It deliberately has no generic calibration/environment manager or cache.
5. **Measurement backends** (`tools/bench_pyperf.py` and documented external
   tools): keep native data and scope. pyperf handles calibration/process runs;
   ASV handles revision histories; hyperfine whole commands; Criterion Rust API
   studies; pytest-benchmark existing pytest workflows. Not every backend has an
   artifact translator yet. The built-in timer is explicitly exploratory.
6. **Reports and verification** (`report.py`, `runner.verify`): disjoint origin/
   split populations plus overlapping views, no overall score, per-case/role
   deltas, immutable artifact content and reproducible accuracy rescoring.

JSON Schemas document wire/manifest shape. Executable semantic validators check
hashes, spans, mappings, task identity and annotation semantics. A future standard
should publish independent implementations and compatibility fixtures, then
freeze this draft. Geocoding/search/postal verification need their own task
modules and reference semantics; no parsing heuristic is silently generalized
into those domains.

The current authored suite establishes executable contracts only. Fair claims
about production libraries require independently reviewed, legally usable
populations, source-family uncertainty, training/exposure disclosure, and matched
runtime work. No dataset, timing framework or metric removes those requirements.
