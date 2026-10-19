import argparse
import csv
import gzip
import json
from pathlib import Path

import numpy as np

from common import ARTIFACT, ROOT
from fast_metrics import FIELDS, FastMetrics
from repository_metrics import RepositoryMetrics


def drop_constant_flags(value):
    # The byte-frozen metrics code adds a constant flag that the stored results omit.
    if isinstance(value, dict):
        return {k: drop_constant_flags(v) for k, v in value.items() if k != "flat_file_bootstrap_used_for_population"}
    if isinstance(value, list):
        return [drop_constant_flags(v) for v in value]
    return value


class Reference:
    def rows(self, corpus):
        with gzip.open(ARTIFACT / f"results/{corpus}-document-results.csv.gz", "rt", encoding="utf-8", newline="") as f:
            return [r for r in csv.DictReader(f) if
                    r["arm"] == "no_code_examples" and
                    r["segmentation"] == "sentence" and
                    r["triggers"] == "broad"]

    def run(self, corpus):
        rows = self.rows(corpus)
        protocol_name = corpus if corpus in {"direct", "agent_context"} else "runbooks"
        protocol = json.loads((ROOT / f"{protocol_name}-reference-protocol.json").read_text(encoding="utf-8"))
        values = np.array([[int(r[k]) for k in FIELDS] for r in rows], dtype=np.int64)
        if corpus == "direct":
            metrics = RepositoryMetrics(protocol)
            metrics.bind_repositories([r["repo"] for r in rows])
            key = ("direct", "ordinary_prose_all_entrypoint_identities", "sentence", "broad", "dual")
        elif corpus == "agent_context":
            metrics = RepositoryMetrics(protocol)
            metrics.bind_repositories([r["path"].split("@", 1)[0].rsplit("/", 1)[0] for r in rows])
            # Use the exact repository identity, not the containing instruction directory.
            with (ARTIFACT / "corpus/MANIFEST.csv").open(encoding="utf-8", newline="") as f:
                identities = [r for r in csv.DictReader(f) if r["corpus"] == corpus]
            metrics.bind_repositories([r["source_repo"] for r in identities])
            key = (corpus, "corpus_all", "no_code_examples", "sentence", "broad")
        else:
            metrics = FastMetrics(protocol)
            key = (corpus, "corpus_all", "no_code_examples", "sentence", "broad")
        summary, draws = metrics.resample(values, key)
        summary, draws = drop_constant_flags(summary), drop_constant_flags(draws)
        output = ARTIFACT / "reproduced"
        output.mkdir(exist_ok=True)
        (output / f"{corpus}-length-reference.json").write_text(json.dumps({"summary": summary, "draws": draws}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"corpus": corpus, "key": key, "summary": summary}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", choices=["direct", "agent_context", "gitlab", "openshift"], required=True)
    Reference().run(p.parse_args().corpus)
