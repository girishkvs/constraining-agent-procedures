import collections
import json
import math
import time
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

from analysis import Analysis
from common import OUT, OLD


class Models(Analysis):
    def design(self, docs, tier="primary_tier", specification="full", outcome="primary"):
        selected = [r for r in docs if r["prose_words"] > 0]
        data = pd.DataFrame({
            "P": [r["outcomes"][outcome]["P"] for r in selected],
            "tier": [r[tier] for r in selected], "publisher": [r["publisher"] for r in selected],
            "family": [r["family"] for r in selected], "words": [r["prose_words"] for r in selected],
            "steps": [r["steps"] for r in selected], "headings": [r["headings"] for r in selected]
        })
        values = {"Intercept": np.ones(len(data))}
        if specification != "no_tier":
            for value in ("D", "W"):
                if value in set(data["tier"]):
                    values["tier_" + value] = (data["tier"] == value).astype(float).to_numpy()
        values["log_prose_words"] = np.log(data["words"].to_numpy(dtype=float))
        if specification != "tier_length_only":
            values["log1p_steps"] = np.log1p(data["steps"].to_numpy(dtype=float))
            values["log1p_headings"] = np.log1p(data["headings"].to_numpy(dtype=float))
            for field in ("publisher", "family"):
                levels = sorted(set(data[field]))
                for level in levels[1:]:
                    values[field + "[" + level + "]"] = (data[field] == level).astype(float).to_numpy()
        x = pd.DataFrame(values, dtype=float)
        return selected, data, x, data["P"].to_numpy(dtype=float)

    def fitted(self, y, x, family, start=None, robust=True):
        with warnings.catch_warnings(record=True) as capture:
            warnings.simplefilter("always")
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                if family == "NB2":
                    model = sm.NegativeBinomial(y, x, loglike_method="nb2")
                    result = model.fit(start_params=start, method="bfgs", maxiter=200, disp=False,
                                       cov_type="HC0" if robust else "nonrobust")
                    converged = bool(result.mle_retvals.get("converged", False))
                    alpha = float(np.asarray(result.params)[-1])
                    valid = converged and np.isfinite(alpha) and alpha > 0
                else:
                    model = sm.Poisson(y, x)
                    result = model.fit(start_params=start, method="newton", maxiter=200, disp=False,
                                       cov_type="HC0" if robust else "nonrobust")
                    converged = bool(result.mle_retvals.get("converged", False))
                    valid = converged
                valid = valid and np.all(np.isfinite(result.params))
                if robust:
                    valid = valid and np.all(np.isfinite(result.bse))
        return result, bool(valid), [{"category": type(w.message).__name__, "message": str(w.message)[:350]}
                                     for w in capture]

    def point_fit(self, label, docs, tier="primary_tier", specification="full", outcome="primary"):
        self.check()
        selected, data, x, y = self.design(docs, tier, specification, outcome)
        if len(data) <= len(x.columns) or np.linalg.matrix_rank(x.to_numpy()) != len(x.columns):
            return {"label": label, "status": "UNSUPPORTED_RANK_OR_N", "N": len(data),
                    "columns": list(x.columns)}, None
        fallback = None
        try:
            result, valid, captured = self.fitted(y, x, "NB2")
            if not valid:
                raise RuntimeError("NB2 convergence/finite-alpha/robust-SE check failed")
            family = "NB2"
        except Exception as exc:
            fallback = str(exc)
            try:
                result, valid, captured = self.fitted(y, x, "Poisson")
                family = "Poisson"
                if not valid:
                    raise RuntimeError("Poisson convergence/finite robust SE check failed")
            except Exception as second:
                return {"label": label, "status": "FIT_FAILED", "N": len(data),
                        "NB_failure": fallback, "Poisson_failure": str(second)}, None
        names = list(x.columns) + (["alpha"] if family == "NB2" else [])
        params = np.asarray(result.params)
        se = np.asarray(result.bse)
        coefficients = []
        for name, estimate, error in zip(names, params, se):
            low = float(estimate - 1.959963984540054 * error)
            high = float(estimate + 1.959963984540054 * error)
            coefficients.append({
                "term": name, "coefficient": float(estimate), "model_robust_SE": float(error),
                "coefficient_Wald95_low": low, "coefficient_Wald95_high": high,
                "IRR": None if name == "alpha" else self.safe_exp(estimate),
                "IRR_Wald95_low": None if name == "alpha" else self.safe_exp(low),
                "IRR_Wald95_high": None if name == "alpha" else self.safe_exp(high)
            })
        record = {
            "label": label, "status": "PASS", "model_family": family, "NB_fallback_reason": fallback,
            "specification": specification, "tier_source": tier, "outcome": outcome,
            "N": len(data), "dropped_zero_word_ids": [r["id"] for r in docs if r["prose_words"] == 0],
            "tier_counts_in_model": dict(collections.Counter(data["tier"])),
            "publisher_FE": specification != "tier_length_only", "family_FE": specification != "tier_length_only",
            "covariance": "HC0",
            "log_likelihood": float(result.llf), "AIC": float(result.aic), "BIC": float(result.bic),
            "coefficients": coefficients, "warnings": captured[:12]
        }
        return record, {"selected": selected, "data": data, "x": x, "y": y,
                        "result": result, "family": family, "names": names}

    def safe_exp(self, value):
        return float(np.exp(value)) if np.isfinite(value) and value < 709 else None

    def run(self):
        started = time.monotonic()
        docs = self.documents()
        records = []
        fitted_primary = None
        for label, spec in (("primary_full", "full"), ("no_tier", "no_tier"),
                            ("tier_length_only", "tier_length_only")):
            record, fitted = self.point_fit(label, docs, specification=spec)
            records.append(record)
            if label == "primary_full":
                fitted_primary = fitted
            print(label, record["status"], record.get("model_family"), "N", record["N"], flush=True)
        if len([r for r in docs if r["prose_words"] == 0]) != 4:
            raise ValueError("Exactly four transformed-empty regression exclusions expected")
        excluded = set(json.loads((OLD / "POSTHOC-origin/definite-posthoc-exclusion-ids.json").read_text())["excluded_ids"])
        variants = [
            ("V-allcode", docs, "V-allcode", "primary"),
            ("V-inline", docs, "V-inline", "primary"), ("V-prose", docs, "V-prose", "primary"),
            ("V-desc_SKILLS_ONLY", [r for r in docs if r["family"] == "skill"], "V-desc", "primary"),
            ("skills_only", [r for r in docs if r["family"] == "skill"], "primary_tier", "primary"),
            ("all_kind_body", docs, "primary_tier", "all_kind"),
            ("narrow_dictionary", docs, "primary_tier", "narrow"),
            ("POSTHOC_origin_1463", [r for r in docs if r["id"] not in excluded], "primary_tier", "primary")
        ]
        for label, subset, tier, outcome in variants:
            record, _ = self.point_fit(label, subset, tier, "full", outcome)
            records.append(record)
        records.append({
            **records[0], "label": "priority_overlap", "reuse_reason": "P count is identical under priority and dual; O-only bookkeeping changes in B5 table, not the P model."
        })
        self.write("B3-models-point.json", records)
        flat = []
        for record in records:
            for coefficient in record.get("coefficients", []):
                flat.append({"model": record["label"], "family": record["model_family"], "N": record["N"], **coefficient})
        self.csv("tables/B3-all-model-coefficients.csv", flat)
        self.csv("tables/B3-model-comparison.csv", [
            {k: r.get(k) for k in ["label", "status", "model_family", "N", "log_likelihood", "AIC", "BIC", "NB_fallback_reason"]}
            for r in records])
        if fitted_primary is None:
            self.write("B3-bootstrap-status.json", {"status": "UNSUPPORTED_PRIMARY_FIT", "requested_draws": 999,
                                                    "completed_draws": 0})
            return
        draws = self.bootstrap(fitted_primary)
        self.write("B3-model-results.json", {
            "point_models": records, "primary_full_bootstrap": draws,
            "elapsed_seconds": time.monotonic() - started
        })

    def bootstrap(self, fitted):
        x = fitted["x"]
        y = fitted["y"]
        data = fitted["data"]
        rng = np.random.Generator(np.random.PCG64(self.seed("publisher-stratified-NB-bootstrap-999")))
        groups = [np.flatnonzero(data["publisher"].to_numpy() == pub) for pub in sorted(set(data["publisher"]))]
        start = np.asarray(fitted["result"].params)
        family = fitted["family"]
        names = fitted["names"]
        values = {"tier_D": [], "tier_W": []}
        failures = []
        path = OUT / "B3-bootstrap-draws.jsonl"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for iteration in range(999):
                self.check()
                indices = np.concatenate([rng.choice(group, size=len(group), replace=True) for group in groups])
                try:
                    result, valid, warnings_found = self.fitted(y[indices], x.iloc[indices], family, start, False)
                    if not valid:
                        raise RuntimeError("Bootstrap selected-family fit did not converge with valid parameters")
                    params = dict(zip(names, np.asarray(result.params)))
                    row = {"draw": iteration, "status": "PASS", "N": len(indices),
                           "tier_D": float(params["tier_D"]) if "tier_D" in params else None,
                           "tier_W": float(params["tier_W"]) if "tier_W" in params else None}
                except Exception as exc:
                    row = {"draw": iteration, "status": "FAILED", "N": len(indices),
                           "tier_D": None, "tier_W": None, "reason": str(exc)[:500]}
                    failures.append(row)
                for name in values:
                    values[name].append(row[name])
                stream.write(json.dumps(row, sort_keys=True) + "\n")
                if (iteration + 1) % 25 == 0:
                    stream.flush()
                    print(f"Primary full publisher-stratified bootstrap {iteration+1}/999; failed={len(failures)}", flush=True)
        intervals = {}
        for name, draws in values.items():
            defined = sorted(v for v in draws if v is not None and np.isfinite(v))
            lo = defined[max(0, math.ceil(.025 * len(defined)) - 1)] if defined else None
            hi = defined[max(0, math.ceil(.975 * len(defined)) - 1)] if defined else None
            coefficient = next((c for c in json.loads((OUT / "B3-models-point.json").read_text())[0]["coefficients"]
                                if c["term"] == name), None)
            intervals[name] = {
                "IRR_point": coefficient["IRR"] if coefficient else None,
                "IRR_bootstrap95_low": self.safe_exp(lo) if lo is not None else None,
                "IRR_bootstrap95_high": self.safe_exp(hi) if hi is not None else None,
                "defined_draws": len(defined), "undefined_or_failed_draws": 999 - len(defined)
            }
        result = {
            "status": "COMPLETE" if not failures else "COMPLETE_WITH_EXPLICIT_FAILED_DRAWS",
            "model_family_fixed_from_primary": family, "replicates_requested": 999,
            "replicates_attempted": 999, "failed_fits": len(failures), "intervals": intervals,
            "stratification": "Rows sampled with replacement within publisher; original publisher Ns retained, total N fixed",
            "seed_integer": str(self.seed("publisher-stratified-NB-bootstrap-999")),
            "percentiles": "nearest-rank 2.5/97.5"
        }
        self.write("B3-bootstrap-status.json", result)
        self.csv("tables/B3-primary-tier-IRR-bootstrap.csv", [{"term": k, **v} for k, v in intervals.items()])
        return result


if __name__ == "__main__":
    Models().run()
