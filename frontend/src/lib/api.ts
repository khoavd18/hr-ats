import { t, type TranslationKey } from "@/i18n/vi";

const DEFAULT_API_URL = "http://localhost:8000/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

const errorKeys: Record<string, TranslationKey> = {
  VALIDATION_ERROR: "api.validation",
  NOT_FOUND: "api.notFound",
  METHOD_NOT_ALLOWED: "api.unknown",
  INTERNAL_ERROR: "api.unknown",
  SERVICE_UNAVAILABLE: "api.unavailable",
  UNAUTHORIZED: "api.unauthorized",
  FORBIDDEN: "api.forbidden",
  CORS_REJECTED: "api.forbidden",
  CSRF_INVALID: "api.csrf",
  INVALID_CREDENTIALS: "auth.invalidCredentials",
  ACCOUNT_LOCKED: "auth.locked",
  EMAIL_EXISTS: "users.emailExists",
  SELF_LOCKOUT: "users.selfLockout",
  INVALID_HIRING_UNIT: "jobs.unitRequired",
  INVALID_JOB_USER: "api.validation",
  EMBEDDING_UNAVAILABLE: "api.unavailable",
  AI_QUEUE_UNAVAILABLE: "api.unavailable",
  APPLICATION_EXISTS: "bank.alreadyAdded",
  INVALID_MERGE: "api.validation",
  EMBEDDING_FAILED: "api.unavailable",
  INVALID_STAGE_TRANSITION: "pipeline.invalidTransition",
  UNDO_NOT_AVAILABLE: "pipeline.undoUnavailable",
  UNDO_FORBIDDEN: "pipeline.undoForbidden",
  UNDO_EXPIRED: "pipeline.undoExpired",
};

const statusKeys: Record<number, TranslationKey> = {
  401: "api.unauthorized",
  403: "api.forbidden",
  404: "api.notFound",
  409: "api.conflict",
  422: "api.validation",
  429: "api.rateLimit",
  503: "api.unavailable",
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const value = document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith("csrf_token="))
    ?.slice("csrf_token=".length);
  if (!value) return undefined;
  try {
    return decodeURIComponent(value);
  } catch {
    return undefined;
  }
}

export type ApiOptions = Omit<RequestInit, "credentials"> & {
  csrfToken?: string;
  responseType?: "blob";
};

let refreshing: Promise<unknown> | null = null;

export async function api<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  try {
    return await request<T>(path, options);
  } catch (error) {
    const canRefresh = !path.startsWith("/auth/") || path === "/auth/me";
    if (!(error instanceof ApiError) || error.status !== 401 || !canRefresh) throw error;
    if (!getCsrfToken()) {
      if (typeof window !== "undefined") window.dispatchEvent(new Event("auth:unauthorized"));
      throw error;
    }
    try {
      refreshing ??= request("/auth/refresh", { method: "POST" }).finally(() => {
        refreshing = null;
      });
      await refreshing;
    } catch (refreshError) {
      if (
        refreshError instanceof ApiError &&
        refreshError.status === 401 &&
        typeof window !== "undefined"
      ) {
        window.dispatchEvent(new Event("auth:unauthorized"));
      }
      throw refreshError;
    }
    return request<T>(path, options);
  }
}

/** Paths are relative to the API base; authentication stays in HttpOnly cookies. */
async function request<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  // Never send credentials or a CSRF token to a caller-supplied origin.
  if (!path.startsWith("/") || /[\\#\r\n]/.test(path) || path.startsWith("//")) {
    throw new ApiError(0, "INVALID_PATH", t("api.unknown"));
  }

  const { csrfToken, responseType, ...requestOptions } = options;
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!SAFE_METHODS.has(method)) {
    const token = csrfToken ?? getCsrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }

  let response: Response;
  try {
    response = await fetch(
      `${(process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "")}${path}`,
      { ...requestOptions, method, headers, credentials: "include" },
    );
  } catch (error) {
    // Cancellation is control flow; callers must be able to distinguish it from an outage.
    if (
      options.signal?.aborted ||
      (error !== null &&
        typeof error === "object" &&
        "name" in error &&
        error.name === "AbortError")
    ) {
      throw error;
    }
    throw new ApiError(0, "NETWORK_ERROR", t("api.network"));
  }

  if (!response.ok) {
    let code = "HTTP_ERROR";
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && "error" in payload) {
        const detail = payload.error;
        if (
          detail &&
          typeof detail === "object" &&
          "code" in detail &&
          typeof detail.code === "string"
        ) {
          // Only retain recognized machine codes, never raw server messages or personal data.
          if (Object.hasOwn(errorKeys, detail.code)) code = detail.code;
        }
      }
    } catch {
      // Proxies may return HTML rather than the API error envelope.
    }
    throw new ApiError(
      response.status,
      code,
      t(errorKeys[code] ?? statusKeys[response.status] ?? "api.unknown"),
    );
  }

  if (response.status === 204 || response.status === 205 || method === "HEAD") {
    return undefined as T;
  }
  try {
    if (responseType === "blob") return (await response.blob()) as T;
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "INVALID_RESPONSE", t("api.invalidResponse"));
  }
}
