export type RagDocument = {
  document_id: string;
  original_file: string;
  stored_file: string;
  size_bytes: number;
  chunks: number;
  uploaded_at: string;
  metadata: Record<string, unknown>;
};

export type RagDocumentListResponse = {
  documents: RagDocument[];
};

export type RagUploadResponse = {
  status: string;
  document_id: string;
  file_name: string;
  stored_file: string;
  chunks: number;
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
