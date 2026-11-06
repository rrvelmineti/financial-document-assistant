export interface DocumentInfo {
  id: number;
  filename: string;
  size_bytes: number;
  pages: number;
  chunks: number;
  embedder: string;
  uploaded_at: string;
}

export interface Passage {
  chunk_id: number;
  document_id: number;
  filename: string;
  page: number;
  text: string;
  context: string;
  score: number;
}

export interface Citation {
  chunk_id: number;
  document_id: number;
  filename: string;
  page: number;
  quote: string;
  passage: string;
  context: string;
}

export type Status = "answered" | "not_found" | "unverified" | "no_ai" | "error";

export interface AnswerResult {
  status: Status;
  answer: string | null;
  reason?: string | null;
  citations: Citation[];
  passages: Passage[];
  rejected_citations?: string[];
  model?: string | null;
  latency_ms: number;
}

export interface Health {
  ok: boolean;
  ai_enabled: boolean;
  documents: number;
  passages_indexed: number;
  questions_logged: number;
  embedder: string;
  database: string;
}
