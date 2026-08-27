import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, ChevronLeft, ChevronRight, Download, Search, ShieldAlert } from "lucide-react";
import { dashboardApi } from "../api/client";
import type { ModuleReadResponse } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { KpiCard } from "../components/ui/KpiCard";
import { Panel } from "../components/ui/Panel";
import { formatDate, formatKzt } from "../lib/format";
import { useI18n } from "../i18n";
import { DomainCharts } from "../components/charts/DomainCharts";
import { PageFrame } from "../components/ui/PageFrame";
import { SourceRowLegend } from "../components/ui/SourceRowLegend";
import { useProvenance } from "../components/ui/ProvenanceContext";
import { useScrollAnchor } from "../hooks/useScrollAnchor";
import {
  AccountingBudgetSectionPanel, AccountingComparabilityNotice, AccountingIncomeStatementPanel,
  AccountingPeriodToggle, AccountingPortfolioPanel, AccountingReconciliationBanner,
  AccountingVersionPickerBar, AccountMappingPanel, type IncomeStatementPeriod,
} from "./domain-panels/AccountingPanels";
import { BrokerageDerivativesPanel, BrokerageRepoToggle } from "./domain-panels/BrokeragePanels";
import { ClientDetailPanel, ClientIdentityExceptionPanel, ClientManagerPanel, ClientMaturityPanel } from "./domain-panels/ClientsPanels";
import { AssetManagementVersionPickerBar, FundControlsPanel } from "./domain-panels/FundPanels";
import { isRiskNearBreach, riskNearBreachThreshold, RiskControlsPanel, RiskVersionPickerBar } from "./domain-panels/RiskPanels";
import {
  ActionItemsPanel, card, domainCardProvenance, domainSourceRefs, DomainSourceMeta, DomainTable,
  FormulaAuditNotice, isRepoTrade, money, moneyThousands, ReadinessChecklist, VersionPicker,
  type DomainKind, type Row, STANDARD_TABLE_PAGE_SIZE,
} from "./domain-panels/shared";
import { TreasuryDetailLinks, TreasuryVersionPicker } from "./domain-panels/TreasuryPanels";

const loaders: Record<DomainKind, (sourceUploadId?: string) => Promise<ModuleReadResponse>> = {
  "asset-management": dashboardApi.assetManagement,
  treasury: dashboardApi.treasury,
  brokerage: dashboardApi.brokerage,
  clients: dashboardApi.clients,
  "corporate-finance": dashboardApi.corporateFinance,
  accounting: dashboardApi.accountingReadiness,
  risk: dashboardApi.risk
};

// These domains expose source-backed workbook history directly on the page.
// Risk has two selectors because SOBSTV and TABYS are independent workbooks;
// a single selector would silently hide one side of the control set.
const PINNABLE_KINDS: ReadonlySet<DomainKind> = new Set(["asset-management", "treasury", "brokerage", "clients", "corporate-finance", "accounting", "risk"]);

type SourceWarning = { title: string; body: string; action?: ReactNode };

function SourceWarningSwitcher({ warnings }: { warnings: SourceWarning[] }) {
  const { language } = useI18n();
  const [index, setIndex] = useState(0);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    setIndex((current) => warnings.length ? Math.min(current, warnings.length - 1) : 0);
    setExpanded(false);
  }, [warnings.length]);
  useEffect(() => { setExpanded(false); }, [index]);
  if (!warnings.length) return null;
  const warning = warnings[index];
  const toggleLabel = expanded
    ? (language === "en" ? "Collapse message" : "Свернуть сообщение")
    : (language === "en" ? "Show full message" : "Показать сообщение полностью");
  return <aside className="source-warning-switcher" aria-label="Source warnings">
    <div className="source-warning-switcher__body"><AlertTriangle aria-hidden="true" /><div className="source-warning-switcher__copy">
      <button className="source-warning-switcher__message" type="button" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>
        <strong>{warning.title}</strong>
        <span className={`source-warning-switcher__text${expanded ? " source-warning-switcher__text--expanded" : ""}`}>{warning.body}</span>
        <span className="source-warning-switcher__toggle">{toggleLabel}</span>
      </button>
      {warning.action ? <div className="source-warning-switcher__action">{warning.action}</div> : null}
    </div></div>
    {warnings.length > 1 ? <div className="source-warning-switcher__controls"><span>{index + 1} / {warnings.length}</span><button className="icon-button" type="button" aria-label="Previous warning" onClick={() => setIndex((current) => (current - 1 + warnings.length) % warnings.length)}><ChevronLeft aria-hidden="true" /></button><button className="icon-button" type="button" aria-label="Next warning" onClick={() => setIndex((current) => (current + 1) % warnings.length)}><ChevronRight aria-hidden="true" /></button></div> : null}
  </aside>;
}

// This anchor dataset supplies the version choices for a module. The selected
// value is the physical source-upload ID, not the child dataset ID: the API
// then loads every compatible child from exactly that uploaded workbook.
// A brokerage page can therefore never combine a trade ledger from one book
// with a client snapshot or derivatives register from another.
const MODULE_ANCHOR_DATASET_TYPE: Partial<Record<DomainKind, string>> = {
  "asset-management": "fund_valuation",
  brokerage: "brokerage_trade_ledger",
  clients: "client_account_snapshot",
  "corporate-finance": "corporate_finance_register"
};

export function DomainPage({ kind }: { kind: DomainKind }) {
  const { language } = useI18n();
  const { open: openProvenance, openSourcePreview } = useProvenance();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [selectedClientRecord, setSelectedClientRecord] = useState<string | null>(null);
  const clientDetailRef = useRef<HTMLDivElement>(null);
  const [term, setTerm] = useState("");
  const [page, setPage] = useState(0);
  const [includeRepo, setIncludeRepo] = useState(true);
  const [incomeStatementPeriod, setIncomeStatementPeriod] = useState<IncomeStatementPeriod>("quarter");
  const [sourceUploadId, setSourceUploadId] = useState<string | null>(null);
  const [riskDatasetSelections, setRiskDatasetSelections] = useState<Record<string, string | null>>({});
  const selectedRiskDatasetVersions = Object.values(riskDatasetSelections).filter((value): value is string => Boolean(value));
  // Accounting is fed by four independently-uploaded physical workbooks
  // (statements, budget, portfolio detail, plus the landing evidence file) -
  // same situation as risk's SOBSTV/TABYS, so it needs the same per-type
  // pinning rather than one "whole module" version pin. Keyed by
  // dataset_type (not scope_code, unlike risk) since all four share the
  // single "ACCOUNTING" scope.
  const [accountingDatasetSelections, setAccountingDatasetSelections] = useState<Record<string, string | null>>({});
  const selectedAccountingDatasetVersions = Object.values(accountingDatasetSelections).filter((value): value is string => Boolean(value));
  // TABYS's unit-value history is its own independent workbook, separate
  // from the valuation/holdings package sourceUploadId pins - see
  // AssetManagementVersionPickerBar.
  const [assetManagementUnitSeriesId, setAssetManagementUnitSeriesId] = useState<string | null>(null);
  const mainPagination = useScrollAnchor<HTMLDivElement>();
  const query = useQuery({
    queryKey: ["domain", kind, sourceUploadId, selectedRiskDatasetVersions, selectedAccountingDatasetVersions, assetManagementUnitSeriesId],
    queryFn: () => kind === "risk"
      ? dashboardApi.risk(undefined, selectedRiskDatasetVersions)
      : kind === "accounting"
        ? dashboardApi.accountingReadiness(undefined, selectedAccountingDatasetVersions)
        : kind === "asset-management"
          ? dashboardApi.assetManagement(sourceUploadId ?? undefined, assetManagementUnitSeriesId ? [assetManagementUnitSeriesId] : undefined)
          : loaders[kind](sourceUploadId ?? undefined)
  });
  const treasurySnapshotId = kind === "treasury"
    ? String(((query.data?.summaries as Record<string, Record<string, unknown>> | undefined)?.portfolio_snapshot?.snapshot_id ?? ""))
    : "";
  const treasuryProvenance = useQuery({
    queryKey: ["treasury-provenance", treasurySnapshotId],
    queryFn: () => dashboardApi.provenance(treasurySnapshotId),
    enabled: Boolean(treasurySnapshotId),
    staleTime: 60_000,
  });
  useEffect(() => { setSourceUploadId(null); setRiskDatasetSelections({}); setAccountingDatasetSelections({}); setAssetManagementUnitSeriesId(null); }, [kind]);
  useEffect(() => {
    if (!selectedClientRecord) return;
    // The detail panel is appended after the long client page. Bring it into
    // view immediately after the user clicks "Карточка" so the action never
    // appears to do nothing.
    const detail = clientDetailRef.current;
    if (detail && typeof detail.scrollIntoView === "function") {
      detail.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [selectedClientRecord]);
  const resetModuleVersion = () => { setSourceUploadId(null); setAssetManagementUnitSeriesId(null); };
  const resetRiskVersions = () => setRiskDatasetSelections({});
  const resetAccountingVersions = () => setAccountingDatasetSelections({});
  const exporter = domainExporter(kind, selectedRiskDatasetVersions, selectedAccountingDatasetVersions, assetManagementUnitSeriesId);
  const exportFile = useMutation({ mutationFn: ({ termValue, includeRepo: includeRepoValue }: { termValue: string; includeRepo: boolean }) => exporter ? exporter(termValue, includeRepoValue, sourceUploadId ?? undefined) : Promise.resolve() });
  const data = query.data;
  const rows = data ? domainRows(kind, data).filter((row) => kind !== "brokerage" || includeRepo || !isRepoTrade(row)) : [];
  const searchableRows = useMemo(() => {
    const normalized = term.trim().toLocaleLowerCase();
    if (!normalized) return rows;
    return rows.filter((row) => matchesSearchTerm(row, normalized));
  }, [rows, term]);
  if (query.isLoading) return <LoadingState label={l("Загрузка данных раздела", "Loading domain data")} />;
  if (query.error) return <ErrorState error={query.error} retry={() => query.refetch()} />;
  if (!data) return <LoadingState label={l("Загрузка данных раздела", "Loading domain data")} />;
  const meta = domainMeta(kind, language);
  if (!data.available) {
    return (
      <PageFrame title={meta.title} eyebrow="Portfolio Operations Insight / controlled source" description={meta.description} meta={<DomainSourceMeta data={data} language={language} />}>
          <DomainVersionBar kind={kind} data={data} pinnable={PINNABLE_KINDS.has(kind)} selectedSourceUploadId={sourceUploadId} onSelect={setSourceUploadId} riskDatasetSelections={riskDatasetSelections} onRiskSelect={(scope, datasetId) => setRiskDatasetSelections((current) => ({ ...current, [scope]: datasetId }))} accountingDatasetSelections={accountingDatasetSelections} onAccountingSelect={(datasetType, datasetId) => setAccountingDatasetSelections((current) => ({ ...current, [datasetType]: datasetId }))} assetManagementUnitSeriesId={assetManagementUnitSeriesId} onAssetManagementUnitSeriesSelect={setAssetManagementUnitSeriesId} />
          <Panel title={l("Источник данных ожидается", "Data source pending")} subtitle={l("Неподтверждённые и демонстрационные показатели не рассчитываются.", "Unverified and demonstration metrics are not calculated.")}>
            <EmptyState title={l("Функциональность пока недоступна", "Functionality is not available yet")} detail={data.disclosure} action={<ShieldAlert aria-hidden="true" />} />
            {data.records.readiness?.length ? <ReadinessChecklist rows={data.records.readiness} /> : null}
          </Panel>
      </PageFrame>
    );
  }
  const cards = domainCards(kind, data, language, includeRepo, term, incomeStatementPeriod);
  const sourceRefs = domainSourceRefs(data, language);
  // Older locally persisted demo responses predate this optional field.  A
  // missing list means that no sections are known to be absent, not that the
  // page should fail to render.
  const missingSourceDatasetTypes = data.missing_source_dataset_types ?? [];
  const pageSize = kind === "risk" ? 10 : STANDARD_TABLE_PAGE_SIZE;
  const pageCount = Math.max(1, Math.ceil(searchableRows.length / pageSize));
  const visibleRows = searchableRows.slice(page * pageSize, (page + 1) * pageSize);
  const setSearchTerm = (value: string) => { setTerm(value); setPage(0); };
  const sourceWarnings: SourceWarning[] = [
    ...(data.report_date_mismatch ? [{ title: l("Даты источников не совпадают", "Source dates do not match"), body: `${data.report_dates.map((value) => formatDate(value, language)).join(" · ")}. ${l("Расхождение показано явно; данные не сдвигаются автоматически.", "The mismatch is explicit; dates are never shifted automatically.")}` }] : []),
    ...(data.filename_date_mismatch ? [{ title: l("Дата в имени файла не совпадает с датой внутри книги", "Filename date differs from workbook date"), body: l("Имя файла сохраняется как доказательство, но датой источника считается дата, прочитанная из рабочей книги.", "The filename is retained as evidence; the source date is the date read from the workbook.") }] : []),
    ...(data.selected_source_upload_id ? [{ title: l("Показана историческая версия рабочей книги", "Viewing a historical workbook version"), body: l("Все разделы страницы загружены только из выбранной версии рабочей книги.", "Every page section is loaded only from the selected workbook version."), action: <button className="button button--secondary" type="button" onClick={resetModuleVersion}>{l("Сбросить до последней версии", "Reset to latest")}</button> }] : []),
    ...(data.pinned_dataset_types?.length ? [{ title: l("Показана выбранная версия источника", "Viewing a selected source version"), body: l(`Зафиксировано: ${data.pinned_dataset_types.join(", ")}. Остальные источники остаются текущими.`, `Pinned: ${data.pinned_dataset_types.join(", ")}. Other sources remain current.`), action: <button className="button button--secondary" type="button" onClick={kind === "accounting" ? resetAccountingVersions : resetRiskVersions}>{l("Сбросить до последней версии", "Reset to latest")}</button> }] : []),
    ...(missingSourceDatasetTypes.length ? [{ title: l("В выбранной рабочей книге отсутствуют разделы", "The selected workbook does not contain every section"), body: l(`Не показано: ${missingSourceDatasetTypes.join(", ")}. Данные из других версий не подмешиваются.`, `Not shown: ${missingSourceDatasetTypes.join(", ")}. Data from other versions is not mixed in.`) }] : []),
  ];
  const openSourcePreviewFromTarget = (target: HTMLElement) => {
    // Keep row-level provenance navigation separate from controls embedded in
    // rows (for example the client-card button and any future links/inputs).
    if (target.closest("button, a, input, select, textarea, option")) return;
    const row = target.closest("tr");
    if (!row) return;
    const sourceCell = row.querySelector<HTMLElement>(".source-cell[data-source-row-id]");
    if (!sourceCell) return;
    const sourceRowId = sourceCell.dataset.sourceRowId;
    const sourceCellAddress = sourceCell.dataset.sourceCell;
    const sheetName = sourceCell.dataset.sourceSheetName;
    if (!sourceRowId || !sourceCellAddress || !sheetName) return;
    openSourcePreview({
      source_kind: "row",
      source_row_id: sourceRowId,
      source_cell: sourceCellAddress,
      sheet_name: sheetName,
      workbook_name: sourceCell.dataset.sourceWorkbookName ?? "",
      parser_version: "",
    });
  };
  const handleSourceRowClick = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    // Keep row-level provenance navigation separate from controls embedded in
    // rows (for example the client-card button and any future links/inputs).
    if (target.closest("button, a, input, select, textarea, option")) return;
    openSourcePreviewFromTarget(target);
  };
  const handleSourceRowKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const target = event.target as HTMLElement;
    if (!target.closest("tr[data-source-row]")) return;
    event.preventDefault();
    openSourcePreviewFromTarget(target);
  };
  // Pulled out so the risk page can place it right after the charts (see
  // below) while every other domain keeps its original position further
  // down, without duplicating this large block.
  const mainTablePanel = <Panel title={meta.tableTitle} subtitle={l(`Показано ${visibleRows.length} из ${searchableRows.length} строк; каждая строка сохраняет ссылку на исходную рабочую книгу.`, `${visibleRows.length} of ${searchableRows.length} rows shown; every row retains a source-workbook reference.`)} action={<div className="table-tools"><label className="search-field"><Search aria-hidden="true" /><span className="sr-only">{l("Поиск по строкам", "Search rows")}</span><input value={term} onChange={(event) => setSearchTerm(event.target.value)} placeholder={l("Поиск по строкам", "Search rows")} /></label><SourceRowLegend language={language} />{exporter ? <button className="button button--secondary" type="button" disabled={exportFile.isPending} onClick={() => exportFile.mutate({ termValue: term, includeRepo })}><Download aria-hidden="true" />{exportFile.isPending ? l("Подготовка…", "Preparing…") : l("Экспорт в Excel", "Export to Excel")}</button> : null}</div>}>
    {exportFile.error ? <div className="inline-error" role="alert">{exportFile.error.message}</div> : null}
    {visibleRows.length ? <><DomainTable kind={kind} rows={visibleRows} language={language} onClientDetail={kind === "clients" ? setSelectedClientRecord : undefined} /><div className="table-pagination" ref={mainPagination.ref}><span>{l(`Страница ${page + 1} из ${pageCount} · ${pageSize} строк на странице`, `Page ${page + 1} of ${pageCount} · ${pageSize} rows per page`)}</span><label className="table-pagination__jump"><span>{l("Перейти", "Go to")}</span><select aria-label={l("Выбрать страницу", "Choose page")} value={page} onChange={(event) => { mainPagination.anchor(); setPage(Number(event.target.value)); }}>{Array.from({ length: pageCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label><div><button className="icon-button" type="button" aria-label={l("Предыдущая страница", "Previous page")} disabled={page === 0} onClick={() => { mainPagination.anchor(); setPage((value) => Math.max(0, value - 1)); }}><ChevronLeft aria-hidden="true" /></button><button className="icon-button" type="button" aria-label={l("Следующая страница", "Next page")} disabled={page >= pageCount - 1} onClick={() => { mainPagination.anchor(); setPage((value) => Math.min(pageCount - 1, value + 1)); }}><ChevronRight aria-hidden="true" /></button></div></div></> : <EmptyState title={l("Нет строк для отображения", "No rows to display")} detail={term ? l("Измените поиск.", "Change the search term.") : l("Опубликованный набор содержит только сводные показатели.", "The published dataset contains summary values only.")} />}
  </Panel>;
  return (
    <PageFrame title={meta.title} eyebrow="Portfolio Operations Insight / controlled data" description={meta.description} meta={<DomainSourceMeta data={data} language={language} />} headerAside={sourceWarnings.length ? <SourceWarningSwitcher warnings={sourceWarnings} /> : null} className={`page-stack--source-rows page-stack--source-rows--${language}`} onClick={handleSourceRowClick} onKeyDown={handleSourceRowKeyDown}>
      <DomainVersionBar kind={kind} data={data} pinnable={PINNABLE_KINDS.has(kind)} selectedSourceUploadId={sourceUploadId} onSelect={setSourceUploadId} riskDatasetSelections={riskDatasetSelections} onRiskSelect={(scope, datasetId) => setRiskDatasetSelections((current) => ({ ...current, [scope]: datasetId }))} accountingDatasetSelections={accountingDatasetSelections} onAccountingSelect={(datasetType, datasetId) => setAccountingDatasetSelections((current) => ({ ...current, [datasetType]: datasetId }))} assetManagementUnitSeriesId={assetManagementUnitSeriesId} onAssetManagementUnitSeriesSelect={setAssetManagementUnitSeriesId} />
      {kind === "accounting" ? <TopbarPeriodControl value={incomeStatementPeriod} onChange={setIncomeStatementPeriod} language={language} /> : null}
      <FormulaAuditNotice data={data} language={language} />
      {kind === "accounting" ? <AccountingReconciliationBanner data={data} language={language} /> : null}
      {kind === "brokerage" ? <BrokerageRepoToggle data={data} includeRepo={includeRepo} onChange={(value) => { setIncludeRepo(value); setPage(0); }} language={language} /> : null}
      <div className={`kpi-grid${kind === "brokerage" ? " kpi-grid--brokerage" : ""}`}>{cards.map((card) => <KpiCard key={card.label} label={card.label} value={card.value} basis={card.basis} detail={card.detail} tone={card.tone ?? "neutral"} onBasisClick={() => openProvenance(card.metricCode && treasuryProvenance.data?.metrics[card.metricCode] ? treasuryProvenance.data.metrics[card.metricCode] : domainCardProvenance(card, sourceRefs, language))} />)}</div>
      <DomainCharts kind={kind} data={data} language={language} sourceRefs={sourceRefs} includeRepo={includeRepo} treasuryMetrics={treasuryProvenance.data?.metrics} incomeStatementPeriod={incomeStatementPeriod} />
      {/* Risk wants its main limit-lines table right after the charts, ahead
          of the watchlist/duration/exposure tables in RiskControlsPanel -
          every other domain keeps the table in its original spot below. */}
      {kind === "risk" ? mainTablePanel : null}
      {kind === "asset-management" ? <FundControlsPanel data={data} language={language} /> : null}
      {kind === "risk" ? <RiskControlsPanel data={data} language={language} /> : null}
      {kind === "clients" ? <><ClientMaturityPanel data={data} language={language} /><ClientManagerPanel data={data} language={language} /><ClientIdentityExceptionPanel /></> : null}
      {kind === "treasury" ? <TreasuryDetailLinks language={language} /> : kind === "risk" ? null : mainTablePanel}
      {kind === "brokerage" ? <BrokerageDerivativesPanel data={data} language={language} /> : null}
      {kind === "accounting" ? <>
        <AccountingIncomeStatementPanel data={data} language={language} />
        <AccountingComparabilityNotice language={language} />
        <AccountingBudgetSectionPanel data={data} language={language} section="income_statement" />
        <AccountingBudgetSectionPanel data={data} language={language} section="cash_flow" />
        <AccountingBudgetSectionPanel data={data} language={language} section="balance" />
        <AccountingPortfolioPanel data={data} language={language} />
        <AccountMappingPanel data={data} language={language} />
      </> : null}
      {kind === "risk" || kind === "accounting" ? <ActionItemsPanel domain={kind} language={language} /> : null}
      {kind === "clients" && selectedClientRecord ? <div ref={clientDetailRef} tabIndex={-1}><ClientDetailPanel recordId={selectedClientRecord} onClose={() => setSelectedClientRecord(null)} /></div> : null}
      <div className="unavailable-note">{data.disclosure}</div>
    </PageFrame>
  );
}

function domainExporter(
  kind: DomainKind, riskDatasetVersions: string[], accountingDatasetVersions: string[], assetManagementUnitSeriesId: string | null
): ((term: string, includeRepo: boolean, sourceUploadId?: string) => Promise<void>) | null {
  if (kind === "asset-management") return (term, _includeRepo, sourceUploadId) => dashboardApi.exportFundData(term, sourceUploadId, assetManagementUnitSeriesId ? [assetManagementUnitSeriesId] : undefined);
  if (kind === "brokerage") return (term, includeRepo, sourceUploadId) => dashboardApi.exportBrokerageData(term, includeRepo, sourceUploadId);
  if (kind === "corporate-finance") return (term) => dashboardApi.exportCorporateFinanceData(term);
  if (kind === "risk") return (term) => dashboardApi.exportRiskData(term, riskDatasetVersions);
  if (kind === "accounting") return (term) => dashboardApi.exportAccountingData(term, accountingDatasetVersions);
  return null;
}

function TopbarPeriodControl({ value, onChange, language }: { value: IncomeStatementPeriod; onChange: (value: IncomeStatementPeriod) => void; language: "ru" | "en" }) {
  // Portaled into the topbar (see AppShell.tsx) rather than the domain
  // version bar below the page content, by request - unlike the version
  // pickers there (rarely touched, since the default is always the latest
  // published data), this control changes what every KPI card and chart on
  // the page shows and is used on every visit, so it leads the persistent
  // header instead.
  const slot = typeof document !== "undefined" ? document.getElementById("topbar-page-control-slot") : null;
  return slot ? createPortal(<AccountingPeriodToggle value={value} onChange={onChange} language={language} />, slot) : null;
}

function DomainVersionBar({ kind, data, pinnable, selectedSourceUploadId, onSelect, riskDatasetSelections, onRiskSelect, accountingDatasetSelections, onAccountingSelect, assetManagementUnitSeriesId, onAssetManagementUnitSeriesSelect }: { kind: DomainKind; data: ModuleReadResponse; pinnable: boolean; selectedSourceUploadId: string | null; onSelect: (sourceUploadId: string | null) => void; riskDatasetSelections: Record<string, string | null>; onRiskSelect: (scopeCode: string, datasetId: string | null) => void; accountingDatasetSelections: Record<string, string | null>; onAccountingSelect: (datasetType: string, datasetId: string | null) => void; assetManagementUnitSeriesId: string | null; onAssetManagementUnitSeriesSelect: (datasetId: string | null) => void }) {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const anchorType = MODULE_ANCHOR_DATASET_TYPE[kind] ?? data.sources[0]?.dataset_type;
  const anchorSource = data.sources.find((source) => source.dataset_type === anchorType);
  const slot = typeof document !== "undefined" ? document.getElementById("domain-version-bar-slot") : null;
  if (!pinnable || !slot) return null;
  // Portaled into the shell's dedicated slot (see AppShell.tsx), below the
  // page content rather than above it - by request, since the default is
  // always the latest published data and this is rarely touched day to day,
  // it doesn't need to sit above everything else on every visit.
  // One control selects one uploaded workbook package.  Its child datasets
  // travel together; the page never reconstructs a brokerage/clients view
  // by combining ledger, register and snapshot versions independently.
  const content = kind === "risk"
    ? <RiskVersionPickerBar data={data} selections={riskDatasetSelections} onSelect={onRiskSelect} language={language} />
    : kind === "accounting"
    ? <AccountingVersionPickerBar data={data} selections={accountingDatasetSelections} onSelect={onAccountingSelect} language={language} />
    : kind === "asset-management"
    ? <AssetManagementVersionPickerBar data={data} selectedSourceUploadId={selectedSourceUploadId} onSelectPackage={onSelect} selectedUnitSeriesId={assetManagementUnitSeriesId} onSelectUnitSeries={onAssetManagementUnitSeriesSelect} language={language} />
    : kind === "treasury"
      ? <TreasuryVersionPicker source={anchorSource} selectedSourceUploadId={selectedSourceUploadId} onSelect={onSelect} language={language} />
      : !anchorSource ? null : <section className="filterbar filterbar--domain-version" aria-label={l("Версия данных", "Data version")}>
        <label className="filterbar__snapshot">
          <span>{l("Версия рабочей книги", "Workbook version")}</span>
          <VersionPicker source={anchorSource} selectedSourceUploadId={selectedSourceUploadId} onSelect={onSelect} language={language} />
        </label>
        <small>{l("Одна версия применяется ко всем разделам этой области.", "One version is applied to every section in this domain.")}</small>
      </section>;
  return content ? createPortal(content, slot) : null;
}

// Same substring-match rule the Excel export's _matches_term uses (scan
// every field's stringified value) - shared by the row table and the KPI
// cards below so a search term narrows both identically, instead of the
// cards silently continuing to summarize every row while the table below
// them shows only a filtered subset.
function matchesSearchTerm(row: Row, normalizedTerm: string): boolean {
  if (!normalizedTerm) return true;
  return Object.values(row).some((value) => String(value ?? "").toLocaleLowerCase().includes(normalizedTerm));
}

function domainRows(kind: DomainKind, data: ModuleReadResponse): Row[] {
  const records = data.records as Record<string, Row[]>;
  if (kind === "asset-management") return records.fund_holdings ?? [];
  if (kind === "brokerage") {
    // "Recent trades" implies newest-first; the source workbook otherwise
    // dictates row order. Same sort key as the Excel export's ledger sheet
    // (multi_source_export.py) so the two agree.
    return [...(records.brokerage_trade_ledger ?? [])].sort((a, b) => {
      const byDate = String(b.trade_date ?? "").localeCompare(String(a.trade_date ?? ""));
      return byDate !== 0 ? byDate : String(b.trade_number ?? "").localeCompare(String(a.trade_number ?? ""));
    });
  }
  if (kind === "clients") {
    // The account register (Лист4) carries the client identity and balances,
    // while the companion Клиенты sheet carries manager assignments. Join
    // them for display without replacing either source dataset. Branch is
    // intentionally left untouched: the supplied workbook has no branch
    // values, so the UI must continue to show it as unavailable rather than
    // infer one.
    const normalizeClientName = (value: unknown) => String(value ?? "").trim().replace(/\s+/g, " ").toLocaleUpperCase();
    const managers = new Map<string, string>();
    for (const row of records.client_dashboard_snapshot ?? []) {
      const name = normalizeClientName(row.client_name);
      const manager = String(row.manager ?? "").trim();
      if (name && manager && manager !== "Не указано") managers.set(name, manager);
    }
    return (records.client_account_snapshot ?? [])
      .filter((row) => row.record_type === "client")
      .map((row) => {
        const existingManager = String(row.manager ?? "").trim();
        const manager = existingManager && existingManager !== "Не указано"
          ? existingManager
          : managers.get(normalizeClientName(row.client_name)) || row.manager;
        return { ...row, manager };
      });
  }
  if (kind === "corporate-finance") return records.corporate_finance_register ?? [];
  if (kind === "accounting") return records.accounting_balance_sheet ?? [];
  if (kind === "risk") return [...(records.risk_limits_sobstv ?? []), ...(records.risk_limits_tabys ?? [])].filter((row) => row.dimension !== "exposure_detail" && row.dimension !== "country_instrument_detail");
  return [];
}

function domainCards(kind: DomainKind, data: ModuleReadResponse, language: "ru" | "en", includeRepo = true, term = "", incomeStatementPeriod: IncomeStatementPeriod = "quarter") {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const s = data.summaries as Record<string, Record<string, unknown>>;
  const records = data.records as Record<string, Row[]>;
  const idsOf = (rows: Row[]) => rows.map((row) => String(row.id));
  const byType = (dataset: string, recordType: string) => (records[dataset] ?? []).filter((row) => String(row.record_type) === recordType);
  const normalizedTerm = term.trim().toLocaleLowerCase();
  const matches = (row: Row) => matchesSearchTerm(row, normalizedTerm);
  if (kind === "asset-management") {
    const v = s.fund_valuation ?? {}; const u = s.fund_unit_series ?? {};
    const valuationRecords = records.fund_valuation ?? [];
    // NAV/unit value/securities are fund-level aggregates, not per-holding
    // figures - a search term doesn't meaningfully narrow them, same call
    // the Excel export's own summary sheet makes (see fund.py). Only the
    // holding count below is per-instrument, so only it gets filtered.
    const holdingRecords = (records.fund_holdings ?? []).filter(matches);
    return [
      card(l("СЧА из источника", "Source-reported NAV"), money(v.nav_kzt, language), "source", "", undefined, idsOf(valuationRecords), ["nav_kzt"]),
      card(l("Стоимость пая", "Unit value"), money(v.unit_value_kzt, language), "source", "", undefined, idsOf(valuationRecords), ["unit_value_kzt"]),
      card(l("Ценные бумаги", "Securities"), money(v.securities_value_kzt, language), "source", "", undefined, idsOf(valuationRecords), ["securities_value_kzt"]),
      // "Лотов"/"Lots", not "Позиций"/"Holdings": this counts every parsed
      // holding row, including repeat purchases of the same instrument on
      // different dates as separate lots - Excel's only comparable sheet
      // ("Уникальные позиции ETF") counts distinct instruments instead, a
      // genuinely different number (confirmed on real data: 15 lots vs 12
      // unique ISINs). Same label on both would make them look like the
      // same metric when they aren't.
      card(l("Лотов", "Lots"), String(holdingRecords.length), "source", String(u.latest_date ?? ""), undefined, idsOf(holdingRecords)),
    ];
  }
  if (kind === "treasury") { const v = s.portfolio_snapshot ?? {}; return [card(l("Операционный итог", "Operational total"), money(v.derived_operational_total_kzt, language), "derived", "", "derived_operational_total_kzt"), card(l("Расчётная стоимость", "Derived carrying value"), money(v.derived_carrying_value_kzt, language), "derived", "", "derived_carrying_value_kzt"), card(l("Деньги", "Cash"), money(v.cash_kzt, language), "source", "", "cash_kzt"), card(l("Инструменты", "Instruments"), String(v.unique_isin_count ?? "—"), "source", "", "unique_isin_count")]; }
  if (kind === "brokerage") {
    const t = records.brokerage_trade_ledger ?? [];
    // Same term+repo filtering the Excel export's own summary sheet applies
    // before it tallies trades/turnover (see brokerage.py) - otherwise
    // these cards keep summarizing every trade while the table below them
    // narrows to the search term.
    const visibleTrades = t.filter((row) => (includeRepo || !isRepoTrade(row)) && matches(row));
    // KZT-equivalent, not KZT-only: same NBK-rate conversion the Excel
    // export's turnover table uses (amount * fx_rates_kzt[currency]), so the
    // web card and the export agree instead of the web card silently
    // ignoring every FX-denominated trade.
    const fxRatesKzt = (s.brokerage_trade_ledger?.fx_rates_kzt ?? {}) as Record<string, string>;
    const convertibleTrades = visibleTrades.filter((row) => {
      const currency = String(row.currency ?? "").trim();
      return currency === "KZT" || fxRatesKzt[currency] !== undefined;
    });
    const turnover = convertibleTrades.reduce((sum, row) => {
      const currency = String(row.currency ?? "").trim();
      const amount = Math.abs(Number(row.amount) || 0);
      return currency === "KZT" ? sum + amount : sum + amount * Number(fxRatesKzt[currency]);
    }, 0);
    const uniqueClients = new Set(visibleTrades.map((row) => String(row.client_name ?? row.account ?? "").trim()).filter(Boolean)).size;
    const c = s.client_account_snapshot ?? {}; const d = s.derivatives_register ?? {};
    const clientRecords = byType("client_account_snapshot", "client");
    const derivativeRecords = records.derivatives_register ?? [];
    return [
      card(l("Сделки", "Trades"), String(visibleTrades.length), "source", includeRepo ? l("РЕПО включены", "Repo included") : l("РЕПО исключены", "Repo excluded"), undefined, idsOf(visibleTrades)),
      card(l("Оборот, экв. KZT", "KZT-equivalent turnover"), formatKzt(String(turnover), language), "derived", l("Конвертировано по курсу НБК", "Converted at the NBK rate"), undefined, idsOf(convertibleTrades), ["amount"]),
      card(l("Уникальные клиенты", "Unique clients"), String(uniqueClients), "source", l("Имя клиента; при отсутствии счёт", "Client name; account when unavailable"), undefined, idsOf(visibleTrades), ["client_name", "account"]),
      card(l("Клиентские активы", "Client assets"), money(c.total_assets_kzt, language), "source", "", undefined, idsOf(clientRecords)),
      card(l("Производные", "Derivatives"), String(d.derivative_count ?? "—"), "source", "", undefined, idsOf(derivativeRecords)),
    ];
  }
  if (kind === "clients") {
    const clientRecords = byType("client_account_snapshot", "client").filter(matches);
    const maturityRecords = (records.client_maturity_calendar ?? []).filter(matches);
    // The account snapshot's own precomputed totals are frequently
    // incomplete (see clients.py) - the dashboard snapshot carries the same
    // figures per real client row, so sum fresh from its filtered records
    // the same way the Excel export's "Аналитика клиентов" sheet does,
    // falling back to the account snapshot only when no dashboard data was
    // published.
    const dashboardRecords = (records.client_dashboard_snapshot ?? []).filter(matches);
    const totalsSource = dashboardRecords.length ? dashboardRecords : clientRecords;
    const totalAssets = totalsSource.reduce((sum, row) => sum + (Number(row.total_assets_kzt) || 0), 0);
    const totalCash = totalsSource.reduce((sum, row) => sum + (Number(row.cash_kzt) || 0), 0);
    const maturityDates = maturityRecords.map((row) => String(row.maturity_date ?? "")).filter(Boolean).sort();
    return [
      card(l("Клиенты", "Clients"), String(clientRecords.length), "source", "", undefined, idsOf(clientRecords)),
      card(l("Активы", "Assets"), money(totalAssets, language), "source", "", undefined, idsOf(totalsSource), ["total_assets_kzt"]),
      card(l("Деньги", "Cash"), money(totalCash, language), "source", "", undefined, idsOf(totalsSource), ["cash_kzt"]),
      card(l("События погашения", "Maturity events"), String(maturityRecords.length), "source", maturityDates[0] ?? "", undefined, idsOf(maturityRecords)),
    ];
  }
  if (kind === "risk") {
    const sobstv = s.risk_limits_sobstv ?? {}; const tabys = s.risk_limits_tabys ?? {};
    const totalLimits = Number(sobstv.limit_count ?? 0) + Number(tabys.limit_count ?? 0);
    const totalBreaches = Number(sobstv.breach_count ?? 0) + Number(tabys.breach_count ?? 0);
    const totalUnknown = Number(sobstv.unknown_count ?? 0) + Number(tabys.unknown_count ?? 0);
    const totalNotApplicable = Number(sobstv.not_applicable_count ?? 0) + Number(tabys.not_applicable_count ?? 0);
    const durationCount = Number(sobstv.duration_count ?? 0) + Number(tabys.duration_count ?? 0);
    // Each card's evidence must be the records that actually make up its
    // number - otherwise every card (Limit lines, Breaches, Duration
    // controls, ...) shows the exact same unfiltered list of every risk
    // record, and clicking "why is this a breach" surfaces unrelated
    // country/sector/IFRS rows alongside the real answer.
    const records = data.records as Record<string, Row[]>;
    const controlRecords = [...(records.risk_limits_sobstv ?? []), ...(records.risk_limits_tabys ?? [])]
      .filter((row) => row.dimension !== "exposure_detail" && row.dimension !== "country_instrument_detail");
    const idsWhere = (predicate: (row: Row) => boolean) => controlRecords.filter(predicate).map((row) => String(row.id));
    // The field(s) that actually determine each card's number - used to point
    // a card's evidence at the cell that matters (e.g. the breached amount)
    // rather than always the record's classification label. Listed in
    // preference order since which field applies varies by dimension (a
    // country row breaches on USD, most others on KZT; duration breaches on
    // modified_duration, not an amount at all).
    const breachFields = ["actual_kzt", "actual_usd", "modified_duration"];
    const durationFields = ["modified_duration"];
    return [
      card(l("Лимитных строк", "Limit lines"), String(totalLimits), "source", "", undefined, controlRecords.map((row) => String(row.id))),
      card(l("Превышений лимита", "Breaches"), String(totalBreaches), "source", totalBreaches ? l("Требует внимания", "Needs attention") : l("Превышений не обнаружено", "No breaches detected"), undefined, idsWhere((row) => row.signal === "breach"), breachFields, totalBreaches ? "danger" : "neutral"),
      (() => {
        const nearBreachIds = idsWhere(isRiskNearBreach);
        const thresholdPercent = riskNearBreachThreshold(controlRecords) * 100;
        // A count here - zero or not - is always a real, sourced fact about
        // the published control rows, not a missing input; "unavailable"
        // would incorrectly claim the underlying data doesn't exist (see
        // BasisBadge's fixed copy for that label) when it plainly does,
        // right there in nearBreachIds.
        return card(l(`Близко к превышению (≥${thresholdPercent}%)`, `Near-breach (≥${thresholdPercent}%)`), String(nearBreachIds.length), "source", l(`Использование лимита ${thresholdPercent}% и выше, но ещё не превышение`, `${thresholdPercent}%+ limit utilization, not yet a breach`), undefined, nearBreachIds, breachFields, nearBreachIds.length ? "warning" : "neutral");
      })(),
      card(l("Статус не определён", "Unknown status"), String(totalUnknown), "source", totalUnknown ? l("Нельзя считать строку безопасной", "Cannot treat the line as safe") : l("Все контрольные строки классифицированы", "All control lines classified"), undefined, idsWhere((row) => row.signal == null), breachFields),
      card(l("Без применимого лимита", "No applicable limit"), String(totalNotApplicable), "source", l("Информативные строки источника", "Informational source rows"), undefined, idsWhere((row) => row.signal === "not_applicable"), breachFields),
      card(l("Контроли дюрации", "Duration controls"), String(durationCount), "source", l("Из отдельного листа дюрации", "From the duration sheet"), undefined, idsWhere((row) => row.dimension === "duration"), durationFields),
      card(l("SOBSTV: превышений", "SOBSTV: breaches"), sobstv.limit_count != null ? String(sobstv.breach_count ?? 0) : "—", "source", "", undefined, idsWhere((row) => row.signal === "breach" && row.portfolio_code === "SOBSTV"), breachFields),
      card(l("TABYS: превышений", "TABYS: breaches"), tabys.limit_count != null ? String(tabys.breach_count ?? 0) : "—", "source", "", undefined, idsWhere((row) => row.signal === "breach" && row.portfolio_code === "TABYS"), breachFields),
    ];
  }
  if (kind === "accounting") {
    const portfolio = s.accounting_portfolio_detail ?? {};
    // The precomputed dataset.summary is an ingestion-time aggregate over
    // ALL rows - using it regardless of the search term made these cards
    // silently disagree with the filtered detail tables below. Recompute
    // each total from the same term-filtered "итого ..." line the Excel
    // export's "Сводка ФО" sheet reads (see accounting.py's total()).
    const balanceSheetRecords = (records.accounting_balance_sheet ?? []).filter(matches);
    const incomeStatementRecords = (records.accounting_income_statement ?? []).filter(matches);
    const portfolioRecords = records.accounting_portfolio_detail ?? [];
    const total = (rows: Row[], label: string, field: string): number | null => {
      for (const row of rows) {
        if (String(row.line_label ?? "").trim().toLocaleLowerCase() !== label) continue;
        const value = row[field];
        if (value !== null && value !== undefined && value !== "") return Number(value);
      }
      return null;
    };
    const totalAssets = total(balanceSheetRecords, "итого активы", "current_period_kzt");
    const totalLiabilities = total(balanceSheetRecords, "итого обязательства", "current_period_kzt");
    const totalEquity = total(balanceSheetRecords, "итого капитал", "current_period_kzt");
    // The income statement is a flow-over-a-period figure, unlike the
    // balance sheet's point-in-time snapshot above - the source workbook
    // carries a separate column for each of "quarter" and "YTD" per line
    // (see AccountingPeriodToggle), so which one these three cards show is
    // a real toggle, not a fixed quarter.
    const incomeField = `${incomeStatementPeriod}_kzt`;
    const totalIncome = total(incomeStatementRecords, "итого доходов", incomeField);
    const totalExpenses = total(incomeStatementRecords, "итого расходов", incomeField);
    const netProfit = total(incomeStatementRecords, "чистая прибыль (убыток) до уплаты корпоративного подоходного налога", incomeField);
    const incomeCardLabel = (ruSuffix: string, enSuffix: string) => incomeStatementPeriod === "ytd"
      ? l(`${ruSuffix} с начала года`, `${enSuffix} YTD`)
      : l(`${ruSuffix} за квартал`, `${enSuffix} for the quarter`);
    return [
      card(l("Активы всего", "Total assets"), moneyThousands(totalAssets, language), "source", "", undefined, idsOf(balanceSheetRecords), ["current_period_kzt"]),
      card(l("Обязательства всего", "Total liabilities"), moneyThousands(totalLiabilities, language), "source", "", undefined, idsOf(balanceSheetRecords), ["current_period_kzt"]),
      card(l("Капитал всего", "Total equity"), moneyThousands(totalEquity, language), "source", "", undefined, idsOf(balanceSheetRecords), ["current_period_kzt"]),
      card(incomeCardLabel("Доходы", "Income"), moneyThousands(totalIncome, language), "source", "", undefined, idsOf(incomeStatementRecords), [incomeField]),
      card(incomeCardLabel("Расходы", "Expenses"), moneyThousands(totalExpenses, language), "source", "", undefined, idsOf(incomeStatementRecords), [incomeField]),
      card(incomeCardLabel("Чистая прибыль", "Net profit"), moneyThousands(netProfit, language), "source", "", undefined, idsOf(incomeStatementRecords), [incomeField]),
      card(l("Балансовая стоимость портфеля", "Portfolio carrying value"), portfolio.total_carrying_value_kzt != null ? money(portfolio.total_carrying_value_kzt, language) : l("Недоступно", "Unavailable"), portfolio.total_carrying_value_kzt != null ? "source" : "unavailable", l("Отдельный источник от баланса; суммы не сверяются построчно", "A separate source from the balance sheet; not reconciled line-for-line"), undefined, idsOf(portfolioRecords), ["carrying_value_kzt"]),
    ];
  }
  const d = s.corporate_finance_register ?? {};
  // deal_count/active_count are ingestion-time aggregates over every deal -
  // recompute from the term-filtered record set, the same fix corporate_finance.py's
  // own summary sheet applies (see its comment on why the raw dataset.summary can't be trusted here).
  const dealRecords = (records.corporate_finance_register ?? []).filter(matches);
  const activeDeals = dealRecords.filter((row) => Boolean(row.active));
  return [
    card(l("Сделки/мандаты", "Deals/mandates"), String(dealRecords.length), "source", "", undefined, idsOf(dealRecords)),
    card(l("Действующие", "Active"), String(activeDeals.length), "source", "", undefined, idsOf(activeDeals), ["duration_raw", "active"]),
    card(l("Период", "Period"), String(d.period ?? "—"), "source", "", undefined, idsOf(dealRecords)),
    card(l("Прогноз pipeline", "Pipeline forecast"), l("Недоступно", "Unavailable"), "unavailable"),
  ];
}

function domainMeta(kind: DomainKind, language: "ru" | "en") {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const values = {
    "asset-management": [l("Управление активами", "Asset management"), l("СЧА, стоимость пая, история и состав TABYS из независимо опубликованных источников.", "TABYS NAV, unit value, history and holdings from independently published sources."), l("Портфель фонда", "Fund portfolio")],
    treasury: [l("Казначейство", "Treasury"), l("Собственный портфель, деньги и расчётные показатели OSIP.", "Own portfolio, cash and OSIP-derived measures."), l("Позиции", "Holdings")],
    brokerage: [l("Брокерская деятельность", "Brokerage"), l("Клиентские активы, сделки, площадки и исполнение из брокерского пакета.", "Client assets, trades, venues and execution from the brokerage pack."), l("Последние сделки", "Recent trades")],
    clients: [l("Клиенты", "Clients"), l("Клиентские счета, менеджеры, активы и даты открытия.", "Client accounts, managers, assets and opening dates."), l("Клиентский реестр", "Client register")],
    "corporate-finance": [l("Корпоративные финансы", "Corporate finance"), l("Контролируемый реестр мандатов и полученного вознаграждения.", "Controlled register of mandates and received fees."), l("Сделки и мандаты", "Deals and mandates")],
    accounting: [l("Бухгалтерия", "Accounting"), l("Бухгалтерский баланс и отчёт о прибылях и убытках из опубликованной финансовой отчётности.", "Balance sheet and income statement from the published financial statements."), l("Бухгалтерский баланс", "Balance sheet")],
    risk: [l("Риски и лимиты", "Risk and limits"), l("Лимиты инвестирования по SOBSTV и TABYS: утверждённые пороги, фактическое использование и статус по странам, валютам, открытой валютной позиции, эмитентам, отраслям, классам инструментов, дюрации и классификации МСФО.", "Investment limits for SOBSTV and TABYS: approved thresholds, actual usage, and status by country, currency, open FX position, issuer, sector, instrument category, duration, and IFRS classification."), l("Лимитные строки", "Limit lines")]
  }[kind];
  return { title: values[0], description: values[1], tableTitle: values[2] };
}
