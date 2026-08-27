import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

const { exportInstrumentHoldings, exportLotHoldings } = vi.hoisted(() => ({
  exportInstrumentHoldings: vi.fn().mockResolvedValue(undefined),
  exportLotHoldings: vi.fn().mockResolvedValue(undefined)
}));

vi.mock("../api/client", () => ({
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
        true_asset_class: "Repo",
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
    }),
    lotHoldings: vi.fn().mockResolvedValue({ snapshot_id: "snapshot-1", view: "lots", items: [{
      id: "lot-1",
      source: { workbook_name: "test.xls", sheet_name: "ОСИП_ПОРТФЕЛЬ", row_number: 5 },
      source_section: "РЕПО",
      security_code: "A_MUM072_0014",
      isin: "KZKD00001210",
      raw_security_type: "РЕПО",
      normalized_asset_class: "Repo",
      issuer: "Министерство финансов Республики Казахстан",
      valuation_method: "",
      instrument_currency: "KZT",
      raw_sector: "Government bonds",
      rating_sp: "",
      rating_moodys: "",
      rating_fitch: "",
      coupon_or_repo_rate: null,
      nominal_value: "1000",
      open_date: null,
      close_date: null,
      quantity: "3",
      purchase_date: "2026-07-15",
      purchase_price: "99.1700",
      purchase_yield: null,
      current_ytm: null,
      purchase_amount_native: "297.51",
      purchase_amount_kzt: "297.51",
      carrying_amount_native: "2910.4567",
      carrying_price_native: "97.0100",
      reserve_kzt: null,
      organizer_fee_kzt: null,
      broker_fee_kzt: null,
      report_fx_rate: "1",
      principal_indexation: "1",
      accrued_income_kzt: null,
      previous_coupon_date: null,
      next_coupon_date: null,
      listing_rating: null,
      derived_carrying_value_kzt: "2910.4567",
      unavailable_fields: []
    }] }),
    provenance: vi.fn().mockResolvedValue({
      snapshot_id: "snapshot-1",
      portfolio: "SOBSTV",
      report_date: "2026-07-15",
      version: 1,
      source_filename: "test.xls",
      metrics: {
        derived_carrying_value_kzt: { code: "derived_carrying_value_kzt", label: "Derived carrying value", basis: "derived", value: "950543693", formula: null, explanation: "", source_refs: [], inputs: [] },
        purchase_amount_kzt: { code: "purchase_amount_kzt", label: "Purchase amount", basis: "source", value: "950408910", formula: null, explanation: "", source_refs: [], inputs: [] }
      }
    }),
    exportInstrumentHoldings,
    exportLotHoldings
  }
}));

vi.mock("../hooks/useSelectedSnapshot", () => ({
  useSelectedSnapshot: () => ({
    search: { portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT" },
    portfolios: { isLoading: false, data: { items: [] } },
    portfolio: { code: "SOBSTV", latest_published_snapshot_id: "snapshot-1" },
    snapshotId: "snapshot-1"
  })
}));

import { LanguageProvider } from "../i18n";
import { HoldingsPage } from "./HoldingsPage";


describe("HoldingsPage", () => {
  it("exports the current instrument view with its active filters", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <HoldingsPage />
        </LanguageProvider>
      </QueryClientProvider>
    );

    const exportButton = await screen.findByRole("button", { name: "Export to Excel" });
    fireEvent.change(screen.getByPlaceholderText("ISIN, ticker, issuer"), {
      target: { value: "MUM072" }
    });
    fireEvent.change(screen.getByLabelText("Asset-class filter"), {
      target: { value: "Repo" }
    });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(exportInstrumentHoldings).toHaveBeenCalledWith("snapshot-1", {
        basis: "derived_carrying",
        term: "MUM072",
        assetClass: "Repo"
      });
    });
  });

  it("exports immutable source lots for the selected published snapshot", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><LanguageProvider><HoldingsPage /></LanguageProvider></QueryClientProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "Export lots" }));
    await waitFor(() => expect(exportLotHoldings).toHaveBeenCalledWith("snapshot-1"));
  });

  it("labels source and derived unit prices separately in the lot detail", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><LanguageProvider><HoldingsPage /></LanguageProvider></QueryClientProvider>);
    fireEvent.click((await screen.findByText("A_MUM072_0014")).closest("tr")!);
    expect(await screen.findByText("Purchase price per unit (source)")).toBeInTheDocument();
    expect(screen.getByText("Current balance price per unit (OSIP source)")).toBeInTheDocument();
    expect(screen.getByText("Price currency")).toBeInTheDocument();
    expect(screen.getByText(/The purchase price is copied from OSIP/)).toBeInTheDocument();
  });
});
