"""Two embedders behind one interface.

GeminiEmbedder: semantic embeddings from Google's API (used when a key is set).
HashingEmbedder: word and word-pair hashing, no network or model download. It is lexical, not
semantic, and exists so the app, tests and CI work offline. Results are labelled with the embedder.
"""
import re
import zlib

import numpy as np

from . import gemini

TOKEN = re.compile(r"[a-z]+|\d+(?:\.\d+)?")


class HashingEmbedder:
    name = "hashing-v1"
    dim = 2048

    def _vector(self, text):
        words = TOKEN.findall(text.lower().replace(",", ""))
        features = words + [a + " " + b for a, b in zip(words, words[1:])]
        v = np.zeros(self.dim, dtype=np.float32)
        for f in features:
            h = zlib.crc32(f.encode())
            v[h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0   # signed hashing reduces collisions
        v = np.sign(v) * np.log1p(np.abs(v))
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts):
        return np.vstack([self._vector(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text):
        return self._vector(text)


class GeminiEmbedder:
    dim = 768
    batch = 100

    def __init__(self, key, model, opener=None):
        self.key, self.model, self.opener = key, model, opener
        self.name = f"gemini:{model}:{self.dim}"

    def _embed(self, texts, task):
        out = []
        for i in range(0, len(texts), self.batch):
            out += gemini.embed(texts[i:i + self.batch], self.key, self.model, task, self.opener, self.dim)
        v = np.asarray(out, dtype=np.float32)
        norms = np.linalg.norm(v, axis=1, keepdims=True)
        return v / np.where(norms == 0, 1, norms)

    def embed_documents(self, texts):
        return self._embed(texts, "RETRIEVAL_DOCUMENT") if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text):
        return self._embed([text], "RETRIEVAL_QUERY")[0]


def make_embedder(settings, opener=None):
    if settings.embedder == "gemini":
        if not settings.gemini_api_key:
            raise gemini.AIError("EMBEDDER=gemini needs GEMINI_API_KEY.")
        return GeminiEmbedder(settings.gemini_api_key, settings.embedding_model, opener)
    return HashingEmbedder()
