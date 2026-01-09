export type RagDocument = {
  document_id: string;
  original_file: string;
  stored_file: string;
  size_bytes: number;
  chunks: number;
  uploaded_at: string;
  metadata: Record<string, unknown>;
  status?: string;
  job_id?: string;
  error?: string | null;
};

export type RagChunk = {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
};

export type RagDocumentListResponse = {
  documents: RagDocument[];
};

export type RagDocumentDetailResponse = {
  document: RagDocument;
};

export type RagChunkListResponse = {
  document_id: string;
  chunks: RagChunk[];
};

export type RagJob = {
  job_id: string;
  document_id: string | null;
  status: string;
  error?: string | null;
  created_at: string | null;
  updated_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  original_file: string;
  stored_file: string;
  size_bytes: number;
};

export type RagJobListResponse = {
  jobs: RagJob[];
};

export type RagJobResponse = {
  job: RagJob;
};

export type RagUploadResponse = {
  status: string;
  task_id: string;
  document_id: string;
  file_name: string;
  stored_file: string;
  job_id?: string;
};

export type RagIngestionStatusResponse = {
  task_id: string;
  status: string;
  result?: {
    status?: string;
    document_id?: string;
    chunks?: number;
    file_name?: string;
  };
  error?: string;
};

export type ChatContext = {
  university: string;
  program: string;
  year: number;
  itp?: string;
  [key: string]: unknown;
};

export type ChatMetadata = {
  channel: string;
  session_id: string;
  [key: string]: unknown;
};

export type ChatRequestPayload = {
  user_id: number;
  telegram_id?: number;
  person_id?: string | null;
  message: string;
  language: string;
  context: ChatContext;
  metadata: ChatMetadata;
};

export type ChatPlanStep = {
  agent: string;
  description: string;
};

export type ChatTraceItem = Record<string, unknown>;

export type ChatLLMInfo = {
  model: string | null;
  used: boolean;
  error: string | null;
  raw_request: Record<string, unknown> | null;
};

export type ChatResult = {
  query: string;
  intents: string[];
  priority?: string;
  plan: ChatPlanStep[];
  trace: ChatTraceItem[];
  final_answer: string;
  validation: Record<string, unknown>;
  citations: Record<string, unknown>[];
  supporting_context: Record<string, unknown>[];
  llm: ChatLLMInfo;
};

export type ChatResponse = {
  result: ChatResult;
};

export type ChatHistoryMessage = {
  id: string;
  role: "user" | "bot";
  content: string;
  created_at: string;
};

export type ChatHistorySession = {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatHistoryMessage[];
};

export type ChatHistoryResponse = {
  sessions: ChatHistorySession[];
};
