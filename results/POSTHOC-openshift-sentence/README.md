# POSTHOC: one repeated sentence in OpenShift's runbooks

Made after the main measurement. 80 of OpenShift's 288 runbooks contain the same support-case
sentence, *If you cannot resolve the issue, log in to the customer portal ...*. It contains *cannot*,
so each copy is a prohibition match, but it forbids nothing. It supplies 80 of OpenShift's 229
prohibition matches in the primary configuration.

The table gives OpenShift's prohibition matches per thousand prose words as a multiple of the public
agent procedures' rate, as counted and with that sentence set aside (its matches and its words
removed). Each length band compares with the agent procedures of the same length.

| Runbooks | OpenShift documents | As counted | Sentence set aside |
|---|---:|---:|---:|
| All | 288 | 0.66 | 0.44 |
| 1–249 prose words | 200 | 1.09 | 0.64 |
| 250–499 prose words | 60 | 0.43 | 0.31 |
| 500–999 prose words | 27 | 0.52 | 0.46 |
| 1,000–1,999 prose words | 1 | 0.15 | 0.15 |

Rerun with `python code/posthoc_openshift_sentence.py`, which re-measures both corpora and writes
`reproduced/POSTHOC-openshift-sentence.json`.
