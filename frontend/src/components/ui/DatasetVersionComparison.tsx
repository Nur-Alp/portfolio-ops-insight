import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../../api/client";
import type { DatasetVersion } from "../../api/types";
import { useI18n } from "../../i18n";

// Fully generic: driven only by the two dataset ids, so any dataset_type
// (OSIP-style imports, every multi-source domain including Risk) gets the
// same compare affordance without dataset-specific wiring.
export function DatasetVersionComparison({ dataset, baseline }: { dataset: DatasetVersion; baseline: DatasetVersion }) {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  const [open, setOpen] = useState(false);
  const comparison = useQuery({ queryKey: ["dataset-compare", dataset.id, baseline.id], queryFn: () => dashboardApi.compareDatasetVersions(dataset.id, baseline.id), enabled: open });
  return <div className="mapping-preview">
    <button className="button button--text" type="button" onClick={() => setOpen((value) => !value)}>{open ? l("Скрыть изменения", "Hide changes") : l(`Сравнить с версией ${baseline.version}`, `Compare with version ${baseline.version}`)}</button>
    {open && comparison.data ? <small>{l("Добавлено", "Added")} {comparison.data.added_count} · {l("Удалено", "Removed")} {comparison.data.removed_count} · {l("Изменено", "Changed")} {comparison.data.changed_count} · {l("Без изменений", "Unchanged")} {comparison.data.unchanged_count}</small> : null}
    {open && comparison.isLoading ? <small>{l("Сравнение…", "Comparing…")}</small> : null}
    {open && comparison.error ? <small className="inline-error">{comparison.error.message}</small> : null}
  </div>;
}
