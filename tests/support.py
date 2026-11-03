"""Adversarial adapters for subprocess contract tests; never installed as plugins."""
import time
from address_benchmark.adapters import DemoParser


class WrongIdentity(DemoParser):
    def parse(self, request):
        output = super().parse(request)
        output["id"] = "wrong"
        return output


class Slow(DemoParser):
    def parse(self, request):
        time.sleep(5)
        return super().parse(request)


class Broken(DemoParser):
    def parse(self, request):
        raise RuntimeError("intentional per-row failure")


class MutatingArtifact(DemoParser):
    def __init__(self, config):
        super().__init__({})
        self.path = config["model"]
        self.metadata["artifact_files"] = [self.path]

    def parse(self, request):
        from pathlib import Path
        Path(self.path).write_bytes(b"changed while evaluating")
        return super().parse(request)


def canonical_text(text, mode="upper"):
    return " ".join(text.upper().split())


def canonical_batch(texts, mode="upper"):
    return [canonical_text(text, mode) for text in texts]


def canonical_stream(texts, mode="upper"):
    for text in texts:
        yield canonical_text(text, mode)


def canonical_chunked(texts, chunk_size=2, mode="upper"):
    values = canonical_batch(texts, mode)
    for index in range(0, len(values), chunk_size):
        yield values[index:index + chunk_size]


def formatted_fields(fields):
    return "\n".join(fields.values())


def known_state(text):
    return {"10001": "NY", "90210": "CA"}.get(text)


class CloseFails(DemoParser):
    def close(self):
        raise RuntimeError("intentional close failure")


class Interrupted(DemoParser):
    closed = False

    def parse(self, request):
        raise KeyboardInterrupt

    def close(self):
        Interrupted.closed = True
        raise RuntimeError("close failure must not swallow the interrupt")


class UnavailableCloseFails(CloseFails):
    def parse_many(self, requests, directory):
        from address_benchmark.adapters import Unavailable
        raise Unavailable('unavailable after adapter initialization')


class InterruptCloseExits(Interrupted):
    def close(self):
        raise SystemExit(23)


class ExitCloseInterrupts(DemoParser):
    def parse(self, request):
        raise SystemExit(23)

    def close(self):
        raise KeyboardInterrupt


class SuccessfulCloseExits(DemoParser):
    def close(self):
        raise SystemExit(23)


class PrivateEcho(DemoParser):
    def parse(self, request):
        raise RuntimeError("private native exception: " + request.text)


class Counting(DemoParser):
    """Input-only invocation witness; counter is observation, never a model."""
    def __init__(self, config):
        super().__init__({})
        self.counter = config['counter']
        self.metadata['artifact_files'] = [config['model']] if config.get('model') else []

    def parse(self, request):
        from pathlib import Path
        with Path(self.counter).open('a') as stream:
            stream.write('inference\n')
        return super().parse(request)


class LazyCounting(Counting):
    def parse(self, request):
        import fractions
        return super().parse(request)
