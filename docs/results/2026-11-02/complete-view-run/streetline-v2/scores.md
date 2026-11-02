# Complete USA parser comparison / saved predictions rescored under v2

strict-streetline/v2 source-order profile agreement

| Dataset / view | Rust learned | Rust default | BoundaryBoys | Doorplate | usaddress | fastaddress | libpostal default | libpostal Senzing | Mailwoman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GeoSearch dev | **98.88%** | 76.88% | 70.64% | 94.34% | 88.25% | 88.25% | 84.28% | 78.71% | 89.05% |
| GeoSearch test (publisher split) | **99.02%** | 80.04% | 72.80% | 96.66% | 88.39% | 88.39% | 88.82% | 86.15% | 91.26% |
| Doorplate suite | 89.03% | 84.08% | 74.84% | **95.94%** | 87.35% | 87.35% | 82.72% | 89.18% | 92.90% |
| Doorplate suite / normal | 94.59% | 91.04% | 82.77% | **98.76%** | 97.09% | 97.09% | 88.71% | 93.15% | 96.74% |
| Doorplate suite / hard | 54.39% | 40.19% | 35.94% | **78.76%** | 24.53% | 24.53% | 48.20% | 67.20% | 70.60% |
| Doorplate suite / handwritten | 89.60% | 86.10% | 48.50% | **95.10%** | 94.00% | 94.00% | 76.10% | 82.40% | 89.00% |
| Expanded USA | 91.59% | **98.62%** | 82.56% | 96.87% | 92.09% | 92.09% | 91.82% | 97.68% | 94.08% |
| Expanded USA / partial | 92.22% | **98.59%** | 83.52% | 97.43% | 92.43% | 92.43% | 91.67% | 97.70% | 94.59% |
| us-units-adversarial | 77.88% | 80.77% | 25.96% | **93.27%** | 89.42% | 89.42% | 58.65% | 68.27% | 73.08% |
| deepparse-hf-us | 87.22% | 80.62% | 74.25% | 90.27% | 89.22% | 89.22% | **99.68%** | 98.21% | 88.98% |
| deepparse-hf-us / full | 86.16% | 78.81% | 74.51% | 90.88% | 90.14% | 90.14% | **99.68%** | 98.63% | 89.94% |
| deepparse-hf-us / partial | 88.84% | 83.39% | 73.86% | 89.33% | 87.80% | 87.80% | **99.69%** | 97.57% | 87.50% |
| nad-rendered | 96.60% | 97.77% | 96.97% | **99.61%** | 99.35% | 99.35% | 94.95% | 98.50% | 98.65% |
| nad-rendered / clean | 98.44% | **99.96%** | 99.93% | **99.96%** | 99.84% | 99.84% | 94.47% | 98.32% | 99.83% |
| nad-rendered / nocomma | 97.67% | 93.76% | 90.95% | **99.88%** | 99.53% | 99.53% | 94.51% | 98.56% | 96.39% |
| nad-rendered / expanded | 92.22% | **99.96%** | 99.93% | **99.96%** | 99.31% | 99.31% | 96.57% | 99.47% | 99.85% |
| nad-rendered / noisy | 98.05% | 97.38% | 97.08% | 98.63% | **98.70%** | **98.70%** | 94.23% | 97.64% | 98.52% |

- Counts and failures use the recorded scoring denominators. Partial references judge supplied labels; they are not whole-address accuracy.
- Subset rows overlap the parent dataset. Public/development-exposed fixtures do not establish unseen accuracy.
- Bold marks rounded row leaders only when measured denominators match. Missing/unsupported scores are unmeasured, never zero.
- Strict preserves punctuation. Edge-delimiter ignores component-edge comma/semicolon/colon only, plus case and whitespace.
- Timing appears only when recorded: exploratory process medians, not accuracy-run wall time. † marks sample spread above 10%; ! marks native errors/refusals.
- DERIVED SCORING ONLY: saved native predictions were rescored under strict-streetline/v2. No parser was executed again. Original v1 results and immutable run records remain unchanged.
- Reference, prediction, case and runtime-identity file hashes were checked against the recorded runs. Every saved v1 case score was reproduced exactly before calculating v2.
- V2 orders road evidence by its own spans when every road item has spans, otherwise by native evidence order. No reference repairs predictions. Discontinuous multi-span values are ordered as whole items by earliest span.
- Deepparse full/partial both use partial references; the corpus has libpostal training lineage. NAD uses our explicitly frozen official-API window sample and generated views, not the unshared screenshot population.
- Seven source populations came from two separately verified execution batches; no simultaneous speed or unseen-accuracy claim is made. See derivation.json for source and scoring identities.
- Doorplate publisher references contain trailing field delimiters in 12,331/19,586 rows. Strict measures literal punctuation fidelity here; use delimiter or versioned streetline scores for canonical component comparison. Reference values/spans were not rewritten.
