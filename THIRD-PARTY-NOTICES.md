# Third-party notices

The root MIT license covers only this artifact's own code and documentation.
It does not change the terms of any third-party source document, quoted passage,
copyright notice, or license text.

1. `corpus/MANIFEST.csv` identifies each selected document, its original repository
   and path, immutable commit, Git blob identity, SHA-256, byte length, and recorded
   license. The files are inert source text; do not run commands found in them.
2. `corpus/RIGHTS.csv` identifies retained license and notice files. Their original
   bytes are under `licenses/<source repo>/<commit>/<original path>`. Commit folders
   keep distinct license versions separate when a repository appears at more than
   one pin. This prevents a newer license from being presented as an older pin's terms.
3. Read the applicable root, ancestor, and file-level terms together. A root license
   is not a blanket grant for every subtree. Existing in-file attributions remain
   intact. Public access alone is not a license grant.
4. GitLab runbooks retain their MIT license. OpenShift runbooks retain their
   Apache-2.0 license. The context-file comparison is the previously qualified
   license-confirmed subset, not the entire discovery collection.
5. Short provenance quotes in `results/POSTHOC-origin/` document identified copied
   or derived scopes. They are not extra corpus documents. The full 1,495-entry
   population is retained in the stored results; the separate 1,463-entry row is
   explicitly post hoc. Neither row certifies independent authorship.
6. Public account names, product names, and upstream example paths are kept where
   they occur in source text and required notices. The only change to source bytes is
   the redacted key listed in `corpus/REDACTIONS.csv`.
7. `labels/` quotes short excerpts of corpus documents: the sampled statements, their
   neighbouring lines, and the procedures' descriptions and commands. Each excerpt
   links to its source file at the pinned commit and keeps that file's license,
   including CC-BY-SA-4.0 and MPL-2.0 where they apply; `corpus/MANIFEST.csv` gives
   each source's license.

No private corpus or private work documents are included. License evidence is a
record of the retained grants and notices, not legal advice.

## Context-comparison collection credit

The comparison collection is credited to **Matthias Galster, Seyedmoein
Mohsenimofidi, Levi Böhme, Jai Lal Lulla, Muhammad Auwal Abubakar, Christoph Treude,
and Sebastian Baltes (2026)**. See [arXiv:2605.08435v1](https://arxiv.org/abs/2605.08435v1)
and collection concept [10.5281/zenodo.19375880](https://doi.org/10.5281/zenodo.19375880).
The collection is licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/legalcode).
Copyright remains with its owners/authors. That compilation license does not
replace the source-file licenses listed in the manifest.

The actual previously acquired mirror was
`https://assets.empirical-software.engineering/data/ai-config-dataset/repos_data.7z`,
24,041,664 bytes, SHA-256
`2f96217a2dd7910fb93b421612c46872c82705dd6ef06d6b45ea92d9574ef90e`.
Its equivalence to the separately recorded version DOI
`10.5281/zenodo.20090356` is not established. The archive itself is not distributed.
Changes here are subset selection, origin/license qualification, identity indexing,
measurement, and reading-check annotations; the selected raw files are unmodified except
the one redacted key listed in `corpus/REDACTIONS.csv`.
