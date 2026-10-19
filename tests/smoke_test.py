import collections
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from measure import Measurement
from score_labels import Scorer


def main():
    m = Measurement()
    rows, docs, missing = m.run(allow_missing=True)
    checks = []

    def check(name, actual, expected):
        checks.append({"check": name, "actual": actual, "expected": expected, "pass": actual == expected})

    direct = [r for r in rows if r["corpus"] == "direct"]
    check("direct N", len(direct), 1495)
    check("direct P", sum(r["P"] for r in direct), 4080)
    check("direct O", sum(r["O_dual"] for r in direct), 1864)
    check("direct zero-P", sum(r["P"] == 0 for r in direct), 462)
    share = sum(sorted((r["P"] for r in direct), reverse=True)[:150]) / sum(r["P"] for r in direct)
    check("direct top-150 percent", round(100 * share, 2), 45.29)
    for corpus, n, p in (("agent_context", 1540, 2403), ("gitlab", 833, 799), ("openshift", 288, 229)):
        selected = [r for r in rows if r["corpus"] == corpus]
        check(corpus + " N", len(selected), n)
        check(corpus + " P", sum(r["P"] for r in selected), p)
    check("command tiers", dict(collections.Counter(r["primary_tier"] for r in docs)), {"D": 22, "W": 140, "R": 1333})
    scorer = Scorer(ROOT / "labels/KEY.json")
    scored = scorer.score(scorer.read_csvs(ROOT / "labels/statements.csv", ROOT / "labels/procedures.csv"))
    for stratum, expected, total in (("P_top", 31, 35), ("P_rest", 30, 35), ("O_full", 28, 30)):
        check("operative " + stratum, scored["operative_samples"][stratum]["Y"], expected)
        check("operative denominator " + stratum, scored["operative_samples"][stratum]["valid_Y_or_N"], total)
    for row in json.loads((ROOT / "code/FROZEN-BYTES.json").read_text(encoding="utf-8")):
        import hashlib
        check("frozen " + row["path"], hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest(), row["sha256"])
    check("all source paths present", len(missing), 0)
    redacted = [r for r in m.manifest() if r["layout_status"] == "REDACTED_SECRET"]
    check("redacted registry identities", sorted(r["document_id"] for r in redacted), sorted(m.sources.redactions))
    from score_strict_reading import score
    strict = score()
    strict_stored = json.loads((ROOT / "labels/strict-reading/scores.json").read_text(encoding="utf-8"))
    check("POSTHOC strict scores exact", strict, strict_stored)
    for group, field, yes, n in (("P_top", "forbids_Y", 28, 35), ("P_rest", "forbids_Y", 25, 35),
                                 ("O_full", "requires_Y", 25, 30)):
        check("POSTHOC strict " + group, strict["consensus_both_Y"][group][field], yes)
        check("POSTHOC strict denominator " + group, strict["consensus_both_Y"][group]["n"], n)
    check("POSTHOC strict P agreement", strict["agreement"]["forbids_P_70"]["raw"], 69)
    check("POSTHOC strict P agreement denominator",
          strict["consensus_both_Y"]["P_top"]["n"] + strict["consensus_both_Y"]["P_rest"]["n"], 70)
    check("POSTHOC zero-match limits", strict["consensus_both_Y"]["zero_match_limit"]["Y"], 16)
    check("POSTHOC zero-match limit denominator", strict["consensus_both_Y"]["zero_match_limit"]["n"], 30)
    guarded = json.loads((ROOT / "results/POSTHOC-guarded-inline/results.json").read_text(encoding="utf-8"))
    check("POSTHOC guarded D IRR", round(guarded["contrasts"]["tier_D"]["IRR"], 3), 1.298)
    check("POSTHOC guarded W IRR", round(guarded["contrasts"]["tier_W"]["IRR"], 3), 1.140)
    topics = json.loads((ROOT / "results/POSTHOC-topic-words/results.json").read_text(encoding="utf-8"))
    classes = {r["class"]: r for r in topics["classes"]}
    excess = {name: row["top_tenth_share"] - row["references"]["length_null"]["top_decile_P_share"]["mean"]
              for name, row in classes.items()}
    for name in ("tests", "users"):
        check("POSTHOC topic excess " + name, excess[name] > excess["prohibition"], True)
    result = {"status": "PASS" if all(r["pass"] for r in checks) else "FAIL", "checks": checks, "missing_files": missing,
              "redacted_documents": [{"document_id": r["document_id"], "relative_path": r["relative_path"],
                                      "verification": "distributed hash"} for r in redacted]}
    print(json.dumps(result, indent=2))
    (ROOT / "results/smoke-test.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
