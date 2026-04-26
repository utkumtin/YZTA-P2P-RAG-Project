import { useState, useCallback, useRef } from 'react';
import axios from 'axios';
import { validateFile } from '../utils/validators';
import { DOC_STATUS, UPLOAD_POLL_INTERVAL_MS } from '../utils/constants';

export type UploadStatus = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

export interface UploadedFile {
  document_id: string;
  filename: string;
  status: UploadStatus;
  error?: string;
}

interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: string;
  message: string;
}

interface DocumentListItem {
  document_id: string;
  filename: string;
  status: string;
}

interface DocumentListResponse {
  documents: DocumentListItem[];
  total: number;
}

export interface UseUploadReturn {
  uploads: UploadedFile[];
  isUploading: boolean;
  uploadFiles: (files: File[]) => Promise<void>;
  removeUpload: (documentId: string) => void;
  clearUploads: () => void;
}

export function useUpload(): UseUploadReturn {
  const [uploads, setUploads] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const pollingIntervalsRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const stopPolling = useCallback((documentId: string) => {
    const interval = pollingIntervalsRef.current.get(documentId);
    if (interval) {
      clearInterval(interval);
      pollingIntervalsRef.current.delete(documentId);
    }
  }, []);

  const startPolling = useCallback((documentId: string) => {
    // TODO(Faz 3): /api/tasks/{job_id}/progress SSE endpoint hazır olduğunda
    // polling yerine SSE stream kullan

    const interval = setInterval(async () => {
      try {
        const response = await axios.get<DocumentListResponse>('/api/routes/documents');
        const doc = response.data.documents.find((d) => d.document_id === documentId);

        if (!doc) return;

        if (doc.status === DOC_STATUS.COMPLETED) {
          setUploads((prev) =>
            prev.map((u) =>
              u.document_id === documentId ? { ...u, status: 'done' } : u
            )
          );
          stopPolling(documentId);
        } else if (doc.status === DOC_STATUS.FAILED) {
          setUploads((prev) =>
            prev.map((u) =>
              u.document_id === documentId
                ? { ...u, status: 'error', error: 'Belge işleme başarısız' }
                : u
            )
          );
          stopPolling(documentId);
        }
      } catch {
        // Polling hatalarını sessizce geç, bir sonraki interval'de tekrar dene
      }
    }, UPLOAD_POLL_INTERVAL_MS);

    pollingIntervalsRef.current.set(documentId, interval);
  }, [stopPolling]);

  const uploadFiles = useCallback(async (files: File[]) => {
    const validFiles: File[] = [];
    const invalidEntries: UploadedFile[] = [];

    for (const file of files) {
      const result = validateFile(file);
      if (result.valid) {
        validFiles.push(file);
      } else {
        invalidEntries.push({
          document_id: crypto.randomUUID?.() ?? Date.now().toString(),
          filename: file.name,
          status: 'error',
          error: result.error,
        });
      }
    }

    if (invalidEntries.length > 0) {
      setUploads((prev) => [...prev, ...invalidEntries]);
    }

    if (validFiles.length === 0) return;

    setIsUploading(true);

    const formData = new FormData();
    for (const file of validFiles) {
      formData.append('files', file);
    }

    try {
      const response = await axios.post<DocumentUploadResponse[]>(
        '/api/routes/upload',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      const uploadedEntries: UploadedFile[] = response.data.map((item) => ({
        document_id: item.document_id,
        filename: item.filename,
        status: 'processing' as UploadStatus,
      }));

      setUploads((prev) => [...prev, ...uploadedEntries]);

      for (const entry of uploadedEntries) {
        startPolling(entry.document_id);
      }
    } catch (err) {
      const message =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : 'Yükleme başarısız';

      const errorEntries: UploadedFile[] = validFiles.map((file) => ({
        document_id: crypto.randomUUID?.() ?? Date.now().toString(),
        filename: file.name,
        status: 'error' as UploadStatus,
        error: message,
      }));

      setUploads((prev) => [...prev, ...errorEntries]);
    } finally {
      setIsUploading(false);
    }
  }, [startPolling]);

  const removeUpload = useCallback((documentId: string) => {
    stopPolling(documentId);
    setUploads((prev) => prev.filter((u) => u.document_id !== documentId));
  }, [stopPolling]);

  const clearUploads = useCallback(() => {
    pollingIntervalsRef.current.forEach((_, id) => stopPolling(id));
    setUploads([]);
    setIsUploading(false);
  }, [stopPolling]);

  return { uploads, isUploading, uploadFiles, removeUpload, clearUploads };
}
