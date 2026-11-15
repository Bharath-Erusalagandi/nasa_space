import { expect, test, type Page } from "@playwright/test";
import { PRODUCT_NAME } from "../lib/brand";

// files the app asks for that are absent until the team records them
const OPTIONAL = /\/(validation\/results|pod\/replay)\.json$/;

function watch(page: Page) {
  const errors: string[] = [];
  const foreign: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !OPTIONAL.test(msg.location().url)) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol.startsWith("http") && !["localhost", "127.0.0.1"].includes(url.hostname)) foreign.push(req.url());
  });
  return { errors, foreign };
}

const picker = (page: Page) => page.getByRole("combobox", { name: "Place" });

test.use({ viewport: { width: 1920, height: 1080 } });

test("the frame shows the product, the panels and Katete", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/mission/");
  await expect(page.getByRole("heading", { name: PRODUCT_NAME })).toBeVisible();
  for (const [word, title] of [["Act", "ACTION"], ["Verify", "GROUND"], ["Detect", "SKY"]]) {
    await page.getByRole("banner").getByRole("button", { name: word }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2 })).toHaveCount(1);
  }
  await expect(picker(page)).toHaveValue("Katete");
  await expect(page).toHaveURL(/\?place=katete$/);
  const scroll = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight]);
  expect(scroll).toEqual([1920, 1080]);
  await page.waitForLoadState("networkidle");
  expect(seen.errors).toEqual([]);
  expect(seen.foreign).toEqual([]);
});

test("typing a place selects it, updates the address and survives a reload", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/mission/");
  await expect(picker(page)).toHaveValue("Katete");
  await picker(page).fill("Chipata");
  await page.getByRole("option", { name: "Chipata", exact: true }).click();
  await expect(page).toHaveURL(/\?place=chipata$/);
  await expect(picker(page)).toHaveValue("Chipata");
  await page.reload();
  await expect(picker(page)).toHaveValue("Chipata");
  await expect(page).toHaveURL(/\?place=chipata$/);
  await page.waitForLoadState("networkidle");
  expect(seen.errors).toEqual([]);
  expect(seen.foreign).toEqual([]);
});

test("story mode steps with the arrow keys and stops at both ends", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/mission/?story=1");
  const step = page.getByLabel(/^Story step/);
  await expect(step).toHaveText("1 / 6");
  await expect(picker(page)).toHaveValue("Katete");
  await page.locator("body").click({ position: { x: 960, y: 1000 } });
  await page.keyboard.press("ArrowRight");
  await expect(step).toHaveText("2 / 6");
  for (let i = 0; i < 8; i++) await page.keyboard.press("ArrowRight");
  await expect(step).toHaveText("6 / 6");
  for (let i = 0; i < 8; i++) await page.keyboard.press("ArrowLeft");
  await expect(step).toHaveText("1 / 6");
  await page.keyboard.press("ArrowLeft");
  await expect(step).toHaveText("1 / 6");
  await page.waitForLoadState("networkidle");
  expect(seen.errors).toEqual([]);
  expect(seen.foreign).toEqual([]);
});

test("the theme toggle switches the theme and the choice survives a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await page.goto("/mission/");
  const html = page.locator("html");
  await expect(html).not.toHaveClass(/\bdark\b/);
  await page.getByRole("group", { name: "Theme" }).getByRole("button", { name: "Use dark mode" }).click();
  await expect(html).toHaveClass(/\bdark\b/);
  await page.reload();
  await expect(html).toHaveClass(/\bdark\b/);
  await expect(page.getByRole("button", { name: "Use dark mode" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Use light mode" }).click();
  await expect(html).not.toHaveClass(/\bdark\b/);
  await page.reload();
  await expect(html).not.toHaveClass(/\bdark\b/);
});
