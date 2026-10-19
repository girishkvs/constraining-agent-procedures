# Why “Never” Is Not Enough: Where Agent Procedures Say No and What It Means for Evaluation

Data, code and results for the paper of the same name by Girish Konda (2026).

The paper counts explicit prohibitions and obligations in procedures written for agents
and asks where that constraint sits. This repository holds the public part of the study:
a pinned snapshot of every public document measured, the code that measured it, the
results behind each table, and the reading-check samples.

The original corpus, more than a hundred procedures written for agents that operate a
large cloud platform, is private and not included. Its figures in the paper cannot be
reproduced from here.

## What is here

| Folder | Contents |
|---|---|
| `corpus/` | The measured documents, unchanged except for one redacted key (see below). `MANIFEST.csv` has one row per document: source repository, commit, original path, hashes and license. `PINS.csv` lists the repository commits; `RIGHTS.csv` lists the license files kept for each. |
| `licenses/` | License and notice files of every source repository, by commit |
| `code/` | Parser, measurement, command classes, regression, length reference, sampling and scoring |
| `results/` | Results behind the paper's tables, per-document counts, and the checks made after the main measurement (folders marked `POSTHOC`) |
| `labels/` | Reading-check samples, the rubrics, both readings and the sample keys |
| `tests/` | Smoke test that re-checks the headline numbers from the snapshot |

`ARTIFACT-SHA256.json` lists the hash of every file.

## Corpora

| Corpus | Documents | Source |
|---|---:|---|
| Public agent procedures | 1,495 | 1,111 skill files, 150 agent definitions, 51 prompts and commands and 183 instruction files from 12 publishing repositories, collected on October 15, 2026 |
| Public agent context files | 1,540 | 893 `AGENTS.md`, 570 `CLAUDE.md` and 77 `copilot-instructions.md` files from 433 repositories in the dataset of [Galster et al. (2026)](https://arxiv.org/abs/2605.08435v1), limited to files whose source and license could be confirmed |
| GitLab on-call runbooks | 833 | `gitlab-com/runbooks` |
| OpenShift alert runbooks | 288 | `openshift/runbooks` |

Every document is pinned to a commit. The publishers and selection rules were fixed before
measurement; the selection is purposive, not a census. Only the entry file of each
procedure is counted. Scripts and other files bundled with a skill are not included.
Nothing in `corpus/` was installed or run for the counts. The agent runs in
`results/POSTHOC-agent-runs/` ran one procedure, `git-cleanup`, on sandbox repositories.

One GitLab filename contains a colon, which Windows cannot store. It is kept as
`component_saturation_slo_out_of_bounds%3Aredis_memory.md`, and `MANIFEST.csv` keeps the
original path.

One agent context file, `packages/maps/AGENTS.md` in `tobitsoftware/chayns-components`,
shows a Google API key in a code example. Here the key is replaced with `REDACTED_KEY`.
`corpus/REDACTIONS.csv` records the change, `MANIFEST.csv` keeps the hashes of the
original file at its pinned commit, and no count changes.

## From the paper to the files

| In the paper | File |
|---|---|
| Table 1, public corpora | `results/D1-cross-corpus.csv` |
| Table A2, all twelve configurations | `results/E1-SC-style-six-rows.csv`; all groups in `results/direct-grid-and-publisher-results.json` |
| Five large publishers | `results/E3-within-publisher-concentration.csv` |
| Table A1 | `results/document-primary-counts-tiers-covariates.csv` (one row per procedure), `corpus/PINS.csv` |
| Length-only reference (499 draws) | `results/direct-length-reference.json` |
| Reading of matched statements, read strictly | `labels/strict-reading/scores.json` |
| Intervals for the corrected top-tenth share (48 percent) and the share that forbids something | `results/POSTHOC-reading-intervals/` |
| Limits in 30 procedures with no prohibition match | `labels/strict-reading/scores.json` |
| Reading of the command classes (16 of 30 agree) | `labels/scored-summary.json` |
| Prohibition matches per document, by bin | `results/D3-SC-P-bins.csv` |
| Runbooks and procedures by length band | `results/D2-fixed-length-bands.csv` |
| Table A3, command classes | `results/B1-primary-tiers.csv`, `results/B3-primary-tier-IRR-bootstrap.csv` |
| Length, file type, publisher, steps and headings | `results/B3-model-results.json`, `results/B3-all-model-coefficients.csv` |
| Other ways of coding command classes, including inline code | `results/B5-sensitivity-tier-tables.csv`, `results/B3-model-results.json` (model `V-inline`) |
| Inline code with commands inside matching statements dropped | `results/POSTHOC-guarded-inline/` |
| Topic words against the length-only reference | `results/POSTHOC-topic-words/` |
| Resampling whole publishers (39 to 50 percent) | `results/direct-length-reference.json` |
| 48 of 162 procedures with commands and no prohibition match | `results/document-primary-counts-tiers-covariates.csv` |
| Contractions such as *don't* | `results/POSTHOC-contractions/` |
| 32 files missed by the origin screen | `results/POSTHOC-origin/` |
| Runbooks against their own length-only reference | `results/gitlab-configuration-results.csv`, `results/openshift-configuration-results.csv` |
| OpenShift's repeated support-case sentence (80 of 229 matches) | `results/POSTHOC-openshift-sentence/` |
| Sampling by explicit constraint against a uniform draw | `results/POSTHOC-sampling-test/` |
| 24 agent runs of `git-cleanup` | `results/POSTHOC-agent-runs/` |

Per-document counts for every corpus are in `results/*-document-results.csv.gz`.

## Reproduce

Use Python 3.13.7 and the versions in `requirements.txt`:

```text
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Linux or macOS, activate with `. .venv/bin/activate`. Outputs go to `reproduced/`, except
the first two checks, which rewrite their reports in `results/`.

| What it does | Command | Output |
|---|---|---|
| Checks every file against its recorded hash and license | `python code/verify_snapshot.py` | `results/snapshot-verification.json` |
| Checks the headline numbers | `python tests/smoke_test.py` | `results/smoke-test.json` |
| Measures all four corpora under all twelve configurations, with command classes and publisher summaries | `python code/measure.py --grid` | `reproduced/document-counts.csv.gz`, `reproduced/configuration-grid.json`, `reproduced/tiers.json`, `reproduced/publishers.json` |
| Builds the cross-corpus, length-band, bin, publisher and grid tables and the origin check | `python code/tables.py` | `reproduced/cross-corpus.csv`, `reproduced/length-bands.csv`, `reproduced/binned-distributions.csv`, `reproduced/publisher-results.csv`, `reproduced/twelve-configuration-grids.csv`, `reproduced/POSTHOC-origin.json` |
| Fits the regression, its variants and the bootstrap | `python code/regression.py` | `reproduced/B3-model-results.json`, `reproduced/B3-bootstrap-status.json`, `reproduced/B3-bootstrap-draws.jsonl`, `reproduced/tables/` |
| Runs the length-only reference | `python code/reference.py --corpus direct` (and `agent_context`, `gitlab`, `openshift`) | `reproduced/<corpus>-length-reference.json` |
| Draws the reading-check samples again from the seed | `python code/sample.py` | `reproduced/sampling-replay.json` |
| Scores the reading checks | `python code/score_labels.py --statements-csv labels/statements.csv --procedures-csv labels/procedures.csv --output reproduced/reading-scores.json` | `reproduced/reading-scores.json` |
| Adds contractions as triggers | `python code/posthoc_contractions.py` | `reproduced/POSTHOC-contractions.json` |
| Scores the strict reading and the read of 30 procedures | `python code/score_strict_reading.py` | `reproduced/strict-reading-scores.json` |
| Codes inline commands, dropping those inside matching statements | `python code/posthoc_guarded_inline.py` | `reproduced/POSTHOC-guarded-inline/` |
| Runs the length-only reference for topic words | `python code/posthoc_topic_words.py` | `reproduced/POSTHOC-topic-words/` |
| Compares stratified and uniform draws of 100 procedures | `python code/posthoc_sampling_test.py` | `reproduced/POSTHOC-sampling-test.json` |
| Gives intervals for the corrected top-tenth share and the share that forbids something | `python code/posthoc_reading_intervals.py` | `reproduced/POSTHOC-reading-intervals.json` |
| Counts OpenShift's repeated sentence and compares rates without it | `python code/posthoc_openshift_sentence.py` | `reproduced/POSTHOC-openshift-sentence.json` |
| Builds the sandbox repositories for the agent runs | `python code/posthoc_agent_runs_setup.py '<runs json>' <folder>` | the repositories; the runs themselves need an agent harness (`results/POSTHOC-agent-runs/README.md`) |

Run the measurement before the regression. The regression leaves out the four procedures
with no prose, since length enters as log words. It made 999 bootstrap draws within
publisher; one could not be fitted, so the intervals use 998.

## How it was measured

- A statement is a sentence or a single list item. Front matter, code, quotations and
  marked examples are removed first, so a trigger inside a command or a sample output does
  not count. GitHub-style warning callouts are kept; other quoted warnings are not counted.
- A statement matches a prohibition trigger (*never*, *do not*, *must not* and others) or
  an obligation trigger (*always*, *you must*, *make sure* and others). Both lists are in
  `code/legacy/protocol.json`.
- The main configuration is sentence segmentation, the broad trigger set, and a statement
  that matches both classes counted in both. The twelve configurations vary segmentation
  (sentence, line, paragraph), trigger set (broad, narrow) and that rule.
- Command classes come from shell and SQL code blocks only. In the data files, `D` is
  destructive, `W` is state-changing and `R` is neither. `R` means no such command was
  found, not that the procedure only reads. The command lists are in
  `code/risk-lexicon-frozen.json` and were fixed before any class was joined to a count.
- The length reference spreads the same matches at random over the same statements, over
  the whole corpus or with each publisher's total held fixed.
- Contractions were not triggers. Adding them is a separate check, made after the main
  measurement.

These are counts of wording. They do not show whether any agent followed a rule; the agent
runs in `results/POSTHOC-agent-runs/` show how such a check can be recorded.

## Reading checks

`labels/statements.csv` holds 100 matched statements: 35 prohibition matches from the most
constrained tenth of procedures, 35 from the rest, and 30 obligation matches, shuffled.
`labels/procedures.csv` holds 30 procedures, ten from each command class. Each was read
blind to its group under `labels/RUBRIC.md`. `labels/KEY.json` maps each item back to its
group; `labels/sampling-design.json` gives the pool sizes, sample sizes and seed.

That first reading asked whether a statement is an operative instruction, and some of its
answers judged the whole source line. `labels/strict-reading/` holds a second, stricter
reading of the same 100 statements, made after the main measurement. Two analysts, working
apart and blind to each statement's group, judged each statement on its own: does it
instruct, forbid or require? The paper counts a statement only where both said yes. The
same analysts read 30 procedures, drawn at random from those with no prohibition match, for
limits written in other words. The rubric is `labels/strict-reading/READ-ME.md`; the hashes
of everything they were given, recorded before reading, are in `SEAL-before-reading.json`.
The paper uses the strict reading for statements and the first reading for command classes.
Coding was tool-assisted in both readings; the author reviewed the labels.

## Licenses

`LICENSE` (MIT) covers this repository's own code and documentation, including the four
index files in `corpus/` (`MANIFEST.csv`, `PINS.csv`, `RIGHTS.csv`, `REDACTIONS.csv`). Every
source document in `corpus/` keeps its original license, recorded per file in
`corpus/MANIFEST.csv`: MIT, Apache-2.0, CC-BY-SA-4.0 or MPL-2.0 for the agent procedures, MIT
or Apache-2.0 for the context files, MIT for the GitLab runbooks and Apache-2.0 for the
OpenShift runbooks. The context files were selected from a dataset published under CC BY 4.0.
Excerpts quoted in `labels/` keep the license of their source. See `THIRD-PARTY-NOTICES.md`,
`corpus/RIGHTS.csv` and `licenses/`.

## Citation

See `CITATION.cff`.
