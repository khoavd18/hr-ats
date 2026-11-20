import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { HiringUnitsSettings } from "@/components/hiring-units-settings";
import { api } from "@/lib/api";
import { t } from "@/i18n/vi";

const state = vi.hoisted(() => ({ role: "lead" }));
vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({ user: { id: "actor", role: state.role } }),
}));
vi.mock("@/components/users-settings", () => ({ UsersSettings: () => null }));
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));

function show(settings = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {settings ? <SettingsPage /> : <HiringUnitsSettings />}
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  state.role = "lead";
  vi.mocked(api).mockReset().mockResolvedValue({ items: [], total: 0 });
});

it("lets leads manage hiring units and keeps user management hidden", async () => {
  show(true);
  expect(screen.queryByRole("tab", { name: t("users.title") })).not.toBeInTheDocument();
  expect(await screen.findByText(t("units.empty"))).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: t("units.create") }));
  await userEvent.click(screen.getByRole("button", { name: t("common.save") }));
  expect(screen.getByRole("alert")).toHaveTextContent(t("units.required"));
  await userEvent.type(screen.getByLabelText(t("units.name")), "Đơn vị giả mới");
  await userEvent.click(screen.getByRole("button", { name: t("common.save") }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(api).toHaveBeenCalledWith("/hiring-units", expect.objectContaining({ method: "POST" }));
});

it("requires confirmation to deactivate a unit", async () => {
  vi.mocked(api).mockResolvedValue({
    items: [
      {
        id: "unit",
        name: "Đơn vị giả",
        kind: "department",
        contact_name: null,
        contact_email: null,
        notes: null,
        is_active: true,
      },
    ],
    total: 1,
  });
  show();
  await userEvent.click(await screen.findByRole("button", { name: t("units.deactivate") }));
  expect(screen.getByRole("dialog")).toHaveTextContent(t("units.deactivateHint"));
  expect(api).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: t("common.confirm") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/hiring-units/unit", {
      method: "PATCH",
      body: JSON.stringify({ is_active: false }),
    }),
  );
});

it("does not render unit management or fetch contacts for recruiters", () => {
  state.role = "recruiter";
  const view = show();
  expect(view.container).toBeEmptyDOMElement();
  expect(api).not.toHaveBeenCalled();
});
