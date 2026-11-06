"""Minimal Gemini REST client. Tests pass a fake `opener`, so no test calls the live API."""
import json
import re
import urllib.error
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_ID = re.compile(r"[A-Za-z0-9._-]+")


class AIError(RuntimeError):
    """Gemini was unavailable or returned something that could not be used."""


def _post(url, body, key, opener=None, timeout=60):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError("response too large")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise AIError(f"Gemini returned HTTP {exc.code}. Check the model ID, API key and quota.") from None
    except (OSError, ValueError) as exc:
        raise AIError(f"Gemini could not be reached or answered unreadably ({type(exc).__name__}).") from None


def _check_model(model):
    if not model or not MODEL_ID.fullmatch(model):
        raise AIError("Set GEMINI_MODEL to a model ID such as the one shown in Google AI Studio.")


def generate_json(prompt, key, model, opener=None):
    _check_model(model)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    data = _post(f"{BASE}/{model}:generateContent", body, key, opener)
    try:
        candidate = data["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError
        text = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
        return json.loads(text)
    except (KeyError, IndexError, TypeError, ValueError):
        raise AIError("Gemini's answer was incomplete or not valid JSON.") from None


def embed(texts, key, model, task, opener=None, dimensions=768):
    """Embed a batch of texts. task is RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY."""
    _check_model(model)
    body = {"requests": [{"model": f"models/{model}", "content": {"parts": [{"text": t}]},
                          "taskType": task, "outputDimensionality": dimensions} for t in texts]}
    data = _post(f"{BASE}/{model}:batchEmbedContents", body, key, opener, timeout=120)
    try:
        vectors = [e["values"] for e in data["embeddings"]]
    except (KeyError, TypeError):
        raise AIError("Gemini returned embeddings in an unexpected format.") from None
    if len(vectors) != len(texts) or any(len(v) != dimensions for v in vectors):
        raise AIError("Gemini returned the wrong number or size of embeddings.")
    return vectors
