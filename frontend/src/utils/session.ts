export function getSessionId(): string {
  let sessionId = localStorage.getItem('docchat_session_id');
  
  if (!sessionId) {
    sessionId = generateId();
    localStorage.setItem('docchat_session_id', sessionId);
  }
  
  return sessionId;
}

function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxx-xxxx-4xxx-yxxx-xxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export function resetSession(): string {
  localStorage.removeItem('docchat_session_id');
  return getSessionId();
}
