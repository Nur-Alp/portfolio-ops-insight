import type { components } from "../../api/schema";
import { useI18n } from "../../i18n";
import { formatKzt } from "../../lib/format";
import { Drawer } from "./Drawer";

type ExcludedLot = components["schemas"]["ExcludedLot"];

const MISSING_FIELD_LABELS: Record<string, { ru: string; en: string }> = {
  carrying_amount_native: { ru: "балансовая сумма (AA)", en: "carrying amount (AA)" },
  report_fx_rate: { ru: "курс отчётной даты (AU)", en: "report-date FX rate (AU)" }
};

// A focused view of just what's missing and why - deliberately separate
// from ProvenanceDrawer (opened by the basis badge), which shows the full
// calculation for every included lot too and buries these among dozens of
// unrelated references.
export function ExcludedLotsDrawer({ open, lots, excludedPurchaseValueKzt, onClose }: {
  open: boolean;
  lots: ExcludedLot[];
  excludedPurchaseValueKzt: string | null;
  onClose: () => void;
}) {
  const { language } = useI18n();
  const l = (ru: string, en: string) => language === "en" ? en : ru;
  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={l("Исключённые позиции", "Excluded lots")}
      subtitle={l(
        "Не учтены в расчётной балансовой стоимости и операционном итоге",
        "Left out of the derived carrying value and operational total"
      )}
    >
      <div className="drawer-stack">
        <div className="drawer-summary">
          <div><span>{l("Количество", "Count")}</span><strong>{lots.length}</strong></div>
          <div><span>{l("Сумма покупки", "Purchase amount")}</span><strong>{excludedPurchaseValueKzt ? formatKzt(excludedPurchaseValueKzt, language) : l("Недоступно", "Unavailable")}</strong></div>
        </div>
        <div className="drawer-section">
          <p>{l(
            "Эти позиции исключены из расчётной балансовой стоимости и операционного итога, а не учтены как ноль, потому что в источнике отсутствует хотя бы одно обязательное поле. Их сумма покупки по-прежнему реальна и подтверждена источником - она просто не входит в показанный итог.",
            "These lots are excluded from the derived carrying value and operational total - not counted as zero - because at least one mandatory source field is missing. Their purchase amount is still real and source-confirmed; it just isn't part of the total shown."
          )}</p>
          <div className="provenance-refs">
            {lots.map((lot) => (
              <div className="evidence-row" key={lot.security_code}>
                <strong>{lot.security_code} · {lot.issuer}</strong>
                <span>
                  {lot.isin} · {l("Сумма покупки", "Purchase amount")}: {formatKzt(lot.purchase_amount_kzt, language)}
                </span>
                <small>
                  {l("Отсутствует", "Missing")}: {lot.missing_fields.map((field) => MISSING_FIELD_LABELS[field]?.[language] ?? field).join(", ")}
                </small>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Drawer>
  );
}
