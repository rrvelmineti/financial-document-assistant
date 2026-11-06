# Financial Document Assistant

Ask questions about financial reports and see the exact line behind every answer. The assistant
answers only from passages it finds in your documents, must quote its evidence word for word, and
**every quote and every figure is checked against the page before you see it**. When the documents
don't contain the answer, it says so.

![An answer checked against the source, with the quoted lines highlighted](docs/screenshots/answer.png)

*The real FDIC 2024 financial section, with real retrieval and verification. The model's reply in this screenshot was simulated, because Gemini was not reachable from the build environment.*

- **Stack:** Python, FastAPI, FAISS, Gemini (embeddings and answers), PostgreSQL, React, TypeScript
- **Evaluated on** three public U.S. government financial reports (FDIC, SEC, Treasury; 410 pages)
  with 25 questions, 5 of which the documents cannot answer
- **Docs:** [problem statement](docs/problem-statement.md) · [user stories](docs/user-stories.md) ·
  [risk note](docs/risk-note.md) · [UAT](docs/uat.md) · [evaluation questions](evaluation/questions.json)

## How an answer is made

```
PDF ─> text by page ─> passages (never cross a page) ─> embeddings ─> FAISS
                                                                        │
question ─> embedding ─> top 6 passages ─> Gemini: answer + exact quotes (JSON)
                                                        │
                                       verify: quote is in its passage?
                                               every figure is in a cited passage?
                                                        │
                       answered with highlighted source  /  withheld with reason  /  not found
```

| Outcome | When | What you see |
| --- | --- | --- |
| Checked against the source | Every quote is found in its passage and every figure is in the cited text | The answer, and each source passage with the quoted line highlighted |
| Answer withheld | A quote isn't in the passage, a figure isn't in the source, or a citation points nowhere | The reason, and the passages so you can read them yourself |
| Not in these documents | The model reports the passages don't contain the answer | Exactly that |
| Relevant passages | No Gemini key is set | The most relevant passages, no generated answer |

## Evaluation

`evaluation/questions.json` has 25 questions written from the three reports in
[`documents/`](documents/README.md). Each of the 20 answerable questions has the figure the answer
must contain and the pages that hold the evidence; 5 questions are not answered anywhere in the
documents (checked by searching all 410 pages).

| Measure | Result |
| --- | --- |
| Retrieval, offline keyword search: evidence page in the top 6 passages | **16 of 20** ([results](evaluation/results/retrieval-hashing.md)) |
| Retrieval, Gemini embeddings | Run `python evaluation/run_eval.py --answers` |
| Answer accuracy, citation accuracy, unanswerable questions declined | Run `python evaluation/run_eval.py --answers` |

The full run needs a Gemini key and writes its results to `evaluation/results/`.

## Run it

Python 3.10+ and Node 20+.

```
python -m pip install -r backend/requirements-dev.txt
cd frontend && npm install && npm run build && cd ..

# PowerShell: $env:GEMINI_API_KEY="..."; $env:GEMINI_MODEL="..."
uvicorn app.main:create_app --factory --app-dir backend
```

Open http://localhost:8000 and upload the PDFs from `documents/`. Without a key the app still runs
and shows the most relevant passages.

**PostgreSQL:** `docker compose up -d`, then set
`DATABASE_URL=postgresql+psycopg://fda:fda@localhost:5432/fda`. Without it, records go to a local
SQLite file in `data/`.

**Development:** run `npm run dev` in `frontend/` (port 5173, proxying `/api` to port 8000).

**Tests:**

```
cd backend && python -m unittest discover -s tests -t . -v
cd frontend && npm test
python evaluation/run_eval.py              # offline retrieval evaluation
```

CI runs the backend tests on PostgreSQL 17 (Python 3.10 and 3.12) and on Windows, the offline
evaluation, and the frontend tests and build.

## Design decisions

- **Verify, don't trust.** The model must return exact quotes; code checks them. Quotes are compared
  without whitespace, because PDF extraction splits words ("de creased", "b illion").
- **Numbers must come from the source.** Any figure in an answer must appear in a cited passage or
  in the question. Calculated figures are withheld by design (see the [risk note](docs/risk-note.md)).
- **Passages never cross pages,** so every citation has one page.
- **Statement tables keep their units and years.** "(Dollars in Thousands)" and "2024 2023" are often
  extracted far from the figures; they are attached to each passage from that page and shown to the
  model, but kept out of the search vectors so they don't distort retrieval.
- **PostgreSQL holds the record:** documents, passages, vectors and a log of every question and
  outcome. FAISS is rebuilt from it on start-up, so there is one source of truth.
- **Offline mode.** Without a key, keyword-hashing search keeps the app, tests and CI working with no
  network.

## How I used AI to build this

- **Requirements.** An AI assistant drafted the problem statement and user stories from a short
  brief. My edits are recorded in the review log in [user-stories.md](docs/user-stories.md).
- **Build.** I set the finish line first, then built with an AI coding assistant in small steps,
  running each step before moving on.
- **Evaluation from the real documents.** Every expected answer was found in the extracted text, and
  the pages holding the evidence were computed by code rather than typed from memory. The 5
  unanswerable questions were confirmed absent by searching all 410 pages.
- **What testing on real documents caught:**
  - PDF extraction splits words and spaces out letters, so exact quote matching would have rejected
    correct answers. Matching now ignores whitespace on both server and interface.
  - Statement tables lose their year headers and units. A first fix put them into the passage text,
    which lowered retrieval from 16 to 15 of 20; they are now stored separately and shown to the
    model, restoring 16 of 20.
  - The verifier first rejected a correct answer because it repeated the year from the question.
    Numbers from the question are now allowed.
  - In the first interface, two quotes from one passage showed the passage twice; they now share one
    highlighted slip.

## Limits

See the [risk note](docs/risk-note.md). In short: confirm the year column and units of any figure
from a table, treat "not found" as "not found in the retrieved passages", and note that scanned PDFs
need OCR first.
