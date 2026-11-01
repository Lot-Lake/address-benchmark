# Contributing

Start with the task, country/locale, input mode and output work. Propose a corpus
or adapter using the v1 contract; keep changes to ontology, normalization,
profiles and scoring versioned. Existing results retain their original policy.

Adapters must never inspect references or repair outputs using gold. Preserve
native values, errors and unsupported capabilities. A persistent command bridge
is available when a public Python binding does not fit. Do not vendor upstream
internal code without a verified license and required attribution.

Data contributions need source revision/content hashes, asset-specific rights,
construction and annotation history, source-family IDs, split/exposure history,
and overlap audits. No private listing extracts, guessed licenses or generated
examples labeled as naturally entered. Review annotations independently before
claiming accuracy beyond the authored conformance suite.

Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` and the authored task
examples. CI needs no network, external runtimes or models. Run heavy evaluations
through your machine's workload coordinator. Keep actual exit codes and all
trials. No automatic host tuning or process termination outside your own jobs.

Useful next contributions: a genuinely independent adapter, a reviewed named
normalization/format profile, a larger legally redistributable natural corpus,
and a native timing-backend attachment with matched scope and contract tests.
