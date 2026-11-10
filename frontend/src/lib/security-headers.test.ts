import { afterEach, expect, it, vi } from "vitest";
import config from "../../next.config";

afterEach(() => vi.unstubAllEnvs());

it("protects every web path and limits production connections to the configured API", async () => {
  vi.stubEnv("NODE_ENV", "production");
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://ats.example.invalid/api/v1");
  const [rule] = await config.headers!();
  const headers = Object.fromEntries(rule.headers.map(({ key, value }) => [key, value]));
  expect(rule.source).toBe("/:path*");
  expect(headers["X-Content-Type-Options"]).toBe("nosniff");
  expect(headers["Referrer-Policy"]).toBe("no-referrer");
  expect(headers["Content-Security-Policy"]).toContain(
    "connect-src 'self' https://ats.example.invalid",
  );
  expect(headers["Content-Security-Policy"]).toContain("object-src 'none'");
  expect(headers["Content-Security-Policy"]).toContain("frame-ancestors 'none'");
  expect(headers["Content-Security-Policy"]).toContain("frame-src 'self' blob:");
  expect(headers["Content-Security-Policy"]).not.toMatch(/unsafe-eval|ws:|localhost|\*/);
});

it("allows the Next development runtime only in development", async () => {
  vi.stubEnv("NODE_ENV", "development");
  const [rule] = await config.headers!();
  expect(rule.headers.find((header) => header.key === "Content-Security-Policy")?.value).toContain(
    "'unsafe-eval'",
  );
});
