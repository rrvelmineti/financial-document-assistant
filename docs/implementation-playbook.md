# Implementation playbook: rolling the assistant out to a finance team

How I would take this assistant from a working build to a team that relies on it. The client below
is a **hypothetical** example used to plan the rollout; the documents, evaluation and safeguards are
the real ones in this repository.

## The engagement in one paragraph

A regional bank's financial reporting team (8 analysts) spends hours each quarter searching annual
reports, regulator filings and peer reports for specific figures. They want answers in seconds, but
a wrong figure in a board pack is worse than a slow one. The goal is to cut lookup time while making
every answer traceable to a page, and to never show an invented figure.

## Stakeholders

| Who | Role in the rollout | Responsible for |
| --- | --- | --- |
| Head of Financial Reporting | Sponsor | Agrees the go-live criteria, signs off go-live |
| 2 senior analysts | Pilot users and reviewers | Write test questions, review withheld answers |
| IT / data platform | Hosting | PostgreSQL, deployment, access control |
| Risk and compliance | Approver | Data-handling review, sign-off on the risk note |
| Implementation consultant (me) | Delivery lead | Discovery, configuration, evaluation, training, hypercare |

## 1. Discovery (week 1)

Questions I ask before configuring anything:

1. Which documents do analysts search most, and how many pages per quarter?
2. Which questions come up every quarter? (These become the evaluation set.)
3. What does "correct" mean: the exact figure, the year column, the units?
4. Can document passages be sent to an external AI API, or must everything stay in-house?
5. Who checks a figure today before it goes into a board pack, and how?
6. How long does a typical lookup take now? (Baseline for measuring value.)

**Today's process:** analyst opens the PDF, searches by keyword, reads around the hit, copies the
figure and page into a spreadsheet, and a second analyst spot-checks it.

**Future process:** analyst asks the question, sees the answer with the quoted line highlighted on its
page, and confirms the year column and units. Withheld or "not found" answers go to a review queue
instead of being silently dropped.

## 2. Configuration and evaluation (weeks 2–3)

- Load the client's documents and confirm text extraction on each one. Scanned PDFs need OCR first
  ([risk note §7](risk-note.md)).
- Build the evaluation set with the pilot analysts: real recurring questions, the expected figure and
  the pages that hold the evidence, plus questions the documents **cannot** answer. This repository's
  set is the template: [evaluation/questions.json](../evaluation/questions.json), 20 answerable and 5
  unanswerable.
- Run `python evaluation/run_eval.py --answers` and review every miss with the analysts.

## 3. Go-live gate (end of week 3)

The criteria are agreed with the sponsor **before** the pilot, so the decision is not argued after
the numbers are in. They live in [evaluation/go_live_criteria.json](../evaluation/go_live_criteria.json):

| Check | Target | Blocks go-live |
| --- | --- | --- |
| Invented answers to unanswerable questions | 0 | Yes |
| Answer accuracy | at least 80% | Yes |
| Citation accuracy | at least 85% | Yes |
| Unanswerable questions said not found | at least 80% | No |
| Retrieval of the evidence page | at least 80% | No |

`python evaluation/go_live.py` turns the latest evaluation into a GO, NO-GO or NOT READY decision
with a sign-off line, written to `evaluation/results/go-live.md`.

## 4. Pilot (weeks 4–5)

- Two senior analysts use the assistant for real quarter-end lookups, alongside the old process.
- Every withheld or not-found answer appears in the review queue (`GET /api/review-queue`). A reviewer
  records what happened (`POST /api/reviews/{id}`) with one of:
  `confirmed_gap` (the documents really don't say), `answer_found` (it was there; a miss),
  `retrieval_miss`, `document_missing` (we need to load another file), `other`.
- These decisions show where to improve: many `retrieval_miss` results mean retrieval needs tuning;
  many `document_missing` results mean the document set is incomplete.

## 5. Training and change management

- A 30-minute session built on the risk note's "what a person should always check" list: year
  column, units, withheld answers, important "not found" results.
- One rule for the team: **the highlighted line is the source, not the answer text.**
- A one-page guide to the three outcomes (checked, withheld, not found) and what to do with each.

## 6. Hypercare (first 4 weeks after go-live)

Daily check of `GET /api/usage`:

| Signal | Healthy | Action if not |
| --- | --- | --- |
| Questions per day | Rising after week 1 | Ask the team what's stopping them; more training |
| Answered share | Stable or rising | Look at review decisions for the cause |
| Withheld share | Low and falling | Check whether a document's tables extract badly |
| Awaiting review | Close to 0 | Agree a reviewer rota |
| Median latency | A few seconds | Check the AI API and database |

## 7. Handover

The client's IT team receives: deployment notes (README "Run it"), the evaluation set and how to
extend it, the go-live criteria, this playbook, and the [risk note](risk-note.md). Rerun the
evaluation and the go-live gate whenever documents, the model or the prompt change.
