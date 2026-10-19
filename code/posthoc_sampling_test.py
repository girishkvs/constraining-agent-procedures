"""POSTHOC: practice 1. Uniform draws against draws stratified by explicit constraint, 100 procedures each.

Reads results/direct-document-results.csv.gz (primary configuration) and writes
reproduced/POSTHOC-sampling-test.json. The stored copy is results/POSTHOC-sampling-test/results.json.
"""
import csv, gzip, json, math, pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
rows = [r for r in csv.DictReader(gzip.open(ROOT / "results" / "direct-document-results.csv.gz", "rt", encoding="utf-8"))
        if r["arm"] == "no_code_examples" and r["segmentation"] == "sentence" and r["triggers"] == "broad"]
P = np.array([int(r["P"]) for r in rows]); N = len(P)
W = np.array([int(r["prose_words"]) for r in rows])
assert N == 1495 and P.sum() == 4080
order = np.argsort(-P, kind="stable"); top = np.zeros(N, bool); top[order[:math.ceil(N / 10)]] = True
strata = {"none": np.where(P == 0)[0], "1-4": np.where((P >= 1) & (P <= 4))[0], "5+": np.where(P >= 5)[0]}
sizes = {k: len(v) for k, v in strata.items()}
n = 100; alloc = {"none": 33, "1-4": 33, "5+": 34}
rng = np.random.default_rng(20261018); R = 10000
U = {"P": [], "any": [], "none": [], "top": [], "mean_est": [], "words": []}
S = {"P": [], "any": [], "none": [], "top": [], "mean_est": [], "none_share_est": [], "words": []}
for _ in range(R):
    u = rng.choice(N, n, replace=False)
    U["P"].append(P[u].sum()); U["any"].append((P[u] > 0).sum()); U["none"].append((P[u] == 0).sum()); U["top"].append(top[u].sum()); U["mean_est"].append(P[u].mean()); U["words"].append(W[u].sum())
    picks = {k: rng.choice(strata[k], alloc[k], replace=False) for k in strata}
    s = np.concatenate(list(picks.values()))
    S["P"].append(P[s].sum()); S["any"].append((P[s] > 0).sum()); S["none"].append((P[s] == 0).sum()); S["top"].append(top[s].sum()); S["words"].append(W[s].sum())
    S["mean_est"].append(sum(sizes[k] / N * P[picks[k]].mean() for k in strata))
    S["none_share_est"].append(sum(sizes[k] / N * (P[picks[k]] == 0).mean() for k in strata))
f = lambda a: round(float(np.mean(a)), 2)
sd = lambda a: round(float(np.std(a)), 3)
res = {"corpus": {"N": N, "P_total": int(P.sum()), "mean_P": round(float(P.mean()), 3), "strata_sizes": sizes, "share_none": round(float((P == 0).mean()), 4)},
       "budget": n, "allocation": alloc, "draws": R, "seed": 20261018,
       "uniform": {"P_covered": f(U["P"]), "with_any_P": f(U["any"]), "with_none": f(U["none"]), "from_top_tenth": f(U["top"]), "mean_P_estimate": f(U["mean_est"]), "mean_P_estimate_sd": sd(U["mean_est"])},
       "stratified": {"P_covered": f(S["P"]), "with_any_P": f(S["any"]), "with_none": f(S["none"]), "from_top_tenth": f(S["top"]), "weighted_mean_P_estimate": f(S["mean_est"]), "weighted_mean_P_estimate_sd": sd(S["mean_est"]), "weighted_share_none_estimate": round(float(np.mean(S["none_share_est"])), 4)}}
res["ratio_P_covered"] = round(res["stratified"]["P_covered"] / res["uniform"]["P_covered"], 2)
res["ratio_from_top_tenth"] = round(res["stratified"]["from_top_tenth"] / res["uniform"]["from_top_tenth"], 2)
res["sd_ratio_mean_estimate"] = round(res["stratified"]["weighted_mean_P_estimate_sd"] / res["uniform"]["mean_P_estimate_sd"], 2)
res["uniform"]["prose_words_read"] = f(U["words"]); res["stratified"]["prose_words_read"] = f(S["words"])
res["ratio_prose_words_read"] = round(res["stratified"]["prose_words_read"] / res["uniform"]["prose_words_read"], 2)
res["ratio_P_covered_per_word"] = round((res["stratified"]["P_covered"] / res["stratified"]["prose_words_read"]) / (res["uniform"]["P_covered"] / res["uniform"]["prose_words_read"]), 2)
out = ROOT / "reproduced" / "POSTHOC-sampling-test.json"; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
print(json.dumps(res, indent=1))
