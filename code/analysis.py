import json
from common import Base, OUT


class Analysis(Base):
    def documents(self):
        p = OUT / "joined-documents.json"
        if not p.exists():
            raise SystemExit("Run code/measure.py --grid first.")
        return json.loads(p.read_text(encoding="utf-8"))
