# Risk note: where the assistant struggles

Every item below was found by testing on the three reports in `documents/`, with the page where it
was seen. The safeguards described are in the code and covered by tests.

## 1. PDF text extraction is imperfect

- **Words split by stray spaces.** The Treasury report (PDF page 9) extracts as "de creased",
  "b illion" and "c ontributor". A model quoting the sentence correctly writes "decreased".
- **Letters spaced out.** Parts of the FDIC report (pages 13 and 14) extract as
  "w h i c h i s t h e r a t i o".

*Safeguard:* quotes are compared with all whitespace removed, so a faithful quote still matches.
*Remaining risk:* keyword-based search finds these passages less reliably. One of the four
offline retrieval misses (the FDIC reserve ratio) is on a page with spaced-out text.

## 2. Tables lose their headers

On the FDIC income statement (PDF page 3), the column headers "2024 2023" are extracted at the
**bottom** of the page, and "(Dollars in Thousands)" at the top. A passage holding "Net Income (Loss)
15,259,556 (9,378,885)" can therefore lack both the years and the units.

*Safeguard:* units and year columns found anywhere on a page are attached to every passage from
that page, shown to the model, and shown in the evidence slip.
*Remaining risk:* **the model can still pick the wrong column.** Both figures are genuinely in the
passage, so quote and number checks pass either way. Always confirm which year column a figure
comes from.

## 3. Calculated figures are withheld

The number check requires every figure in an answer to appear in a cited passage (or in the
question). A correct calculation, such as growth between two years, is therefore withheld. This is
deliberate: a wrong calculation is worse than none.

## 4. Non-numeric claims are checked less strictly

For answers like "the audit opinion was unmodified", the check confirms the quote exists in the
passage, but cannot confirm that the answer's wording follows from it. Read the highlighted line.

## 5. Page numbers are PDF positions

Pages are counted from the first page of the file. Printed page numbers differ: the FDIC balance
sheet is PDF page 2 but printed page 72.

## 6. Retrieval can miss the right page

The offline keyword search found the evidence page for 16 of 20 questions. The misses were
assessment revenue and the reserve ratio (FDIC), total assets and the audit opinion (SEC): mostly
table-heavy pages, where many passages look alike. Gemini embeddings are expected to do better;
`evaluation/run_eval.py --answers` measures it.

If the right passage is not retrieved, the assistant should say "not found". **"Not found" means
not found in the passages retrieved, not proof that the document lacks the answer.**

## 7. Scanned documents

Scanned PDFs without a text layer are rejected. They need OCR first.

## 8. Data sent to Google

With a Gemini key, the question and the retrieved passages (not whole files) are sent to Google's
API, and document passages are sent for embedding. The evaluation documents are public. For
confidential documents, check your organisation's policy and the API's data terms, or use the
offline mode, which sends nothing.

## What a person should always check

1. The year column of any figure taken from a table.
2. The units: thousands, millions or billions.
3. Any answer marked **Answer withheld**: read the passages shown.
4. Any **Not in these documents** result on an important question: search the PDF directly.
