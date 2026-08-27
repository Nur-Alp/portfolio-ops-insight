import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../../i18n";
import { Drawer } from "./Drawer";

function renderDrawer(onClose = vi.fn()) {
  const trigger = document.createElement("button");
  trigger.textContent = "Open details";
  document.body.append(trigger);
  trigger.focus();
  const view = render(
    <LanguageProvider>
      <Drawer open title="Details" onClose={onClose}>
        <button type="button">First action</button>
        <button type="button">Last action</button>
      </Drawer>
    </LanguageProvider>
  );
  return { ...view, onClose, trigger };
}

describe("Drawer", () => {
  it("moves focus into the dialog, traps Tab, and restores the trigger on close", () => {
    const { onClose, trigger, unmount } = renderDrawer();
    const close = screen.getByRole("button", { name: "Close details" });
    const first = screen.getByRole("button", { name: "First action" });
    const last = screen.getByRole("button", { name: "Last action" });
    expect(close).toHaveFocus();

    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(close).toHaveFocus();

    close.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
    expect(first).not.toBeInTheDocument();
  });
});
