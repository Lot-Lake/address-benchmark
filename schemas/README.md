# Versioned shape schemas

Draft 2020-12 JSON Schemas document portable request, prediction and manifest
shapes. Runtime core dependencies remain empty: `protocol.py` and `corpus.py`
perform executable admission checks, including identity, ontology/task/profile,
UTF-8 byte boundaries, file hashes, path safety, coverage and stream semantics.
JSON Schema alone cannot establish those properties or semantic correctness.

The wire is a v1 proposal. Breaking semantic changes require new identifiers;
additive audit metadata may coexist in response/manifest objects. Request keys
are closed so gold/reference data cannot be silently added by the harness.
