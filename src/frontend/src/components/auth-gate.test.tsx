import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthGate } from "@/components/auth-gate";
import { AppShell } from "@/components/app-shell";
import { t } from "@/i18n/vi";

const state = vi.hoisted(() => ({
  path: "/jobs",
  replace: vi.fn(),
  auth: {
    user: null as { full_name: string; role: string } | null,
    loading: false,
    error: null as string | null,
    reload: vi.fn(),
    logout: vi.fn(),
  },
}));
vi.mock("next/navigation", () => ({
  usePathname: () => state.path,
  useRouter: () => ({ replace: state.replace }),
}));
vi.mock("@/components/auth-provider", () => ({ useAuth: () => state.auth }));

beforeEach(() => {
  state.path = "/jobs";
  state.auth.user = null;
  state.auth.loading = false;
  state.auth.error = null;
  state.replace.mockClear();
});

it("redirects unauthenticated users without rendering protected content", () => {
  render(
    <AuthGate>
      <div>protected sentinel</div>
    </AuthGate>,
  );
  expect(state.replace).toHaveBeenCalledWith("/login");
  expect(screen.queryByText("protected sentinel")).not.toBeInTheDocument();
});

it("shows retry on connection failure without rendering protected content", () => {
  state.auth.error = t("api.network");
  render(
    <AuthGate>
      <div>protected sentinel</div>
    </AuthGate>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent(t("api.network"));
  expect(state.replace).not.toHaveBeenCalled();
  expect(screen.queryByText("protected sentinel")).not.toBeInTheDocument();
});

it("hides settings from recruiters and shows account name", () => {
  state.auth.user = { full_name: "Tài khoản giả", role: "recruiter" };
  render(
    <AppShell>
      <div />
    </AppShell>,
  );
  expect(screen.queryByRole("link", { name: t("nav.settings") })).not.toBeInTheDocument();
  expect(screen.getByLabelText(t("shell.account"))).toHaveTextContent("Tài khoản giả");
});

it("rejects a recruiter opening the settings URL directly", () => {
  state.path = "/settings";
  state.auth.user = { full_name: "Tài khoản giả", role: "recruiter" };
  render(
    <AuthGate>
      <div>protected sentinel</div>
    </AuthGate>,
  );
  expect(state.replace).toHaveBeenCalledWith("/");
  expect(screen.queryByText("protected sentinel")).not.toBeInTheDocument();
});

it.each(["admin", "lead"])("shows settings to %s", (role) => {
  state.auth.user = { full_name: "Tài khoản giả", role };
  render(
    <AppShell>
      <div />
    </AppShell>,
  );
  expect(screen.getByRole("link", { name: t("nav.settings") })).toBeVisible();
});
