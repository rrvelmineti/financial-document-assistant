"""Document metadata and passages in PostgreSQL (or SQLite locally); vectors searched with FAISS."""
import hashlib
import json
import threading
from datetime import datetime, timezone

import faiss
import numpy as np
from sqlalchemy import (JSON, Column, DateTime, ForeignKey, Integer, LargeBinary, MetaData, String, Table, Text,
                        create_engine, delete, event, func, insert, select)

from .documents import chunk_pages, read_pages

metadata = MetaData()

documents = Table(
    "documents", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("filename", String(255), nullable=False),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("size_bytes", Integer, nullable=False),
    Column("pages", Integer, nullable=False),
    Column("chunks", Integer, nullable=False),
    Column("embedder", String(100), nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
)
chunks = Table(
    "chunks", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("page", Integer, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("context", Text, nullable=False, default=""),
    Column("embedding", LargeBinary, nullable=False),
)
questions = Table(
    "questions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("asked_at", DateTime(timezone=True), nullable=False),
    Column("question", Text, nullable=False),
    Column("status", String(20), nullable=False),     # answered | not_found | unverified | no_ai
    Column("answer", Text),
    Column("citations", JSON),
    Column("model", String(100)),
    Column("latency_ms", Integer),
)


def now():
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, settings, embedder):
        self.settings, self.embedder = settings, embedder
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(settings.database_url, future=True)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys = ON"))
        metadata.create_all(self.engine)
        self.lock = threading.Lock()
        self.index = faiss.IndexIDMap(faiss.IndexFlatIP(embedder.dim))
        self._load_index()

    def _load_index(self):
        """Rebuild the in-memory FAISS index from stored vectors made by the current embedder."""
        with self.engine.connect() as conn:
            rows = conn.execute(select(chunks.c.id, chunks.c.embedding).join(documents)
                                .where(documents.c.embedder == self.embedder.name)).all()
        if rows:
            ids = np.array([r.id for r in rows], dtype=np.int64)
            vectors = np.vstack([np.frombuffer(r.embedding, dtype=np.float32) for r in rows])
            self.index.add_with_ids(vectors, ids)

    def add_document(self, filename, data):
        """Store a document once (by content hash). Returns (document, created)."""
        sha = hashlib.sha256(data).hexdigest()
        with self.engine.connect() as conn:
            existing = conn.execute(select(documents).where(documents.c.sha256 == sha)).mappings().first()
        if existing:
            if existing["embedder"] != self.embedder.name:
                self.delete_document(existing["id"])        # re-index with the embedder now in use
            else:
                return dict(existing), False
        pages = read_pages(filename, data, self.settings.max_pages)
        parts = chunk_pages(pages)
        vectors = self.embedder.embed_documents([c.text for c in parts])
        with self.lock, self.engine.begin() as conn:
            doc_id = conn.execute(insert(documents).values(
                filename=filename[:255], sha256=sha, size_bytes=len(data), pages=len(pages), chunks=len(parts),
                embedder=self.embedder.name, uploaded_at=now())).inserted_primary_key[0]
            rows = [{"document_id": doc_id, "page": c.page, "ordinal": c.ordinal, "text": c.text, "context": c.context,
                     "embedding": np.asarray(v, dtype=np.float32).tobytes()} for c, v in zip(parts, vectors)]
            ids = [r.id for r in conn.execute(
                insert(chunks).returning(chunks.c.id, sort_by_parameter_order=True), rows)] if rows else []
            if ids:
                self.index.add_with_ids(np.asarray(vectors, dtype=np.float32), np.array(ids, dtype=np.int64))
        return self.get_document(doc_id), True

    def get_document(self, doc_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(documents).where(documents.c.id == doc_id)).mappings().first()
        return dict(row) if row else None

    def list_documents(self):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(documents).order_by(documents.c.uploaded_at)).mappings()]

    def delete_document(self, doc_id):
        with self.lock, self.engine.begin() as conn:
            ids = [r.id for r in conn.execute(select(chunks.c.id).where(chunks.c.document_id == doc_id))]
            conn.execute(delete(chunks).where(chunks.c.document_id == doc_id))
            deleted = conn.execute(delete(documents).where(documents.c.id == doc_id)).rowcount
            if ids:
                self.index.remove_ids(np.array(ids, dtype=np.int64))
        return bool(deleted)

    def search(self, query, k, document_ids=None):
        """Top-k passages with document name, page and similarity score."""
        if self.index.ntotal == 0:
            return []
        q = np.asarray(self.embedder.embed_query(query), dtype=np.float32)[None, :]
        wanted = set(document_ids or [])
        fetch = min(self.index.ntotal, k * 8 if wanted else k)
        scores, ids = self.index.search(q, fetch)
        hits = [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
        if not hits:
            return []
        with self.engine.connect() as conn:
            rows = {r.id: r for r in conn.execute(
                select(chunks.c.id, chunks.c.document_id, chunks.c.page, chunks.c.text, chunks.c.context, documents.c.filename)
                .join(documents).where(chunks.c.id.in_([i for i, _ in hits])))}
        out = []
        for i, score in hits:
            r = rows.get(i)
            if r is None or (wanted and r.document_id not in wanted):
                continue
            out.append({"chunk_id": i, "document_id": r.document_id, "filename": r.filename,
                        "page": r.page, "text": r.text, "context": r.context, "score": round(score, 4)})
            if len(out) == k:
                break
        return out

    def log_question(self, question, result, latency_ms):
        with self.engine.begin() as conn:
            conn.execute(insert(questions).values(
                asked_at=now(), question=question[:4000], status=result["status"], answer=result.get("answer"),
                citations=json.loads(json.dumps(result.get("citations", []))), model=result.get("model"),
                latency_ms=latency_ms))

    def stats(self):
        with self.engine.connect() as conn:
            n_docs = conn.execute(select(func.count()).select_from(documents)).scalar_one()
            n_q = conn.execute(select(func.count()).select_from(questions)).scalar_one()
        return {"documents": n_docs, "passages_indexed": int(self.index.ntotal), "questions_logged": n_q,
                "embedder": self.embedder.name, "database": self.engine.dialect.name}
