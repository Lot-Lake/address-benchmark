# Adapter protocol v1

Identifiers: `address-benchmark.adapter/v1`, `address-benchmark.prediction/v1`.
Executable semantic validation lives in `protocol.py`; v1 is a draft proposal.

A factory receives only a user-provided configuration object. Its `parse`
method is the historical method name for execution of **one declared task**;
it receives an immutable Request with exactly these keys:

```json
{"id":"case-1","text":"12 Alder St","input_sha256":"<64 hex>","country":"US","locale":"en-US","task":"parse","profile":"","other_text":null,"payload":null}
```

The runner alone sees references. Workers receive only the exported input file,
configuration and output paths; no reference/corpus path is passed. Plugins are
trusted executable code, not a security sandbox: filesystem/network permissions
could let a malicious plugin find gold. OS isolation and independent submission
custody are required for adversarial evaluation. Configuration must not contain
gold. No label-aware token alignment or reference-derived output filling.

Input identity is SHA-256 of original UTF-8 `text` for ordinary free text. Pair
identity is SHA-256 of canonical sorted compact JSON `{text, other_text}`.
Structured payload identity uses `{text, other_text, payload}`. Canonical JSON
preserves strings exactly and excludes no field of that payload. Formatting uses
`payload.fields`, an ordered list of literal `{role,value}` objects; stability
uses `payload.texts`. A pair carries the second literal input in `other_text`.
ZIPs, unit IDs and all other identifiers are strings.
Payload keys are closed to those task inputs; every other task requires null.

Metadata declares name/version, protocol, one task, ontology, mapping_version,
role_map, supported_roles, runtime, model, dependency_versions, threading,
ownership, span_support and token_support. Non-parsing tasks declare supported
profiles. `role_map` covers every emitted native role, mapping it to a registered
fine role or explicit null. Null remains visible as `unsupported:NATIVE_ROLE`.
Crosswalks are lossy policies, not claims of equivalent semantic meaning.

Every prediction carries schema, exact id/hash, `status` (`ok`, `error`,
`refused`), `native`, ordered `evidence`, native `tokens`, `inferred` and
`normalized`. Failed/refused rows have a nonempty message and no committed
evidence/tokens/keys. Preserve native audit payload even for refused outputs.

Parsed items retain `native_role`, original native `value`, and optional `spans`
(list of half-open original UTF-8 byte `[start,end]` ranges). Preserve multiple
nonadjacent ranges and repeated/nonadjacent role occurrences. Byte boundaries
must decode as UTF-8 and ranges within an item cannot overlap. Native values may
differ from source bytes (for example native casing); retain both the value and
the span. No claim of literal source equality follows from a span alone. Native
token items have one original byte span. APIs without offsets declare them
unsupported; they do not search gold or pretend normalized text has source
offsets. Source-derived alignment, if added, needs separate declared provenance.

For normalization/formatting, ordered output strings live in `normalized` and
the response repeats the requested profile. Matching has exactly two nonempty
native `keys`; the frozen equality rule generates the decision. Utility tracks
carry `result` with task-specific types. Parsing evidence is empty in these
tracks. Inferred geography, canonical strings and comparison keys never become
source parsing evidence.

## Persistent command bridge

Use adapter `command` with configuration `{command: [executable, ...args],
metadata: {...}}`. Metadata describes the underlying engine/task; the wrapper
adds its bridge scope and hashes executable/script files. Each stdin JSONL
record is a Request; emit exactly one Prediction JSONL record to stdout in the
same order. Stdout is protocol-only; diagnostics go to stderr. EOF must terminate
with exit 0. There is no shell. Nonzero exits, missing/reordered/duplicated rows,
timeouts and malformed JSON invalidate the cell and retain actual exit/logs.
Declare native model/data files through `artifact_files` in metadata.

The bridge is persistent per worker: startup is outside warmed parse timings,
while pipe/JSON request-response work is inside each call. Do not compare that
number to an unwrapped native decoder as if API work were identical.

Python specs accept built-in names, installed entry point names, or
`module:Factory`. `conform` checks structural input-only probes; the contract
test suite also covers failure semantics and scorer behavior. Neither certifies
an adapter's semantic fidelity to its upstream implementation.
