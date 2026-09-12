// Shared TypeScript types for the GitHub Chat Assistant

export type IngestStatus = "pending" | "running" | "completed" | "failed";

export type NodeType =
  | "function"
  | "class"
  | "interface"
  | "method"
  | "module"
  | "unknown";

export interface IngestRequest {
  repo_url: string;
  branch: string;
  force_reindex?: boolean;
}

export interface IngestStatusResponse {
  job_id: string;
  status: IngestStatus;
  repo_url: string;
  branch: string;
  files_processed: number;
  chunks_indexed: number;
  error?: string | null;
}

export interface SourceReference {
  chunk_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  node_type: NodeType;
  node_name?: string | null;
  language: string;
  score: number;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  sources: SourceReference[];
  cached: boolean;
  latency_ms: number;
  repo_id: string;
}

export type SSEEventType = "sources" | "token" | "done" | "error";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[];
  cached?: boolean;
  streaming?: boolean;
  latency_ms?: number;
  timestamp: Date;
}
