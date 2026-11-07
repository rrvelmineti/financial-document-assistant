# Evaluation results

Run on 2026-11-07. Retrieval: `hashing-v1`, top 10 passages. Answer model: `gemini-3.5-flash-lite`.

| Measure | Result |
| --- | --- |
| Retrieval: evidence page among retrieved passages | 17 of 20 |
| Answer accuracy (verified and contains the expected figure) | 14 of 20 |
| Citation accuracy (cites a page with the evidence) | 15 of 20 |
| Answerable questions withheld by verification | 1 |
| Answerable questions wrongly said not found | 2 |
| Unanswerable questions correctly said not found | 4 of 5 |
| False answers shown on unanswerable questions | 0 |

## Per question

| ID | Status | Correct | Cited pages | Notes |
| --- | --- | --- | --- | --- |
| A01 | answered | yes | p2, p2 |  |
| A02 | answered | yes | p3, p3 |  |
| A03 | answered | no | p14 |  |
| A04 | not_found | no | - |  |
| A05 | answered | yes | p31 |  |
| A06 | answered | yes | p22 |  |
| A07 | answered | yes | p19 |  |
| A08 | answered | yes | p21 |  |
| A09 | error | no | - | Gemini returned HTTP 503. Check the model ID, API key and quota. |
| A10 | answered | yes | p22 |  |
| A11 | not_found | no | - |  |
| A12 | error | no | - | Gemini returned HTTP 503. Check the model ID, API key and quota. |
| A13 | answered | yes | p9 |  |
| A14 | answered | yes | p22 |  |
| A15 | answered | yes | p35 |  |
| A16 | unverified | no | p168 | The answer contains figures not in the cited passages: 576. |
| A17 | answered | yes | p22 |  |
| A18 | answered | yes | p28 |  |
| A19 | answered | yes | p19 |  |
| A20 | answered | yes | p19 |  |
| U01 | not_found | yes | - |  |
| U02 | not_found | yes | - |  |
| U03 | not_found | yes | - |  |
| U04 | error | no | - | Gemini returned HTTP 503. Check the model ID, API key and quota. |
| U05 | not_found | yes | - |  |
