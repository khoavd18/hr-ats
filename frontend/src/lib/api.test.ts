import { describe, expect, it, vi } from "vitest";
import { api, ApiError, getCsrfToken } from "@/lib/api";
import { t } from "@/i18n/vi";

function mockResponse(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(Response.json(body, { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("API client", () => {
  it("reads authorized download bytes while retaining cookie authentication", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response("synthetic-pdf", { headers: { "Content-Type": "application/pdf" } }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const blob = await api<Blob>("/cv-files/synthetic/download", { responseType: "blob" });
    expect(await blob.text()).toBe("synthetic-pdf");
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty("responseType");
  });
  it("uses the configured API base and always includes cookies", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8001/api/v1/");
    const fetchMock = mockResponse({ items: [] });
    expect(await api("/jobs?page=2")).toEqual({ items: [] });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8001/api/v1/jobs?page=2",
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Accept")).toBe("application/json");
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"])(
    "sends the CSRF cookie as a header on %s",
    async (method) => {
      document.cookie = "csrf_token=synthetic%2Bcsrf; path=/";
      const fetchMock = mockResponse({});
      await api("/jobs", { method, body: JSON.stringify({}) });
      const headers = new Headers(fetchMock.mock.calls[0][1].headers);
      expect(headers.get("X-CSRF-Token")).toBe("synthetic+csrf");
      expect(headers.get("Content-Type")).toBe("application/json");
    },
  );

  it.each(["GET", "HEAD", "OPTIONS"])("does not add a CSRF header on %s", async (method) => {
    document.cookie = "csrf_token=synthetic-csrf; path=/";
    const fetchMock = mockResponse({});
    await api("/jobs", { method });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).has("X-CSRF-Token")).toBe(false);
  });

  it("accepts an explicit CSRF token without persisting it", async () => {
    const fetchMock = mockResponse({});
    await api("/jobs", { method: "POST", csrfToken: "synthetic-explicit" });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("X-CSRF-Token")).toBe(
      "synthetic-explicit",
    );
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty("csrfToken");
    expect(document.cookie).not.toContain("synthetic-explicit");
  });

  it("handles malformed cookie encoding without inventing a CSRF value", async () => {
    document.cookie = "csrf_token=%broken; path=/";
    expect(getCsrfToken()).toBeUndefined();
    const fetchMock = mockResponse({});
    await api("/auth/login", { method: "POST" });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).has("X-CSRF-Token")).toBe(false);
  });

  it("refreshes once for concurrent 401s and retries with the rotated CSRF", async () => {
    document.cookie = "csrf_token=synthetic-before; path=/";
    let count = 0;
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith("/auth/refresh")) {
        await new Promise((resolve) => setTimeout(resolve, 10));
        document.cookie = "csrf_token=synthetic-after; path=/";
        return Response.json({});
      }
      count += 1;
      return count <= 2 ? Response.json({}, { status: 401 }) : Response.json({ ok: true });
    });
    vi.stubGlobal("fetch", fetchMock);
    await Promise.all([api("/jobs", { method: "POST" }), api("/jobs", { method: "POST" })]);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(new Headers(fetchMock.mock.calls.at(-1)![1].headers).get("X-CSRF-Token")).toBe(
      "synthetic-after",
    );
  });

  it("reports revoked sessions and never loops refreshing", async () => {
    document.cookie = "csrf_token=synthetic-csrf; path=/";
    const expired = vi.fn();
    window.addEventListener("auth:unauthorized", expired);
    const fetchMock = mockResponse({}, 401);
    await expect(api("/jobs")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener("auth:unauthorized", expired);
  });

  it("preserves custom headers, FormData boundaries and cancellation signals", async () => {
    const fetchMock = mockResponse({});
    const body = new FormData();
    const controller = new AbortController();
    await api("/cv-files", {
      method: "POST",
      body,
      headers: { "X-Test": "synthetic" },
      signal: controller.signal,
    });
    const request = fetchMock.mock.calls[0][1];
    expect(request.body).toBe(body);
    expect(request.signal).toBe(controller.signal);
    expect(new Headers(request.headers).get("X-Test")).toBe("synthetic");
    expect(new Headers(request.headers).has("Content-Type")).toBe(false);
  });

  it.each([204, 205])("handles an empty %s response", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })));
    await expect(api("/jobs", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("maps API errors to local Vietnamese text and discards raw messages", async () => {
    mockResponse(
      { error: { code: "VALIDATION_ERROR", message: "synthetic-internal-message" } },
      422,
    );
    await expect(api("/jobs")).rejects.toMatchObject({
      status: 422,
      code: "VALIDATION_ERROR",
      message: t("api.validation"),
    });
  });

  it.each([
    ["EMAIL_MISSING_INTERVIEW_TIME", 422, "emailTemplates.missing.interview_time"],
    ["EMAIL_MISSING_OFFER_SALARY", 422, "emailTemplates.missing.offer_salary"],
    ["EMAIL_TEMPLATE_INVALID", 422, "emailTemplates.invalid"],
    ["EMAIL_VARIABLE_UNKNOWN", 422, "emailTemplates.unknownVariable"],
    ["INVALID_STAGE_TRANSITION", 409, "pipeline.invalidTransition"],
    ["UNDO_NOT_AVAILABLE", 409, "pipeline.undoUnavailable"],
    ["UNDO_FORBIDDEN", 403, "pipeline.undoForbidden"],
    ["UNDO_EXPIRED", 409, "pipeline.undoExpired"],
  ] as const)("translates pipeline error %s without raw server text", async (code, status, key) => {
    mockResponse({ error: { code, message: "SYNTHETIC_PRIVATE_ERROR" } }, status);
    await expect(api("/applications/fake/move", { method: "POST" })).rejects.toMatchObject({
      status,
      code,
      message: t(key),
    });
  });

  it.each(["UNKNOWN_INTERNAL_CODE", "__proto__", "toString"])(
    "uses the HTTP fallback for unrecognized code %s",
    async (code) => {
      mockResponse({ error: { code, message: "synthetic-internal-message" } }, 403);
      await expect(api("/jobs")).rejects.toMatchObject({
        status: 403,
        code: "HTTP_ERROR",
        message: t("api.forbidden"),
      });
    },
  );

  it("handles non-JSON error bodies without displaying them", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("synthetic-proxy-error", { status: 503 })),
    );
    await expect(api("/jobs")).rejects.toMatchObject({
      status: 503,
      message: t("api.unavailable"),
    });
  });

  it("reports an invalid success response in Vietnamese", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("synthetic-invalid-json")));
    await expect(api("/jobs")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
      message: t("api.invalidResponse"),
    });
  });

  it("reports a network failure without exposing the original error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("synthetic-network-detail")));
    await expect(api("/jobs")).rejects.toMatchObject({
      status: 0,
      code: "NETWORK_ERROR",
      message: t("api.network"),
    });
  });

  it("preserves abort errors so callers can ignore cancelled requests", async () => {
    const abort = new DOMException("synthetic-abort", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    await expect(api("/jobs")).rejects.toBe(abort);
  });

  it.each([
    "https://example.invalid/jobs",
    "//example.invalid/jobs",
    "/\\example.invalid",
    "/jobs#fragment",
    "jobs",
  ])("rejects unsafe or non-relative paths: %s", async (path) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(api(path)).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
