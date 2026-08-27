import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/**
 * Client-side search for a panel's rendered table rows. It deliberately
 * scopes itself to the nearest panel so several tables on one page do not
 * interfere with one another. Existing source-row click handlers remain
 * attached to the rows; search only toggles their visibility.
 */
export function TableSearch({ label, placeholder }: { label: string; placeholder: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [term, setTerm] = useState("");

  useEffect(() => {
    const panel = inputRef.current?.closest(".panel");
    if (!panel) return;
    const normalized = term.trim().toLocaleLowerCase();
    panel.querySelectorAll<HTMLElement>("tbody tr").forEach((row) => {
      const matches = !normalized || row.textContent?.toLocaleLowerCase().includes(normalized);
      row.classList.toggle("table-row--search-hidden", !matches);
    });
    return () => {
      panel.querySelectorAll<HTMLElement>("tbody tr.table-row--search-hidden").forEach((row) => row.classList.remove("table-row--search-hidden"));
    };
  }, [term]);

  return <label className="search-field table-search-field">
    <Search aria-hidden="true" />
    <span className="sr-only">{label}</span>
    <input ref={inputRef} value={term} onChange={(event) => setTerm(event.target.value)} placeholder={placeholder} aria-label={label} />
  </label>;
}
