import hashlib
import json
from pathlib import Path

import numpy as np

from common import ARTIFACT, Base
from measure import Measurement


class Sampling(Base):
    def run(self):
        measurement = Measurement()
        rows, docs, missing = measurement.run(corpora={"direct"})
        if missing:
            raise ValueError("Incomplete procedure input")
        top = {r["id"] for r in sorted(docs, key=lambda r: (-r["P"], r["full_path"]))[:150]}
        pools = {"P_top": [], "P_rest": [], "O_full": []}
        for source in measurement.manifest():
            if source["corpus"] != "direct":
                continue
            text = measurement.text(source)
            records, _ = measurement.parser.records(text, True)
            for unit in measurement.parser.units(records, "sentence"):
                p, o = measurement.parser.matches(unit, "broad")[:2]
                value = {"doc_id": source["document_id"], "unit_index": unit["ordinal"], "unit_sha256": unit["text_sha256"]}
                if p:
                    pools["P_top" if source["document_id"] in top else "P_rest"].append(value)
                if o:
                    pools["O_full"].append(value)
        selected = []
        for name, count in (("P_top", 35), ("P_rest", 35), ("O_full", 30)):
            rng = np.random.Generator(np.random.PCG64(self.seed("operative-sample-" + name)))
            for i in rng.choice(len(pools[name]), size=count, replace=False):
                row = pools[name][int(i)]
                item = "S-" + hashlib.sha256((name + "|" + row["doc_id"] + "|" + str(row["unit_index"])).encode()).hexdigest()[:16]
                selected.append({"item_id": item, "stratum": name, **row})
        rng = np.random.Generator(np.random.PCG64(self.seed("statement-shuffle")))
        selected = [selected[int(i)] for i in rng.permutation(len(selected))]
        procedures = []
        for tier in ("D", "W", "R"):
            group = [r for r in docs if r["primary_tier"] == tier]
            rng = np.random.Generator(np.random.PCG64(self.seed("risk-validation-" + tier)))
            for i in rng.choice(len(group), size=10, replace=False):
                row = group[int(i)]
                procedures.append({"item_id": "P-" + hashlib.sha256(row["id"].encode()).hexdigest()[:16], "doc_id": row["id"], "detected_tier": tier})
        rng = np.random.Generator(np.random.PCG64(self.seed("procedure-shuffle")))
        procedures = [procedures[int(i)] for i in rng.permutation(len(procedures))]
        key = json.loads((ARTIFACT / "labels/KEY.json").read_text(encoding="utf-8"))
        for row in selected + procedures:
            expected = key["items"][row["item_id"]]
            for field in ("doc_id", "unit_index", "unit_sha256", "stratum", "detected_tier"):
                if field in row and row[field] != expected[field]:
                    raise ValueError("Sampling replay differs")
        if set(key["items"]) != {r["item_id"] for r in selected + procedures}:
            raise ValueError("Sampling item set differs")
        self.write("sampling-replay.json", {"status": "PASS", "statements": selected, "procedures": procedures,
                                           "pools": {k: len(v) for k, v in pools.items()}})
        print("Sampling replay PASS: 100 statement IDs and 30 procedure IDs.")


if __name__ == "__main__":
    Sampling().run()
