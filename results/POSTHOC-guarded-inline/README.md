# POSTHOC guarded inline commands

Primary command matches are retained. Inline additions are excluded when their
physical line overlaps a sentence/list-item unit matching broad P or O.

From the artifact root:

```text
python code/posthoc_guarded_inline.py
```

Output: `reproduced/POSTHOC-guarded-inline/`. The output contains D/W/R counts,
per-document classes, changes from primary, information-based and HC0 Wald
intervals, and 999 within-publisher bootstrap attempts with every failed draw kept.
The stored files here contain the corresponding counts, intervals, status, and draws.
