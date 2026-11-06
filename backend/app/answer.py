"""Answer only from retrieved passages, and verify the evidence before showing an answer.

Statuses:
  answered    every cited quote appears in its passage, and every number in the answer is in the cited text
  not_found   the model said the passages do not contain the answer, or nothing was retrieved
  unverified  the model answered, but its evidence did not check out; the answer is withheld
  no_ai       no Gemini key is configured; the most relevant passages are returned instead
  error       Gemini could not be reached
"""
import re

from . import gemini

NOT_FOUND = "Not found in these documents."
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalise(text):
    """Compare text without case, curly quotes or any whitespace.

    PDF text extraction often inserts or drops spaces ("de creased", "b illion", or every letter
    spaced out), so a faithful quote may differ from the extracted text only in spacing.
    """
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", "", text).lower()


def numbers_in(text):
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)}


def build_prompt(question, passages):
    blocks = "\n\n".join(
        f"[P{i}] ({p['filename']}, page {p['page']})"
        + (f"\n[Stated elsewhere on this page: {p['context']}]" if p.get("context") else "")
        + f"\n{p['text']}" for i, p in enumerate(passages, 1))
    return (
        "You answer questions about financial documents for an analyst. Use ONLY the passages below.\n"
        "Rules:\n"
        "- If the passages do not contain the answer, set found to false and leave answer empty.\n"
        "- Every fact in the answer must be supported by a citation. For each citation, copy an exact "
        "quote of one or two sentences or table lines from that passage, character for character.\n"
        "- Copy numbers exactly as written in the passage, with their units. Do not calculate, round or "
        "convert numbers. When a passage notes units or year columns stated elsewhere on the page, use them "
        "to read the figures, and say the units in the answer. Quotes must come from the passage text, not "
        "from that note.\n"
        "- Keep the answer to one to three sentences.\n"
        'Return only JSON: {"found": true|false, "answer": "...", '
        '"citations": [{"passage": "P1", "quote": "..."}]}\n\n'
        f"Passages:\n{blocks}\n\nQuestion: {question}")


def verify(raw, passages, model, question=""):
    """Turn the model's JSON into a result, keeping only evidence that is really in the passages.

    Every number in the answer must appear in a cited passage or in the question itself
    (so an answer may repeat the year the user asked about). Single digits are exempt.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("found"), bool):
        return {"status": "unverified", "reason": "The model's answer was not in the expected format.",
                "answer": None, "citations": [], "model": model}
    if not raw["found"]:
        return {"status": "not_found", "answer": NOT_FOUND, "citations": [], "model": model}
    answer = raw.get("answer") if isinstance(raw.get("answer"), str) else ""
    labels = {f"P{i}": p for i, p in enumerate(passages, 1)}
    citations, rejected = [], []
    for c in raw.get("citations") or []:
        if not isinstance(c, dict):
            continue
        p, quote = labels.get(str(c.get("passage", "")).strip("[] ")), c.get("quote")
        if p is None or not isinstance(quote, str) or len(normalise(quote)) < 8:
            rejected.append("a citation pointed at no retrieved passage")
        elif normalise(quote) not in normalise(p["text"]):
            rejected.append(f"a quote was not found word for word on {p['filename']} page {p['page']}")
        else:
            citations.append({"chunk_id": p["chunk_id"], "document_id": p["document_id"], "filename": p["filename"],
                              "page": p["page"], "quote": quote.strip(), "passage": p["text"],
                              "context": p.get("context", "")})
    base = {"answer": None, "citations": citations, "model": model, "rejected_citations": rejected}
    if not answer.strip():
        return {**base, "status": "unverified", "reason": "The model said it found an answer but gave none."}
    if not citations:
        return {**base, "status": "unverified", "reason": "None of the model's quotes could be found in the passages."}
    cited_numbers = set().union(numbers_in(question), *(numbers_in(c["passage"]) for c in citations))
    unsupported = sorted(n for n in numbers_in(answer) if n not in cited_numbers and len(n) > 1)
    if unsupported:
        return {**base, "status": "unverified",
                "reason": "The answer contains figures not in the cited passages: " + ", ".join(unsupported) + "."}
    return {**base, "status": "answered", "answer": answer.strip()}


def answer_question(question, store, settings, opener=None, document_ids=None):
    passages = store.search(question, settings.top_k, document_ids)
    shown = [{k: p.get(k, "") for k in ("chunk_id", "document_id", "filename", "page", "text", "context", "score")}
             for p in passages]
    if not passages:
        return {"status": "not_found", "answer": NOT_FOUND, "citations": [], "passages": [],
                "reason": "No documents have been uploaded yet." if not store.list_documents() else None}
    if not settings.ai_enabled:
        return {"status": "no_ai", "answer": None, "citations": [], "passages": shown,
                "reason": "No Gemini key is set, so here are the most relevant passages instead of an answer."}
    try:
        raw = gemini.generate_json(build_prompt(question, passages), settings.gemini_api_key,
                                   settings.gemini_model, opener)
    except gemini.AIError as exc:
        return {"status": "error", "answer": None, "citations": [], "passages": shown, "reason": str(exc)}
    return {**verify(raw, passages, settings.gemini_model, question), "passages": shown}
