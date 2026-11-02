import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest

from address_benchmark.corpus import check_manifest, check_reference

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_deepparse_hf", ROOT / "tools/prepare_deepparse_hf.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
RECIPE = json.loads((ROOT / "datasets/deepparse-hf-us/recipe.json").read_text())


class FakeTable:
    def __init__(self, rows):
        self.rows, self.num_rows = rows, len(rows)

    def take(self, indices):
        return FakeTable([self.rows[i] for i in indices])

    def to_pylist(self):
        return list(self.rows)


class FakeParquet:
    groups = {}

    def __init__(self, handle):
        self.metadata = types.SimpleNamespace(num_row_groups=len(self.groups))

    def read_row_group(self, group, columns):
        return FakeTable(self.groups[group])


class DeepparseRecipeTests(unittest.TestCase):
    def test_recipe_pins_revision_files_and_license(self):
        self.assertRegex(RECIPE["source"]["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(len(RECIPE["source"]["files"]), 4)
        for item in RECIPE["source"]["files"]:
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(item["bytes"], 0)
        self.assertEqual(RECIPE["license"]["spdx"], "CC-BY-4.0")

    def test_reference_is_partial_with_one_street_line(self):
        words = "12 north main street springfield il 62701".split()
        tags = ["StreetNumber", "StreetName", "StreetName", "StreetName", "Municipality", "Province", "PostalCode"]
        stratum, reference = tool.reference_for(words, tags, RECIPE)
        self.assertEqual(stratum, "full")
        self.assertEqual(reference["fields"], {"house_number": ["12"], "road": ["north main street"], "city": ["springfield"],
                                               "state": ["il"], "postcode": ["62701"]})
        self.assertEqual(reference["coverage"], "partial")
        check_reference(reference, " ".join(words))

    def test_strata_and_inadmissible_rows(self):
        with self.assertRaisesRegex(ValueError, 'unknown publisher tags: NewTag'):
            tool.reference_for(['main', 'example'], ['StreetName', 'NewTag'], RECIPE)
        self.assertEqual(tool.reference_for(["main", "st"], ["StreetName", "StreetName"], RECIPE)[0], "partial")
        self.assertEqual(tool.reference_for(["main", "st", "kings"], ["StreetName", "StreetName", "County"], RECIPE)[0], "extra")
        self.assertIsNone(tool.reference_for(["12", "springfield"], ["StreetNumber", "Municipality"], RECIPE))
        self.assertIsNone(tool.reference_for(["12"], ["StreetNumber", "StreetName"], RECIPE))

    def test_sampler_quota_counts_extra_rows_skips_duplicates_and_is_deterministic(self):
        recipe = json.loads(json.dumps(RECIPE))
        recipe["source"]["files"] = recipe["source"]["files"][:1]
        recipe["sampler"].update(row_groups_per_chunk=1, rows_per_row_group=3, candidates_per_row_group=6)
        row = lambda text, tags, language="eng": {"Address": text, "Tags": tags, "Language": language}
        FakeParquet.groups = {0: [row("1 a st", ["StreetNumber", "StreetName", "StreetName"]),
                                  row("1 a st", ["StreetNumber", "StreetName", "StreetName"]),
                                  row("2 b st kings", ["StreetNumber", "StreetName", "StreetName", "County"]),
                                  row("3 c st", ["StreetNumber", "StreetName", "StreetName"], "fra"),
                                  row("4 d st", ["StreetNumber", "StreetName", "StreetName"]),
                                  row("5 e st", ["StreetNumber", "StreetName", "StreetName"])]}
        fake = types.ModuleType("pyarrow.parquet")
        fake.ParquetFile = FakeParquet
        package = types.ModuleType("pyarrow")
        package.parquet = fake
        modules = {"pyarrow": package, "pyarrow.parquet": fake}
        saved = {k: sys.modules.get(k) for k in modules}
        sys.modules.update(modules)
        try:
            opener = lambda name: contextlib.nullcontext(io.BytesIO())
            first = list(tool.sample(opener, recipe))
            second = list(tool.sample(opener, recipe))
        finally:
            for key, value in saved.items():
                if value is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = value
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertEqual(len({text for _, _, text, _ in first}), 3)
        self.assertNotIn("3 c st", [text for _, _, text, _ in first])

    def test_written_manifest_is_admissible_and_records_hash_verification(self):
        row = tool.corpus_row("c0g01-0000", "full", "12 main st", tool.reference_for(["12", "main", "st"], ["StreetNumber", "StreetName", "StreetName"], RECIPE)[1])
        data = (json.dumps(row) + "\n").encode()
        manifest = tool.manifest(RECIPE, data, verified=False)
        check_manifest(manifest)
        self.assertEqual(manifest["provenance"]["file_hashes"], "unverified (remote row-group reads)")
        self.assertEqual(manifest["license"]["spdx"], "CC-BY-4.0")
        self.assertEqual(row["subsets"], ["full"])


if __name__ == "__main__":
    unittest.main()
