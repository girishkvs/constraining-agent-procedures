# POSTHOC: prohibition matches by trigger word, and procedures with steps

Made after the main measurement. `code/posthoc_triggers.py` re-measures the public agent procedures, the
agent context files and both runbook collections in the primary configuration (ordinary prose, sentence
segmentation, broad triggers), and writes `reproduced/POSTHOC-triggers.json`. This folder keeps a copy.

| | Agent procedures | Context files | GitLab runbooks | OpenShift runbooks |
|---|---:|---:|---:|---:|
| Prohibition matches per 1,000 prose words | 4.99 | 4.62 | 1.73 | 3.30 |
| Without statements whose only triggers are *cannot* or *avoid* | 3.69 | 3.20 | 1.04 | 0.63 |
| With *never*, *do not* and *must not* only | 3.61 | 3.05 | 0.94 | 0.45 |
| Share of matches containing *cannot* | 10% | 3% | 30% | 79% |
| Runbook or context-file rate over the agent rate, as counted | | 0.93 | 0.35 | 0.66 |
| The same without *cannot*-or-*avoid*-only statements | | 0.87 | 0.28 | 0.17 |

**Strict reading by trigger.** Of the 70 sampled prohibition matches, the share both analysts judged to
forbid something, by the triggers each statement contains: *never* 24 of 31, *do not* 16 of 18, *avoid*
11 of 14, *must not* 3 of 3, *cannot* 2 of 7.

**Procedures with steps.** 641 of the 1,495 procedures have no numbered steps, among them 334 of the 521
TerminalSkills files. Among the 833 procedures with three or more steps, 28 percent carry no prohibition
match and the most constrained tenth carry 45 percent of the matches, as in the whole corpus.
