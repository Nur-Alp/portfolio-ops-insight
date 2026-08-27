import { Download } from "lucide-react";
import { Fragment, useLayoutEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../../api/client";
import type { SourcePreviewResponse } from "../../api/types";
import { ErrorState, LoadingState } from "./AsyncState";
import { Drawer } from "./Drawer";
import { useI18n } from "../../i18n";
import type { components } from "../../api/schema";

type SourceReference = components["schemas"]["ProvenanceReference"];
export type SourceReferenceWithUpload = SourceReference & { source_upload_id?: string };

export function SourcePreviewDrawer({
  reference,
  onClose
}: {
  reference: SourceReferenceWithUpload | null;
  onClose: () => void;
}) {
  const { language } = useI18n();
  const [downloadError, setDownloadError] = useState<Error | null>(null);
  const canPreview = Boolean(reference?.source_row_id && reference.source_cell);
  const canDownload = Boolean(reference?.source_upload_id || canPreview);
  const query = useQueryPreview(reference, canPreview);
  if (!reference || !canDownload) return null;

  const preview = query.data;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const download = async () => {
    setDownloadError(null);
    try {
      if (reference.source_upload_id) {
        await dashboardApi.downloadSourceUpload(reference.source_upload_id, reference.workbook_name);
      } else if (preview?.source_upload_id) {
        // Multi-source (non-OSIP) rows: preview.import_id is a DatasetVersion
        // id, not an ImportBatch id, so /imports/{id}/source 404s for these -
        // the preview response carries the real source_upload_id instead.
        await dashboardApi.downloadSourceUpload(preview.source_upload_id, preview.original_filename);
      } else if (preview) {
        await dashboardApi.downloadSourceWorkbook(preview.import_id, preview.original_filename);
      }
    } catch (error) {
      setDownloadError(error instanceof Error ? error : new Error(String(error)));
    }
  };

  const title = canPreview ? l("Просмотр исходной ячейки", "Source cell preview") : l("Просмотр исходной книги", "Source workbook");
  const subtitle = canPreview
    ? `${reference.workbook_name} · ${reference.sheet_name} · ${reference.source_cell}`
    : `${reference.workbook_name} · ${reference.sheet_name}`;

  return (
    <Drawer
      open
      onClose={onClose}
      title={title}
      subtitle={subtitle}
    >
      {query.isLoading ? <LoadingState label={l("Загрузка строки источника", "Loading source row")} /> : null}
      {query.error ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : null}
      {preview ? <PreviewContents preview={preview} reference={reference} onDownload={() => void download()} downloadError={downloadError} language={language} /> : null}
      {!canPreview ? <WorkbookContents reference={reference} onDownload={() => void download()} downloadError={downloadError} language={language} /> : null}
    </Drawer>
  );
}

function useQueryPreview(reference: SourceReferenceWithUpload | null, enabled: boolean) {
  return useQuery({
    queryKey: ["source-preview", reference?.source_row_id, reference?.source_cell],
    queryFn: () => dashboardApi.sourcePreview(reference!.source_row_id, reference!.source_cell!),
    enabled
  });
}

function WorkbookContents({
  reference,
  onDownload,
  downloadError,
  language
}: {
  reference: SourceReferenceWithUpload;
  onDownload: () => void;
  downloadError: Error | null;
  language: "ru" | "en";
}) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  return (
    <div className="drawer-stack source-preview">
      <div className="drawer-summary">
        <div><span>{l("Рабочая книга", "Workbook")}</span><strong>{reference.workbook_name}</strong></div>
        <div><span>{l("Источник", "Source")}</span><strong>{reference.sheet_name}</strong></div>
        {reference.dataset_type ? <div><span>{l("Набор данных", "Dataset")}</span><strong>{reference.dataset_type}</strong></div> : null}
        {reference.version != null ? <div><span>{l("Версия", "Version")}</span><strong>{reference.version}</strong></div> : null}
      </div>
      <div className="drawer-section">
        <p>{l("Это агрегированная ссылка: у показателя нет одной исходной ячейки. Скачайте неизменяемую рабочую книгу или откройте связанную таблицу домена для построчного подтверждения.", "This is an aggregate reference, so the metric has no single source cell. Download the immutable workbook or use the related domain table for row-level evidence.")}</p>
        <div className="workflow-actions source-preview__actions">
          <button type="button" className="button button--secondary" onClick={onDownload}><Download aria-hidden="true" />{l("Скачать оригинал", "Download original")}</button>
          {downloadError ? <div className="inline-error" role="alert">{downloadError.message}</div> : null}
        </div>
      </div>
    </div>
  );
}

function PreviewContents({
  preview,
  reference,
  onDownload,
  downloadError,
  language
}: {
  preview: SourcePreviewResponse;
  reference: SourceReferenceWithUpload;
  onDownload: () => void;
  downloadError: Error | null;
  language: "ru" | "en";
}) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const containerRef = useRef<HTMLDivElement>(null);
  const targetCellRef = useRef<HTMLTableCellElement>(null);

  // Center the highlighted target cell in the scrollable table on open,
  // instead of leaving the view at its default top-left scroll position -
  // the target is often many columns/rows into the preserved source data.
  useLayoutEffect(() => {
    const container = containerRef.current;
    const target = targetCellRef.current;
    if (!container || !target) return;
    const containerRect = container.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    container.scrollLeft += targetRect.left + targetRect.width / 2 - (containerRect.left + containerRect.width / 2);
    container.scrollTop += targetRect.top + targetRect.height / 2 - (containerRect.top + containerRect.height / 2);
  }, [preview.target_row, preview.target_column]);

  return (
    <div className="drawer-stack source-preview">
      <div className="drawer-summary">
        <div><span>{l("Рабочая книга", "Workbook")}</span><strong>{preview.workbook_name}</strong></div>
        <div><span>{l("Точная ячейка", "Exact cell")}</span><strong>{preview.sheet_name}!{preview.target_cell}</strong></div>
        <div><span>{l("Значение", "Value")}</span><strong>{displayValue(preview.target_value)}</strong></div>
        <div><span>{l("Поле", "Field")}</span><strong>{reference.field ?? l("Строка источника", "Source row")}</strong></div>
      </div>
      <div className="drawer-section">
        <p>{l("Показана неизменяемая строка источника и соседние сохранённые строки. Выделенная ячейка соответствует ссылке показателя.", "The immutable source row and nearby preserved rows are shown. The highlighted cell is the exact cell used by the metric.")}</p>
        <div className="workflow-actions source-preview__actions">
          <button type="button" className="button button--secondary" onClick={onDownload}><Download aria-hidden="true" />{l("Скачать оригинал", "Download original")}</button>
          {downloadError ? <div className="inline-error" role="alert">{downloadError.message}</div> : null}
        </div>
      </div>
      <div className="source-preview__table" tabIndex={0} ref={containerRef}>
        <table>
          <thead><tr>
            <th>{l("Строка", "Row")}</th>
            {preview.columns.map((column, columnIndex) => {
              const label = displayValue(preview.column_labels?.[columnIndex]);
              return (
                <th key={column}>
                  {label !== "—" ? <span className="source-preview__column-label">{label}</span> : null}
                  <span className="source-preview__column-letter">{column}</span>
                </th>
              );
            })}
          </tr></thead>
          <tbody>{preview.rows.map((row, index) => {
            // Rows 1-10 are always included as header context even when the
            // target is far below them (see the backend comment on this),
            // so a gap in row numbers here means "header band, then a jump
            // down to the target's neighborhood" rather than adjacent rows.
            const previousRow = preview.rows[index - 1];
            const isGap = previousRow !== undefined && row.row_number - previousRow.row_number > 1;
            const isHeaderRow = preview.header_row != null && row.row_number === preview.header_row;
            return <Fragment key={row.row_number}>
              {isGap ? <tr className="source-preview__gap-row"><td colSpan={preview.columns.length + 1}>⋯</td></tr> : null}
              <tr className={[
                row.row_number === preview.target_row ? "source-preview__target-row" : null,
                isHeaderRow ? "source-preview__header-band-row" : null
              ].filter(Boolean).join(" ") || undefined}
              >
                <th scope="row">
                  {row.row_number}
                  {isHeaderRow ? <span className="source-preview__header-tag">{l("заголовок", "header")}</span> : null}
                </th>
                {preview.columns.map((column, columnIndex) => {
                  const isTarget = row.row_number === preview.target_row && columnIndex + 1 === preview.target_column;
                  return (
                    <td
                      key={column}
                      ref={isTarget ? targetCellRef : undefined}
                      className={isTarget ? "source-preview__target-cell" : undefined}
                    >
                      {displayValue(row.values[columnIndex])}
                    </td>
                  );
                })}
              </tr>
            </Fragment>;
          })}</tbody>
        </table>
      </div>
    </div>
  );
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}
