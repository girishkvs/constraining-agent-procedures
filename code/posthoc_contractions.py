import collections
import json

from common import Base
from measure import Measurement


class Contractions(Base):
    def run(self):
        original = Measurement()
        baseline, _, missing = original.run()
        expected = {"direct": 4080, "agent_context": 2403, "gitlab": 799, "openshift": 229}
        for corpus, p in expected.items():
            if sum(r["P"] for r in baseline if r["corpus"] == corpus) != p:
                raise ValueError("Baseline failed; do not extend the dictionary")
        extended = Measurement(contractions=True)
        updated, _, missing = extended.run()
        by_id = {(r["corpus"], r["document_id"]): r for r in baseline}
        out = []
        for row in updated:
            before = by_id[(row["corpus"], row["document_id"])]
            if row["O_dual"] != before["O_dual"] or row["prose_words"] != before["prose_words"]:
                raise ValueError("Unchanged quantities differ")
            if row["P"] < before["P"]:
                raise ValueError("Original matches lost")
        for corpus in (*expected, "runbooks_pooled"):
            included = {"gitlab", "openshift"} if corpus == "runbooks_pooled" else {corpus}
            for band in ("all", "250-999"):
                before = [r for r in baseline if r["corpus"] in included and (band == "all" or 250 <= r["prose_words"] < 1000)]
                after = [r for r in updated if r["corpus"] in included and (band == "all" or 250 <= r["prose_words"] < 1000)]
                out.append({"corpus": corpus, "band": band, "original": original.aggregate(before),
                            "extended": extended.aggregate(after), "new_only_statements": sum(r["P"] for r in after) - sum(r["P"] for r in before)})
        self.write("POSTHOC-contractions.json", {"status": "POSTHOC", "added_forms": ["don't", "shouldn't", "can't", "mustn't", "shan't"], "rows": out})
        print("POSTHOC contractions reproduced.")


if __name__ == "__main__":
    Contractions().run()
