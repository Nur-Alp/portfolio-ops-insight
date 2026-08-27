import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../api/client", () => ({
  dashboardApi: {
    sourcePreview: vi.fn().mockResolvedValue({
      workbook_name: "portfolio.xls",
      sheet_name: "ОСИП_ПОРТФЕЛЬ",
      target_cell: "AA5",
      target_row: 5,
      target_column: 27,
      target_value: "99121.77",
      columns: Array.from({ length: 27 }, (_, index) => index === 26 ? "AA" : `C${index}`),
      rows: [{ row_number: 5, values: Array.from({ length: 27 }, (_, index) => index === 26 ? "99121.77" : null) }],
      import_id: "import-1",
      original_filename: "portfolio.xls"
    }),
    downloadSourceWorkbook: vi.fn()
  }
}));

import { LanguageProvider } from "../../i18n";
import { SourcePreviewDrawer } from "./SourcePreviewDrawer";

const reference = {
  workbook_name: "portfolio.xls",
  sheet_name: "ОСИП_ПОРТФЕЛЬ",
  row_number: 5,
  source_column: 27,
  source_column_letter: "AA",
  source_cell: "AA5",
  source_kind: "row" as const,
  parser_version: "osip-test",
  source_row_id: "row-1",
  field: "carrying_amount_native",
  value: "99121.77",
  dataset_id: null,
  dataset_type: null,
  scope_code: null,
  business_date: null,
  version: null,
  source_header: null,
  note: null
};

describe("SourcePreviewDrawer", () => {
  it("loads and highlights the exact referenced cell", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <SourcePreviewDrawer reference={reference} onClose={vi.fn()} />
        </LanguageProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText("ОСИП_ПОРТФЕЛЬ!AA5")).toBeInTheDocument();
    expect(screen.getAllByText("99121.77")).toHaveLength(2);
    expect(document.querySelector(".source-preview__target-cell")).toHaveTextContent("99121.77");
    expect(screen.getByRole("button", { name: "Download original" })).toBeInTheDocument();
    expect(screen.getByText("AA")).toBeInTheDocument();
  });

  it("labels a column by its real header text and tags the header row", async () => {
    const { dashboardApi } = await import("../../api/client");
    vi.mocked(dashboardApi.sourcePreview).mockResolvedValueOnce({
      workbook_name: "risk-sobstv.xls",
      sheet_name: "Лимит по странам",
      target_cell: "C9",
      target_row: 9,
      target_column: 3,
      target_value: "ФРАНЦИЯ",
      columns: ["A", "B", "C"],
      header_row: 3,
      column_labels: ["№", "Код", "Страна"],
      rows: [
        { row_number: 3, values: ["№", "Код", "Страна"] },
        { row_number: 9, values: [8, "FR", "ФРАНЦИЯ"] }
      ],
      import_id: "import-2",
      original_filename: "risk-sobstv.xls"
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <SourcePreviewDrawer reference={{ ...reference, sheet_name: "Лимит по странам", source_cell: "C9", value: "ФРАНЦИЯ" }} onClose={vi.fn()} />
        </LanguageProvider>
      </QueryClientProvider>
    );

    await screen.findByText("header");
    expect(screen.getAllByText("Страна").length).toBeGreaterThan(0);
    expect(document.querySelector(".source-preview__column-label")).toHaveTextContent("№");
  });
});
