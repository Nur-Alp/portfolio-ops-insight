import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookMarked, CheckCheck, Download, FileSpreadsheet, GitCompareArrows, Upload } from "lucide-react";
import { useState } from "react";
import type { DatasetVersion, ImportRecord, SourceUpload } from "../api/types";
import { dashboardApi } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { BasisBadge } from "../components/ui/BasisBadge";
import { DatasetVersionComparison } from "../components/ui/DatasetVersionComparison";
import { Drawer } from "../components/ui/Drawer";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { formatDate, formatKzt } from "../lib/format";
import { useI18n } from "../i18n";
import { getCurrentDomainScope } from "../auth/session";
import { PageFrame } from "../components/ui/PageFrame";
import { TableSearch } from "../components/ui/TableSearch";

export function ImportsPage() {
  const { language, t } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const domainScope = getCurrentDomainScope();
  const osipEnabled = domainScope === "*" || domainScope === "back_office";
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<ImportRecord | null>(null);
  const [actionError, setActionError] = useState("");
  const [portfolioCode, setPortfolioCode] = useState("");
  const [portfolioName, setPortfolioName] = useState("");
  const [withdrawReason, setWithdrawReason] = useState("");
  const [approveReason, setApproveReason] = useState("");
  const imports = useQuery({ queryKey: ["imports", domainScope], queryFn: dashboardApi.imports, enabled: osipEnabled });
  const comparison = useQuery({ queryKey: ["comparison", selected?.id], queryFn: () => dashboardApi.comparison(selected!.id), enabled: Boolean(selected?.snapshot_id) });
  const issues = useQuery({ queryKey: ["issues", selected?.snapshot_id], queryFn: () => dashboardApi.issues(selected!.snapshot_id!), enabled: Boolean(selected?.snapshot_id) });
  const refresh = async (result?: ImportRecord) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["imports"] }),
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
    ]);
    if (result) setSelected(result);
  };
  const upload = useMutation({ mutationFn: dashboardApi.upload, onSuccess: refresh, onError: (error) => setActionError(error.message) });
  const approve = useMutation({ mutationFn: ({ id, codes, comment }: { id: string; codes: string[]; comment: string }) => dashboardApi.approve(id, codes, comment), onSuccess: async (result) => { setApproveReason(""); await refresh(result); }, onError: (error) => setActionError(error.message) });
  const publish = useMutation({ mutationFn: dashboardApi.publish, onSuccess: refresh, onError: (error) => setActionError(error.message) });
  const withdraw = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => dashboardApi.withdraw(id, reason), onSuccess: async (result) => { setWithdrawReason(""); await refresh(result); }, onError: (error) => setActionError(error.message) });
  const exportRegistry = useMutation({ mutationFn: dashboardApi.exportImportRegistry, onError: (error) => setActionError(error.message) });
  if (osipEnabled && imports.isLoading) return <LoadingState label={l("Загрузка неизменяемого реестра загрузок", "Loading immutable upload registry")} />;
  if (osipEnabled && imports.error) return <ErrorState error={imports.error} retry={() => imports.refetch()} />;
  const records = imports.data?.items ?? [];
  const requiredCodes = [...new Set((issues.data?.items ?? []).filter((issue) => ["blocker", "high"].includes(issue.severity)).map((issue) => issue.code))];

  if (!osipEnabled) return <PageFrame title={l("Загрузки источников", "Source uploads")} eyebrow={l("Portfolio Operations Insight / Контролируемые источники", "Portfolio Operations Insight / controlled sources")} description={l("Загружайте рабочие книги текущей области. Тип источника и независимые наборы определяются по содержимому.", "Upload workbooks for the current domain. Source type and independent datasets are detected from workbook content.")}><MultiSourceUploadPanel /></PageFrame>;

  return (
    <PageFrame title={l("Загрузки источников", "Source uploads")} eyebrow={l("OSIP / Контролируемая загрузка", "OSIP / controlled upload")} description={l("Загружайте, проверяйте, сравнивайте, независимо утверждайте и публикуйте неизменяемые подтверждения из рабочих книг.", "Upload, validate, compare, independently approve, and publish immutable evidence from source workbooks.")}>
      <MultiSourceUploadPanel />
      <Panel title={l("Загрузить рабочую книгу OSIP", "Upload OSIP workbook")} subtitle={l("Имя файла сохраняется как доказательство, но не определяет портфель или дату. Код портфеля назначает ответственный сотрудник; дата считывается из рабочей книги.", "The filename is retained as evidence but does not determine the portfolio or date. A responsible user assigns the portfolio code; the report date is read from the workbook.")}>
        <div className="upload-assignment">
          <label>{l("Код портфеля", "Portfolio code")}<input value={portfolioCode} onChange={(event) => setPortfolioCode(event.target.value.toUpperCase())} placeholder={l("Введите код, например SOBSTV", "Enter a code, for example SOBSTV")} maxLength={16} required /></label>
          <label>{l("Наименование нового портфеля", "New portfolio name")} <input value={portfolioName} onChange={(event) => setPortfolioName(event.target.value)} placeholder={l("Только при новом коде", "Only for a new code")} maxLength={120} /></label>
        </div>
        <label className={`upload-zone ${upload.isPending ? "upload-zone--busy" : ""}`}>
          <Upload aria-hidden="true" /><strong>{upload.isPending ? l("Проверка рабочей книги…", "Validating workbook…") : l("Выберите рабочую книгу OSIP .xls", "Choose an OSIP .xls workbook")}</strong><span>{l("Сначала укажите код портфеля: имя файла не используется для его определения. Оригинал сохраняется по SHA-256; идентичное содержимое не создаёт дубликат.", "Enter the portfolio code first: the filename is not used to identify it. The original is retained by SHA-256; identical content does not create a duplicate.")}</span><input type="file" accept=".xls,application/vnd.ms-excel" disabled={upload.isPending || !portfolioCode.trim()} onChange={(event) => { const file = event.target.files?.[0]; if (file) { setActionError(""); upload.mutate({ file, portfolioCode, portfolioName }); } event.target.value = ""; }} />
        </label>
        {actionError ? <div className="inline-error" role="alert">{actionError}</div> : null}
      </Panel>
      <ReferenceDictionaryPanel />
      <DividendDataPanel />
      <Panel title={l("Реестр загрузок", "Upload registry")} subtitle={l(`${records.length} неизменяемых версий; отклонённые и ошибочные подтверждения сохраняются`, `${records.length} immutable versions; rejected and failed evidence is retained`)} action={<div className="table-tools"><TableSearch label={l("Поиск реестра загрузок", "Search upload registry")} placeholder={l("Файл, портфель, статус", "File, portfolio, status")} /><button className="button button--secondary table-tools__export" type="button" disabled={exportRegistry.isPending} onClick={() => { setActionError(""); exportRegistry.mutate(); }}><Download aria-hidden="true" /> {exportRegistry.isPending ? t("common.prepare") : t("common.exportExcel")}</button></div>}>
        {exportRegistry.error ? <div className="inline-error" role="alert">{exportRegistry.error.message}</div> : null}
        {records.length ? <div className="table-scroll" tabIndex={0}><table className="clickable-table"><thead><tr><th>{l("Файл источника", "Source file")}</th><th>{t("filter.portfolio")}</th><th>{l("Отчётная дата", "Report date")}</th><th>{l("Версия", "Version")}</th><th>{l("Статус", "Status")}</th><th>{t("holding.lots")}</th><th>DQ: {l("блок./высокие", "blocker/high")}</th><th>{l("Загрузил", "Uploaded by")}</th></tr></thead><tbody>{records.map((record) => <tr key={record.id} tabIndex={0} onClick={() => { setSelected(record); setActionError(""); }} onKeyDown={(event) => { if (event.key === "Enter") setSelected(record); }}><td><strong><FileSpreadsheet className="table-icon" /> {record.original_filename}</strong><small>{record.source_sha256.slice(0, 12)}…</small></td><td>{record.portfolio ?? l("Не определён", "Unassigned")}</td><td>{formatDate(record.report_date, language)}</td><td>{record.version ?? "—"}</td><td><StatusPill status={record.status} /></td><td>{record.summary?.position_count ?? "—"}</td><td>{(record.dq_counts.blocker ?? 0) + (record.dq_counts.high ?? 0)}</td><td>{record.uploader_id}</td></tr>)}</tbody></table></div> : <EmptyState title={l("Загрузок пока нет", "No uploads yet")} detail={l("Загрузите любую из предоставленных рабочих книг OSIP, чтобы создать первую проверенную версию портфеля.", "Upload an OSIP workbook to create the first validated portfolio version.")} />}
      </Panel>
      <Drawer open={Boolean(selected)} onClose={() => { setSelected(null); setWithdrawReason(""); setApproveReason(""); }} title={selected?.original_filename ?? l("Загрузка", "Upload")} subtitle={selected ? `${selected.portfolio ?? l("Не определён", "Unassigned")} · ${formatDate(selected.report_date, language)}` : undefined}>
        {selected ? <div className="drawer-stack"><div className="drawer-summary"><div><span>{l("Статус", "Status")}</span><StatusPill status={selected.status} /></div><div><span>{l("Версия", "Version")}</span><strong>{selected.version ?? "—"}</strong></div><div><span>{l("Загрузил", "Uploaded by")}</span><strong>{selected.uploader_id}</strong></div><div><span>SHA-256</span><strong>{selected.source_sha256.slice(0, 16)}…</strong></div></div>{selected.error_message ? <div className="inline-error">{selected.error_message}</div> : null}{selected.summary ? <div className="drawer-section"><h3>{l("Проверенный предварительный просмотр", "Validated preview")}</h3><p>{selected.summary.position_count} {l("лотов", "lots")} · {selected.summary.unique_isin_count} {l("инструментов", "instruments")} · {l("операционный итог", "operational total")} {formatKzt(selected.summary.derived_operational_total_kzt, language)}.</p></div> : null}{comparison.data ? <div className="comparison-card"><header><GitCompareArrows /><strong>{comparison.data.baseline ? l(`Сравнение с версией ${comparison.data.baseline.version}`, `Compared with version ${comparison.data.baseline.version}`) : l("Первая утверждённая версия для сравнения недоступна", "No first approved version is available for comparison")}</strong></header><div><span>{l("Добавлено лотов", "Lots added")}</span><strong>{comparison.data.lot_changes.added_count}</strong><span>{l("Удалено лотов", "Lots removed")}</span><strong>{comparison.data.lot_changes.removed_count}</strong><span>{l("Без изменений", "Unchanged")}</span><strong>{comparison.data.lot_changes.unchanged_count}</strong></div>{comparison.data.baseline ? <p>{l("Изменение операционного итога", "Operational total change")}: {formatKzt(comparison.data.metrics.derived_operational_total_kzt.delta as string, language)}</p> : null}</div> : null}<div className="workflow-actions">{selected.status === "validated" ? <div className="assignment-form"><label>{l("Обоснование утверждения", "Approval justification")}<textarea value={approveReason} onChange={(event) => setApproveReason(event.target.value)} placeholder={l("Например: проверены все блокирующие/высокие замечания DQ, расхождений с рабочей книгой не выявлено", "For example: reviewed all blocker/high DQ findings, no discrepancies found against the workbook")} maxLength={4000} /></label><button className="button button--primary" type="button" disabled={approve.isPending || !issues.data || !approveReason.trim()} onClick={() => approve.mutate({ id: selected.id, codes: requiredCodes, comment: approveReason })}><CheckCheck /> {l("Подтвердить и утвердить", "Acknowledge and approve")}</button></div> : null}{selected.status === "approved" ? <button className="button button--primary" type="button" disabled={publish.isPending} onClick={() => publish.mutate(selected.id)}><Upload /> {l("Опубликовать версию", "Publish version")}</button> : null}{selected.status === "published" ? <><div className="alert-banner alert-banner--success"><CheckCheck /><div><strong>{l("Операционная версия портфеля опубликована", "Operational portfolio version published")}</strong><p>{l("Проверил", "Reviewed by")}: {selected.reviewer_id}; {l("опубликовал", "published by")}: {selected.publisher_id}.</p></div></div><div className="withdraw-action"><label>{l("Причина снятия с публикации", "Withdrawal reason")}<textarea value={withdrawReason} onChange={(event) => setWithdrawReason(event.target.value)} placeholder={l("Например: рабочая книга была назначена неверному портфелю", "For example: the workbook was assigned to the wrong portfolio")} maxLength={4000} /></label><p>{l("Версия исчезнет из рабочего дашборда. Оригинальная книга, снимок и аудит сохранятся.", "The version will disappear from the working dashboard. The original workbook, snapshot, and audit trail are retained.")}</p><button className="button button--danger" type="button" disabled={withdraw.isPending || !withdrawReason.trim()} onClick={() => withdraw.mutate({ id: selected.id, reason: withdrawReason })}>{withdraw.isPending ? l("Снятие…", "Withdrawing…") : l("Снять версию с публикации", "Withdraw version")}</button></div></> : null}</div><div className="drawer-section"><h3>{l("Политика оценки", "Valuation policy")}</h3><p><BasisBadge basis="derived" /> {l("Доступна расчётная балансовая стоимость. Официальные NAV и доходность недоступны.", "Derived carrying value is available. Official NAV and performance are unavailable.")}</p></div></div> : null}
      </Drawer>
    </PageFrame>
  );
}

function DividendDataPanel() {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const status = useQuery({ queryKey: ["dividend-data-status"], queryFn: dashboardApi.dividendDataStatus });
  const upload = useMutation({
    mutationFn: dashboardApi.uploadDividendData,
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["dividend-data-status"] });
    },
    onError: (caught) => setError(caught.message)
  });
  const current = status.data;
  const freshnessLabel = current?.freshness === "fresh"
    ? l("Актуально", "Current")
    : current?.freshness === "stale"
      ? l("Устарело", "Stale")
      : current?.freshness === "unknown"
        ? l("Дата не подтверждена", "Date not confirmed")
        : l("Данные отсутствуют", "Missing");
  const freshnessClass = current?.freshness === "fresh" && current.future_pay_count === 0 ? "alert-banner--success" : "alert-banner--warning";
  return (
    <Panel
      title={l("Словарь дивидендов Bloomberg", "Bloomberg dividend dictionary")}
      subtitle={l(
        "Используется для корректировки HPR по ex-date и pay-date. Новая книга заменяет текущую и сохраняется с SHA-256.",
        "Used to adjust HPR by ex-date and pay-date. A new workbook replaces the current one and is retained by SHA-256."
      )}
    >
      {current ? <div className={`alert-banner ${freshnessClass}`}>{current.freshness === "fresh" && current.future_pay_count === 0 ? <CheckCheck aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}<div><strong>{current.future_pay_count > 0 ? l("Актуально, но есть будущие выплаты", "Current, with future payments") : freshnessLabel}</strong><p>{current.source_filename ?? l("Файл не загружен", "No file uploaded")}{current.source_date ? ` · ${l("дата выгрузки", "extract date")} ${formatDate(current.source_date, language)}` : ""} · {current.row_count} {l("строк", "rows")} · {current.ticker_count} {l("тикеров", "tickers")}</p>{current.freshness !== "fresh" ? <p>{l("HPR может быть занижен, если в книге отсутствуют последние объявления или выплаты.", "HPR may be understated if the workbook is missing recent declarations or payments.")}</p> : null}{current.future_pay_count > 0 ? <p>{l(`Будущих выплат: ${current.future_pay_count}. Они не включаются в HPR до наступления pay-date.`, `${current.future_pay_count} future payment(s) are excluded until their pay date.`)}</p> : null}</div></div> : null}
      <label className={`upload-zone ${upload.isPending ? "upload-zone--busy" : ""}`}>
        <BookMarked aria-hidden="true" />
        <strong>{upload.isPending ? l("Загрузка словаря дивидендов…", "Uploading dividend dictionary…") : l("Выберите файл Bloomberg .xlsx", "Choose a Bloomberg .xlsx file")}</strong>
        <span>{l("Рекомендуемый файл содержит ID, #Dividend, #ExDate, #Payable и #Type. Дата в имени файла используется для контроля актуальности.", "The recommended file contains ID, #Dividend, #ExDate, #Payable, and #Type. A date in the filename is used for freshness checks.")}</span>
        <input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={upload.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = ""; }} />
      </label>
      {error ? <div className="inline-error" role="alert">{error}</div> : null}
      {upload.data ? <div className="alert-banner alert-banner--success"><CheckCheck aria-hidden="true" /><div><strong>{l("Словарь дивидендов обновлён", "Dividend dictionary updated")}</strong><p>{upload.data.row_count} {l("строк", "rows")} · {upload.data.ticker_count} {l("тикеров", "tickers")} · SHA-256 {upload.data.source_sha256?.slice(0, 12)}…</p></div></div> : null}
    </Panel>
  );
}

function ReferenceDictionaryPanel() {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const status = useQuery({ queryKey: ["reference-dictionary-status"], queryFn: dashboardApi.referenceDictionaryStatus });
  const upload = useMutation({
    mutationFn: dashboardApi.uploadReferenceDictionary,
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["reference-dictionary-status"] });
    },
    onError: (caught) => setError(caught.message)
  });
  return (
    <Panel
      title={l("Словарь классов и рейтингов", "Classes and ratings dictionary")}
      subtitle={l(
        "Справочник ISIN → класс актива / группа рейтинга, используемый для распределения по риску в отчётах OSIP, когда в рабочей книге нет собственного рейтинга.",
        "The ISIN → asset class / rating group lookup used for OSIP risk-bucket reporting when the source workbook has no rating of its own."
      )}
    >
      <p className="upload-assignment__hint">
        {status.data ? l(`Текущая версия: ${status.data.row_count} инструментов`, `Current version: ${status.data.row_count} instruments`) : null}
        {status.data?.updated_at ? ` · ${l("обновлено", "updated")} ${formatDate(status.data.updated_at.slice(0, 10), language)}` : ""}
      </p>
      <label className={`upload-zone ${upload.isPending ? "upload-zone--busy" : ""}`}>
        <BookMarked aria-hidden="true" />
        <strong>{upload.isPending ? l("Загрузка словаря…", "Uploading dictionary…") : l("Выберите файл словаря .csv или .xlsx", "Choose a dictionary .csv or .xlsx file")}</strong>
        <span>{l("Должны быть столбцы: ISIN, Класс актива, Class, Rating group, Focus/sector/factor. Новая версия заменяет текущую немедленно.", "Must have columns: ISIN, Класс актива, Class, Rating group, Focus/sector/factor. The new version replaces the current one immediately.")}</span>
        <input
          type="file"
          accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
          disabled={upload.isPending}
          onChange={(event) => { const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = ""; }}
        />
      </label>
      {error ? <div className="inline-error" role="alert">{error}</div> : null}
      {upload.data ? (
        <div className="alert-banner alert-banner--success">
          <CheckCheck aria-hidden="true" />
          <div>
            <strong>{l(`Установлено: ${upload.data.row_count} инструментов`, `Installed: ${upload.data.row_count} instruments`)}</strong>
            <p>
              {l(
                `Добавлено: ${upload.data.added_isins.length} · удалено: ${upload.data.removed_isins.length} · изменено: ${upload.data.changed_isins.length}`,
                `Added: ${upload.data.added_isins.length} · removed: ${upload.data.removed_isins.length} · changed: ${upload.data.changed_isins.length}`
              )}
            </p>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

export function MultiSourceUploadPanel() {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const queryClient = useQueryClient();
  const [source, setSource] = useState<SourceUpload | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [scopes, setScopes] = useState<Record<string, string>>({});
  const [reconciliationPortfolios, setReconciliationPortfolios] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const datasets = useQuery({ queryKey: ["dataset-versions"], queryFn: () => dashboardApi.datasetVersions() });
  const detect = useMutation({
    mutationFn: dashboardApi.createSourceUpload,
    onSuccess: (result) => {
      setSource(result);
      setSelectedKeys(result.datasets.map((item) => item.key));
      setScopes(Object.fromEntries(result.datasets.map((item) => [item.key, item.scope_code])));
      setError("");
    },
    onError: (caught) => setError(caught.message)
  });
  const materialize = useMutation({
    mutationFn: () => dashboardApi.materializeSourceDatasets(source!.id, selectedKeys.map((key) => ({ detected_key: key, scope_code: scopes[key] || null, reconciliation_portfolio_code: reconciliationPortfolios[key] || null }))),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["dataset-versions"] });
      setSource(null);
      setSelectedKeys([]);
    },
    onError: (caught) => setError(caught.message)
  });
  const approve = useMutation({ mutationFn: ({ dataset, mappingConfirmed }: { dataset: DatasetVersion; mappingConfirmed: boolean }) => dashboardApi.approveDataset(dataset.id, dataset.issues.filter((issue) => ["blocker", "high"].includes(issue.severity)).map((issue) => issue.code), l("Проверены исходные строки, суммы и все критические замечания.", "Source rows, totals, and all critical findings reviewed."), mappingConfirmed), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dataset-versions"] }), onError: (caught) => setError(caught.message) });
  const publish = useMutation({ mutationFn: (dataset: DatasetVersion) => dashboardApi.publishDataset(dataset.id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dataset-versions"] }), onError: (caught) => setError(caught.message) });
  const reject = useMutation({ mutationFn: ({ dataset, reason }: { dataset: DatasetVersion; reason: string }) => dashboardApi.rejectDataset(dataset.id, reason), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dataset-versions"] }), onError: (caught) => setError(caught.message) });
  const withdraw = useMutation({ mutationFn: ({ dataset, reason }: { dataset: DatasetVersion; reason: string }) => dashboardApi.withdrawDataset(dataset.id, reason), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dataset-versions"] }), onError: (caught) => setError(caught.message) });
  const children = datasets.data?.items ?? [];
  const isOsipSource = source?.detected_source_type === "osip_portfolio";
  return <Panel title={l("Универсальная загрузка Portfolio Operations Insight", "Portfolio Operations Insight multi-source upload")} subtitle={l("Тип источника и разделы определяются по структуре рабочей книги; имя файла используется только как доказательство.", "Source type and partitions are detected from workbook structure; the filename is retained only as evidence.")}>
    {!source ? <label className={`upload-zone ${detect.isPending ? "upload-zone--busy" : ""}`}><Upload aria-hidden="true" /><strong>{detect.isPending ? l("Определение источника…", "Detecting source…") : l("Выберите рабочую книгу .xls или .xlsx", "Choose an .xls or .xlsx workbook")}</strong><span>{l("Временные, пустые и неподдерживаемые файлы отклоняются до создания наборов данных.", "Temporary, empty, and unsupported files are rejected before datasets are created.")}</span><input type="file" accept=".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={detect.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) detect.mutate(file); event.target.value = ""; }} /></label> : <div className="drawer-stack">
      <div className="alert-banner alert-banner--success"><CheckCheck /><div><strong>{l("Источник определён", "Source detected")}: {source.detected_source_type}</strong><p>{source.original_filename} · {source.sheets.length} {l("листов", "sheets")} · SHA-256 {source.source_sha256.slice(0, 12)}…</p></div></div>
      {isOsipSource ? <div className="inline-error">{l("Это рабочая книга OSIP. Для неё используйте явное назначение портфеля в форме ниже: так код портфеля никогда не определяется по имени файла.", "This is an OSIP workbook. Use the explicit portfolio assignment form below so the portfolio code is never inferred from the filename.")}</div> : source.datasets.length ? (() => {
        const hasAccountingPortfolio = source.datasets.some((item) => item.dataset_type === "accounting_portfolio_detail");
        return <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Создать", "Create")}</th><th>{l("Раздел", "Partition")}</th><th>{l("Тип набора", "Dataset type")}</th><th>{l("Область", "Scope")}</th>{hasAccountingPortfolio ? <th>{l("Портфель для сверки", "Reconciliation portfolio")}</th> : null}</tr></thead><tbody>{source.datasets.map((item) => <tr key={item.key}><td><input aria-label={l(`Создать ${item.key}`, `Create ${item.key}`)} type="checkbox" checked={selectedKeys.includes(item.key)} onChange={(event) => setSelectedKeys((value) => event.target.checked ? [...value, item.key] : value.filter((key) => key !== item.key))} /></td><td><strong>{item.key}</strong></td><td>{item.dataset_type}</td><td><input value={scopes[item.key] ?? ""} maxLength={120} onChange={(event) => setScopes((value) => ({ ...value, [item.key]: event.target.value.toUpperCase() }))} /></td>{hasAccountingPortfolio ? <td>{item.dataset_type === "accounting_portfolio_detail" ? <select aria-label={l("Портфель для сверки", "Reconciliation portfolio")} value={reconciliationPortfolios[item.key] ?? ""} onChange={(event) => setReconciliationPortfolios((value) => ({ ...value, [item.key]: event.target.value }))}><option value="">{l("Не сверять", "Do not reconcile")}</option><option value="SOBSTV">SOBSTV</option><option value="TABYS">TABYS</option></select> : null}</td> : null}</tr>)}</tbody></table></div>;
      })() : <div className="inline-error">{l("В рабочей книге не найдены поддерживаемые разделы.", "No supported partitions were found in this workbook.")}</div>}
      <div className="workflow-actions"><button className="button button--secondary" type="button" onClick={() => setSource(null)}>{l("Отменить", "Cancel")}</button>{source.datasets.length && !isOsipSource ? <button className="button button--primary" type="button" disabled={!selectedKeys.length || materialize.isPending} onClick={() => materialize.mutate()}>{materialize.isPending ? l("Разбор…", "Parsing…") : l("Создать выбранные наборы", "Create selected datasets")}</button> : null}</div>
    </div>}
    {error ? <div className="inline-error" role="alert">{error}</div> : null}
    {children.some((dataset) => dataset.status === "published") ? <div className="alert-banner alert-banner--success"><CheckCheck aria-hidden="true" /><div><strong>{l("Рабочие книги домена доступны сразу", "Domain workbooks are available immediately")}</strong><p>{l("В локальном режиме опубликованные наборы являются представлением исходных файлов. DQ показывается как предупреждение; подтверждение требуется только для явного контролируемого OSIP-процесса.", "In local mode, published datasets are a presentation of the source files. DQ remains visible as a warning; approval is only needed for the explicit controlled OSIP workflow.")}</p></div></div> : null}
    {children.length ? <div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Набор", "Dataset")}</th><th>{l("Область", "Scope")}</th><th>{l("Бизнес-дата", "Business date")}</th><th>{l("Версия", "Version")}</th><th>{l("Статус", "Status")}</th><th>DQ</th><th>{l("Действие", "Action")}</th></tr></thead><tbody>{children.slice(0, 40).map((dataset) => { const mapping = dataset.summary?.mapping as { confidence?: string; mapping_confirmed?: boolean; missing_fields?: string[] } | undefined; const needsMappingConfirmation = dataset.dataset_type === "brokerage_trade_ledger" && mapping?.confidence !== "high"; const baseline = children.find((candidate) => candidate.id !== dataset.id && candidate.dataset_type === dataset.dataset_type && candidate.scope_code === dataset.scope_code && candidate.business_date === dataset.business_date && candidate.version === dataset.version - 1); const approveDataset = () => { if (needsMappingConfirmation && !window.confirm(l("Столбцы журнала сделок сопоставлены не полностью. Подтвердить сопоставление вручную и продолжить?", "Trade-ledger columns are not fully mapped. Confirm the mapping manually and continue?"))) return; approve.mutate({ dataset, mappingConfirmed: needsMappingConfirmation }); }; return <tr key={dataset.id}><td><strong>{dataset.dataset_type}</strong><small>{dataset.source_filename}</small>{dataset.dataset_type !== "portfolio_snapshot" ? <MappingPreview dataset={dataset} onConfirmed={() => queryClient.invalidateQueries({ queryKey: ["dataset-versions"] })} /> : null}{baseline ? <DatasetVersionComparison dataset={dataset} baseline={baseline} /> : null}{dataset.dataset_type === "brokerage_trade_ledger" ? <small className={needsMappingConfirmation ? "inline-error" : "success-text"}>{needsMappingConfirmation ? l("Сопоставление требует подтверждения", "Mapping needs confirmation") : l("Сопоставление подтверждено по заголовкам", "Header mapping confirmed")}</small> : null}</td><td>{dataset.scope_code}</td><td>{formatDate(dataset.business_date, language)}</td><td>{dataset.version}</td><td><StatusPill status={dataset.status} /></td><td>{dataset.issues.length}</td><td><div className="workflow-actions">{dataset.status === "validated" ? <><button className="button button--secondary" type="button" disabled={approve.isPending} onClick={approveDataset}>{l("Утвердить", "Approve")}</button><button className="button button--secondary" type="button" disabled={reject.isPending} onClick={() => { const reason = window.prompt(l("Причина отклонения", "Rejection reason")); if (reason?.trim()) reject.mutate({ dataset, reason }); }}>{l("Отклонить", "Reject")}</button></> : dataset.status === "approved" ? <><button className="button button--primary" type="button" disabled={publish.isPending} onClick={() => publish.mutate(dataset)}>{l("Опубликовать", "Publish")}</button><button className="button button--secondary" type="button" disabled={reject.isPending} onClick={() => { const reason = window.prompt(l("Причина отклонения", "Rejection reason")); if (reason?.trim()) reject.mutate({ dataset, reason }); }}>{l("Отклонить", "Reject")}</button></> : dataset.status === "published" ? <button className="button button--danger" type="button" disabled={withdraw.isPending} onClick={() => { const reason = window.prompt(l("Причина снятия с публикации", "Withdrawal reason")); if (reason?.trim()) withdraw.mutate({ dataset, reason }); }}>{l("Снять", "Withdraw")}</button> : "—"}</div></td></tr>; })}</tbody></table></div> : null}
  </Panel>;
}

function MappingPreview({ dataset, onConfirmed }: { dataset: DatasetVersion; onConfirmed: () => void }) {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [open, setOpen] = useState(false);
  const mapping = useQuery({ queryKey: ["dataset-mapping", dataset.id], queryFn: () => dashboardApi.datasetMapping(dataset.id), enabled: open });
  const confirm = useMutation({ mutationFn: (comment: string) => dashboardApi.confirmDatasetMapping(dataset.id, comment), onSuccess: () => { onConfirmed(); }, onError: () => undefined });
  return <div className="mapping-preview"><button className="button button--text" type="button" onClick={() => setOpen((value) => !value)}>{open ? l("Скрыть сопоставление", "Hide mapping") : l("Показать сопоставление", "Show mapping")}</button>{open ? <div className="mapping-preview__body">{mapping.isLoading ? <small>{l("Загрузка…", "Loading…")}</small> : mapping.error ? <small className="inline-error">{mapping.error.message}</small> : mapping.data ? <>{(() => { const fields = mapping.data.fields ?? []; const missing = mapping.data.missing_fields ?? []; return <><small>{l("Уверенность", "Confidence")}: {mapping.data.confidence} · {fields.length} {l("полей", "fields")}</small><div className="table-scroll" tabIndex={0}><table><thead><tr><th>{l("Поле приложения", "Application field")}</th><th>{l("Заголовок источника", "Source header")}</th><th>{l("Место", "Location")}</th><th>{l("Пример", "Sample")}</th></tr></thead><tbody>{fields.slice(0, 20).map((field) => <tr key={field.normalized_field}><td>{field.normalized_field}</td><td>{field.source_header ?? "—"}</td><td>{field.source_sheet ?? "—"}:{field.source_row ?? "—"}{field.source_column ? `:${field.source_column}` : ""}</td><td>{(field.sample_values ?? []).join(", ") || "—"}</td></tr>)}</tbody></table></div>{missing.length ? <div className="inline-error">{l("Отсутствуют", "Missing")}: {missing.join(", ")}</div> : null}</>; })()}{dataset.status === "validated" && !mapping.data.mapping_confirmed ? <button className="button button--secondary" type="button" disabled={confirm.isPending} onClick={() => { const comment = window.prompt(l("Обоснование подтверждения сопоставления", "Mapping confirmation justification")); if (comment?.trim()) confirm.mutate(comment); }}>{confirm.isPending ? l("Подтверждение…", "Confirming…") : l("Подтвердить сопоставление", "Confirm mapping")}</button> : mapping.data.mapping_confirmed ? <small className="success-text">{l("Подтверждено", "Confirmed")}</small> : null}</> : null}</div> : null}</div>;
}
