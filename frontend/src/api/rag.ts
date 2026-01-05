import { apiClient } from "./client";
import type { RagDocument, RagDocumentListResponse, RagUploadResponse } from "../types";

export async function fetchDocuments(): Promise<RagDocument[]> {
  const data = await apiClient.get<RagDocumentListResponse>("/rag/documents");
  return data.documents;
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
