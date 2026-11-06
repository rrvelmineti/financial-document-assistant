# Problem statement

## Context

Analysts, auditors and finance teams spend hours searching long financial reports for one figure:
a fund balance, an audit opinion, a ratio at a given date. Agency and annual reports run to
hundreds of pages, mix narrative with dense statement tables, and repeat similar numbers in many
places.

General-purpose AI chat tools can answer quickly, but they can also state a confident figure that
appears nowhere in the document. In finance, an answer without its source is not usable.

## Problem

People need fast answers from their own documents that they can **verify in seconds**: which
document, which page, which exact line. When the documents do not contain the answer, the tool must
say so instead of guessing.

## Users

| User | Need |
| --- | --- |
| Financial analyst | Find a figure or statement quickly and cite it in their own work |
| Reviewer or auditor | See exactly which line supports an answer before relying on it |
| Team lead | Know how accurate the tool is before the team uses it |

## Goal

1. Upload PDFs (or text) and search them by meaning, not only keywords.
2. Answer only from retrieved passages, with an exact quote and page for every answer.
3. Check every quote and every figure against the source before showing the answer.
4. Say "Not found in these documents" when the answer is not there.
5. Measure accuracy on real financial documents with a fixed question set.

## Success measures

Measured by `evaluation/run_eval.py` on three public U.S. government financial reports (410 pages):

- Answer accuracy on 20 answerable questions
- Citation accuracy: the cited page actually contains the evidence
- Unanswerable questions correctly declined (5 questions)
- No false answers shown on unanswerable questions

## Out of scope

- OCR for scanned PDFs
- Calculated answers (totals, differences, growth rates). Figures must appear in the source, so
  calculated numbers are withheld by design.
- User accounts and access control. The app is a single-user analyst tool.
