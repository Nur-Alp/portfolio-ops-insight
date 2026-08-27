import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  sourcePreview: vi.fn(),
  downloadSourceUpload: vi.fn().mockResolvedValue(undefined)
}));

vi.mock("../../api/client", () => ({ dashboardApi: api }));

import { renderWithProviders } from "../../test/render";
import { ProvenanceProvider, useProvenance } from "./ProvenanceContext";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.sessionStorage.removeItem("osip-dashboard-language");
});

const riskMetric = {
  code: "risk_breaches",
  label: "Breaches",
  basis: "source" as const,
  value: "1",
  explanation: "",
  source_refs: [{
    workbook_name: "risk.xls", sheet_name: "Лимит по странам", row_number: 5,
    parser_version: "v1", source_row_id: "risk-row-1",
    source_cell: "C5", source_column: 3, source_column_letter: "C",
    source_kind: "row" as const, field: "label"
  }]
};

const navMetric = {
  code: "am_nav",
  label: "Source-reported NAV",
  basis: "source" as const,
  value: "63892817",
  explanation: "",
  source_refs: [{
    workbook_name: "tabys-valuation.xlsx", sheet_name: "дата", row_number: null,
    parser_version: "v1", source_row_id: "am-dataset",
    source_cell: null, source_column: null, source_column_letter: null,
    source_kind: "dataset" as const,
    source_upload_id: "upload-1"
  }]
};

const operationalMetric = {
  code: "derived_operational_total_kzt",
  // Deliberately use the API's English copy: this is the regression case for
  // a Russian session opening a snapshot produced by the backend.
  label: "Operational total",
  basis: "derived" as const,
  value: "519987019",
  formula: "derived_carrying_value_kzt + cash_kzt",
  explanation: "Operational total combines the derived carrying value and source cash equivalent; it is not NAV or market value.",
  inputs: [
    { code: "derived_carrying_value_kzt", label: "Derived carrying value", value: "4785739590", basis: "derived" as const },
    { code: "cash_kzt", label: "Cash equivalent", value: "40714429", basis: "source" as const }
  ],
  source_refs: []
};

function Harness() {
  const { open } = useProvenance();
  return <>
    <button type="button" onClick={() => open(riskMetric)}>open risk</button>
    <button type="button" onClick={() => open(navMetric)}>open nav</button>
  </>;
}

it("does not resurrect a closed cell preview when a different, unrelated metric is opened later", async () => {
  api.sourcePreview.mockResolvedValue({
    workbook_name: "risk.xls", sheet_name: "Лимит по странам", target_cell: "C5", target_row: 5, target_column: 3,
    target_value: "Kazakhstan", columns: ["A", "B", "C"], rows: [{ row_number: 5, values: [null, null, "Kazakhstan"] }],
    import_id: "import-1", original_filename: "risk.xls"
  });

  await renderWithProviders(<ProvenanceProvider><Harness /></ProvenanceProvider>);

  // Open the risk metric and its cell preview.
  fireEvent.click(screen.getByRole("button", { name: "open risk" }));
  const riskDialog = await screen.findByRole("dialog");
  fireEvent.click(within(riskDialog).getByRole("button", { name: /Open cell/ }));
  expect(await screen.findByText("Source cell preview")).toBeInTheDocument();
  expect(screen.getAllByRole("dialog").length).toBe(2);

  // Close the metric drawer (its onClose overlay/X button) WITHOUT explicitly
  // closing the cell preview first - this is the exact sequence that left
  // the preview's state dangling.
  fireEvent.click(within(riskDialog).getByRole("button", { name: "Close details" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  // Opening a completely different, unrelated metric must not resurrect the
  // old preview - it must show only that new metric's own evidence.
  fireEvent.click(screen.getByRole("button", { name: "open nav" }));
  const navDialog = await screen.findByRole("dialog");
  expect(within(navDialog).getByText("Source-reported NAV")).toBeInTheDocument();
  expect(screen.queryByText("Source cell preview")).not.toBeInTheDocument();
  expect(screen.queryByText("risk.xls")).not.toBeInTheDocument();
  expect(screen.getAllByRole("dialog").length).toBe(1);
});

it("localizes the operational calculation and its inputs for Russian users", async () => {
  window.sessionStorage.setItem("osip-dashboard-language", "ru");

  await renderWithProviders(
    <ProvenanceProvider>
      <OperationalHarness />
    </ProvenanceProvider>
  );

  fireEvent.click(screen.getByRole("button", { name: "open operational total" }));
  const dialog = await screen.findByRole("dialog");

  expect(within(dialog).getByText("Операционный итог")).toBeInTheDocument();
  expect(within(dialog).getByText(/Операционный итог — сумма расчётной балансовой стоимости/)).toBeInTheDocument();
  expect(within(dialog).getByText("Техническая формула")).toBeInTheDocument();
  expect(within(dialog).getByText("Расчётная балансовая стоимость + денежный эквивалент (KZT)")).toBeInTheDocument();
  expect(within(dialog).getByText("Расчётная балансовая стоимость")).toBeInTheDocument();
  expect(within(dialog).getByText("Денежный эквивалент")).toBeInTheDocument();
  expect(within(dialog).queryByText(/Operational total combines/)).not.toBeInTheDocument();
});

it("opens aggregate dataset evidence as a source-workbook action", async () => {
  await renderWithProviders(
    <ProvenanceProvider>
      <Harness />
    </ProvenanceProvider>
  );

  fireEvent.click(screen.getByRole("button", { name: "open nav" }));
  const metricDialog = await screen.findByRole("dialog");
  fireEvent.click(within(metricDialog).getByRole("button", { name: /Open source workbook/ }));

  const workbookDialog = screen.getAllByRole("dialog")[1];
  expect(within(workbookDialog).getByText("дата")).toBeInTheDocument();
  fireEvent.click(within(workbookDialog).getByRole("button", { name: "Download original" }));
  expect(api.downloadSourceUpload).toHaveBeenCalledWith("upload-1", "tabys-valuation.xlsx");
});

function OperationalHarness() {
  const { open } = useProvenance();
  return <button type="button" onClick={() => open(operationalMetric)}>open operational total</button>;
}
