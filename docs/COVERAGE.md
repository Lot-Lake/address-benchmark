# Capability coverage and next steps

This project is an independent benchmark product and standards **proposal**.
It does not certify an existing engine or promise an overall winner. Research
informed its concepts; it owns the new contracts/scorers/authored suite. External
corpus ingestion is optional, not its purpose.

## Current address-library surface

The source library's public Python/TypeScript/Rust documentation was inspected
read-only on 2026-11-01. No implementation, model, private data or corpus was
copied. That library has parsing, normalization/formatting, classification,
inference, variants/suggestions, diagnostics and comparison keys. Its matching
surface is key generation, not a separately verified pair-classifier/geocoder.

| Capability | Executable benchmark support | Evidence/limitations in this release |
| --- | --- | --- |
| Free-text source/semantic parsing; tokenization | Ordered native evidence, fine roles/tokens/spans, partial/complete coarse scores | Nine installed production configurations on GeoSearch DEV/TEST, Doorplate v1 and expanded USA. Native coarse and fine capabilities remain distinct. Rich hierarchy/source-accounting scoring still needs upstream-specific work. |
| End-to-end normalization and field-level helpers | Exact named-profile output | Native source-library/Doorplate adapters for four complete default-profile scourgify text assertions, projected through a common five-field renderer. Field helpers and larger postal/dictionary profiles need dedicated references. |
| Formatting from components; USPS/display/mixed modes | Ordered structured inputs and exact named-profile strings | Authored line formatter. Real postal profiles need published jurisdiction-specific rules; no USPS certification claim. |
| Delivery-unit/property comparison keys | Independently labeled pairs, key stability/collisions/P/R/F1/coverage | Native source-library/Doorplate delivery-unit keys on ten independent fictional controls. No real matching population evidence. Property identity is a future distinct profile; clustering/ranked matching out of scope. |
| Classification and Boolean predicates | Exact typed output under a named taxonomy/profile | Native source-library/Doorplate classification on 19,586 publisher assertions. Highway/street granularity differs; finer taxonomies and Boolean predicates need separate review. |
| ZIP→state and other inferred attributes | Explicit typed inference task | Tiny control inventory only. No complete ZIP database, inferred-state-as-source credit or deliverability claim. |
| Variants and suggestions | Closed permitted/required output inventories, duplicates | Authored finite controls; ranked/open-ended suggestions need relevance/utility labels and separate scorer. |
| Analyze/validate and diagnostics | Exact typed assertions and native-output audit | Empty-input/deliverability-not-checked controls. Neutral diagnostic semantics need dedicated adapter mappings and independently known conditions. |
| House/street extraction | Generic exact typed extraction profile, parsing metrics when richer evidence exists | Dedicated house-number corpus; public callable supports other extraction profiles. No falsely attributed fine-role capability. |
| Scalar/batch/stream/chunk APIs | Scalar/repeat/native-batch/stream/chunk/idempotence observation comparisons | Native source-library/Doorplate APIs on a frozen 1,024-string real input panel; source-library stream/chunk is a separate supported arm. Backpressure/resource/performance contracts pending; do not equate scalar loop to native batching. |
| Bindings and repeated/upgrade stability | Per-runtime identity and repeated execution artifacts | Cross-binding and upgrade comparison backends pending. Stable wrong predictions do not imply accuracy. |
| Performance | Paired independent-process serial API pilot, optional pyperf helper | Startup wall/load audit observations only. Native batch/stream timing, memory, allocation, payload/footprint, latency percentiles and dedicated cold-start measurements pending. |
| Geocoding/search/postal verification | Extension boundaries documented | No implemented scorer, external provider call or score. |

All ten task families are executable; that does **not** mean each
native API has already been integrated and measured on representative evidence.
The authored suite has 82 rows across 12 corpus manifests; 24 are renderings of
six families. These counts are implementation/conformance scope, not independent
population-accuracy denominators. See `tools/author_corpora.py` for exact freezes.

## Standardization path

1. Freeze this proposal's wire/manifest/task semantics after independent review;
   publish semantic version policy and compatibility fixtures. MIT makes the
   original protocol/code/data straightforward to adopt; it does not license
   third-party assets.
2. Extend independently maintained production adapters to unmeasured utility
   profiles and more libraries. Native Doorplate/libpostal/Mailwoman parsing
   interfaces are integrated; their model lineage and actual installed versions
   remain explicit. Retain raw native output. No privileged local-engine path.
3. Add independently annotated, legally redistributable natural-entry data,
   geography/domain/time strata, blind adjudication, frozen source-family splits
   and exposure logs. Keep challenge/generated panels separate. Add country
   modules with local annotation/format expertise.
4. Add exact named normalization/format/diagnostic profiles and complete utility
   inventories. Add streaming resource/backpressure and binding/upgrade checks as separate operations.
5. Integrate calibrated timing-backend artifacts with verified panel/runtime/
   contract pins and actual exits. Predeclare performance studies; use dedicated
   hardware and independent process replication where publication needs it.
6. Publish capability dashboards and per-case/per-role failure distributions.
   Improvements must be trained/developed on permitted independent families,
   then checked on heldouts. Avoid gold-selected unions and universal best claims.

Before broader publication claims: review annotations, third-party license
inventory, naming/versioning and public asset contents; run CI on Linux/Python
3.11–3.13; record optional-runtime results separately. The first production
comparison publishes aggregate observations only, with exposure and task limits;
the repository contains no copied private cache.
