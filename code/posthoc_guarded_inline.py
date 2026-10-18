"""POSTHOC guarded inline-command coding."""
import collections
import csv
import json
from pathlib import Path
import shutil

from common import ARTIFACT
from measure import Measurement
from regression import Models as Fits
import regression as fit_code


class OutputFits(Fits):
    def __init__(self, output):
        self.output = output

    def write(self, name, value):
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    def csv(self, name, rows):
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"classification": "POSTHOC", **row} for row in rows]
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


class GuardedInline:
    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    def run(self):
        measurement = Measurement()
        _, docs, missing = measurement.run(corpora={"direct"})
        if missing:
            raise ValueError("Incomplete source snapshot")
        identities = {r["document_id"]: r for r in measurement.manifest() if r["corpus"] == "direct"}
        classes = []
        for doc in docs:
            source = identities[doc["id"]]
            text = measurement.text(source)
            records, _ = measurement.parser.records(text, True)
            guarded_lines = set()
            for unit in measurement.parser.units(records, "sentence"):
                if any(measurement.parser.matches(unit, "broad")[:2]):
                    guarded_lines.update(range(unit["start_line"], unit["end_line"] + 1))
            inline = [r for r in doc["V-inline_matches"] if r["source"] == "inline"]
            outside = [r for r in inline if r["line"] not in guarded_lines]
            inside = [r for r in inline if r["line"] in guarded_lines]
            doc["guarded_tier"] = measurement.risk.highest(doc["primary_matches"] + outside)
            doc["inside_inline_tier"] = measurement.risk.highest(doc["primary_matches"] + inside)
            classes.append({
                "classification": "POSTHOC", "id": doc["id"], "publisher": doc["publisher"],
                "corpus_path": source["relative_path"], "primary": doc["primary_tier"],
                "all_inline": doc["V-inline"], "guarded_outside": doc["guarded_tier"],
                "inside_only": doc["inside_inline_tier"],
                "outside_changes_primary": doc["guarded_tier"] != doc["primary_tier"],
                "inside_changes_primary": doc["inside_inline_tier"] != doc["primary_tier"],
            })
        output = ARTIFACT / "reproduced/POSTHOC-guarded-inline"
        output.mkdir(parents=True, exist_ok=True)
        raw = output / "calculation"
        raw.mkdir()
        fits = OutputFits(raw)
        hc, fitted = fits.point_fit("primary_full", docs, tier="guarded_tier", specification="full", outcome="primary")
        if hc["status"] != "PASS" or hc["model_family"] != "NB2":
            raise ValueError("Required NB2 calculation unavailable")
        standard, valid, _ = fits.fitted(fitted["y"], fitted["x"], "NB2", robust=False)
        if not valid:
            raise ValueError("Information-based covariance unavailable")
        import numpy as np
        if not np.array_equal(np.asarray(standard.params), np.asarray(fitted["result"].params)):
            raise ValueError("Covariance calculations changed point estimates")
        fits.write("B3-models-point.json", [hc])
        saved_output = fit_code.OUT
        fit_code.OUT = raw
        try:
            bootstrap = fits.bootstrap(fitted)
        finally:
            fit_code.OUT = saved_output
        contrasts = {}
        for name in ("tier_D", "tier_W"):
            index = fitted["names"].index(name)
            estimate = next(c for c in hc["coefficients"] if c["term"] == name)
            se = float(np.asarray(standard.bse)[index])
            contrasts[name] = {
                "IRR": estimate["IRR"],
                "wald_standard": [float(np.exp(estimate["coefficient"] - 1.959963984540054 * se)),
                                  float(np.exp(estimate["coefficient"] + 1.959963984540054 * se))],
                "wald_HC0": [estimate["IRR_Wald95_low"], estimate["IRR_Wald95_high"]],
                "bootstrap": [bootstrap["intervals"][name]["IRR_bootstrap95_low"],
                              bootstrap["intervals"][name]["IRR_bootstrap95_high"]],
            }
        outside_ids = {r["id"] for r in classes if r["outside_changes_primary"]}
        inside_ids = {r["id"] for r in classes if r["inside_changes_primary"]}
        counts = {name: dict(collections.Counter(r[name] for r in classes))
                  for name in ("primary", "all_inline", "guarded_outside", "inside_only")}
        result = {
            "classification": "POSTHOC", "documents": len(docs), "fit_n": hc["N"],
            "distribution": "NB2", "counts": counts, "contrasts": contrasts,
            "changes": {"outside": len(outside_ids), "inside": len(inside_ids),
                        "intersection": len(outside_ids & inside_ids), "union": len(outside_ids | inside_ids)},
            "bootstrap": {"attempts": bootstrap["replicates_attempted"], "failed": bootstrap["failed_fits"],
                          "valid": bootstrap["replicates_attempted"] - bootstrap["failed_fits"],
                          "seed_integer": bootstrap["seed_integer"], "intervals": bootstrap["intervals"]},
        }
        self.write(output / "results.json", result)
        self.write(output / "bootstrap-status.json", {"classification": "POSTHOC", **result["bootstrap"]})
        shutil.copyfile(raw / "B3-bootstrap-draws.jsonl", output / "bootstrap-draws.jsonl")
        shutil.copyfile(raw / "tables/B3-primary-tier-IRR-bootstrap.csv", output / "bootstrap-table.csv")
        with (output / "per-document-classes.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(classes[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(classes)
        interval_rows = [{"classification": "POSTHOC", "term": name, **values}
                         for name, values in contrasts.items()]
        with (output / "intervals.csv").open("w", encoding="utf-8", newline="") as stream:
            fields = ["classification", "term", "IRR", "wald_standard", "wald_HC0", "bootstrap"]
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(interval_rows)
        for path in (raw / "B3-models-point.json", raw / "B3-bootstrap-draws.jsonl", raw / "B3-bootstrap-status.json",
                     raw / "tables/B3-primary-tier-IRR-bootstrap.csv"):
            path.unlink()
        (raw / "tables").rmdir()
        raw.rmdir()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    GuardedInline().run()
