"""POSTHOC: 95% intervals for the strict reading's corrected top-tenth share and weighted precision.

Reads labels/strict-reading/scores.json (statements both readers said forbid something) and
labels/sampling-design.json (prohibition matches in the most constrained tenth and in the rest), and
writes reproduced/POSTHOC-reading-intervals.json. The stored copy is
results/POSTHOC-reading-intervals/results.json.

The tenth is fixed: the 150 procedures with the most prohibition matches. The corrected share is the
share of real prohibitions held by those same 150, not by a tenth ranked again after reading.
"""
import json, math, pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
scores = json.loads((ROOT / "labels" / "strict-reading" / "scores.json").read_text(encoding="utf-8"))["consensus_both_Y"]
pools = json.loads((ROOT / "labels" / "sampling-design.json").read_text(encoding="utf-8"))["population_pools"]
n_top, y_top = scores["P_top"]["n"], scores["P_top"]["forbids_Y"]
n_rest, y_rest = scores["P_rest"]["n"], scores["P_rest"]["forbids_Y"]
assert (n_top, y_top, n_rest, y_rest, pools["P_top"], pools["P_rest"]) == (35, 28, 35, 25, 1848, 2232)


class ReadingIntervals:
    def __init__(self, m_top, m_rest):
        self.m_top = m_top
        self.m_rest = m_rest

    def share(self, p_top, p_rest):
        return self.m_top * p_top / (self.m_top * p_top + self.m_rest * p_rest)

    def precision(self, p_top, p_rest):
        return (self.m_top * p_top + self.m_rest * p_rest) / (self.m_top + self.m_rest)

    def nearest_rank(self, values):
        ordered = np.sort(values)
        return [round(float(ordered[math.ceil(q * len(ordered)) - 1]), 4) for q in (0.025, 0.975)]

    def both(self, p_top, p_rest):
        return {"corrected_top_tenth_share": self.nearest_rank(self.share(p_top, p_rest)),
                "weighted_precision": self.nearest_rank(self.precision(p_top, p_rest))}


calc = ReadingIntervals(pools["P_top"], pools["P_rest"])
R = 100000
seed = 20261019
rng = np.random.default_rng(seed)
boot_top = rng.binomial(n_top, y_top / n_top, R) / n_top
boot_rest = rng.binomial(n_rest, y_rest / n_rest, R) / n_rest
jeff_top = rng.beta(y_top + 0.5, n_top - y_top + 0.5, R)
jeff_rest = rng.beta(y_rest + 0.5, n_rest - y_rest + 0.5, R)
res = {
    "inputs": {"read_top": n_top, "forbids_top": y_top, "read_rest": n_rest, "forbids_rest": y_rest,
               "matches_top_tenth": calc.m_top, "matches_rest": calc.m_rest},
    "unadjusted_top_tenth_share": round(calc.m_top / (calc.m_top + calc.m_rest), 4),
    "corrected_top_tenth_share": round(calc.share(y_top / n_top, y_rest / n_rest), 4),
    "weighted_precision": round(calc.precision(y_top / n_top, y_rest / n_rest), 4),
    "draws": R, "seed": seed, "percentiles": "nearest-rank 2.5/97.5",
    "parametric_bootstrap95": calc.both(boot_top, boot_rest),
    "jeffreys95": calc.both(jeff_top, jeff_rest),
}
out = ROOT / "reproduced" / "POSTHOC-reading-intervals.json"; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
print(json.dumps(res, indent=1))
