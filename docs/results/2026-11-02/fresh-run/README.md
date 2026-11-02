# Fresh benchmark — 2026-11-02

9 parsing configurations; 113,807 source rows across five panels; 1,024,263 fresh predictions. All 45 engine/panel cells completed and all five panels were verified. Framework source and bridges were frozen from merged main before execution.

Our learned column uses `usa-lexical-locality-unit-boundary28` (`e429c2cf5a1e01abcb6fad02d7f39768d3d8923141dee58b14ce016a889fe965`). It is an optional experimental model; the default public parser remains a separate column. Competitors use the actual installed cohort versions, not claims about latest upstream releases.

## Full parsing comparison


Edge-delimiter supplied-field agreement

| Dataset / view | Rust learned | Rust default | BoundaryBoys | Doorplate | usaddress | fastaddress | libpostal default | libpostal Senzing | Mailwoman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GeoSearch dev | **98.88%** | 76.88% | 70.64% | 94.31% | 88.24% | 88.24% | 84.27% | 78.70% | 89.05% |
| GeoSearch test (publisher split) | **99.02%** | 80.04% | 72.80% | 96.66% | 88.39% | 88.39% | 88.81% | 86.15% | 91.26% |
| Doorplate suite | 88.41% | 83.63% | 69.79% | **93.85%** | 86.11% | 86.11% | 82.45% | 88.57% | 90.76% |
| Doorplate suite / normal | 94.36% | 91.04% | 79.53% | **96.92%** | 96.46% | 96.46% | 88.70% | 93.01% | 94.96% |
| Doorplate suite / hard | 54.24% | 40.19% | 22.86% | **75.28%** | 20.70% | 20.70% | 48.16% | 67.12% | 70.17% |
| Doorplate suite / handwritten | 81.60% | 77.30% | 35.30% | **92.70%** | 89.70% | 89.70% | 71.10% | 73.00% | 76.90% |
| Expanded USA | 89.88% | 95.26% | 80.93% | 86.65% | 90.04% | 90.04% | 91.42% | **95.39%** | 91.12% |
| us-units-adversarial | 71.15% | 73.08% | 22.12% | **89.42%** | 82.69% | 82.69% | 52.88% | 62.50% | 72.12% |

- Counts and failures use the recorded scoring denominators. Partial references judge supplied labels; they are not whole-address accuracy.
- Subset rows overlap the parent dataset. Public/development-exposed fixtures do not establish unseen accuracy.
- Bold marks rounded row leaders only when measured denominators match. Missing/unsupported scores are unmeasured, never zero.
- Strict preserves punctuation. Edge-delimiter ignores component-edge comma/semicolon/colon only, plus case and whitespace.
- Timing appears only when recorded: exploratory process medians, not accuracy-run wall time. † marks sample spread above 10%; ! marks native errors/refusals.
- The report command checks recorded run identities. Exports do not rescore predictions or rehash every artifact.


## Change since the previous full run

Same frozen input populations and the same edge-delimiter policy. These are fresh model/runtime observations, not improvements created by switching scoring profiles. Gained/lost counts are paired row decisions.

| Panel | Our configuration | Previous correct | Current correct | Gained | Lost |
| --- | --- | ---: | ---: | ---: | ---: |
| geosearch-dev | rust-learned | 59,748/60,522 | 59,845/60,522 | 159 | 62 |
| geosearch-dev | rust-default | 46,527/60,522 | 46,527/60,522 | 0 | 0 |
| geosearch-test | rust-learned | 30,291/30,622 | 30,323/30,622 | 66 | 34 |
| geosearch-test | rust-default | 24,511/30,622 | 24,511/30,622 | 0 | 0 |
| doorplate-v1 | rust-learned | 17,056/19,586 | 17,316/19,586 | 360 | 100 |
| doorplate-v1 | rust-default | 16,380/19,586 | 16,380/19,586 | 0 | 0 |
| expanded-usa | rust-learned | 2,647/2,973 | 2,672/2,973 | 40 | 15 |
| expanded-usa | rust-default | 2,832/2,973 | 2,832/2,973 | 0 | 0 |

## Utility observations

| Track | Our default | Doorplate |
| --- | ---: | ---: |
| identity-conformance | 10/10 | 9/10 |
| normalized-components | 4/4 | 1/4 |
| property-identity | 6/8 | 8/8 |
| publisher-classification | 19446/19586 | 19473/19586 |
| stability-common | 0/1 | 0/1 |
| stability-stream-chunk | 0/1 | unsupported / not selected |

Stability agreement is a panel-level assertion, not a per-address accuracy percentage. Actual changed-row counts are retained in utilities.md and summary.json.

For property identity, Doorplate uses its native `key(unit=False)`. Our selected native comparison-key API retains units; it is evaluated unchanged against property-level gold. No unit stripping or gold-selected repair was added. A false split here documents a capability gap, not a claim that our delivery-unit API is a property-key implementation.

## Score policy and scope

- [Strict score table](strict/scores.md) and [edge-delimiter table](delimiter/scores.md) preserve the original policies.
- [New streetline profile](streetline/scores.md) is opt-in and separately reported. Its abbreviation folds, ZIP+4 truncation, four-digit ZIP repair and spacing removal are lossy comparison rules; they do not demonstrate new parsing accuracy or deliverability.
- [Fine token F1](fine-f1/scores.md) is measured only where the native API and complete fine references support it. Unmeasured is not zero.
- Expanded USA mostly has partial references; its score is supplied-field agreement, not whole-address accuracy. The unit challenge and property pairs are exposed authored controls.
- NAD and Deepparse full source assets are not installed, so these populations are explicitly unrun in this pass. Existing NAD API samples lack the structured fields required by the new recipe. Their recipe/integration tests passed separately.
- No calibrated competitor speed ranking follows from accuracy-run wall times. Geocoding is outside scope.
- Raw datasets, predictions, native outputs, model weights, logs and private executable identities remain local. Aggregate exports contain no raw addresses.

The [HTML comparison](delimiter/scores.html), text, Markdown, CSV and JSON exports are generated from the accepted fresh run. Complete local run artifacts are indexed in `local-run-index.json`.
