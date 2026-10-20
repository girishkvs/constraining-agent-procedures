# POSTHOC: the runbook reading

Made after the main measurement. It asks how many runbook matches are real prohibitions, under the rubric
of the strict reading (`labels/strict-reading/READ-ME.md`).

- **Sample:** 35 prohibition matches in the primary configuration from each of three sources:
  - GitLab's runbooks (pool 799);
  - OpenShift's runbooks other than the repeated support-case sentence (pool 149; the sentence supplies
    the other 80 matches and forbids nothing);
  - the public agent procedures not already in the strict reading (pool 4,004).
- **Packet:** fixed seeds; shuffled into `R-001` to `R-105`.
  - `statements-to-read.csv` gives each statement with its source line and neighbours, but not its
    source, so the analysts were blind to the collection.
  - `READ-ME.md` is the strict reading's rubric with Part 2 removed and a neutral first line.
  - `KEY.json` maps each id to its source.
- **Readers:** the strict reading's two analysts, working apart. The packet and key were sealed before
  reading (`SEAL-before-reading.json`). Their labels are `reader-A-statements.csv` and
  `reader-B-statements.csv`, as written.
- **Reproduce:** `python code/posthoc_runbook_reading.py` rebuilds the packet from the corpus and checks
  it against these files and the seal. It scores both readers and writes
  `reproduced/POSTHOC-runbook-reading.json`; `scores.json` here is the stored copy.

| Source | Statements | Both say it forbids something | Share (95% interval) | Agreement on *forbids* |
|---|---:|---:|---|---|
| Agent procedures | 35 | 22 | 63% (46-77) | 34/35 |
| GitLab runbooks | 35 | 7 | 20% (10-36) | 34/35 |
| OpenShift runbooks, without the repeated sentence | 35 | 1 | 3% (0.5-15) | 35/35 |

- Overall agreement is 103 of 105 (kappa 0.96).
- Counting only matches that forbid something, with none from the repeated sentence:
  - GitLab's runbooks carry 0.11 times the agent rate (0.35 as counted);
  - OpenShift's carry 0.02 (0.44 without the repeated sentence, 0.66 as counted).
