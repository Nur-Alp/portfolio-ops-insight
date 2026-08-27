import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Download, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { InstrumentHolding } from "../api/types";
import { dashboardApi } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/AsyncState";
import { BasisBadge } from "../components/ui/BasisBadge";
import { Drawer } from "../components/ui/Drawer";
import { Panel } from "../components/ui/Panel";
import { useSelectedSnapshot } from "../hooks/useSelectedSnapshot";
import { formatAssetClass, formatDate, formatKzt, formatNumber, formatPercent } from "../lib/format";
import { useI18n } from "../i18n";
import { PageFrame } from "../components/ui/PageFrame";
import { ProvenanceDrawer } from "../components/ui/ProvenanceDrawer";
import { useProvenance } from "../components/ui/ProvenanceContext";

export function HoldingsPage() {
  const { language, t } = useI18n();
  const { openSourcePreview } = useProvenance();
  const { search, portfolios, portfolio, snapshotId } = useSelectedSnapshot();
  const [term, setTerm] = useState(() => search.term ?? "");
  // The command palette navigates here with a `term` search param to jump
  // straight to an instrument. useState's initializer only runs on mount, so
  // without this effect the filter silently keeps its old value when the
  // palette is used while already on this page (no remount occurs).
  useEffect(() => {
    if (search.term !== undefined) setTerm(search.term);
  }, [search.term]);
  const [assetClass, setAssetClass] = useState("all");
  const [selected, setSelected] = useState<InstrumentHolding | null>(null);
  const [showProvenance, setShowProvenance] = useState(false);
  const instruments = useQuery({
    queryKey: ["holdings", snapshotId, "instruments"],
    queryFn: () => dashboardApi.instrumentHoldings(snapshotId),
    enabled: Boolean(snapshotId)
  });
  const lots = useQuery({
    queryKey: ["holdings", snapshotId, "lots"],
    queryFn: () => dashboardApi.lotHoldings(snapshotId),
    enabled: Boolean(snapshotId)
  });
  const provenance = useQuery({ queryKey: ["provenance", snapshotId], queryFn: () => dashboardApi.provenance(snapshotId), enabled: Boolean(snapshotId) });
  const filtered = useMemo(() => {
    const normalized = term.trim().toLocaleLowerCase();
    return (instruments.data?.items ?? []).filter(
      (item) =>
        (assetClass === "all" || item.true_asset_class === assetClass) &&
        (!normalized ||
          [item.isin, item.security_code, item.issuer].some((value) =>
            value.toLocaleLowerCase().includes(normalized)
          ))
    );
  }, [assetClass, instruments.data, term]);
  const assetClasses = [...new Set((instruments.data?.items ?? []).map((item) => item.true_asset_class))].sort();
  const selectedLots = (lots.data?.items ?? []).filter((lot) => lot.isin === selected?.isin);
  const exportHoldings = useMutation({
    mutationFn: () => dashboardApi.exportInstrumentHoldings(snapshotId, {
      basis: search.basis,
      term,
      assetClass
    })
  });
  const exportLots = useMutation({
    mutationFn: () => dashboardApi.exportLotHoldings(snapshotId)
  });

  if (portfolios.isLoading || instruments.isLoading || lots.isLoading || provenance.isLoading) return <LoadingState label={language === "en" ? "Loading instruments and lots" : "Загрузка инструментов и лотов"} />;
  const error = portfolios.error ?? instruments.error ?? lots.error ?? provenance.error;
  if (error) return <ErrorState error={error} />;
  if (!snapshotId) {
    return <PageFrame title={t("holding.title")} eyebrow="OSIP / Instruments" description={language === "en" ? "Aggregated holdings with immutable lot detail." : "Агрегированные позиции с детализацией по неизменяемым лотам."}><EmptyState title={t("holding.noPublished")} detail={t("holding.noPublishedDetail", { portfolio: search.portfolio })} /></PageFrame>;
  }

  const valueKey = search.basis === "purchase" ? "purchase_amount_kzt" : "derived_carrying_value_kzt";
  const weightKey = search.basis === "purchase" ? "purchase_weight_percent" : "derived_weight_percent";
  return (
    <PageFrame
      title={t("holding.title")}
      eyebrow={t("holding.eyebrow")}
      description={t("holding.description")}
      meta={<><span>{portfolio?.code}</span><BasisBadge basis={search.basis === "purchase" ? "source" : "derived"} onClick={() => setShowProvenance(true)} ariaLabel={language === "en" ? "Open metric provenance" : "Открыть происхождение показателя"} /></>}
    >
      {instruments.data?.dividend_data_status && (instruments.data.dividend_data_status.freshness !== "fresh" || instruments.data.dividend_data_status.future_pay_count > 0) ? <div className="alert-banner alert-banner--warning"><AlertTriangle aria-hidden="true" /><div><strong>{language === "en" ? "Dividend data needs review" : "Данные о дивидендах требуют проверки"}</strong><p>{instruments.data.dividend_data_status.freshness !== "fresh" ? (language === "en" ? "Dividend-adjusted HPR may be understated until a current Bloomberg workbook is uploaded." : "Скорректированный на дивиденды HPR может быть занижен, пока не загружена актуальная книга Bloomberg.") : null}{instruments.data.dividend_data_status.future_pay_count > 0 ? ` ${language === "en" ? `${instruments.data.dividend_data_status.future_pay_count} future payment(s) are excluded until their pay date.` : `Будущих выплат: ${instruments.data.dividend_data_status.future_pay_count}; они не включены до наступления pay-date.`}` : null}</p></div></div> : null}
      <Panel
        title={t("holding.panel")}
        subtitle={t("holding.count", { instruments: filtered.length, lots: lots.data?.items.length ?? 0 })}
        action={
          <div className="table-tools">
            <label className="search-field"><Search aria-hidden="true" /><span className="sr-only">{t("holding.searchLabel")}</span><input value={term} onChange={(event) => setTerm(event.target.value)} placeholder={t("holding.search")} /></label>
            <select value={assetClass} onChange={(event) => setAssetClass(event.target.value)} aria-label={t("holding.assetFilter")}>
              <option value="all">{t("holding.allAssetClasses")}</option>
              {assetClasses.map((value) => <option value={value} key={value}>{formatAssetClass(value, language)}</option>)}
            </select>
            <button className="button button--secondary table-tools__export" type="button" disabled={exportHoldings.isPending} onClick={() => exportHoldings.mutate()}>
              <Download aria-hidden="true" /> {exportHoldings.isPending ? t("common.prepare") : t("common.exportExcel")}
            </button>
            <button className="button button--secondary table-tools__export" type="button" disabled={exportLots.isPending} onClick={() => exportLots.mutate()}>
              <Download aria-hidden="true" /> {exportLots.isPending ? t("common.prepare") : t("holding.exportLots")}
            </button>
          </div>
        }
      >
        {exportHoldings.error ? <div className="inline-error" role="alert">{exportHoldings.error.message}</div> : null}
        {exportLots.error ? <div className="inline-error" role="alert">{exportLots.error.message}</div> : null}
        <div className="table-scroll" tabIndex={0}>
          <table className="clickable-table">
            <thead><tr><th>{t("holding.instrument")}</th><th>{t("holding.issuer")}</th><th>{t("holding.class")}</th><th>{t("filter.currency")}</th><th>{t("holding.lots")}</th><th>{t("holding.quantity")}</th><th title={t("holding.hprTitle")}>{t("holding.hpr")}</th><th title={t("holding.ytmTitle")}>{t("holding.ytm")}</th><th>{search.basis === "purchase" ? t("holding.purchase") : t("holding.value")}</th><th>{t("holding.weight")}</th></tr></thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.isin} tabIndex={0} onClick={() => setSelected(item)} onKeyDown={(event) => { if (event.key === "Enter") setSelected(item); }}>
                  <td><strong>{item.security_code || item.isin}</strong><small>{item.isin}</small></td>
                  <td>{item.issuer}</td>
              <td><span className="category-chip">{formatAssetClass(item.true_asset_class, language)}</span></td>
                  <td>{item.instrument_currency}</td>
                  <td>{item.lot_count}</td>
                  <td>{Number(item.quantity).toLocaleString(language === "en" ? "en-GB" : "ru-RU", { maximumFractionDigits: 4 })}</td>
                  <td>{formatPercent(item.hpr_percent, 1, language)}</td>
                  <td>{formatPercent(item.current_ytm, 2, language)}</td>
                  <td><strong>{formatKzt(item[valueKey], language)}</strong></td>
                  <td>{formatPercent(item[weightKey], 1, language)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.security_code || t("holding.instrument")} subtitle={selected?.isin}>
        {selected ? (
          <div className="drawer-stack">
            <div className="drawer-summary">
              <div><span>{t("holding.summaryIssuer")}</span><strong>{selected.issuer}</strong></div>
              <div><span>{t("holding.summaryClass")}</span><strong>{formatAssetClass(selected.true_asset_class, language)}</strong></div>
              <div><span>{t("holding.summaryValue")}</span><strong>{formatKzt(selected[valueKey], language)}</strong></div>
              <div><span>{t("holding.summaryLots")}</span><strong>{selected.lot_count}</strong></div>
            </div>
            <div className="drawer-section"><h3>{t("holding.lotParts")}</h3><p>{t("holding.lotPartsDetail")}</p></div>
            {selectedLots.map((lot) => {
              const sourceText = holdingSourceLocation(lot.source, language);
              const sourceLink = lot.source.source_cell
                ? <button className="link-button" type="button" onClick={() => openSourcePreview(lot.source)}>{sourceText}</button>
                : sourceText;
              return (
              <article className="lot-card" key={lot.id}>
                <header><strong>{formatDate(lot.purchase_date, language)}</strong><span>{sourceLink}</span></header>
                <dl>
                  <div><dt>{t("holding.quantity")}</dt><dd>{formatNumber(lot.quantity, language)}</dd></div>
                  <div><dt>{t("holding.nominal")}</dt><dd>{formatNumber(lot.nominal_value, language)}</dd></div>
                  <div><dt>{t("holding.priceCurrency")}</dt><dd>{lot.instrument_currency}</dd></div>
                  <div><dt>{t("holding.purchasePriceUnit")}</dt><dd>{formatNumber(lot.purchase_price, language)}</dd></div>
                  <div><dt>{t("holding.currentUnitCarryingPrice")}</dt><dd>{formatNumber(lot.carrying_price_native, language)}</dd></div>
                  <div><dt>{t("holding.purchase")}</dt><dd>{formatKzt(lot.purchase_amount_kzt, language)}</dd></div>
                  <div><dt>{t("holding.value")}</dt><dd>{formatKzt(lot.derived_carrying_value_kzt, language)}</dd></div>
                  <div><dt>{t("holding.listingRating")}</dt><dd>{lot.listing_rating ?? t("common.notProvided")}</dd></div>
                  <div><dt>{t("common.source")}</dt><dd>{lot.source.workbook_name} · {sourceLink}</dd></div>
                </dl>
                <div className="unavailable-note">{t("holding.priceBasisNote")}</div>
                {lot.unavailable_fields.length ? <div className="unavailable-note">{t("holding.unavailableFields", { count: lot.unavailable_fields.length })}</div> : null}
              </article>
              );
            })}
          </div>
        ) : null}
      </Drawer>
      <ProvenanceDrawer metric={showProvenance && provenance.data ? provenance.data.metrics[search.basis === "purchase" ? "purchase_amount_kzt" : "derived_carrying_value_kzt"] : null} onClose={() => setShowProvenance(false)} />
    </PageFrame>
  );
}

function holdingSourceLocation(
  source: { sheet_name: string; row_number: number; source_cell?: string | null; source_column_letter?: string | null },
  language: "ru" | "en",
) {
  const row = language === "en" ? `row ${source.row_number}` : `строка ${source.row_number}`;
  const cell = source.source_cell ? (language === "en" ? `cell ${source.source_cell}` : `ячейка ${source.source_cell}`) : null;
  const column = source.source_column_letter ? (language === "en" ? `column ${source.source_column_letter}` : `столбец ${source.source_column_letter}`) : null;
  return [source.sheet_name, row, cell, column].filter(Boolean).join(" · ");
}
