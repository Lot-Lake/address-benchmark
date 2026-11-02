import importlib.util
import io
import json
from pathlib import Path
import random
import unittest
import tracemalloc

from address_benchmark.corpus import check_manifest, check_reference
from address_benchmark.scoring import normalize

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_nad", ROOT / "tools/render_nad.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
COLUMNS = ["State", "Add_Number", "AddNum_Pre", "AddNum_Suf", "St_PosMod", "Building", "Floor", "Zip_Code", "Post_City",
           "Inc_Muni", "St_PreMod", "St_PreTyp", "St_PreSep", "St_Name", "St_PosTyp", "St_PreDir", "St_PosDir", "Unit", "NAD_Source"]


def nad(**values):
    record = dict.fromkeys(COLUMNS, "")
    record.update(State="UT", Add_Number="123", Zip_Code="84999", Post_City="Exampleville", St_Name="Alder",
                  St_PosTyp="Street", St_PreDir="North", NAD_Source="Fictional County")
    record.update(values)
    return record


def csv_text(records):
    lines = [",".join(COLUMNS)] + [",".join(r[c] for c in COLUMNS) for r in records]
    return io.StringIO("\n".join(lines) + "\n")


class NadRenderTests(unittest.TestCase):
    def test_hyphenated_unit_identifier_is_preserved(self):
        self.assertEqual(tool.split_unit('Apt B-2'), ('APT', 'B-2'))
        rec = tool.admit(nad(Unit='APT B-2'))
        line, fields = tool.render(rec, 'expanded', random.Random(1))
        self.assertIn('APARTMENT B-2', line)
        self.assertEqual(fields['unit'], ['APARTMENT B-2'])

    def test_sampling_memory_does_not_grow_with_all_admitted_rows(self):
        def lines():
            yield ','.join(COLUMNS) + '\n'
            for i in range(20000):
                row = nad(Add_Number=str(100 + i))
                yield ','.join(row[c] for c in COLUMNS) + '\n'
        tracemalloc.start()
        try:
            rows, meta = tool.generate(lines(), per_state=8, seed='bounded', min_state=500)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(len(rows), 8)
        self.assertEqual(meta['UT']['usable'], 20000)
        self.assertLess(peak, 8 * 1024 * 1024)
        self.assertEqual(tool.generate(lines(), per_state=8, seed='bounded', min_state=500)[0], rows)

    def test_sampling_rejects_nonpositive_limits(self):
        with self.assertRaisesRegex(ValueError, 'positive'):
            tool.generate(csv_text([nad()]), per_state=-1, seed='x', min_state=1)

    def test_admission_folds_pub28_and_rejects_unusable_records(self):
        rec = tool.admit(nad(Unit="Apartment 5"))
        self.assertEqual((rec["predir"], rec["street"], rec["suffix"], rec["unit"]), ("N", "ALDER", "ST", ("APT", "5")))
        self.assertIsNone(tool.admit(nad(State="PR")))
        self.assertIsNone(tool.admit(nad(AddNum_Suf="A")))
        self.assertIsNone(tool.admit(nad(Zip_Code="849")))
        self.assertIsNone(tool.admit(nad(St_Name="Alder St", St_PosTyp="")), "type stored in the name")
        self.assertIsNone(tool.admit(nad(Unit="Apt 5 Rear Side")))

    def test_every_stratum_renders_literal_complete_references(self):
        rec = tool.admit(nad(Unit="Apt 5"))
        for stratum in tool.STRATA:
            for seed in range(30):
                line, fields = tool.render(rec, stratum, random.Random(seed))
                reference = dict(coverage="complete", fields=fields, spans=[], tokens=[], spans_coverage="none", tokens_coverage="none")
                check_reference(reference, line)
                collapsed = normalize(line)
                for values in fields.values():
                    for value in values:
                        self.assertIn(normalize(value), collapsed, (stratum, line, value))

    def test_expanded_spells_out_and_clean_uses_title_case(self):
        rec = tool.admit(nad(Unit="Apt 5"))
        line, fields = tool.render(rec, "expanded", random.Random(1))
        self.assertEqual(line, "123 NORTH ALDER STREET APARTMENT 5, EXAMPLEVILLE, UT 84999")
        self.assertEqual(fields["road"], ["NORTH ALDER STREET"])
        line, fields = tool.render(rec, "clean", random.Random(1))
        self.assertEqual(line, "123 N Alder St Apt 5, Exampleville, UT 84999")
        self.assertEqual(fields["unit"], ["Apt 5"])

    def test_noisy_drops_remove_the_field_from_the_reference(self):
        rec = tool.admit(nad())
        seen = set()
        for seed in range(200):
            line, fields = tool.render(rec, "noisy", random.Random(seed))
            seen.add(("state" in fields, "postcode" in fields))
            self.assertEqual("84999" in line, "postcode" in fields)
        self.assertTrue({(True, True), (True, False), (False, True)} <= seen)

    def test_generation_is_deterministic_per_state_and_manifest_is_admissible(self):
        records = [nad(Add_Number=str(100 + i), St_Name="Alder" if i % 2 else "Birch") for i in range(12)]
        first, meta = tool.generate(csv_text(records), per_state=8, seed="s", min_state=5)
        second, _ = tool.generate(csv_text(records), per_state=8, seed="s", min_state=5)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertEqual({r["origin"] for r in first}, {"generated"})
        self.assertEqual(meta["UT"]["providers"], {"Fictional County": 12})
        self.assertEqual(tool.generate(csv_text(records), per_state=8, seed="s", min_state=13)[0], [])
        data = "".join(json.dumps(r) + "\n" for r in first).encode()
        check_manifest(tool.manifest(data, "0" * 64, meta, {"seed": "s"}))


if __name__ == "__main__":
    unittest.main()
