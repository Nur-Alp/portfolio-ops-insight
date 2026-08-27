import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LanguageProvider, useI18n } from ".";
import { formatDate, formatKzt } from "../lib/format";

function Probe() {
  const { language, setLanguage, t } = useI18n();
  return <>
    <span>{t("nav.overview")}</span>
    <span>{formatKzt(1200, language)}</span>
    <span>{formatDate("2026-07-15", language)}</span>
    <span>{formatDate(null, language)}</span>
    <button onClick={() => setLanguage("en")}>EN</button>
    <button onClick={() => setLanguage("ru")}>RU</button>
  </>;
}

describe("LanguageProvider", () => {
  afterEach(() => window.sessionStorage.clear());

  it("defaults to Russian and remembers the session choice", () => {
    // Override the test suite's own global English default (test/setup.ts)
    // to actually exercise a fresh session with no stored preference at all.
    window.sessionStorage.removeItem("osip-dashboard-language");
    render(<LanguageProvider><Probe /></LanguageProvider>);
    expect(screen.getByText("Обзор портфеля")).toBeInTheDocument();
    expect(screen.getByText(/1\s200 ₸/)).toBeInTheDocument();
    expect(screen.getByText(/июл/i)).toBeInTheDocument();
    expect(screen.getByText("Недоступно")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByText("Portfolio overview")).toBeInTheDocument();
    expect(window.sessionStorage.getItem("osip-dashboard-language")).toBe("en");
  });
});
