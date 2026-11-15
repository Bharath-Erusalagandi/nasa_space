import { expect, test, type Page } from "@playwright/test";

const ground = (page: Page) => page.getByRole("region", { name: "GROUND" });

test("a held-out recording played from its card is scored by the model and opens the conversation", async ({ page }) => {
  await page.goto("/mission/");
  await page.getByRole("banner").getByRole("button", { name: "Verify" }).click();
  await ground(page).getByRole("button", { name: "Play a recording of Anopheles arabiensis" }).click();
  const heard = ground(page).locator("[data-heard]");
  await expect(heard).toHaveCount(1, { timeout: 20_000 });
  await expect(heard).toContainText(/recording \d\d:\d\d, [A-Z][a-z]+ \d+%/);
  await expect(ground(page).getByRole("group", { name: "Conversation" })).toContainText("This recording is a mosquito");
});
