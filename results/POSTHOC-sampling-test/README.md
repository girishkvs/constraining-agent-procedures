# POSTHOC: sampling by explicit constraint (practice 1)

Made after the main measurement. Draws 100 of the 1,495 public procedures, 10,000 times, in two
ways:

- **Uniform:** 100 procedures at random.
- **Stratified:** a third from each stratum of the primary configuration's prohibition count: none
  (462 procedures, 33 drawn), one to four (771, 33 drawn), and five or more (262, 34 drawn).

For each draw it records the prohibition matches covered, the procedures drawn from the most
constrained tenth, the prose words to read, and the corpus mean, estimated with stratum-size weights
in the stratified case.
Seed `20261018`. Rerun with `python code/posthoc_sampling_test.py`, which writes
`reproduced/POSTHOC-sampling-test.json`.

| | Uniform | Stratified |
|---|---:|---:|
| Prohibition matches covered (mean) | 272.7 | 388.0 |
| Procedures from the most constrained tenth | 10.0 | 19.5 |
| Procedures with no match | 31.0 | 33 |
| Corpus mean estimate (standard deviation) | 2.73 (0.425) | 2.73 (0.214) |
| Prose words to read (mean) | 54,616 | 65,739 |

Both gains follow from stratifying on the count itself. Per procedure the stratified draw covers 1.42
times as many matches; per word read, 1.18 times, because it reads 1.20 times as many words.
