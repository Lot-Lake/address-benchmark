# Findings and improvement priorities

The independent address-benchmark v0.2 framework ran nine installed parsing configurations on 113,703 public/development-exposed source rows (113,644 distinct exact inputs). All 36 parsing cells completed, with zero adapter errors/refusals, and their artifacts were rehashed and rescored. This is 1,023,327 fresh predictions. It is neither a natural-population accuracy estimate nor unseen generalization evidence.

| Panel | Default source parser | Retained learned model | Strongest other configuration on this panel |
| --- | ---: | ---: | ---: |
| GeoSearch DEV (60,522) | 76.88% | 98.72% | Doorplate 94.31% |
| GeoSearch TEST (30,622) | 80.04% | 98.92% | Doorplate 96.66% |
| Doorplate v1 (19,586) | 83.63% | 87.08% | Doorplate 93.85% |
| Expanded USA (2,973) | 95.26% | 89.03% | libpostal Senzing 95.39% |

These are **component agreement under the edge-delimiter diagnostic**, not the primary strict metric. The [complete report](comparison.md) retains both. Expanded USA mostly has partial references, so its figure judges only supplied fields. The default source-evidence parser and experimental retained model request distinct native APIs; neither result justifies silently promoting one backend. Rows, rendered views and overlapping strata are not independent address families.

1. **Fix normalization idempotence first.** Native normalization changes on its second pass for 4 of 1,024 panel rows, representing 3 distinct input strings. The examples involve a numberless street/city boundary, a floor/unit boundary and a military box prefix. Repeated calls and scalar/batch/stream/chunk outputs agree on every row. Preserve digits, unit identifiers and address meaning when making a fix, then check gains and regressions across the entire panel. Doorplate changes on 9 panel rows under its own native USPS renderer.

2. **Improve the default parser's street/city boundaries in delimiter-free inputs.** GeoSearch inputs are constructed by joining source tokens with spaces. On TEST, the default has road mismatches on 5,702 rows and city mismatches on 5,910; these overlap. The retained model alone passes 5,850 rows and the default alone passes 70. Investigate a source-compatible learned candidate or targeted boundary fixes while retaining the default's wins and explicit source evidence. This comparison does not measure throughput or deployment cost.

3. **Strengthen secondary-unit and affix behavior on the Doorplate hard stratum.** On its 2,585 rendered hard rows, default/learned/Doorplate agreement is 40.19%/51.41%/75.28%. The learned model's frequent exact-boundary confusions include street suffix→street name (1,452 tokens) and occupancy identifier→street name (1,029). On the 1,000 hand fixtures, scores are 77.30%/81.70%/92.70%. Review unit, directional and affix boundaries with independent positive and negative development families; do not relabel ambiguous publisher cases automatically.

4. **Treat role coverage as an API/model decision.** The retained model cannot express several supplied expanded-panel roles, including level (71 rows), city district (24) and suburb (11). The default source API exposes generic names rather than typed building/recipient distinctions; mapping every name to a building would fabricate evidence. On the small 53-case complete libpostal subset, default/learned/Senzing agreement is 45/24/51. Review ontology/annotation boundaries before interpreting all disagreements as trainable parsing errors.

5. **Review classification separately from parsing.** The default agrees with 19,446/19,586 publisher type assertions (99.29%), versus Doorplate 19,473/19,586 (99.42%). Default disagreements include 19 PO boxes and 12 rural forms classified as street. Highway/street and military/street disagreements also involve taxonomy scope, so keep their raw classes and adjudicate the mapping. The normalization projection passes 4/4 complete scourgify assertions and delivery-unit keys pass 10/10 independent fictional pairs; these tiny controls do not estimate broad normalization or matching quality.

The framework has executable contracts/examples for formatting, extraction, inference, variants and diagnostics. Those surfaces still need dedicated production adapters and independently reviewed references. Calibrated performance, memory and startup comparisons are also separate work. Geocoding is outside this run.

The next candidate should be evaluated on the same frozen profiles with paired gains/losses, followed by a separately adjudicated heldout population. Existing public evaluation rows should not become new training examples. The benchmark defines a proposal for a reusable standard; it does not establish an overall winning utility library.

See [all parsing configurations and role diagnostics](comparison.md), [utility observations](utilities.md), [aggregate parsing JSON](comparison.json), and [aggregate utility JSON](utilities.json). Detailed raw predictions, references, logs, model hashes and per-row decisions remain local; public exports contain aggregate results only.
