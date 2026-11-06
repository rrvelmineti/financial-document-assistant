# UAT test cases

Run on 5 November 2026. Cases 1 to 16 have automated equivalents in `backend/tests/`,
`frontend/src/highlight.test.ts` and `evaluation/run_eval.py`, and run on every push (backend on
PostgreSQL 17 and on Windows with SQLite). Cases 17 and 18 need a Gemini key and are run by hand.

| # | Story | Steps | Expected | Actual | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | US-1 | Upload a 3-page PDF | 201; pages and passages shown; file hash not exposed | As expected | Pass |
| 2 | US-1 | Upload the same file again under another name | Stored once, "already here" | Stored once | Pass |
| 3 | US-1 | Upload a fake PDF, a .docx, a non-UTF-8 .txt | Each rejected with a clear message | As expected | Pass |
| 4 | US-1 | Upload a PDF above the page limit | Rejected | Rejected | Pass |
| 5 | US-2 | Offline search for three facts in the sample report | Right page ranked first for each | 3 of 3 | Pass |
| 6 | US-2 | Long page split into passages | Passages never cross pages and overlap | As expected | Pass |
| 7 | US-3 | Units and year columns stated elsewhere on a statement page | Attached to every passage, shown to the model, kept out of search | As expected | Pass |
| 8 | US-3 | Two quotes from the same passage | One evidence slip, both lines highlighted | As expected | Pass |
| 9 | US-4 | Model quotes text that is not in the passage | Answer withheld, reason shown | Withheld | Pass |
| 10 | US-4 | Model states 9,999 when the passage says 3,260 | Answer withheld, figure named | Withheld: "9999" | Pass |
| 11 | US-4 | Model cites passage P9 when 3 were retrieved | Answer withheld | Withheld | Pass |
| 12 | US-4 | Quote matches text where the PDF split words ("de creased") | Accepted | Accepted | Pass |
| 13 | US-5 | Model reports the answer is not in the passages | "Not in these documents" | As expected | Pass |
| 14 | US-6 | Delete a document; restart the app | Passages leave the index; index rebuilt from the database on restart | As expected | Pass |
| 15 | US-6 | Ask a question | Logged with outcome, model and time | Logged | Pass |
| 16 | US-7 | `python evaluation/run_eval.py` (offline) | Retrieval recall reported for 20 questions | 16 of 20 | Pass |
| 17 | US-7 | `python evaluation/run_eval.py --answers` with a Gemini key | Answer, citation and not-found accuracy reported | | Not yet run |
| 18 | US-2, US-3 | Upload the three reports in the browser with a Gemini key and ask 3 of the evaluation questions | Verified answers with highlighted source lines | | Not yet run |
