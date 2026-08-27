import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { dashboardApi } from "../../api/client";
import type { ModuleReadResponse } from "../../api/types";
import { Panel } from "../../components/ui/Panel";
import { formatDate } from "../../lib/format";

export function TreasuryDetailLinks({ language }: { language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  return <Panel title={l("Детализация собственного портфеля", "Own-portfolio detail")} subtitle={l("Для строковых доказательств используйте специализированные страницы OSIP.", "Use the specialized OSIP pages for row-level evidence.")}>
    <div className="workflow-actions">
      <Link className="button button--secondary" to="/" search={{ portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT" }}>{l("Обзор портфеля", "Portfolio overview")}</Link>
      <Link className="button button--secondary" to="/holdings" search={{ portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT" }}>{l("Позиции и лоты", "Holdings and lots")}</Link>
      <Link className="button button--secondary" to="/cash-calendar" search={{ portfolio: "SOBSTV", basis: "derived_carrying", currency: "KZT" }}>{l("Деньги и календарь", "Cash and calendar")}</Link>
    </div>
  </Panel>;
}

export function TreasuryVersionPicker({ source, selectedSourceUploadId, onSelect, language }: { source?: ModuleReadResponse["sources"][number]; selectedSourceUploadId: string | null; onSelect: (sourceUploadId: string | null) => void; language: "ru" | "en" }) {
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const query = useQuery({ queryKey: ["treasury-snapshots", "SOBSTV"], queryFn: () => dashboardApi.snapshots("SOBSTV", true) });
  const options = (query.data?.items ?? []).filter((item) => ["published", "superseded"].includes(item.status) && item.source_upload_id);
  return <section className="filterbar filterbar--domain-version" aria-label={l("Версия данных", "Data version")}>
    {/* Treasury always reads the firm's own OSIP book (ImportBatch.portfolio_code
      == "SOBSTV", hardcoded server-side in module_payload) - it never
      switches with the global portfolio filter the way other domains do.
      Naming that plainly here, rather than leaving it implicit in the
      workbook filename, is the point: nobody should have to infer which
      portfolio Treasury covers by parsing the source filename. */}
    <span className="filterbar__currency-note">{l("Портфель: SOBSTV (собственный)", "Portfolio: SOBSTV (own book)")}</span>
    <label className="filterbar__snapshot">
      <span>{l("Версия рабочей книги", "Workbook version")}</span>
      <select aria-label={l("Версия рабочей книги", "Workbook version")} value={selectedSourceUploadId ?? "latest"} disabled={query.isLoading} onChange={(event) => onSelect(event.target.value === "latest" ? null : event.target.value)}>
        <option value="latest">{l("Текущая (последняя)", "Current (latest)")}</option>
        {options.map((item) => <option key={item.id} value={item.source_upload_id ?? ""}>{formatDate(item.report_date, language)} · {l(`Версия ${item.version}`, `Version ${item.version}`)}{item.status === "superseded" ? ` · ${l("заменена", "superseded")}` : ""}</option>)}
      </select>
    </label>
    <small>{source?.source_filename ? `${source.source_filename} · ` : ""}{l("Одна версия применяется ко всем разделам этой области.", "One version is applied to every section in this domain.")}</small>
  </section>;
}
