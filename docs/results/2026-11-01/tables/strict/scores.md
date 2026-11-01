# USA parser comparison

Strict supplied-field agreement

| Dataset / view | Rust learned | Rust default | BoundaryBoys | Doorplate | usaddress | fastaddress | libpostal default | libpostal Senzing | Mailwoman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GeoSearch dev | **98.72%** | 76.88% | 70.64% | 94.31% | 88.24% | 88.24% | 84.27% | 78.70% | 89.05% |
| GeoSearch test (publisher split) | **98.92%** | 80.04% | 72.80% | 96.66% | 88.39% | 88.39% | 88.81% | 86.15% | 91.26% |
| Doorplate suite | 87.03% | 27.88% | 24.01% | **93.85%** | 86.11% | 86.11% | 30.73% | 33.12% | 32.71% |
| Doorplate suite / normal | 93.18% | 30.07% | 25.92% | **96.92%** | 96.46% | 96.46% | 31.62% | 33.09% | 33.04% |
| Doorplate suite / hard | 51.41% | 18.10% | 17.52% | **75.28%** | 20.70% | 20.70% | 30.41% | 38.96% | 36.36% |
| Doorplate suite / handwritten | 80.60% | 18.10% | 10.30% | **92.70%** | 89.70% | 89.70% | 17.30% | 18.40% | 18.00% |
| Expanded USA | 21.16% | 73.26% | 60.71% | 22.27% | 23.68% | 23.68% | 69.69% | **73.73%** | 69.53% |

- Counts and failures use the recorded scoring denominators. Partial references judge supplied labels; they are not whole-address accuracy.
- Subset rows overlap the parent dataset. Public/development-exposed fixtures do not establish unseen accuracy.
- Bold marks rounded row leaders only when measured denominators match. Missing/unsupported scores are unmeasured, never zero.
- Strict preserves punctuation. Edge-delimiter ignores component-edge comma/semicolon/colon only, plus case and whitespace.
- Timing appears only when recorded: exploratory process medians, not accuracy-run wall time. † marks sample spread above 10%; ! marks native errors/refusals.
- The report command checks recorded run identities. Exports do not rescore predictions or rehash every artifact.
