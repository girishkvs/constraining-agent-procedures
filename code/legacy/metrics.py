import bisect
import hashlib
import math
import random
import statistics


class Metrics:
    def __init__(self, protocol):
        self.protocol = protocol

    def divide(self, numerator, denominator):
        return numerator / denominator if denominator else None

    def seed(self, purpose, *parts):
        text = "|".join([self.protocol["seed"], purpose, *map(str, parts)])
        return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)

    def ranks(self, values):
        ordered = sorted(range(len(values)), key=lambda index: values[index])
        result = [0.0] * len(values)
        start = 0
        while start < len(ordered):
            end = start + 1
            while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
                end += 1
            rank = (start + 1 + end) / 2
            for position in range(start, end):
                result[ordered[position]] = rank
            start = end
        return result

    def correlation(self, first, second):
        if len(first) < 2:
            return None
        try:
            return statistics.correlation(first, second)
        except statistics.StatisticsError:
            return None

    def aggregate(self, documents, overlap):
        count = len(documents)
        p_only = sum(row["P_only"] for row in documents)
        o_only = sum(row["O_only"] for row in documents)
        both = sum(row["both"] for row in documents)
        neither = sum(row["neither"] for row in documents)
        p_count = p_only + both
        o_count = o_only + (both if overlap == "dual" else 0)
        statement_count = p_only + o_only + both + neither
        ordered = sorted(documents, key=lambda row: (-row["P"], row["path"]))
        top_k = math.ceil(count / 10)
        top_p = sum(row["P"] for row in ordered[:top_k])
        zero_p = sum(row["P"] == 0 for row in documents)
        prose_words = sum(row["prose_words"] for row in documents)
        eligible_words = sum(row["eligible_words"] for row in documents)
        prose_p = sum(row["prose_P"] for row in documents)
        return {
            "documents": count,
            "statements": statement_count,
            "P_only": p_only, "O_only": o_only, "both": both, "neither": neither,
            "P": p_count, "O": o_count,
            "P_O_ratio": self.divide(p_count, o_count),
            "zero_P_documents": zero_p,
            "zero_P_document_share": self.divide(zero_p, count),
            "top_decile_k": top_k, "top_decile_P": top_p,
            "top_decile_P_share": self.divide(top_p, p_count),
            "overlap_per_statement": self.divide(both, statement_count),
            "overlap_per_any_match": self.divide(both, p_only + o_only + both),
            "eligible_words": eligible_words, "prose_words": prose_words,
            "prose_P": prose_p,
            "prose_P_per_1000_words": self.divide(1000 * prose_p, prose_words),
            "all_kind_P_per_1000_eligible_words": self.divide(1000 * p_count, eligible_words),
            "zero_unit_documents": sum(row["statements"] == 0 for row in documents)
        }

    def associations(self, documents):
        matches = [row["P"] for row in documents]
        statements = [row["statements"] for row in documents]
        prose_words = [row["prose_words"] for row in documents]
        return {
            "pearson_P_statements": self.correlation(matches, statements),
            "spearman_P_statements": self.correlation(self.ranks(matches), self.ranks(statements)),
            "pearson_P_prose_words": self.correlation(matches, prose_words),
            "spearman_P_prose_words": self.correlation(self.ranks(matches), self.ranks(prose_words))
        }

    def interval(self, values):
        defined = sorted(value for value in values if value is not None)
        if not defined:
            return {
                "low": None, "high": None,
                "defined_replicates": 0, "undefined_replicates": len(values)
            }
        low_index = max(0, math.ceil(0.025 * len(defined)) - 1)
        high_index = max(0, math.ceil(0.975 * len(defined)) - 1)
        return {
            "low": defined[low_index], "high": defined[high_index],
            "defined_replicates": len(defined),
            "undefined_replicates": len(values) - len(defined)
        }

    def allocate(self, rng, lengths, match_total):
        total = sum(lengths)
        if not 0 <= match_total <= total:
            raise ValueError("Length-null match total outside eligible statement count")
        cumulative = []
        running = 0
        for length in lengths:
            running += length
            cumulative.append(running)
        counts = [0] * len(lengths)
        for slot in rng.sample(range(total), match_total):
            counts[bisect.bisect_right(cumulative, slot)] += 1
        return counts

    def null_distribution(self, documents, key):
        seed = self.seed("length_null", *key)
        rng = random.Random(seed)
        repetitions = self.protocol["length_null"]["replicates"]
        lengths = [row["statements"] for row in documents]
        total_p = sum(row["P"] for row in documents)
        top_k = math.ceil(len(documents) / 10)
        top_shares = []
        zero_shares = []
        for _ in range(repetitions):
            counts = self.allocate(rng, lengths, total_p)
            if sum(counts) != total_p or any(
                value > length for value, length in zip(counts, lengths)
            ):
                raise ValueError("Length-null allocation integrity failure")
            top_shares.append(
                self.divide(sum(sorted(counts, reverse=True)[:top_k]), total_p)
            )
            zero_shares.append(self.divide(sum(value == 0 for value in counts), len(counts)))
        observed = self.aggregate(documents, "dual")
        result = {}
        for name, values in (
            ("top_decile_P_share", top_shares),
            ("zero_P_document_share", zero_shares)
        ):
            defined = [value for value in values if value is not None]
            observed_value = observed[name]
            result[name] = {
                "observed": observed_value,
                "mean": statistics.fmean(defined) if defined else None,
                "interval": self.interval(values),
                "upper_tail_reference_p": (
                    (1 + sum(value >= observed_value for value in defined)) / (1 + len(defined))
                    if defined and observed_value is not None else None
                )
            }
        return result, {
            "seed_integer": str(seed),
            "top_decile_P_share": top_shares,
            "zero_P_document_share": zero_shares
        }

    def bootstrap(self, documents, key):
        seed = self.seed("bootstrap", *key)
        rng = random.Random(seed)
        repetitions = self.protocol["bootstrap"]["replicates"]
        values = {
            "top_decile_P_share": [], "zero_P_document_share": [],
            "P_O_ratio_priority": [], "P_O_ratio_dual": [],
            "prose_P_per_1000_words": []
        }
        n = len(documents)
        for _ in range(repetitions):
            sampled = [documents[rng.randrange(n)] for _ in range(n)]
            dual = self.aggregate(sampled, "dual")
            values["top_decile_P_share"].append(dual["top_decile_P_share"])
            values["zero_P_document_share"].append(dual["zero_P_document_share"])
            values["P_O_ratio_dual"].append(dual["P_O_ratio"])
            p_total = dual["P"]
            o_only = dual["O_only"]
            values["P_O_ratio_priority"].append(self.divide(p_total, o_only))
            values["prose_P_per_1000_words"].append(dual["prose_P_per_1000_words"])
        return {
            name: self.interval(items) for name, items in values.items()
        }, {"seed_integer": str(seed), **values}
