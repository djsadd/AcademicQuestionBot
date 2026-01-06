import { apiClient } from "./client";
import type {
  RagDocument,
  RagChunk,
  RagChunkListResponse,
  RagDocumentDetailResponse,
  RagDocumentListResponse,
  RagIngestionStatusResponse,
  RagJob,
  RagJobListResponse,
  RagJobResponse,
  RagUploadResponse,
} from "../types";

export async function fetchDocuments(): Promise<RagDocument[]> {
  const data = await apiClient.get<RagDocumentListResponse>("/rag/documents");
  return data.documents;
}

export async function fetchDocumentDetail(documentId: string): Promise<RagDocument> {
  const data = await apiClient.get<RagDocumentDetailResponse>(`/rag/documents/${documentId}`);
  return data.document;
}

export async function fetchDocumentChunks(documentId: string, limit = 200): Promise<RagChunk[]> {
  const data = await apiClient.get<RagChunkListResponse>(
    `/rag/documents/${documentId}/chunks?limit=${limit}`
  );
  return data.chunks;
}

export async function deleteDocument(documentId: string): Promise<RagDocument> {
  const data = await apiClient.delete<{ status: string; document: RagDocument }>(
    `/rag/documents/${documentId}`
  );
  return data.document;
}

export async function uploadDocument(file: File, metadata?: Record<string, unknown>) {
  const formData = new FormData();
  formData.append("file", file);
  if (metadata && Object.keys(metadata).length > 0) {
    formData.append("metadata", JSON.stringify(metadata));
  }
  return apiClient.post<RagUploadResponse>("/rag/documents/upload", formData);
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
