import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

// Audits the actual frontend upload UX (not just the backend parser) against
// every real workbook the user has in sources/. Runs against the disposable
// e2e backend (its own temp SQLite DB - see playwright.config.ts), never the
// persistent local dashboard, so it is always safe to re-run.
//
// sources/ holds real client financial data and is gitignored on purpose -
// it only ever exists on a machine someone has deliberately placed it on
// (never a CI checkout). Skipping here - loudly, as "skipped" rather than
// silently excluding the file from the test run - keeps CI honestly green
// without ever claiming this audit passed in an environment that can't
// possibly satisfy it.
const SOURCES = path.resolve("../sources");
const FIXTURES = path.resolve("e2e/fixtures");
const SOURCES_AVAILABLE = fs.existsSync(SOURCES);

test.beforeEach(async ({ page }) => {
  test.skip(!SOURCES_AVAILABLE, "sources/ (real, gitignored client workbooks) is not present in this environment");
  await page.addInitScript(() => {
    window.sessionStorage.setItem("osip-dashboard-language", "ru");
  });
});

const MULTI_SOURCE_FILES: Array<{ name: string; file: string; expectedSourceType: string; expectedPartitions: number }> = [
  { name: "Clients/Brokerage dashboard", file: "Клиентский_дашборд.xlsx", expectedSourceType: "client_brokerage", expectedPartitions: 6 },
  { name: "Corporate finance", file: "Направление_Корпфин_01072026.xlsx", expectedSourceType: "corporate_finance", expectedPartitions: 1 },
  { name: "TABYS fund portfolio", file: "Бэк офис_УИП_ Портфель TABYS Capital -19.07.26.xlsx", expectedSourceType: "tabys_valuation", expectedPartitions: 6 },
  { name: "TABYS unit price history", file: "Бэк офис_УИП_ Стоимость пая Tabys Capital 19.07.2026.xlsx", expectedSourceType: "fund_unit_history", expectedPartitions: 2 },
  // Both accounting contracts always propose two datasets (landing evidence
  // + the detailed one), unconditionally - see detect_source's
  // accounting_budget_landing/accounting_portfolio_landing branches, and
  // the matching backend assertions in tests/test_multi_source.py
  // (test_accounting_portfolio_detail_parses_positions_and_grand_total and
  // the sibling budget test). This test was written before budget_detail
  // was added (2026-07-24 vs. 2026-07-28's "accounting cockpit Phase 2"),
  // so expectedPartitions: 1 was correct when written but never updated.
  { name: "Accounting budget", file: "Бухгалтерия_Бюджет 2026.xlsx", expectedSourceType: "accounting_budget_landing", expectedPartitions: 2 },
  { name: "Accounting portfolio landing", file: "Бухгалтерия_Портфель.xls", expectedSourceType: "accounting_portfolio_landing", expectedPartitions: 2 },
  { name: "Risk limits - SOBSTV", file: "Риски_Собств_Лимиты на 01.07.26.xls", expectedSourceType: "risk_limits_sobstv", expectedPartitions: 1 },
  { name: "Risk limits - TABYS", file: "Риски_Tabys_Лимиты на 01.07.26.xls", expectedSourceType: "risk_limits_tabys", expectedPartitions: 1 }
];

const OSIP_FILES: Array<{ name: string; file: string; portfolioCode: string }> = [
  { name: "OSIP portfolio - SOBSTV", file: "Бэк офис_УИП_ ОСИП собственный портфель 19.07.2026.xls", portfolioCode: "SOBSTV" },
  { name: "OSIP portfolio - TABYS", file: "Бэк офис_УИП_ ОСИП ТАбыс 19.07.2026.xls", portfolioCode: "TABYS" }
];

for (const spec of MULTI_SOURCE_FILES) {
  test(`multi-source upload: ${spec.name}`, async ({ page }) => {
    // sources/ existing doesn't mean every individual workbook in it does -
    // check the specific fixture this test needs, so a missing file skips
    // cleanly (with its name) instead of throwing ENOENT out of setInputFiles.
    test.skip(!fs.existsSync(path.join(SOURCES, spec.file)), `Fixture not present: ${spec.file}`);
    await page.goto("/imports");
    const zone = page.locator(".upload-zone", { hasText: "Выберите рабочую книгу .xls или .xlsx" });
    await expect(zone).toBeVisible();
    await zone.locator('input[type="file"]').setInputFiles(path.join(SOURCES, spec.file));

    // Detection must resolve to an actionable state - either a recognized
    // source with partitions to create, or a visible error. Never a silent
    // hang or unhandled crash. Scoped to the detection banner specifically -
    // the disposable e2e backend also seeds demo fixtures whose registry
    // rows can otherwise collide with a loose text match.
    const detectedBanner = page.locator(".alert-banner--success", { hasText: "Источник определён" });
    await expect(detectedBanner).toBeVisible({ timeout: 15_000 });
    await expect(detectedBanner).toContainText(spec.expectedSourceType);

    const partitionTable = page.locator("table").filter({ has: page.locator("th", { hasText: "Раздел" }) });
    await expect(partitionTable.locator("tbody tr")).toHaveCount(spec.expectedPartitions);

    const createButton = page.getByRole("button", { name: "Создать выбранные наборы" });
    await expect(createButton).toBeEnabled();
    await createButton.click();

    // Materialization + source-first auto-publish should surface the new
    // dataset rows in the registry table below without any inline error.
    await expect(page.locator(".inline-error")).toHaveCount(0);
    await expect(page.getByText("Рабочие книги домена доступны сразу")).toBeVisible({ timeout: 15_000 });
  });
}

test("uploading an external workbook with an unrecognized structure fails clearly, not silently", async ({ page }) => {
  // A real bank/vendor statement, or any workbook that isn't one of this
  // app's known source contracts - the frontend must surface a clear,
  // actionable error and never claim a partition table it can't back up.
  await page.goto("/imports");
  const zone = page.locator(".upload-zone", { hasText: "Выберите рабочую книгу .xls или .xlsx" });
  await zone.locator('input[type="file"]').setInputFiles(path.join(FIXTURES, "unknown-external-statement.xlsx"));
  await expect(page.locator(".inline-error", { hasText: "не соответствует известному контракту" })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".alert-banner--success", { hasText: "Источник определён" })).toHaveCount(0);
  await expect(page.locator("table").filter({ has: page.locator("th", { hasText: "Раздел" }) })).toHaveCount(0);
});

test("uploading a corrupted or non-workbook file fails clearly, not silently", async ({ page }) => {
  await page.goto("/imports");
  const zone = page.locator(".upload-zone", { hasText: "Выберите рабочую книгу .xls или .xlsx" });
  await zone.locator('input[type="file"]').setInputFiles({
    name: "renamed-not-a-workbook.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: Buffer.from("this is plain text pretending to be a workbook, not a real .xlsx file")
  });
  await expect(page.locator(".inline-error", { hasText: "корректные рабочие книги" })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".alert-banner--success", { hasText: "Источник определён" })).toHaveCount(0);
});

for (const spec of OSIP_FILES) {
  test(`OSIP upload: ${spec.name}`, async ({ page }) => {
    test.skip(!fs.existsSync(path.join(SOURCES, spec.file)), `Fixture not present: ${spec.file}`);
    await page.goto("/imports?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
    await page.getByRole("textbox", { name: "Код портфеля" }).fill(spec.portfolioCode);
    await page.locator('input[type="file"][accept=".xls,application/vnd.ms-excel"]').setInputFiles(
      path.join(SOURCES, spec.file)
    );
    await expect(page.getByText("Проверка рабочей книги…")).toBeHidden({ timeout: 15_000 });
    await expect(page.locator(".inline-error")).toHaveCount(0);
    await expect(page.locator("tbody tr", { hasText: spec.file })).toBeVisible();
  });
}

test("all domain pages render real data after every source file is uploaded", async ({ page }) => {
  test.setTimeout(90_000);
  const missing = [...MULTI_SOURCE_FILES, ...OSIP_FILES]
    .map((spec) => spec.file)
    .filter((file) => !fs.existsSync(path.join(SOURCES, file)));
  test.skip(missing.length > 0, `Fixture(s) not present: ${missing.join(", ")}`);
  // Upload everything first (multi-source, then OSIP so the back-office
  // portfolio view is also populated), then verify each page that consumes
  // this data actually shows it - the point of the audit isn't just "did the
  // upload succeed" but "does the resulting UI show real numbers."
  await page.goto("/imports");
  for (const spec of MULTI_SOURCE_FILES) {
    const zone = page.locator(".upload-zone", { hasText: "Выберите рабочую книгу .xls или .xlsx" });
    await zone.locator('input[type="file"]').setInputFiles(path.join(SOURCES, spec.file));
    await expect(page.getByText("Источник определён")).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Создать выбранные наборы" }).click();
    await expect(page.getByText("Рабочие книги домена доступны сразу")).toBeVisible({ timeout: 15_000 });
  }
  await page.goto("/imports?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  for (const spec of OSIP_FILES) {
    await page.getByRole("textbox", { name: "Код портфеля" }).fill(spec.portfolioCode);
    await page.locator('input[type="file"][accept=".xls,application/vnd.ms-excel"]').setInputFiles(
      path.join(SOURCES, spec.file)
    );
    await expect(page.getByText("Проверка рабочей книги…")).toBeHidden({ timeout: 15_000 });
  }

  // Accounting is deliberately excluded here: module_payload() hardcodes
  // available=False for it always (landing/DQ-precheck only, never a
  // published-metrics domain) - showing the "not available yet" marker there
  // is correct behavior, not a sign the upload failed.
  const checks: Array<{ route: string; heading: string }> = [
    { route: "/clients", heading: "Клиенты" },
    { route: "/brokerage", heading: "Брокерская деятельность" },
    { route: "/corporate-finance", heading: "Корпоративные финансы" },
    { route: "/asset-management", heading: "Управление активами" },
    { route: "/risk", heading: "Риски и лимиты" }
  ];
  for (const { route, heading } of checks) {
    await page.goto(`${route}?portfolio=SOBSTV&basis=derived_carrying&currency=KZT`);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await expect(page.locator(".state-card__spinner")).toHaveCount(0);
    // "Functionality is not available yet" is this app's own honest-unavailable
    // marker - its presence here means a domain that should now have real
    // uploaded data is still showing the pre-upload empty state.
    await expect(page.getByText("Функциональность пока недоступна")).toHaveCount(0);
  }

  // Accounting gets its own check: landing rows should be visible even
  // though the module never flips to "available".
  await page.goto("/accounting?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.getByRole("heading", { name: "Бухгалтерия", level: 1 })).toBeVisible();
});
