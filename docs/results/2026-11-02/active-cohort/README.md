# Active parsing cohort — 2026-11-02

Eight configurations across seven source populations, including Deepparse full/partial and all four NAD views. The displayed cells contain **1,344,536 previously recorded predictions** over 168,067 source rows. These tables select the eight retained configurations from the original two verified nine-configuration batches. **No parser was rerun, no prediction was rescored, and no cell score or denominator changed for this presentation.** Row leaders are recalculated over the displayed cohort.

[Complete component comparison](delimiter/scores.html) · [Markdown](delimiter/scores.md) · [console text](delimiter/scores.txt) · [CSV](delimiter/scores.csv)

Separate policies: [literal strict](strict/scores.html), [streetline v1](streetline/scores.html), [streetline v2](streetline-v2/scores.html) and [fine token F1](fine-f1/scores.html).

The active cohort comprises our learned and default parsers, BoundaryBoys, Doorplate, usaddress, fastaddress, libpostal default and libpostal Senzing. Current setup tools generate these eight configurations. Retired integration code and setup dependencies have been removed. The [original full-cohort report](../complete-view-run/README.md) is an unchanged historical record, with its original nine-configuration counts and run identities.

Interpretation remains unchanged:

- Deepparse has libpostal training lineage; full/partial describe tagged input-field strata and both have partial reference coverage.
- NAD is a frozen official-API window sample rendered into clean/nocomma/expanded/noisy inputs, not the unshared screenshot population or nationally representative natural-entry data.
- Doorplate references include trailing field delimiters in 12,331/19,586 rows. Literal strict measures punctuation fidelity; delimiter/streetline are separate comparison policies. No gold or native values were repaired.
- Subsets overlap their parents. Public/development-exposed data do not establish unseen accuracy.
- V2 uses the earlier explicitly derived saved-prediction rescore; this cohort selection does not perform another rescore. Its [original derivation](../complete-view-run/streetline-v2/derivation.json) retains its full source scope and identity.

[Presentation provenance](presentation.json) records the selected configurations and hashes of the original scorecards. Historical results remain auditable; source inputs, private runtimes and model assets remain local.
