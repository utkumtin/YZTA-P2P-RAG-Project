import { ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES } from './constants';

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

export function validateFile(file: File): ValidationResult {
  const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
  
  if (!ALLOWED_EXTENSIONS.includes(fileExtension)) {
    return {
      valid: false,
      error: `Desteklenmeyen dosya türü: ${fileExtension}. Desteklenen türler: ${ALLOWED_EXTENSIONS.join(', ')}`,
    };
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      valid: false,
      error: `Dosya boyutu çok büyük. Maksimum ${MAX_FILE_SIZE_BYTES / (1024 * 1024)}MB yükleyebilirsiniz.`,
    };
  }

  return { valid: true };
}
