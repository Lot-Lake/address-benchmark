# Adapter examples

The runnable built-ins are demonstration controls. `demo` is a tiny US grammar;
`refusal` intentionally refuses every case; `demo-normalize`, `demo-keys` and
`demo-utility` exercise the other task contracts. No one should use their scores
as a production ranking.

`usaddress.json` invokes the optional real usaddress public `parse()` API.
Native tokens/roles and punctuation survive; native byte spans are unsupported.
Only this parser-specific real wrapper is included in v0.1. Other production
parsers can implement the protocol through Python entry points or commands.

## Existing address utility APIs

Adapter `python-callable` calls an installed public function without copying its
implementation. Use a separately licensed/installed runtime, selected with an
engine entry's optional `python` absolute interpreter path. No package/model is
automatically built or downloaded. For example, the existing address-normalizer
Python API exposes comparison keys:

```json
[
  {
    "name": "installed-normalizer-keys",
    "adapter": "python-callable",
    "config": {
      "callable": "address_normalizer:standardize_for_comparison",
      "task": "match",
      "profile": "address-benchmark.delivery-unit-key-equality/v1",
      "kwargs": {},
      "artifact_files": []
    }
  }
]
```

Select `us-identity/manifest.json`. This compares the API's actual keys to
independent pair labels. It does not rewrite them or privilege that engine.
Supply extra model/data files in `artifact_files` if installation metadata does
not cover them; provide build/compiler flags and dependency locks separately.

For the other operations, choose the right task/corpus/profile **before** running:

| Public function(s) in the source library | Adapter use / measurement |
| --- | --- |
| `standardize_address`, `normalize_city`, `normalize_state`, `normalize_zip`, `normalize_directional`, `normalize_street_type`, `normalize_unit_type`, `normalize_street_name`, `normalize_street` | `task: normalize`, named profile, `kwargs` for requested output mode; authored references must specify that function's requested target rules. The included uppercase control is not that library's USPS profile. |
| `format_address_components` | `task: format`, `constructor: ParsedAddress`; `payload.fields` roles must match constructor names. Repeated fields unsupported by this dictionary-based API are explicit, not merged silently. |
| `classify_address`, `get_address_type`, `is_po_box`, `is_intersection_address` | `task: classify`; exact typed result under the chosen taxonomy. Boolean predicates need their own corpus profile. |
| `zip_to_state` | `task: infer`, `result_field: state`; preserve null for unknowns, no geographic validation claim. |
| `generate_variants`, `get_suggestions` | `task: variants`; predeclare limit/mode in `kwargs`, use an independently reviewed closed inventory. Open-ended ranked suggestions need a different scorer. |
| `validate_address`, `analyze_address` | `task: diagnostics`; native dataclasses become JSON for audit. Their full output needs a matching independently defined reference profile or an explicit versioned native→neutral diagnostic adapter; it cannot be silently reinterpreted as deliverability. |
| `extract_house_number`, `extract_street_name` | `task: extract`, exact typed component-extraction profile, or a richer parsing adapter. The bundled house-number control profile preserves leading zeros/fractions. |
| `standardize_address` + `normalize_batch`, `normalize_stream`, `normalize_chunked` | `task: stability`, `batch_callable: normalize_batch`, optional `stream_callable: normalize_stream`, `chunked_callable: normalize_chunked`, `chunk_size: 2`, same mode in `kwargs`; retain actual scalar/repeat/batch/stream/flattened-chunk/twice-normalized outputs. Only predeclared checks are scored; missing required streams invalidate the cell. |
| `parse_record`, `parse_structure_record`, `normalize_record`, `parse_records`, `normalize_records` | Rich evidence requires a dedicated native mapping/capability adapter. The generic callable wrapper does not claim to preserve a rich record's role hierarchy or source accounting. |

The adapter method remains named `parse(Request)` for all tasks. Only one task
and named profile are selected per configuration. The callable may take one text
input, two separate text calls for key generation, or a constructed structured
input for formatting. A declared profile is a test target; compatibility with a
different library's style is not assumed. Keep unsupported APIs out of timed
cells rather than substituting another operation.

## Non-Python runtime

`jsonl_demo.py` is an executable example of the persistent command protocol:

```sh
python3 tools/write_command_example.py --out /absolute/path/command.json
python3 -m address_benchmark run examples/corpora/us-core/manifest.json \
  --engines /absolute/path/command.json --out runs/command-001
```

It receives only requests on stdin, writes one prediction per stdout line, and
exits cleanly at EOF. Replace its implementation with a separately installed
Rust/Go/Node/C runtime. Metadata and model artifact declarations are mandatory.
Pipe/JSON work is inside command-bridge timing, while factory startup is outside.
