import { useEffect, useRef } from "react";
import { highlight } from "../highlight";
import type { AnswerResult, Citation, Passage } from "../types";

export interface Exchange {
  id: number;
  question: string;
  result?: AnswerResult;
  error?: string;
}

const VERDICT: Record<string, { label: string; tone: string }> = {
  answered: { label: "Checked against the source", tone: "ok" },
  not_found: { label: "Not in these documents", tone: "neutral" },
  unverified: { label: "Answer withheld", tone: "warn" },
  no_ai: { label: "Relevant passages", tone: "neutral" },
  error: { label: "Could not answer", tone: "warn" },
};

interface EvidenceProps {
  filename: string;
  page: number;
  text: string;
  context?: string;
  quotes?: string[];
}

function Evidence({ filename, page, text, context, quotes = [] }: EvidenceProps) {
  const parts = quotes.length ? highlight(text, quotes) : [{ text, mark: false }];
  const body = useRef<HTMLQuoteElement>(null);
  useEffect(() => {
    // Long passages scroll inside the slip; start at the first highlighted line.
    const box = body.current;
    const mark = box?.querySelector("mark");
    if (box && mark) box.scrollTop = Math.max(0, mark.offsetTop - box.offsetTop - 48);
  }, [text]);
  return (
    <figure className="evidence">
      <figcaption className="evidence-ref" aria-label={`${filename}, page ${page}`}>
        <span className="ref-page">p. {page}</span>
      </figcaption>
      <div className="evidence-body">
        <p className="ref-doc">{filename}</p>
        {context && <p className="ref-context">Stated elsewhere on this page: {context}</p>}
        <blockquote className="evidence-text" ref={body}>
          {parts.map((p, i) => (p.mark ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))}
        </blockquote>
      </div>
    </figure>
  );
}

/** One evidence slip per passage, with every quote from that passage highlighted in it. */
function groupByPassage(citations: Citation[]) {
  const groups = new Map<number, { citation: Citation; quotes: string[] }>();
  for (const c of citations) {
    const g = groups.get(c.chunk_id);
    if (g) g.quotes.push(c.quote);
    else groups.set(c.chunk_id, { citation: c, quotes: [c.quote] });
  }
  return [...groups.values()];
}

function PassageList({ passages }: { passages: Passage[] }) {
  return (
    <>
      {passages.slice(0, 3).map((p) => (
        <Evidence key={p.chunk_id} filename={p.filename} page={p.page} text={p.text} context={p.context} />
      ))}
    </>
  );
}

export function AnswerView({ exchange }: { exchange: Exchange }) {
  const { question, result, error } = exchange;
  const verdict = result ? VERDICT[result.status] : null;
  return (
    <article className="exchange" aria-busy={!result && !error}>
      <p className="question">{question}</p>
      {!result && !error && <p className="pending">Searching the documents…</p>}
      {error && <p className="text-error">{error}</p>}
      {result && verdict && (
        <div className={`answer tone-${verdict.tone}`}>
          <p className="verdict">
            <span className="tick" aria-hidden="true" />
            {verdict.label}
          </p>
          {result.status === "answered" && <p className="answer-text">{result.answer}</p>}
          {result.status === "not_found" && (
            <p className="answer-text">{result.reason ?? "The uploaded documents don't contain an answer to this question."}</p>
          )}
          {(result.status === "unverified" || result.status === "error" || result.status === "no_ai") && result.reason && (
            <p className="answer-note">{result.reason}</p>
          )}
          {result.status === "unverified" && (
            <p className="answer-note">The passages it drew on are below, so you can check them yourself.</p>
          )}

          {result.status === "answered" &&
            groupByPassage(result.citations).map(({ citation: c, quotes }) => (
              <Evidence key={c.chunk_id} filename={c.filename} page={c.page} text={c.passage} context={c.context} quotes={quotes} />
            ))}
          {result.status !== "answered" && result.status !== "not_found" && <PassageList passages={result.passages} />}

          <p className="timing">{(result.latency_ms / 1000).toFixed(1)} s</p>
        </div>
      )}
    </article>
  );
}
