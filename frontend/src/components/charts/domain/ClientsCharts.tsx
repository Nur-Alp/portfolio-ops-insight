import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { BarChart, Bar, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ModuleReadResponse } from "../../../api/types";
import { useScrollAnchor } from "../../../hooks/useScrollAnchor";
import {
  ChartCard, ChartEmpty, ChartGrid, ChartTooltip, COLORS, GRID, axisTick, categoryAxisWidth, compact, numeric,
  sourceRefsFromRecords, type Language, type MetricProvenance, type ProvenanceRef, type Row,
} from "./shared";

// Unlike every other domain, the clients chart never plots the passed-in
// `sourceRefs` directly - it computes its own `clientRefs` (scoped to the
// client-account-snapshot rows that actually feed this chart) instead. The
// prop stays in the signature so DomainCharts can pass it uniformly to
// every domain, but it is intentionally not read here.
export function ClientsCharts({ data, language }: { data: ModuleReadResponse; language: Language; sourceRefs?: ProvenanceRef[] }) {
  const records = data.records as Record<string, Row[]>;
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [clientAssetPage, setClientAssetPage] = useState(0);
  const clientAssetPagination = useScrollAnchor<HTMLDivElement>();
  const allClients = (records.client_account_snapshot ?? []).filter((row) => row.record_type === "client").map((row) => {
    const assets = numeric(row.total_assets_kzt) ?? 0;
    const cash = numeric(row.cash_kzt) ?? 0;
    // Keep the arithmetic relationship visible. Clamping a negative
    // residual to zero would silently replace a source inconsistency with a
    // fabricated value; the corresponding DQ finding must remain visible.
    const clientName = String(row.client_name ?? "").trim() || String(row.account ?? "").trim() || "—";
    return { name: clientName, cash, securities: assets - cash };
  }).sort((a, b) => (b.cash + b.securities) - (a.cash + a.securities));
  const clientsPageSize = 10;
  const clientsPageCount = Math.max(1, Math.ceil(allClients.length / clientsPageSize));
  const clientsCurrentPage = Math.min(clientAssetPage, clientsPageCount - 1);
  const clients = allClients.slice(clientsCurrentPage * clientsPageSize, (clientsCurrentPage + 1) * clientsPageSize);
  const clientRefs = sourceRefsFromRecords(records.client_account_snapshot ?? [], language);
  const clientAssetProvenance: MetricProvenance = {
    code: "client_asset_composition",
    label: l("Структура активов клиентов", "Client asset composition"),
    basis: "derived",
    value: null,
    formula: l(
      "По каждому клиенту: ценные бумаги = Общие активы KZT − Денежные средства KZT. Столбцы показывают исходные деньги и рассчитанный остаток ценных бумаг.",
      "For each client: securities = total assets in KZT − cash in KZT. The bars show source cash and the calculated residual securities value.",
    ),
    explanation: l(
      "Отрицательный остаток не ограничивается нулём: возможное расхождение источника остаётся видимым и подлежит проверке качества данных.",
      "A negative residual is not clamped to zero: a possible source inconsistency remains visible and is subject to data-quality review.",
    ),
    source_refs: clientRefs,
    inputs: [{
      code: "client_account_snapshot_rows",
      label: l("Строки снимка клиентских счетов", "Client-account snapshot rows"),
      basis: "source",
      value: String(allClients.length),
      source_refs: clientRefs,
    }],
  };
  return <ChartGrid single>
    <ChartCard
      title={l("Структура активов клиентов", "Client asset composition")}
      subtitle={l(`Денежные средства и остаточная стоимость ценных бумаг по всем клиентам, отсортировано по активам (страница ${clientsCurrentPage + 1} из ${clientsPageCount}; по 10 клиентов на странице).`, `Cash and residual securities value for all clients, sorted by total assets (page ${clientsCurrentPage + 1} of ${clientsPageCount}; 10 clients per page).`)}
      basis="derived" sourceRefs={clientRefs} provenance={clientAssetProvenance}
      footer={allClients.length ? <div className="table-pagination" ref={clientAssetPagination.ref}><span>{l(`Страница ${clientsCurrentPage + 1} из ${clientsPageCount}`, `Page ${clientsCurrentPage + 1} of ${clientsPageCount}`)}</span><label className="table-pagination__jump"><span>{l("Перейти", "Go to")}</span><select aria-label={l("Выбрать страницу", "Choose page")} value={clientsCurrentPage} onChange={(event) => { clientAssetPagination.anchor(); setClientAssetPage(Number(event.target.value)); }}>{Array.from({ length: clientsPageCount }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label><div><button className="icon-button" type="button" aria-label={l("Предыдущая страница", "Previous page")} disabled={clientsCurrentPage === 0} onClick={() => { clientAssetPagination.anchor(); setClientAssetPage((value) => Math.max(0, value - 1)); }}><ChevronLeft aria-hidden="true"/></button><button className="icon-button" type="button" aria-label={l("Следующая страница", "Next page")} disabled={clientsCurrentPage >= clientsPageCount - 1} onClick={() => { clientAssetPagination.anchor(); setClientAssetPage((value) => Math.min(clientsPageCount - 1, value + 1)); }}><ChevronRight aria-hidden="true"/></button></div></div> : null}
    >
      {/* Client/company names run long (full legal entity names, full
          patronymics) and Recharts wraps the y-axis category label to fit
          its `width` - a narrow width forced 3-4 wrapped lines into a
          48px-tall row and adjacent labels overlapped (confirmed live).
          Claiming more of the card's own left-hand space for the label
          column cuts the wrap depth, and a taller row gives whatever
          wrapping still happens room to breathe. */}
      {clients.length ? <ResponsiveContainer width="100%" height={Math.max(280, clients.length * 80)}><BarChart data={clients} layout="vertical" margin={{ top: 18, right: 18, left: 24, bottom: 8 }}><CartesianGrid stroke={GRID} strokeDasharray="3 5" horizontal={false}/><XAxis type="number" tickFormatter={(value) => compact(value, language)} tick={axisTick}/><YAxis type="category" dataKey="name" tick={axisTick} width={categoryAxisWidth(clients.map((row) => row.name))} interval={0} padding={{ top: 10, bottom: 10 }}/><Tooltip content={<ChartTooltip language={language} valueKind="kzt"/>}/><Legend iconType="circle"/><Bar isAnimationActive={false} dataKey="securities" stackId="assets" name={l("Ценные бумаги", "Securities")} fill={COLORS[0]} radius={[0, 0, 0, 0]}/><Bar isAnimationActive={false} dataKey="cash" stackId="assets" name={l("Деньги", "Cash")} fill={COLORS[2]} radius={[0, 6, 6, 0]}/></BarChart></ResponsiveContainer> : <ChartEmpty language={language}/>}
    </ChartCard>
  </ChartGrid>;
}
