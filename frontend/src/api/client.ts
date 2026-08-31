import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { ReportArtifact } from "./types";
import { authorizationHeaders, type DevelopmentIdentity } from "../auth/session";
import { getCurrentLanguage, translate } from "../i18n";


const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");
const client = createClient<paths>({ baseUrl: API_ORIGIN });


export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
  }
}


type OpenApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};


async function unwrap<T>(request: Promise<OpenApiResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok || data === undefined) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("osip:unauthorized"));
    }
    throw new ApiError(errorMessage(error, response.status), response.status);
  }
  return data;
}


function errorMessage(error: unknown, status: number): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String(item.msg)
            : ""
        )
        .filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
  }
  return translate(getCurrentLanguage(), "api.requestError", { status });
}


function headers(identity?: DevelopmentIdentity): Record<string, string> {
  return { ...authorizationHeaders(identity), "Accept-Language": getCurrentLanguage() };
}


function downloadSpreadsheet(result: OpenApiResult<unknown>, fallbackFilename: string, errorText: string): void {
  const { data, response } = result;
  if (!response.ok || !(data instanceof Blob)) {
    throw new ApiError(errorText, response.status);
  }
  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const filename = contentDisposition.match(/filename="?([^";]+)"?/)?.[1] ?? fallbackFilename;
  const url = URL.createObjectURL(data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}


async function holdingView(snapshotId: string, view: "lots" | "instruments") {
  return unwrap(
    client.GET("/api/v1/snapshots/{snapshot_id}/holdings", {
      headers: headers(),
      params: { path: { snapshot_id: snapshotId }, query: { view } }
    })
  );
}


export const dashboardApi = {
  demoLogin: (username: string, password: string) =>
    unwrap(
      client.POST("/api/v1/auth/demo-login", {
        headers: { "Accept-Language": getCurrentLanguage() },
        body: { username, password }
      })
    ),
  createSourceUpload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return unwrap(
      client.POST("/api/v1/source-uploads", {
        headers: headers(),
        body: { file: file.name },
        bodySerializer: () => formData
      })
    );
  },
  materializeSourceDatasets: (uploadId: string, datasets: Array<{ detected_key: string; scope_code?: string | null; reconciliation_portfolio_code?: string | null }>) =>
    unwrap(client.POST("/api/v1/source-uploads/{upload_id}/datasets", {
      headers: headers(),
      params: { path: { upload_id: uploadId } }, body: { datasets }
    })),
  sessionContext: () => unwrap(client.GET("/api/v1/session/context", { headers: headers() })),
  datasetVersions: (datasetType?: string, scopeCode?: string) => unwrap(client.GET("/api/v1/dataset-versions", { headers: headers(), params: { query: { dataset_type: datasetType, scope_code: scopeCode } } })),
  datasetMapping: (datasetId: string) => unwrap(client.GET("/api/v1/dataset-versions/{dataset_id}/mapping", { headers: headers(), params: { path: { dataset_id: datasetId } } })),
  compareDatasetVersions: (datasetId: string, withId: string) => unwrap(client.GET("/api/v1/dataset-versions/{dataset_id}/compare", { headers: headers(), params: { path: { dataset_id: datasetId }, query: { with_id: withId } } })),
  confirmDatasetMapping: (datasetId: string, comment: string) => unwrap(client.POST("/api/v1/dataset-versions/{dataset_id}/mapping/confirm", { headers: headers(), params: { path: { dataset_id: datasetId } }, body: { comment } })),
  approveDataset: (datasetId: string, codes: string[], comment: string, mappingConfirmed = false) =>
    unwrap(client.POST("/api/v1/dataset-versions/{dataset_id}/approve", {
      headers: headers(),
      params: { path: { dataset_id: datasetId } },
      body: { comment, acknowledged_dq_codes: codes, mapping_confirmed: mappingConfirmed }
    })),
  publishDataset: (datasetId: string) =>
    unwrap(client.POST("/api/v1/dataset-versions/{dataset_id}/publish", {
      headers: headers(),
      params: { path: { dataset_id: datasetId } }
    })),
  rejectDataset: (datasetId: string, reason: string) =>
    unwrap(client.POST("/api/v1/dataset-versions/{dataset_id}/reject", {
      headers: headers(),
      params: { path: { dataset_id: datasetId } }, body: { reason }
    })),
  withdrawDataset: (datasetId: string, reason: string) =>
    unwrap(client.POST("/api/v1/dataset-versions/{dataset_id}/withdraw", {
      headers: headers(),
      params: { path: { dataset_id: datasetId } }, body: { reason }
    })),
  assetManagement: (sourceUploadId?: string, datasetVersions?: string[]) => unwrap(client.GET("/api/v1/funds/TABYS/overview", { headers: headers(), params: { query: { source_upload_id: sourceUploadId, dataset_versions: datasetVersions } } })),
  treasury: (sourceUploadId?: string) => unwrap(client.GET("/api/v1/treasury/overview", { headers: headers(), params: { query: { source_upload_id: sourceUploadId } } })),
  brokerage: (sourceUploadId?: string) => unwrap(client.GET("/api/v1/brokerage/overview", { headers: headers(), params: { query: { source_upload_id: sourceUploadId } } })),
  clients: (sourceUploadId?: string) => unwrap(client.GET("/api/v1/clients", { headers: headers(), params: { query: { source_upload_id: sourceUploadId } } })),
  clientDetail: (recordId: string) => unwrap(client.GET("/api/v1/clients/records/{record_id}", { headers: headers(), params: { path: { record_id: recordId } } })),
  clientIdentityExceptions: (status: "pending" | "confirmed" | "rejected" | "all" = "pending") => unwrap(client.GET("/api/v1/client-exceptions", { headers: headers(), params: { query: { status } } })),
  resolveClientIdentityException: (recordId: string, disposition: "confirmed" | "rejected", account: string | null, comment: string) => unwrap(client.POST("/api/v1/client-exceptions/{record_id}/resolve", { headers: headers(), params: { path: { record_id: recordId } }, body: { disposition, account, comment } })),
  corporateFinance: (sourceUploadId?: string) => unwrap(client.GET("/api/v1/corporate-finance/overview", { headers: headers(), params: { query: { source_upload_id: sourceUploadId } } })),
  accountingReadiness: (sourceUploadId?: string, datasetVersions?: string[]) => unwrap(client.GET("/api/v1/accounting/source-readiness", { headers: headers(), params: { query: { source_upload_id: sourceUploadId, dataset_versions: datasetVersions } } })),
  risk: (sourceUploadId?: string, datasetVersions?: string[]) => unwrap(client.GET("/api/v1/risk/overview", { headers: headers(), params: { query: { source_upload_id: sourceUploadId, dataset_versions: datasetVersions } } })),
  operationsReadiness: () => unwrap(client.GET("/api/v1/operations/source-readiness", { headers: headers() })),
  exportFundData: async (term = "", sourceUploadId?: string, datasetVersions?: string[]) => {
    const result = await client.GET("/api/v1/funds/TABYS/export", { headers: headers(), params: { query: { term, source_upload_id: sourceUploadId, dataset_versions: datasetVersions } }, parseAs: "blob" });
    downloadSpreadsheet(result, "PortfolioOpsInsight_fund_TABYS.xlsx", translate(getCurrentLanguage(), "api.requestError", { status: result.response.status }));
  },
  exportBrokerageData: async (term = "", includeRepo = true, sourceUploadId?: string) => {
    const result = await client.GET("/api/v1/brokerage/export", { headers: headers(), params: { query: { term, include_repo: includeRepo, source_upload_id: sourceUploadId } }, parseAs: "blob" });
    downloadSpreadsheet(result, "PortfolioOpsInsight_brokerage.xlsx", translate(getCurrentLanguage(), "api.requestError", { status: result.response.status }));
  },
  exportCorporateFinanceData: async (term = "") => {
    const result = await client.GET("/api/v1/corporate-finance/export", { headers: headers(), params: { query: { term } }, parseAs: "blob" });
    downloadSpreadsheet(result, "PortfolioOpsInsight_corporate_finance.xlsx", translate(getCurrentLanguage(), "api.requestError", { status: result.response.status }));
  },
  exportRiskData: async (term = "", datasetVersions?: string[]) => {
    const result = await client.GET("/api/v1/risk/export", { headers: headers(), params: { query: { term, dataset_versions: datasetVersions } }, parseAs: "blob" });
    downloadSpreadsheet(result, "PortfolioOpsInsight_risk.xlsx", translate(getCurrentLanguage(), "api.requestError", { status: result.response.status }));
  },
  exportAccountingData: async (term = "", datasetVersions?: string[]) => {
    const result = await client.GET("/api/v1/accounting/export", { headers: headers(), params: { query: { term, dataset_versions: datasetVersions } }, parseAs: "blob" });
    downloadSpreadsheet(result, "PortfolioOpsInsight_accounting.xlsx", translate(getCurrentLanguage(), "api.requestError", { status: result.response.status }));
  },
  portfolios: () =>
    unwrap(client.GET("/api/v1/portfolios", { headers: headers() })),
  snapshots: (portfolioCode: string, includeSuperseded = false) =>
    unwrap(
      client.GET("/api/v1/portfolios/{code}/snapshots", {
        headers: headers(),
        params: {
          path: { code: portfolioCode },
          query: { include_superseded: includeSuperseded }
        }
      })
    ),
  overview: (snapshotId: string) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/overview", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } }
      })
    ),
  provenance: (snapshotId: string) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/provenance", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } }
      })
    ),
  sourcePreview: (sourceRowId: string, cell: string) =>
    unwrap(
      client.GET("/api/v1/source-rows/{source_row_id}/preview", {
        headers: headers(),
        params: { path: { source_row_id: sourceRowId }, query: { cell } }
      })
    ),
  downloadSourceWorkbook: async (importId: string, filename: string) => {
    const result = await client.GET("/api/v1/imports/{import_id}/source", {
      headers: headers(),
      params: { path: { import_id: importId } },
      parseAs: "blob"
    });
    const blob = result.data;
    if (!result.response.ok || !(blob instanceof Blob)) {
      throw new ApiError(translate(getCurrentLanguage(), "api.requestError", { status: result.response.status }), result.response.status);
    }
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },
  downloadSourceUpload: async (uploadId: string, filename: string) => {
    const result = await client.GET("/api/v1/source-uploads/{upload_id}/source", {
      headers: headers(),
      params: { path: { upload_id: uploadId } },
      parseAs: "blob"
    });
    const blob = result.data;
    if (!result.response.ok || !(blob instanceof Blob)) {
      throw new ApiError(translate(getCurrentLanguage(), "api.requestError", { status: result.response.status }), result.response.status);
    }
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },
  allocation: (
    snapshotId: string,
    dimension: "asset_class" | "currency" | "issuer" | "valuation_method" | "raw_sector" | "rating" = "asset_class",
    basis: "derived_carrying" | "purchase" = "derived_carrying"
  ) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/allocations", {
        headers: headers(),
        params: {
          path: { snapshot_id: snapshotId },
          query: { dimension, basis }
        }
      })
    ),
  calendar: (snapshotId: string) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/calendar", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } }
      })
    ),
  readiness: (snapshotId: string) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/report-readiness", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } }
      })
    ),
  instrumentHoldings: async (snapshotId: string) => {
    const result = await holdingView(snapshotId, "instruments");
    if (result.view !== "instruments") {
      throw new ApiError(translate(getCurrentLanguage(), "api.invalidInstrumentView"), 500);
    }
    return result;
  },
  lotHoldings: async (snapshotId: string) => {
    const result = await holdingView(snapshotId, "lots");
    if (result.view !== "lots") {
      throw new ApiError(translate(getCurrentLanguage(), "api.invalidLotView"), 500);
    }
    return result;
  },
  exportInstrumentHoldings: async (
    snapshotId: string,
    options: {
      basis: "derived_carrying" | "purchase";
      term: string;
      assetClass: string;
    }
  ) => {
    const result = await client.GET("/api/v1/snapshots/{snapshot_id}/holdings/export", {
      headers: headers(),
      params: {
        path: { snapshot_id: snapshotId },
        query: {
          basis: options.basis,
          term: options.term.trim(),
          asset_class: options.assetClass === "all" ? undefined : options.assetClass
        }
      },
      parseAs: "blob"
    });
    downloadSpreadsheet(result, "OSIP_holdings.xlsx", translate(getCurrentLanguage(), "api.holdingsExport"));
  },
  exportLotHoldings: async (snapshotId: string) => {
    const result = await client.GET("/api/v1/snapshots/{snapshot_id}/lots/export", {
      headers: headers(), params: { path: { snapshot_id: snapshotId } }, parseAs: "blob"
    });
    downloadSpreadsheet(result, "OSIP_lots.xlsx", translate(getCurrentLanguage(), "api.lotsExport"));
  },
  cash: (snapshotId: string) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/cash", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } }
      })
    ),
  exportCashCalendar: async (snapshotId: string, includeInactive: boolean) => {
    const result = await client.GET("/api/v1/snapshots/{snapshot_id}/cash-calendar/export", {
      headers: headers(),
      params: { path: { snapshot_id: snapshotId }, query: { include_inactive: includeInactive } },
      parseAs: "blob"
    });
    downloadSpreadsheet(result, "OSIP_cash_calendar.xlsx", translate(getCurrentLanguage(), "api.cashExport"));
  },
  issues: (snapshotId: string) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/issues", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } }
      })
    ),
  exportDqIssues: async (snapshotId: string, options: { term: string; severity: "all" | "blocker" | "high" | "medium" | "low" }) => {
    const result = await client.GET("/api/v1/snapshots/{snapshot_id}/issues/export", {
      headers: headers(),
      params: { path: { snapshot_id: snapshotId }, query: { term: options.term.trim(), severity: options.severity } },
      parseAs: "blob"
    });
    downloadSpreadsheet(result, "OSIP_dq_issues.xlsx", translate(getCurrentLanguage(), "api.dqExport"));
  },
  metrics: () =>
    unwrap(client.GET("/api/v1/metrics", { headers: headers() })),
  imports: () =>
    unwrap(client.GET("/api/v1/imports", { headers: headers() })),
  upload: ({ file, portfolioCode, portfolioName }: { file: File; portfolioCode: string; portfolioName?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("portfolio_code", portfolioCode);
    if (portfolioName?.trim()) formData.append("portfolio_name", portfolioName.trim());
    return unwrap(
      client.POST("/api/v1/imports", {
        headers: headers(),
        body: { file: file.name, portfolio_code: portfolioCode, portfolio_name: portfolioName },
        bodySerializer: () => formData
      })
    );
  },
  referenceDictionaryStatus: () =>
    unwrap(client.GET("/api/v1/reference-data/classes-and-ratings", { headers: headers() })),
  uploadReferenceDictionary: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return unwrap(
      client.POST("/api/v1/reference-data/classes-and-ratings", {
        headers: headers(),
        body: { file: file.name },
        bodySerializer: () => formData
      })
    );
  },
  dividendDataStatus: () =>
    unwrap(client.GET("/api/v1/reference-data/dividends", { headers: headers() })),
  uploadDividendData: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return unwrap(
      client.POST("/api/v1/reference-data/dividends", {
        headers: headers(),
        body: { file: file.name },
        bodySerializer: () => formData
      })
    );
  },
  comparison: (importId: string) =>
    unwrap(
      client.GET("/api/v1/imports/{import_id}/comparison", {
        headers: headers(),
        params: { path: { import_id: importId } }
      })
    ),
  exportImportRegistry: async () => {
    const result = await client.GET("/api/v1/imports/export", { headers: headers(), parseAs: "blob" });
    downloadSpreadsheet(result, "OSIP_import_registry.xlsx", translate(getCurrentLanguage(), "api.importExport"));
  },
  approve: (importId: string, codes: string[], comment: string) =>
    unwrap(
      client.POST("/api/v1/imports/{import_id}/approve", {
        headers: headers(),
        params: { path: { import_id: importId } },
        body: {
          comment,
          acknowledged_dq_codes: codes,
          mapping_confirmed: false
        }
      })
    ),
  publish: (importId: string) =>
    unwrap(
      client.POST("/api/v1/imports/{import_id}/publish", {
        headers: headers(),
        params: { path: { import_id: importId } }
      })
    ),
  withdraw: (importId: string, reason: string) =>
    unwrap(
      client.POST("/api/v1/imports/{import_id}/withdraw", {
        headers: headers(),
        params: { path: { import_id: importId } },
        body: { reason }
      })
    ),
  assignDqIssue: (issueId: string, body: { ownerId: string | null; dueDate: string | null; reason: string }) =>
    unwrap(
      client.POST("/api/v1/issues/{issue_id}/assign", {
        headers: headers(),
        params: { path: { issue_id: issueId } },
        body: { owner_id: body.ownerId, due_date: body.dueDate, reason: body.reason }
      })
    ),
  reports: (snapshotId: string) =>
    unwrap(
      client.GET("/api/v1/snapshots/{snapshot_id}/reports", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } }
      })
    ),
  createReport: (snapshotId: string) =>
    unwrap(
      client.POST("/api/v1/snapshots/{snapshot_id}/reports", {
        headers: headers(),
        params: { path: { snapshot_id: snapshotId } },
        body: { format: "csv" }
      })
    ),
  downloadReport: async (report: ReportArtifact) => {
    const blob = await unwrap(
      client.GET("/api/v1/reports/{report_id}/artifact", {
        headers: headers(),
        params: { path: { report_id: report.id } },
        parseAs: "blob"
      })
    );
    if (!(blob instanceof Blob)) {
      throw new ApiError(translate(getCurrentLanguage(), "api.invalidArtifact"), 500);
    }
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "OSIP-operational-snapshot.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }
};
