import { useEffect, useState } from "react";
import type { components } from "../../api/schema";
import { useI18n } from "../../i18n";
import { formatMetricLabel, formatMetricReason } from "../../lib/format";
import { Drawer } from "./Drawer";
import { SourcePreviewDrawer, type SourceReferenceWithUpload } from "./SourcePreviewDrawer";

type Provenance = components["schemas"]["MetricProvenance"];
type SourceReference = NonNullable<Provenance["source_refs"]>[number];
// A group aggregated by domainCardProvenance (DomainPage.tsx) carries the
// rows beyond the visible sample on this non-schema property so the
// summary line can expand to the full list on demand instead of being a
// dead end.
type AggregateReference = SourceReferenceWithUpload & { remaining_rows?: SourceReference[] };

type MetricCopy = {
  label: { ru: string; en: string };
  explanation: { ru: string; en: string };
  formula?: { ru: string; en: string };
};

// The API keeps stable English identifiers and labels so that exports and
// audit logs remain machine-readable. The drawer is user-facing, however, so
// the operational definitions live here as reviewed RU/EN copy. This also
// prevents a Russian session from displaying an English explanation when an
// older API snapshot is opened.
const metricCopy: Record<string, MetricCopy> = {
  position_count: {
    label: { ru: "Текущие лоты", en: "Current lots" },
    explanation: {
      ru: "Количество сохранённых лотов портфеля. Каждый лот связан с исходной строкой рабочей книги и не заменяет детализацию по инструментам.",
      en: "Number of persisted portfolio lots. Each lot remains linked to its source workbook row and is not a substitute for instrument-level detail."
    }
  },
  unique_isin_count: {
    label: { ru: "Уникальные инструменты", en: "Unique instruments" },
    explanation: {
      ru: "Количество уникальных ISIN среди сохранённых позиций портфеля.",
      en: "Number of distinct ISINs represented by the persisted portfolio positions."
    }
  },
  purchase_amount_kzt: {
    label: { ru: "Сумма покупки", en: "Purchase amount" },
    explanation: {
      ru: "Сумма покупки всех включённых лотов в тенге, считанная из опубликованной рабочей книги.",
      en: "Purchase amount for all included lots in KZT, read from the published source workbook."
    }
  },
  derived_carrying_value_kzt: {
    label: { ru: "Расчётная балансовая стоимость", en: "Derived carrying value" },
    explanation: {
      ru: "Для каждой позиции берутся балансовая сумма в исходной валюте, курс отчётной даты, коэффициент индексации номинала и начисленный доход; затем полученные суммы складываются. Это расчётный операционный показатель, а не официальный СЧА (NAV), рыночная стоимость или прибыль.",
      en: "For each position, the native-currency carrying amount, report-date FX rate, principal-indexation factor, and accrued income are combined and then summed. This is an operational derived measure, not official NAV, market value, or profit."
    },
    formula: {
      ru: "carrying_amount_native × report_fx_rate × principal_indexation + accrued_income_kzt (по каждой позиции, затем сумма)",
      en: "carrying_amount_native × report_fx_rate × principal_indexation + accrued_income_kzt (per lot, then summed)"
    }
  },
  cash_kzt: {
    label: { ru: "Денежный эквивалент", en: "Cash equivalent" },
    explanation: {
      ru: "Сумма денежных остатков из исходных строк, приведённых к тенге по курсу отчётной даты. Это источник денежных средств, а не независимо подтверждённая банковская позиция.",
      en: "Sum of cash balances from the source rows, converted to KZT using the report-date rate. It is source cash evidence, not an independently reconciled bank position."
    }
  },
  derived_operational_total_kzt: {
    label: { ru: "Операционный итог", en: "Operational total" },
    explanation: {
      ru: "Операционный итог — сумма расчётной балансовой стоимости ценных бумаг и денежного эквивалента из источника. Показатель предназначен для операционного контроля; он не является официальным СЧА (NAV), рыночной стоимостью или бухгалтерским итогом.",
      en: "Operational total is the sum of the derived carrying value of securities and the source cash equivalent. It supports operational control; it is not official NAV, market value, or an accounting total."
    },
    formula: {
      ru: "Расчётная балансовая стоимость + денежный эквивалент (KZT)",
      en: "Derived carrying value + cash equivalent (KZT)"
    }
  },
  total_fees_kzt: {
    label: { ru: "Комиссии организатора и брокера", en: "Organizer and broker fees" },
    explanation: {
      ru: "Сумма комиссий организатора и брокера по включённым лотам, если эти значения представлены в рабочей книге.",
      en: "Sum of organizer and broker fees for included lots when those fields are present in the source workbook."
    }
  },
  total_reserves_kzt: {
    label: { ru: "Учтённые резервы", en: "Recognised reserves" },
    explanation: {
      ru: "Сумма признанных резервов по включённым лотам из доступных строк источника.",
      en: "Sum of recognised reserves for included lots from the available source rows."
    }
  },
  official_nav_kzt: {
    label: { ru: "Официальный NAV / СЧА", en: "Official NAV" },
    explanation: {
      ru: "Официальный СЧА недоступен: в опубликованном наборе нет утверждённых цен, обязательств, денежных потоков, политики оценки и подтверждения NAV.",
      en: "Official NAV is unavailable because the published set does not contain approved prices, liabilities, cash flows, valuation policy, and NAV approval."
    }
  },
  official_performance: {
    label: { ru: "Официальная доходность", en: "Official performance" },
    explanation: {
      ru: "Официальная доходность недоступна: отсутствуют исторический NAV, внешние денежные потоки, бенчмарк и утверждённая методология расчёта.",
      en: "Official performance is unavailable because historical NAV, external cash flows, benchmark data, and an approved calculation methodology are absent."
    }
  }
};

function localizeMetric(metric: Pick<Provenance, "code" | "label" | "explanation" | "formula">, language: "ru" | "en") {
  const copy = metricCopy[metric.code];
  return {
    label: copy?.label[language] ?? formatMetricLabel(metric.code, metric.label, language),
    explanation: copy?.explanation[language] ?? formatMetricReason(metric.code, metric.explanation, language),
    formula: metric.formula ? copy?.formula?.[language] ?? metric.formula : null
  };
}

export function ProvenanceDrawer({ metric, onClose }: { metric: Provenance | null; onClose: () => void }) {
  const { language } = useI18n();
  const [showAll, setShowAll] = useState(false);
  const [expandedAggregates, setExpandedAggregates] = useState<Record<string, boolean>>({});
  const [previewReference, setPreviewReference] = useState<SourceReferenceWithUpload | null>(null);
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  // ProvenanceDrawer is a single persistent instance mounted for the whole
  // app session (see ProvenanceProvider) - it never unmounts just because
  // `metric` becomes null, so its local state otherwise survives across
  // closes and even across completely different metrics. Without this, a
  // cell preview left open when the drawer is closed reappears - showing
  // the PREVIOUS metric's workbook/cell - the next time any card's
  // provenance is opened, anywhere in the app.
  useEffect(() => {
    setShowAll(false);
    setExpandedAggregates({});
    setPreviewReference(null);
  }, [metric]);
  if (!metric) return null;
  // A provenance response can contain evidence from older parsers with
  // partially populated optional fields. Keep the drawer usable and keep a
  // malformed reference from taking down the whole page when a basis badge
  // is clicked.
  const allRefs = (Array.isArray(metric.source_refs) ? metric.source_refs : []).filter((ref): ref is SourceReference => Boolean(ref) && typeof ref === "object");
  const inputs = (Array.isArray(metric.inputs) ? metric.inputs : []).filter((input) => Boolean(input) && typeof input === "object");
  const localizedMetric = localizeMetric(metric, language);
  // The dataset-registry reference identifies the workbook/version behind a
  // card - it never has a cell, so it is background identity, not evidence
  // a reader can click through to a value. Keeping it out of the "exact
  // references" list stops it from being mistaken for one of the (often
  // many) row-level references that DO open a cell preview.
  const identityRefs = allRefs.filter((ref) => ref.source_kind === "dataset");
  const refs = allRefs.filter((ref) => ref.source_kind !== "dataset");
  const shownRefs = showAll ? refs : refs.slice(0, 40);
  const sourceOverview = summarizeSourceColumns(refs);
  const renderRef = (ref: SourceReference, key: string) => {
    const aggregateRef = ref as AggregateReference;
    const remaining = aggregateRef.remaining_rows;
    const isExpandable = ref.source_kind === "workbook" && Array.isArray(remaining) && remaining.length > 0;
    const location = sourceLocation(ref, language);
    const field = ref.field ?? (ref.source_kind === "dataset" ? l("набор данных", "dataset") : l("строка", "row"));
    const header = ref.source_header ? ` · ${l("заголовок", "header")} ${ref.source_header}` : "";
    const canPreview = ref.source_kind === "row" && Boolean(ref.source_row_id && ref.source_cell);
    const canOpenWorkbook = ref.source_kind === "dataset" && Boolean(aggregateRef.source_upload_id);
    const expanded = Boolean(expandedAggregates[key]);
    const isIdentity = ref.source_kind === "dataset";
    const rowClassName = `evidence-row${isIdentity ? " evidence-row--identity" : ""}`;
    const content = <><strong>{ref.workbook_name}</strong><span>{location} · {field}{header}{ref.value !== null && ref.value !== undefined ? ` = ${ref.value}` : ""}</span>{ref.note ? <small>{ref.note}</small> : null}</>;
    if (isExpandable) {
      return <button type="button" className={`${rowClassName} evidence-row--button`} key={key} aria-expanded={expanded} onClick={() => setExpandedAggregates((value) => ({ ...value, [key]: !value[key] }))}>
        {content}
        <small className="evidence-row__toggle">{expanded ? l("Свернуть строки", "Collapse rows") : l(`Показать ещё ${remaining!.length} строк`, `Show ${remaining!.length} more rows`)}</small>
      </button>;
    }
    return canPreview
      ? <button type="button" className={`${rowClassName} evidence-row--button`} key={key} onClick={() => setPreviewReference(ref)} aria-label={l(`Открыть ячейку ${ref.source_cell}`, `Open cell ${ref.source_cell}`)}>{content}</button>
      : canOpenWorkbook
        ? <button type="button" className={`${rowClassName} evidence-row--button`} key={key} onClick={() => setPreviewReference(aggregateRef)} aria-label={l(`Открыть рабочую книгу ${ref.workbook_name}`, `Open source workbook ${ref.workbook_name}`)}>{content}</button>
      : <div className={rowClassName} key={key}>{content}</div>;
  };
  const displayedRefs = shownRefs.flatMap((ref, index) => {
    const key = `${ref.source_row_id ?? ref.dataset_id ?? ref.workbook_name}-${index}`;
    const rendered = [renderRef(ref, key)];
    const aggregateRef = ref as AggregateReference;
    if (Array.isArray(aggregateRef.remaining_rows) && expandedAggregates[key]) {
      rendered.push(...aggregateRef.remaining_rows.map((row, rowIndex) => renderRef(row, `${key}-expanded-${rowIndex}`)));
    }
    return rendered;
  });
  const displayedIdentityRefs = identityRefs.map((ref, index) => renderRef(ref, `identity-${ref.dataset_id ?? ref.workbook_name}-${index}`));
  return (
    <>
      <Drawer
        open={Boolean(metric)}
        onClose={onClose}
        title={localizedMetric.label}
        subtitle={l("Происхождение показателя", "Metric provenance")}
      >
      <div className="drawer-stack provenance-drawer">
        <div className="drawer-summary">
          <div><span>{l("Основа", "Basis")}</span><strong className={`basis-badge basis-badge--${metric.basis}`}>{metric.basis === "source" ? l("Источник", "Source") : metric.basis === "derived" ? l("Расчётный показатель", "Derived metric") : l("Недоступно", "Unavailable")}</strong></div>
          <div><span>{l("Значение", "Value")}</span><strong>{metric.value ?? l("Недоступно", "Unavailable")}</strong></div>
        </div>
        <div className="drawer-section">
          <h3>{metric.basis === "derived" ? l("Как рассчитано", "How it was derived") : metric.basis === "source" ? l("Источник значения", "Value source") : l("Почему недоступно", "Why unavailable")}</h3>
          <p>{localizedMetric.explanation}</p>
          {localizedMetric.formula ? <><span className="provenance-formula-label">{l("Техническая формула", "Technical formula")}</span><code className="provenance-formula">{localizedMetric.formula}</code></> : null}
        </div>
        {inputs.length ? <div className="drawer-section"><h3>{l("Входные показатели", "Input metrics")}</h3><div className="provenance-inputs">{inputs.map((input) => <div className="provenance-input" key={input.code}><div><strong>{formatMetricLabel(input.code, input.label, language)}</strong><span>{input.code} · {input.value ?? l("Недоступно", "Unavailable")}</span></div><strong className={`basis-badge basis-badge--${input.basis}`}>{input.basis === "source" ? l("Источник", "Source") : input.basis === "derived" ? l("Расчётный показатель", "Derived metric") : l("Недоступно", "Unavailable")}</strong></div>)}</div></div> : null}
        {identityRefs.length ? <div className="drawer-section">
          <h3>{l("Источник (идентификация)", "Source identity")}</h3>
          <p>{l("Определяет рабочую книгу и версию набора, лежащие в основе показателя. У записи нет одной ячейки — она не открывается для предпросмотра значения.", "Identifies the workbook and dataset version behind this metric. It has no single cell, so it does not open a value preview.")}</p>
          <div className="provenance-refs">{displayedIdentityRefs}</div>
        </div> : null}
        {sourceOverview.length ? <div className="drawer-section">
          <h3>{l("Обзор источника", "Source overview")}</h3>
          <p>{l("Из каких рабочих книг, листов и столбцов взяты значения ниже - по одной строке на каждое уникальное сочетание.", "Which workbooks, sheets, and columns the references below come from - one row per unique combination.")}</p>
          <div className="table-scroll" tabIndex={0}>
            <table>
              <thead><tr><th>{l("Рабочая книга", "Workbook")}</th><th>{l("Лист", "Sheet")}</th><th>{l("Столбец", "Column")}</th><th>{l("Строк", "Rows")}</th></tr></thead>
              <tbody>{sourceOverview.map((group) => <tr key={`${group.workbook}-${group.sheet}-${group.columnLetter ?? "none"}`}><td>{group.workbook}</td><td>{group.sheet}</td><td>{group.columnLetter ? `${group.columnLetter}${group.column != null ? ` (${group.column})` : ""}` : l("не одна ячейка", "no single cell")}</td><td>{group.count}</td></tr>)}</tbody>
            </table>
          </div>
        </div> : null}
        <div className="drawer-section">
          <h3>{l("Точные ссылки на рабочую книгу", "Exact workbook references")}</h3>
          {refs.length ? <>
            <p>{refs.some((ref) => ref.source_kind === "row" && ref.row_number != null) ? l("Ссылки указывают на неизменяемую рабочую книгу, лист, строку, столбец/ячейку и поле, использованное в показателе. Нажмите на запись, чтобы открыть предпросмотр ячейки.", "References identify the immutable workbook, sheet, row, column/cell, and field used by this metric. Click an entry to open its cell preview.") : l("Ссылки указывают на неизменяемые рабочие книги и версии наборов; связанные строки показываются на таблице домена.", "References identify immutable workbooks and dataset versions; related row evidence is shown in the domain table.")}</p>
            <div className="provenance-refs">{displayedRefs}</div>
            {refs.length > 40 ? <div className="workflow-actions"><button type="button" className="button button--secondary" onClick={() => setShowAll((value) => !value)}>{showAll ? l("Показать первые 40 ссылок", "Show first 40 references") : l(`Показать все ${refs.length} ссылок`, `Show all ${refs.length} references`)}</button></div> : null}
          </> : <div className="unavailable-note">{metric.basis === "source" ? l("Построчных ссылок нет: показатель подтверждается только реестром источника выше.", "No row-level references are available: the metric is evidenced only by the source identity above.") : l("Для этого показателя нет строки исходной рабочей книги: требуемые данные не предоставлены.", "No source row is available for this metric because the required data was not provided.")}</div>}
        </div>
      </div>
      </Drawer>
      <SourcePreviewDrawer reference={previewReference} onClose={() => setPreviewReference(null)} />
    </>
  );
}

type SourceColumnGroup = { workbook: string; sheet: string; columnLetter: string | null; column: number | null; count: number };

// A metric can carry dozens of near-identical row references (one per
// source row) - useful for opening a specific cell, but tedious for
// answering "which workbook/sheet/column is this even from" without
// scrolling through all of them. This collapses that same list into one
// row per unique (workbook, sheet, column) combination instead.
function summarizeSourceColumns(refs: SourceReference[]): SourceColumnGroup[] {
  const groups = new Map<string, SourceColumnGroup>();
  for (const ref of refs) {
    const workbook = ref.workbook_name ?? "—";
    const sheet = ref.sheet_name ?? "—";
    const columnLetter = ref.source_column_letter ?? null;
    const column = ref.source_column ?? null;
    const key = `${workbook} ${sheet} ${columnLetter ?? ""}`;
    const existing = groups.get(key);
    if (existing) existing.count += 1;
    else groups.set(key, { workbook, sheet, columnLetter, column, count: 1 });
  }
  return [...groups.values()].sort((a, b) => b.count - a.count);
}

function sourceLocation(ref: NonNullable<Provenance["source_refs"]>[number], language: "ru" | "en") {
  const sourceKind = ref.source_kind ?? "row";
  if (sourceKind === "dataset" || sourceKind === "workbook") {
    const dataset = ref.dataset_type ? ` · ${ref.dataset_type}` : "";
    const scope = ref.scope_code ? ` · ${ref.scope_code}` : "";
    const version = ref.version != null ? ` · ${language === "en" ? "version" : "версия"} ${ref.version}` : "";
    return `${ref.sheet_name}${dataset}${scope}${version}`;
  }
  const row = ref.row_number == null ? `${language === "en" ? "row" : "строка"} ${language === "en" ? "unavailable" : "недоступна"}` : `${language === "en" ? "row" : "строка"} ${ref.row_number}`;
  const cell = ref.source_cell ? ` · ${language === "en" ? "cell" : "ячейка"} ${ref.source_cell}` : "";
  const column = ref.source_column_letter ? ` · ${language === "en" ? "column" : "столбец"} ${ref.source_column_letter}${ref.source_column != null ? ` (${ref.source_column})` : ""}` : "";
  return `${ref.sheet_name} · ${row}${cell}${column}`;
}
