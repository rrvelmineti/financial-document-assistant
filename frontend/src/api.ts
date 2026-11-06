import type { AnswerResult, DocumentInfo, Health } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = `The server returned ${response.status}.`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join(" ");
    } catch {
      /* keep the generic message */
    }
    throw new Error(detail);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const api = {
  health: () => request<Health>("/api/health"),
  documents: () => request<DocumentInfo[]>("/api/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ document: DocumentInfo; created: boolean }>("/api/documents", { method: "POST", body: form });
  },
  remove: (id: number) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  ask: (question: string, documentIds: number[] | null) =>
    request<AnswerResult>("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, document_ids: documentIds }),
    }),
};
