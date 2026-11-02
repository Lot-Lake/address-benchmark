# Production interfaces and real-corpus intake

Reviewed **2026-11-01** against upstream documentation/source and the previous
comparison's local manifests. These are integration facts and recommendations,
not new benchmark results. No upstream implementation, model, corpus rows or
private extract was copied for this research. The installed artifact used by an
actual run remains authoritative; a moving repository head is not a wheel pin.

## Parsing interfaces

| Engine | Public operating point | Evidence and cautions |
| --- | --- | --- |
| usaddress | `usaddress.parse(text)` | Ordered native `(token, label)` pairs. Preserve punctuation and repeated labels. `tag` is a different operation with merging and repeated-label errors. No native original-byte offsets. Pin installed CRF model/native dependency files. [Official implementation](https://github.com/datamade/usaddress/blob/main/usaddress/__init__.py) |
| fastaddress | `fastaddress.parse(text, model="v1")` | Returns the same ordered pair shape. The published binding exposes an explicit model selector; choose `v1` rather than allowing a later default change. This is a runtime implementation of the usaddress model, not independent annotation/training evidence. [Publishing-revision binding](https://github.com/vinvomero/fastaddress/blob/4ee4159fb3bae910f3857b3cffc49e4e35d1f962/crates/python/src/lib.rs), [model provenance](https://github.com/vinvomero/fastaddress/blob/main/model/PROVENANCE.md) |
| Doorplate | `doorplate.parse_tokens(text, default_state=None, custom_layer=None)` or `Parser().parse(text).to_usaddress_tags()` | Returns `list[tuple[str, str | None]]`; null labels mean unplaced native input tokens. Retain those tokens with an explicitly unmapped sentinel role. Do not silently filter them away. The Python token interface does not expose byte offsets. Rich `ParsedAddress.to_dict()` may be retained separately for audit; normalized fields and resolved `place` are not substitutions for parsed tokens. [Official type stubs](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate-py/python/doorplate/__init__.pyi) |
| polars-usaddress | `polars_usaddress.parse_address(expr)` | A Polars expression returning `list[struct{token,label}]`, retaining order/repetition. Evaluate and materialize the expression explicitly. Confidence APIs add work; keep them separate. [Python expression implementation](https://github.com/nexmoov/polars-usaddress/blob/main/python/polars_usaddress/__init__.py) |
| libpostal default / Senzing | C `libpostal_parse_address` or Python `postal.parser.parse_address` | Native ordered component/value outputs are generally coarser than street-token roles. Do not invent fine roles using gold. Separate process/model identity per model; pin the actual loaded library and data files. Expansion/normalization is another task. [C interface](https://github.com/openvenues/libpostal/blob/master/src/libpostal.h), [official Python binding](https://github.com/openvenues/pypostal/blob/master/postal/parser.py), [Senzing installation/model source](https://github.com/Senzing/libpostal-data) |
| BoundaryBoys | Existing user-installed local executable, with declared source/binary fingerprints | Public web access returns 404, while the authenticated GitHub repository query reports **private**, with no declared license. This does not make the existing local runtime missing. Do not vendor private internal Go source into this MIT project. A local wrapper can identify the already installed runtime without distributing it. Public integration rights remain unverified. [Access-controlled origin](https://github.com/Andrei-Dr/BoundaryBoys) |
| Existing learned Rust engine | Content-pinned retained model and matching native decoder/executable | The local retained manifest names an experimental learned benchmark operating point, not a production-default parser switch. Freeze its model bytes and compatible decoder before inference. If the deterministic production parser is also evaluated, give it a separate engine identity. Training/exposure limitations stay attached to both. Local `retained_model.json`, its compatible runtime manifest and the new run's file hashes are the evidence. |

The previous local matrix's Doorplate emission filtered null token labels. A new
adapter should preserve them. If compatibility with that historical metric is
also reported, name it separately and explain the changed evidence handling;
do not silently present new strict scores as a reproduction of the old table.

### Installation observations

- Doorplate's live PyPI JSON on the review date identified **0.5.0**, Python
  >=3.10, `MIT OR Apache-2.0`. The universal macOS wheel was
  `doorplate-0.5.0-cp310-abi3-macosx_10_12_universal2.macosx_10_12_x86_64.macosx_11_0_arm64.whl`,
  SHA-256 `7b33108a1aa13e4ef1d51c7451a30ad317bae04b982835928723ee10c3149df9`.
  The rendered PyPI description still mentioned an older release, illustrating
  why an exact artifact matters. [Primary release metadata](https://pypi.org/pypi/doorplate/0.5.0/json)
- fastaddress's published PyPI release was **0.1.0**, with a Python >=3.10 macOS
  ARM64 abi3 wheel and MIT metadata. Do not replace a known local artifact
  implicitly just because a repository head moved. [Release files/provenance](https://pypi.org/project/fastaddress/0.1.0/)
- No `polars-usaddress` PyPI project was found at review time. Its source build
  instructions require Rust 1.98+ and a release build. If unavailable, report an
  explicit missing runtime; do not fabricate a zero score or silently substitute
  fastaddress. Its plugin uses `POLARS_MAX_THREADS`, defaulting to one thread per
  core. Set and record one thread **before import** for a serial operating point.
  A one-row DataFrame call includes Polars setup/materialization overhead; native
  batch performance is a separate job. [Official build/thread documentation](https://github.com/nexmoov/polars-usaddress#build)

The model alphabet can contain `CountryName`, `ZipPlus4` and
`StreetNamePostModifier` beyond the upstream Python `LABELS` declaration. Admit
every actual native label through an explicit versioned mapping; in particular,
map `ZipPlus4` explicitly to postcode evidence rather than crashing or dropping
it. Intersection `Second*` labels, where a tagged API introduces them, also need
explicit mappings and preserved occurrence order. [Alphabet explanation and model notice](https://github.com/nexmoov/polars-usaddress/blob/main/python/polars_usaddress/__init__.py), [model license](https://github.com/nexmoov/polars-usaddress/blob/main/models/LICENSE.usaddress)

## Real data is several distinct evidence populations

| Population | Appropriate intake and interpretation | Rights/publication posture |
| --- | --- | --- |
| GeoSearch DEV/TEST | Existing local admitted populations contain 60,522/30,622 rows. Preserve original tokens/BIO tags and the history of joining tokens with spaces. They are synthesized/corrupted views, not a raw-keystroke mailing corpus. A publisher test split does not clear competitors' training exposure. | No upstream redistribution license was established. Use local-only resources/manifests; no raw mirror. [Primary benchmark](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark), [source reader](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark/blob/main/utils.py) |
| Doorplate suite v1 | The 19,586 rows partition into normal/hard/handwritten strata; the all row overlaps every stratum. Preserve source, styles/modifiers, original tokens and upstream field-supervision. The label `natural` names a rendered stratum, not naturally entered text. The field/format/key file shares source IDs with the parse file. | Upstream documents shipped anonymized NAD/TIGER/template/hand-shaped assets and counts-only use of private aggregate sources. Keep original notices/provenance and asset-level review; code license alone is not a blanket grant. Local intake avoids unnecessary mirroring. [Suite specification](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmark-suite.md), [frozen asset manifest](https://github.com/jeremeybingham/doorplate/blob/main/benchmarks/suite/v1/MANIFEST.md), [data policy](https://github.com/jeremeybingham/doorplate/blob/main/docs/data-policy.md) |
| Expanded USA public-fixture intake | The existing parse subset has 2,973 rows: US50/Senzing supplied-field references plus 53 complete libpostal C fixtures. Preserve each row's original completeness; do not relabel the 2,920 partial references as complete. The local kit separately has 15 normalization cases. | Local kit records US50 NCSA attribution, Senzing Apache-2.0, libpostal MIT and scourgify license snapshots/revisions. Preserve those asset chains; do not apply this project's MIT to all rows. [US50 original data](https://github.com/datamade/usaddress/tree/main/measure_performance/test_data), [Senzing public CSV](https://github.com/Senzing/libpostal-data/blob/main/files/tests/v1.2.0/test_data.csv), [libpostal C fixtures](https://github.com/openvenues/libpostal/blob/master/test/test_parser.c), [scourgify tests](https://github.com/GreenBuildingRegistry/usaddress-scourgify/blob/dev/scourgify/tests/test_address_normalization.py) |
| Private listing stress panel | Workload/error/coverage evidence only while unlabeled. Keep source identity and deduplication history, and distinguish it from accuracy populations. | No established redistribution license: no archive or raw extracts in the public repository. |

Senzing states that its full evaluation contains more records than the public
CSV because some examples lack publication permission. Count the exact public
asset actually admitted; do not inherit the full private-suite headline count.
[Publisher explanation](https://github.com/Senzing/libpostal-data#quality)

## Comparable utility APIs

**Identity:** Doorplate's `ParsedAddress.key(unit=True)` is the delivery-unit
operating point; its default `unit=False` must not silently be compared to a
unit-preserving key. Compare the existing library's native comparison keys on
independent identity labels. Style siblings can support a predeclared key
stability test, but key equality must never define same-entity gold. No equivalent
identity capability is inferred merely because a parser returns components.
[Doorplate key contract](https://github.com/jeremeybingham/doorplate/blob/main/docs/key-format.md)

**Formatting/normalization:** Doorplate exposes structured `parse_fields`,
`to_usps`, `to_display`, `to_long` and `to_reso`. Its documented Python API also
offers native batch calls. libpostal's expansions return alternatives, so they
belong in an explicitly labeled variant/set task rather than an arbitrary
single canonical output. A common postal/display profile needs independently
reviewed expected strings and explicit native capability declarations.
[Doorplate Python API](https://pypi.org/project/doorplate/), [libpostal normalization interface](https://github.com/openvenues/libpostal#usage-normalization)

**Classification/diagnostics:** compare mapped native address types or warning
conditions under a frozen taxonomy, retaining each original code. An internal
validity flag, a successful parse, or a ZIP/state inference does not establish
deliverability. Missing equivalent APIs remain unsupported cells rather than
being reimplemented by benchmark logic.

For improvement diagnosis, retain per-case/role regressions, supplied-label
scope, fine-versus-coarse distinctions and source families. Use the same panel
for all engines; separate strict punctuation/value agreement from any separately
versioned permitted-delimiter metric. Do not mistake a common projection or
annotation-policy disagreement for a demonstrated model error.

## Classification taxonomy and normalized-field follow-up

Doorplate's native `address_type()` and `to_dict()["address_type"]` use
`street`, `po_box`, `rural_route`, `military`, `general_delivery`, `dual`,
`unknown`. Its `Street` enum explicitly includes highways. A native enum-only
mapping cannot manufacture the suite's finer `highway` category. The rich
normalized `highway` object can support a separately declared structural subtype
projection, applied without reference access, or the common taxonomy can merge
highway into street for **every** engine/reference under another named profile.
Retain native `dual`/unknown outputs rather than selecting a gold-compatible
class. [Native enum and stable codes](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate/src/emit/usaddress.rs), [Python dictionary emission](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate-py/src/lib.rs)

The inspected current address-normalizer Rust `AddressType` serializes as
`unknown`, `standard`, `intersection`, `po_box`, `rural_route`, `highway`,
`military`, `general_delivery`. A versioned publisher taxonomy maps `standard`
to `street` and `rural_route` to `rural`; retain intersection/unknown explicitly.
This is the classifier operating point, not the learned sequence parser's role
output. Its Python `classify_address` returns the native `address_type` string.

The local expanded kit contains 11 scourgify **text** normalization assertions:
eight default-style and three `long_hand` assertions. Four default-style rows
assert all five fields (`address_line_1`, `address_line_2`, `city`, `state`,
`postal_code`); four default rows assert only line 1. These scopes must survive
intake. A line-1-only assertion is not complete five-field normalization gold.
Long-hand rules are a separate style/profile; no default operating point should
be silently switched after seeing the expected output.

A common, explicitly named uppercase five-field renderer can compare native
normalized components without repairing predictions: join native number/road
components into line 1, native unit components into line 2, retain native
city/state/postal values, then apply the same uppercase/space policy. Missing
secondary values become null under that profile; preserve `0`, leading zeros,
fractions and punctuation. Do not abbreviate, infer geography, or reparse a
native formatted string in benchmark code. Report this as **component-projection
normalization**, distinct from each engine's native full-string formatting.

The current library exposes `number`, `fraction`, street `prefix`, `street`,
`street_type`, street `suffix`, `unit_prefix`, `unit`, `city`, `state`,
`postal_code`. Doorplate exposes `street_number`, `street_dir_prefix`,
`street_name`, `street_suffix`, `street_dir_suffix`, `unit_type`, `unit_number`,
`second_unit_type`, `second_unit_number`, `city`, `state`, `zip5`, `zip4`, and
the native `highway` object (`state`, `prefix`, `route`, `name`). Map these native
semantic fields under an explicit renderer version. Doorplate's ordinary
`to_usps()` appends units to line 1, with line 2 normally absent; its strings
therefore do not directly implement scourgify's separate-unit-line profile.
[Doorplate field contract](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate-py/python/doorplate/__init__.pyi), [USPS line emitter](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate/src/emit/usps.rs), [scourgify source assertions](https://github.com/GreenBuildingRegistry/usaddress-scourgify/blob/dev/scourgify/tests/test_address_normalization.py)
