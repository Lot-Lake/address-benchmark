# USA parser comparison / active eight-configuration cohort

Edge-delimiter supplied-field agreement

| Dataset / view | Rust learned | Rust default | BoundaryBoys | Doorplate | usaddress | fastaddress | libpostal default | libpostal Senzing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GeoSearch dev | **98.88%** | 76.88% | 70.64% | 94.31% | 88.24% | 88.24% | 84.27% | 78.70% |
| GeoSearch test (publisher split) | **99.02%** | 80.04% | 72.80% | 96.66% | 88.39% | 88.39% | 88.81% | 86.15% |
| Doorplate suite | 88.41% | 83.63% | 69.79% | **93.85%** | 86.11% | 86.11% | 82.45% | 88.57% |
| Doorplate suite / normal | 94.36% | 91.04% | 79.53% | **96.92%** | 96.46% | 96.46% | 88.70% | 93.01% |
| Doorplate suite / hard | 54.24% | 40.19% | 22.86% | **75.28%** | 20.70% | 20.70% | 48.16% | 67.12% |
| Doorplate suite / handwritten | 81.60% | 77.30% | 35.30% | **92.70%** | 89.70% | 89.70% | 71.10% | 73.00% |
| Expanded USA | 89.88% | 95.26% | 80.93% | 86.65% | 90.04% | 90.04% | 91.42% | **95.39%** |
| Expanded USA / partial | 90.58% | **95.45%** | 82.02% | 87.16% | 90.58% | 90.58% | 91.27% | 95.38% |
| us-units-adversarial | 71.15% | 73.08% | 22.12% | **89.42%** | 82.69% | 82.69% | 52.88% | 62.50% |
| deepparse-hf-us | 87.10% | 80.55% | 68.30% | 90.15% | 88.49% | 88.49% | **99.65%** | 98.20% |
| deepparse-hf-us / full | 86.05% | 78.74% | 67.84% | 90.76% | 89.58% | 89.58% | **99.65%** | 98.62% |
| deepparse-hf-us / partial | 88.71% | 83.30% | 69.01% | 89.22% | 86.83% | 86.83% | **99.64%** | 97.56% |
| nad-rendered | 94.40% | 97.76% | 86.43% | 89.28% | 89.08% | 89.08% | 94.94% | **98.48%** |
| nad-rendered / clean | 98.44% | **99.96%** | 87.58% | 87.63% | 87.55% | 87.55% | 94.47% | 98.31% |
| nad-rendered / nocomma | 97.67% | 93.76% | 80.09% | 88.08% | 87.81% | 87.81% | 94.51% | **98.56%** |
| nad-rendered / expanded | 92.22% | **99.92%** | 86.38% | 88.24% | 87.67% | 87.67% | 96.55% | 99.42% |
| nad-rendered / noisy | 89.25% | 97.38% | 91.69% | 93.16% | 93.31% | 93.31% | 94.23% | **97.64%** |

- Counts and failures use the recorded scoring denominators. Partial references judge supplied labels; they are not whole-address accuracy.
- Subset rows overlap the parent dataset. Public/development-exposed fixtures do not establish unseen accuracy.
- Bold marks rounded row leaders only when measured denominators match. Missing/unsupported scores are unmeasured, never zero.
- Strict preserves punctuation. Edge-delimiter ignores component-edge comma/semicolon/colon only, plus case and whitespace.
- Timing appears only when recorded: exploratory process medians, not accuracy-run wall time. † marks sample spread above 10%; ! marks native errors/refusals.
- The report command checks recorded run identities. Exports do not rescore predictions or rehash every artifact.
- Combined from multiple recorded experiment sources; source run identities remain separate. This is not a new simultaneous run or a pooled overall score.
- Deepparse full means all five tagged core fields are present; both full and partial views still have partial reference coverage. This source has libpostal training lineage.
- NAD rows are generated from an explicit frozen sample of the official public API. Fifty indexed 1,000-record OBJECTID windows were acquired; eligible states were sampled/rendered by the merged generator. This is not the r24 TXT archive or an exact reproduction of an unshared screenshot.
- The first five panels come from the earlier verified run; Deepparse/NAD were executed afterward with the same frozen framework and configured engines. Separate source run identities and timestamps are retained.
- Doorplate publisher references contain trailing field delimiters in 12,331/19,586 rows. Strict measures literal punctuation fidelity here; use delimiter or versioned streetline scores for canonical component comparison. Reference values/spans were not rewritten.
- Cohort presentation only: eight retained configurations selected from the previously recorded nine-configuration execution batches. Scores and denominators are unchanged; row leaders reflect the displayed cohort. No parser was rerun for this export. Original full-cohort reports retain their original identities and counts.
