import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { calendarLine } from "../lib/mission/calendar";
import { descriptor, pValue, qValue, rate, significance } from "../lib/trends/format";
import type { CellFile, IndicatorKey, Trend, TrendIndex } from "../lib/trends/types";

// the live demo of plan section A8, walked with the keyboard in story mode with the simulator

const publicFile = (path: string) => join(__dirname, "..", "public", path);
const read = <T>(path: string): T => JSON.parse(readFileSync(publicFile(path), "utf8")) as T;

type Routes = { hub: { name: string }; routes: Record<string, { km: number; minutes: number }> };

const index = read<TrendIndex>("trends/index.json");
const katete = index.places.find((p) => p.id === "katete")!;
const cell = read<CellFile>(`trends/cells/${katete.cell}.json`);
const route = read<Routes>("map/routes.json").routes.katete;
const hasReplay = existsSync(publicFile("pod/replay.json"));
const results: Record<string, unknown> = existsSync(publicFile("validation/results.json")) ? read("validation/results.json") : {};
const untested = 1 + ["air_temp_c", "heart_rate", "spo2"].filter((kind) => !results[kind]).length;

const trendOf = (key: IndicatorKey, window: "all" | "10" = "all") =>
  (window === "all" ? cell.indicators[key].trend : cell.indicators[key].windows[window]) as Trend;
const summaryOf = (key: IndicatorKey) => index.cells.find((c) => c.id === katete.cell)!.indicators![key]!;

test.use({ viewport: { width: 1920, height: 1080 } });

function watch(page: Page) {
  const errors: string[] = [];
  const foreign: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (!["localhost", "127.0.0.1"].includes(url.hostname) && url.protocol !== "data:" && url.protocol !== "blob:") foreign.push(req.url());
  });
  return { errors, foreign };
}

const story = (page: Page) => page.locator('p[aria-live="polite"]');
const sky = (page: Page) => page.getByRole("region", { name: "SKY" });
const ground = (page: Page) => page.getByRole("region", { name: "GROUND" });
const action = (page: Page) => page.getByRole("region", { name: "ACTION" });
const banner = (page: Page) => page.getByRole("banner");

async function expectStep(page: Page, n: number, question: string, active: string, loopWord: string) {
  await expect(page.getByLabel(/^Story step/)).toHaveText(`${n} / 6`);
  await expect(story(page)).toContainText(question);
  await expect(page.getByRole("region", { name: active })).toHaveAttribute("data-emphasis", "active");
  await expect(banner(page).locator('[aria-current="step"]')).toHaveText(loopWord);
}

async function expectSky(page: Page, key: IndicatorKey, window: "all" | "10") {
  const trend = trendOf(key, window);
  const r = rate(trend, cell.indicators[key].unit);
  await expect(sky(page).getByRole("button", { name: /Indicator/ })).toContainText(cell.indicators[key].label);
  await expect(sky(page).getByRole("radio", { name: window === "all" ? "All" : window, exact: true })).toBeChecked();
  for (const part of [r.figure, r.unit, r.range]) await expect(sky(page).getByTestId("how-much")).toContainText(part);
  await expect(sky(page).getByTestId("significant")).toContainText(significance(trend));
  return trend;
}

test("the A8 demo runs on the keyboard, every figure matches the data, and nothing leaves localhost", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/mission/?story=1&sim=1");
  await expect(page.getByRole("combobox", { name: "Place" })).toHaveValue("Katete");
  await expect(banner(page).getByText("SIMULATION", { exact: true })).toBeVisible();

  // 1: the suspect is innocent
  await expectStep(page, 1, "Is the rain disappearing?", "SKY", "Detect");
  const rain = await expectSky(page, "wet_season_rain_mm", "all");
  await expect(sky(page)).toContainText(descriptor(cell, "wet_season_rain_mm"));
  if (!rain.significant) {
    await expect(sky(page).getByTestId("significant")).toContainText("not statistically significant");
    await expect(story(page)).toContainText(`over ${rain.n} seasons is not statistically significant (${pValue(rain.mk_p, rain.alpha)})`);
  }
  const rainQ = summaryOf("wet_season_rain_mm").q;
  if (rainQ != null) await expect(sky(page).getByTestId("significant")).toContainText(`${qValue(rainQ, rain.alpha)} across all cells`);

  // 2: the real change
  await page.keyboard.press("ArrowRight");
  await expectStep(page, 2, "Then what is changing?", "SKY", "Detect");
  const october = await expectSky(page, "october_temp_c", "all");
  expect(october.significant).toBe(true);
  await expect(story(page)).toContainText(`${Math.abs(october.slope_per_decade).toFixed(2)} °C per decade over ${october.n} seasons`);

  // 3: the record switch flips to 10 seasons and the line turns the other way
  await page.keyboard.press("ArrowRight");
  await expectStep(page, 3, "Why ten years is not enough.", "SKY", "Detect");
  const ten = await expectSky(page, "october_temp_c", "10");
  expect(ten.n).toBe(10);
  const way = (t: Trend) => (t.direction === "increasing" ? "up" : "down");
  await expect(story(page)).toContainText(`The last 10 seasons alone point ${way(ten)} by ${Math.abs(ten.slope_per_decade).toFixed(2)} °C per decade`);
  await expect(story(page)).toContainText(`Over ${october.n} seasons the trend is ${way(october)}.`);
  if (!ten.significant) {
    await expect(sky(page).getByTestId("significant")).toContainText("not statistically significant");
    await expect(story(page)).toContainText(`but that is not statistically significant (${pValue(ten.mk_p, ten.alpha)})`);
  }

  // 4: where; solid outlines are the cells that survive the correction
  await page.keyboard.press("ArrowRight");
  await expectStep(page, 4, "Where?", "Map", "Detect");
  await expectSky(page, "october_temp_c", "all");
  const tested = index.cells.filter((c) => !c.error && c.indicators?.october_temp_c?.mk_p != null);
  const strong = tested.filter((c) => c.indicators?.october_temp_c?.significant_fdr);
  await expect(story(page)).toContainText(`${strong.length} of ${tested.length} grid cells`);
  await expect(page.locator('[data-map-ready] [data-outline-for][data-style="solid"]')).toHaveCount(strong.length);

  // 5: the pod checks the ground, labelled as simulation
  await page.keyboard.press("ArrowRight");
  await expectStep(page, 5, "Check the ground.", "GROUND", "Verify");
  await expect(ground(page).getByText("simulation", { exact: true })).toBeVisible();
  for (const name of ["Temperature", "Humidity", "Heart rate", "SpO2"]) {
    await expect(ground(page).getByRole("group", { name, exact: true })).toBeVisible();
  }
  await expect(ground(page).getByText(/^Not yet tested against a reference: /)).toHaveCount(untested > 0 ? 1 : 0);

  // the patient answers the danger sign question; the only step that needs the mouse
  await ground(page).getByRole("button", { name: "Yes", exact: true }).click();
  await ground(page).getByRole("button", { name: "very sleepy or hard to wake" }).click();
  await expect(ground(page).getByTestId("answer").last()).toHaveText("very sleepy or hard to wake");

  // 6: act
  await page.keyboard.press("ArrowRight");
  await expectStep(page, 6, "Act.", "ACTION", "Act");
  await expect(action(page).getByText("Decision support, not a diagnosis.")).toBeVisible();
  await expect(action(page).getByRole("group", { name: "Triage" })).toContainText("Urgent referral");
  await expect(action(page).getByRole("group", { name: "Order" })).toContainText("Referral transport to the nearest hospital");
  const delivery = action(page).getByRole("group", { name: "Delivery" });
  await expect(delivery).toContainText(`${route.km} km by road, ${route.minutes} min`);
  await expect(delivery).toContainText("simulated vehicle");
  await expect(page.locator("[data-vehicle]")).toHaveCount(1);
  await expect(action(page)).toContainText(calendarLine(cell.indicators.rain_onset_day.trend));

  // R: replay the recorded session, or say there is none
  await page.keyboard.press("r");
  if (hasReplay) {
    await expect(banner(page).getByText("REPLAY", { exact: true })).toBeVisible();
    await page.keyboard.press("r");
    await expect(banner(page).getByText("REPLAY", { exact: true })).toHaveCount(0);
  } else {
    await expect(page.getByText("No replay recorded yet")).toBeVisible();
    await expect(banner(page).getByText("SIMULATION", { exact: true })).toBeVisible();
  }

  // back one step and forward again, still on the keyboard
  await page.keyboard.press("ArrowLeft");
  await expectStep(page, 5, "Check the ground.", "GROUND", "Verify");
  await page.keyboard.press("ArrowRight");
  await expectStep(page, 6, "Act.", "ACTION", "Act");

  await page.waitForLoadState("networkidle");
  expect(seen.foreign).toEqual([]);
  expect(seen.errors).toEqual([]);
});
