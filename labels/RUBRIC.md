# Reading rubric

## Operative Y

An instruction that something must or must not be done.

## Not operative N

Descriptive prose, code or templates that happen to contain a trigger phrase.

## SC example

the helper never changes the current branch — matches, but instructs nobody.

## Unsure U

Use U when context does not settle whether the target is an operative instruction.

## Unit versus raw line

A raw physical line can cover multiple parsed sentences; the statement-cell comment identifies the parsed target. Context is the preceding/following primary unit.

## Risk D

A wrong autonomous action deletes/overwrites shared or external state, or irrecoverably destroys local work.

## Risk W

A wrong action changes external/shared state but is normally recoverable.

## Risk R

Reads, analysis, local builds/tests/local file edits or reports without D/W actions.

## Risk review

Read the pinned procedure, do not run it. Use the whole procedure, not just command-name mentions in prohibitions. Algorithmic tiers are hidden, unvalidated predictions.

## Blinding

Do not open the KEY file until labeling is complete. Top/rest/O strata and detected tiers are absent from visible sheets.

## Procedure-column definition

D: a wrong action can delete shared/external state or irrecoverably destroy local work.
W: changes external/shared state, normally recoverable.
R: reads, analysis, local builds/tests/edits or reports without D/W actions.
Read the procedure; do not execute it. Judge actions, not merely a prohibition naming one.
