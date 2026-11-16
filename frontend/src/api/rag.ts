import { API_BASE_URL, apiClient, authStorage, describeHttpError } from "./client";
import type {
  RagChunk,
  RagChunkListResponse,
  RagDocument,
  RagDocumentDetailResponse,
  RagDocumentListResponse,
  RagIngestionStatusResponse,
  RagJob,
  RagJobListResponse,
  RagJobResponse,
  RagSearchResult,
  RagStats,
  RagUploadResponse,
} from "../types";

export const fetchStats = () => apiClient.get<RagStats>("/rag/stats");

export async function fetchDocuments(): Promise<RagDocument[]> {
  const data = await apiClient.get<RagDocumentListResponse>("/rag/documents");
  return data.documents;
}

export async function fetchDocumentDetail(documentId: string): Promise<RagDocument> {
  const data = await apiClient.get<RagDocumentDetailResponse>(`/rag/documents/${encodeURIComponent(documentId)}`);
  return data.document;
}

export async function fetchDocumentChunks(documentId: string, limit = 500): Promise<RagChunk[]> {
  const data = await apiClient.get<RagChunkListResponse>(`/rag/documents/${encodeURIComponent(documentId)}/chunks?limit=${limit}`);
  return data.chunks;
}

export async function updateDocument(documentId: string, patch: Partial<Record<"title" | "category" | "audience" | "description", string>>) {
  const data = await apiClient.patch<{ document: RagDocument; reindex_recommended: boolean }>(
    `/rag/documents/${encodeURIComponent(documentId)}`,
    JSON.stringify(patch),
  );
  return data;
}

export async function deleteDocument(documentId: string): Promise<RagDocument> {
  const data = await apiClient.delete<{ status: string; document: RagDocument }>(`/rag/documents/${encodeURIComponent(documentId)}`);
  return data.document;
}

export const reindexDocument = (documentId: string) =>
  apiClient.post<{ status: string; task_id: string }>(`/rag/documents/${encodeURIComponent(documentId)}/reindex`);

export const reindexAll = (recreateCollection = false) =>
  apiClient.post<{ status: string; documents: number }>(`/rag/reindex-all?recreate_collection=${recreateCollection}`);

export type UploadFields = { title?: string; category?: string; audience?: string; description?: string; allowDuplicate?: boolean };

export async function uploadDocument(file: File, fields: UploadFields = {}) {
  const formData = new FormData();
  formData.append("file", file);
  for (const key of ["title", "category", "audience", "description"] as const) {
    const value = fields[key]?.trim();
    if (value) formData.append(key, value);
  }
  if (fields.allowDuplicate) formData.append("allow_duplicate", "true");
  return apiClient.post<RagUploadResponse>("/rag/documents/upload", formData);
}

export async function searchKnowledgeBase(query: string, topK = 5, hybrid = true): Promise<RagSearchResult[]> {
  const params = new URLSearchParams({ query, top_k: String(topK), hybrid: String(hybrid) });
  const data = await apiClient.get<{ results: RagSearchResult[] }>(`/rag/documents/search?${params}`);
  return data.results;
}

/** Download the original file (needs the auth header, so a plain link would not work). */
export async function downloadDocument(document: Pick<RagDocument, "document_id" | "original_file">) {
  const response = await fetch(`${API_BASE_URL}/rag/documents/${encodeURIComponent(document.document_id)}/file`, {
    headers: { Authorization: `Bearer ${authStorage.getAccessToken() ?? ""}` },
  });
  if (!response.ok) throw new Error(await describeHttpError(response));
  const url = URL.createObjectURL(await response.blob());
  const link = Object.assign(window.document.createElement("a"), { href: url, download: document.original_file });
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function fetchIngestionStatus(taskId: string) {
  return apiClient.get<RagIngestionStatusResponse>(`/rag/tasks/${taskId}`);
}

export async function fetchJobs(): Promise<RagJob[]> {
  const data = await apiClient.get<RagJobListResponse>("/rag/jobs");
  return data.jobs;
}

export async function fetchJob(jobId: string): Promise<RagJob> {
  const data = await apiClient.get<RagJobResponse>(`/rag/jobs/${jobId}`);
  return data.job;
}
