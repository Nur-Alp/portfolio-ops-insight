import { Bell } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { dashboardApi } from "../../api/client";
import { formatDate } from "../../lib/format";
import { useI18n } from "../../i18n";
import { navigation } from "./AppShell";

// Reuses the same open action items already shown per-domain on the Risk
// and Accounting pages (ActionItemsPanel in domain-panels/shared.tsx) -
// this is just an always-visible, cross-domain view of that same data,
// scoped server-side to the actor's own accessible domains.
function domainRoute(domain: string): "/operations" | (typeof navigation)[number]["to"] {
  const match = navigation.find((item) => "domain" in item && item.domain === domain);
  return match ? match.to : "/operations";
}

export function NotificationBell() {
  const { t, language } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const items = useQuery({
    queryKey: ["action-items", "open", "notification-bell"],
    queryFn: () => dashboardApi.actionItems(undefined, "open"),
    refetchInterval: 60_000
  });
  const list = items.data?.items ?? [];

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="notification-bell" ref={containerRef}>
      <button
        type="button"
        className="icon-button"
        aria-label={`${t("top.notifications")}${list.length ? ` (${list.length})` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell aria-hidden="true" />
        {list.length ? <span className="notification-bell__badge">{list.length > 9 ? "9+" : list.length}</span> : null}
      </button>
      {open ? (
        <div className="notification-bell__panel" role="menu" aria-label={t("top.notifications")}>
          <header className="notification-bell__header">{t("top.notifications")}</header>
          {list.length ? (
            <ul className="notification-bell__list">
              {list.slice(0, 20).map((item) => (
                <li key={item.id}>
                  <Link to={domainRoute(item.domain) as never} onClick={() => setOpen(false)}>
                    <strong>{item.title}</strong>
                    <span>
                      {item.domain}
                      {item.due_date ? ` · ${formatDate(item.due_date, language)}` : ""}
                      {item.is_overdue ? ` · ${t("top.notifications.overdue")}` : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="notification-bell__empty">{t("top.notifications.empty")}</p>
          )}
          <Link className="notification-bell__viewall" to={"/operations" as never} onClick={() => setOpen(false)}>
            {t("top.notifications.viewAll")}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
