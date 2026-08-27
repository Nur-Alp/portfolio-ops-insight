import type { ReactNode } from "react";
import type { Basis } from "../../api/types";
import { BasisBadge } from "./BasisBadge";

export function KpiCard({
  label,
  value,
  basis,
  detail,
  tone = "neutral",
  icon,
  onBasisClick,
  alertLabel,
  onAlertClick
}: {
  label: string;
  value: string;
  basis: Basis;
  detail?: string;
  tone?: "neutral" | "positive" | "warning" | "danger";
  icon?: ReactNode;
  onBasisClick?: () => void;
  // A short, always-bounded call to action (e.g. "3 excluded") - separate
  // from `detail` because detail is meant for a plain caption, not
  // something whose real content (a list of names) can't be squeezed into
  // one card's footer no matter how many there are. This button only ever
  // has to fit a count, and hands the actual list off to onAlertClick
  // (typically the same provenance drawer onBasisClick already opens).
  alertLabel?: string;
  onAlertClick?: () => void;
}) {
  return (
    <article className={`kpi-card kpi-card--${tone}`}>
      <div className="kpi-card__topline">
        <span className="kpi-card__label">{label}</span>
        {icon}
      </div>
      <strong className={`kpi-card__value ${value.length > 18 ? "kpi-card__value--wrap" : ""}`}>{value}</strong>
      <div className="kpi-card__footer">
        <BasisBadge basis={basis} onClick={onBasisClick} ariaLabel={`${label}: ${basis}`} />
        {detail ? <span className="kpi-card__detail" title={detail}>{detail}</span> : null}
        {alertLabel ? <button type="button" className="kpi-card__alert" onClick={onAlertClick}>{alertLabel}</button> : null}
      </div>
    </article>
  );
}
