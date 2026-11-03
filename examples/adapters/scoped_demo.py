"""Input-only synthetic gain/loss control, intentionally not a real parser."""
from address_benchmark.adapters import DemoParser
from address_benchmark.io import require


class Parser(DemoParser):
    def __init__(self, config):
        require(set(config) <= {"variant", "artifact_files"} and "variant" in config and config["variant"] in ("incumbent", "candidate"), "select synthetic variant")
        super().__init__({})
        self.metadata["artifact_files"] = config.get("artifact_files", [])
        self.variant = config["variant"]
        self.metadata["version"] = "synthetic-" + self.variant

    def parse(self, request):
        result = super().parse(request)
        # Authored, input-only bugs produce one gain and one loss. No references,
        # case IDs, paths, cohorts or source annotations are available here.
        prefix = "1 " if self.variant == "incumbent" else "2 "
        if result["status"] == "ok" and request.text.startswith(prefix):
            for item in result["evidence"]:
                if item["native_role"] == "house_number":
                    item["value"] = "999"
            result["native"]["synthetic_bug"] = True
        return result
