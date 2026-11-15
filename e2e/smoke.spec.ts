import { expect, test } from "@playwright/test";
import { PRODUCT_NAME } from "../lib/brand";

test("mission view loads offline from the static build with no failed request and no console error", async ({ page }) => {
  const errors: string[] = [];
  const foreign: string[] = [];
  const failed: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("requestfailed", (req) => failed.push(req.url()));
  page.on("response", (res) => {
    if (res.status() >= 400) failed.push(`${res.status()} ${res.url()}`);
  });
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol.startsWith("http") && !["localhost", "127.0.0.1"].includes(url.hostname)) foreign.push(req.url());
  });

  await page.goto("/mission/");
  await expect(page.getByRole("heading", { name: PRODUCT_NAME })).toBeVisible();
  await page.waitForLoadState("networkidle");

  expect(errors).toEqual([]);
  expect(failed).toEqual([]);
  expect(foreign).toEqual([]);
  await page.getByRole("banner").getByRole("button", { name: "Verify" }).click();
  await expect(page.getByRole("region", { name: "GROUND" }).getByRole("heading", { name: "Patient check" })).toBeVisible();
});

test("the root sends the visitor to the mission view", async ({ page }) => {
  await page.goto("/");
  // the mission view adds the selected place to the address as soon as the index loads
  await expect(page).toHaveURL(/\/mission\/(\?place=[\w-]+)?$/);
});
