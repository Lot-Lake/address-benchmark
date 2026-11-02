# Production utility observations

Separate task profiles; no combined score. Classification uses real publisher fixtures; normalization and matching are small exposed conformance panels. Stability compares actual native API observations on 1,024 real public input strings and does not establish accuracy.

| Track | Engine | Agreements / evaluated rows | Status counts |
| --- | --- | ---: | --- |
| identity-conformance | doorplate | 9/10 | {'ok': 10} |
| identity-conformance | rust-default | 10/10 | {'ok': 10} |
| normalized-components | doorplate | 1/4 | {'ok': 4} |
| normalized-components | rust-default | 4/4 | {'ok': 4} |
| property-identity | doorplate | 8/8 | {'ok': 8} |
| property-identity | rust-default | 6/8 | {'ok': 8} |
| publisher-classification | doorplate | 19473/19586 | {'ok': 19586} |
| publisher-classification | rust-default | 19446/19586 | {'ok': 19586} |
| stability-common | doorplate | 0/1 | {'ok': 1} |
| stability-common | rust-default | 0/1 | {'ok': 1} |
| stability-stream-chunk | rust-default | 0/1 | {'ok': 1} |

Doorplate native `street` includes highway forms, whereas the publisher type fixture distinguishes `highway`; taxonomy disagreement needs review before attributing these rows to parser errors. The normalization profile is a uniform five-component projection, not native full-string postal formatting. The identity-conformance track measures delivery-unit key equality. The property-identity track uses eight independent property-level controls: Doorplate key(unit=False) versus our unchanged native comparison-key API, which retains units. Neither track measures ranked matching, clustering or geocoding.

### identity-conformance / doorplate

Distinct-pair collisions: 1; key coverage: 1.0. Ten fictional independent pair controls do not estimate real matching accuracy.

### identity-conformance / rust-default

Distinct-pair collisions: 0; key coverage: 1.0. Ten fictional independent pair controls do not estimate real matching accuracy.

### normalized-components / doorplate

Normalized component mismatches (overlapping): address_line_2: 1, address_line_1: 2.

### normalized-components / rust-default

No disagreement in this narrowly scoped panel.

### property-identity / doorplate

Distinct-pair collisions: 0; key coverage: 1.0. Eight fictional independent property-pair controls do not estimate real matching accuracy.

### property-identity / rust-default

Distinct-pair collisions: 0; key coverage: 1.0. Eight fictional independent property-pair controls do not estimate real matching accuracy.

### publisher-classification / doorplate

Class disagreements: highway → rural: 65; military → street: 36; street → unknown: 6; street → dual: 6.

### publisher-classification / rust-default

Class disagreements: highway → street: 65; military → street: 36; po_box → street: 19; rural → street: 12; street → intersection: 6; street → highway: 1; general_delivery → street: 1.

### stability-common / doorplate

- repeat: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.
- scalar_batch: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.
- idempotence: 9/1,024 changed input rows (9 distinct exact inputs); 1,024 outputs.

### stability-common / rust-default

- repeat: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.
- scalar_batch: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.
- idempotence: 4/1,024 changed input rows (3 distinct exact inputs); 1,024 outputs.

### stability-stream-chunk / rust-default

- repeat: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.
- scalar_batch: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.
- idempotence: 4/1,024 changed input rows (3 distinct exact inputs); 1,024 outputs.
- scalar_stream: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.
- scalar_chunked: 0/1,024 changed input rows (0 distinct exact inputs); 1,024 outputs.

## Coverage limits

The real parsing cohort and these utility panels do not cover every production API. Formatting from structured components, field-level helpers, source-accounting hierarchy, extraction, ZIP/state inference, diagnostics and variants have executable framework/example contracts, but still need dedicated production adapters and independently reviewed task-matched references. No production accuracy claim is made for those unmeasured surfaces. Streaming backpressure, memory, cold start and calibrated throughput also remain separate work.

Classification inputs overlap the parsing panel. Stability inputs also come from the existing public comparison workload. Do not add these counts as independent source families. Full references, predictions, native observations, exceptions and per-row decisions stay in local verified run artifacts.
