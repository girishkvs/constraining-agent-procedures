import collections
import csv
import gzip
import json
import math
from pathlib import Path

from common import ARTIFACT, Base
from measure import Measurement


class Tables(Base):
    def rows(self, corpus):
        with gzip.open(ARTIFACT / f"results/{corpus}-document-results.csv.gz", "rt", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def numeric(self, row):
        names = ("statements", "P_only", "O_only", "both", "neither", "eligible_words", "prose_words", "prose_P",
                 "prose_units", "code_units", "quote_units", "example_units", "P", "O_dual", "O_priority")
        return {**row, "path": row.get("path") or row["repo"] + "/" + row["origin_path"],
                **{k: int(row[k]) for k in names}}

    def run(self):
        m = Measurement()
        contrast = []
        bands = []
        bins = []
        grids = []
        publisher_tables = []
        edges = [(0, 1, "0"), (1, 250, "1-249"), (250, 500, "250-499"),
                 (500, 1000, "500-999"), (1000, 2000, "1000-1999"), (2000, math.inf, "2000+")]
        for corpus in ("direct", "agent_context", "gitlab", "openshift"):
            rows = [self.numeric(r) for r in self.rows(corpus)]
            primary = [r for r in rows if
                       r["arm"] == "no_code_examples" and
                       r["segmentation"] == "sentence" and
                       r["triggers"] == "broad"]
            contrast.append({"corpus": corpus, **m.aggregate(primary)})
            for low, high, label in edges:
                selected = [r for r in primary if low <= r["prose_words"] < high]
                bands.append({"corpus": corpus, "prose_word_band": label, **m.aggregate(selected)})
            bins.append({
                "corpus": corpus, "N": len(primary),
                **{label: sum(low <= r["P"] < high for r in primary) / len(primary)
                   for low, high, label in [(0, 1, "0"), (1, 5, "1-4"), (5, 10, "5-9"), (10, 20, "10-19"), (20, math.inf, "20+")]},
            })
            for segment in ("sentence", "line", "paragraph"):
                for triggers in ("broad", "narrow"):
                    selected = [r for r in rows if
                                r["arm"] == "no_code_examples" and
                                r["segmentation"] == segment and
                                r["triggers"] == triggers]
                    for overlap in ("dual", "prohibition_priority"):
                        grids.append({"corpus": corpus, "segmentation": segment, "triggers": triggers,
                                      "overlap_rule": overlap, **m.aggregate(selected, overlap)})
            if corpus == "direct":
                for pub in sorted({r["repo"] for r in primary}):
                    publisher_tables.append({"publisher": pub, **m.aggregate([r for r in primary if r["repo"] == pub])})
        self.csv("cross-corpus.csv", contrast)
        self.csv("length-bands.csv", bands)
        self.csv("binned-distributions.csv", bins)
        self.csv("twelve-configuration-grids.csv", grids)
        self.csv("publisher-results.csv", publisher_tables)
        origin = json.loads((ARTIFACT / "results/POSTHOC-origin/definite-posthoc-exclusion-ids.json").read_text(encoding="utf-8"))
        excluded = set(origin["excluded_ids"])
        direct = [self.numeric(r) for r in self.rows("direct") if
                  r["arm"] == "no_code_examples" and r["segmentation"] == "sentence" and r["triggers"] == "broad"]
        self.write("POSTHOC-origin.json", {"full": m.aggregate(direct), "excluded_ids": sorted(excluded),
                                         "reduced": m.aggregate([r for r in direct if r["id"] not in excluded])})
        print("Stored-count grids, publishers, bands, bins, and POSTHOC origin arithmetic reproduced.")


if __name__ == "__main__":
    Tables().run()
