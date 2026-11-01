"""Separate real utility tracks with explicit scope and independent references."""
from pathlib import Path
import argparse
import gzip
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from address_benchmark.io import canonical, read_json, read_jsonl, sha256, write_json, write_jsonl
from address_benchmark.protocol import MATCH_ONTOLOGY, NORMALIZE_ONTOLOGY, TASK_ONTOLOGIES
from adapters.utilities import CLASS_PROFILE, IDENTITY_PROFILE, NORMAL_PROFILE, STABILITY_PROFILE, FIELDS

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--doorplate',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
source,out=args.source.resolve(),args.out.resolve()
out.mkdir(parents=True)

def make(name, task, profile, rows, provenance, notes, *, ours_only=False):
    folder=out/name;folder.mkdir()
    write_jsonl(folder/'cases.jsonl',rows)
    manifest=dict(schema='address-benchmark.corpus/v1',id=name,version='1.0.0',country='US',locale='en-US',task=task,ontology=TASK_ONTOLOGIES[task],profile=profile,
        provenance=provenance,license=dict(spdx='LicenseRef-Upstream-LocalEvaluation',redistribution='local-only'),
        construction=[notes],annotation_policy='docs/spec/utility-production.md',exposure=dict(status='public/development-exposed conformance and generated panels',history=['No independent unseen claim']),
        family_policy='Exact-input or publisher source-row proxy; independent family count unavailable',split_policy='Development-exposed evaluation; no heldout claim',
        resources=[dict(path='cases.jsonl',sha256=sha256(folder/'cases.jsonl'))])
    write_json(folder/'corpus.json',manifest)
    engines=[dict(name='rust-default',adapter='adapters.utilities:Factory',config=dict(library='address_normalizer',task=task,module_path=str(source/'packages/python/python')))]
    if not ours_only:
        engines.append(dict(name='doorplate',adapter='adapters.utilities:Factory',python=str(source/'.cache/us-python-library-matrix-20261029/venv/bin/python'),config=dict(library='doorplate',task=task)))
    write_json(folder/'engines.json',engines)
    write_json(folder/'plan.json',dict(schema='address-benchmark.plan/v1',name=name,engines='engines.json',tracks=[dict(id=name,corpus='corpus.json',output='results')],execution=dict(timeout=3600)))

def base(index,text,reference,subset,origin='publisher-fixture',payload=None):
    row=dict(id=str(index),text=text,family='exact-input-proxy:'+__import__('hashlib').sha256(text.encode()).hexdigest(),split='development-exposed',origin=origin,subsets=[subset],reference=reference)
    if payload is not None:row['payload']=payload
    return row

asset=args.doorplate.resolve()/'benchmarks/suite/v1/compare.jsonl.gz'
rows=[]
with gzip.open(asset,'rt') as f:
    for line in f:
        row=json.loads(line)
        rows.append(base(row['id'],row['input'],dict(coverage='complete',expected=row['type']),row['type'],origin='publisher-fixture' if row['stratum']=='hand' else 'source-field-supervised'))
make('publisher-classification','classify',CLASS_PROFILE,rows,dict(source='https://github.com/jeremeybingham/doorplate',upstream_revision='0a2f1fc748f8747d926490288fac38e19421ae44',asset_sha256=sha256(asset)),
     'Publisher generator type assertions; neutral standard->street and rural_route->rural mappings. Native Doorplate street includes highway; subtype disagreement needs taxonomy review, not automatic error attribution.')

asset=source/'.cache/us-benchmark-expansion-20261028/kit-v2/cases.jsonl'
normal,excluded=[],[]
for row in read_jsonl(asset):
    if row['task']!='record_normalization':continue
    reason=None
    if row['input_kind']!='text':reason='structured input: requires separate input-mode adapter'
    elif set(row['expected'])!=set(FIELDS):reason='partial supplied-field assertion: not a complete five-field reference'
    elif row.get('options',{}):reason='custom long-hand profile not supported by this native projection'
    if reason:
        excluded.append(dict(id=row['id'],reason=reason));continue
    normal.append(base(row['id'],row['input'],dict(coverage='complete',values=[canonical(row['expected']).decode('utf-8')]),'complete-five-field'))
make('normalized-components','normalize',NORMAL_PROFILE,normal,dict(source='https://github.com/GreenBuildingRegistry/usaddress-scourgify',upstream_revision='cf66bdc42aebc57d48fe41e32e108fdcde347e3c',asset_sha256=sha256(asset)),
     'Only complete default-profile text assertions; all other normalization assertions explicitly inventoried. Exact canonical JSON of five native normalized fields after a uniform uppercase line renderer. This is component projection, not native formatter accuracy.')
write_json(out/'normalization-intake.json',dict(total_assertions=len(normal)+len(excluded),included=len(normal),excluded=excluded))

asset=Path(__file__).resolve().parents[1]/'examples/corpora/us-identity/cases.jsonl'
make('identity-conformance','match',IDENTITY_PROFILE,list(read_jsonl(asset)),dict(source='Original fictional authored identity controls',upstream_revision='authored-v1',asset_sha256=sha256(asset)),
     'Independent authored same/distinct delivery-unit pairs. This is exposed conformance, not real-world entity-matching population accuracy.')

asset=source/'.cache/us-common-matrix-20261101/frozen-v1/speed.jsonl'
texts=[row['input'] for row in read_jsonl(asset)]
provenance=dict(source='Input-only shared public comparison workload',upstream_revision='frozen-v1',asset_sha256=sha256(asset))
row=base('panel','',dict(coverage='complete',checks=['repeat','scalar_batch','idempotence']),'real-input-panel',payload=dict(texts=texts))
make('stability-common','stability',STABILITY_PROFILE,[row],provenance,'Actual scalar/repeat/native-public-batch/re-normalized observations over the fixed 1024-string panel; stable wrong outputs do not imply accuracy.')
row=base('panel','',dict(coverage='complete',checks=['repeat','scalar_batch','scalar_stream','scalar_chunked','idempotence']),'real-input-panel',payload=dict(texts=texts))
make('stability-stream-chunk','stability',STABILITY_PROFILE,[row],provenance,'Actual supported public stream/chunk outputs and retained trailing chunk/order; no emulated stream for an unsupported competitor.',ours_only=True)
print(json.dumps(dict(root=str(out),classification_rows=len(rows),normalization_rows=len(normal),normalization_excluded=len(excluded),stability_inputs=len(texts))))
