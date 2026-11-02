"""Sample the deepparse-hf-us parsing corpus from its pinned Hugging Face parquet files.

    python3 tools/prepare_deepparse_hf.py --parquet-dir DIR --out OUT     # verified local copies (recommended)
    python3 tools/prepare_deepparse_hf.py --remote --out OUT              # range reads at the pinned revision

Recipe: datasets/deepparse-hf-us/recipe.json (revision, file sizes and SHA-256, seed, tag map, strata). The data
is not bundled: this writes OUT/cases.jsonl and OUT/manifest.json locally. `--parquet-dir` verifies every file's
size and SHA-256 before reading. `--remote` reads only the sampled row groups over HTTPS from the immutable
revision URL; whole-file hashes are then unverified, which the manifest records. Needs pyarrow (and fsspec with
aiohttp for --remote); the benchmark core stays dependency-free.

Sampler (deterministic for a seed and file set): for each chunk in order, draw row groups with
random.Random(seed).sample, then candidates from each row group, and keep up to the per-group quota of English
rows whose tags align with the words, that tag a StreetName and whose text was not already kept. Rows carrying an
unmapped tag count toward the quota (stratum "extra") but are not emitted. References are partial: a field is
supplied only when tagged, so an untagged unit is unknown, not absent. The whole street line is one `road` value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "datasets/deepparse-hf-us/recipe.json"


def reference_for(words, tags, recipe):
    """(stratum, reference) for one aligned row, or None when the row is not admissible."""
    if len(words) != len(tags) or "StreetName" not in tags:
        return None
    unknown = set(tags) - set(recipe['tags']) - set(recipe['unmapped_tags'])
    if unknown:
        raise ValueError('unknown publisher tags: ' + ', '.join(sorted(unknown)))
    fields, previous = {}, None
    for word, tag in zip(words, tags):
        role = recipe["tags"].get(tag)
        if role is None:
            previous = None
            continue
        if role == previous:
            fields[role][-1] += " " + word
        else:
            fields.setdefault(role, []).append(word)
        previous = role
    if set(tags) & set(recipe["unmapped_tags"]):
        stratum = "extra"
    elif all(r in fields for r in ("house_number", "road", "city", "state", "postcode")):
        stratum = "full"
    else:
        stratum = "partial"
    return stratum, dict(coverage="partial", fields=fields, spans=[], tokens=[], spans_coverage="none", tokens_coverage="none")


def sample(open_file, recipe):
    """Yield (native_id, stratum, text, reference) in sampler order; open_file(path) returns a binary file."""
    import pyarrow.parquet as pq
    s = recipe["sampler"]
    rng, seen = random.Random(s["seed"]), set()
    for chunk, spec in enumerate(recipe["source"]["files"]):
        with open_file(spec["path"]) as handle:
            parquet = pq.ParquetFile(handle)
            for group in sorted(rng.sample(range(parquet.metadata.num_row_groups), s["row_groups_per_chunk"])):
                table = parquet.read_row_group(group, columns=["Address", "Tags", "Language"])
                rows = table.take(rng.sample(range(table.num_rows), s["candidates_per_row_group"])).to_pylist()
                kept = 0
                for row in rows:
                    if kept >= s["rows_per_row_group"]:
                        break
                    if row["Language"] != s["language"] or row["Address"] in seen:
                        continue
                    result = reference_for(row["Address"].split(), row["Tags"], recipe)
                    if result is None:
                        continue
                    seen.add(row["Address"])
                    yield f"c{chunk}g{group:02d}-{kept:04d}", result[0], row["Address"], result[1]
                    kept += 1


def corpus_row(native_id, stratum, text, reference):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"family": "exact-input-proxy:" + digest, "id": "deepparse-hf-us:" + native_id, "origin": "source-field-supervised",
            "reference": reference, "split": "evaluation", "subsets": [stratum], "text": text}


def manifest(recipe, data, verified):
    sha = hashlib.sha256(data).hexdigest()
    source = recipe["source"]
    return {"schema": "address-benchmark.corpus/v1", "id": recipe["id"], "version": recipe["version"], "country": "US", "locale": "en-US",
            "task": "parse", "ontology": "address-benchmark.us-roles/v2",
            "provenance": {"source": source["dataset"], "upstream_revision": source["revision"],
                           "files": source["files"], "file_hashes": "verified" if verified else "unverified (remote row-group reads)"},
            "license": {"spdx": recipe["license"]["spdx"], "redistribution": "allowed", "notice": recipe["license"]["attribution"]},
            "construction": ["Sampled by tools/prepare_deepparse_hf.py from the pinned recipe (seed, row groups, quota)",
                             "Partial coarse references from the publisher word tags; the street line is one road value; extra-stratum rows not emitted"],
            "annotation_policy": "docs/spec/annotations.md#external-and-private-corpora",
            "exposure": {"status": "public; libpostal training lineage (libpostal-family parsers are in-sample)",
                         "history": ["Formatted from libpostal training data per the dataset card"]},
            "family_policy": "Exact-input hash proxy only; not independent source families.",
            "split_policy": "One evaluation split sampled from the publisher's single US config.",
            "resources": [{"path": "cases.jsonl", "sha256": sha, "bytes": len(data)}]}


def local_opener(directory, recipe):
    for spec in recipe["source"]["files"]:
        path = directory / Path(spec["path"]).name
        if path.stat().st_size != spec["bytes"]:
            raise SystemExit(f"{path}: size differs from the recipe")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 24), b""):
                digest.update(block)
        if digest.hexdigest() != spec["sha256"]:
            raise SystemExit(f"{path}: SHA-256 differs from the recipe")
    return lambda name: (directory / Path(name).name).open("rb")


def remote_opener(recipe):
    import fsspec
    base = recipe["source"]["dataset"] + "/resolve/" + recipe["source"]["revision"] + "/"
    fs = fsspec.filesystem("https", block_size=8 << 20)
    return lambda name: fs.open(base + name, "rb", cache_type="none")


def main():
    parser = argparse.ArgumentParser()
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--parquet-dir", type=Path)
    where.add_argument("--remote", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    recipe = json.loads(RECIPE.read_text())
    opener = remote_opener(recipe) if args.remote else local_opener(args.parquet_dir.resolve(), recipe)
    args.out.mkdir(parents=True)
    rows = [corpus_row(*item) for item in sample(opener, recipe) if item[1] != "extra"]
    data = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in rows).encode()
    (args.out / "cases.jsonl").write_bytes(data)
    (args.out / "manifest.json").write_text(json.dumps(manifest(recipe, data, not args.remote), indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rows": len(rows), "manifest": str(args.out / "manifest.json")}))


if __name__ == "__main__":
    main()
