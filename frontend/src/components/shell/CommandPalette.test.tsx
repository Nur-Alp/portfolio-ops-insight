import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => cleanup());

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigateMock
}));

vi.mock("../../api/client", () => ({
  dashboardApi: {
    instrumentHoldings: vi.fn().mockResolvedValue({
      snapshot_id: "snapshot-1",
      view: "instruments",
      value_basis: "derived_carrying_value_kzt",
      items: [{
        isin: "KZKD00001210",
        security_code: "A_MUM072_0014",
        issuer: "Министерство финансов Республики Казахстан",
        raw_security_type: "РЕПО",
        normalized_asset_class: "Repo",
        instrument_currency: "KZT",
        raw_sector: "Government bonds",
        lot_count: 2,
        quantity: "896800",
        purchase_amount_native: "950408910",
        purchase_amount_kzt: "950408910",
        derived_carrying_value_kzt: "950543693",
        source_refs: [],
        derived_weight_percent: "19.9",
        purchase_weight_percent: "19.9"
      }]
    })
  }
}));

vi.mock("../../hooks/useSelectedSnapshot", () => ({
  useSelectedSnapshot: () => ({
    search: { portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT" },
    snapshotId: "snapshot-1"
  })
}));

import { LanguageProvider } from "../../i18n";
import type { DomainScope } from "../../auth/session";
import { CommandPalette } from "./CommandPalette";

function renderPalette(
  open: boolean,
  onClose = vi.fn(),
  domainScope: DomainScope = "*",
  actorDomains: readonly string[] = ["*"]
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <CommandPalette
          open={open}
          onClose={onClose}
          domainScope={domainScope}
          actorDomains={actorDomains}
        />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

describe("CommandPalette", () => {
  it("renders nothing when closed", () => {
    renderPalette(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("lists navigation destinations when opened", async () => {
    renderPalette(true);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Holdings")).toBeInTheDocument();
    expect(screen.getByText("OSIP operational export")).toBeInTheDocument();
    expect(screen.queryByText("My work")).not.toBeInTheDocument();
  });

  it("limits navigation destinations to the active accounting domain", async () => {
    renderPalette(true, vi.fn(), "accounting", ["accounting"]);

    expect(await screen.findByText("Accounting")).toBeInTheDocument();
    expect(screen.getByText("Operations and reconciliations")).toBeInTheDocument();
    expect(screen.queryByText("My work")).not.toBeInTheDocument();
    expect(screen.queryByText("Holdings")).not.toBeInTheDocument();
    expect(screen.queryByText("Brokerage")).not.toBeInTheDocument();
    expect(screen.queryByText("Corporate finance")).not.toBeInTheDocument();
    expect(screen.queryByText("Risk & limits — source pending")).not.toBeInTheDocument();
  });

  it("finds a matching instrument by ISIN and navigates to holdings with the term set", async () => {
    const onClose = vi.fn();
    renderPalette(true, onClose);
    const input = screen.getByPlaceholderText("Page, portfolio instrument, ISIN, issuer…");
    fireEvent.change(input, { target: { value: "KZKD00001210" } });

    await waitFor(() => {
      expect(screen.getByText("A_MUM072_0014")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("A_MUM072_0014"));

    expect(navigateMock).toHaveBeenCalledWith({
      to: "/holdings",
      search: { portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT", term: "KZKD00001210" }
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("shows no-results text for an unmatched query", async () => {
    renderPalette(true);
    fireEvent.change(screen.getByPlaceholderText("Page, portfolio instrument, ISIN, issuer…"), {
      target: { value: "does-not-exist" }
    });
    await waitFor(() => expect(screen.getByText("No results")).toBeInTheDocument());
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    renderPalette(true, onClose);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
