"""POSTHOC statement-class finite-slot references."""
import csv
import json
import re

import numpy as np

from common import ARTIFACT, ROOT
from fast_metrics import FIELDS
from measure import Measurement
from repository_metrics import RepositoryMetrics


class TopicWords:
    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    def run(self):
        measurement = Measurement()
        sources = [r for r in measurement.manifest() if r["corpus"] == "direct"]
        labels = ("prohibition", "obligation", "files", "users", "tests")
        patterns = {name: re.compile(r"\b" + name + r"?\b", re.I) for name in labels[2:]}
        counts = np.zeros((5, len(sources)), dtype=np.int64)
        lengths = np.zeros(len(sources), dtype=np.int64)
        words = np.zeros(len(sources), dtype=np.int64)
        per_document = []
        for i, source in enumerate(sources):
            records, _ = measurement.parser.records(measurement.text(source), True)
            units = list(measurement.parser.units(records, "sentence"))
            lengths[i] = len(units)
            words[i] = sum(u["prose_words"] for u in units)
            for unit in units:
                p, o = measurement.parser.matches(unit, "broad")[:2]
                counts[0, i] += int(p)
                counts[1, i] += int(o)
                for k, name in enumerate(labels[2:], 2):
                    counts[k, i] += int(bool(patterns[name].search(unit["text"])))
            per_document.append({
                "classification": "POSTHOC", "id": source["document_id"], "publisher": source["source_repo"],
                "statements": int(lengths[i]), **{name: int(counts[k, i]) for k, name in enumerate(labels)},
            })
        if (len(sources), int(lengths.sum()), int(counts[0].sum()), int(counts[1].sum())) != (1495, 102955, 4080, 1864):
            raise ValueError("Primary counts differ")
        protocol = json.loads((ROOT / "direct-reference-protocol.json").read_text(encoding="utf-8"))
        key = ("direct", "ordinary_prose_all_entrypoint_identities", "sentence", "broad", "dual")
        output = ARTIFACT / "reproduced/POSTHOC-topic-words"
        output.mkdir(parents=True, exist_ok=True)
        results = []
        for k, name in enumerate(labels):
            values = np.zeros((len(sources), len(FIELDS)), dtype=np.int64)
            values[:, 0] = lengths
            values[:, 1] = counts[k]
            values[:, 4] = lengths - counts[k]
            values[:, 5] = values[:, 6] = words
            values[:, 7] = counts[k]
            values[:, 8] = lengths
            reference = RepositoryMetrics(protocol)
            reference.bind_repositories([r["source_repo"] for r in sources])
            summary, draws = reference.resample(values, key)
            observed = {
                "zero_P_document_share": float(np.count_nonzero(counts[k] == 0) / len(sources)),
                "top_decile_P_share": reference.top_share(counts[k], 150, int(counts[k].sum())),
            }
            references = {}
            for scope in ("length_null", "repository_conditioned_length_null"):
                references[scope] = {}
                for metric, value in observed.items():
                    stream = draws[scope][metric]
                    references[scope][metric] = {
                        **summary[scope][metric], "strict_below_observed_count": sum(v < value for v in stream),
                        "strict_below_observed_share": sum(v < value for v in stream) / len(stream),
                        "equal_observed_count": sum(v == value for v in stream), "draws": len(stream),
                    }
            results.append({
                "classification": "POSTHOC", "class": name, "documents": len(sources),
                "statements": int(lengths.sum()), "matched_statements": int(counts[k].sum()),
                "statement_match_share": int(counts[k].sum()) / int(lengths.sum()),
                "zero_share": observed["zero_P_document_share"], "top_tenth_share": observed["top_decile_P_share"],
                "references": references,
                "seeds": {field: draws[field] for field in ("key", "rng", "length_null_seed_integer",
                         "repository_conditioned_length_null_seed_integer", "bootstrap_seed_integer", "numpy_version")},
            })
            self.write(output / f"{name}-draws.json", {
                "classification": "POSTHOC", "key": list(key), "global": draws["length_null"],
                "repository_conditioned": draws["repository_conditioned_length_null"],
            })
        self.write(output / "results.json", {"classification": "POSTHOC", "classes": results})
        table = []
        for row in results:
            values = {k: row[k] for k in ("classification", "class", "documents", "statements", "matched_statements",
                                         "statement_match_share", "zero_share", "top_tenth_share")}
            for scope, metrics in row["references"].items():
                for metric in sorted(metrics):
                    record = metrics[metric]
                    for field in ("mean", "strict_below_observed_count", "strict_below_observed_share", "draws"):
                        values[scope + "_" + metric + "_" + field] = record[field]
            table.append(values)
        with (output / "table.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(table[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(table)
        with (output / "per-document-counts.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(per_document[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(per_document)
        print(json.dumps({"classification": "POSTHOC", "classes": results}, indent=2))


if __name__ == "__main__":
    TopicWords().run()
