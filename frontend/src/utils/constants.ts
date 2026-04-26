export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const ALLOWED_FILE_TYPES: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/msword': ['.doc'],
  'text/plain': ['.txt'],
};

export const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt'];

export const MAX_FILE_SIZE_MB = 50;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export const UPLOAD_POLL_INTERVAL_MS = 2000;

export const SSE_EVENT_TYPES = {
  TOKEN: 'token',
  CACHE_HIT: 'cache_hit',
  SOURCES: 'sources',
  DONE: 'done',
  ERROR: 'error',
} as const;

export const MESSAGE_ROLES = {
  USER: 'user',
  ASSISTANT: 'assistant',
  SYSTEM: 'system',
} as const;

export const DOC_STATUS = {
  QUEUED: 'queued',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;
