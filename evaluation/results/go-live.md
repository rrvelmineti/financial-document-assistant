# Go-live readiness

**Decision: NO-GO**

Evaluation run: `evaluation/results/answers-hashing.json`, run on 2026-11-07, answer model `gemini-3.5-flash-lite`, retrieval `hashing-v1`.

| Check | Result | Target | Blocking | Status |
| --- | --- | --- | --- | --- |
| No invented answers to questions the documents cannot answer | 0 | at most 0 | yes | Pass |
| Answer accuracy (verified and contains the expected figure) | 14 of 20 (70%) | at least 80% | yes | **Fail** |
| Citation accuracy (cites a page with the evidence) | 15 of 20 (75%) | at least 85% | yes | **Fail** |
| Unanswerable questions correctly said not found | 4 of 5 (80%) | at least 80% | no | Pass |
| Retrieval: evidence page among retrieved passages | 17 of 20 (85%) | at least 80% | no | Pass |

At least one blocking check fails. Do not go live. Review the failing questions in the per-question table of the evaluation report, fix, and run the evaluation again.

Sign-off: ______________________  (client owner)   Date: __________
