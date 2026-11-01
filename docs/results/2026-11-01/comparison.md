# Fresh production parsing comparison

Nine engine configurations; 113,703 source rows across four panels, 113,644 distinct exact UTF-8 inputs. Each engine ran fresh through the benchmark plan; predictions were rehashed and rescored. Source rows are not independent source families. Detailed exact cross-split/source overlap is retained locally in overlap.json; public exports include aggregate overlap counts only.

The retained learned Rust model and the default source parser are separate columns. These public/development-exposed fixtures do not establish unseen generalization. No private runtime, corpus or raw address is included in this report.

| Corpus | Engine | Correct / eligible | Edge-delimiter agreement | Strict agreement | Fine token F1 | Errors / refusals |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| geosearch-dev | boundaryboys | 42,751/60,522 | 70.64% | 70.64% | unmeasured | 0 / 0 |
| geosearch-dev | doorplate | 57,081/60,522 | 94.31% | 94.31% | 96.12% | 0 / 0 |
| geosearch-dev | fastaddress | 53,404/60,522 | 88.24% | 88.24% | 95.39% | 0 / 0 |
| geosearch-dev | libpostal-default | 51,000/60,522 | 84.27% | 84.27% | unmeasured | 0 / 0 |
| geosearch-dev | libpostal-senzing | 47,630/60,522 | 78.70% | 78.70% | unmeasured | 0 / 0 |
| geosearch-dev | mailwoman | 53,892/60,522 | 89.05% | 89.05% | unmeasured | 0 / 0 |
| geosearch-dev | rust-default | 46,527/60,522 | 76.88% | 76.88% | unmeasured | 0 / 0 |
| geosearch-dev | rust-learned | 59,748/60,522 | 98.72% | 98.72% | 99.67% | 0 / 0 |
| geosearch-dev | usaddress | 53,404/60,522 | 88.24% | 88.24% | 95.39% | 0 / 0 |
| geosearch-test | boundaryboys | 22,292/30,622 | 72.80% | 72.80% | unmeasured | 0 / 0 |
| geosearch-test | doorplate | 29,598/30,622 | 96.66% | 96.66% | 95.99% | 0 / 0 |
| geosearch-test | fastaddress | 27,068/30,622 | 88.39% | 88.39% | 94.70% | 0 / 0 |
| geosearch-test | libpostal-default | 27,194/30,622 | 88.81% | 88.81% | unmeasured | 0 / 0 |
| geosearch-test | libpostal-senzing | 26,381/30,622 | 86.15% | 86.15% | unmeasured | 0 / 0 |
| geosearch-test | mailwoman | 27,945/30,622 | 91.26% | 91.26% | unmeasured | 0 / 0 |
| geosearch-test | rust-default | 24,511/30,622 | 80.04% | 80.04% | unmeasured | 0 / 0 |
| geosearch-test | rust-learned | 30,291/30,622 | 98.92% | 98.92% | 99.70% | 0 / 0 |
| geosearch-test | usaddress | 27,068/30,622 | 88.39% | 88.39% | 94.70% | 0 / 0 |
| doorplate-v1 | boundaryboys | 13,669/19,586 | 69.79% | 24.01% | unmeasured | 0 / 0 |
| doorplate-v1 | doorplate | 18,381/19,586 | 93.85% | 93.85% | 98.00% | 0 / 0 |
| doorplate-v1 | fastaddress | 16,866/19,586 | 86.11% | 86.11% | 96.08% | 0 / 0 |
| doorplate-v1 | libpostal-default | 16,149/19,586 | 82.45% | 30.73% | unmeasured | 0 / 0 |
| doorplate-v1 | libpostal-senzing | 17,347/19,586 | 88.57% | 33.12% | unmeasured | 0 / 0 |
| doorplate-v1 | mailwoman | 17,777/19,586 | 90.76% | 32.71% | unmeasured | 0 / 0 |
| doorplate-v1 | rust-default | 16,380/19,586 | 83.63% | 27.88% | unmeasured | 0 / 0 |
| doorplate-v1 | rust-learned | 17,056/19,586 | 87.08% | 87.03% | 95.63% | 0 / 0 |
| doorplate-v1 | usaddress | 16,866/19,586 | 86.11% | 86.11% | 96.08% | 0 / 0 |
| expanded-usa | boundaryboys | 2,406/2,973 | 80.93% | 60.71% | unmeasured | 0 / 0 |
| expanded-usa | doorplate | 2,576/2,973 | 86.65% | 22.27% | unmeasured | 0 / 0 |
| expanded-usa | fastaddress | 2,677/2,973 | 90.04% | 23.68% | unmeasured | 0 / 0 |
| expanded-usa | libpostal-default | 2,718/2,973 | 91.42% | 69.69% | unmeasured | 0 / 0 |
| expanded-usa | libpostal-senzing | 2,836/2,973 | 95.39% | 73.73% | unmeasured | 0 / 0 |
| expanded-usa | mailwoman | 2,709/2,973 | 91.12% | 69.53% | unmeasured | 0 / 0 |
| expanded-usa | rust-default | 2,832/2,973 | 95.26% | 73.26% | unmeasured | 0 / 0 |
| expanded-usa | rust-learned | 2,647/2,973 | 89.03% | 21.16% | unmeasured | 0 / 0 |
| expanded-usa | usaddress | 2,677/2,973 | 90.04% | 23.68% | unmeasured | 0 / 0 |

## Runtime cohort

| Engine | Installed package/model | Runtime |
| --- | --- | --- |
| boundaryboys | embedded dictionary in pinned executable | Python 3.12.8 |
| doorplate | doorplate 0.5.0.dev0; installed 0.5.0.dev0 public parse + compatibility tokens, null labels retained | Python 3.14.6 |
| fastaddress | fastaddress 0.1.0; upstream usaddress 0.5.16 CRF lineage; runtime/package/model file hashes recorded | Python 3.12.8 |
| libpostal-default | libpostal model=default | Python 3.12.8 |
| libpostal-senzing | libpostal model=senzing | Python 3.12.8 |
| mailwoman | @mailwoman/libpostal 10.7.0, @mailwoman/neural 10.7.0, @mailwoman/neural-weights-en-us 10.7.0, mailwoman 10.7.0; @mailwoman/neural-weights-en-us@10.7.0; CPU; one intra-op thread | Python 3.12.8; Node v24.18.0 |
| rust-default | installed default embedded deterministic engine | Python 3.12.8 |
| rust-learned | usa-raw28-wisconsin-projected100:afc89a22cbea4c100131fbf68728fde819b24a953e2ca5cf8328f00eb542d922 | Python 3.12.8 |
| usaddress | usaddress 0.5.16; upstream usaddress 0.5.16 CRF lineage; runtime/package/model file hashes recorded | Python 3.14.6 |

These are the installed versions actually executed, not claims about the latest upstream release. Fastaddress model v1 shares the usaddress CRF lineage. Mailwoman accuracy uses four independent CPU processes with one ONNX intra-op thread each. BoundaryBoys is a locally installed private executable; its source is not redistributed. Full runtime/file identities are retained locally; per-track identity hashes are exported in comparison.json.

Both field policies use the same untouched native predictions. The edge-delimiter diagnostic ignores only component-edge comma/semicolon/colon, case and whitespace; periods, abbreviations, accents, ZIP width and internal punctuation remain significant. Fine scores require publisher fine labels and declared native token support; coarse emitters are unmeasured, not zero.

Expanded USA contains 2,920 partial and 53 complete references. Its shared figure is supplied-field agreement; extra roles are unadjudicated. It is not whole-address accuracy. Doorplate has rendered and hand-authored origins; its strata are views, not additional rows. Native unplaced tokens are retained.

## Where to investigate

### rust-learned

- **geosearch-dev:** 59,748/60,522 supplied-field agreements. Frequent mismatch roles: road: 748, city: 740, state: 33, house_number: 20, unit: 15, intersection_separator: 1. These role counts overlap.
  Against doorplate, the other engine alone passes 386 rows and this baseline alone passes 3,053; net difference -2,667. This is paired diagnostic evidence, not a deployable gold-selected selector.
  On exactly matching native/publisher token boundaries: us:StreetName → us:PlaceName: 219; us:PlaceName → us:StreetNamePostDirectional: 218; us:StreetName → us:StreetNamePostType: 178; us:PlaceName → us:StreetName: 157; us:StreetName → us:StreetNamePreDirectional: 99; us:StreetName → us:StreetNamePostDirectional: 92.

- **geosearch-test:** 30,291/30,622 supplied-field agreements. Frequent mismatch roles: road: 317, city: 316, state: 14, house_number: 14, unit: 3, intersection_separator: 2. These role counts overlap.
  Against doorplate, the other engine alone passes 196 rows and this baseline alone passes 889; net difference -693. This is paired diagnostic evidence, not a deployable gold-selected selector.
  On exactly matching native/publisher token boundaries: us:StreetName → us:PlaceName: 109; us:PlaceName → us:StreetNamePostDirectional: 85; us:StreetName → us:StreetNamePostType: 77; us:PlaceName → us:StreetName: 54; us:StreetName → us:StreetNamePostDirectional: 48; us:StreetName → us:StreetNamePreDirectional: 47.

- **doorplate-v1:** 17,056/19,586 supplied-field agreements. Frequent mismatch roles: road: 2,158, unit: 1,483, city: 1,036, house_number: 294, po_box: 129, state: 57. These role counts overlap.
  Against doorplate, the other engine alone passes 1,965 rows and this baseline alone passes 640; net difference +1,325. This is paired diagnostic evidence, not a deployable gold-selected selector.
  On exactly matching native/publisher token boundaries: us:StreetNamePostType → us:StreetName: 1,452; us:OccupancyIdentifier → us:StreetName: 1,029; us:StreetNamePostDirectional → us:PlaceName: 572; us:StreetNamePreType → us:StreetName: 480; us:StreetNamePreDirectional → us:StreetName: 377; us:StreetNamePostDirectional → us:StreetName: 320.

- **expanded-usa:** 2,647/2,973 supplied-field agreements. Frequent mismatch roles: road: 207, city: 113, unit: 98, level: 71, building: 36, city_district: 24. These role counts overlap.
  Against libpostal-senzing, the other engine alone passes 224 rows and this baseline alone passes 35; net difference +189. This is paired diagnostic evidence, not a deployable gold-selected selector.
  Reference-role requirements outside the declared active model/API inventory: level: 71, city_district: 24, suburb: 11, category: 4, near: 4, state_district: 2. These are capability/ontology gaps, not necessarily training-only errors.

### rust-default

- **geosearch-dev:** 46,527/60,522 supplied-field agreements. Frequent mismatch roles: city: 13,709, road: 13,060, state: 4,365, house_number: 4,354, postcode: 4,033, unit: 1,092. These role counts overlap.
  Against rust-learned, the other engine alone passes 13,336 rows and this baseline alone passes 115; net difference +13,221. This is paired diagnostic evidence, not a deployable gold-selected selector.

- **geosearch-test:** 24,511/30,622 supplied-field agreements. Frequent mismatch roles: city: 5,910, road: 5,702, state: 2,729, house_number: 2,689, postcode: 2,483, unit: 409. These role counts overlap.
  Against rust-learned, the other engine alone passes 5,850 rows and this baseline alone passes 70; net difference +5,780. This is paired diagnostic evidence, not a deployable gold-selected selector.

- **doorplate-v1:** 16,380/19,586 supplied-field agreements. Frequent mismatch roles: road: 2,891, city: 1,814, house_number: 1,646, unit: 846, postcode: 409, state: 408. These role counts overlap.
  Against doorplate, the other engine alone passes 2,624 rows and this baseline alone passes 623; net difference +2,001. This is paired diagnostic evidence, not a deployable gold-selected selector.
  Reference-role requirements outside the declared active model/API inventory: recipient: 247, corner_of: 4. These are capability/ontology gaps, not necessarily training-only errors.

- **expanded-usa:** 2,832/2,973 supplied-field agreements. Frequent mismatch roles: level: 65, building: 36, road: 30, house_number: 14, city: 12, unit: 10. These role counts overlap.
  Against libpostal-senzing, the other engine alone passes 43 rows and this baseline alone passes 39; net difference +4. This is paired diagnostic evidence, not a deployable gold-selected selector.
  Reference-role requirements outside the declared active model/API inventory: building: 36, corner_of: 2, not_address: 1. These are capability/ontology gaps, not necessarily training-only errors.

## Improvement workflow

1. Review the leading role confusions and paired deficits in their original annotation/task profiles. Distinguish segmentation, native normalization, ontology mismatch and incorrect role decisions.
2. Build independent positive/negative development and training families for those phenomena. Keep these public evaluation rows out of newly collected training material; log existing exposure explicitly.
3. Fix and evaluate one declared candidate at a time, retaining gains and losses by source/stratum. Freeze a separately adjudicated heldout population before generalization claims.
4. Measure performance on a fixed input-only panel in a separate contemporaneous paired experiment. Accuracy process wall times include model hashing/loading/I/O and are not parse throughput.

The files comparison.json and comparison.csv contain the aggregate evidence and per-baseline comparative counts. Full predictions, references, runtime identities, model hashes, exits/logs and case deltas remain in the local verified run folders. No raw address values are exported here.
