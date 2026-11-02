from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from address_benchmark.corpus import input_requests, load_corpus
from address_benchmark.intake import align_native, parse_reference, records
from address_benchmark.io import read_json, sha256, write_json
from address_benchmark.ontologies import ONTOLOGY_V2, US_FINE
from address_benchmark.plan import load_plan, run_plan
from address_benchmark.adapters import Unavailable
from address_benchmark.production import Libpostal, NativeBatch, adapter_metadata, convert, role_map
from address_benchmark.protocol import Request, check_prediction, request_hash
from address_benchmark.scoring import normalize_delimiters, score_case

ROOT = Path(__file__).resolve().parents[1]


class IntakeTests(unittest.TestCase):
    def test_utf8_alignment_uses_input_only_and_keeps_native(self):
        text = "7 Café St, Café NY 00123"
        parts = [("7", "AddressNumber"), ("Café", "StreetName"), ("ST", "StreetNamePostType"), ("Café", "PlaceName")]
        spans = align_native(text, parts)
        self.assertEqual(spans[1], [2, 7])
        self.assertIsNone(spans[2])
        self.assertGreater(spans[3][0], spans[1][0])
        request = Request("a", text, request_hash(text), "US", "en-US")
        result = convert(request, parts, "usaddress", {"tokens": parts})
        meta = adapter_metadata("test", "usaddress", {})
        check_prediction(result, request, meta)
        self.assertEqual(result["evidence"][2]["value"], "ST")
        self.assertEqual(result["alignment"]["unresolved"], 1)

    def test_unplaced_tokens_are_preserved_as_explicit_unmapped(self):
        request = Request("a", "??", request_hash("??"), "US", "en-US")
        result = convert(request, [("??", None)], "usaddress", {"tokens": [["??", None]]})
        check_prediction(result, request, adapter_metadata("test", "usaddress", {}))
        self.assertEqual(result["evidence"][0]["native_role"], "__unplaced__")

    def test_fine_prefix_suffix_distinctions_preserved(self):
        self.assertNotEqual(US_FINE["StreetNamePreDirectional"], US_FINE["StreetNamePostDirectional"])
        self.assertNotEqual(US_FINE["AddressNumber"], US_FINE["AddressNumberPrefix"])


    def test_model_inventory_does_not_claim_every_mappable_role(self):
        meta=adapter_metadata('limited','neutral',dict(active_native_roles=['city']))
        self.assertEqual(meta['active_roles'],['city'])
        row=dict(id='x',family='x',split='dev',origin='authored',subsets=[],reference=dict(coverage='complete',fields={'recipient':['Example']},tokens=[],spans=[],tokens_coverage='none',spans_coverage='none'))
        request=Request('x','Example',request_hash('Example'),'US','en-US')
        case=score_case(row,convert(request,[],'neutral',{}),meta)
        self.assertEqual(case['unsupported_reference_roles'],['recipient'])

    def test_generic_source_name_is_not_promoted_to_building(self):
        self.assertEqual(role_map('neutral')['name'],'name')

    def test_partial_resource_override_keeps_unknown_roles_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = read_json(ROOT / "examples/corpora/us-core/manifest.json")
            resource = manifest["resources"][0]
            resource["external_path"] = str(ROOT / "examples/corpora/us-core" / resource.pop("path"))
            resource["coverage"] = "partial"
            manifest["license"]["redistribution"] = "local-only"
            path = Path(tmp) / "manifest.json"
            write_json(path, manifest)
            row = load_corpus(path)[1][0]
            self.assertEqual(row["reference"]["coverage"], "partial")
            self.assertEqual(row["reference"]["tokens_coverage"], "partial")

    def test_publisher_span_cannot_change_source_value(self):
        with self.assertRaisesRegex(ValueError, "span/value differs"):
            parse_reference("12 Main St", [("12", "AddressNumber")], [[1, 3]])

    def test_delimiter_policy_uniform_and_narrow(self):
        self.assertEqual(normalize_delimiters(" Main St., "), "main st.")
        self.assertNotEqual(normalize_delimiters("St."), normalize_delimiters("St"))
        self.assertNotEqual(normalize_delimiters("00123"), normalize_delimiters("0123"))

    def test_xml_preserves_tail_text_and_derives_token_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.xml"
            path.write_text('<AddressCollection><AddressString><AddressNumber>7</AddressNumber> <StreetName>Café Tree</StreetName>, <StateName>NY</StateName></AddressString></AddressCollection>')
            row = next(records(path, dict(format="usaddress-xml"), dict(id="xml")))
            self.assertEqual(row["text"], "7 Café Tree, NY")
            self.assertEqual(len(row["reference"]["tokens"]), 4)
            self.assertEqual(row["reference"]["fields"]["road"], ["Café Tree"])

    def test_external_paths_require_local_only_asset_policy(self):
        original = ROOT / "examples/corpora/us-core/manifest.json"
        for policy, expected in (("local-only", True), ("allowed", False)):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as tmp:
                manifest = read_json(original)
                resource = manifest["resources"][0]
                resource["external_path"] = str(original.parent / resource.pop("path"))
                manifest["license"]["redistribution"] = policy
                path = Path(tmp) / "manifest.json"
                write_json(path, manifest)
                if expected:
                    self.assertEqual(len(load_corpus(path)[1]), 8)
                else:
                    with self.assertRaisesRegex(ValueError, "local-only"):
                        load_corpus(path)

    def test_native_batch_exit_and_order_are_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "runtime.py"
            script.write_text('import json,sys,hashlib\nf=open(sys.argv[2],"x")\nfor line in open(sys.argv[1]):\n r=json.loads(line);f.write(json.dumps(dict(id=r["id"],input_sha256=hashlib.sha256(r["input"].encode()).hexdigest(),namespace="usaddress",labels=[dict(value=r["input"],label="ZipCode")],error=None))+"\\n")\nf.close()\n')
            adapter = NativeBatch(dict(name="test", namespace="usaddress", command=[sys.executable, str(script), "{inputs}", "{outputs}"]))
            request = Request("zip", "00123", request_hash("00123"), "US", "en-US")
            output = list(adapter.parse_many([request], root))
            self.assertEqual(output[0]["evidence"][0]["value"], "00123")
            self.assertEqual(read_json(root / "native-execution.json")["exit_code"], 0)



class PlanTests(unittest.TestCase):
    def fixture(self, tmp, execution=None):
        root = Path(tmp)
        corpus = root / "corpus"
        corpus.mkdir()
        original = ROOT / "examples/corpora/us-core"
        for name in ("manifest.json", "cases.jsonl"):
            (corpus / name).write_bytes((original / name).read_bytes())
        write_json(root / "engines.json", [dict(name="demo", adapter="demo")])
        plan = dict(schema="address-benchmark.plan/v1", name="test", engines="engines.json", tracks=[dict(id="core", corpus="corpus/manifest.json", output="results/core")], execution=execution or {})
        write_json(root / "plan.json", plan)
        return root / "plan.json"

    def test_json_plan_executes_and_verifies_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.fixture(tmp)
            result = run_plan(plan)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["tracks"][0]["verification"], "verified")
            self.assertEqual(read_json(Path(tmp) / "plan-results.json")["plan_sha256"], sha256(plan))

    def test_json_plan_rejects_implicit_types_and_unknown_settings(self):
        for settings in (dict(timing="false"), dict(timeout=True), dict(trials=3), dict(samples=0), dict(shell="echo forbidden")):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as tmp:
                path = self.fixture(tmp, settings)
                with self.assertRaises(ValueError):
                    load_plan(path)

    def test_json_plan_cannot_escape_directory_or_reuse_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.fixture(tmp)
            value = read_json(path)
            value["tracks"][0]["output"] = "../escape"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "escapes"):
                load_plan(path)


class LibpostalSetupTests(unittest.TestCase):
    BASE = ("transliteration", "address_expansions", "numex")

    def layout(self, root, base=BASE, parser=True):
        root = Path(root)
        library = root / "libpostal.dylib"
        library.write_bytes(b"")
        data = root / "data"
        for name in base:
            (data / name).mkdir(parents=True)
        if parser:
            (data / "address_parser").mkdir(parents=True)
        return library, data

    def test_unavailable_names_each_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, data = self.layout(tmp, base=("transliteration",), parser=False)
            with self.assertRaises(Unavailable) as caught:
                Libpostal({"library": str(library), "data_dir": str(data)})
            message = str(caught.exception)
            for name in ("address_expansions", "numex", "address_parser"):
                self.assertIn(str(data / name), message)
            self.assertNotIn(str(data / "transliteration"), message)

    def test_unavailable_names_a_missing_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, data = self.layout(tmp)
            library.unlink()
            with self.assertRaisesRegex(Unavailable, "libpostal.dylib"):
                Libpostal({"library": str(library), "data_dir": str(data)})

    def test_parser_dir_holds_only_the_parser_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, data = self.layout(tmp, parser=False)
            parser = Path(tmp) / "model"
            with self.assertRaises(Unavailable) as caught:
                Libpostal({"library": str(library), "data_dir": str(data), "parser_dir": str(parser)})
            message = str(caught.exception)
            self.assertIn(str(parser / "address_parser"), message)
            self.assertNotIn(str(data / "address_parser"), message)

    def test_separate_parser_setup_uses_and_pins_the_selected_model(self):
        class Function:
            def __init__(self, result=True):self.result,self.calls=result,[]
            def __call__(self,*args):self.calls.append(args);return self.result
        class Library:
            def __getattr__(self,name):
                value=Function();setattr(self,name,value);return value
        with tempfile.TemporaryDirectory() as tmp:
            library,data=self.layout(tmp,parser=False)
            parser=Path(tmp)/'model';(parser/'address_parser').mkdir(parents=True)
            model=parser/'address_parser/parser.dat';model.write_bytes(b'fictional model')
            native=Library()
            with patch('ctypes.CDLL',return_value=native):
                adapter=Libpostal(dict(library=str(library),data_dir=str(data),parser_dir=str(parser),artifact_files=[str(library)]))
            self.assertEqual(native.libpostal_setup_datadir.calls,[(str(data).encode(),)])
            self.assertEqual(native.libpostal_setup_parser_datadir.calls,[(str(parser).encode(),)])
            self.assertIn(str(model),adapter.metadata['artifact_files'])
            adapter.close()
            self.assertEqual(len(native.libpostal_teardown_parser.calls),1)
            self.assertEqual(len(native.libpostal_teardown.calls),1)


if __name__ == "__main__":
    unittest.main()
