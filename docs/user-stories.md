# User stories

First drafted with an AI assistant from a short brief, then reviewed. Record your changes in the
review log at the end, so the gap between the AI draft and the final version stays visible.

**Brief given to the AI:** "An analyst uploads financial reports and asks questions. Every answer must
show the exact passage and page it came from, be checked before it is shown, and say not found when
the documents don't contain the answer. Write user stories with acceptance criteria, including how
we measure accuracy."

---

### US-1 Upload documents

As an analyst, I want to upload financial reports so that I can ask questions about them.

Acceptance criteria:
- PDF, TXT and MD files up to 25 MB and 600 pages are accepted.
- Non-PDF files named .pdf, password-protected PDFs and scanned PDFs without text are rejected
  with a clear message.
- The same file uploaded twice is stored once.
- Each document shows its page and passage counts.

### US-2 Search by meaning

As an analyst, I want the assistant to find relevant passages even when my wording differs from the
document so that I don't need the exact phrase.

Acceptance criteria:
- With a Gemini key, passages are embedded with Gemini and searched with FAISS.
- Without a key, an offline keyword-hashing search still works, and the interface says so.
- Passages never cross a page, so every result has one page number.
- I can leave documents out of the search.

### US-3 Answers with their source line

As an analyst, I want each answer to show the document, page and exact quoted line so that I can
verify it in seconds.

Acceptance criteria:
- The quoted line is highlighted inside the passage it came from.
- Units and year columns stated elsewhere on the page are shown with the passage.

### US-4 Answers are checked before I see them

As a reviewer, I want the tool to check its own evidence so that a fabricated quote or figure never
reaches me as an answer.

Acceptance criteria:
- A quote that does not appear in the cited passage is rejected.
- A figure in the answer that is not in a cited passage (or in my question) gets the answer withheld,
  with the reason shown.
- A citation to a passage that was not retrieved is rejected.
- Withheld answers still show the passages, so I can read them myself.

### US-5 Honest "not found"

As an analyst, I want the tool to say when the documents don't contain the answer so that I don't
act on a guess.

Acceptance criteria:
- When the model reports the answer is not in the passages, the tool shows "Not in these documents".

### US-6 Records of documents and questions

As a team lead, I want documents and questions recorded in a database so that usage and outcomes
can be reviewed.

Acceptance criteria:
- Document metadata, passages and their vectors are stored in PostgreSQL (SQLite for local use).
- Each question is logged with its outcome (answered, not found, withheld), model and response time.
- Restarting the app rebuilds the search index from the database without re-embedding.

### US-7 Measured accuracy

As a team lead, I want accuracy measured on real documents so that I know how far to trust the tool.

Acceptance criteria:
- 25 questions on three public financial reports: 20 with known answers and pages, 5 that the
  documents cannot answer.
- Reported: retrieval recall, answer accuracy, citation accuracy, unanswerable questions declined,
  and false answers shown.

---

## Review log

| Story | What changed after review | Why |
| --- | --- | --- |
| | | |
