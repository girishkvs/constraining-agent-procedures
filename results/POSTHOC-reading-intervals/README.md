# POSTHOC: intervals for the strict reading's corrected share

Made after the main measurement. In the strict reading, 28 of 35 prohibition matches drawn from the
most constrained tenth forbid something, against 25 of 35 from the rest. Applying those two rates to
the 1,848 and 2,232 matches in the two groups gives:

- the share of real prohibitions held by the same tenth: 48.1 percent, against 45.3 percent as counted;
- the share of all prohibition matches that forbid something: 75.3 percent.

The tenth is fixed: the 150 procedures with the most matches. The corrected share is for those 150,
not for a tenth ranked again after reading.

The 95% intervals come from 100,000 draws of both reading counts, binomial at the observed rates,
seed `20261019`, nearest-rank 2.5 and 97.5 percent. A Jeffreys interval is given as a check. The
statements were drawn without replacement from much larger pools (35 of 1,848 and 35 of 2,232),
which the binomial ignores.

| | Point | 95% interval | Jeffreys |
|---|---:|---|---|
| Corrected top-tenth share | 48.1% | 41.5–55.4% | 41.5–55.2% |
| Share of matches that forbid something | 75.3% | 64.9–85.2% | 64.1–83.9% |

Rerun with `python code/posthoc_reading_intervals.py`, which writes
`reproduced/POSTHOC-reading-intervals.json`.
