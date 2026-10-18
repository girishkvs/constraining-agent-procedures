import csv
import hashlib
import json
from pathlib import Path

from common import ARTIFACT
from source_files import SourceFiles


def main():
    checked = 0
    missing = []
    mismatches = []
    redacted = []
    sources = SourceFiles(ARTIFACT)
    for name in ("MANIFEST.csv", "RIGHTS.csv"):
        with (ARTIFACT / "corpus" / name).open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                p = ARTIFACT / row["relative_path"]
                if not p.is_file():
                    missing.append(row["relative_path"])
                    continue
                try:
                    sources.read(row)
                    if row.get("layout_status") == "REDACTED_SECRET":
                        redacted.append({"document_id": row["document_id"], "relative_path": row["relative_path"],
                                         "verification": "distributed SHA-256 and bytes; upstream identity retained separately"})
                except ValueError:
                    mismatches.append(row["relative_path"])
                checked += 1
    result = {"status": "PASS" if not missing and not mismatches else "INCOMPLETE" if not mismatches else "FAIL",
              "checked_identities": checked, "missing_files": missing, "byte_mismatches": mismatches,
              "redacted_documents": redacted}
    (ARTIFACT / "results/snapshot-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
