import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { dashboardApi } from "../../api/client";
import { isOidcMode, type DomainScope } from "../../auth/session";
import { useSelectedSnapshot } from "../../hooks/useSelectedSnapshot";
import { useI18n } from "../../i18n";
import { navigation } from "./AppShell";

type NavPaletteItem = { kind: "nav"; key: string; to: (typeof navigation)[number]["to"]; label: string };
type InstrumentPaletteItem = { kind: "instrument"; key: string; isin: string; label: string; detail: string };
type PaletteItem = NavPaletteItem | InstrumentPaletteItem;

export function CommandPalette({
  open,
  onClose,
  domainScope,
  actorDomains
}: {
  open: boolean;
  onClose: () => void;
  domainScope: DomainScope;
  actorDomains?: readonly string[];
}) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { search, snapshotId } = useSelectedSnapshot();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const instruments = useQuery({
    queryKey: ["holdings", snapshotId, "instruments"],
    queryFn: () => dashboardApi.instrumentHoldings(snapshotId),
    enabled: open && Boolean(snapshotId)
  });

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(focusTimer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const normalized = query.trim().toLocaleLowerCase();

  const navItems = useMemo<NavPaletteItem[]>(
    () =>
      navigation
        .filter((item) => {
          const domain = "domain" in item ? item.domain : undefined;
          if (!domain) return true;
          if (!isOidcMode()) return domainScope === "*" || domain === domainScope;
          return Boolean(actorDomains?.includes("*") || actorDomains?.includes(domain));
        })
        .map((item) => ({ kind: "nav" as const, key: item.to, to: item.to, label: t(item.labelKey) }))
        .filter((item) => !normalized || item.label.toLocaleLowerCase().includes(normalized)),
    [actorDomains, domainScope, normalized, t]
  );

  const instrumentItems = useMemo<InstrumentPaletteItem[]>(() => {
    if (!normalized) return [];
    return (instruments.data?.items ?? [])
      .filter((item) =>
        [item.isin, item.security_code, item.issuer].some((value) =>
          value.toLocaleLowerCase().includes(normalized)
        )
      )
      .slice(0, 8)
      .map((item) => ({
        kind: "instrument" as const,
        key: item.isin,
        isin: item.isin,
        label: item.security_code || item.isin,
        detail: `${item.isin} · ${item.issuer}`
      }));
  }, [instruments.data, normalized]);

  const items = useMemo(() => [...navItems, ...instrumentItems], [navItems, instrumentItems]);

  useEffect(() => {
    setActiveIndex((current) => Math.min(current, Math.max(items.length - 1, 0)));
  }, [items.length]);

  if (!open) return null;

  const activate = (item: PaletteItem) => {
    if (item.kind === "nav") {
      navigate({ to: item.to, search });
    } else {
      navigate({ to: "/holdings", search: { ...search, term: item.isin } });
    }
    onClose();
  };

  const onInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => Math.min(current + 1, Math.max(items.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = items[activeIndex];
      if (item) activate(item);
    }
  };

  return (
    <div className="palette-layer" role="presentation" onMouseDown={onClose}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label={t("palette.title")}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="palette__input-row">
          <Search aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder={t("palette.placeholder")}
            aria-label={t("palette.title")}
          />
          <button type="button" className="icon-button" aria-label={t("palette.close")} onClick={onClose}>
            Esc
          </button>
        </div>
        <div className="palette__results">
          {navItems.length ? (
            <div className="palette__section">
              <p className="palette__section-label">{t("palette.navigation")}</p>
              {navItems.map((item) => {
                const index = items.indexOf(item);
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`palette__item ${index === activeIndex ? "palette__item--active" : ""}`}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => activate(item)}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          ) : null}
          {normalized ? (
            <div className="palette__section">
              <p className="palette__section-label">{t("palette.instruments")}</p>
              {instrumentItems.length ? (
                instrumentItems.map((item) => {
                  const index = items.indexOf(item);
                  return (
                    <button
                      key={item.key}
                      type="button"
                      className={`palette__item ${index === activeIndex ? "palette__item--active" : ""}`}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => activate(item)}
                    >
                      <strong>{item.label}</strong>
                      <span>{item.detail}</span>
                    </button>
                  );
                })
              ) : (
                <p className="palette__empty">{t("palette.noResults")}</p>
              )}
            </div>
          ) : null}
        </div>
        <div className="palette__hint">{t("palette.hint")}</div>
      </div>
    </div>
  );
}
