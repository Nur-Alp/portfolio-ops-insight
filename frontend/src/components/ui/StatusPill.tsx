import { humanize } from "../../lib/format";
import { useI18n } from "../../i18n";

type Tone = "success" | "warning" | "danger" | "info" | "neutral";

const tones: Record<string, Tone> = {
  published: "success",
  approved: "success",
  validated: "info",
  upcoming: "info",
  historical: "neutral",
  draft: "neutral",
  validating: "info",
  rejected: "danger",
  failed: "danger",
  overdue: "danger",
  blocker: "danger",
  high: "danger",
  medium: "warning",
  date_mismatch: "warning",
  low: "info",
  superseded: "neutral",
  withdrawn: "danger",
  future: "warning",
  ok: "success",
  breach: "danger",
  near_breach: "warning",
  unknown: "warning",
  not_applicable: "neutral",
  unavailable: "neutral",
  open: "info",
  resolved: "success",
  ready: "success",
  due: "warning",
  blocked: "danger",
  missing: "neutral",
  pass: "success",
  fail: "danger"
};

export function StatusPill({ status }: { status: string }) {
  const { language } = useI18n();
  const tone = tones[status.toLowerCase()] ?? "neutral";
  return <span className={`status-pill status-pill--${tone}`}>{humanize(status, language)}</span>;
}
