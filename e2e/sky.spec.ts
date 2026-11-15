import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { descriptor, NOT_ENOUGH_SEASONS, pValue, qValue, rate, reading, significance } from "../lib/trends/format";
import type { CellFile, IndicatorKey, Trend, TrendIndex } from "../lib/trends/types";

const read = <T>(path: string): T => JSON.parse(readFileSync(join(__dirname, "..", "public", path), "utf8")) as T;

const index = read<TrendIndex>("trends/index.json");
const katete = index.places.find((p) => p.id === "katete")!;
const cellPath = `trends/cells/${katete.cell}.json`;
const cell = read<CellFile>(cellPath);
const summary = index.cells.find((c) => c.id === katete.cell)!;

test.use({ viewport: { width: 1920, height: 1080 } });

function pageErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

const sky = (page: Page) => page.getByRole("region", { name: "SKY" });

async function chooseIndicator(page: Page, key: IndicatorKey) {
  await sky(page).getByRole("button", { name: /Indicator/ }).click();
  await page.getByRole("option", { name: new RegExp(`^${cell.indicators[key].label}`) }).click();
  await expect(sky(page).getByRole("button", { name: /Indicator/ })).toContainText(cell.indicators[key].label);
}

async function expectVerdict(panel: Locator, trend: Trend, unit: string) {
  const r = rate(trend, unit);
  const howMuch = panel.getByTestId("how-much");
  await expect(howMuch).toContainText(r.figure);
  await expect(howMuch).toContainText(r.unit);
  await expect(howMuch).toContainText(r.range);
  const significant = panel.getByTestId("significant");
  await expect(significant).toContainText(significance(trend));
  await expect(significant).toContainText(pValue(trend.mk_p, trend.alpha));
  if (trend.mk_p >= 0.05) await expect(significant).toContainText("not statistically significant");
  else await expect(significant).toContainText("Yes");
}

// the Sen line's start and end in pixels, read from the drawn path
async function senLine(panel: Locator) {
  const d = await panel.getByTestId("sen-line").getAttribute("data-d");
  const [x1, y1, x2, y2] = (d ?? "").match(/-?[\d.]+/g)!.map(Number);
  return { x1, y1, x2, y2 };
}

test("(a) Katete, October temperature, all seasons: the verdict matches the cell file", async ({ page }) => {
  const errors = pageErrors(page);
  await page.goto("/mission/?place=katete");
  await chooseIndicator(page, "october_temp_c");
  const panel = sky(page);
  const indicator = cell.indicators.october_temp_c;
  const trend = indicator.trend!;

  await expect(panel.getByRole("radio", { name: "All" })).toBeChecked();
  await expectVerdict(panel, trend, indicator.unit);
  await expect(panel.getByTestId("how-much")).toContainText(`+${trend.slope_per_decade.toFixed(2)}`);
  await expect(panel.getByTestId("how-much")).toContainText(
    `(${trend.ci_low_per_decade.toFixed(2)} to ${trend.ci_high_per_decade.toFixed(2)})`,
  );
  const q = summary.indicators?.october_temp_c?.q;
  if (q != null) await expect(panel.getByTestId("significant")).toContainText(`${qValue(q, trend.alpha)} across all cells`);
  await expect(panel).toContainText(descriptor(cell, "october_temp_c"));

  const dots = panel.locator("[data-season]");
  await expect(dots).toHaveCount(indicator.series.filter((s) => s.value !== null).length);
  const sample = indicator.series[Math.floor(indicator.series.length / 2)];
  // hover again if the dot was still moving when the pointer arrived
  await expect(async () => {
    await page.mouse.move(0, 0);
    await panel.locator(`[data-season="${sample.season}"]`).hover();
    await expect(page.getByRole("tooltip")).toHaveText(`${sample.label}: ${reading(sample.value!, indicator.unit)}`, { timeout: 2000 });
  }).toPass({ timeout: 20_000 });

  const line = await senLine(panel);
  expect(Math.sign(line.y1 - line.y2)).toBe(Math.sign(trend.slope_per_decade));
  expect(errors).toEqual([]);
});

test("(b) ten seasons: the line and the verdict switch to the 10-season window", async ({ page }) => {
  const errors = pageErrors(page);
  await page.goto("/mission/?place=katete");
  await chooseIndicator(page, "october_temp_c");
  const panel = sky(page);
  const indicator = cell.indicators.october_temp_c;
  const all = await senLine(panel);

  await panel.getByRole("radio", { name: "10", exact: true }).click();
  const window = indicator.windows["10"]!;
  await expectVerdict(panel, window, indicator.unit);
  await expect(panel.getByTestId("significant")).not.toContainText("across all cells");

  await expect.poll(async () => (await senLine(panel)).x1).not.toBe(all.x1);
  const ten = await senLine(panel);
  expect(Math.sign(ten.y1 - ten.y2)).toBe(Math.sign(window.slope_per_decade));
  const used = indicator.series.slice(-10).map((s) => String(s.season));
  const inWindow = await panel.locator('[data-in-window="true"]').evaluateAll((els) => els.map((el) => el.getAttribute("data-season")));
  expect(inWindow).toEqual(used);
  expect(errors).toEqual([]);
});

test("(c) wet-season rainfall shows the wording that matches its p-value", async ({ page }) => {
  const errors = pageErrors(page);
  await page.goto("/mission/?place=katete");
  await chooseIndicator(page, "wet_season_rain_mm");
  const indicator = cell.indicators.wet_season_rain_mm;
  await expectVerdict(sky(page), indicator.trend!, indicator.unit);
  expect(errors).toEqual([]);
});

test("(g) a cell with 9 seasons has no test, and a cell that failed to download says so", async ({ page }) => {
  const errors = pageErrors(page);
  const short: CellFile = structuredClone(cell);
  for (const indicator of Object.values(short.indicators)) {
    indicator.series = indicator.series.slice(-9);
    indicator.trend = null;
    indicator.windows = { "10": null, "20": null, "30": null };
    if (indicator.second_source) indicator.second_source.trend = null;
  }
  await page.route(`**/${cellPath}`, (route) => route.fulfill({ json: short }));
  await page.goto("/mission/?place=katete");
  const panel = sky(page);
  await expect(panel.getByText(NOT_ENOUGH_SEASONS, { exact: true })).toBeVisible();
  await expect(panel.locator("[data-season]")).toHaveCount(9);
  await expect(panel.getByTestId("sen-line")).toHaveCount(0);
  await panel.getByRole("radio", { name: "10", exact: true }).click();
  await expect(panel.getByText(NOT_ENOUGH_SEASONS, { exact: true })).toBeVisible();
  expect(errors).toEqual([]);

  const broken: TrendIndex = structuredClone(index);
  const target = broken.cells.find((c) => c.id === katete.cell)!;
  target.error = "download failed";
  delete target.indicators;
  await page.unroute(`**/${cellPath}`);
  await page.route("**/trends/index.json", (route) => route.fulfill({ json: broken }));
  await page.goto("/mission/?place=katete");
  await expect(panel.getByText("NASA data for this cell could not be downloaded when the trends were built.")).toBeVisible();
  await expect(panel.locator("[data-season]")).toHaveCount(0);
  expect(errors).toEqual([]);
});
