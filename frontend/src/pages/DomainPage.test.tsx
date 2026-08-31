import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  assetManagement: vi.fn(),
  treasury: vi.fn(),
  brokerage: vi.fn(),
  clients: vi.fn(),
  clientDetail: vi.fn(),
  corporateFinance: vi.fn(),
  accountingReadiness: vi.fn(),
  risk: vi.fn(),
  sourcePreview: vi.fn().mockResolvedValue({
    workbook_name: "risk-limits.xls",
    original_filename: "risk-limits.xls",
    sheet_name: "Limits",
    target_cell: "C5",
    target_row: 5,
    target_column: 3,
    target_value: "Kazakhstan",
    columns: ["A", "B", "C"],
    rows: [{ row_number: 5, values: ["SOBSTV", "country", "Kazakhstan"] }]
  }),
  datasetVersions: vi.fn().mockResolvedValue({ items: [] }),
  operationsReadiness: vi.fn().mockResolvedValue({ datasets: [], reconciliations: [], readiness: [] }),
  exportFundData: vi.fn(),
  exportBrokerageData: vi.fn(),
  exportCorporateFinanceData: vi.fn().mockResolvedValue(undefined),
  exportRiskData: vi.fn().mockResolvedValue(undefined),
  exportAccountingData: vi.fn().mockResolvedValue(undefined)
}));

vi.mock("../api/client", () => ({ dashboardApi: api }));

import { renderWithProviders } from "../test/render";
import { ProvenanceProvider } from "../components/ui/ProvenanceContext";
import { DomainPage } from "./DomainPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("multi-source domain pages", () => {
  it("opens the client card and requests the selected client detail", async () => {
    api.clients.mockResolvedValue({
      available: true,
      disclosure: "Client source",
      report_date_mismatch: false,
      report_dates: ["2026-07-20"],
      sources: [],
      summaries: { client_account_snapshot: { client_count: 1, position_count: 0, cash_kzt: "100", total_assets_kzt: "500" } },
      records: {
        client_account_snapshot: [{ id: "client-1", record_type: "client", client_name: "Тестовый клиент", account: "ACC-1", iin: "123" }],
        client_dashboard_snapshot: [{ id: "summary-1", record_type: "client_summary", client_name: "Тестовый клиент", manager: "Менеджер 1" }]
      },
      pinned_dataset_types: []
    });
    api.clientDetail.mockResolvedValue({
      records: { client_account_snapshot: [{ id: "client-1", record_type: "client", client_name: "Тестовый клиент", account: "ACC-1", iin: "123" }] }
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="clients" /></ProvenanceProvider>);

    fireEvent.click(await screen.findByRole("button", { name: "Open" }));
    expect(api.clientDetail).toHaveBeenCalledWith("client-1");
    expect((await screen.findAllByText("Менеджер 1")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Client detail")).toBeInTheDocument();
    expect((await screen.findAllByText("Тестовый клиент")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Dataset")).not.toBeInTheDocument();
  });

  it("opens the source-cell drawer when a source-backed row is clicked", async () => {
    api.risk.mockResolvedValue({
      available: true,
      disclosure: "Risk source",
      report_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [],
      summaries: {
        risk_limits_sobstv: { limit_count: 1, breach_count: 0 },
        risk_limits_tabys: { limit_count: 0, breach_count: 0 }
      },
      records: {
        risk_limits_sobstv: [{
          id: "source-row-1", portfolio_code: "SOBSTV", dimension: "country", label: "Clickable row",
          signal: "ok", limit_pct: "0.5", actual_pct: "0.2", source: {
            filename: "risk-limits.xls", sheet_name: "Limits", source_cell: "C5", row_number: 5
          }
        }],
        risk_limits_tabys: []
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="risk" /></ProvenanceProvider>);
    fireEvent.click((await screen.findAllByText("Clickable row"))[0]);

    expect(await screen.findByText("Source cell preview")).toBeInTheDocument();
    expect(api.sourcePreview).toHaveBeenCalledWith("source-row-1", "C5");
  });

  it("opens a source-backed main-table row from the keyboard", async () => {
    api.risk.mockResolvedValue({
      available: true, disclosure: "Risk source", report_date_mismatch: false, report_dates: ["2026-07-01"], sources: [],
      summaries: { risk_limits_sobstv: { limit_count: 1, breach_count: 0 }, risk_limits_tabys: { limit_count: 0, breach_count: 0 } },
      records: { risk_limits_sobstv: [{
        id: "keyboard-source-row", portfolio_code: "SOBSTV", dimension: "country", label: "Keyboard row", signal: "ok",
        source: { filename: "risk-limits.xls", sheet_name: "Limits", source_cell: "C6", row_number: 6 }
      }], risk_limits_tabys: [] },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="risk" /></ProvenanceProvider>);
    const row = (await screen.findByText("Keyboard row")).closest("tr")!;
    expect(row).toHaveAttribute("data-source-row");
    row.focus();
    fireEvent.keyDown(row, { key: "Enter" });
    expect(await screen.findByText("Source cell preview")).toBeInTheDocument();
    expect(api.sourcePreview).toHaveBeenCalledWith("keyboard-source-row", "C6");
  });

  it("renders published risk limits and flags breaches for both portfolios", async () => {
    api.risk.mockResolvedValue({
      available: true,
      disclosure: "Investment limits for SOBSTV and TABYS from independently published sources.",
      report_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [{
        dataset_id: "dataset-sobstv",
        dataset_type: "risk_limits_sobstv",
        scope_code: "SOBSTV",
        source_filename: "sobstv-limits.xls",
        source_report_date: "2026-07-01",
        business_date: "2026-07-01",
        publication_status: "published",
        version: 1
      }],
      summaries: {
        risk_limits_sobstv: { limit_count: 1, breach_count: 1 },
        risk_limits_tabys: { limit_count: 1, breach_count: 0 }
      },
      records: {
        risk_limits_sobstv: [{ id: "r1", portfolio_code: "SOBSTV", dimension: "country", label: "Kazakhstan", limit_pct: "0.5", limit_kzt: "1000", actual_pct: "0.6", actual_kzt: "1200", free_limit_kzt: "-200", signal: "breach" }],
        risk_limits_tabys: [{ id: "r2", portfolio_code: "TABYS", dimension: "issuer", label: "Sample Bank", limit_pct: "0.2", limit_kzt: "500", actual_pct: "0.1", actual_kzt: "300", free_limit_kzt: "200", signal: "ok" }]
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="risk" /></ProvenanceProvider>);

    // "Kazakhstan" breaches its limit, so it appears both in the main table
    // and in the watchlist panel above it.
    expect((await screen.findAllByText("Kazakhstan")).length).toBeGreaterThan(0);
    expect(screen.getByText("Sample Bank")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Limit lines: source" }));
    expect(await screen.findByText("Metric provenance")).toBeInTheDocument();
  });

  it("watchlist trusts the backend's near_breach classification rather than re-deriving it", async () => {
    // near_breach/utilization/near_breach_threshold are computed once by
    // _risk_near_breach/_risk_utilization in ingestion/multi_source.py and
    // sent as-is; the frontend must not recompute (and risk silently
    // diverging from) that classification. This fixture includes an "OK"
    // issuer row whose actual/limit ratio is well over 1 (e.g. a
    // supranational issuer the source explicitly exempts) with
    // near_breach: false, exactly as the backend would send it, to confirm
    // the UI displays the backend's answer rather than deriving its own.
    api.risk.mockResolvedValue({
      available: true,
      disclosure: "",
      report_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [],
      summaries: {
        risk_limits_sobstv: { limit_count: 2, breach_count: 0 },
        risk_limits_tabys: { limit_count: 0, breach_count: 0 }
      },
      records: {
        risk_limits_sobstv: [
          { id: "near-miss", portfolio_code: "SOBSTV", dimension: "instrument_category", label: "Genuine near-miss", limit_pct: "0.5", actual_pct: "0.48", signal: "ok", utilization: "0.96", near_breach: true, near_breach_threshold: "0.9" },
          { id: "exempt", portfolio_code: "SOBSTV", dimension: "issuer", label: "Exempted supranational issuer", limit_kzt: "1000", actual_kzt: "3800", signal: "ok", utilization: "3.8", near_breach: false, near_breach_threshold: "0.9" }
        ],
        risk_limits_tabys: []
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="risk" /></ProvenanceProvider>);
    // The exempted row still appears in the main table (it's a real,
    // published control line) - only the watchlist panel must exclude it.
    expect((await screen.findAllByText("Exempted supranational issuer")).length).toBe(1);
    const watchlistPanel = screen.getByText("Watchlist: breaches and near-breaches").closest("section");
    expect(watchlistPanel).not.toBeNull();
    expect(within(watchlistPanel as HTMLElement).getByText("Genuine near-miss")).toBeInTheDocument();
    expect(within(watchlistPanel as HTMLElement).queryByText("Exempted supranational issuer")).not.toBeInTheDocument();
  });

  it("scopes each risk KPI card's evidence to the records that make up its own count", async () => {
    api.risk.mockResolvedValue({
      available: true,
      disclosure: "Investment limits for SOBSTV and TABYS from independently published sources.",
      report_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [{
        dataset_id: "dataset-sobstv",
        dataset_type: "risk_limits_sobstv",
        scope_code: "SOBSTV",
        source_filename: "sobstv-limits.xls",
        source_report_date: "2026-07-01",
        business_date: "2026-07-01",
        publication_status: "published",
        version: 1
      }],
      summaries: {
        risk_limits_sobstv: { limit_count: 2, breach_count: 1, unknown_count: 0, not_applicable_count: 0, duration_count: 1 },
        risk_limits_tabys: { limit_count: 0, breach_count: 0, unknown_count: 0, not_applicable_count: 0, duration_count: 0 }
      },
      records: {
        risk_limits_sobstv: [
          {
            id: "breach-1", portfolio_code: "SOBSTV", dimension: "country", label: "Kazakhstan", signal: "breach",
            source: {
              sheet_name: "Лимит по странам", row_number: 5, filename: "sobstv-limits.xls", source_cell: "C5",
              field_columns: { actual_usd: { source_cell: "K5", source_column: 11, source_column_letter: "K" } }
            }
          },
          { id: "duration-1", portfolio_code: "SOBSTV", dimension: "duration", label: "Some Issuer", signal: "ok", source: { sheet_name: "Лимит по дюрации", row_number: 20, filename: "sobstv-limits.xls", source_cell: "N20" } }
        ],
        risk_limits_tabys: []
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="risk" /></ProvenanceProvider>);
    // "Kazakhstan" breaches its limit, so it appears both in the main table
    // and in the watchlist panel above it.
    expect((await screen.findAllByText("Kazakhstan")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Breaches: source" }));
    const breachDialog = await screen.findByRole("dialog");
    expect(await within(breachDialog).findByText("Metric provenance")).toBeInTheDocument();
    expect(within(breachDialog).getAllByText(/Лимит по странам/).length).toBeGreaterThan(0);
    expect(within(breachDialog).queryAllByText(/Лимит по дюрации/).length).toBe(0);
    // The card's evidence should point at the cell that actually breached
    // (actual_usd, from field_columns) rather than the record's label cell.
    expect(within(breachDialog).getByText(/cell K5/)).toBeInTheDocument();
    expect(within(breachDialog).queryByText(/cell C5/)).not.toBeInTheDocument();
    expect(within(breachDialog).getByText(/actual amount \(USD\)/)).toBeInTheDocument();
    fireEvent.click(within(breachDialog).getByRole("button", { name: "Close details" }));

    fireEvent.click(screen.getByRole("button", { name: "Duration controls: source" }));
    const durationDialog = await screen.findByRole("dialog");
    expect(await within(durationDialog).findByText("Metric provenance")).toBeInTheDocument();
    expect(within(durationDialog).getAllByText(/Лимит по дюрации/).length).toBeGreaterThan(0);
    expect(within(durationDialog).queryAllByText(/Лимит по странам/).length).toBe(0);
  });

  it("uses a 10-row page size for risk tables", async () => {
    api.risk.mockResolvedValue({
      available: true,
      disclosure: "Risk source",
      report_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [{ dataset_id: "dataset-sobstv", dataset_type: "risk_limits_sobstv", scope_code: "SOBSTV", source_filename: "sobstv-limits.xls", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1 }],
      summaries: { risk_limits_sobstv: { limit_count: 11, breach_count: 0 }, risk_limits_tabys: { limit_count: 0, breach_count: 0 } },
      records: { risk_limits_sobstv: Array.from({ length: 11 }, (_, index) => ({ id: `risk-${index + 1}`, portfolio_code: "SOBSTV", dimension: "country", label: `Risk row ${index + 1}`, signal: "ok" })), risk_limits_tabys: [] },
      pinned_dataset_types: []
    });

    await renderWithProviders(<DomainPage kind="risk" />);

    expect(await screen.findByText("Page 1 of 2 · 10 rows per page")).toBeInTheDocument();
    expect(screen.getByText("Risk row 1")).toBeInTheDocument();
    expect(screen.queryByText("Risk row 11")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Risk row 11")).toBeInTheDocument();
  });

  it("does not present freshness status as a user-action warning", async () => {
    api.brokerage.mockResolvedValue({
      available: true,
      disclosure: "Brokerage trade ledger from an independently published source.",
      report_date_mismatch: false,
      report_dates: ["2026-07-10", "2026-07-20"],
      sources: [
        { dataset_id: "d1", dataset_type: "brokerage_trade_ledger", scope_code: "BROKERAGE", source_filename: "a.xlsx", source_report_date: "2026-07-10", business_date: "2026-07-10", publication_status: "published", version: 1, freshness: "stale" },
        { dataset_id: "d2", dataset_type: "client_account_snapshot", scope_code: "BROKERAGE", source_filename: "a.xlsx", source_report_date: "2026-07-20", business_date: "2026-07-20", publication_status: "published", version: 1, freshness: "aging" },
        { dataset_id: "d3", dataset_type: "client_maturity_calendar", scope_code: "BROKERAGE", source_filename: "a.xlsx", source_report_date: "2026-07-20", business_date: "2026-07-20", publication_status: "published", version: 1, freshness: "aging" },
        { dataset_id: "d4", dataset_type: "client_dashboard_snapshot", scope_code: "BROKERAGE", source_filename: "a.xlsx", source_report_date: "2026-07-20", business_date: "2026-07-20", publication_status: "published", version: 1, freshness: "aging" }
      ],
      summaries: { brokerage_trade_ledger: { trade_count: 0 }, client_account_snapshot: {}, derivatives_register: {} },
      records: { brokerage_trade_ledger: [], client_account_snapshot: [], derivatives_register: [] },
      pinned_dataset_types: []
    });

    await renderWithProviders(<DomainPage kind="brokerage" />);
    expect(screen.queryByText("Source data is stale")).not.toBeInTheDocument();
  });

  it("aggregates a large brokerage trade set into a summary plus a clickable sample instead of one row per trade", async () => {
    const kztTrades = Array.from({ length: 15 }, (_, index) => ({
      id: `kzt-${index + 1}`,
      trade_number: `T-${index + 1}`,
      client_name: "Client A",
      currency: "KZT",
      amount: "100000",
      source: {
        sheet_name: "Лист8", row_number: 10 + index, filename: "brokerage.xlsx", source_cell: `C${10 + index}`,
        field_columns: { amount: { source_cell: `L${10 + index}`, source_column: 12, source_column_letter: "L" } }
      }
    }));
    const usdTrades = Array.from({ length: 3 }, (_, index) => ({
      id: `usd-${index + 1}`,
      trade_number: `U-${index + 1}`,
      client_name: "Client B",
      currency: "USD",
      amount: "500",
      source: { sheet_name: "Лист8", row_number: 30 + index, filename: "brokerage.xlsx", source_cell: `C${30 + index}` }
    }));
    api.brokerage.mockResolvedValue({
      available: true,
      disclosure: "Brokerage trade ledger from an independently published source.",
      report_date_mismatch: false,
      report_dates: ["2026-07-20"],
      sources: [{
        dataset_id: "dataset-brokerage", dataset_type: "brokerage_trade_ledger", scope_code: "BROKERAGE",
        source_filename: "brokerage.xlsx", source_report_date: "2026-07-20", business_date: "2026-07-20",
        publication_status: "published", version: 1
      }],
      summaries: { brokerage_trade_ledger: { trade_count: 18 }, client_account_snapshot: {}, derivatives_register: {} },
      records: { brokerage_trade_ledger: [...kztTrades, ...usdTrades], client_account_snapshot: [], derivatives_register: [] },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="brokerage" /></ProvenanceProvider>);
    expect((await screen.findAllByText("Client A")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "KZT-equivalent turnover: derived" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Metric provenance")).toBeInTheDocument();
    // 15 KZT rows exceed the grouping threshold, so the drawer must show one
    // summary line (with the total count) plus a small clickable sample -
    // never all 15 individual "row" entries.
    expect(within(dialog).getByText(/15 rows/)).toBeInTheDocument();
    expect(within(dialog).queryByText(/USD/)).not.toBeInTheDocument();
    const openButtons = within(dialog).getAllByRole("button", { name: /Open cell/ });
    expect(openButtons.length).toBeGreaterThan(0);
    expect(openButtons.length).toBeLessThan(15);

    // The summary line itself must not be a dead end - expanding it reveals
    // every remaining row as its own clickable entry.
    fireEvent.click(within(dialog).getByRole("button", { name: /Show 9 more rows/ }));
    const expandedButtons = within(dialog).getAllByRole("button", { name: /Open cell/ });
    expect(expandedButtons.length).toBe(15);
    fireEvent.click(within(dialog).getByRole("button", { name: /Collapse rows/ }));
    expect(within(dialog).getAllByRole("button", { name: /Open cell/ }).length).toBeLessThan(15);
  });

  it("converts non-KZT brokerage trades to KZT-equivalent turnover using the summary's FX rates", async () => {
    api.brokerage.mockResolvedValue({
      available: true,
      disclosure: "Brokerage trade ledger from an independently published source.",
      report_date_mismatch: false,
      report_dates: ["2026-07-20"],
      sources: [{
        dataset_id: "dataset-brokerage", dataset_type: "brokerage_trade_ledger", scope_code: "BROKERAGE",
        source_filename: "brokerage.xlsx", source_report_date: "2026-07-20", business_date: "2026-07-20",
        publication_status: "published", version: 1
      }],
      summaries: {
        brokerage_trade_ledger: { trade_count: 2, fx_rates_kzt: { USD: "450" }, fx_rate_date: "2026-07-20" },
        client_account_snapshot: {}, derivatives_register: {}
      },
      records: {
        brokerage_trade_ledger: [
          { id: "kzt-1", trade_number: "T-1", client_name: "Client A", currency: "KZT", amount: "100000" },
          { id: "usd-1", trade_number: "U-1", client_name: "Client B", currency: "USD", amount: "500" }
        ],
        client_account_snapshot: [], derivatives_register: []
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<DomainPage kind="brokerage" />);
    // 100 000 KZT + (500 USD * 450) = 325 000 KZT, not 100 000 KZT (the old
    // KZT-only sum) - matches the Excel export's own amount * fx.rate formula.
    expect(await screen.findByText("325,000 ₸")).toBeInTheDocument();
  });

  it("shows source-date mismatches and exports published corporate-finance data", async () => {
    api.corporateFinance.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: true,
      filename_date_mismatch: true,
      report_dates: ["2026-06-30", "2026-07-01"],
      sources: [{
        dataset_id: "dataset-1",
        dataset_type: "corporate_finance_register",
        scope_code: "CORPFIN",
        source_filename: "sanitized-corporate-finance.xlsx",
        source_report_date: "2026-07-01",
        business_date: "2026-07-01",
        publication_status: "published",
        version: 1
      }],
      summaries: { corporate_finance_register: { deal_count: 1, active_count: 1, period: "H1 2026" } },
      records: { corporate_finance_register: [{ issuer: "Demo Issuer", subject: "Bond placement", placement_amount: "1000", satisfied_demand: "750", placement_raw: "1 000 KZT", duration_raw: "active" }] },
      pinned_dataset_types: []
    });

    await renderWithProviders(<DomainPage kind="corporate-finance" />);

    expect(await screen.findByText("Source dates do not match")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next warning" }));
    expect(screen.getByText("Filename date differs from workbook date")).toBeInTheDocument();
    expect(screen.getByText("Demo Issuer")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Placement and satisfied demand/i })).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search rows"), { target: { value: "Demo Issuer" } });
    fireEvent.click(screen.getByRole("button", { name: "Export to Excel" }));
    await waitFor(() => expect(api.exportCorporateFinanceData).toHaveBeenCalledWith("Demo Issuer"));
  });

  it("narrows the corporate-finance KPI cards to the active search term, not just the table below them", async () => {
    api.corporateFinance.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [{
        dataset_id: "dataset-1", dataset_type: "corporate_finance_register", scope_code: "CORPFIN",
        source_filename: "sanitized-corporate-finance.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01",
        publication_status: "published", version: 1
      }],
      // Deliberately stale/unfiltered - the ingestion-time aggregate must
      // never be trusted once a search term is active; the cards need to
      // recompute from the filtered records instead.
      summaries: { corporate_finance_register: { deal_count: 99, active_count: 99, period: "H1 2026" } },
      records: {
        corporate_finance_register: [
          { id: "deal-1", issuer: "Demo Issuer", subject: "Bond placement", active: true },
          { id: "deal-2", issuer: "Other Issuer", subject: "Loan facility", active: true }
        ]
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<DomainPage kind="corporate-finance" />);

    const dealsCard = (await screen.findByText("Deals/mandates")).closest(".kpi-card") as HTMLElement;
    expect(within(dealsCard).getByText("2")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Search rows"), { target: { value: "Demo Issuer" } });
    expect(within(dealsCard).getByText("1")).toBeInTheDocument();
  });

  it("scopes a corporate-finance chart's evidence to only the issuers plotted on it, not every currency's rows", async () => {
    api.corporateFinance.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [{
        dataset_id: "dataset-1", dataset_type: "corporate_finance_register", scope_code: "CORPFIN",
        source_filename: "sanitized-corporate-finance.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01",
        publication_status: "published", version: 1
      }],
      summaries: { corporate_finance_register: { deal_count: 4, active_count: 4, period: "H1 2026" } },
      records: {
        corporate_finance_register: [
          {
            id: "deal-usd-1", issuer: "USD Issuer One", subject: "Bond placement", active: true,
            placement_currency: "USD", placement_amount: "1000000", demand_currency: "USD", satisfied_demand: "1200000",
            source: { sheet_name: "Дашборд", row_number: 5, filename: "Направление_Корпфин.xlsx", source_cell: "B5" }
          },
          {
            id: "deal-usd-2", issuer: "USD Issuer Two", subject: "Bond placement", active: true,
            placement_currency: "USD", placement_amount: "800000", demand_currency: "USD", satisfied_demand: "900000",
            source: { sheet_name: "Дашборд", row_number: 6, filename: "Направление_Корпфин.xlsx", source_cell: "B6" }
          },
          {
            id: "deal-kzt-1", issuer: "KZT Issuer One", subject: "Loan facility", active: true,
            placement_currency: "KZT", placement_amount: "500000000", demand_currency: "KZT", satisfied_demand: "600000000",
            source: { sheet_name: "Дашборд", row_number: 9, filename: "Направление_Корпфин.xlsx", source_cell: "B9" }
          },
          {
            id: "deal-kzt-2", issuer: "KZT Issuer Two", subject: "Loan facility", active: true,
            placement_currency: "KZT", placement_amount: "400000000", demand_currency: "KZT", satisfied_demand: "450000000",
            source: { sheet_name: "Дашборд", row_number: 10, filename: "Направление_Корпфин.xlsx", source_cell: "B10" }
          }
        ]
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="corporate-finance" /></ProvenanceProvider>);

    const usdChart = (await screen.findByText("Placement and satisfied demand · USD")).closest("article") as HTMLElement;
    fireEvent.click(within(usdChart).getByRole("button", { name: "Source" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/cell B5/)).toBeInTheDocument();
    expect(within(dialog).getByText(/cell B6/)).toBeInTheDocument();
    expect(within(dialog).queryByText(/cell B9/)).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/cell B10/)).not.toBeInTheDocument();
  });

  it("renders the accounting cockpit with KPI cards, the income statement table, and a reconciliation warning", async () => {
    api.accountingReadiness.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [
        { dataset_id: "bs-1", dataset_type: "accounting_balance_sheet", scope_code: "ACCOUNTING", source_filename: "fo.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1, dq_blocker_count: 1 },
        { dataset_id: "is-1", dataset_type: "accounting_income_statement", scope_code: "ACCOUNTING", source_filename: "fo.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1, dq_blocker_count: 0 }
      ],
      summaries: {
        accounting_balance_sheet: { total_assets_kzt: "4200000", total_liabilities_kzt: "200000", total_equity_kzt: "4000000" },
        accounting_income_statement: { total_income_kzt: "287651", total_expenses_kzt: "184920", net_profit_kzt: "102731" },
        accounting_portfolio_detail: { total_carrying_value_kzt: "55200000" },
        accounting_landing: { formula_audit: { format: "xls", formula_status: "formula_records_detected" }, consumed_formula_audit: { status: "not_inspectable" } },
        accounting_budget: { formula_audit: { format: "xlsx", formula_status: "source_errors", error_value_count: 1, formula_error_count: 0, blank_cached_formula_count: 0 }, consumed_formula_audit: { status: "passed", checked_formula_cells: 0 } }
      },
      records: {
        accounting_balance_sheet: [{ id: "bs-row-1", line_code: "25", line_label: "Итого активы", section: "Активы", current_period_kzt: "4200000", prior_period_kzt: "4000000" }],
        accounting_income_statement: [{ id: "is-row-1", line_code: "13", line_label: "Итого доходов", quarter_kzt: "287651", ytd_kzt: "695279" }],
        accounting_budget: [{ id: "budget-row-1", section: "income_statement", line_label: "Процентные доходы", forecast_2025_kzt: "627384" }],
        accounting_portfolio_detail: [{ id: "portfolio-row-1", category: "Корпоративные облигации", issuer: "Test Issuer", isin: "US0000000001", carrying_value_kzt: "46000000" }]
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<DomainPage kind="accounting" />);

    expect(await screen.findByText("Statements do not reconcile")).toBeInTheDocument();
    // Legacy .xls formula records are not inspectable, and the budget's
    // workbook-wide source error is outside the published fields (gate passed);
    // neither should appear as an orange publication warning.
    expect(screen.queryByText("Source check requires attention")).not.toBeInTheDocument();
    expect(screen.queryByText(/accounting_budget: source_errors/)).not.toBeInTheDocument();
    expect(screen.queryByText(/accounting_landing: formula_records_detected/)).not.toBeInTheDocument();
    // The full line-by-line balance sheet table was retired in favor of the
    // condensed management-balance rollup (see the dedicated test below); its
    // record here only feeds KPI cards now, not a visible "Итого активы" row.
    expect(screen.getByText("Итого доходов")).toBeInTheDocument();
    expect(screen.getByText("Процентные доходы")).toBeInTheDocument();
    expect(screen.getByText("Test Issuer")).toBeInTheDocument();
    // The budget workbook's cash-flow (and balance, in this fixture) section
    // has no data yet - this must read as an honest "no data" state, never a
    // fabricated empty-looking chart.
    expect(screen.getAllByText("No data in the source").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Export to Excel" }));
    // Second argument is the pinned accounting dataset versions (empty here -
    // no version was pinned in this test) - see the version-pin export fix.
    await waitFor(() => expect(api.exportAccountingData).toHaveBeenCalledWith("", []));
  });

  it("renders the management balance sheet rollup near the top of the accounting page", async () => {
    api.accountingReadiness.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [{ dataset_id: "bs-1", dataset_type: "accounting_balance_sheet", scope_code: "ACCOUNTING", source_filename: "fo.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1, dq_blocker_count: 0 }],
      summaries: { accounting_balance_sheet: { total_assets_kzt: "4856706", total_liabilities_kzt: "72026", total_equity_kzt: "4784680" } },
      records: {
        accounting_balance_sheet: [{ id: "bs-row-1", line_code: "25", line_label: "Итого активы", section: "Активы", current_period_kzt: "4856706", prior_period_kzt: "4643981" }],
        accounting_balance_sheet_summary: [
          { group: "asset", is_total: false, label_ru: "Денежные средства", label_en: "Денежные средства", current_period_kzt: "80187", prior_period_kzt: "83098" },
          { group: "total", is_total: true, label_ru: "ИТОГО АКТИВЫ", label_en: "TOTAL ASSETS", current_period_kzt: "4856706", prior_period_kzt: "4643981" },
          { group: "equity", is_total: false, label_ru: "Уставный капитал", label_en: "Share capital", current_period_kzt: "3500000", prior_period_kzt: "3500000" },
          { group: "total", is_total: true, label_ru: "ИТОГО СОБСТВЕННЫЙ КАПИТАЛ", label_en: "TOTAL EQUITY", current_period_kzt: "4784680", prior_period_kzt: "4472609", reconciles: false },
        ],
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<DomainPage kind="accounting" />);

    const panel = (await screen.findByText("Management balance sheet")).closest(".panel") as HTMLElement;
    expect(within(panel).getByText("TOTAL ASSETS")).toBeInTheDocument();
    expect(within(panel).getByText("4,856,706 ₸")).toBeInTheDocument();
    // A reconciliation gap on the equity total must surface as a visible
    // note, not be silently swallowed.
    expect(within(panel).getByText(/doesn't tie to the source's own/)).toBeInTheDocument();
  });

  it("opens a formula breakdown drawer when a management balance sheet row is clicked", async () => {
    api.accountingReadiness.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [{ dataset_id: "bs-1", dataset_type: "accounting_balance_sheet", scope_code: "ACCOUNTING", source_filename: "fo.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1, dq_blocker_count: 0 }],
      summaries: { accounting_balance_sheet: { total_assets_kzt: "80187", total_liabilities_kzt: "0", total_equity_kzt: "0" } },
      records: {
        accounting_balance_sheet: [{ id: "bs-row-1", line_code: "1", line_label: "Денежные средства", section: "Активы", current_period_kzt: "80187", prior_period_kzt: "63945" }],
        accounting_balance_sheet_summary: [
          {
            group: "asset", is_total: false, label_ru: "Денежные средства", label_en: "Cash", current_period_kzt: "80187", prior_period_kzt: "63945",
            derivation: {
              kind: "sum_of_lines",
              formula_ru: "Сумма строк раздела Баланса, для которых: наименование строки равно «Денежные средства».",
              formula_en: 'Sum of Balance Sheet lines where: line label equals "Денежные средства".',
              contributors: [{
                kind: "line", sign: "+", line_code: "1", line_label: "Денежные средства",
                current_period_kzt: "80187", prior_period_kzt: "63945",
                id: "bs-row-1", source: { sheet_name: "f1_uip", row_number: 12, source_cell: "A12", filename: "fo.xlsx" }
              }]
            }
          }
        ]
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="accounting" /></ProvenanceProvider>);

    const panel = (await screen.findByText("Management balance sheet")).closest(".panel") as HTMLElement;
    fireEvent.click(within(panel).getByText("Cash"));

    expect(await screen.findByText("How this value was derived")).toBeInTheDocument();
    expect(screen.getByText(/line label equals/)).toBeInTheDocument();
    // The contributing source line is a clickable evidence row that opens
    // the real cell preview via the same source-row-id/cell mechanism the
    // domain tables use.
    fireEvent.click(screen.getByText(/1\. Денежные средства/));
    expect(await screen.findByText("Source cell preview")).toBeInTheDocument();
    expect(api.sourcePreview).toHaveBeenCalledWith("bs-row-1", "A12");
  });

  it("switches the income-statement KPI cards between quarter and YTD via the period dropdown", async () => {
    api.accountingReadiness.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [
        { dataset_id: "is-1", dataset_type: "accounting_income_statement", scope_code: "ACCOUNTING", source_filename: "fo.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1, dq_blocker_count: 0 }
      ],
      summaries: { accounting_income_statement: { total_income_kzt: "287651", total_expenses_kzt: "184920", net_profit_kzt: "102731" } },
      records: {
        accounting_income_statement: [{ id: "is-row-1", line_code: "13", line_label: "Итого доходов", quarter_kzt: "287651", ytd_kzt: "695279" }]
      },
      pinned_dataset_types: []
    });

    // The period toggle now lives inside DomainVersionBar, which portals
    // into AppShell's "domain-version-bar-slot" - not rendered by this
    // standalone DomainPage test, so provide the slot the same way AppShell
    // does or the toggle (and every other accounting version picker) never
    // mounts at all.
    const slot = document.createElement("div");
    slot.id = "domain-version-bar-slot";
    document.body.appendChild(slot);

    await renderWithProviders(<DomainPage kind="accounting" />);

    const incomeCard = (await screen.findByText("Income for the quarter")).closest(".kpi-card") as HTMLElement;
    expect(within(incomeCard).getByText("287,651,000 ₸")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Income statement"), { target: { value: "ytd" } });

    const ytdCard = (await screen.findByText("Income YTD")).closest(".kpi-card") as HTMLElement;
    expect(within(ytdCard).getByText("695,279,000 ₸")).toBeInTheDocument();

    document.body.removeChild(slot);
  });

  it("switches the income-statement year-over-year chart's comparison period with the toggle", async () => {
    api.accountingReadiness.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [
        { dataset_id: "is-1", dataset_type: "accounting_income_statement", scope_code: "ACCOUNTING", source_filename: "fo.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1, dq_blocker_count: 0 }
      ],
      summaries: { accounting_income_statement: { total_income_kzt: "287651", total_expenses_kzt: "184920", net_profit_kzt: "102731" } },
      records: {
        accounting_income_statement: [
          { id: "is-row-1", line_code: "13", line_label: "Итого доходов", quarter_kzt: "287651", ytd_kzt: "695279", prior_quarter_kzt: "168322", prior_ytd_kzt: "446018" },
          { id: "is-row-2", line_code: "28", line_label: "Итого расходов", quarter_kzt: "184920", ytd_kzt: "388685", prior_quarter_kzt: "127845", prior_ytd_kzt: "365752" },
          { id: "is-row-3", line_code: "29", line_label: "Чистая прибыль (убыток) до уплаты корпоративного подоходного налога", quarter_kzt: "102731", ytd_kzt: "306594", prior_quarter_kzt: "40477", prior_ytd_kzt: "80266" },
        ]
      },
      pinned_dataset_types: []
    });

    const slot = document.createElement("div");
    slot.id = "domain-version-bar-slot";
    document.body.appendChild(slot);

    await renderWithProviders(<DomainPage kind="accounting" />);

    await screen.findByText("Income, expenses and net profit: year over year");
    expect(screen.getByText("The reporting quarter against the same quarter last year.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Income statement"), { target: { value: "ytd" } });

    await screen.findByText("Year to date against the same period last year.");
    expect(screen.queryByText("The reporting quarter against the same quarter last year.")).not.toBeInTheDocument();

    document.body.removeChild(slot);
  });

  it("swaps the income-statement panel for monthly budget charts and tables via the period dropdown", async () => {
    api.accountingReadiness.mockResolvedValue({
      available: true,
      disclosure: "Operational source data; not an accounting-approved result.",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [
        { dataset_id: "is-1", dataset_type: "accounting_income_statement", scope_code: "ACCOUNTING", source_filename: "fo.xlsx", source_report_date: "2026-07-01", business_date: "2026-07-01", publication_status: "published", version: 1, dq_blocker_count: 0 }
      ],
      summaries: { accounting_income_statement: { total_income_kzt: "287651", total_expenses_kzt: "184920", net_profit_kzt: "102731" } },
      records: {
        accounting_income_statement: [{ id: "is-row-1", line_code: "13", line_label: "Итого доходов", quarter_kzt: "287651", ytd_kzt: "695279" }],
        accounting_budget: [{
          id: "budget-row-1", section: "cash_flow", line_label: "Процентные доходы",
          month_01_kzt: "301", month_02_kzt: "302", month_03_kzt: "303", month_04_kzt: "304", month_05_kzt: "305", month_06_kzt: "306",
          month_07_kzt: "307", month_08_kzt: "308", month_09_kzt: "309", month_10_kzt: "310", month_11_kzt: "311", month_12_kzt: "312",
        }]
      },
      pinned_dataset_types: []
    });

    const slot = document.createElement("div");
    slot.id = "domain-version-bar-slot";
    document.body.appendChild(slot);

    await renderWithProviders(<DomainPage kind="accounting" />);

    await screen.findByText("Income for the quarter");
    expect(screen.getByText("Prior-year quarter")).toBeInTheDocument();
    expect(screen.queryByText("Cash flow by month")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Income statement"), { target: { value: "monthly" } });

    const monthlyPanel = (await screen.findByText("Cash flow by month")).closest(".panel") as HTMLElement;
    expect(screen.queryByText("Prior-year quarter")).not.toBeInTheDocument();
    expect(within(monthlyPanel).getByText("Процентные доходы")).toBeInTheDocument();
    expect(within(monthlyPanel).getByText("Jan")).toBeInTheDocument();
    expect(within(monthlyPanel).getByText("Dec")).toBeInTheDocument();

    document.body.removeChild(slot);
  });

  it("renders the country x instrument-category pivot with a valid per-row total but no cross-currency column total", async () => {
    api.risk.mockResolvedValue({
      available: true,
      disclosure: "",
      report_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [],
      summaries: { risk_limits_sobstv: { limit_count: 0, breach_count: 0 }, risk_limits_tabys: { limit_count: 0, breach_count: 0 } },
      records: {
        risk_limits_sobstv: [
          { id: "d1", portfolio_code: "SOBSTV", dimension: "country_instrument_detail", country: "Россия", currency: "RUB", instrument_category: "Облигации", amount_native: "1000", source: { sheet_name: "Detail", row_number: 10, source_cell: "D10", filename: "sobstv-limits.xls" } },
          { id: "d2", portfolio_code: "SOBSTV", dimension: "country_instrument_detail", country: "Россия", currency: "RUB", instrument_category: "Акции", amount_native: "500", source: { sheet_name: "Detail", row_number: 11, source_cell: "D11", filename: "sobstv-limits.xls" } },
          { id: "d3", portfolio_code: "SOBSTV", dimension: "country_instrument_detail", country: "Франция", currency: "EUR", instrument_category: "Облигации", amount_native: "2000", source: { sheet_name: "Detail", row_number: 20, source_cell: "D20", filename: "sobstv-limits.xls" } },
          { id: "d4", portfolio_code: "SOBSTV", dimension: "country_instrument_detail", country: "Пустая страна", currency: "EUR", instrument_category: "Акции", amount_native: "", source: { sheet_name: "Detail", row_number: 21, source_cell: "D21", filename: "sobstv-limits.xls" } },
          { id: "d5", portfolio_code: "SOBSTV", dimension: "country_instrument_detail", country: "Нулевая страна", currency: "EUR", instrument_category: "Облигации", amount_native: "0", source: { sheet_name: "Detail", row_number: 22, source_cell: "D22", filename: "sobstv-limits.xls" } }
        ],
        risk_limits_tabys: []
      },
      pinned_dataset_types: []
    });

    await renderWithProviders(<ProvenanceProvider><DomainPage kind="risk" /></ProvenanceProvider>);

    const pivotPanel = (await screen.findByText("Country x instrument-category summary")).closest("section");
    expect(pivotPanel).not.toBeNull();
    const withinPivot = within(pivotPanel as HTMLElement);
    // Россия's row total (1000 + 500 = 1500) is valid since both cells share RUB.
    expect(withinPivot.getByText("1,500")).toBeInTheDocument();
    // No across-country total is ever rendered - it would silently mix RUB and EUR.
    expect(withinPivot.queryByText("3,500")).not.toBeInTheDocument();
    expect(withinPivot.getAllByText("RUB").length).toBeGreaterThan(0);
    expect(withinPivot.getAllByText("EUR").length).toBeGreaterThan(0);
    expect(withinPivot.queryByText("Пустая страна")).not.toBeInTheDocument();
    expect(withinPivot.queryByText("Нулевая страна")).not.toBeInTheDocument();

    fireEvent.click(withinPivot.getByText("1,000"));
    expect(await screen.findByText("Source cell preview")).toBeInTheDocument();
  });

  it("shows the OSIP portfolio reconciliation result on the accounting page", async () => {
    api.accountingReadiness.mockResolvedValue({
      available: true,
      disclosure: "",
      report_date_mismatch: false,
      filename_date_mismatch: false,
      report_dates: ["2026-07-01"],
      sources: [],
      summaries: {
        accounting_balance_sheet: { total_assets_kzt: "4200000", total_liabilities_kzt: "200000", total_equity_kzt: "4000000" },
        accounting_income_statement: { total_income_kzt: "287651", total_expenses_kzt: "184920", net_profit_kzt: "102731" },
        accounting_portfolio_detail: { total_carrying_value_kzt: "55200000", reconciliation_portfolio_code: "SOBSTV" }
      },
      records: {
        accounting_balance_sheet: [],
        accounting_income_statement: [],
        accounting_budget: [],
        accounting_portfolio_detail: [{ id: "portfolio-row-1", category: "Корпоративные облигации", issuer: "Test Issuer", isin: "US0000000001", carrying_value_kzt: "46000000" }],
        accounting_landing: [{ id: "landing-1", record_type: "sheet_evidence", sheet: "Temp", rows: 40, columns: 6, formula_error_count: 2, external_link_count: 0 }]
      },
      pinned_dataset_types: []
    });
    api.operationsReadiness.mockResolvedValue({
      datasets: [],
      readiness: [],
      reconciliations: [{
        rule_code: "ACCOUNTING-PORTFOLIO", scope_code: "SOBSTV", business_date: "2026-07-01",
        actual_values: { accounting: "55200000", osip: "55200001" }, difference: "1", tolerance: "1", status: "pass", evidence: {},
      }],
    });

    await renderWithProviders(<DomainPage kind="accounting" />);

    expect(await screen.findByText("Budget and accounting are shown separately")).toBeInTheDocument();
    expect(await screen.findByText('Accounting to OSIP reconciliation · SOBSTV')).toBeInTheDocument();
    const reconciliation = document.querySelector<HTMLElement>(".reconciliation-workspace")!;
    expect(within(reconciliation).getByText("Portfolio carrying value")).toBeInTheDocument();
    expect(within(reconciliation).getByText("Difference, KZT")).toBeInTheDocument();
    expect(within(reconciliation).getByText("Tolerance, KZT")).toBeInTheDocument();
    expect(screen.getByText("Pass")).toBeInTheDocument();
  });
});
