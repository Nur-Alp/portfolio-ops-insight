import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarClock, Download, Landmark, WalletCards } from "lucide-react";
import { useMemo, useState } from "react";
import type { CalendarEvent } from "../api/types";
import { dashboardApi } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { BasisBadge } from "../components/ui/BasisBadge";
import { Drawer } from "../components/ui/Drawer";
import { KpiCard } from "../components/ui/KpiCard";
import { Panel } from "../components/ui/Panel";
import { StatusPill } from "../components/ui/StatusPill";
import { useSelectedSnapshot } from "../hooks/useSelectedSnapshot";
import { formatDate, formatKzt, humanize } from "../lib/format";
import { useI18n } from "../i18n";
import { PageFrame } from "../components/ui/PageFrame";
import { ProvenanceDrawer } from "../components/ui/ProvenanceDrawer";
import { useProvenance } from "../components/ui/ProvenanceContext";
import { SourceRowLegend } from "../components/ui/SourceRowLegend";
import { TableSearch } from "../components/ui/TableSearch";

export function CashCalendarPage() {
  const { language, t } = useI18n();
  const { openSourcePreview } = useProvenance();
  const { search, portfolios, snapshotId } = useSelectedSnapshot();
  const [showTemplates, setShowTemplates] = useState(false);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [provenanceCode, setProvenanceCode] = useState<string | null>(null);
  const cash = useQuery({ queryKey: ["cash", snapshotId], queryFn: () => dashboardApi.cash(snapshotId), enabled: Boolean(snapshotId) });
  const calendar = useQuery({ queryKey: ["calendar", snapshotId], queryFn: () => dashboardApi.calendar(snapshotId), enabled: Boolean(snapshotId) });
  const provenance = useQuery({ queryKey: ["provenance", snapshotId], queryFn: () => dashboardApi.provenance(snapshotId), enabled: Boolean(snapshotId) });
  const exportCashCalendar = useMutation({
    mutationFn: () => dashboardApi.exportCashCalendar(snapshotId, showTemplates)
  });
  const balances = showTemplates ? cash.data?.items ?? [] : (cash.data?.items ?? []).filter((item) => item.active);
  const currencies = useMemo(() => {
    const values = new Map<string, { native: number; kzt: number }>();
    for (const item of (cash.data?.items ?? []).filter((balance) => balance.active)) {
      const current = values.get(item.currency) ?? { native: 0, kzt: 0 };
      current.native += Number(item.native_amount);
      current.kzt += Number(item.kzt_amount);
      values.set(item.currency, current);
    }
    return values;
  }, [cash.data]);

  if (portfolios.isLoading || cash.isLoading || calendar.isLoading || provenance.isLoading) return <LoadingState label={t("cash.loading")} />;
  const error = portfolios.error ?? cash.error ?? calendar.error ?? provenance.error;
  if (error) return <ErrorState error={error} />;
  if (!snapshotId) return <PageFrame title={t("cash.title")} eyebrow="OSIP / Operations" description={language === "en" ? "Cash balances and dated events from the source workbook." : "Остатки денежных средств и датированные события из рабочей книги."}><EmptyState title={t("holding.noPublished")} detail={t("cash.noPublishedDetail", { portfolio: search.portfolio })} /></PageFrame>;
  if (!cash.data || !calendar.data) return null;
  const activeCount = cash.data.items.filter((item) => item.active).length;

  return (
    <PageFrame title={t("cash.title")} eyebrow={t("cash.eyebrow")} description={t("cash.description")}>
      <div className="kpi-grid">
        <KpiCard label={t("cash.activeRows")} value={String(activeCount)} basis="source" detail={t("cash.zeroTemplates", { count: cash.data.items.length - activeCount })} icon={<WalletCards />} onBasisClick={() => setProvenanceCode("cash_kzt")} />
        <KpiCard label={t("cash.kztEquivalent")} value={formatKzt([...currencies.values()].reduce((sum, item) => sum + item.kzt, 0), language)} basis="source" icon={<Landmark />} onBasisClick={() => setProvenanceCode("cash_kzt")} />
        <KpiCard label={t("cash.upcoming")} value={String(calendar.data.counts.upcoming)} basis="source" icon={<CalendarClock />} />
        <KpiCard label={t("cash.overdue")} value={String(calendar.data.counts.overdue_settlements)} basis="source" tone={calendar.data.counts.overdue_settlements ? "danger" : "positive"} />
      </div>
      <div className="content-grid content-grid--two-thirds">
        <Panel title={t("cash.byCustodian")} subtitle={t("cash.byCustodianDetail")} action={<div className="table-tools"><TableSearch label={language === "en" ? "Search cash balances" : "Поиск остатков денежных средств"} placeholder={language === "en" ? "Custodian, currency" : "Кастодиан, валюта"} /><SourceRowLegend language={language} /><label className="toggle"><input type="checkbox" checked={showTemplates} onChange={(event) => setShowTemplates(event.target.checked)} /> {t("cash.showTemplates")}</label><button className="button button--secondary table-tools__export" type="button" disabled={exportCashCalendar.isPending} onClick={() => exportCashCalendar.mutate()}><Download aria-hidden="true" /> {exportCashCalendar.isPending ? t("common.prepare") : t("common.exportExcel")}</button></div>}>
          {exportCashCalendar.error ? <div className="inline-error" role="alert">{exportCashCalendar.error.message}</div> : null}
          <div className="table-scroll" tabIndex={0}><table className="clickable-table"><thead><tr><th>{t("cash.custodian")}</th><th>{t("filter.currency")}</th><th>{t("cash.nativeBalance")}</th><th>{t("cash.kztEquivalent")}</th></tr></thead><tbody>{balances.map((item) => {
            const openable = Boolean(item.source.source_cell);
            return (
              <tr
                key={item.id}
                tabIndex={openable ? 0 : undefined}
                onClick={openable ? () => openSourcePreview(item.source) : undefined}
                onKeyDown={openable ? (event) => { if (event.key === "Enter") openSourcePreview(item.source); } : undefined}
                style={openable ? undefined : { cursor: "default" }}
              >
                <td><strong>{item.custodian ?? t("common.notProvided")}</strong></td>
                <td>{item.currency}</td>
                <td>{Number(item.native_amount).toLocaleString(language === "en" ? "en-GB" : "ru-RU", { maximumFractionDigits: 2 })}</td>
                <td>{formatKzt(item.kzt_amount, language)}</td>
              </tr>
            );
          })}</tbody></table></div>
        </Panel>
        <Panel title={t("cash.currencySummary")} subtitle={t("cash.currencySummaryDetail")}>
          <div className="allocation-list">{[...currencies.entries()].map(([currency, value]) => <div className="allocation-row" key={currency}><div><strong>{currency}</strong><span>{value.native.toLocaleString(language === "en" ? "en-GB" : "ru-RU", { maximumFractionDigits: 2 })} {t("cash.inNative")}</span></div><div className="allocation-row__value"><strong>{formatKzt(value.kzt, language)}</strong><BasisBadge basis="source" /></div></div>)}</div>
        </Panel>
      </div>
      <Panel title={t("cash.events")} subtitle={t("cash.eventsDetail")} action={<div className="table-tools"><TableSearch label={language === "en" ? "Search cash events" : "Поиск денежных событий"} placeholder={language === "en" ? "Date, instrument, status" : "Дата, инструмент, статус"} /><SourceRowLegend language={language} /><button className="button button--secondary table-tools__export" type="button" disabled={exportCashCalendar.isPending} onClick={() => exportCashCalendar.mutate()}><Download aria-hidden="true" /> {exportCashCalendar.isPending ? t("common.prepare") : t("common.exportExcel")}</button></div>}>
        {exportCashCalendar.error ? <div className="inline-error" role="alert">{exportCashCalendar.error.message}</div> : null}
        <div className="table-scroll" tabIndex={0}><table className="clickable-table"><thead><tr><th>{language === "en" ? "Date" : "Дата"}</th><th>{t("cash.type")}</th><th>{t("holding.instrument")}</th><th>{language === "en" ? "Status" : "Статус"}</th><th>{t("cash.cashFlow")}</th><th>{t("cash.confirmation")}</th></tr></thead><tbody>{calendar.data.items.map((event) => <tr key={event.id} tabIndex={0} onClick={() => setSelected(event)} onKeyDown={(key) => { if (key.key === "Enter") setSelected(event); }}><td>{formatDate(event.event_date, language)}</td><td>{humanize(event.event_type, language)}</td><td><strong>{event.security_code || event.isin}</strong><small>{event.isin}</small></td><td><StatusPill status={event.status} /></td><td>{event.amount_kzt !== null ? formatKzt(event.amount_kzt, language) : t("common.unavailable")}</td><td>{t("cash.sourceRows", { count: uniqueSourceRows(event.source_refs) })}</td></tr>)}</tbody></table></div>
      </Panel>
      <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected ? `${humanize(selected.event_type, language)} — ${selected.security_code || selected.isin}` : t("cash.event")} subtitle={selected ? formatDate(selected.event_date, language) : undefined}>
        {selected ? <div className="drawer-stack"><div className="drawer-summary"><div><span>{language === "en" ? "Status" : "Статус"}</span><StatusPill status={selected.status} /></div><div><span>{t("cash.amountBasis")}</span><strong>{humanize(selected.amount_basis, language)}</strong></div><div><span>{t("filter.currency")}</span><strong>{selected.currency}</strong></div><div><span>{t("cash.sourceRowsLabel")}</span><strong>{uniqueSourceRows(selected.source_refs)}</strong></div></div><div className="drawer-section"><h3>{t("cash.sourceEvidence")}</h3><p>{t("cash.sourceEvidenceDetail")}</p></div>{selected.source_refs.map((source, index) => {
          const key = `${source.source_row_id}-${source.field ?? "row"}-${index}`;
          const content = <><strong>{source.workbook_name}</strong><span>{sourceLocation(source, language)} · {source.field ?? (language === "en" ? "source row" : "строка источника")} · {source.parser_version}</span></>;
          return source.source_cell
            ? <button type="button" className="evidence-row evidence-row--button" key={key} onClick={() => openSourcePreview(source)} aria-label={language === "en" ? `Open cell ${source.source_cell}` : `Открыть ячейку ${source.source_cell}`}>{content}</button>
            : <div className="evidence-row" key={key}>{content}</div>;
        })}</div> : null}
      </Drawer>
      <ProvenanceDrawer metric={provenanceCode && provenance.data ? provenance.data.metrics[provenanceCode] ?? null : null} onClose={() => setProvenanceCode(null)} />
    </PageFrame>
  );
}

function uniqueSourceRows(refs: Array<{ source_row_id: string }>) {
  return new Set(refs.map((ref) => ref.source_row_id)).size;
}

function sourceLocation(source: {
  sheet_name: string;
  row_number: number;
  source_cell?: string | null;
  source_column_letter?: string | null;
}, language: "ru" | "en") {
  const row = language === "en" ? `row ${source.row_number}` : `строка ${source.row_number}`;
  const cell = source.source_cell ? (language === "en" ? `cell ${source.source_cell}` : `ячейка ${source.source_cell}`) : null;
  const column = source.source_column_letter ? (language === "en" ? `column ${source.source_column_letter}` : `столбец ${source.source_column_letter}`) : null;
  return [source.sheet_name, row, cell, column].filter(Boolean).join(" · ");
}
