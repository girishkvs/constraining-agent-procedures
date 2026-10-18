import argparse
import collections
import copy
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sqlite3
import sys

from adapter import BodySourceParser
from common import ARTIFACT, ROOT
from legacy.metrics import Metrics
from risk import Risk
from source_files import SourceFiles
from frozen_dedup import FirstOccurrence


class Measurement:
    def __init__(self, contractions=False):
        self.legacy = json.loads((ROOT / "legacy/protocol.json").read_text(encoding="utf-8"))
        self.selection = json.loads((ROOT / "legacy/selection.json").read_text(encoding="utf-8"))
        self.revision = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
        if contractions:
            self.legacy = copy.deepcopy(self.legacy)
            self.legacy["triggers"]["broad_prohibition"] += ["don't", "shouldn't", "can't", "mustn't", "shan't"]
        self.parser = BodySourceParser(self.legacy, self.selection, self.revision)
        self.risk = Risk()
        self.metrics = Metrics({})
        self.sources = SourceFiles(ARTIFACT)

    def manifest(self):
        with (ARTIFACT / "corpus/MANIFEST.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def text(self, row):
        return self.sources.read(row).decode("utf-8-sig")

    def count(self, units, triggers):
        counts = {k: 0 for k in ("statements", "P_only", "O_only", "both", "neither", "eligible_words", "prose_words", "prose_P", "prose_units", "code_units", "quote_units", "example_units")}
        for unit in units:
            p, o = self.parser.matches(unit, triggers)[:2]
            counts["statements"] += 1
            counts["both" if p and o else "P_only" if p else "O_only" if o else "neither"] += 1
            counts["eligible_words"] += unit["eligible_words"]
            counts["prose_words"] += unit["prose_words"]
            counts[unit["kind"] + "_units"] += 1
            if unit["kind"] == "prose":
                prose_unit = {**unit, "text": unit["prose_text"]}
                counts["prose_P"] += int(self.parser.matches(prose_unit, triggers)[0])
        counts["P"] = counts["P_only"] + counts["both"]
        counts["O_dual"] = counts["O_only"] + counts["both"]
        counts["O_priority"] = counts["O_only"]
        return counts

    def aggregate(self, rows, overlap="dual"):
        if not rows:
            return {"documents": 0}
        return {
            **self.metrics.aggregate(rows, overlap),
            "median_prose_words": statistics.median(r["prose_words"] for r in rows),
            "median_P": statistics.median(r["P"] for r in rows),
        }

    def run(self, grid=False, allow_missing=False, corpora=None):
        results = []
        docs = []
        missing = []
        manifest = self.manifest()
        if corpora:
            manifest = [r for r in manifest if r["corpus"] in corpora]
        connection = sqlite3.connect(":memory:") if grid else None
        first = FirstOccurrence()
        scopes = {name: i for i, name in enumerate(sorted({r["corpus"] for r in manifest}))}
        if connection is not None:
            connection.execute(
                "CREATE TABLE seen(v INTEGER,s INTEGER,g INTEGER,h BLOB,d INTEGER,a INTEGER,z INTEGER,o INTEGER,"
                "PRIMARY KEY(v,s,g,h)) WITHOUT ROWID"
            )
        for index, source in enumerate(manifest):
            try:
                text = self.text(source)
            except FileNotFoundError:
                if not allow_missing:
                    raise
                missing.append(source["relative_path"])
                continue
            variants = {}
            for arm in (("no_code_examples", "baseline") if grid else ("no_code_examples",)):
                records, _ = self.parser.records(text, arm == "no_code_examples")
                for segment_index, segment in enumerate((("sentence", "line", "paragraph") if grid else ("sentence",))):
                    units = list(self.parser.units(records, segment))
                    kept = []
                    if grid:
                        for unit in units:
                            keep, _ = first.first_occurrence(
                                connection, int(arm == "no_code_examples"), segment_index, scopes[source["corpus"]],
                                bytes.fromhex(unit["text_sha256"]),
                                [int(source["document_index"]), unit["start_line"], unit["end_line"], unit["ordinal"]]
                            )
                            if keep:
                                kept.append(unit)
                    for triggers in (("broad", "narrow") if grid else ("broad",)):
                        counts = self.count(units, triggers)
                        result = {
                            **{k: source[k] for k in ("corpus", "document_id", "document_index", "source_repo", "family")},
                            "id": source["document_id"], "path": source["source_repo"] + "/" + source["original_path"],
                            "arm": arm, "segmentation": segment, "triggers": triggers, **counts,
                        }
                        results.append(result)
                        if grid:
                            results.append({
                                **result,
                                "arm": "exact_dedup_no_code_examples" if arm == "no_code_examples" else "exact_dedup",
                                **self.count(kept, triggers),
                            })
                        if segment == "sentence":
                            key = "primary" if arm == "no_code_examples" and triggers == "broad" else "narrow" if arm == "no_code_examples" else "all_kind"
                            if key != "all_kind" or triggers == "broad":
                                variants[key] = counts
            if source["corpus"] == "direct":
                description = self.description(text)
                tier = self.risk.extract(text, description)
                records, _ = self.parser.records(text, True)
                verbs = []
                for unit in self.parser.units(records, "sentence"):
                    if not any(self.parser.matches(unit, "broad")[:2]):
                        verbs.extend(self.risk.verb_matches(unit["text"], "unmatched_prose", unit["start_line"]))
                tier["V-prose"] = self.risk.highest(tier["primary_matches"] + verbs)
                docs.append({
                    "id": source["document_id"], "publisher": source["source_repo"], "family": source["family"],
                    "path": source["original_path"], "full_path": source["source_repo"] + "/" + source["original_path"],
                    "name": self.name(text, source), "description": description,
                    "outcomes": variants, **variants["primary"], **tier,
                })
            if (index + 1) % 500 == 0:
                print("Measured", index + 1, flush=True)
        if connection is not None:
            connection.close()
        return results, docs, missing

    def frontmatter(self, text):
        import yaml
        lines = text.splitlines()
        if lines and lines[0].strip() == "---":
            ending = next((i for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), None)
            if ending is not None:
                value = yaml.safe_load("\n".join(lines[1:ending]))
                return value if isinstance(value, dict) else {}
        return {}

    def description(self, text):
        value = self.frontmatter(text).get("description", "")
        return value if isinstance(value, str) else ""

    def name(self, text, source):
        return self.frontmatter(text).get("name") or source["original_path"]

    def export(self, output, rows, docs, missing):
        output.mkdir(parents=True, exist_ok=True)
        with gzip.open(output / "document-counts.csv.gz", "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        (output / "joined-documents.json").write_text(json.dumps(docs, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        groups = collections.defaultdict(list)
        for row in rows:
            groups[(row["corpus"], row["arm"], row["segmentation"], row["triggers"])].append(row)
        summaries = []
        for key, group in sorted(groups.items()):
            for overlap in ("dual", "prohibition_priority"):
                summaries.append({"corpus": key[0], "arm": key[1], "segmentation": key[2], "triggers": key[3], "overlap_rule": overlap, **self.aggregate(group, overlap)})
        (output / "configuration-grid.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
        tier_rows = []
        for tier in ("R", "W", "D"):
            selected = [r for r in docs if r["primary_tier"] == tier]
            tier_rows.append({"tier": tier, "N": len(selected), **self.aggregate(selected)})
        (output / "tiers.json").write_text(json.dumps(tier_rows, indent=2) + "\n", encoding="utf-8")
        publishers = []
        for pub in sorted({r["publisher"] for r in docs}):
            publishers.append({"publisher": pub, **self.aggregate([r for r in docs if r["publisher"] == pub])})
        (output / "publishers.json").write_text(json.dumps(publishers, indent=2) + "\n", encoding="utf-8")
        (output / "measurement-status.json").write_text(json.dumps({"missing_files": missing, "complete": not missing}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--grid", action="store_true")
    args.add_argument("--output", default="reproduced")
    args.add_argument("--corpus", action="append", choices=["direct", "agent_context", "gitlab", "openshift"])
    opts = args.parse_args()
    m = Measurement()
    rows, docs, missing = m.run(grid=opts.grid, corpora=opts.corpus)
    m.export(ARTIFACT / opts.output, rows, docs, missing)
