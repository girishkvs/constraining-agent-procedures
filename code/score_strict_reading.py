"""POSTHOC strict statement and procedure scoring."""
import csv
import json
import math
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parents[1]
BASE = ARTIFACT / "labels/strict-reading"
KEY = json.loads((BASE / "KEY.json").read_text(encoding="utf-8"))
POOL = {"P_top": 1848, "P_rest": 2232, "O_full": 1864}


def load(reader):
    with (BASE / f"reader-{reader}-statements.csv").open(encoding="utf-8-sig", newline="") as stream:
        st = {r["id"]: r for r in csv.DictReader(stream)}
    with (BASE / f"reader-{reader}-procedures.csv").open(encoding="utf-8-sig", newline="") as stream:
        pr = {r["id"]: r for r in csv.DictReader(stream)}
    assert set(st) == set(KEY["statements"]) and set(pr) == set(KEY["procedures"]), reader
    return st, pr


def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(c - h, 4), round(c + h, 4)]


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)




def score():
    readers = {r: load(r) for r in ("A", "B")}
    ids_by = {s: sorted(i for i, v in KEY["statements"].items() if v["stratum"] == s) for s in POOL}
    question = {"P_top": "forbids", "P_rest": "forbids", "O_full": "requires"}
    out = {"readers": {}, "consensus_both_Y": {}, "either_Y": {}, "agreement": {}}
    for r, (st, pr) in readers.items():
        o = {}
        for s, ids in ids_by.items():
            q = question[s]
            o[s] = {"n": len(ids), "instructs_Y": sum(st[i]["instructs"] == "Y" for i in ids),
                    f"{q}_Y": sum(st[i][q] == "Y" for i in ids),
                    "U_any": sum("U" in (st[i]["instructs"], st[i][q]) for i in ids)}
        o["zero_match_limit_Y"] = sum(v["limit"] == "Y" for v in pr.values())
        o["zero_match_limit_U"] = sum(v["limit"] == "U" for v in pr.values())
        out["readers"][r] = o
    A, B = readers["A"], readers["B"]
    for mode, f in (("consensus_both_Y", all), ("either_Y", any)):
        res = {}
        for s, ids in ids_by.items():
            q = question[s]
            k_q = sum(f(rd[0][i][q] == "Y" for rd in (A, B)) for i in ids)
            k_i = sum(f(rd[0][i]["instructs"] == "Y" for rd in (A, B)) for i in ids)
            res[s] = {"n": len(ids), f"{q}_Y": k_q, f"{q}_rate": round(k_q / len(ids), 4), f"{q}_wilson95": wilson(k_q, len(ids)),
                      "instructs_Y": k_i, "instructs_rate": round(k_i / len(ids), 4), "instructs_wilson95": wilson(k_i, len(ids))}
        for basis in ("forbids", "instructs"):
            rt, rr = res["P_top"][f"{basis}_rate"], res["P_rest"][f"{basis}_rate"]
            top, rest = rt * POOL["P_top"], rr * POOL["P_rest"]
            res[f"adjusted_top_share_{basis}"] = round(top / (top + rest), 4) if top + rest else None
            res[f"weighted_P_precision_{basis}"] = round((top + rest) / (POOL["P_top"] + POOL["P_rest"]), 4)
        kz = sum(f(rd[1][z]["limit"] == "Y" for rd in (A, B)) for z in KEY["procedures"])
        res["zero_match_limit"] = {"n": 30, "Y": kz, "rate": round(kz / 30, 4), "wilson95": wilson(kz, 30)}
        out[mode] = res
    P_ids = ids_by["P_top"] + ids_by["P_rest"]
    O_ids = ids_by["O_full"]
    all_ids = sorted(KEY["statements"])
    out["agreement"] = {
        "instructs_all_100": {"kappa": kappa([A[0][i]["instructs"] for i in all_ids], [B[0][i]["instructs"] for i in all_ids]),
                              "raw": sum(A[0][i]["instructs"] == B[0][i]["instructs"] for i in all_ids)},
        "forbids_P_70": {"kappa": kappa([A[0][i]["forbids"] for i in P_ids], [B[0][i]["forbids"] for i in P_ids]),
                         "raw": sum(A[0][i]["forbids"] == B[0][i]["forbids"] for i in P_ids)},
        "requires_O_30": {"kappa": kappa([A[0][i]["requires"] for i in O_ids], [B[0][i]["requires"] for i in O_ids]),
                          "raw": sum(A[0][i]["requires"] == B[0][i]["requires"] for i in O_ids)},
        "limit_Z_30": {"kappa": kappa([A[1][z]["limit"] for z in KEY["procedures"]], [B[1][z]["limit"] for z in KEY["procedures"]]),
                       "raw": sum(A[1][z]["limit"] == B[1][z]["limit"] for z in KEY["procedures"])},
    }
    out["disagreements_forbids_P"] = [{"id": i, "stratum": KEY["statements"][i]["stratum"], "A": A[0][i]["forbids"], "B": B[0][i]["forbids"],
                                       "A_reason": A[0][i]["reason"], "B_reason": B[0][i]["reason"]} for i in P_ids if A[0][i]["forbids"] != B[0][i]["forbids"]]
    out["note"] = 'POSTHOC strict scoring. Rubric: labels/strict-reading/READ-ME.md. Input hashes: labels/strict-reading/SEAL-before-reading.json.'
    return out


if __name__ == "__main__":
    value = score()
    output = ARTIFACT / "reproduced/strict-reading-scores.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=1), encoding="utf-8")
    print(json.dumps(value["consensus_both_Y"], indent=1))
