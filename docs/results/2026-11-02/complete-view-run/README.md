# Complete corpus/view comparison — 2026-11-02

This corrects the earlier incomplete population coverage. The earlier five panels were verified separately; the two missing corpora have now run through all nine configurations. No score was copied from the screenshot.

**168,067 source rows, 63 engine/panel cells and 1,512,603 recorded parsing predictions** across seven populations. Of these, 488,340 predictions on Deepparse/NAD were executed in the added batch. All seven panels completed and were verified.

| New population / view | Source rows |
| --- | ---: |
| deepparse-hf-us | 21,234 |
| deepparse-hf-us / full | 12,829 |
| deepparse-hf-us / partial | 8,405 |
| nad-rendered | 33,026 |
| nad-rendered / clean | 8,263 |
| nad-rendered / nocomma | 8,258 |
| nad-rendered / expanded | 8,254 |
| nad-rendered / noisy | 8,251 |

[Open the complete comparison table](delimiter/scores.html) · [Markdown](delimiter/scores.md) · [console text](delimiter/scores.txt) · [CSV](delimiter/scores.csv)

[Opt-in streetline v2 comparison](streetline-v2/scores.html) rescored the saved predictions under the newly merged source-order policy. This is derived scoring, not another parser execution; all 1,512,603 original v1 case scores were reproduced exactly first. Source/artifact hashes and the derivation identity are in [derivation.json](streetline-v2/derivation.json).

Separate exports: [strict](strict/scores.html), [new streetline profile](streetline/scores.html), and [fine token F1](fine-f1/scores.html). The new profile is an opt-in lossy comparison policy, not new parsing evidence.

## Provenance and interpretation

- Deepparse follows the merged pinned-revision/seed sampler. Remote Parquet row groups were used; whole-source-file hashes are declared but not independently verified in this mode. The locally derived corpus is hash-pinned. Its libpostal training lineage is explicitly disclosed.
- Deepparse full/partial are input-label strata. Both reference sets remain partial; full does not assert absent units or whole-address accuracy.
- NAD uses an explicitly recorded API window sample because the r24 TXT archive is not locally available. The unchanged merged renderer produced clean/nocomma/expanded/noisy strata. Frozen source responses, API metadata and hashes are local. This is generated data and not a nationally representative or naturally entered sample.
- These are two recorded execution batches using the same frozen framework/configuration. Runtime identity comparisons and original per-panel content IDs are retained in summary.json; no new simultaneous speed comparison is implied.
- The screenshot source population was not shared or found on GitHub. These are our actual reproducible populations; their counts and scores are not asserted to match that screenshot.
- Views overlap their parent rows. Exact overlap counts are retained separately; public exposure and source-family uncertainty remain. No unseen-accuracy claim follows.
- Earlier reports remain historical records. This directory is the complete corpus/view report; raw inputs, predictions and private runtime/model assets remain local.

The report command now accepts multiple explicit plan sources and --all-views (or named subsets), while rejecting duplicate dataset IDs and mixed task/scoring policies. Its source identities remain separate, so report composition cannot masquerade as missing execution.

Doorplate reference caveat: 12,331 of 19,586 rows include trailing field delimiters. Strict is literal punctuation fidelity on this corpus; use delimiter or streetline for canonical component comparison. The [count audit](doorplate-delimiter-audit.json) preserves raw publisher gold without rewriting values or spans.
