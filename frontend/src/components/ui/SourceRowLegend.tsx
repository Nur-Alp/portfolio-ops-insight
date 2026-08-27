export function SourceRowLegend({ language }: { language: "ru" | "en" }) {
  return (
    <span className="source-row-legend">
      <span className="source-row-legend__dot" aria-hidden="true" />
      {language === "en" ? "Source preview" : "Просмотр источника"}
    </span>
  );
}
