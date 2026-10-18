import csv
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
ARTIFACT = ROOT.parent
OUT = ARTIFACT / os.environ.get("REPRO_OUTPUT", "reproduced")
OLD = ARTIFACT / "results"
sys.path.insert(0, str(ROOT))


class Base:
    def check(self):
        pass

    def seed(self, purpose):
        return int(hashlib.sha256(("SC-public-expansion-2026-10-16-v1|" + purpose).encode()).hexdigest(), 16)

    def write(self, name, value):
        p = OUT / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    def csv(self, name, rows):
        p = OUT / name
        p.parent.mkdir(parents=True, exist_ok=True)
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
