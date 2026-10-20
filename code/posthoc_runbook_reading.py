"""POSTHOC: the runbook reading. Rebuilds the reading packet from the corpus and scores the two readers.

After the main measurement, 35 prohibition matches were drawn (primary configuration) from each of: GitLab's runbooks;
OpenShift's runbooks other than the repeated support-case sentence (which forbids nothing and supplies 80 of its 229
matches); and the public agent procedures not already in the strict reading. They were shuffled without their sources
and read by the strict reading's two analysts under its rubric. This script rebuilds the packet with the same seeds,
checks it against results/POSTHOC-runbook-reading/, checks the seal, and scores the readers. Writes
reproduced/POSTHOC-runbook-reading.json; the stored copy is results/POSTHOC-runbook-reading/scores.json.
"""
import csv, hashlib, io, json, math, pathlib, re, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from measure import Measurement

HERE = ROOT / "results" / "POSTHOC-runbook-reading"
SENTENCE = re.compile(r"(?i)if you cannot resolve the issue")


def seed(name):
    return int.from_bytes(hashlib.sha256(f"runbook-reading-2026-10-19|{name}".encode()).digest()[:8], "big")


def rebuild():
    m = Measurement()
    already = {(i["doc_id"], i["unit_index"]) for i in json.load(open(ROOT / "labels" / "KEY.json", encoding="utf-8"))["items"].values()
               if i.get("kind") == "statement"}
    pools = {"gitlab": [], "openshift": [], "direct": []}
    sentence_units = 0
    for source in m.manifest():
        corpus = source["corpus"]
        if corpus not in pools:
            continue
        raw = m.text(source)
        raw_lines = raw.splitlines()
        units = list(m.parser.units(m.parser.records(raw, True)[0], "sentence"))
        for i, u in enumerate(units):
            if not m.parser.matches(u, "broad")[0]:
                continue
            if corpus == "openshift" and SENTENCE.search(u["text"]):
                sentence_units += 1
                continue
            if corpus == "direct" and (source["document_id"], u["ordinal"]) in already:
                continue
            pools[corpus].append({"corpus": corpus, "doc_id": source["document_id"], "unit_index": u["ordinal"],
                                  "statement": u["text"], "line": "\n".join(raw_lines[u["start_line"] - 1:u["end_line"]]).rstrip(),
                                  "before": units[i - 1]["text"] if i > 0 else "", "after": units[i + 1]["text"] if i + 1 < len(units) else ""})
    picked = []
    for corpus in ("gitlab", "openshift", "direct"):
        rng = np.random.Generator(np.random.PCG64(seed(corpus)))
        picked += [pools[corpus][int(j)] for j in rng.choice(len(pools[corpus]), size=35, replace=False)]
    rng = np.random.Generator(np.random.PCG64(seed("shuffle")))
    picked = [picked[int(j)] for j in rng.permutation(len(picked))]
    for n, row in enumerate(picked, 1):
        row["id"] = f"R-{n:03d}"
    return picked, {c: len(v) for c, v in pools.items()}, sentence_units


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - w, 3), round(c + w, 3)]


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in sorted(set(a) | set(b)))
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


picked, pools, sentence_units = rebuild()
buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=["id", "statement", "line", "before", "after"])
w.writeheader()
for row in picked:
    w.writerow({k: row[k] for k in ("id", "statement", "line", "before", "after")})
assert buf.getvalue().encode("utf-8") == (HERE / "statements-to-read.csv").read_bytes(), "packet differs from the released one"
key = json.load(open(HERE / "KEY.json", encoding="utf-8"))
assert all(key["items"][r["id"]]["corpus"] == r["corpus"] and key["items"][r["id"]]["doc_id"] == r["doc_id"] and key["items"][r["id"]]["unit_index"] == r["unit_index"] for r in picked)
assert key["pools"] == pools and key["openshift_repeated_sentence_units"] == sentence_units
seal = json.load(open(HERE / "SEAL-before-reading.json", encoding="utf-8"))
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert seal["files"]["packet/READ-ME.md"] == digest(HERE / "READ-ME.md") and seal["files"]["packet/statements-to-read.csv"] == digest(HERE / "statements-to-read.csv")
assert seal["key"]["key/KEY.json"] == digest(HERE / "KEY.json")
readers = {}
for x in ("A", "B"):
    rows = list(csv.DictReader(open(HERE / f"reader-{x}-statements.csv", encoding="utf-8-sig")))
    assert sorted(r["id"].strip() for r in rows) == sorted(key["items"]), f"reader {x} ids"
    readers[x] = {r["id"].strip(): {q: r[q].strip() for q in ("instructs", "forbids", "requires")} for r in rows}
A, B = readers["A"], readers["B"]
res = {"sealed_at": seal["sealed_at"], "by_source": {}}
for corpus in ("gitlab", "openshift", "direct"):
    its = sorted(i for i, v in key["items"].items() if v["corpus"] == corpus)
    n = len(its)
    both = {q: sum(A[i][q] == "Y" and B[i][q] == "Y" for i in its) for q in ("instructs", "forbids", "requires")}
    res["by_source"][corpus] = {"statements": n, "both_instructs": both["instructs"], "both_forbid": both["forbids"], "both_require": both["requires"],
                                "forbids_share": round(both["forbids"] / n, 3), "forbids_wilson95": wilson(both["forbids"], n),
                                "agreement_forbids": sum(A[i]["forbids"] == B[i]["forbids"] for i in its),
                                "kappa_forbids": kappa([A[i]["forbids"] for i in its], [B[i]["forbids"] for i in its]),
                                "reader_A_forbids": sum(A[i]["forbids"] == "Y" for i in its), "reader_B_forbids": sum(B[i]["forbids"] == "Y" for i in its)}
ids = sorted(key["items"])
res["overall_agreement_forbids"] = sum(A[i]["forbids"] == B[i]["forbids"] for i in ids)
res["overall_kappa_forbids"] = kappa([A[i]["forbids"] for i in ids], [B[i]["forbids"] for i in ids])
tr = json.load(open(ROOT / "results" / "POSTHOC-triggers" / "results.json", encoding="utf-8"))["densities"]
osr = json.load(open(ROOT / "results" / "POSTHOC-openshift-sentence" / "results.json", encoding="utf-8"))
p = {c: res["by_source"][c]["forbids_share"] for c in res["by_source"]}
p_os_counted = p["openshift"] * pools["openshift"] / (pools["openshift"] + sentence_units)
res["openshift_forbids_share_as_counted"] = round(p_os_counted, 3)
res["ratio_to_agent"] = {"gitlab_as_counted": tr["gitlab"]["ratio_to_agent_procedures"]["per_1000"],
                         "gitlab_forbidding_only": round(tr["gitlab"]["ratio_to_agent_procedures"]["per_1000"] * p["gitlab"] / p["direct"], 2),
                         "openshift_without_sentence": osr["ratio_to_agent_rate"]["sentence_set_aside"],
                         "openshift_without_sentence_forbidding_only": round(osr["ratio_to_agent_rate"]["sentence_set_aside"] * p["openshift"] / p["direct"], 2),
                         "openshift_as_counted_forbidding_only": round(tr["openshift"]["ratio_to_agent_procedures"]["per_1000"] * p_os_counted / p["direct"], 2)}
stored = json.load(open(HERE / "scores.json", encoding="utf-8"))
assert stored == res, "scores differ from the stored copy"
out = ROOT / "reproduced" / "POSTHOC-runbook-reading.json"; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
print("Runbook reading: packet rebuilt identically; seal holds; scores match the stored copy.")
print(json.dumps(res["by_source"], indent=1)); print(json.dumps(res["ratio_to_agent"], indent=1))
