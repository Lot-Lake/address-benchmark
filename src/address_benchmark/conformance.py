"""Input-only structural probes, separate from accuracy gold."""
from .adapters import load_adapter
from .io import digest_bytes
from .protocol import Request, check_prediction, request_hash


def conform_adapter(spec, config):
    texts = ["12 Alder St, Exampleville, NY 00123", "7 Rue Café Ave, Sampleton, CA 90210", "",
             "Apt 4, 12 Alder St, Apt 5", "12 Main St.\nNorth Example, AA 00001-0002", "東京"]
    adapter = load_adapter(spec, config)
    task = adapter.metadata["tasks"][0]
    profile = adapter.metadata.get("profiles", [""])[0]
    if task == "match":
        texts = texts[:-2]
    statuses = []
    try:
        for i, text in enumerate(texts):
            other = text + " Apt 99" if task == "match" else None
            payload = {"fields": [dict(role="line1", value=text)]} if task == "format" else {"texts": [text, "12 Example Rd"]} if task == "stability" else None
            request = Request(f"probe-{i}", text, request_hash(text, other, payload), "US", "en-US", task, profile, other, payload)
            result = check_prediction(adapter.parse(request), request, adapter.metadata)
            statuses.append(result["status"])
    finally:
        if hasattr(adapter, "close"):
            adapter.close()
    return dict(status="conformant", probes=len(texts), statuses=statuses,
                scope="structural wire contract only; no semantic correctness certification", adapter=adapter.metadata)
