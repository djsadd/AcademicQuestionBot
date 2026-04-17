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

export type ChatHistoryEntry = {
  role: "user" | "assistant" | "bot";
  content: string;
  created_at?: string;
};

export type ChatRequestPayload = {
  user_id?: number;
  telegram_id?: number;
  person_id?: string | null;
  uuid?: string;
  message: string;
  language: string;
  context: ChatContext;
  metadata: ChatMetadata;
  history?: ChatHistoryEntry[];
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
  validation?: Record<string, unknown>;
  citations?: Record<string, unknown>[];
  supporting_context?: Record<string, unknown>[];
  llm: ChatLLMInfo;
  tool_data?: Record<string, unknown>;
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

export type AdmissionApplication = {
  id: string;
  telegram_id: number | null;
  person_id: string | null;
  channel: string | null;
  full_name: string;
  iin: string | null;
  birth_date: string | null;
  phone: string;
  email: string | null;
  education_level: string;
  program: string;
  study_language: string | null;
  study_format: string | null;
  comment: string | null;
  status: string;
  source: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AdmissionApplicationListResponse = {
  items: AdmissionApplication[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export type AdmissionTechnicalContact = {
  name: string;
  phone: string;
  note?: string | null;
};

export type AdmissionContactSection = {
  department: string;
  phone: string[];
  email: string[];
  address: string;
  working_hours: string;
  website?: string | null;
  technical_contacts: AdmissionTechnicalContact[];
  updated_at?: string | null;
  [key: string]: unknown;
};

export type AdmissionProgram = {
  id?: string | null;
  name: string;
  name_ru?: string | null;
  name_kk?: string | null;
  name_en?: string | null;
  profile_subject_1?: string | null;
  profile_subject_2?: string | null;
  aliases?: string[];
  level: string;
  duration: string;
  tuition: {
    amount: number | null;
    period?: string | null;
    updated_at?: string | null;
    [key: string]: unknown;
  };
  passing_score: {
    gop_code?: string | null;
    grant?: number | null;
    grant_full?: number | null;
    grant_short?: number | null;
    paid?: number | null;
    exam?: string | null;
    notes?: string[];
    updated_at?: string | null;
    [key: string]: unknown;
  };
  source?: string | null;
  [key: string]: unknown;
};

export type AdmissionInfoPayload = {
  institution: string;
  currency: string;
  last_updated?: string | null;
  duration_rules: Record<string, unknown>;
  contacts: AdmissionContactSection;
  scholarships?: Record<string, unknown>;
  management?: Record<string, unknown>;
  documents: Record<string, unknown>;
  programs: AdmissionProgram[];
  [key: string]: unknown;
};

export type AdmissionInfoResponse = {
  status: string;
  source_path: string;
  data: AdmissionInfoPayload;
};

export type AdmissionProgramsListItem = {
  program_index: number;
  program_id?: string | null;
};

export type AdmissionProgramsListResponse = {
  status: string;
  items: AdmissionProgramsListItem[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
  filters: {
    search: string;
    level: string;
  };
};

export type ChatAnalyticsSummary = {
  total_events: number;
  total_sessions: number;
  anonymous_events: number;
  authenticated_events: number;
  anonymous_sessions: number;
  authenticated_sessions: number;
  unique_users: number;
  last_event_at: string | null;
};

export type ChatAnalyticsQuestion = {
  query: string;
  created_at: string;
};

export type ChatAnalyticsSession = {
  session_key: string;
  session_id: string;
  request_uuid?: string | null;
  channel: string | null;
  telegram_id: number | null;
  person_id: string | null;
  full_name: string | null;
  email: string | null;
  auth_mode: "anonymous" | "authenticated";
  event_count: number;
  started_at: string | null;
  updated_at: string | null;
  last_query: string | null;
  last_response: string | null;
  questions: ChatAnalyticsQuestion[];
};

export type ChatAnalyticsSessionListResponse = {
  items: ChatAnalyticsSession[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export type ChatAnalyticsUser = {
  user_key: string;
  telegram_id: number | null;
  person_id: string | null;
  full_name: string | null;
  email: string | null;
  role: string | null;
  event_count: number;
  session_count: number;
  first_seen: string | null;
  last_seen: string | null;
  last_query: string | null;
  recent_queries: ChatAnalyticsQuestion[];
};

export type ChatAnalyticsUserListResponse = {
  items: ChatAnalyticsUser[];
  limit: number;
};

export type ChatAnalyticsEvent = {
  id: string;
  session_key: string;
  session_id: string;
  request_uuid?: string | null;
  channel: string | null;
  telegram_id: number | null;
  person_id: string | null;
  auth_mode: "anonymous" | "authenticated";
  query: string | null;
  response: string | null;
  llm_model: string | null;
  llm_used: boolean | null;
  llm_error: string | null;
  intents: unknown[];
  agents: unknown[];
  trace: unknown[];
  metadata: Record<string, unknown>;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
  created_at: string | null;
};

export type ChatAnalyticsEventListResponse = {
  session_key: string;
  items: ChatAnalyticsEvent[];
};

export type AgentChannelMetric = {
  channel: string;
  count: number;
};

export type AgentOverviewItem = {
  key: string;
  name: string;
  label: string;
  description: string;
  kind: string;
  state: "healthy" | "degraded" | "idle" | string;
  executions: number;
  sessions: number;
  success_count: number;
  error_count: number;
  direct_response_count: number;
  authenticated_count: number;
  anonymous_count: number;
  success_rate: number;
  channel_breakdown: AgentChannelMetric[];
  last_used_at: string | null;
  last_status: string;
  last_error: string | null;
};

export type AgentOverviewResponse = {
  items: AgentOverviewItem[];
  window_days: number;
  summary: {
    total_agents: number;
    active_agents: number;
    healthy_agents: number;
    degraded_agents: number;
    idle_agents: number;
    error_agents: number;
  };
};
