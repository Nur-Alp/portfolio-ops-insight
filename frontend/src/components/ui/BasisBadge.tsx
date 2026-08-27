import type { Basis } from "../../api/types";
import type { components } from "../../api/schema";
import { useQuery } from "@tanstack/react-query";
import { useI18n } from "../../i18n";
import { dashboardApi } from "../../api/client";
import { useSelectedSnapshot } from "../../hooks/useSelectedSnapshot";
import { useProvenance } from "./ProvenanceContext";

const labels: Record<Basis, string> = {
  source: "basis.source",
  derived: "basis.derived",
  unavailable: "basis.unavailable"
};

export function BasisBadge({ basis, onClick, ariaLabel, interactive = true }: { basis: Basis; onClick?: () => void; ariaLabel?: string; interactive?: boolean }) {
  const { language, t } = useI18n();
  const { open } = useProvenance();
  const { snapshotId, osipEnabled } = useSelectedSnapshot();
  const provenance = useQuery({
    queryKey: ["provenance", snapshotId],
    queryFn: () => dashboardApi.provenance(snapshotId),
    enabled: !onClick && basis !== "unavailable" && osipEnabled && Boolean(snapshotId),
    staleTime: 60_000
  });
  const content = t(labels[basis]);
  const fallback: components["schemas"]["MetricProvenance"] = {
    code: `basis_${basis}`,
    label: content,
    basis,
    value: null,
    explanation: basis === "derived"
      ? (language === "en" ? "This label identifies a calculated value. The page description and metric definition state the calculation basis; no official NAV is implied." : "Этот показатель рассчитан. Основа расчёта указана в описании страницы и определении метрики; официальный NAV не подразумевается.")
      : basis === "source"
        ? (language === "en" ? "This label identifies a value read from the controlled source data shown on this page. The references below identify the immutable workbook, sheet, row, column, and cell evidence available for the selected snapshot. Use the related table to narrow an aggregate to one business row." : "Этот показатель взят из контролируемого источника, показанного на странице. Ссылки ниже указывают неизменяемую рабочую книгу, лист, строку, столбец и ячейку выбранного снимка. Для одного бизнес-ряда используйте связанную таблицу.")
        : (language === "en" ? "The required source inputs for this metric are unavailable." : "Требуемые исходные данные для этого показателя недоступны."),
    source_refs: provenance.data && basis !== "unavailable" ? aggregateSourceRefs(provenance.data.metrics) : []
  };
  // A derived badge without a metric-specific handler has no honest formula
  // or input set to show.  Render it as a disclosure label rather than
  // opening the selected OSIP snapshot (or a generic fallback) by accident.
  if (!interactive || (basis === "derived" && !onClick)) return <span className={`basis-badge basis-badge--${basis}`}><span>{content}</span></span>;
  return <button type="button" className={`basis-badge basis-badge--${basis} basis-badge--interactive`} onClick={onClick ?? (() => open(fallback))} aria-label={ariaLabel ?? content} title={ariaLabel ?? content}><span>{content}</span></button>;
}

function aggregateSourceRefs(metrics: Record<string, components["schemas"]["MetricProvenance"]>) {
  const refs = Object.values(metrics).flatMap((metric) => metric.source_refs ?? []);
  const seen = new Set<string>();
  return refs.filter((ref) => {
    const key = [ref.workbook_name, ref.sheet_name, ref.row_number, ref.source_cell, ref.field, ref.dataset_id].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).map((ref) => ({
    ...ref,
    note: ref.note ?? "Aggregate basis badge reference; use the related table or metric-specific provenance for the exact contributing field."
  }));
}
