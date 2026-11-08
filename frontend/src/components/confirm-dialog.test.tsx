import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { t } from "@/i18n/vi";

function setup(onConfirm = vi.fn<() => void | Promise<void>>()) {
  const onOpenChange = vi.fn();
  render(
    <ConfirmDialog
      open
      onOpenChange={onOpenChange}
      title={t("common.confirm")}
      description={t("shell.aiNote")}
      onConfirm={onConfirm}
    />,
  );
  return { onConfirm, onOpenChange, user: userEvent.setup() };
}

describe("ConfirmDialog", () => {
  it("explains the action and only confirms after an explicit click", async () => {
    const { onConfirm, onOpenChange, user } = setup();
    expect(screen.getByRole("dialog", { name: t("common.confirm") })).toHaveAccessibleDescription(
      t("shell.aiNote"),
    );
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: t("common.cancel") })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: t("common.cancel") }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("closes only after a successful confirmation", async () => {
    const { onConfirm, onOpenChange, user } = setup();
    await user.click(screen.getByRole("button", { name: t("common.confirm") }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("keeps a failed action open and presents a safe Vietnamese error", async () => {
    const { onOpenChange, user } = setup(
      vi.fn().mockRejectedValue(new Error("synthetic-internal-detail")),
    );
    await user.click(screen.getByRole("button", { name: t("common.confirm") }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t("common.confirmError"));
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("prevents duplicate submits and dismissal while pending", async () => {
    let resolve!: () => void;
    const work = new Promise<void>((done) => {
      resolve = done;
    });
    const { onOpenChange, onConfirm, user } = setup(vi.fn(() => work));
    await user.click(screen.getByRole("button", { name: t("common.confirm") }));
    expect(screen.getByRole("button", { name: t("common.processing") })).toBeDisabled();
    expect(screen.getByRole("button", { name: t("common.cancel") })).toBeDisabled();
    expect(screen.getByRole("button", { name: t("common.close") })).toBeDisabled();
    await user.keyboard("{Escape}");
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(onConfirm).toHaveBeenCalledOnce();
    resolve();
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("returns keyboard focus to the opener when dismissed", async () => {
    function Example() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>{t("common.confirm")}</button>
          <ConfirmDialog
            open={open}
            onOpenChange={setOpen}
            title={t("common.confirm")}
            description={t("shell.aiNote")}
            onConfirm={() => {}}
          />
        </>
      );
    }
    const user = userEvent.setup();
    render(<Example />);
    const opener = screen.getByRole("button", { name: t("common.confirm") });
    await user.click(opener);
    await user.click(screen.getByRole("button", { name: t("common.cancel") }));
    await waitFor(() => expect(opener).toHaveFocus());
  });
});
