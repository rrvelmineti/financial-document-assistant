import { useRef, useState } from "react";
import { api } from "../api";
import type { DocumentInfo, Health } from "../types";

interface Props {
  documents: DocumentInfo[];
  health: Health | null;
  excluded: Set<number>;
  onToggle: (id: number) => void;
  onChange: () => void;
}

const sizeLabel = (bytes: number) => (bytes > 1_000_000 ? `${(bytes / 1_000_000).toFixed(1)} MB` : `${Math.ceil(bytes / 1000)} KB`);

export function DocumentPanel({ documents, health, excluded, onToggle, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [dragging, setDragging] = useState(false);

  async function add(files: FileList | null) {
    if (!files?.length) return;
    setMessage(null);
    for (const file of Array.from(files)) {
      setBusy(`Reading ${file.name}…`);
      try {
        const { document, created } = await api.upload(file);
        setMessage({
          kind: "ok",
          text: created
            ? `Added ${document.filename}: ${document.pages} pages, ${document.chunks} passages.`
            : `${document.filename} is already here.`,
        });
      } catch (err) {
        setMessage({ kind: "error", text: `${file.name}: ${(err as Error).message}` });
      }
    }
    setBusy(null);
    if (input.current) input.current.value = "";
    onChange();
  }

  async function remove(doc: DocumentInfo) {
    if (!window.confirm(`Remove ${doc.filename} and its passages?`)) return;
    try {
      await api.remove(doc.id);
      onChange();
    } catch (err) {
      setMessage({ kind: "error", text: (err as Error).message });
    }
  }

  return (
    <aside className="rail" aria-label="Documents">
      <h1 className="wordmark">Financial Document Assistant</h1>
      <p className="rail-intro">Answers come only from the documents below, with the line that backs them.</p>

      <div
        className={`drop${dragging ? " is-dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(e.dataTransfer.files);
        }}
      >
        <input ref={input} id="file" type="file" accept=".pdf,.txt,.md" multiple onChange={(e) => add(e.target.files)} hidden />
        <button type="button" className="button secondary" onClick={() => input.current?.click()} disabled={!!busy}>
          Add documents
        </button>
        <span className="hint">PDF, TXT or MD, up to 25 MB. Or drop files here.</span>
      </div>
      <p className="status-line" role="status" aria-live="polite">
        {busy ?? (message && <span className={message.kind === "error" ? "text-error" : undefined}>{message.text}</span>)}
      </p>

      <h2 className="rail-heading">{documents.length === 1 ? "1 document" : `${documents.length} documents`}</h2>
      {documents.length === 0 ? (
        <p className="empty">Add a financial report to start asking questions.</p>
      ) : (
        <ul className="doc-list">
          {documents.map((d) => (
            <li key={d.id} className="doc">
              <label className="doc-check">
                <input type="checkbox" checked={!excluded.has(d.id)} onChange={() => onToggle(d.id)} />
                <span className="doc-name">{d.filename}</span>
              </label>
              <span className="doc-meta">
                {d.pages} pages, {d.chunks} passages, {sizeLabel(d.size_bytes)}
              </span>
              <button type="button" className="link-button" onClick={() => remove(d)} aria-label={`Remove ${d.filename}`}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {documents.length > 1 && <p className="hint">Untick a document to leave it out of the search.</p>}

      {health && (
        <p className="engine">
          {health.ai_enabled ? "Answers by Gemini, checked against the source." : "No Gemini key set: showing the most relevant passages only."}{" "}
          Search: {health.embedder.startsWith("gemini") ? "Gemini embeddings" : "offline keyword hashing"}. Records:{" "}
          {health.database === "postgresql" ? "PostgreSQL" : "SQLite"}.
        </p>
      )}
    </aside>
  );
}
