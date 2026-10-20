"""POSTHOC: prohibition matches by trigger word, and the main figures for procedures with steps.

Re-measures the public agent procedures, the agent context files and both runbook collections in the
primary configuration (ordinary prose, sentence segmentation, broad triggers). For each corpus it counts
the statements with a prohibition match, how many contain each trigger, and matches per thousand prose
words: as counted, without statements whose only triggers are *cannot* or *avoid*, and with only
*never*, *do not* and *must not*. It also gives, from the strict reading, how many of the 70 sampled
prohibition matches containing each trigger both analysts judged to forbid something, and the no-match
share and top-tenth share for the 833 procedures with three or more steps. Writes
reproduced/POSTHOC-triggers.json. The stored copy is results/POSTHOC-triggers/results.json.
"""
import collections, csv, json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from measure import Measurement

SOFT = {"cannot", "avoid"}
CORE = {"never", "do not", "must not"}
CORPORA = ("direct", "agent_context", "gitlab", "openshift")


def densities(measurement):
    stats = {c: {"documents": 0, "words": 0, "P": 0, "P_without_soft": 0, "P_core": 0, "by_trigger": collections.Counter()} for c in CORPORA}
    for source in measurement.manifest():
        if source["corpus"] not in stats:
            continue
        s = stats[source["corpus"]]
        s["documents"] += 1
        records, _ = measurement.parser.records(measurement.text(source), True)
        for unit in measurement.parser.units(records, "sentence"):
            s["words"] += unit["prose_words"]
            p, _, phrases, _ = measurement.parser.matches(unit, "broad")
            if not p:
                continue
            found = {x.lower() for x in phrases}
            s["P"] += 1
            s["by_trigger"].update(found)
            s["P_without_soft"] += not found <= SOFT
            s["P_core"] += bool(found & CORE)
    out = {}
    for c, s in stats.items():
        k = 1000 / s["words"]
        out[c] = {"documents": s["documents"], "prose_words": s["words"], "P": s["P"],
                  "per_1000": round(s["P"] * k, 2),
                  "per_1000_without_cannot_or_avoid_only": round(s["P_without_soft"] * k, 2),
                  "per_1000_never_do_not_must_not": round(s["P_core"] * k, 2),
                  "statements_containing": dict(s["by_trigger"].most_common()),
                  "share_containing": {t: round(n / s["P"], 3) for t, n in s["by_trigger"].most_common()}}
    for c in ("agent_context", "gitlab", "openshift"):
        out[c]["ratio_to_agent_procedures"] = {v: round(out[c][v] / out["direct"][v], 2) for v in
                                               ("per_1000", "per_1000_without_cannot_or_avoid_only", "per_1000_never_do_not_must_not")}
    return out


def precision(measurement):
    folder = ROOT / "labels" / "strict-reading"
    key = json.load(open(folder / "KEY.json", encoding="utf-8"))["statements"]
    text = {r["id"]: r["statement"] for r in csv.DictReader(open(folder / "statements-to-read.csv", encoding="utf-8"))}
    readers = [{r["id"]: r for r in csv.DictReader(open(folder / f"reader-{x}-statements.csv", encoding="utf-8"))} for x in "AB"]
    by = collections.defaultdict(lambda: [0, 0])
    for sid, k in key.items():
        if not k["stratum"].startswith("P"):
            continue
        forbids = all(r[sid]["forbids"] == "Y" for r in readers)
        for t in {x.lower() for x in measurement.parser.matches({"text": text[sid]}, "broad")[2]}:
            by[t][0] += 1
            by[t][1] += forbids
    return {t: {"statements": n, "both_forbid": f} for t, (n, f) in sorted(by.items(), key=lambda x: -x[1][0])}


def with_steps():
    rows = list(csv.DictReader(open(ROOT / "results" / "document-primary-counts-tiers-covariates.csv", encoding="utf-8")))
    sub = sorted((int(r["P"]) for r in rows if int(r["steps"]) >= 3), reverse=True)
    top = sub[:math.ceil(len(sub) / 10)]
    terminal = [r for r in rows if r["publisher"].startswith("TerminalSkills")]
    return {"procedures_with_3_or_more_steps": len(sub),
            "share_with_no_match": round(sum(p == 0 for p in sub) / len(sub), 3),
            "top_tenth_share": round(sum(top) / sum(sub), 3),
            "procedures_with_no_steps": sum(int(r["steps"]) == 0 for r in rows),
            "terminalskills_with_no_steps": sum(int(r["steps"]) == 0 for r in terminal), "terminalskills": len(terminal)}


measurement = Measurement()
res = {"configuration": "no_code_examples, sentence, broad", "densities": densities(measurement),
       "strict_reading_by_trigger": precision(measurement), "procedures_with_steps": with_steps()}
assert res["densities"]["direct"]["P"] == 4080 and res["densities"]["gitlab"]["P"] == 799 and res["densities"]["openshift"]["P"] == 229
out = ROOT / "reproduced" / "POSTHOC-triggers.json"; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
print(json.dumps(res, indent=1))
