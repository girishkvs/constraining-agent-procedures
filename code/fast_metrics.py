import math

import numpy as np

from legacy.metrics import Metrics


FIELDS = [
    "statements", "P_only", "O_only", "both", "neither", "eligible_words",
    "prose_words", "prose_P", "prose_units", "code_units", "quote_units", "example_units"
]


class FastMetrics(Metrics):
    def __init__(self, protocol):
        super().__init__({
            "seed": protocol["seed"],
            "length_null": {"replicates": protocol["resampling"]["length_null_replicates"]},
            "bootstrap": {"replicates": protocol["resampling"]["bootstrap_replicates"]}
        })

    def documents(self, values, paths):
        rows = []
        for path, values_row in zip(paths, values):
            row = {name: int(value) for name, value in zip(FIELDS, values_row)}
            row["path"] = path
            row["P"] = row["P_only"] + row["both"]
            row["O_dual"] = row["O_only"] + row["both"]
            row["O_priority"] = row["O_only"]
            rows.append(row)
        return rows

    def ratio(self, numerator, denominator):
        return float(numerator / denominator) if denominator else None

    def top_share(self, values, k, denominator):
        if not denominator:
            return None
        return float(np.partition(values, len(values) - k)[-k:].sum() / denominator)

    def resample(self, values, key):
        n = len(values)
        if not n:
            raise ValueError("Empty frozen population")
        lengths = values[:, 0]
        p_values = values[:, 1] + values[:, 3]
        total_p = int(p_values.sum())
        k = math.ceil(n / 10)
        if np.any(p_values > lengths):
            raise ValueError("Observed P exceeds eligible slots")
        null_seed = self.seed("length_null", *key)
        boot_seed = self.seed("bootstrap", *key)
        null_rng = np.random.Generator(np.random.PCG64(null_seed))
        boot_rng = np.random.Generator(np.random.PCG64(boot_seed))
        null_values = {"top_decile_P_share": [], "zero_P_document_share": []}
        for _ in range(self.protocol["length_null"]["replicates"]):
            allocation = null_rng.multivariate_hypergeometric(lengths, total_p, method="marginals")
            if int(allocation.sum()) != total_p or np.any(allocation > lengths) or np.any(allocation < 0):
                raise ValueError("Finite-slot null allocation failed")
            null_values["top_decile_P_share"].append(self.top_share(allocation, k, total_p))
            null_values["zero_P_document_share"].append(float(np.count_nonzero(allocation == 0) / n))
        bootstrap_values = {
            "top_decile_P_share": [], "zero_P_document_share": [],
            "P_O_ratio_priority": [], "P_O_ratio_dual": [],
            "prose_P_per_1000_words": [], "all_kind_P_per_1000_eligible_words": []
        }
        for _ in range(self.protocol["bootstrap"]["replicates"]):
            indices = boot_rng.integers(0, n, size=n)
            sampled = values[indices]
            totals = sampled.sum(axis=0)
            sampled_p = sampled[:, 1] + sampled[:, 3]
            p_count = int(totals[1] + totals[3])
            bootstrap_values["top_decile_P_share"].append(self.top_share(sampled_p, k, p_count))
            bootstrap_values["zero_P_document_share"].append(float(np.count_nonzero(sampled_p == 0) / n))
            bootstrap_values["P_O_ratio_priority"].append(self.ratio(p_count, int(totals[2])))
            bootstrap_values["P_O_ratio_dual"].append(self.ratio(p_count, int(totals[2] + totals[3])))
            bootstrap_values["prose_P_per_1000_words"].append(self.ratio(1000 * int(totals[7]), int(totals[6])))
            bootstrap_values["all_kind_P_per_1000_eligible_words"].append(self.ratio(1000 * p_count, int(totals[5])))
        observed = {
            "top_decile_P_share": self.top_share(p_values, k, total_p),
            "zero_P_document_share": float(np.count_nonzero(p_values == 0) / n)
        }
        null_summary = {}
        for name, draws in null_values.items():
            defined = [value for value in draws if value is not None]
            obs = observed[name]
            null_summary[name] = {
                "observed": obs,
                "mean": sum(defined) / len(defined) if defined else None,
                "interval": self.interval(draws),
                "upper_tail_reference_p": (
                    (1 + sum(value >= obs for value in defined)) / (1 + len(defined))
                    if defined and obs is not None else None
                )
            }
        return {
            "length_null": null_summary,
            "bootstrap": {name: self.interval(draws) for name, draws in bootstrap_values.items()}
        }, {
            "key": list(key), "numpy_version": np.__version__, "rng": "PCG64",
            "length_null_seed_integer": str(null_seed), "bootstrap_seed_integer": str(boot_seed),
            "length_null": null_values, "bootstrap": bootstrap_values
        }
