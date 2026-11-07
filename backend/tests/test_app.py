"""Offline tests: no test calls a live AI service. Set TEST_DATABASE_URL to run them on PostgreSQL."""
import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.answer import NOT_FOUND, verify
from app.config import load_settings
from app.answer import build_prompt
from app.documents import DocumentError, Page, chunk_pages, page_context, read_pages
from app.embeddings import HashingEmbedder
from app.main import create_app
from tests.fixtures import report_pdf, fake_gemini

NET_INCOME = {"found": True, "answer": "Net income was 3,260 thousand dollars.",
              "citations": [{"passage": "P1", "quote": "Net income: 3,260"}]}


class AppTestCase(unittest.TestCase):
    """Each test gets a fresh database and data folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {"DATA_DIR": self.tmp.name, "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model",
               "EMBEDDER": "hashing"}
        if os.environ.get("TEST_DATABASE_URL"):
            env["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
            engine = create_engine(env["DATABASE_URL"])
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS reviews, questions, chunks, documents CASCADE"))
            engine.dispose()
        self.settings = load_settings(env)

    def tearDown(self):
        if hasattr(self, "client"):
            self.client.app.state.store.engine.dispose()
        self.tmp.cleanup()

    def client_with(self, *answers):
        self.opener = fake_gemini(*answers)
        self.client = TestClient(create_app(self.settings, self.opener))
        return self.client

    def upload(self, data=None, name="harbor.pdf"):
        return self.client.post("/api/documents", files={"file": (name, data or report_pdf(), "application/pdf")})


class DocumentTests(AppTestCase):
    def test_upload_reads_pages_and_indexes_passages(self):
        self.client_with()
        r = self.upload()
        self.assertEqual(r.status_code, 201)
        doc = r.json()["document"]
        self.assertEqual((doc["pages"], doc["filename"], r.json()["created"]), (3, "harbor.pdf", True))
        self.assertNotIn("sha256", doc)
        health = self.client.get("/api/health").json()
        self.assertEqual(health["passages_indexed"], doc["chunks"])

    def test_same_file_twice_is_stored_once(self):
        self.client_with()
        self.upload()
        again = self.upload(name="copy.pdf")
        self.assertEqual((again.status_code, again.json()["created"]), (201, False))
        self.assertEqual(len(self.client.get("/api/documents").json()), 1)

    def test_bad_files_are_rejected_with_clear_messages(self):
        self.client_with()
        for name, data, message in [("x.pdf", b"not a pdf", "not a valid PDF"),
                                    ("x.docx", b"PK..", "Upload a PDF"),
                                    ("x.txt", b"\xff\xfe\x00", "UTF-8")]:
            r = self.upload(data, name)
            self.assertEqual(r.status_code, 400, name)
            self.assertIn(message, r.json()["detail"])

    def test_delete_removes_passages_from_search(self):
        self.client_with()
        doc_id = self.upload().json()["document"]["id"]
        self.assertEqual(self.client.delete(f"/api/documents/{doc_id}").status_code, 204)
        self.assertEqual(self.client.get("/api/health").json()["passages_indexed"], 0)
        self.assertEqual(self.client.delete(f"/api/documents/{doc_id}").status_code, 404)

    def test_index_is_rebuilt_from_the_database_on_restart(self):
        self.client_with()
        self.upload()
        restarted = TestClient(create_app(self.settings, fake_gemini()))
        self.assertEqual(restarted.get("/api/health").json()["passages_indexed"],
                         self.client.get("/api/health").json()["passages_indexed"])
        restarted.app.state.store.engine.dispose()

    def test_chunks_never_cross_pages_and_overlap(self):
        pages = [Page(1, "\n".join(f"Line {i} " + "x" * 90 for i in range(30))), Page(2, "Short page.")]
        chunks = chunk_pages(pages)
        self.assertEqual({c.page for c in chunks}, {1, 2})
        self.assertTrue(all(len(c.text) <= 1_100 for c in chunks))
        page1 = [c for c in chunks if c.page == 1]
        self.assertTrue(any(page1[i].text[-50:] in page1[i + 1].text for i in range(len(page1) - 1)))

    def test_units_and_year_columns_from_elsewhere_on_the_page_reach_every_passage(self):
        text = ("Statement of Income\n(Dollars in Thousands)\n"
                + "\n".join(f"Line item {i}: {i * 1000:,} {i * 900:,}" for i in range(80)) + "\n2024 2023")
        self.assertEqual(page_context(text), "(Dollars in Thousands); columns: 2024 2023")
        chunks = chunk_pages([Page(3, text)])
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.context for c in chunks))
        self.assertNotIn("Page context", chunks[1].text)           # kept out of the searchable text
        prompt = build_prompt("q", [{"filename": "f.pdf", "page": 3, "text": chunks[1].text, "context": chunks[1].context}])
        self.assertIn("[Stated elsewhere on this page: (Dollars in Thousands); columns: 2024 2023]", prompt)

    def test_pdf_page_limit(self):
        with self.assertRaises(DocumentError):
            read_pages("a.pdf", report_pdf(), max_pages=2)


class RetrievalTests(AppTestCase):
    def test_offline_embedder_finds_the_right_page(self):
        self.client_with()
        self.upload()
        store = self.client.app.state.store
        for question, page in [("What was net income?", 3), ("How many members and branches?", 1),
                               ("What is the net worth ratio?", 2)]:
            self.assertEqual(store.search(question, 1)[0]["page"], page, question)

    def test_hashing_vectors_are_normalised(self):
        e = HashingEmbedder()
        v = e.embed_documents(["Net income: 3,260", "Total assets"])
        self.assertAlmostEqual(float((v[0] ** 2).sum()), 1.0, places=5)


class AnswerTests(AppTestCase):
    def ask(self, question="What was net income?"):
        return self.client.post("/api/ask", json={"question": question}).json()

    def test_verified_answer_with_citation(self):
        self.client_with(NET_INCOME)
        self.upload()
        r = self.ask()
        self.assertEqual(r["status"], "answered")
        self.assertEqual(r["citations"][0]["page"], 3)
        self.assertEqual(r["citations"][0]["quote"], "Net income: 3,260")

    def test_quote_not_in_passage_is_rejected(self):
        self.client_with({**NET_INCOME, "citations": [{"passage": "P1", "quote": "Net income rose to a record high"}]})
        self.upload()
        r = self.ask()
        self.assertEqual((r["status"], r["answer"]), ("unverified", None))
        self.assertTrue(r["rejected_citations"])

    def test_quote_matches_text_where_the_pdf_split_words(self):
        passage = [{"chunk_id": 1, "document_id": 1, "filename": "t.pdf", "page": 9,
                    "text": "The budget deficit de creased by $41.4 b illion (2.3 percent) to $1.8 trillion"}]
        raw = {"found": True, "answer": "The deficit decreased by $41.4 billion to $1.8 trillion.",
               "citations": [{"passage": "P1", "quote": "The budget deficit decreased by $41.4 billion"}]}
        self.assertEqual(verify(raw, passage, "m")["status"], "answered")

    def test_invented_figure_is_rejected(self):
        self.client_with({**NET_INCOME, "answer": "Net income was 9,999 thousand dollars."})
        self.upload()
        r = self.ask()
        self.assertEqual(r["status"], "unverified")
        self.assertIn("9999", r["reason"])

    def test_numbers_from_the_question_are_allowed(self):
        self.client_with({**NET_INCOME, "answer": "In 2025, net income was 3,260 thousand dollars."})
        self.upload()
        self.assertEqual(self.ask("What was net income in 2025?")["status"], "answered")

    def test_not_found_is_honest(self):
        self.client_with({"found": False, "answer": "", "citations": []})
        self.upload()
        r = self.ask("Who audited the financial statements?")
        self.assertEqual((r["status"], r["answer"]), ("not_found", NOT_FOUND))

    def test_citation_to_a_passage_that_was_not_retrieved_is_rejected(self):
        self.client_with({**NET_INCOME, "citations": [{"passage": "P9", "quote": "Net income: 3,260"}]})
        self.upload()
        self.assertEqual(self.ask()["status"], "unverified")

    def test_prompt_contains_retrieved_passages_and_question_only(self):
        self.client_with(NET_INCOME)
        self.upload()
        self.ask()
        prompt = self.opener.sent[0]["contents"][0]["parts"][0]["text"]
        self.assertIn("Question: What was net income?", prompt)
        self.assertIn("(harbor.pdf, page 3)", prompt)
        self.assertEqual(prompt.count("[P"), 3)            # the fixture has 3 passages, all retrieved

    def test_without_a_key_relevant_passages_are_returned_instead(self):
        self.settings = load_settings({"DATA_DIR": self.tmp.name, "EMBEDDER": "hashing"})
        self.client_with()
        self.upload()
        r = self.ask()
        self.assertEqual(r["status"], "no_ai")
        self.assertEqual(r["passages"][0]["page"], 3)

    def test_questions_are_logged(self):
        self.client_with(NET_INCOME)
        self.upload()
        self.ask()
        self.assertEqual(self.client.get("/api/health").json()["questions_logged"], 1)

    def test_malformed_model_output_is_not_shown(self):
        for raw in (None, [], {"found": "yes"}, {"found": True, "answer": "", "citations": []}):
            with self.subTest(raw=raw):
                self.assertNotEqual(verify(raw, [], "m")["status"], "answered")


class ReviewAndUsageTests(AppTestCase):
    """The human review step and the hypercare usage report."""

    def ask(self, question="What was net income?"):
        return self.client.post("/api/ask", json={"question": question}).json()

    def setUp(self):
        super().setUp()
        self.client_with(NET_INCOME, {"found": False, "answer": "", "citations": []},
                         {**NET_INCOME, "answer": "Net income was 9,999 thousand dollars."})
        self.upload()
        self.ask()                                   # answered
        self.ask("Who audited the statements?")      # not found
        self.ask("What was net income in total?")    # withheld

    def test_withheld_and_not_found_answers_wait_for_review(self):
        queue = self.client.get("/api/review-queue").json()
        self.assertEqual([q["status"] for q in queue], ["not_found", "unverified"])
        self.assertIsInstance(queue[0]["asked_at"], str)

    def test_a_reviewed_question_leaves_the_queue(self):
        first = self.client.get("/api/review-queue").json()[0]
        r = self.client.post(f"/api/reviews/{first['id']}",
                             json={"decision": "confirmed_gap", "reviewer": "analyst-1", "note": "Not in the report."})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["decision"], "confirmed_gap")
        self.assertEqual(len(self.client.get("/api/review-queue").json()), 1)

    def test_a_second_review_replaces_the_first(self):
        qid = self.client.get("/api/review-queue").json()[0]["id"]
        for decision in ("other", "retrieval_miss"):
            self.client.post(f"/api/reviews/{qid}", json={"decision": decision, "reviewer": "analyst-1"})
        self.assertEqual(self.client.get("/api/usage").json()["review_decisions"], {"retrieval_miss": 1})

    def test_bad_reviews_are_rejected(self):
        qid = self.client.get("/api/review-queue").json()[0]["id"]
        self.assertEqual(self.client.post(f"/api/reviews/{qid}", json={"decision": "looks fine", "reviewer": "a"}).status_code, 422)
        self.assertEqual(self.client.post("/api/reviews/999", json={"decision": "other", "reviewer": "a"}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/reviews/{qid}", json={"decision": "other", "reviewer": ""}).status_code, 422)

    def test_usage_report_shows_adoption_and_quality(self):
        u = self.client.get("/api/usage").json()
        self.assertEqual(u["questions"], 3)
        self.assertEqual(u["by_status"], {"answered": 1, "not_found": 1, "unverified": 1})
        self.assertEqual((u["answered_share"], u["needs_review"], u["awaiting_review"]), (0.333, 2, 2))
        self.assertIsNotNone(u["median_latency_ms"])

    def test_usage_report_on_an_empty_log(self):
        self.tearDown()
        AppTestCase.setUp(self)
        self.client_with()
        u = self.client.get("/api/usage").json()
        self.assertEqual((u["questions"], u["answered_share"], u["median_latency_ms"]), (0, None, None))


if __name__ == "__main__":
    unittest.main()
