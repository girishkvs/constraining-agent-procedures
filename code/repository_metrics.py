import hashlib
import math

import numpy as np

from fast_metrics import FastMetrics


class RepositoryMetrics(FastMetrics):
    def __init__(self, protocol):
        super().__init__(protocol)
        self.revision_protocol = protocol
        self.repositories = []
        self.repository_indices = []
        self.repository_index_per_file = None

    def bind_repositories(self, labels):
        canonical = [name.casefold() for name in labels]
        self.repositories = sorted(set(canonical))
        positions = {name: index for index, name in enumerate(self.repositories)}
        self.repository_index_per_file = np.array([positions[name] for name in canonical], dtype=np.int64)
        self.repository_indices = [
            np.flatnonzero(self.repository_index_per_file == index) for index in range(len(self.repositories))
        ]

    def null_summary(self, draws, observed):
        result = {}
        for name, values in draws.items():
            defined = [value for value in values if value is not None]
            obs = observed[name]
            result[name] = {
                "observed": obs, "mean": sum(defined) / len(defined) if defined else None,
                "interval": self.interval(values),
                "upper_tail_reference_p": (
                    (1 + sum(value >= obs for value in defined)) / (1 + len(defined))
                    if defined and obs is not None else None
                )
            }
        return result

    def resample(self, values, key):
        n = len(values)
        if not n or self.repository_index_per_file is None or len(self.repository_index_per_file) != n:
            raise ValueError("Repository clustering is not bound to all file identities")
        r = len(self.repositories)
        lengths = values[:, 0]
        p_values = values[:, 1] + values[:, 3]
        total_p = int(p_values.sum())
        k = math.ceil(n / 10)
        if np.any(p_values > lengths):
            raise ValueError("Observed P exceeds finite slots")
        global_seed = self.seed("length_null", *key)
        repository_null_seed = self.seed("length_null_repository_conditioned", *key)
        bootstrap_seed = self.seed("repository_cluster_bootstrap", *key)
        global_rng = np.random.Generator(np.random.PCG64(global_seed))
        repo_rng = np.random.Generator(np.random.PCG64(repository_null_seed))
        boot_rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
        global_draws = {"top_decile_P_share": [], "zero_P_document_share": []}
        repository_draws = {"top_decile_P_share": [], "zero_P_document_share": []}
        for _ in range(self.protocol["length_null"]["replicates"]):
            allocation = (
                global_rng.multivariate_hypergeometric(lengths, total_p, method="marginals")
                if total_p else np.zeros(n, dtype=np.int64)
            )
            if int(allocation.sum()) != total_p or np.any(allocation > lengths) or np.any(allocation < 0):
                raise ValueError("Global finite-slot integrity failure")
            global_draws["top_decile_P_share"].append(self.top_share(allocation, k, total_p))
            global_draws["zero_P_document_share"].append(float(np.count_nonzero(allocation == 0) / n))
        for _ in range(self.revision_protocol["resampling"]["repository_conditioned_length_null_replicates"]):
            allocation = np.zeros(n, dtype=np.int64)
            for indices in self.repository_indices:
                target = int(p_values[indices].sum())
                if len(indices) == 1:
                    allocation[indices] = target
                elif target:
                    allocation[indices] = repo_rng.multivariate_hypergeometric(lengths[indices], target, method="marginals")
                if int(allocation[indices].sum()) != target:
                    raise ValueError("Repository-conditioned P total changed")
            if int(allocation.sum()) != total_p or np.any(allocation > lengths) or np.any(allocation < 0):
                raise ValueError("Repository finite-slot integrity failure")
            repository_draws["top_decile_P_share"].append(self.top_share(allocation, k, total_p))
            repository_draws["zero_P_document_share"].append(float(np.count_nonzero(allocation == 0) / n))
        bootstrap_values = {
            "top_decile_P_share": [], "zero_P_document_share": [],
            "P_O_ratio_priority": [], "P_O_ratio_dual": [],
            "prose_P_per_1000_words": [], "all_kind_P_per_1000_eligible_words": []
        }
        file_counts = []
        selected_cluster_digest = hashlib.sha256()
        for _ in range(self.protocol["bootstrap"]["replicates"]):
            selected = boot_rng.integers(0, r, size=r)
            selected_cluster_digest.update(np.asarray(selected, dtype="<i8").tobytes())
            multiplicities = np.bincount(selected, minlength=r)
            weights = multiplicities[self.repository_index_per_file]
            sampled = np.repeat(values, weights, axis=0)
            sampled_n = len(sampled)
            if not sampled_n or int(multiplicities.sum()) != r:
                raise ValueError("Repository bootstrap cluster count failed")
            file_counts.append(sampled_n)
            totals = sampled.sum(axis=0)
            sample_p = sampled[:, 1] + sampled[:, 3]
            p_count = int(totals[1] + totals[3])
            bootstrap_values["top_decile_P_share"].append(self.top_share(sample_p, math.ceil(sampled_n / 10), p_count))
            bootstrap_values["zero_P_document_share"].append(float(np.count_nonzero(sample_p == 0) / sampled_n))
            bootstrap_values["P_O_ratio_priority"].append(self.ratio(p_count, int(totals[2])))
            bootstrap_values["P_O_ratio_dual"].append(self.ratio(p_count, int(totals[2] + totals[3])))
            bootstrap_values["prose_P_per_1000_words"].append(self.ratio(1000 * int(totals[7]), int(totals[6])))
            bootstrap_values["all_kind_P_per_1000_eligible_words"].append(self.ratio(1000 * p_count, int(totals[5])))
        observed = {
            "top_decile_P_share": self.top_share(p_values, k, total_p),
            "zero_P_document_share": float(np.count_nonzero(p_values == 0) / n)
        }
        design = {
            "unit": "repository_cluster", "repositories": r, "clusters_sampled_per_draw": r,
            "file_identities_per_draw": file_counts,
            "minimum_file_identities_per_draw": min(file_counts),
            "maximum_file_identities_per_draw": max(file_counts),
            "selected_repository_index_stream_sha256": selected_cluster_digest.hexdigest(),
            "flat_file_bootstrap_used_for_population": False
        }
        return {
            "length_null": self.null_summary(global_draws, observed),
            "repository_conditioned_length_null": self.null_summary(repository_draws, observed),
            "bootstrap": {name: self.interval(draws) for name, draws in bootstrap_values.items()},
            "bootstrap_design": design
        }, {
            "key": list(key), "numpy_version": np.__version__, "rng": "PCG64",
            "length_null_seed_integer": str(global_seed),
            "repository_conditioned_length_null_seed_integer": str(repository_null_seed),
            "bootstrap_seed_integer": str(bootstrap_seed),
            "length_null": global_draws, "repository_conditioned_length_null": repository_draws,
            "bootstrap": bootstrap_values, "bootstrap_design": design
        }
