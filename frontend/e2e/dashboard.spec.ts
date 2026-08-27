import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import path from "node:path";

// The app defaults new visitors to English; this suite's assertions and the
// committed visual baselines are Russian, so every test forces that language
// before the app's first render rather than relying on the "RU"/"EN" toggle.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.sessionStorage.setItem("osip-dashboard-language", "ru");
  });
});

const routes = [
  ["/", "Обзор портфеля"],
  ["/holdings", "Позиции"],
  ["/cash-calendar", "Деньги и календарь"],
  ["/data-quality", "Качество данных"],
  ["/imports", "Загрузки источников"],
  ["/reporting", "Экспорт OSIP"],
  ["/comparison", "Сравнение портфелей"],
  ["/asset-management", "Управление активами"],
  ["/treasury", "Казначейство"],
  ["/brokerage", "Брокерская деятельность"],
  ["/clients", "Клиенты"],
  ["/corporate-finance", "Корпоративные финансы"],
  ["/operations", "Операции и сверки"],
  ["/accounting", "Бухгалтерия"],
  ["/risk", "Риски и лимиты"]
] as const;

for (const [route, heading] of routes) {
  test(`${heading} renders live data without serious accessibility violations`, async ({ page }) => {
    const runtimeErrors: string[] = [];
    page.on("pageerror", (error) => runtimeErrors.push(error.message));
    await page.goto(`${route}?portfolio=SOBSTV&basis=derived_carrying&currency=KZT`);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await expect(page.locator(".state-card__spinner")).toHaveCount(0);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
      .analyze();
    expect(results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""))).toEqual([]);
    expect(runtimeErrors).toEqual([]);
  });
}

const sourcePreviewRoutes = [
  ["/risk", "Риски и лимиты"],
  ["/accounting", "Бухгалтерия"],
  ["/clients", "Клиенты"],
  ["/brokerage", "Брокерская деятельность"]
] as const;

for (const [route, heading] of sourcePreviewRoutes) {
  test(`${heading} keeps source preview discoverable and keyboard-operable`, async ({ page }) => {
    await page.goto(`${route}?portfolio=SOBSTV&basis=derived_carrying&currency=KZT`);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();

    // The single marker belongs in a panel header. Provenance is an action on
    // the whole row, never a bulky source column or a per-row dot.
    await expect(page.locator(".panel__header .source-row-legend").first()).toBeVisible();
    await expect(page.locator(".source-cell:visible")).toHaveCount(0);
    await expect(page.getByRole("columnheader", { name: "Источник" })).toHaveCount(0);

    const row = page.locator("tr[data-source-row]").first();
    await expect(row).toBeVisible();
    await row.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Просмотр исходной ячейки" })).toBeVisible();

    // Regression: for every non-OSIP domain, the preview response's
    // import_id is a DatasetVersion id, not an ImportBatch id - the
    // "Download original" button used to call the OSIP-only
    // /imports/{import_id}/source endpoint regardless, which always 404s
    // for these rows. It must resolve to a real file download instead.
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Скачать оригинал" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.xlsx?$/);
    await expect(page.locator(".inline-error", { hasText: "Ошибка запроса" })).toHaveCount(0);

    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await expect(row).toBeFocused();
  });
}

test("maturity calendar places its source-preview legend in the panel header", async ({ page }) => {
  await page.goto("/clients?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  const calendarPanel = page.getByRole("heading", { name: "Календарь погашения", level: 2 }).locator("xpath=ancestor::section");
  await expect(calendarPanel.locator(".panel__header .source-row-legend")).toBeVisible();
  await expect(calendarPanel.locator(".panel__body > .source-table-legend")).toHaveCount(0);
});

test("compare portfolios button opens the comparison page with both portfolios", async ({ page }) => {
  await page.goto("/?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  await page.getByRole("button", { name: "Сравнить портфели" }).click();
  await expect(page).toHaveURL(/\/comparison/);
  await expect(page.getByRole("heading", { name: "Сравнение портфелей", level: 1 })).toBeVisible();
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  await expect(page.locator(".comparison-identity__side h3").filter({ hasText: "SOBSTV" })).toBeVisible();
  await expect(page.locator(".comparison-identity__side h3").filter({ hasText: "TABYS" })).toBeVisible();
});

test("holdings instrument row opens immutable lot evidence", async ({ page }) => {
  await page.goto("/holdings?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  const firstRow = page.locator("tbody tr").first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Составляющие лоты" })).toBeVisible();
  await expect(page.getByText("Лоты источника").first()).toBeVisible();
});

test("data-quality finding opens source evidence and acknowledgement", async ({ page }) => {
  await page.goto("/data-quality?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await page.locator("tbody tr").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Подтверждение источника" })).toBeVisible();
  await expect(page.getByText("Подтвердил: e2e-reviewer")).toBeVisible();
});

test("duplicate upload is idempotent through the browser", async ({ page }) => {
  await page.goto("/imports?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  // Regression: reading the row count before the registry's initial fetch
  // resolves races that fetch, and loses more often under the extra load of
  // running after several preceding tests - it can capture 0 rows and then
  // "gain" rows once the real (unrelated to this test) data finishes loading.
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  const rowsBefore = await page.locator("tbody tr").count();
  await page.getByRole("textbox", { name: "Код портфеля" }).fill("SOBSTV");
  await page.locator('input[type="file"][accept=".xls,application/vnd.ms-excel"]').setInputFiles(
    path.resolve("../Portfolio operations/ОСИП Портфель о состоянии текущего портфеля и  предстоящих расчетах по сделкам  СОБСТВ 15.07.2026.xls")
  );
  await expect(page.getByText("Проверка рабочей книги…")).toBeHidden();
  await expect(page.locator("tbody tr")).toHaveCount(rowsBefore);
});

test("published reporting generates a controlled artifact download", async ({ page }) => {
  await page.goto("/reporting?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Сформировать и скачать CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("OSIP-operational-snapshot.csv");
  await expect(page.getByText("Операционная версия портфеля CSV")).toBeVisible();
});

test("responsive shell and primary reference pages match visual baselines", async ({ page }) => {
  // The committed baseline is captured on Ubuntu (see the update-e2e-snapshots
  // CI job) because that's the environment the real check runs in. Chromium's
  // font rasterisation differs enough on macOS to fail on dimension alone,
  // regardless of pixel-diff tolerance, so this is only meaningful in CI.
  test.skip(!process.env.CI, "Visual baselines are Ubuntu-native; run in CI or via update-e2e-snapshots.");
  await page.goto("/?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  await expect(page).toHaveScreenshot("overview-desktop.png", { fullPage: true });
  await page.goto("/holdings?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await expect(page).toHaveScreenshot("holdings-desktop.png", { fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?portfolio=TABYS&basis=purchase&currency=KZT");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  await expect(page).toHaveScreenshot("overview-mobile.png", { fullPage: true });
});

test("command search finds an instrument and jumps to holdings with the term applied", async ({ page }) => {
  await page.goto("/?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  await page.getByRole("button", { name: "Поиск по данным портфеля" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await page.getByPlaceholder("Раздел, инструмент портфеля, ISIN, эмитент…").fill("KZKD00001210");
  await expect(dialog.getByText("A_MUM072_0014")).toBeVisible();
  await dialog.getByText("A_MUM072_0014").click();
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(/\/holdings\?.*term=KZKD00001210/);
  await expect(page.getByPlaceholder("ISIN, тикер, эмитент")).toHaveValue("KZKD00001210");
});

test("command search Escape key closes the palette", async ({ page }) => {
  await page.goto("/?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  await page.getByRole("button", { name: "Поиск по данным портфеля" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("command search updates the holdings filter when used while already on that page", async ({ page }) => {
  await page.goto("/holdings?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.getByRole("button", { name: "Поиск по данным портфеля" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await page.getByPlaceholder("Раздел, инструмент портфеля, ISIN, эмитент…").fill("KZ2C00012904");
  await expect(dialog.getByText("NITCb1")).toBeVisible();
  await dialog.getByText("NITCb1").click();
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(/term=KZ2C00012904/);
  // Regression: useState's initializer only runs on mount, so navigating to
  // the same already-mounted route with a new `term` used to leave this
  // filter showing its stale (empty) value instead of the new search.
  await expect(page.getByPlaceholder("ISIN, тикер, эмитент")).toHaveValue("KZ2C00012904");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody tr")).toContainText("NITCb1");
});

test("sidebar navigation scrolls independently from the page", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 760 });
  await page.goto("/operations");
  const navigation = page.locator(".sidebar nav");
  await expect(navigation).toBeVisible();
  const dimensions = await navigation.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight
  }));
  expect(dimensions.scrollHeight).toBeGreaterThan(dimensions.clientHeight);
  await navigation.evaluate((element) => element.scrollTo({ top: element.scrollHeight }));
  await expect.poll(() => navigation.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: "Операции и сверки", level: 1 })).toBeVisible();
});

test("domain charts render published values and expose hover details", async ({ page }) => {
  await page.goto("/asset-management");
  await expect(page.getByRole("heading", { name: "Управление активами", level: 1 })).toBeVisible();
  const sectors = page.locator(".recharts-pie-sector");
  await expect(sectors).toHaveCount(2);
  await expect(page.locator(".recharts-area-area")).toHaveAttribute("d", /.+/);
  const point = await sectors.first().locator("path").evaluate((path) => {
    const geometry = path as SVGGeometryElement;
    const local = geometry.getPointAtLength(geometry.getTotalLength() / 2);
    const matrix = geometry.getScreenCTM()!;
    return { x: matrix.a * local.x + matrix.c * local.y + matrix.e, y: matrix.b * local.x + matrix.d * local.y + matrix.f };
  });
  await page.mouse.move(point.x, point.y);
  await expect(page.locator(".insight-chart-tooltip")).toBeVisible();
});

test("language switch remains contextual while navigating between domains", async ({ page }) => {
  await page.goto("/operations");
  await page.getByRole("button", { name: "EN" }).click();
  await expect(page.getByRole("heading", { name: "Operations and reconciliations", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "Brokerage" }).click();
  await expect(page.getByRole("heading", { name: "Brokerage", level: 1 })).toBeVisible();
  await expect(page.getByText("Source dates do not match")).toBeVisible();
  await page.getByRole("button", { name: "RU" }).click();
  await expect(page.getByRole("heading", { name: "Брокерская деятельность", level: 1 })).toBeVisible();
});

test("mobile navigation opens, scrolls, navigates, and closes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/brokerage");
  await page.getByRole("button", { name: "Открыть навигацию" }).click();
  const navigation = page.getByRole("complementary", { name: "Основная навигация" });
  await expect(navigation).toBeVisible();
  await navigation.getByRole("link", { name: "Клиенты" }).click();
  await expect(page.getByRole("heading", { name: "Клиенты", level: 1 })).toBeVisible();
  await expect(navigation).not.toHaveClass(/sidebar--open/);
});

// These two tests are deliberately last in the file: they withdraw real
// published data (an OSIP snapshot, a multi-source dataset), which every
// preceding test in this run depends on staying published. Playwright runs
// this file's tests serially (workers: 1) against one shared disposable
// backend, so anything after these two would see the withdrawn state - see
// upload-audit.spec.ts, which is unaffected because it re-uploads its own
// OSIP files rather than relying on the seeded published state.
test("withdrawing a published OSIP version records the reason and clears its published state", async ({ page }) => {
  await page.goto("/imports?portfolio=TABYS&basis=derived_carrying&currency=KZT");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  const row = page.locator("table.clickable-table tbody tr", { hasText: "TABYS" }).first();
  await expect(row).toBeVisible();
  await row.click();
  await expect(page.getByText("Операционная версия портфеля опубликована")).toBeVisible();
  await page.getByLabel("Причина снятия с публикации").fill("E2E: проверка отзыва версии");
  await page.getByRole("button", { name: "Снять версию с публикации" }).click();
  await expect(page.locator(".drawer-summary")).toContainText("Снято с публикации");
  await expect(page.getByText("Операционная версия портфеля опубликована")).toHaveCount(0);
});

test("withdrawing a published multi-source dataset clears its row actions", async ({ page }) => {
  await page.goto("/imports?portfolio=SOBSTV&basis=derived_carrying&currency=KZT");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  const row = page.locator("table")
    .filter({ has: page.locator("th", { hasText: "Действие" }) })
    .locator("tbody tr", { hasText: "corporate_finance_register" });
  await expect(row).toBeVisible();
  await expect(row.locator(".status-pill")).toContainText("Опубликовано");
  const actionCell = row.locator(".workflow-actions");
  page.once("dialog", (dialog) => dialog.accept("E2E: проверка отзыва набора"));
  await actionCell.getByRole("button", { name: "Снять" }).click();
  await expect(row.locator(".status-pill")).toContainText("Снято с публикации");
  await expect(actionCell).toHaveText("—");
});

test("notification bell shows open action items and navigates to the right domain", async ({ page, request }) => {
  await page.goto("/operations");
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);

  const bell = page.getByRole("button", { name: /Уведомления/ });
  await bell.click();
  await expect(page.getByText("Открытых пунктов нет")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByText("Открытых пунктов нет")).toBeHidden();

  // Same call a reviewer's "create action item" form makes; exercises the
  // bell against a real open item rather than only its empty state.
  const created = await request.post("/api/v1/action-items", {
    headers: { "X-Actor-Id": "e2e-reviewer", "X-Actor-Roles": "reader,reviewer", "X-Actor-Domains": "risk", "X-Actor-Portfolios": "*" },
    data: { domain: "risk", kind: "manual", title: "Проверить превышение лимита по эмитенту" }
  });
  expect(created.ok()).toBeTruthy();

  await page.reload();
  await expect(page.locator(".state-card__spinner")).toHaveCount(0);
  await expect(bell.locator(".notification-bell__badge")).toHaveText("1");
  await bell.click();
  await page.getByRole("menu").getByText("Проверить превышение лимита по эмитенту").click();
  await expect(page).toHaveURL(/\/risk/);
});
