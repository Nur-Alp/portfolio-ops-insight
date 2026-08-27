import { AlertTriangle, DatabaseZap } from "lucide-react";
import type { ReactNode } from "react";
import { useI18n } from "../../i18n";

export function LoadingState({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="state-card" role="status" aria-live="polite">
      <span className="state-card__spinner" aria-hidden="true" />
      <strong>{label ?? t("async.loading")}</strong>
      <span>{t("async.loadingDetail")}</span>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="state-card state-card--error" role="alert">
      <AlertTriangle aria-hidden="true" />
      <strong>{t("async.error")}</strong>
      <span>{error.message}</span>
      {retry ? (
        <button className="button button--secondary" type="button" onClick={retry}>
          {t("common.retry")}
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
  action
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-card">
      <DatabaseZap aria-hidden="true" />
      <strong>{title}</strong>
      <span>{detail}</span>
      {action}
    </div>
  );
}
