"""POSTHOC: one support-case sentence repeated across OpenShift's runbooks.

Re-measures the OpenShift runbooks and the public agent procedures in the primary configuration
(ordinary prose, sentence segmentation, broad triggers) and counts the prohibition matches made by the
sentence "If you cannot resolve the issue, log in to the customer portal ...", which forbids nothing.
Compares OpenShift's prohibition matches per thousand prose words with the agent procedures', as
counted and with that sentence set aside, overall and by length band. Writes
reproduced/POSTHOC-openshift-sentence.json. The stored copy is
results/POSTHOC-openshift-sentence/results.json.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from measure import Measurement

SENTENCE = re.compile(r"(?i)if you cannot resolve the issue")
BANDS = [(1, 249), (250, 499), (500, 999), (1000, 1999), (2000, None)]


class SentenceCheck:
    def __init__(self):
        self.measurement = Measurement()
        self.docs = {"openshift": [], "direct": []}

    def measure(self):
        for source in self.measurement.manifest():
            if source["corpus"] in self.docs:
                self.docs[source["corpus"]].append(self.document(source))

    def document(self, source):
        parser = self.measurement.parser
        records, _ = parser.records(self.measurement.text(source), True)
        doc = {"words": 0, "P": 0, "sentence_P": 0, "sentence_words": 0}
        for unit in parser.units(records, "sentence"):
            doc["words"] += unit["prose_words"]
            if parser.matches(unit, "broad")[0]:
                doc["P"] += 1
                if SENTENCE.search(unit["text"]):
                    doc["sentence_P"] += 1
                    doc["sentence_words"] += unit["prose_words"]
        return doc

    def rate(self, docs, set_aside):
        matches = sum(d["P"] - (d["sentence_P"] if set_aside else 0) for d in docs)
        words = sum(d["words"] - (d["sentence_words"] if set_aside else 0) for d in docs)
        return 1000 * matches / words

    def in_band(self, docs, low, high):
        upper = high if high is not None else float("inf")
        return [d for d in docs if low <= d["words"] <= upper]

    def results(self):
        openshift, direct = self.docs["openshift"], self.docs["direct"]
        agent_rate = self.rate(direct, False)
        res = {"configuration": "no_code_examples, sentence, broad",
               "sentence_pattern": SENTENCE.pattern,
               "openshift": {"documents": len(openshift), "P": sum(d["P"] for d in openshift),
                             "P_from_sentence": sum(d["sentence_P"] for d in openshift),
                             "documents_with_sentence": sum(d["sentence_P"] > 0 for d in openshift)},
               "agent_procedures": {"documents": len(direct), "P": sum(d["P"] for d in direct)},
               "ratio_to_agent_rate": {"as_counted": round(self.rate(openshift, False) / agent_rate, 2),
                                       "sentence_set_aside": round(self.rate(openshift, True) / agent_rate, 2)},
               "bands": []}
        for low, high in BANDS:
            band_openshift = self.in_band(openshift, low, high)
            band_direct = self.in_band(direct, low, high)
            if not band_openshift:
                continue
            band_rate = self.rate(band_direct, False)
            res["bands"].append({"prose_words": f"{low}-{high}" if high else f"{low}+",
                                 "openshift_documents": len(band_openshift),
                                 "agent_documents": len(band_direct),
                                 "ratio_as_counted": round(self.rate(band_openshift, False) / band_rate, 2),
                                 "ratio_sentence_set_aside": round(self.rate(band_openshift, True) / band_rate, 2)})
        return res


check = SentenceCheck()
check.measure()
res = check.results()
assert res["openshift"]["P"] == 229
assert res["agent_procedures"]["P"] == 4080
out = ROOT / "reproduced" / "POSTHOC-openshift-sentence.json"; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
print(json.dumps(res, indent=1))
