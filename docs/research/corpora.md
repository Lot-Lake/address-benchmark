# Corpus research and independent suite design

Research date: **2026-11-01**. This project is an independent benchmark product. Upstream suites inform its coverage and methodology; they are not the product's reference authority. No upstream address case strings, model weights, or corpus rows were copied for this research. All proposed imports remain optional and asset-specific.

## What to take from existing suites

| Primary source | Useful concept | Independent design response |
| --- | --- | --- |
| [Doorplate suite specification](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmark-suite.md) | Separate parse comparisons from formatting and key stability; report ordinary/challenge/hand-authored strata; use blind label audits and immutable versions. Its source-field construction makes labels explainable. | Give our suite distinct parse, normalization, and matching contracts. Author original core and challenge cases. Report source-field/generated views separately from naturally entered text. The upstream `natural` name does not make rendered records naturally entered observations. |
| [GeoSearch 2023 benchmark](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark) | Synthetic corruptions reflect 21 error/variation categories mined from geocoding logs; street/component diversity matters beyond row count. | Give original challenge cases named phenomena and transformation history. Preserve a family identifier across generated variants and split by family before expansion. A corruption suite measures robustness to its stated transformations, not the frequency of those errors in production. |
| [usaddress labeling tests](https://github.com/datamade/usaddress/blob/main/tests/test_labeling.py) | Regression examples and training examples may intentionally overlap; source tests explicitly direct new formats into both. Fine and coarse comparisons differ. | Keep regression/conformance examples separate from heldout claims. Publish exposure status as known/possible/unknown, with evidence. Coarse agreement and fine-role agreement remain separate metrics. |
| [libpostal training documentation](https://github.com/openvenues/libpostal#training-data) | Structured-source rendering, component dropout, abbreviations, multilingual and country-aware formats provide scale. Different source shards have different licenses. | Keep a generated weak-supervision corpus with its own identity and score tables. Pin generator/seed/source record/renderer/transformation. Never market rendered labels as independent human transcription or a universally unseen test. |
| [Senzing model evaluation](https://github.com/Senzing/libpostal-data) | Versioned multilingual test revisions, public/private coverage differences, and support-derived hard examples. | Every corpus release names exact assets and omissions. Never apply a private full-test headline to the smaller public asset. Keep error-discovered challenges useful but distinct from population estimates. |
| [Deepparse dataset documentation](https://github.com/GRAAL-Research/deepparse-address-data) | Clean versus incomplete inputs, countries held out from model training, and a targeted unit/house-number hyphen ambiguity set. | Input completeness and annotation completeness are independent axes. Country transfer requires an engine-specific exposure declaration. Include original ambiguity cases and refuse a global meaning for USA-specific role names. |

These are design judgments informed by the cited suites. No upstream choice of weights, percentage targets, or scorer normalization is inherited automatically.

## Proposed corpus families for this product

**Authored core.** Original fictional cases provide reviewable, complete references for ordinary street/locality/state/postal forms, missing components, punctuation, leading-zero ZIPs, units, and explicit non-address/refusal behavior. Each case records its authoring method and annotation coverage. These examples establish protocol/scorer behavior; they are too small and intentionally chosen to estimate population accuracy.

**Authored challenge.** Original cases cover repeated/nonadjacent roles, numbers inside street names, direction words used as names, units before the street, hyphenated/fractional house numbers, multiword locality/region values, PO boxes and route forms, Unicode and byte offsets, and unsupported locale/task boundaries. Cases can share a phenomenon without sharing a source family. Challenge averages are diagnostic and must not be presented as natural incidence estimates.

**Generated weak supervision.** A deterministic renderer produces inputs from original component vocabularies/templates. Its source fields supply labels, with explicit limits on ambiguous constructions. Preserve every family, seed and transformation; do not count ten renderings of one source record as ten independent source families. Hold out template families before generation. Generated complete labels mean complete under the renderer's declared ontology, not proof of real-world address validity.

**Future naturally entered panel.** Add only after obtaining rights and a documented collection/annotation process, with geographic/time/domain strata, independent blind review, adjudication, and frozen heldouts. Public-source addresses rendered from database columns do not fill this gap. Private local panels may use the same contracts without redistribution.

**Future locale extensions.** Use explicit country, language and script metadata; native local ontologies; and deliberately versioned mappings. USA unit/direction/state heuristics are not universal. Formatting metadata can guide authored locale cases but cannot establish token-level reference labels for arbitrary raw text.

Keep these families as interchangeable named corpora. Publish per-corpus and per-stratum results first. A combined score needs a declared target population and weighting policy; it is not justified by merely summing rows.

## Optional upstream asset inventory

### Doorplate v1

The [manifest](https://github.com/jeremeybingham/doorplate/blob/main/benchmarks/suite/v1/MANIFEST.md) records 19,586 records: 16,001 `natural`, 2,585 `hard`, 1,000 `hand`; these are partitions of the same suite. `compare.jsonl.gz` and `doorplate.jsonl.gz` share IDs and must not be counted as independent corpora. It records build commit `0a2f1fc748f8747d926490288fac38e19421ae44`, seed `75001`, and compare gzip SHA-256 `2336f0996f2d044d56d69467f6f3ea7d33a4a64a680decb43179651bf006b430`.

Comparison records have `id`, `input`, ordered `tokens: [[value, label], ...]`, `stratum`, `style`, `mods`, `type`, `state`, `source`, `tags`. The separate track contains structured fields, alternate styles, standardized components, and USPS lines. The public specification describes field-supervised generation and changed numbers/units; these are generated views, including the stratum called natural. Its scorer folds several roles and excludes punctuation-only tokens; importing the data does not require adopting that scoring policy. [Record and scoring specification](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmark-suite.md)

The repository is [MIT OR Apache-2.0](https://github.com/jeremeybingham/doorplate). Its specification names NAD, TIGER, authored templates, and private aggregate sources. Before mirroring, preserve the actual asset license/provenance chain; a repository code license or a claim of anonymization does not by itself document all source rights. Initial posture: local optional data, no mirrored rows.

### usaddress XML collections

Primary files are `training/labeled.xml`, and `measure_performance/test_data/{labeled.xml,simple_address_patterns.xml,synthetic_osm_data.xml,synthetic_clean_osm_data.xml,multi_word_state_addresses.xml,us50_test_tagged.xml}`. The upstream [training guide](https://github.com/datamade/usaddress/blob/main/training/README.md) identifies canonical training data, while [tests/test_labeling.py](https://github.com/datamade/usaddress/blob/main/tests/test_labeling.py) shows which sets are used for regression and how some fine labels are folded for US50. Public presence is not evidence of heldout status.

The [XML format](https://github.com/datamade/usaddress/blob/main/training/labeled.xml) is `AddressCollection` containing `AddressString` elements with ordered label-named children. Labels can repeat; punctuation and whitespace can occur in child text/tails. A lossless local converter should retain the reconstructed element text and raw source digest, rather than silently joining tokens with new spaces. The [repository license is MIT](https://github.com/datamade/usaddress/blob/main/LICENSE); historical synthetic/source-derived files still need asset-level provenance in an imported manifest. Include as exposed regression/development evidence if used; do not call it an independent test of usaddress or ports sharing its model.

### GeoSearch / Geocoding Address Parsing Benchmark

Primary assets are [`benchmark_dataset/{train,dev,test}.txt`](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark/tree/main/benchmark_dataset). Upstream describes approximately 239,000 synthetic USA records, with unique component combinations and injected variations. Its street-oriented eight-role ontology does not establish unit/recipient/other-role coverage. [Benchmark description](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark)

The [upstream reader](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark/blob/main/utils.py) uses the sentinel `-END- -X- -X-` to end an address; blank lines do not end records. Token is the first whitespace column, BIO tag is the last. A converter must preserve original tokens/tags and construct a single-space input explicitly, recording that original keystroke whitespace is unavailable. Roles are `HOUSENUM`, `PREDIRECTIONAL`, `STREET`, `ROADTYPE`, `POSTDIRECTIONAL`, `CITY`, `STATE`, `POSTAL`; validate BIO transitions rather than repairing them silently. The [test asset](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark/blob/main/benchmark_dataset/test.txt) confirms this format.

No license file or redistribution grant was established in the inspected upstream repository. Use a private/local plugin only until rights are clarified; do not bundle or mirror raw files. The previous project's DEV60,522/TEST30,622 figures describe its audited local intake, not an independently verified count for every upstream revision. Source label validity, duplicate rows, source-family overlap, and model exposure need fresh audit.

### libpostal and Senzing

libpostal's [training documentation](https://github.com/openvenues/libpostal#training-data) identifies dated compressed TSV shards with `language`, `country`, `address` columns, and source-specific terms: OSM-derived shards are ODbL, GeoPlanet-derived data is CC-BY, and OpenAddresses-derived shards retain varying upstream terms. The [training-set pointer](https://github.com/openvenues/libpostal/blob/master/current_parser_training_set) read `20170304` during this review. Pin the dated assets and hashes, never the moving pointer. This is training/exposure and generated-workload material, not an unseen accuracy corpus.

Senzing publishes [`files/tests/v1.2.0/test_data.csv`](https://github.com/Senzing/libpostal-data/blob/main/files/tests/v1.2.0/test_data.csv) and an older v1.1.0 test directory, plus separate training downloads. Its documentation says the full v1.2 test has 12,982 records from 88 countries, with just over 100 removed from publication for lack of permission. Those figures describe the upstream full suite, not a counted public CSV in this project. [Senzing evaluation and source terms](https://github.com/Senzing/libpostal-data), [Apache-2.0 repository license](https://github.com/Senzing/libpostal-data/blob/main/LICENSE)

Useful dimensions are country, script, difficult source families and revision regressions. Public support/example tests remain potentially exposed. Initial posture: optional future review, no model/training downloads or copied test rows.

### Three additional useful resources

| Resource | Why useful | Rights and initial decision |
| --- | --- | --- |
| [Deepparse structured multinational data](https://github.com/GRAAL-Research/deepparse-address-data) and [worldwide-addresses](https://huggingface.co/datasets/deepparse/worldwide-addresses) | The legacy set separates clean/incomplete data and country-transfer evaluation. The newer Parquet collection exposes `Address`, whitespace-aligned `Tags`, and ISO639-3 `Language`; useful for schema and multilingual workload coverage. | Legacy publisher states MIT; newer card states CC-BY-4.0. Both derive from libpostal, so retain source lineage and resolve asset-level terms before mirroring. Neither is an independent new natural-entry population. Optional later plugin; no pickle loading or data download in CI. |
| [OpenCage address-formatting testcases](https://github.com/OpenCageData/address-formatting/tree/master/testcases) | Country-specific structured-input/expected-display cases inform locale ordering, missing fields, and formatting separation. `countries`, `abbreviations`, and `other` are distinct test groups. | [MIT](https://github.com/OpenCageData/address-formatting/blob/master/LICENSE.txt). Useful for a future formatting task after preserving notices. These are formatting references, not NER gold; do not reverse-render them and call the result naturally entered parsing data. |
| [Google libaddressinput metadata/tests](https://github.com/google/libaddressinput) | Required fields, administrative levels, country-specific validation and language metadata help design locale-aware schema/conformance tests. `testdata/countryinfo.txt` supplies test metadata, rather than an address-parse leaderboard. | Upstream distinguishes Apache-2.0 code from CC-BY-4.0 data. Review the pinned asset's notices. Useful future metadata/validation task; withhold from parse accuracy totals. |

**BPEmb is not another address corpus.** Deepparse's [parser documentation](https://deepparse.org/parser.html) identifies fastText/BPEmb model choices and preprocessing. Compare those engine variants on a fixed corpus with their own model pins; do not count the embedding choice as independent dataset evidence.

**OpenAddresses is a source catalog, not a universally labeled parser test.** Its [license statement](https://github.com/openaddresses/openaddresses#license) explicitly says processed data retains source licenses; source-definition JSON is CC0 and the rest of the repository BSD-3-Clause. A future source-field-generated panel must choose individual licensed sources, preserve attribution/content hashes, and audit overlap with libpostal/other training sources. Generated labels remain weak supervision.

## Revisions inspected

The following are repository revision observations retrieved from the upstream GitHub commit interface on the research date. An importer must additionally hash each downloaded file; a repository revision alone is not a corpus content hash, and the Doorplate build revision above is distinct from the later repository head.

| Repository | Inspected revision |
| --- | --- |
| Doorplate | [`f6e1ece6589aaf9228b8621e45027d52b044e979`](https://github.com/jeremeybingham/doorplate/tree/f6e1ece6589aaf9228b8621e45027d52b044e979) |
| usaddress | [`aa7699b53a0843fc443f9e87285b88cbd9eaf50a`](https://github.com/datamade/usaddress/tree/aa7699b53a0843fc443f9e87285b88cbd9eaf50a) |
| GeoSearch | [`424f94167c21d1ad3f8e70b50a75174f68dfe1f0`](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark/tree/424f94167c21d1ad3f8e70b50a75174f68dfe1f0) |
| Senzing libpostal-data | [`5113929832ac06619d18a4816f78a90fef8cc7a3`](https://github.com/Senzing/libpostal-data/tree/5113929832ac06619d18a4816f78a90fef8cc7a3) |
| Deepparse legacy data | [`ecb77e4ec86d82b4ed61d973adc67f5b6a7dd150`](https://github.com/GRAAL-Research/deepparse-address-data/tree/ecb77e4ec86d82b4ed61d973adc67f5b6a7dd150) |
| OpenCage address-formatting | [`cbf23487c13ad437cadab0083ef79fe5f1d1823e`](https://github.com/OpenCageData/address-formatting/tree/cbf23487c13ad437cadab0083ef79fe5f1d1823e) |
| libaddressinput | [`81eb9628382b07d371d8ea0b11badf7de3857fd5`](https://github.com/google/libaddressinput/tree/81eb9628382b07d371d8ea0b11badf7de3857fd5) |

The previous project's expanded USA corpus and unlabeled private listing stress sample remain local evidence. An unlabeled workload has no accuracy denominator. Its private listing archive and raw extracts have no established redistribution grant and are excluded from this product.
