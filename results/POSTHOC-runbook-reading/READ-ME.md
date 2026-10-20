# Reading task

You are reading short statements from public operational documents. Judge them from this packet alone;
do not look up their sources or other copies of these texts.

There is no expected answer and no target rate. Read each item on its own and answer what it says.

## `statements-to-read.csv` (105 rows)

Each row has:

- `statement`: **the text you judge**;
- `line`: the source line or list item it came from (it can hold more than one sentence);
- `before`, `after`: the neighbouring statements.

The `line`, `before` and `after` columns are there only to help you understand the statement. **Never
answer from them.** If the statement itself is a description and the next sentence is an instruction,
the statement is still a description.

Answer three questions for every row, each `Y`, `N` or `U` (unclear):

1. **instructs** — Does the statement itself tell someone (the agent or the user) to do something or
   not to do something? Conditional instructions count. Descriptions, explanations, examples, names,
   headings, titles and table labels are `N`, even when they contain words like *never*, *always* or
   *do not*.
2. **forbids** — Does the statement itself tell someone not to do something, or limit when or how
   something may be done (for example "never X", "do not X unless Y", "X only after Y")? `N` when
   *never* or *do not* only describes behaviour ("the helper never changes the branch"), or is part
   of a name, heading or table category ("Do not report", "Never reviewed").
3. **requires** — Does the statement itself tell someone to do something?

A statement can be `Y` for both 2 and 3. If 2 or 3 is `Y`, then 1 is `Y`.

Write `labels-statements.csv` in this folder with the columns
`id,instructs,forbids,requires,reason` — one row per statement, in any order, and a one-line `reason`
that refers only to the statement itself.

## When you are done

Check that the file has every id exactly once and only `Y`, `N` or `U` in the answer columns.
