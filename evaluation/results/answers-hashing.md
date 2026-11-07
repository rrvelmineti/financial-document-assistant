# Evaluation results

Run on 2026-11-06. Retrieval: `hashing-v1`, top 6 passages. Answer model: `gemini-3.5-flash-lite`.

| Measure | Result |
| --- | --- |
| Retrieval: evidence page among retrieved passages | 16 of 20 |
| Answer accuracy (verified and contains the expected figure) | 13 of 20 |
| Citation accuracy (cites a page with the evidence) | 13 of 20 |
| Answerable questions withheld by verification | 0 |
| Answerable questions wrongly said not found | 5 |
| Unanswerable questions correctly said not found | 5 of 5 |
| False answers shown on unanswerable questions | 0 |

## Per question

| ID | Status | Correct | Cited pages | Notes |
| --- | --- | --- | --- | --- |
| A01 | error | no | - | Gemini returned HTTP 503. Check the model ID, API key and quota. |
| A02 | answered | yes | p3 |  |
| A03 | not_found | no | - |  |
| A04 | not_found | no | - |  |
| A05 | answered | yes | p31 |  |
| A06 | answered | yes | p22 |  |
| A07 | not_found | no | - |  |
| A08 | answered | yes | p21 |  |
| A09 | answered | yes | p21 |  |
| A10 | answered | yes | p22 |  |
| A11 | not_found | no | - |  |
| A12 | answered | yes | p9 |  |
| A13 | answered | yes | p11 |  |
| A14 | not_found | no | - |  |
| A15 | answered | yes | p33 |  |
| A16 | answered | yes | p23 |  |
| A17 | error | no | - | Gemini returned HTTP 503. Check the model ID, API key and quota. |
| A18 | answered | yes | p28 |  |
| A19 | answered | yes | p19 |  |
| A20 | answered | yes | p19 |  |
| U01 | not_found | yes | - |  |
| U02 | not_found | yes | - |  |
| U03 | not_found | yes | - |  |
| U04 | not_found | yes | - |  |
| U05 | not_found | yes | - |  |
