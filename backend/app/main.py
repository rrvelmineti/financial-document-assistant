"""HTTP API and the built web interface.

    uvicorn app.main:create_app --factory --app-dir backend --reload
"""
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import gemini
from .answer import answer_question
from .config import ROOT, load_settings
from .documents import DocumentError
from .embeddings import make_embedder
from .store import REVIEW_DECISIONS, Store

FRONTEND = ROOT / "frontend" / "dist"


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_ids: list[int] | None = None


class Review(BaseModel):
    decision: str = Field(description="One of: " + ", ".join(REVIEW_DECISIONS))
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=2000)


def public(doc):
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in doc.items() if k != "sha256"}


def create_app(settings=None, opener=None):
    settings = settings or load_settings()
    store = Store(settings, make_embedder(settings, opener))
    app = FastAPI(title="Financial Document Assistant", version="1.0.0")
    app.state.store, app.state.settings = store, settings

    @app.get("/api/health")
    def health():
        return {"ok": True, "ai_enabled": settings.ai_enabled, **store.stats()}

    @app.get("/api/documents")
    def list_documents():
        return [public(d) for d in store.list_documents()]

    @app.post("/api/documents", status_code=201)
    async def upload(file: UploadFile = File(...)):
        limit = settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Files must be {settings.max_upload_mb} MB or smaller.")
        try:
            doc, created = store.add_document(Path(file.filename or "document").name, data)
        except DocumentError as exc:
            raise HTTPException(400, str(exc)) from None
        except gemini.AIError as exc:
            raise HTTPException(502, f"The document could not be indexed: {exc}") from None
        return {"document": public(doc), "created": created}

    @app.delete("/api/documents/{doc_id}", status_code=204)
    def remove(doc_id: int):
        if not store.delete_document(doc_id):
            raise HTTPException(404, "No such document.")

    @app.post("/api/ask")
    def ask(body: Ask):
        start = time.perf_counter()
        try:
            result = answer_question(body.question, store, settings, opener, body.document_ids)
        except gemini.AIError as exc:                     # embedding the question failed
            raise HTTPException(502, str(exc)) from None
        latency = round((time.perf_counter() - start) * 1000)
        store.log_question(body.question, result, latency)
        return {**result, "latency_ms": latency}

    @app.get("/api/review-queue")
    def review_queue(limit: int = 50):
        """Withheld and not-found answers that a person has not reviewed yet."""
        return [public(q) for q in store.review_queue(max(1, min(limit, 500)))]

    @app.post("/api/reviews/{question_id}", status_code=201)
    def review(question_id: int, body: Review):
        try:
            saved = store.record_review(question_id, body.decision, body.reviewer, body.note)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if saved is None:
            raise HTTPException(404, "No such question.")
        return public(saved)

    @app.get("/api/usage")
    def usage():
        """Adoption and quality figures for the hypercare period after go-live."""
        return store.usage_report()

    if FRONTEND.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            return FileResponse(FRONTEND / "index.html")

    return app
