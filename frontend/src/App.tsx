import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { AnswerView, type Exchange } from "./components/AnswerView";
import { DocumentPanel } from "./components/DocumentPanel";
import type { DocumentInfo, Health } from "./types";

const EXAMPLES = [
  "What was net cost of operations for the year?",
  "How much did the Deposit Insurance Fund balance change?",
  "Who audited the financial statements?",
];

export default function App() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [question, setQuestion] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const nextId = useRef(1);

  const refresh = useCallback(async () => {
    try {
      const [docs, h] = await Promise.all([api.documents(), api.health()]);
      setDocuments(docs);
      setHealth(h);
      setExcluded((prev) => new Set([...prev].filter((id) => docs.some((d) => d.id === id))));
      setLoadError(null);
    } catch (err) {
      setLoadError(`The server could not be reached: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function toggle(id: number) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const included = documents.filter((d) => !excluded.has(d.id));

  async function ask(text: string) {
    const q = text.trim();
    if (q.length < 3) return;
    const id = nextId.current++;
    setExchanges((prev) => [{ id, question: q }, ...prev]);
    setQuestion("");
    try {
      const result = await api.ask(q, excluded.size ? included.map((d) => d.id) : null);
      setExchanges((prev) => prev.map((e) => (e.id === id ? { ...e, result } : e)));
    } catch (err) {
      setExchanges((prev) => prev.map((e) => (e.id === id ? { ...e, error: (err as Error).message } : e)));
    }
  }

  const canAsk = included.length > 0;

  return (
    <div className="layout">
      <DocumentPanel documents={documents} health={health} excluded={excluded} onToggle={toggle} onChange={refresh} />
      <main className="desk">
        {loadError && <p className="text-error banner">{loadError}</p>}
        <form
          className="ask"
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
        >
          <label htmlFor="question" className="ask-label">
            Ask about your documents
          </label>
          <div className="ask-row">
            <input
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={
                canAsk ? "For example: what was total revenue for the fiscal year?" : documents.length ? "Tick at least one document" : "Add a document first"
              }
              disabled={!canAsk}
              maxLength={1000}
              autoComplete="off"
            />
            <button className="button" type="submit" disabled={!canAsk || question.trim().length < 3}>
              Ask
            </button>
          </div>
          {canAsk && exchanges.length === 0 && (
            <div className="examples">
              <span className="hint">Try:</span>
              {EXAMPLES.map((ex) => (
                <button type="button" key={ex} className="chip" onClick={() => ask(ex)}>
                  {ex}
                </button>
              ))}
            </div>
          )}
        </form>

        {exchanges.length === 0 ? (
          <section className="intro" aria-label="How answers are checked">
            <h2>Every answer shows its source line</h2>
            <p>
              The assistant reads only the passages it finds in your documents. It must quote the line it relied on, and
              the quote and every figure are checked against the page before you see them. When the documents don't say,
              it tells you so.
            </p>
          </section>
        ) : (
          <div className="exchanges">
            {exchanges.map((e) => (
              <AnswerView key={e.id} exchange={e} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
