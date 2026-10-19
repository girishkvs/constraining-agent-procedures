import argparse
import csv
import json
import math
from pathlib import Path

import openpyxl


class Scorer:
    def __init__(self, key_path):
        self.key = json.loads(Path(key_path).read_text(encoding="utf-8"))

    def wilson(self, yes, n):
        if not n:
            return [None, None]
        z = 1.959963984540054
        p = yes / n
        denom = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denom
        width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        return [max(0, center - width), min(1, center + width)]

    def normalized(self, value, allowed, item):
        text = "" if value is None else str(value).strip().upper()
        if text and text not in allowed:
            raise ValueError(f"Invalid label for {item}: expected {sorted(allowed)} or blank")
        return text

    def read_workbook(self, path):
        book = openpyxl.load_workbook(path, data_only=False, read_only=True)
        result = {}
        for sheet in ("statements", "procedures"):
            rows = book[sheet].iter_rows(values_only=True)
            header = next(rows)
            columns = {("label" if str(value).startswith("label") else str(value)): index
                       for index, value in enumerate(header) if value is not None}
            for row in rows:
                item = row[columns["item_id"]] if len(row) > columns["item_id"] else None
                if not item:
                    continue
                if item in result:
                    raise ValueError("Duplicate workbook item_id")
                result[item] = row[columns["label"]] if len(row) > columns["label"] else None
        book.close()
        return result

    def read_csvs(self, statements, procedures):
        result = {}
        for path in (statements, procedures):
            with Path(path).open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    if row["item_id"] in result:
                        raise ValueError("Duplicate CSV item_id")
                    result[row["item_id"]] = row.get("label")
        return result

    def score(self, labels):
        items = self.key["items"]
        unknown = set(labels) - set(items)
        if unknown:
            raise ValueError("Workbook contains item IDs not in this sample key")
        groups = {"P_top": [], "P_rest": [], "O_full": []}
        matrix = {d: {h: 0 for h in ("D", "W", "R")} for d in ("D", "W", "R")}
        risk_blank = 0
        for item, value in items.items():
            if value["kind"] == "statement":
                label = self.normalized(labels.get(item), {"Y", "N", "U"}, item)
                groups[value["stratum"]].append(label)
            else:
                label = self.normalized(labels.get(item), {"D", "W", "R"}, item)
                if label:
                    matrix[value["detected_tier"]][label] += 1
                else:
                    risk_blank += 1
        rates = {}
        for group, values in groups.items():
            yes = values.count("Y")
            no = values.count("N")
            unsure = values.count("U")
            blank = values.count("")
            valid = yes + no
            rates[group] = {
                "sample_items": len(values), "Y": yes, "N": no, "U": unsure, "blank": blank,
                "valid_Y_or_N": valid, "operative_rate": yes / valid if valid else None,
                "Wilson95": self.wilson(yes, valid)
            }
        top = rates["P_top"]["operative_rate"]
        rest = rates["P_rest"]["operative_rate"]
        counts = self.key["population_pools"]
        adjusted = weighted = None
        if top is not None and rest is not None:
            numerator = counts["P_top"] * top
            denominator = numerator + counts["P_rest"] * rest
            adjusted = numerator / denominator if denominator else None
            weighted = denominator / (counts["P_top"] + counts["P_rest"])
        risk_valid = sum(sum(row.values()) for row in matrix.values())
        return {
            "operative_samples": rates, "SC_adjusted_top_P_share": adjusted,
            "stratum_weighted_overall_P_precision": weighted,
            "O_operative_rate": rates["O_full"]["operative_rate"],
            "risk_confusion_detected_rows_reading_label_columns": matrix,
            "risk_valid_labels": risk_valid, "risk_blank": risk_blank,
            "risk_agreement": sum(matrix[k][k] for k in matrix) / risk_valid if risk_valid else None
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook")
    parser.add_argument("--statements-csv")
    parser.add_argument("--procedures-csv")
    parser.add_argument("--key", default=str(Path(__file__).parent.parent / "labels/KEY.json"))
    parser.add_argument("--output", default=str(Path(__file__).parent.parent / "reproduced/reading-scores.json"))
    args = parser.parse_args()
    scorer = Scorer(args.key)
    labels = scorer.read_workbook(args.workbook) if args.workbook else scorer.read_csvs(args.statements_csv, args.procedures_csv)
    value = scorer.score(labels)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, indent=2, sort_keys=True))
