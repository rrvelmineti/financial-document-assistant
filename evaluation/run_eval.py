"""Evaluate the assistant on 25 questions about the three documents in documents/.

Offline (retrieval only, no key needed):
    python evaluation/run_eval.py

Full evaluation with Gemini answers (needs GEMINI_API_KEY and GEMINI_MODEL):
    python evaluation/run_eval.py --answers
    python evaluation/run_eval.py --answers --embedder hashing   # Gemini answers, offline retrieval

What is measured
- Retrieval: for answerable questions, does a retrieved passage come from a page that contains the
  evidence (recall at k)?
- Answer accuracy: the answer passed verification and contains every expected figure or phrase.
- Citation accuracy: at least one citation is on a page that contains the evidence.
- Not found: for the 5 unanswerable questions, did the assistant say it was not in the documents?
"""
import argparse
import json
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.answer import answer_question  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.embeddings import make_embedder  # noqa: E402
from app.store import Store  # noqa: E402

QUESTIONS = ROOT / "evaluation" / "questions.json"
DOCUMENTS = ROOT / "documents"
RESULTS = ROOT / "evaluation" / "results"


def norm(text):
    return re.sub(r"\s+", "", (text or "").replace("’", "'")).lower()


def build_store(embedder_name, data_dir):
    import os
    env = dict(os.environ, DATA_DIR=str(data_dir), EMBEDDER=embedder_name)
    env.pop("DATABASE_URL", None)                 # always a throwaway SQLite database
    settings = load_settings(env)
    store = Store(settings, make_embedder(settings))
    for pdf in sorted(DOCUMENTS.glob("*.pdf")):
        start = time.perf_counter()
        doc, _ = store.add_document(pdf.name, pdf.read_bytes())
        print(f"  indexed {pdf.name}: {doc['pages']} pages, {doc['chunks']} passages ({time.perf_counter() - start:.0f}s)")
    return settings, store


def on_evidence_page(q, filename, page):
    return filename == q["document"] and page in q["accepted_pages"]


def grade(q, result):
    answerable = q["document"] is not None
    row = {"id": q["id"], "question": q["question"], "status": result["status"], "answer": result.get("answer"),
           "reason": result.get("reason"),
           "citations": [{"filename": c["filename"], "page": c["page"], "quote": c["quote"]} for c in result.get("citations", [])],
           "retrieved": [{"filename": p["filename"], "page": p["page"], "score": p["score"]} for p in result.get("passages", [])]}
    row["retrieval_hit"] = any(on_evidence_page(q, p["filename"], p["page"]) for p in row["retrieved"]) if answerable else None
    if answerable:
        row["answer_correct"] = result["status"] == "answered" and all(norm(m) in norm(result.get("answer")) for m in q["must_contain"])
        row["citation_correct"] = any(on_evidence_page(q, c["filename"], c["page"]) for c in row["citations"])
    else:
        row["not_found_correct"] = result["status"] == "not_found"
        row["false_answer_shown"] = result["status"] == "answered"
    return row


def summarise(rows, embedder, model, k):
    a = [r for r in rows if r["id"].startswith("A")]
    u = [r for r in rows if r["id"].startswith("U")]
    s = {"run_on": date.today().isoformat(), "embedder": embedder, "model": model, "top_k": k,
         "answerable": len(a), "unanswerable": len(u),
         "retrieval_hits": sum(r["retrieval_hit"] for r in a)}
    if model:
        s.update({
            "answers_correct": sum(r["answer_correct"] for r in a),
            "citations_correct": sum(r["citation_correct"] for r in a),
            "answers_withheld": sum(r["status"] == "unverified" for r in a),
            "answerable_said_not_found": sum(r["status"] == "not_found" for r in a),
            "not_found_correct": sum(r["not_found_correct"] for r in u),
            "false_answers_on_unanswerable": sum(r["false_answer_shown"] for r in u),
        })
    return s


def write_report(summary, rows, path):
    lines = ["# Evaluation results", "",
             f"Run on {summary['run_on']}. Retrieval: `{summary['embedder']}`, top {summary['top_k']} passages. "
             f"Answer model: `{summary['model'] or 'none (retrieval only)'}`.", "",
             "| Measure | Result |", "| --- | --- |",
             f"| Retrieval: evidence page among retrieved passages | {summary['retrieval_hits']} of {summary['answerable']} |"]
    if summary["model"]:
        lines += [
            f"| Answer accuracy (verified and contains the expected figure) | {summary['answers_correct']} of {summary['answerable']} |",
            f"| Citation accuracy (cites a page with the evidence) | {summary['citations_correct']} of {summary['answerable']} |",
            f"| Answerable questions withheld by verification | {summary['answers_withheld']} |",
            f"| Answerable questions wrongly said not found | {summary['answerable_said_not_found']} |",
            f"| Unanswerable questions correctly said not found | {summary['not_found_correct']} of {summary['unanswerable']} |",
            f"| False answers shown on unanswerable questions | {summary['false_answers_on_unanswerable']} |",
        ]
    lines += ["", "## Per question", "", "| ID | Status | Correct | Cited pages | Notes |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["id"].startswith("A"):
            ok = ("yes" if r.get("answer_correct") else "no") if summary["model"] else ("hit" if r["retrieval_hit"] else "miss")
        else:
            ok = ("yes" if r.get("not_found_correct") else "no") if summary["model"] else "n/a"
        pages = ", ".join(f"p{c['page']}" for c in r["citations"]) or "-"
        note = (r.get("reason") or "").replace("|", "/")[:120]
        lines.append(f"| {r['id']} | {r['status']} | {ok} | {pages} | {note} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--answers", action="store_true", help="also generate and grade Gemini answers")
    parser.add_argument("--embedder", choices=["gemini", "hashing"], help="default: gemini with --answers, else hashing")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to wait between questions (rate limits)")
    args = parser.parse_args(argv)
    embedder = args.embedder or ("gemini" if args.answers else "hashing")
    questions = json.loads(QUESTIONS.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Indexing {len(list(DOCUMENTS.glob('*.pdf')))} documents with the {embedder} embedder...")
        settings, store = build_store(embedder, tmp)
        if args.answers and not settings.ai_enabled:
            raise SystemExit("--answers needs GEMINI_API_KEY and GEMINI_MODEL.")
        if not args.answers:
            settings = load_settings({"DATA_DIR": tmp, "EMBEDDER": embedder})      # retrieval only: no AI calls
        rows = []
        for q in questions:
            result = answer_question(q["question"], store, settings)
            rows.append(grade(q, result))
            mark = {True: "ok", False: "--", None: "  "}[rows[-1].get("answer_correct", rows[-1].get("not_found_correct"))
                                                           if args.answers else rows[-1]["retrieval_hit"]]
            print(f"  {q['id']} {mark} {result['status']:10} {q['question'][:70]}")
            if args.delay:
                time.sleep(args.delay)
        store.engine.dispose()
    summary = summarise(rows, store.embedder.name, settings.gemini_model if args.answers else None, settings.top_k)
    RESULTS.mkdir(exist_ok=True)
    tag = f"{'answers' if args.answers else 'retrieval'}-{embedder}"
    (RESULTS / f"{tag}.json").write_text(json.dumps({"summary": summary, "results": rows}, indent=2) + "\n")
    write_report(summary, rows, RESULTS / f"{tag}.md")
    print("\n" + json.dumps(summary, indent=2))
    print(f"Wrote evaluation/results/{tag}.md")


if __name__ == "__main__":
    main()
