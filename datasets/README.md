# Real corpus catalog

`catalog.json` describes the real populations wired into the production plan.
Counts identify the previously audited frozen intake, not every revision of an
upstream project. `tools/prepare_local_matrix.py` reads the explicitly selected
assets, hashes their actual bytes, writes corpus/engine manifests and a JSON
plan, and records per-source annotation/construction/exposure policy.

Raw data remains in the user's existing source locations. Run inputs/references
and predictions are necessary local evaluation artifacts and are ignored by Git.
No private listing archive or large runtime cache is copied into this project.
Public repository code licenses do not authorize every data/model asset.

The readers also support `usaddress-xml` as a local plugin format. Specify
resource `coverage: "partial"` when only supplied fields are asserted. XML labels
and their tokenization convention need explicit review before fine-role claims;
do not infer exhaustive labels or training non-exposure from XML structure.

To add another corpus, provide a versioned manifest with pinned local/HTTPS
assets and an existing reader or a reviewed reader plugin. An `external_path`
must be absolute and requires `license.redistribution: "local-only"`. Ordinary
relative resources retain traversal/symlink-escape protection. The parent plan
contains no gold values or executable expressions.
