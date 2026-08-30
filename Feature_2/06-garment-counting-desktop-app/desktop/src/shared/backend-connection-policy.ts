const RETRYABLE_CONNECTION_CODES = new Set([
  "ECONNRESET",
  "ECONNREFUSED",
  "EPIPE",
  "UND_ERR_SOCKET",
  "UND_ERR_CONNECT_TIMEOUT",
]);

export function backendConnectionErrorCode(error: unknown): string | null {
  if (!error || typeof error !== "object") return null;

  const candidate = error as { code?: unknown; cause?: unknown };
  if (typeof candidate.code === "string") return candidate.code;
  if (candidate.cause && candidate.cause !== error) {
    return backendConnectionErrorCode(candidate.cause);
  }

  return null;
}

export function shouldRetryBackendConnection(
  method: string,
  attempt: number,
  error: unknown,
): boolean {
  if (method !== "GET" || attempt >= 2) return false;
  const code = backendConnectionErrorCode(error);
  return code !== null && RETRYABLE_CONNECTION_CODES.has(code);
}
